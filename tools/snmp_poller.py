"""SNMP poller (Task 8).

Poll a network device's SNMP agent (snmpd) every POLL_SECS and store one
row per poll in db/telemetry.db -> snmp_stats: CPU load, memory usage,
interface octet counters and bandwidth derived from octet deltas.

This is pull-based, coarse monitoring -- the baseline that streaming
telemetry (INT/gNMI) was invented to replace.

OIDs polled (community "public", SNMPv2c):
  load:   1.3.6.1.4.1.2021.10.1.5.1   laLoadInt1 (1-min load * 100)
  mem:    1.3.6.1.4.1.2021.4.6.0      memTotalReal
          1.3.6.1.4.1.2021.4.5.0      memAvailReal
  iface:  1.3.6.1.2.1.2.2.1.10        ifInOctets.<idx>  (bulk walk)
          1.3.6.1.2.1.2.2.1.16        ifOutOctets.<idx> (bulk walk)
  uptime: 1.3.6.1.2.1.1.3.0           sysUpTime (hundredths of a second)

The active (emulated) interface is the one with the largest octet count,
matching the traffic-bearing host NIC. Bandwidth comes from octet deltas
between polls, like the sFlow collector (task 06).

Usage:
  python3 tools/snmp_poller.py                       # poll every 5s forever
  python3 tools/snmp_poller.py --duration 60
  python3 tools/snmp_poller.py --host 10.0.1.4 --port 161 --community public
  python3 tools/snmp_poller.py --poll-once           # single read, print, exit
  python3 tools/snmp_poller.py --selftest            # math + DB check, no agent
"""

import argparse
import asyncio
import os
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, "db"))
from telemetry import cleanup_table, insert_row  # noqa: E402

from pysnmp.hlapi.v3arch.asyncio import (  # noqa: E402
    CommunityData, ContextData, NoSuchInstance, NoSuchObject,
    ObjectIdentity, ObjectType, SnmpEngine, UdpTransportTarget,
    bulk_walk_cmd, get_cmd,
)

POLL_SECS = 5
OID_LOAD = ObjectIdentity("1.3.6.1.4.1.2021.10.1.5.1")
OID_MEM_TOTAL = ObjectIdentity("1.3.6.1.4.1.2021.4.6.0")
OID_MEM_AVAIL = ObjectIdentity("1.3.6.1.4.1.2021.4.5.0")
OID_UPTIME = ObjectIdentity("1.3.6.1.2.1.1.3.0")
OID_IF_IN = "1.3.6.1.2.1.2.2.1.10"
OID_IF_OUT = "1.3.6.1.2.1.2.2.1.16"


def num(value):
    """int() a varbind value; None for no-such instances."""
    if isinstance(value, (NoSuchInstance, NoSuchObject)):
        return None
    return int(value)


def build_row(load, mem_total, mem_avail, uptime, if_in, if_out,
              bw_in_mbps, bw_out_mbps, ts, device):
    """Pure row construction (used by selftest with synthetic values)."""
    cpu_load = load / 100.0 if load is not None else None
    mem_used_pct = None
    if mem_total and mem_avail is not None:
        mem_used_pct = (mem_total - mem_avail) / mem_total * 100.0
        # Some agents report avail > total (e.g. reclaimable cache on WSL2);
        # clamp so the metric stays in the 0-100 range.
        mem_used_pct = max(0.0, min(100.0, mem_used_pct))
    return dict(ts=ts, device=device, cpu_load=cpu_load,
                mem_used_pct=mem_used_pct, if_octets_in=if_in,
                if_octets_out=if_out, bw_in_mbps=bw_in_mbps,
                bw_out_mbps=bw_out_mbps, uptime=uptime)


