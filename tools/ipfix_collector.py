"""IPFIX (NetFlow v10) collector (Task 7).

Listens for IPFIX datagrams (UDP/9996) exported by softflowd, learns
dynamic templates (set_id 2), decodes data sets (set_id = template id)
and stores one row per flow record in db/telemetry.db -> ipfix_flows.

Message layout (big-endian):
  header (16 bytes): version(2)=10 length(2) export_time(4) seq(4) domain(4)
  set: set_id(2) set_len(2) records...
    set_id 2: template set; each template: template_id(2) field_count(2)
              then field_count x (ie_id(2) length(2))
    set_id >= 256: data set for that template; records are padded to
              4-byte boundaries.

Information elements used:
  1=octetDeltaCount 2=packetDeltaCount 4=protocolIdentifier
  7=sourceTransportPort 8=sourceIPv4Address 11=destinationTransportPort
  12=destinationIPv4Address 150/152=flowStart 151/153=flowEnd

Usage:
  python3 tools/ipfix_collector.py                  # run forever
  python3 tools/ipfix_collector.py --duration 60
  python3 tools/ipfix_collector.py --selftest       # synthetic datagrams
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

IPFIX_PORT = 9996
FLUSH_SECS = 0.5
FLUSH_ROWS = 5000

IE_COL = {1: "bytes", 2: "packets", 21: "packets", 22: "bytes",
          4: "proto", 7: "src_port", 8: "src_ip", 11: "dst_port",
          12: "dst_ip", 27: "src_ip", 28: "dst_ip",
          150: "first_ts", 151: "last_ts",
          152: "first_ts", 153: "last_ts"}

COLUMNS = ("src_ip", "dst_ip", "src_port", "dst_port", "proto",
           "packets", "bytes", "first_ts", "last_ts")


def ipstr(b):
    return "%d.%d.%d.%d" % tuple(b)


def ip6str(b):
    """16-byte IPv6 address -> compact hex string."""
    words = [struct.unpack_from("!H", b, i)[0] for i in range(0, 16, 2)]
    groups = ["%x" % w for w in words]
    s = ":".join(groups)
    # collapse the longest run of zero groups
    best, blen = 0, 0
    cur, clen = None, 0
    for i, g in enumerate(groups + [None]):
        if g == "0":
            if cur is None:
                cur, clen = i, 1
            else:
                clen += 1
        else:
            if clen > blen:
                best, blen = cur, clen
            cur, clen = None, 0
    if blen > 1:
        s = ":".join(groups[:best]) + "::" + ":".join(groups[best + blen:])
    return s or "::"


def parse_template(rec):
    """Template set body -> list of (template_id, [(ie_id, len), ...])."""
    templates = []
    off = 0
    while off + 4 <= len(rec):
        tid, fcount = struct.unpack_from("!HH", rec, off)
        off += 4
        fields = []
        for _ in range(fcount):
            if off + 4 > len(rec):
                break
            fields.append(struct.unpack_from("!HH", rec, off))
            off += 4
        templates.append((tid, fields))
    return templates


def parse_value(ie, raw):
    if ie == 8:
        return ipstr(raw[:4])
    if ie == 12:
        return ipstr(raw[:4])
    if ie == 27:
        return ip6str(raw[:16])
    if ie == 28:
        return ip6str(raw[:16])
    if ie in (7, 11):
        return struct.unpack("!H", raw)[0] if len(raw) >= 2 else None
    if ie == 4:
        return raw[0] if raw else None
    if ie in (1, 2, 21, 22):  # octets/packets: softflowd may use 4 or 8 bytes
        if len(raw) >= 8:
            return struct.unpack("!Q", raw)[0]
        if len(raw) >= 4:
            return struct.unpack("!I", raw)[0]
        return None
    if ie in (150, 151, 152, 153):  # flow start/end (sec or msec)
        if len(raw) >= 8:
            return struct.unpack("!Q", raw)[0]
        if len(raw) >= 4:
            return struct.unpack("!I", raw)[0]
        return None
    return None


def parse_record(body, off, fields):
    """Decode one data record -> (row dict, offset after record, padded)."""
    row = {}
    for ie, flen in fields:
        if off >= len(body):
            break
        if flen == 65535:  # variable-length field: 1- or 2-byte length prefix
            n = body[off]
            if n == 255:
                if off + 2 > len(body):
                    break
                n = struct.unpack_from("!H", body, off + 1)[0]
                off += 2
            else:
                off += 1
            raw = body[off:off + n]
            off += n
        else:
            raw = body[off:off + flen]
            off += flen
        if flen != 65535 and len(raw) < flen:
            break
        col = IE_COL.get(ie)
        if col:
            row[col] = parse_value(ie, raw)
    for col in COLUMNS:
        row.setdefault(col, None)
    return row, off


def parse_datagram(data, templates):
    """IPFIX message -> ([row dicts], [new templates (tid, fields)]).

    New templates become visible to data sets later in the same message.
    """
    if len(data) < 16:
        return [], []
    version, length = struct.unpack_from("!HH", data, 0)
    if version != 10:
        return [], []
    end = min(length, len(data)) if length else len(data)
    rows = []
    new_templates = []
    known = dict(templates)
    off = 16
    while off + 4 <= end:
        sid, slen = struct.unpack_from("!HH", data, off)
        if slen < 4 or off + slen > len(data):
            break
        body = data[off + 4:off + slen]
        off += slen
        if sid == 2:  # template set
            for tid, fields in parse_template(body):
                if fields:
                    known[tid] = fields
                    new_templates.append((tid, fields))
        elif sid == 3:  # options template set: skip
            continue
        else:  # data set for template sid
            fields = known.get(sid)
            if not fields:
                continue
            fixed_len = sum(f[1] for f in fields if f[1] != 65535)
            o = 0
            # softflowd packs data records back-to-back without per-record
            # padding (verified on the wire); leftover < fixed_len is set pad.
            while o + fixed_len <= len(body):
                row, nxt = parse_record(body, o, fields)
                if nxt <= o:  # no progress (truncated)
                    break
                if row:
                    rows.append(row)
                o = nxt
    return rows, new_templates


def run(duration=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", IPFIX_PORT))
    sock.settimeout(1.0)
    templates = {}
    buf = []
    last_flush = time.time()
    total = 0
    t0 = time.time()
    print("IPFIX collector: listening on 0.0.0.0:%d" % IPFIX_PORT)
    while duration == 0 or time.time() - t0 < duration:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            data = None
        if data:
            rows, new_templates = parse_datagram(data, templates)
            for tid, fields in new_templates:
                if fields:
                    templates[tid] = fields
                    print("  template %d: %s" % (
                        tid, ", ".join("IE%d=%dB" % (ie, l)
                                       for ie, l in fields)), flush=True)
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
            insert_rows("ipfix_flows", buf)
            buf[:] = []
        return time.time()
    return last_flush


def _make_datagram(count=2):
    tid = 256
    fields = [(8, 4), (12, 4), (7, 2), (11, 2), (4, 1), (1, 8), (2, 8),
              (153, 8)]
    tpl = struct.pack("!HH", tid, len(fields)) + b"".join(
        struct.pack("!HH", *f) for f in fields)
    tset = struct.pack("!HH", 2, 4 + len(tpl)) + tpl

    def rec(src_ip, dst_ip, sport, dport, proto, octets, packets, end):
        return (bytes(src_ip) + bytes(dst_ip) +
                struct.pack("!HH", sport, dport) + bytes([proto]) +
                struct.pack("!QQ", octets, packets) + struct.pack("!Q", end))

    recs = [rec([10, 0, 1, 1], [10, 0, 1, 4], 5001, 5201, 6, 50000, 1000,
                60000),
            rec([10, 0, 1, 2], [10, 0, 1, 4], 5002, 5202, 17, 8000, 200,
                70000)]
    assert len(recs[0]) == 37  # no padding: softflowd packs records tightly
    body = struct.pack("!HH", tid, 4 + len(recs[0]) + len(recs[1])) + \
        b"".join(recs)
    hdr = struct.pack("!HHIII", 10, 16 + len(tset) + len(body),
                      1000000, 1, 0)
    return hdr + tset + body


def selftest():
    """Feed synthetic IPFIX messages through the parser, verify DB."""
    from telemetry import get_conn

    conn = get_conn()
    conn.execute("DELETE FROM ipfix_flows")
    conn.commit()
    conn.close()

    templates = {}
    data = _make_datagram()
    rows, new_templates = parse_datagram(data, templates)
    assert len(new_templates) == 1, new_templates
    tid, fields = new_templates[0]
    assert tid == 256 and len(fields) == 8
    templates[tid] = fields

    rows, _ = parse_datagram(data, templates)
    assert len(rows) == 2, rows
    assert rows[0]["src_ip"] == "10.0.1.1" and rows[0]["dst_ip"] == "10.0.1.4"
    assert rows[0]["src_port"] == 5001 and rows[0]["dst_port"] == 5201
    assert rows[0]["proto"] == 6
    assert rows[0]["bytes"] == 50000 and rows[0]["packets"] == 1000
    assert rows[0]["last_ts"] == 60000
    assert rows[1]["proto"] == 17 and rows[1]["bytes"] == 8000
    bad = struct.pack("!HHIII", 9, 16, 0, 0, 0)
    assert parse_datagram(bad, templates) == ([], [])

    for r in rows:
        r["ts"] = int(time.time())
    insert_rows("ipfix_flows", rows)

    conn = get_conn()
    got = list(conn.execute(
        "SELECT src_ip, dst_ip, src_port, dst_port, proto, packets, bytes "
        "FROM ipfix_flows ORDER BY ts"))
    conn.close()
    assert len(got) == 2, got
    assert got[0][0] == "10.0.1.1" and got[0][5] == 1000
    print("selftest OK: rows=%s" % (tuple(got[0]),))


def main():
    ap = argparse.ArgumentParser(description="IPFIX (NetFlow v10) collector")
    ap.add_argument("--selftest", action="store_true",
                    help="feed synthetic datagrams and exit (no socket)")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="run for N seconds (0 = forever)")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    cleanup_table("ipfix_flows")
    run(args.duration)
    cleanup_table("ipfix_flows")


if __name__ == "__main__":
    main()
