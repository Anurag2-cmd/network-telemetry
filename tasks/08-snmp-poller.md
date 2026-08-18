# Task 08: SNMP poller (device CPU/memory/interface counters)

## Goal
Poll a network device's SNMP agent (snmpd) and store CPU load, memory usage,
and interface octet counters into `db/telemetry.db` table `snmp_stats` every 5 s.
Contrast with streaming telemetry: this is **pull-based, coarse** monitoring —
demonstrates why telemetry evolved past SNMP.

## Context
- snmpd 5.9.4 installed. pysnmp 7.1.27 installed (use the async/high-level
  `pysnmp.hlapi.v3arch` API or plain `pysnmp.hlapi`).
- Device to poll: run `snmpd` inside a Mininet host (h4 from task 07 topo, or
  any host) — it represents a "network device" with an SNMP agent.
  - In the host: `h4.cmd('snmpd -f -Lo -c /etc/snmp/snmpd.conf ... &')` —
    snmpd reads /etc/snmp/snmpd.conf from WSL; check `agentaddress udp:161` is
    bound inside the host netns. Default community: `public`, but recent Ubuntu
    snmpd.conf restricts by default — simplest: run
    `h4.cmd('snmpd -f -c /etc/snmp/snmpd.conf -C -Lo 0.0.0.0:161 &')` won't parse…
    → **simplest reliable**: override config with a minimal file:
    ```
    rocommunity public
    agentaddress udp:161
    ```
    written to /tmp/snmpd.conf and passed with `-c /tmp/snmpd.conf`.

## Poller `tools/snmp_poller.py` (runs in WSL root netns)
Use pysnmp v3arch (snmpv3arch API in pysnmp 7):
```python
from pysnmp.hlapi.v3arch.asyncio import *
```
Simpler alternative that's robust in pysnmp 7: use the synchronous
`pysnmp.hlapi.v3arch.sync` API:
```python
from pysnmp.hlapi.v3arch.sync import bulk_walk, get, UdpTransportTarget, CommunityData
```
OIDs to poll (target host 10.0.1.4:161, community public):
- load:  `1.3.6.1.4.1.2021.10.1.5.1` (laLoadInt1, 1-min load ×100)
- mem:   `1.3.6.1.4.1.2021.4.6.0` (memTotalReal), `1.3.6.1.4.1.2021.4.5.0` (memAvailReal)
- iface: `1.3.6.1.2.1.2.2.1.10` (ifInOctets), `1.3.6.1.2.1.2.2.1.16` (ifOutOctets)
  — bulk_walk with `max_vars=50` to get all interfaces; pick the emulated one.
- uptime: `1.3.6.1.2.1.1.3.0`
Compute bandwidth Mb/s from octet deltas between polls (like task 06).

## Storage
```sql
CREATE TABLE IF NOT EXISTS snmp_stats (
    ts INTEGER, device TEXT, cpu_load REAL, mem_used_pct REAL,
    if_octets_in INTEGER, if_octets_out INTEGER,
    bw_in_mbps REAL, bw_out_mbps REAL, uptime INTEGER
);
```

## Verification (Definition of Done)
1. Topology running, snmpd up inside h4, iperf traffic h1→h2.
2. `sqlite3 db/telemetry.db "SELECT * FROM snmp_stats ORDER BY ts DESC LIMIT 5"`
   shows rows every ~5 s with cpu/mem values (0-100) and non-zero bw during iperf.
3. `snmpget -v2c -c public 10.0.1.4 1.3.6.1.2.1.1.3.0` (from WSL host) also works
   → proves the agent responds.

## Troubleshooting
- Timeout: community wrong / snmpd not listening in host netns
  (test from inside host: `h4.cmd('snmpget -v2c -c public 127.0.0.1 1.3.6.1.2.1.1.3.0')`).
- pysnmp API moved in v7: if `pysnmp.hlapi.v3arch` import fails, fall back to
  `pysnmp.hlapi.v1arch` (v1 API: `getCmd`, `nextCmd`, `bulkCmd`) which still
  exists in pysnmp 7.1.

## On success
Update `tasks/TASKS.md` (task 8 DONE) → task 09.