class BandwidthTracker:
    """Per-device octet deltas -> Mb/s between polls."""

    def __init__(self):
        self.last = {}  # device -> (ts, in_octets, out_octets)

    def update(self, device, in_octets, out_octets):
        now = time.monotonic()
        prev = self.last.get(device)
        in_mbps = out_mbps = 0.0
        if prev and in_octets is not None and out_octets is not None:
            dt = now - prev[0]
            if dt > 0:
                in_mbps = max(in_octets - prev[1], 0) * 8 / dt / 1e6
                out_mbps = max(out_octets - prev[2], 0) * 8 / dt / 1e6
        self.last[device] = (now, in_octets, out_octets)
        return in_mbps, out_mbps


async def fetch_scalars(engine, community, target):
    """GET laLoadInt1/memTotalReal/memAvailReal/sysUpTime in one request."""
    ei, es, _, var_binds = await get_cmd(
        engine, community, target, ContextData(),
        ObjectType(OID_LOAD), ObjectType(OID_MEM_TOTAL),
        ObjectType(OID_MEM_AVAIL), ObjectType(OID_UPTIME))
    if ei:
        raise RuntimeError("SNMP get failed: %s" % ei)
    if es:
        raise RuntimeError("SNMP error: %s" % es)
    load = num(var_binds[0][1])
    mem_total = num(var_binds[1][1])
    mem_avail = num(var_binds[2][1])
    uptime = num(var_binds[3][1])
    return load, mem_total, mem_avail, uptime


async def walk_octets(engine, community, target, base):
    """BULK walk ifInOctets/ifOutOctets -> {ifIndex: octets}."""
    rows = {}
    async for ei, es, _, var_binds in bulk_walk_cmd(
            engine, community, target, ContextData(), 0, 50,
            ObjectType(ObjectIdentity(base))):
        if ei:
            raise RuntimeError("SNMP walk failed: %s" % ei)
        if es:
            raise RuntimeError("SNMP error: %s" % es)
        for oid, value in var_binds:
            oid_s = str(oid)
            if not oid_s.startswith(base + "."):
                continue
            value = num(value)
            if value is not None:
                rows[int(oid_s.rsplit(".", 1)[1])] = value
    return rows


async def collect(engine, community, target, tracker, device):
    """One poll cycle -> row dict (bandwidth from deltas since last poll)."""
    load, mem_total, mem_avail, uptime = await fetch_scalars(
        engine, community, target)
    if_in_map = await walk_octets(engine, community, target, OID_IF_IN)
    if_out_map = await walk_octets(engine, community, target, OID_IF_OUT)
    # The emulated interface is the traffic-bearing one (largest octets).
    idx = max(set(if_in_map) | set(if_out_map),
              key=lambda i: if_in_map.get(i, 0) + if_out_map.get(i, 0),
              default=None)
    if idx is None:
        raise RuntimeError("no interface counters found")
    if_in = if_in_map.get(idx)
    if_out = if_out_map.get(idx)
    bw_in, bw_out = tracker.update(device, if_in, if_out)
    return build_row(load, mem_total, mem_avail, uptime, if_in, if_out,
                     bw_in, bw_out, int(time.time()), device)


async def poll_once(args):
    engine = SnmpEngine()
    community = CommunityData(args.community, mpModel=1)
    target = await UdpTransportTarget.create(
        (args.host, args.port), timeout=args.timeout, retries=1)
    try:
        row = await collect(engine, community, target,
                            BandwidthTracker(), args.host)
        print("  %s cpu=%.2f mem=%.1f%% in=%s out=%s bw_in=%.3f bw_out=%.3f "
              "uptime=%s" % (args.host, row["cpu_load"] or 0,
                             row["mem_used_pct"] or 0, row["if_octets_in"],
                             row["if_octets_out"], row["bw_in_mbps"],
                             row["bw_out_mbps"], row["uptime"]))
    finally:
        engine.transportDispatcher.close_dispatcher()


