"""NetFlow v5 collector (Task 7).

Listens for NetFlow v5 datagrams (UDP/9995) exported by softflowd,
parses the fixed 48-byte flow records and stores one row per flow in
db/telemetry.db -> netflow_flows.

Datagram layout (big-endian):
  header (24 bytes): version(2) count(2) uptime(4) epoch(4) seq(4)
                     src(4) dst(4)
  record (48 bytes): src_ip(4) dst_ip(4) next_hop(4) if_in(2) if_out(2)
                     dPkts(4) dOctets(4) first(4) last(4) src_port(2)
                     dst_port(2) pad1(1) tcp_flags(1) prot(1) tos(1)
                     src_as(2) dst_as(2) src_mask(1) dst_mask(1) pad2(2)

Usage:
  python3 tools/netflow_collector.py                  # run forever
  python3 tools/netflow_collector.py --duration 60
  python3 tools/netflow_collector.py --selftest       # synthetic datagrams
"""

import argparse
import os
import socket
import struct
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, "db"))
from telemetry import cleanup_table, insert_rows  # noqa: E402

NETFLOW_PORT = 9995
FLUSH_SECS = 0.5
FLUSH_ROWS = 5000

HDR = struct.Struct("!HHIIIII")                 # 24 bytes
REC = struct.Struct("!4s4s4sHHIIIIHHBBBBHHBBH")  # 48 bytes


def ipstr(b):
    return "%d.%d.%d.%d" % tuple(b)


def parse_datagram(data):
    """NetFlow v5 datagram -> list of row dicts (or None if invalid)."""
    if len(data) < 24:
        return None
    version, count = struct.unpack_from("!HH", data, 0)
    if version != 5:
        return None
    if len(data) < 24 + count * REC.size:
        return None
    rows = []
    for i in range(count):
        off = 24 + i * REC.size
        f = REC.unpack_from(data, off)
        rows.append(dict(
            src_ip=ipstr(f[0]), dst_ip=ipstr(f[1]),
            src_port=f[9], dst_port=f[10],
            proto=f[13], tcp_flags=f[12],
            packets=f[5], bytes=f[6],
            first_ts=f[7], last_ts=f[8]))
    return rows


def run(duration=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", NETFLOW_PORT))
    sock.settimeout(1.0)
    buf = []
    last_flush = time.time()
    total = 0
    t0 = time.time()
    print("NetFlow v5 collector: listening on 0.0.0.0:%d" % NETFLOW_PORT)
    while duration == 0 or time.time() - t0 < duration:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            data = None
        if data:
            rows = parse_datagram(data)
            if rows:
                now = int(time.time())
                for r in rows:
                    r["ts"] = now
                buf.extend(rows)
                total += 1
                if len(buf) >= FLUSH_ROWS:
                    last_flush = flush(buf, last_flush, force=True)
        else:
            last_flush = flush(buf, last_flush)
        if total % 100 == 0 and total:
            print("  datagrams: %d, buffered rows: %d" %
                  (total, len(buf)), flush=True)
    flush(buf, last_flush, force=True)
    print("done: %d datagrams" % total)


def flush(buf, last_flush, force=False):
    if force or (buf and time.time() - last_flush > FLUSH_SECS):
        if buf:
            insert_rows("netflow_flows", buf)
            buf[:] = []
        return time.time()
    return last_flush


def _make_datagram(count=2):
    recs = []
    for i in range(count):
        recs.append(REC.pack(
            bytes([10, 0, 1, 1 + i]), bytes([10, 0, 1, 4]), b"\x00\x00\x00\x00",
            2, 1,
            100 + i, 10000 + i * 1000,   # dPkts, dOctets
            5000 + i, 6000 + i,          # first, last
            5001, 5201, 0, 0x1B, 6, 0,   # ports, pad, tcp_flags, proto, tos
            0, 0, 0, 0, 0))             # as, masks, pad
    hdr = struct.pack("!HHIIIII", 5, count, 10000, 1000000, 42,
                      0x0A000001, 0x0A000001)
    return hdr + b"".join(recs)


def selftest():
    """Feed synthetic v5 datagrams through the parser, verify DB."""
    from telemetry import get_conn

    conn = get_conn()
    conn.execute("DELETE FROM netflow_flows")
    conn.commit()
    conn.close()

    data = _make_datagram()
    rows = parse_datagram(data)
    assert rows is not None and len(rows) == 2, rows
    assert rows[0]["src_ip"] == "10.0.1.1" and rows[0]["dst_ip"] == "10.0.1.4"
    assert rows[0]["src_port"] == 5001 and rows[0]["dst_port"] == 5201
    assert rows[0]["proto"] == 6 and rows[0]["tcp_flags"] == 0x1B
    assert rows[0]["packets"] == 100 and rows[0]["bytes"] == 10000
    assert rows[1]["src_ip"] == "10.0.1.2"
    bad = struct.pack("!HHIIIII", 7, 1, 0, 0, 0, 0, 0)  # version != 5
    assert parse_datagram(bad) is None
    assert parse_datagram(b"") is None

    for r in rows:
        r["ts"] = int(time.time())
    insert_rows("netflow_flows", rows)

    conn = get_conn()
    got = list(conn.execute(
        "SELECT src_ip, dst_ip, src_port, dst_port, proto, packets, bytes "
        "FROM netflow_flows ORDER BY ts"))
    conn.close()
    assert len(got) == 2, got
    assert got[0][0] == "10.0.1.1" and got[0][6] == 10000
    print("selftest OK: rows=%s" % (tuple(got[0]),))


def main():
    ap = argparse.ArgumentParser(description="NetFlow v5 collector")
    ap.add_argument("--selftest", action="store_true",
                    help="feed synthetic datagrams and exit (no socket)")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="run for N seconds (0 = forever)")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    cleanup_table("netflow_flows")
    run(args.duration)
    cleanup_table("netflow_flows")


if __name__ == "__main__":
    main()
