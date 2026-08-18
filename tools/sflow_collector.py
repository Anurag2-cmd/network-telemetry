"""sFlow v5 collector (Task 6).

Listens for sFlow v5 datagrams (UDP/6343) exported by Open vSwitch,
parses flow samples (raw packet headers -> L3/L4 tuple, in/out port)
and interface counter samples (octets -> bandwidth since last poll),
and stores one row per sample in db/telemetry.db -> sflow_samples.

Datagram layout (sFlow v5, big-endian):
  version(4) agent_addr_type(4) agent(4) sub_agent_id(4) sequence(4)
  uptime(4) num_samples(4)
  sample: type(4) length(4) body...
    type 1 flow sample: seq(4) source_id(4) rate(4) pool(4) drops(4)
                        input(4) output(4) num_records(4) records...
                        (input/output pack format+value in one word:
                         0x00000000|x = ifIndex x, 0x80000000|c = flooded to c)
    type 2 counters sample: seq(4) source_id(4) num_records(4) records...
    record: type(4) length(4) data (padded to 4 bytes)
      type 1 (raw packet header): protocol(4) frame_len(4) stripped(4)
                                  header_len(4) header bytes...
      type 1 (generic counters, inside counters sample): ifIndex(4) ifType(4)
        ifSpeed(8) ifDirection(4) ifStatus(4) ifInOctets(8) ifInUcastPkts(4)
        ifInMulticastPkts(4) ifInBroadcastPkts(4) ifInDiscards(4)
        ifInErrors(4) ifInUnknownProtos(4) ifOutOctets(8) ifOutUcastPkts(4)
        ifOutMulticastPkts(4) ifOutBroadcastPkts(4) ifOutDiscards(4)
        ifOutErrors(4) ifPromiscuousMode(4)

Usage:
  sudo python3 tools/sflow_collector.py              # run forever
  sudo python3 tools/sflow_collector.py --duration 60
  python3 tools/sflow_collector.py --selftest        # synthetic datagrams, no socket
"""

import argparse
import socket
import struct
import sys
import time

sys.path.insert(0, "db")
from telemetry import cleanup_table, insert_rows  # noqa: E402

SFLOW_PORT = 6343
FLUSH_SECS = 0.5
FLUSH_ROWS = 2000


def u32(b, o):
    return struct.unpack_from("!I", b, o)[0]


def u64(b, o):
    return struct.unpack_from("!Q", b, o)[0]


def ipstr(b, o):
    return "%d.%d.%d.%d" % tuple(b[o:o + 4])


def parse_raw_header(rec):
    """raw packet header record -> L3/L4 tuple dict or None."""
    if len(rec) < 16:
        return None
    frame_len = u32(rec, 4)
    header_len = u32(rec, 12)
    hdr = rec[16:16 + header_len]
    if len(hdr) < 14:
        return None
    etype = hdr[12:14]
    if etype == b"\x08\x00":
        eth = 14
    elif etype in (b"\x81\x00", b"\x88\xa8") and len(hdr) >= 18:
        eth = 18  # 802.1Q/QinQ tag
    else:
        return None
    ip = hdr[eth:]
    if len(ip) < 20 or (ip[0] >> 4) != 4:
        return None
    ihl = (ip[0] & 0x0F) * 4
    if len(ip) < ihl + 4:
        return None
    proto = ip[9]
    sport = dport = 0
    if proto in (6, 17) and len(ip) >= ihl + 4:
        sport, dport = struct.unpack_from("!HH", ip, ihl)
    return dict(src_ip=ipstr(ip, 12), dst_ip=ipstr(ip, 16),
                src_port=sport, dst_port=dport, proto=proto,
                bytes_sampled=frame_len)


def parse_records(buf, off, num):
    """Iterate count records starting at off -> [(type, data)], 4-byte aligned."""
    recs = []
    for _ in range(num):
        if off + 8 > len(buf):
            break
        rtype = u32(buf, off)
        rlen = u32(buf, off + 4)
        off += 8
        recs.append((rtype, buf[off:off + rlen]))
        off += (rlen + 3) & ~3
    return recs


def parse_flow_sample(body):
    """Flow sample body -> row dict (flow fields) or None.

    Compact encoding: seq(4) source_id(4) rate(4) pool(4) drops(4)
    input(4) output(4) num_records(4) records...
    input/output pack format+value in one word: 0x00000000|x = ifIndex,
    0x80000000|c = flooded to c interfaces, 0x40000000 = ACL discard.
    """
    if len(body) < 32:
        return None
    rate = u32(body, 8)
    in_port = u32(body, 20) & 0x3FFFFFFF
    out_port = u32(body, 24) & 0x3FFFFFFF
    num = u32(body, 28)
    row = None
    for rtype, data in parse_records(body, 32, num):
        if rtype == 1:  # raw packet header: packet-level visibility
            row = parse_raw_header(data)
            if row:
                break
    if row is None:
        return None
    row["in_port"] = in_port
    row["out_port"] = out_port
    row["sampling_rate"] = rate
    return row