async def run_poller(args):
    engine = SnmpEngine()
    community = CommunityData(args.community, mpModel=1)
    target = await UdpTransportTarget.create(
        (args.host, args.port), timeout=args.timeout, retries=1)
    tracker = BandwidthTracker()
    t0 = time.time()
    n = 0
    print("SNMP poller: %s:%d community=%s every %ds"
          % (args.host, args.port, args.community, args.interval))
    while args.duration == 0 or time.time() - t0 < args.duration:
        start = time.monotonic()
        try:
            row = await collect(engine, community, target, tracker, args.host)
            insert_row("snmp_stats", row)
            n += 1
            print("  [%d] %s cpu=%.2f mem=%.1f%% in=%s out=%s "
                  "bw_in=%.3f bw_out=%.3f uptime=%s"
                  % (n, args.host, row["cpu_load"] or 0,
                     row["mem_used_pct"] or 0, row["if_octets_in"],
                     row["if_octets_out"], row["bw_in_mbps"],
                     row["bw_out_mbps"], row["uptime"]), flush=True)
        except Exception as exc:
            print("  poll %d failed: %s" % (n + 1, exc), flush=True)
        await asyncio.sleep(max(0.5, args.interval - (time.monotonic() - start)))
    print("done: %d polls" % n)
    engine.transportDispatcher.close_dispatcher()


def selftest():
    """Synthetic varbind values through build_row + tracker, verify DB."""
    from telemetry import get_conn

    conn = get_conn()
    conn.execute("DELETE FROM snmp_stats")
    conn.commit()
    conn.close()

    row1 = build_row(1523, 1000000, 250000, 123456,
                     1_000_000, 2_000_000, 0.0, 0.0,
                     int(time.time()), "10.0.1.4")
    assert abs(row1["cpu_load"] - 15.23) < 1e-9
    assert abs(row1["mem_used_pct"] - 75.0) < 1e-9
    assert row1["if_octets_in"] == 1_000_000
    assert row1["uptime"] == 123456

    tracker = BandwidthTracker()
    bw_in, bw_out = tracker.update("10.0.1.4", 1_000_000, 2_000_000)
    assert bw_in == 0.0 and bw_out == 0.0
    time.sleep(1.1)
    bw_in, bw_out = tracker.update("10.0.1.4", 5_000_000, 10_000_000)
    assert 0 < bw_in < 100 and 0 < bw_out < 200, (bw_in, bw_out)
    print("  bw delta: in=%.2f Mb/s out=%.2f Mb/s" % (bw_in, bw_out))

    row2 = build_row(1523, 1000000, 250000, 123456,
                     5_000_000, 10_000_000, bw_in, bw_out,
                     int(time.time()), "10.0.1.4")
    insert_row("snmp_stats", row1)
    insert_row("snmp_stats", row2)

    conn = get_conn()
    rows = list(conn.execute(
        "SELECT device, cpu_load, mem_used_pct, if_octets_in, if_octets_out, "
        "bw_in_mbps, bw_out_mbps, uptime FROM snmp_stats ORDER BY ts"))
    conn.close()
    assert len(rows) == 2, rows
    assert rows[0][0] == "10.0.1.4" and abs(rows[0][1] - 15.23) < 1e-9
    assert rows[0][2] == 75.0 and rows[1][4] == 10_000_000
    print("selftest OK: %s -> %s" % (tuple(rows[0]), tuple(rows[1])))


def main():
    ap = argparse.ArgumentParser(description="SNMP poller (pull-based)")
    ap.add_argument("--host", default="10.0.1.4", help="agent address")
    ap.add_argument("--port", type=int, default=161)
    ap.add_argument("--community", default="public")
    ap.add_argument("--interval", type=float, default=POLL_SECS,
                    help="poll interval in seconds")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="run for N seconds (0 = forever)")
    ap.add_argument("--timeout", type=float, default=3.0,
                    help="per-request timeout in seconds")
    ap.add_argument("--poll-once", action="store_true",
                    help="single poll, print, exit")
    ap.add_argument("--selftest", action="store_true",
                    help="math + DB check with synthetic values")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.poll_once:
        asyncio.run(poll_once(args))
        return

    cleanup_table("snmp_stats")
    asyncio.run(run_poller(args))
    cleanup_table("snmp_stats")


if __name__ == "__main__":
    main()
