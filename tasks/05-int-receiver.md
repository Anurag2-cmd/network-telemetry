# Task 05: INT receiver/parser + telemetry storage

## Goal
`tools/int_receiver.py` runs on h2 inside Mininet, sniffs UDP/4000,
parses the INT header + per-hop metadata stack, computes per-hop latency
and jitter, and writes rows to `db/telemetry.db` table `int_hops`.

## INT stack format (what the P4 program emits)
```
int_header_t (4 bytes, big-endian):
  byte0: ver=0xF, rep, c, reserved1     (-> 0xF0)
  byte1: count
  byte2: length  (= 12 * count)
  byte3: ins
per-hop entry (12 bytes): switch_id(4) ingress_ts(4µs) enq_qdepth(2) padding(2)
```
Notes (verified on BMv2 1.15.4):
- ingress_ts is BMv2's per-switch µs counter since switch start — NOT
  synchronized across switches. The receiver calibrates the constant
  clock offset from the first packet's delta, then subtracts it.
- The P4 program inserts the entry in the EGRESS pipeline (BMv2 only
  populates standard_metadata.enq_qdepth at enqueue time, i.e. after
  ingress), and sets udp.checksum = 0 (IPv4-legal) because v1model
  cannot recompute the UDP checksum over the modified payload.
- enq_qdepth only grows when the egress queue builds; use
  `set_queue_rate 500` on a switch before bursting to demo the spike.

## Receiver algorithm (scapy)
```python
from scapy.all import sniff, IP, UDP, Raw
def parse_int(pkt):
    if UDP in pkt and pkt[UDP].dport == 4000:
        data = bytes(pkt[Raw].load)
        ver_rep, count, length = data[0], data[3], data[4]
        if (data[0] >> 4) != 0xF: return
        hops = []
        for i in range(count):
            off = 4 + i * 8
            swid, ts, qd = struct.unpack("!IIH", data[off:off+10])
            hops.append((swid, ts, qd))
        # per-hop latency = ts[i] - ts[i-1] (µs, approx; bmv2 timestamps
        # are per-switch, so also record raw deltas and absolute times)
        # jitter = |latency_i - latency_{i-1}|
        # insert one row per hop:
        #   ts, flow_5tuple, hop_idx, switch_id, ingress_ts,
        #   hop_latency_us (delta vs previous hop ts), jitter_us,
        #   queue_occupancy (enq_qdepth)
```

## DB (create `db/telemetry.py` with helpers shared by all collectors)
SQLite at `/mnt/c/Users/ASUS/Desktop/Network telementry/db/telemetry.db`.
```sql
CREATE TABLE IF NOT EXISTS int_hops (
    ts INTEGER, flow TEXT, hop_idx INTEGER, switch_id INTEGER,
    ingress_ts INTEGER, hop_latency_us REAL, jitter_us REAL,
    queue_occupancy INTEGER
);
```
Central helper: `get_conn()` (sqlite3, WAL mode, `timeout=30`), `insert_row(table, dict)`.
Collectors run forever; the dashboard only reads. Cleanup old rows > 24h.

## Running it
In task-04 Mininet:
- `h2: sudo python3 tools/int_receiver.py &`
- `h1: python3 tools/int_sender.py 10.0.1.2` (extend sender to loop 60s, 10 pkt/s,
  so charts get a real stream; add `--burst` mode for queue-occupancy demo:
  1000 packets back-to-back in 1s → enq_qdepth should spike).

## Verification (Definition of Done)
```bash
sqlite3 db/telemetry.db "SELECT switch_id, hop_latency_us, queue_occupancy FROM int_hops ORDER BY ts DESC LIMIT 10"
```
Rows show switch_id 1 and 2, small hop latencies (0-1000 µs), and qdepth spikes
when the sender bursts.

## Troubleshooting
- No packets seen: receiver must run with `sudo` (raw sockets); tcpdump on h2
  to confirm traffic; check h2 default route; switches must have int_table default.
- `queue_occupancy` always 0: BMv2 only fills enq_qdepth when the queue
  actually builds up — force with the burst mode.
- Parse errors on Raw load: some packets (ARP etc.) have no payload — guard.

## On success
Update `tasks/TASKS.md` (task 5 DONE) → task 06 (independent, can run after).