def parse_counters_sample(body):
    """Counters sample body -> list of {if_index, if_in_octets, if_out_octets}."""
    if len(body) < 12:
        return []
    num = u32(body, 8)
    rows = []
    for rtype, data in parse_records(body, 12, num):
        if rtype != 1 or len(data) < 64:  # generic interface counters
            continue
        rows.append(dict(if_index=u32(data, 0),
                         if_in_octets=u64(data, 24),
                         if_out_octets=u64(data, 56)))
    return rows


def parse_datagram(data):
    """sFlow datagram -> (agent, [(kind, payload), ...]) or None."""
    if len(data) < 28 or u32(data, 0) != 5:
        return None
    agent = ipstr(data, 8)  # agent addr type @4 (1=IPv4), address @8
    num_samples = u32(data, 24)
    samples = []
    off = 28
    for _ in range(num_samples):
        if off + 8 > len(data):
            break
        stype = u32(data, off)
        slen = u32(data, off + 4)
        body = data[off + 8:off + 8 + slen]
        off += 8 + ((slen + 3) & ~3)
        if stype == 1:
            samples.append(("flow", parse_flow_sample(body)))
        elif stype == 2:
            samples.append(("counters", parse_counters_sample(body)))
    return agent, samples


class BandwidthTracker:
    """Per (agent, ifIndex) octet deltas -> Mb/s between counter polls."""

    def __init__(self):
        self.last = {}  # (agent, if_index) -> (ts, in_octets, out_octets)

    def update(self, agent, counter):
        key = (agent, counter["if_index"])
        now = time.time()
        prev = self.last.get(key)
        in_mbps = out_mbps = 0.0
        if prev:
            dt = now - prev[0]
            if dt > 0:
                in_mbps = max(counter["if_in_octets"] - prev[1], 0) * 8 / dt / 1e6
                out_mbps = max(counter["if_out_octets"] - prev[2], 0) * 8 / dt / 1e6
        self.last[key] = (now, counter["if_in_octets"], counter["if_out_octets"])
        return in_mbps, out_mbps


def handle_datagram(data, tracker, flow_buf, counter_buf, now):
    parsed = parse_datagram(data)
    if not parsed:
        return
    agent, samples = parsed
    for kind, payload in samples:
        if kind == "flow" and payload:
            row = payload
            row.pop("sampling_rate", None)
            row["ts"] = now
            row["agent"] = agent
            flow_buf.append(row)
        elif kind == "counters":
            for counter in payload:
                in_mbps, out_mbps = tracker.update(agent, counter)
                counter_buf.append(dict(
                    ts=now, agent=agent,
                    if_in_octets=counter["if_in_octets"],
                    if_out_octets=counter["if_out_octets"],
                    bandwidth_in_mbps=in_mbps, bandwidth_out_mbps=out_mbps,
                ))


def flush(buffers, last_flush, force=False):
    if force or (sum(len(b) for b in buffers)
                 and time.time() - last_flush > FLUSH_SECS):
        for buf in buffers:
            if buf:
                insert_rows("sflow_samples", buf)
                buf[:] = []
        return time.time()
    return last_flush


