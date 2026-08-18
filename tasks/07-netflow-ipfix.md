# Task 07: NetFlow v5 + IPFIX collectors (softflowd exporters)

## Goal
In the OVS topology (task 06), run **softflowd** inside two Mininet hosts:
- h1: exports **NetFlow v5** to collector port 9995
- h3: exports **IPFIX** (v10) to collector port 9996

Two Python UDP collectors parse the records and store into
`db/telemetry.db` tables `netflow_flows` and `ipfix_flows`.
This demonstrates flow-based monitoring (per-flow byte/packet counts).

## Context
- softflowd 1.1.1 installed on WSL (the same binary runs inside Mininet hosts —
  they share the kernel; `h1.cmd('softflowd ...')` works).
- Mininet hosts each have one interface (e.g., `h1-eth0`).

## Start exporters inside hosts (from the topology script, after traffic starts)
```bash
# on h1: NetFlow v5, observation of all traffic, 60s timeout, export every 10s
h1: softflowd -i h1-eth0 -v 5 -n 127.0.0.1:9995 -t 60 -m 10
# on h3: IPFIX export
h3: softflowd -i h3-eth0 -v 10 -n 127.0.0.1:9996 -t 60 -m 10
```
Note: each Mininet host has its own netns → the collector listening on the
host loopback would see only its own exports. Solution: run collectors on the
**WSL host** (root netns) and target `127.0.0.1` → they arrive on the WSL host,
but hosts' loopback is separate... So instead:
- option A: point `-n` at the **collector host h4** (e.g. `-n 10.0.1.4:9995`)
  and run the collector on h4 inside the emulated network.
- option B (simpler): collectors listen on 0.0.0.0:9995/9996 in the WSL host
  netns; exporters use the *veth IP of their switch side*… complex.
→ **Use option A**: run `tools/netflow_collector.py` and
  `tools/ipfix_collector.py` ON h4 (h4 = dedicated collector host).

## NetFlow v5 format (UDP 9995)
Fixed 24-byte header: version(2)=5 count(2) uptime(4) epoch(4) seq(4) src(4) dst(4).
Each flow record is 48 bytes: src_ip(4) dst_ip(4) next_hop(4) if_in(2) if_out(2)
dPkts(4) dOctets(4) first(4) last(4) src_port(2) dst_port(2) pad1(1) tcp_flags(1)
prot(1) tos(1) src_as(2) dst_as(2) src_mask(1) dst_mask(1) pad2(2).
Parse with `struct.unpack('!HHIIII', header)` + `'!4s4s4sHHIIIIHHBBBBHHBBH'` per record.
Map 4-byte IP to dotted string. Counts: dOctets = bytes in flow, dPkts = packets.

## IPFIX format (UDP 9996)
Variable-length: version(2)=10 length(2) export_time(4) seq(4) domain(4),
then sets: set_id(2) set_len(2). set_id 2 = template (fields described in records
by IE numbers: 8=srcIP 12=dstIP 7=srcPort 11=dstPort 4=protocol 1=octets 2=packets…).
Parse templates, then data records per template. Implement a minimal template
parser (templates 256+ are dynamic; set_id 2 is the template set).
Use these IEs at minimum: 1 (octetDeltaCount), 2 (packetDeltaCount), 4/7/11
(protocol/srcPort/dstPort), 8/12 (src/dst IPv4), 152 (flowStart), 153 (flowEnd).

## Storage
```sql
CREATE TABLE IF NOT EXISTS netflow_flows (
    ts INTEGER, src_ip TEXT, dst_ip TEXT, src_port INTEGER, dst_port INTEGER,
    proto INTEGER, tcp_flags INTEGER, packets INTEGER, bytes INTEGER,
    first_ts INTEGER, last_ts INTEGER
);
CREATE TABLE IF NOT EXISTS ipfix_flows (   -- same columns
    ts INTEGER, src_ip TEXT, dst_ip TEXT, src_port INTEGER, dst_port INTEGER,
    proto INTEGER, packets INTEGER, bytes INTEGER, first_ts INTEGER, last_ts INTEGER
);
```

## Verification (Definition of Done)
1. Start OVS topology, iperf h1→h2, softflowd on h1 (v5) and h3 (v10),
   collectors on h4.
2. Both tables fill within ~10-60 s (flow timeout).
3. `SELECT src_ip, dst_ip, bytes FROM netflow_flows ORDER BY ts DESC LIMIT 5`
   shows 10.0.1.1 → 10.0.1.2 TCP flows with realistic byte counts
   (matches iperf volume within sampling).

## Troubleshooting
- No export: `softflowd -v` prints to stderr — run it in foreground in a host
  xterm (`h1.xterm()`) to see errors; check `-n` target reachable (ping h4).
- NetFlow collector receiving garbage: verify version bytes == 5.
- IPFIX template parsing: print every template received during development;
  softflowd sends templates repeatedly (every export), so late subscribers recover.

## On success
Update `tasks/TASKS.md` (task 7 DONE) → task 08.
