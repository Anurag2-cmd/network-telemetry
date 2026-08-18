# Task 06: sFlow collector (packet sampling from Open vSwitch)

## Goal
An Open vSwitch-based Mininet topology where OVS exports **sFlow v5** samples to
a Python UDP collector on port 6343, which parses flow samples + interface
counters and stores them in `db/telemetry.db` table `sflow_samples`.

## Context
- Open vSwitch 3.7.1 installed (comes with Mininet). This task is independent of INT.
- OVS in WSL2: uses userspace datapath; Mininet's default switch OVSSwitch works.

## Topology `mn/topology_ovs.py` (4 hosts, 1 OVS switch)
`h1 h2 h3 h4 -- s1(OVS)` with 10.0.1.x/24. Run `iperf3` between h1 and h2 to generate traffic.

## Enable sFlow export on the OVS bridge (after net.start())
```bash
ovs-vsctl -- --id=@s create sflow agent=eth0 target="127.0.0.1:6343" \
  sampling=1 header=128 polling=10 \
  -- set bridge s1 sflow=@s
```
- `sampling=1` → sample every packet (demo); in real life 1/100-1/1000.
- `polling=10` → per-interface counters every 10 s (this gives bandwidth utilization).

## Collector `tools/sflow_collector.py`
- UDP socket on 0.0.0.0:6343, parse **sFlow v5** datagram (scapy has `SFlow`
  classes: `scapy.layers.sflow`):
  - datagram header: version(4) agent_ip(4) sub_agent_id(4) seq(4) uptime(4)
    samples_count(4)
  - sample type 1 = flow sample: sequence, source_id, sampling_rate, pool,
    drops, input port, output port, flow records…
  - record type 4 = raw packet header → gives sampled packet (use it to extract
    src/dst IP, ports, proto — this is the "packet-level visibility" demo)
  - sample type 2 = counters sample (interface counters → octets in/out
    → compute bandwidth Mb/s between polls)
- Store rows:
```sql
CREATE TABLE IF NOT EXISTS sflow_samples (
    ts INTEGER, agent TEXT, src_ip TEXT, dst_ip TEXT, src_port INTEGER,
    dst_port INTEGER, proto INTEGER, bytes_sampled INTEGER,
    in_port INTEGER, out_port INTEGER, if_in_octets INTEGER, if_out_octets INTEGER,
    bandwidth_in_mbps REAL, bandwidth_out_mbps REAL
);
```
- Keep last 24h; drop rows when tables are empty during idle periods is fine.

## Verification (Definition of Done)
1. Start topology + collector, run `iperf3 -s` on h2, `iperf3 -c 10.0.1.2` on h1.
2. `sqlite3 db/telemetry.db "SELECT count(*) FROM sflow_samples"` grows every second.
3. Table shows src 10.0.1.1 → dst 10.0.1.2, proto TCP, and bandwidth_in_mbps > 0
   during iperf (matches `iperf3` reported throughput roughly).

## Troubleshooting
- No sFlow packets: verify with `tcpdump -i any port 6343`; check agent IP is a
  real interface IP; sampling=1 with header=128 guarantees samples.
- OVS bridge name: `net.get('s1').name` might be `s1` — use the actual OVS bridge
  name (`ovs-vsctl show`).

## On success
Update `tasks/TASKS.md` (task 6 DONE) → task 07.