def run(duration=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", SFLOW_PORT))
    sock.settimeout(1.0)
    tracker = BandwidthTracker()
    flow_buf = []
    counter_buf = []
    last_flush = time.time()
    total = 0
    t0 = time.time()
    print("sFlow collector: listening on 0.0.0.0:%d" % SFLOW_PORT)
    while duration == 0 or time.time() - t0 < duration:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            data = None
        if data:
            handle_datagram(data, tracker, flow_buf, counter_buf, int(time.time()))
            total += 1
            if len(flow_buf) + len(counter_buf) >= FLUSH_ROWS:
                last_flush = flush([flow_buf, counter_buf], last_flush, force=True)
        else:
            last_flush = flush([flow_buf, counter_buf], last_flush)
        if total % 500 == 0 and total:
            print("  datagrams: %d, buffered rows: %d" %
                  (total, len(flow_buf) + len(counter_buf)), flush=True)
    last_flush = flush([flow_buf, counter_buf], last_flush, force=True)
    print("done: %d datagrams" % total)


def _raw_header_record():
    eth = b"\x02\x00\x00\x00\x00\x02" + b"\x02\x00\x00\x00\x00\x01" + b"\x08\x00"
    ip = b"\x45\x00\x00\x2c\x00\x00\x00\x00\x40\x06\x00\x00" + \
        bytes([10, 0, 1, 1]) + bytes([10, 0, 1, 2])
    tcp = struct.pack("!HHHH", 5001, 5201, 0, 0)
    pkt = eth + ip + tcp
    rec = struct.pack("!IIII", 1, len(pkt), 0, len(pkt)) + pkt
    return rec + b"\x00" * ((-len(rec)) % 4)


def _make_flow_dgram():
    body = struct.pack("!IIIIIIII",
                       1,          # sequence
                       0x00010001,  # source_id (type 0, index 1)
                       1,          # sampling_rate
                       1,          # sample_pool
                       0,          # drops
                       2,          # input: ifIndex 2
                       3,          # output: ifIndex 3
                       1)          # num_records
    rec = _raw_header_record()
    body += struct.pack("!II", 1, len(rec)) + rec
    dgram = struct.pack("!IIIIIII", 5, 1, 0x0A000001, 0, 1, 1000, 1)
    return dgram + struct.pack("!II", 1, len(body)) + body


def _make_counters_dgram(in_octets, out_octets):
    rec = struct.pack("!IIQII", 1, 6, 1000000000, 1, 1)      # ifIndex..ifStatus
    rec += struct.pack("!Q", in_octets)                      # ifInOctets
    rec += struct.pack("!IIIIII", 0, 0, 0, 0, 0, 0)          # in pkts/discards/errors
    rec += struct.pack("!Q", out_octets)                     # ifOutOctets
    rec += struct.pack("!IIIII", 0, 0, 0, 0, 0)              # out pkts/discards/errors
    rec += struct.pack("!I", 0)                              # ifPromiscuousMode
    assert len(rec) == 88
    body = struct.pack("!III", 1, 0x00010001, 1)
    body += struct.pack("!II", 1, len(rec)) + rec
    dgram = struct.pack("!IIIIIII", 5, 1, 0x0A000001, 0, 2, 2000, 1)
    return dgram + struct.pack("!II", 2, len(body)) + body


def selftest():
    """Feed synthetic flow + counters datagrams through the parser, verify DB."""
    from telemetry import get_conn

    conn = get_conn()
    conn.execute("DELETE FROM sflow_samples")
    conn.commit()
    conn.close()

    flow = parse_datagram(_make_flow_dgram())
    assert flow is not None and flow[0] == "10.0.0.1"
    kind, row = flow[1][0]
    assert kind == "flow" and row is not None, row
    assert row["src_ip"] == "10.0.1.1" and row["dst_ip"] == "10.0.1.2"
    assert row["src_port"] == 5001 and row["dst_port"] == 5201
    assert row["proto"] == 6 and row["bytes_sampled"] == 42
    assert row["in_port"] == 2 and row["out_port"] == 3

    tracker = BandwidthTracker()
    c1 = parse_datagram(_make_counters_dgram(1_000_000, 2_000_000))
    c2 = parse_datagram(_make_counters_dgram(5_000_000, 10_000_000))
    assert c1[1][0][0] == "counters" and c1[1][0][1][0]["if_in_octets"] == 1_000_000
    _, c1c = c1[1][0]
    _, c2c = c2[1][0]
    in0, out0 = tracker.update("10.0.0.1", c1c[0])
    assert in0 == 0.0 and out0 == 0.0
    time.sleep(1.1)
    in1, out1 = tracker.update("10.0.0.1", c2c[0])
    assert 0 < in1 < 100 and 0 < out1 < 200, (in1, out1)
    print("  counters delta: in=%.2f Mb/s out=%.2f Mb/s" % (in1, out1))

    flow_buf, counter_buf = [], []
    handle_datagram(_make_flow_dgram(), tracker, flow_buf, counter_buf,
                    int(time.time()))
    handle_datagram(_make_counters_dgram(1_000_000, 2_000_000), tracker,
                    flow_buf, counter_buf, int(time.time()))
    insert_rows("sflow_samples", flow_buf)
    insert_rows("sflow_samples", counter_buf)

    conn = get_conn()
    rows = list(conn.execute(
        "SELECT src_ip, dst_ip, src_port, dst_port, proto, in_port, out_port "
        "FROM sflow_samples WHERE src_ip IS NOT NULL"))
    counters = list(conn.execute(
        "SELECT if_in_octets, bandwidth_out_mbps FROM sflow_samples "
        "WHERE if_in_octets IS NOT NULL"))
    conn.close()
    assert len(rows) == 1, rows
    assert rows[0][1] == "10.0.1.2" and rows[0][4] == 6
    assert len(counters) == 1 and counters[0][0] == 1_000_000
    print("selftest OK: flow=%s counters=%s" % (tuple(rows[0]), tuple(counters[0])))


def main():
    ap = argparse.ArgumentParser(description="sFlow v5 collector")
    ap.add_argument("--selftest", action="store_true",
                    help="feed synthetic datagrams and exit (no socket)")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="run for N seconds (0 = forever)")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    cleanup_table("sflow_samples")
    run(args.duration)
    cleanup_table("sflow_samples")


if __name__ == "__main__":
    main()
