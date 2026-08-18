# Task 04: Mininet topology with 2 P4 switches (INT path)

## Goal
`mn/topology_int.py` starts: `h1 - s1 - s2 - h2` (P4 switches running int.json)
plus a third host `h3` attached to s2 (for traffic-load later).

## Context
- Mininet 2.3.0 installed. BMv2 built (task 02 DONE). int.json compiled (task 03 DONE).
- WSL needs root for Mininet → scripts run with `sudo`.
- The INT data path uses `simple_switch` (not grpc version).
- Write the file at: `/mnt/c/Users/ASUS/Desktop/Network telementry/mn/topology_int.py`

## Key implementation (use this structure)
```python
#!/usr/bin/env python3
import os, sys, subprocess
from mininet.net import Mininet
from mininet.node import Host
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel, info

P4_DIR = "/mnt/c/Users/ASUS/Desktop/Network telementry/p4"

class P4Switch(Host):          # simple_switch runs as a host process
    def config(self, **kw):
        super().config(**kw)
        iface = self.params["intf"]
        info(f"*** starting simple_switch {self.name}\n")
        self.cmd(f"simple_switch --log-console --thrift-port {self.thrift_port} "
                 f"{P4_DIR}/int.json > /tmp/{self.name}.log 2>&1 &")
        self.cmd("sleep 1")

    def add_port(self, iface):
        self.cmd(f"simple_switch_CLI --thrift-port {self.thrift_port} "
                 f"<<< 'add-port {self.port_no} {iface}'")
```

Topology: `h1 -- s1 -- s2 -- h2`, plus `s2 -- h3`.
IPs: h1=10.0.1.1/24, h2=10.0.1.2/24, h3=10.0.1.3/24, s1 port map:
eth0→h1(port0), eth1→s2(port1); s2: eth0→s1(port0), eth1→h2(port1), eth2→h3(port2).

After net.start(), program every switch's tables (port numbers match the add-port order):
- `table_add ipv4_lpm set_egress_port 10.0.1.2/32 => 1` (s1)
- `table_add ipv4_lpm set_egress_port 10.0.1.1/32 => 0` (s1)
- s2: `10.0.1.1/32 => 0`, `10.0.1.2/32 => 1`, `10.0.1.3/32 => 2`
- `table_set_default swid_table set_swid 1` (s1), `set_swid 2` (s2)
- `table_set_default int_table add_int_metadata` on BOTH switches
- Switch-to-switch ports need L2: add CLI `add-port` for both ends, and for
  s1→s2 link the two veth ends, `ip link set up` both.

Then: `net.pingAll()` must pass (h2 pings are NOT int-flagged → normal L2/L3 path).

## INT traffic test
1. `h2: sudo tcpdump -i h2-eth0 -c 10 -X > /tmp/tcpdump.log 2>&1 &`
2. `h1: python3 tools/int_sender.py 10.0.1.2`
3. Check /tmp/tcpdump.log: payload begins `f0 00 00 00`, count=2, length=16,
   and TWO stack entries: switch_id 1 then 2, each with a timestamp + qdepth.

## Verification (Definition of Done)
- `sudo python3 mn/topology_int.py` starts without errors; `pingAll` OK.
- INT packets show 2-hop metadata on h2 (two switch_ids: 1, 2).
- `simple_switch_CLI --thrift-port 9090` (s1) `counter_read` style commands work.

## Notes
- Run: `sudo python3 mn/topology_int.py` (sudo python3, not python).
- On exit it should `net.stop()`; Ctrl+C then `sudo mn -c` to clean up.
- s1/s2 thrift ports: 9090 and 9091. simple_switch needs one CPU port? No —
  plain ports only. Keep it simple.
- If `h3` is unused in this task, still include it (task 07 uses hosts for
  softflowd; task 05 uses h2 for parsing).

## On success
Update `tasks/TASKS.md` (task 4 DONE) → task 05.

## Implementation notes (from session 2026-08-02)

- Implemented as `P4Switch(Switch)` (classic p4 tutorial style) with
  `--interface port@iface` at startup — NOT the Host+CLI add-port sketch.
  Port map matches the spec: s1: h1=0, s2=1; s2: s1=0, h2=1, h3=2.
- Do NOT pass `--json X` to simple_switch: boost prefix-matches it to
  `--json-version`, printing `2.24` and exiting 0. Pass the JSON path
  positionally (quoted — folder name has a space).
- `--log-console` and `--log-file` are mutually exclusive.
- Each switch needs a distinct `--device-id` (nanomsg ipc socket collision).
- Hosts use autoSetMacs + autoStaticArp (int.p4 does no ARP and no MAC
  rewrite; proven pattern from test-int.sh).
- s1 needs an extra route `10.0.1.3/32 => 1` (not in the original rule list)
  or h1↔h3 pings fail.
- INT stack is now APPENDED (was push_front → reverse order): action writes
  `hdr.int_meta[idx]` at index=count. Receiver sees switch_id 1 then 2.
- Live INT packet on h2: `f0 02 18 00` + two 12-byte entries (count=2,
  length=24; NOT f0 00 00 00 / length=16 as stated in the old test steps).
- One-shot verification built into the script: pingAll + tcpdump/scapy-free
  pcap parse + CLI table_dump; exits via net.stop().
