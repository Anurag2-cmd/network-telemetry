"""INT receiver / parser + telemetry storage (Task 5).

Runs on h2 inside Mininet: sniffs UDP/4000 with scapy, parses the
INT v0.5 header + per-hop metadata stack emitted by p4/int.p4,
computes per-hop latency and jitter, and writes one row per hop to
db/telemetry.db -> int_hops.

INT stack format emitted by the P4 program:
  int_header_t (4 bytes, big-endian):
    byte0: ver(4)=0xF, rep(2), c(1), reserved1(1)   -> 0xF0
    byte1: count
    byte2: length  (= 12 * count)
    byte3: ins
  per-hop entry (12 bytes): switch_id(4) ingress_ts(4) enq_qdepth(2) padding(2)

Timestamp semantics (important): BMv2's ingress_global_timestamp is a
per-switch counter in µs since that switch started, and switches are
NOT time-synchronized. Raw delta ts[i]-ts[i-1] therefore contains a
constant per-pair boot offset (seconds) plus the real forwarding
delay (µs). The first packet of each flow calibrates that offset
(forwarding delay is negligible), and it is subtracted from every
later delta to recover meaningful per-hop latency. Jitter (delta of
deltas) is unaffected by the offset.

Usage:
  sudo python3 tools/int_receiver.py            # sniff forever (h2)
  sudo python3 tools/int_receiver.py --selftest # feed synthetic packets, no sniffing
"""

import argparse
import struct
import sys
import time

from scapy.all import IP, Raw, UDP, sniff

sys.path.insert(0, "db")
from telemetry import cleanup_old_rows, insert_rows  # noqa: E402

UDP_PORT = 4000
ENTRY = struct.Struct("!IIHH")  # switch_id, ingress_ts, enq_qdepth, padding


def parse_int(data):
    """Parse an INT UDP payload -> [(switch_id, ts_us, qdepth)] or None."""
    if len(data) < 4 or (data[0] >> 4) != 0xF:
        return None
    count = data[1]
    length = data[2]
    if length != count * 12 or len(data) < 4 + count * 12:
        return None
    hops = []
    for i in range(count):
        swid, ts, qd, _ = ENTRY.unpack(data[4 + i * 12: 4 + (i + 1) * 12])
        hops.append((swid, ts, qd))
    return hops


def flow_5tuple(pkt):
    return "%s:%d->%s:%d" % (pkt[IP].src, pkt[UDP].sport, pkt[IP].dst, pkt[UDP].dport)


class IntHandler:
    """Sniff callback with per-flow clock-offset calibration."""

    def __init__(self):
        self.offset = {}     # flow -> {hop_idx: calibrated offset for that pair}
        self.last_lat = {}   # flow -> {hop_idx: last corrected latency (jitter)}

    def __call__(self, pkt):
        if not (UDP in pkt and pkt[UDP].dport == UDP_PORT and Raw in pkt):
            return
        hops = parse_int(bytes(pkt[Raw].load))
        if not hops:
            return
        flow = flow_5tuple(pkt)
        cal = self.offset.setdefault(flow, {})
        last = self.last_lat.setdefault(flow, {})
        now = int(time.time())
        rows = []
        for i, (swid, ts, qd) in enumerate(hops):
            raw = float(ts - hops[i - 1][1]) if i > 0 else 0.0
            if i > 0 and i not in cal:
                cal[i] = raw  # first packet: delta ≈ constant clock offset
            lat = max(raw - cal.get(i, 0.0), 0.0) if i > 0 else 0.0
            jit = abs(lat - last[i]) if i in last else 0.0
            last[i] = lat
            rows.append(dict(
                ts=now, flow=flow, hop_idx=i, switch_id=swid,
                ingress_ts=ts, hop_latency_us=lat, jitter_us=jit,
                queue_occupancy=qd,
            ))
        insert_rows("int_hops", rows)


def selftest():
    """Feed two synthetic 2-hop packets through the handler, verify DB."""
    from scapy.all import IP as ScapyIP
    from scapy.all import UDP as ScapyUDP
    from scapy.all import Raw as ScapyRaw
    from telemetry import get_conn
    import time

    conn = get_conn()
    conn.execute("DELETE FROM int_hops")
    conn.commit()
    conn.close()

    h = IntHandler()
    p1 = ScapyIP(src="10.0.1.1", dst="10.0.1.2") / ScapyUDP(sport=5000, dport=4000) / \
        ScapyRaw(bytes([0xF0, 0x02, 0x18, 0x00]) +
                 struct.pack("!IIHH", 1, 1000, 0, 0) +
                 struct.pack("!IIHH", 2, 1320, 7, 0))
    p2 = ScapyIP(src="10.0.1.1", dst="10.0.1.2") / ScapyUDP(sport=5000, dport=4000) / \
        ScapyRaw(bytes([0xF0, 0x02, 0x18, 0x00]) +
                 struct.pack("!IIHH", 1, 1100, 0, 0) +
                 struct.pack("!IIHH", 2, 1430, 7, 0))
    h(p1)
    h(p2)

    conn = get_conn()
    rows = list(conn.execute(
        "SELECT hop_idx, switch_id, hop_latency_us, jitter_us, queue_occupancy "
        "FROM int_hops"))
    conn.close()
    # insertion order: p1h0, p1h1, p2h0, p2h1
    assert len(rows) == 4, rows
    assert rows[0][1] == 1 and rows[0][2] == 0.0           # p1 hop0: baseline
    assert rows[1][1] == 2 and rows[1][2] == 0.0           # p1 hop1: calibrates offset
    assert rows[2][1] == 1 and rows[2][2] == 0.0           # p2 hop0: baseline
    assert rows[3][1] == 2 and rows[3][2] == 10.0          # p2 hop1: 10µs latency
    assert rows[3][3] == 10.0                              # jitter vs p1
    print("selftest OK: rows=%s" % [tuple(r) for r in rows])


def main():
    ap = argparse.ArgumentParser(description="INT receiver/parser")
    ap.add_argument("--selftest", action="store_true",
                    help="feed synthetic packets and exit (no sniffing)")
    ap.add_argument("--iface", default=None, help="interface to sniff on")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    kwargs = {"filter": "udp port %d" % UDP_PORT, "prn": IntHandler(),
              "store": False}
    if args.iface:
        kwargs["iface"] = args.iface

    cleanup_old_rows()
    print("INT receiver: sniffing UDP/%d on %s" %
          (UDP_PORT, args.iface or "default iface"))
    while True:
        sniff(timeout=600, **kwargs)
        cleanup_old_rows()


if __name__ == "__main__":
    main()
