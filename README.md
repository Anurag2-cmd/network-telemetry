# Network Telemetry — 6-protocol emulated monitoring stack

A complete, runnable network-telemetry demonstration: an emulated network
(Mininet + P4/BMv2 + Open vSwitch) exports **SNMP, NetFlow v5, sFlow,
IPFIX, gNMI, and In-band Network Telemetry (INT)**, all funneled into a
single SQLite database and rendered on a real-time Flask dashboard.

Built on Windows 11 + WSL2 (Ubuntu). Everything runs inside WSL; the
dashboard opens in a normal browser.

**Written report (assignment objectives):** see [`report.md`](report.md).

**Full documentation (what it does, architecture, DB schema, how to use,
verification, troubleshooting):** see [`DOCUMENTATION.md`](DOCUMENTATION.md).

**New machine, just want it running:** see [`QUICKSTART.md`](QUICKSTART.md) —
preflight checks, the one-command run, verification, stopping and
troubleshooting. [`RUN_LOG.md`](RUN_LOG.md) logs a verified end-to-end run
(results, timings, and two known dashboard bugs).

## Assignment mapping

| Objective / complaint being answered | Where in this project |
|---|---|
| "We can't see what broke in the network" | In-band telemetry (INT) stamps every packet, per switch, with queue depth and per-hop latency — you watch a queue spike in real time |
| "SNMP polling is slow and coarse" | SNMP poller (CPU/mem/interface octets every 5 s) shares the same timeline as the streaming protocols so you can compare |
| "Flow-level visibility is missing" | NetFlow v5 (softflowd on h1) and IPFIX v10 (softflowd on h3) export flow records; sFlow (OVS, sampling=1) gives packet samples + interface counters |
| "Monitoring can't model today's boxes" | gNMI (pygnmi) streams OpenConfig-style interface counters over gRPC — the modern, model-driven successor to SNMP |
| "Every tool needs a separate dashboard" | One Flask dashboard with a tab per protocol, all reading one SQLite DB |

## Architecture

```
                         +-------- emulated network (Mininet, WSL) -------+
                         |                                              |
   INT path              |  h1 -- s1 (P4) -- s2 (P4) -- h2              |
   UDP/4000 + stack      |                                          h3  |
   (1 entry per switch)  |                                              |
                         +----------------------------------------------+
                        (every path below this line hits the same DB)

 INT:   h1 --int_sender--> P4 switches add metadata --> int_receiver on h2
                                                        |  shot
 sFlow: OVS s1 samples every pkt --> 127.0.0.1:6343 --> sflow_collector
 NetFlow: softflowd(h1, v5) --> h4:9995 ----------------> netflow_collector
 IPFIX:  softflowd(h3, v10) --> h4:9996 ----------------> ipfix_collector
 SNMP:   snmpd(h4, agent) <-- 5s poll <-- snmp_poller (root netns)
 gNMI:   gnmi_agent (emulated gNMI svc over P4Runtime counters) <-- 2s
           <-- gnmi_client (pygnmi Get, gRPC)

              all -> db/telemetry.db (SQLite, WAL) -> dashboard/app.py
                                                        -> http://localhost:5000
```

## Prerequisites

- Windows 11 with WSL2 (Ubuntu), passwordless sudo for `anurag`
- Tasks 01-02 builds installed on PATH: `p4c`, `simple_switch`,
  `simple_switch_grpc`, `simple_switch_CLI`
- Mininet, OVS, softflowd, snmpd, iperf3, tcpdump, sqlite3 (Python)
- Python deps: `scapy flask pysnmp pygnmi grpcio`

## How to run

One command executes the whole demo and keeps the dashboard up:

```bash
# WSL shell, from the project folder
sudo bash run_all.sh
```

This runs (each step checks rows land in its DB table):

1. INT — 2 P4 switches, receiver on h2, steady flow + 1000-pkt burst
2. sFlow + NetFlow + IPFIX — OVS topology, softflowd exporters, iperf h1/h3→h2
3. SNMP — snmpd on h4, poller every 5 s, iperf into h4
4. gNMI — emulated gNMI agent over P4Runtime counters, pull client every 2 s
5. Dashboard — starts `dashboard/app.py`, left running

Then open **http://localhost:5000** from Windows.

To run things individually:

```bash
sudo python3 mn/topology_int_demo.py   # INT only
sudo python3 mn/topology_ovs.py        # sFlow + NetFlow + IPFIX
sudo python3 mn/topology_snmp.py       # SNMP
bash scripts/wsl-tmp/e2e-gnmi.sh       # gNMI
python3 dashboard/app.py               # dashboard
```

Check rows directly:

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
python3 -c "import sqlite3;c=sqlite3.connect('db/telemetry.db');\
print(c.execute('SELECT COUNT(*) FROM sflow_samples').fetchone()[0])"
```

## What to watch per protocol

- **INT** — the *queue occupancy* line spikes when the sender bursts
  (s2 throttled to 500 pps); per-hop latency/jitter on the h1→s1→s2→h2 path.
- **sFlow** — bandwidth lines flicker to multi-Gb/s during iperf; a
  packet-sample table shows exact 5-tuples and byte counts.
- **NetFlow / IPFIX** — flow records (src/dst IP+port, proto, packets,
  bytes); IPFIX also carries IPv6-length templates. Watch them appear
  ~10-60 s after traffic, when softflowd flushes.
- **SNMP** — counter rows every 5 s; `bw_in_mbps` jumps to 1-2 Gb/s while
  iperf runs into the SNMP device (h4).
- **gNMI** — OpenConfig-style `in-octets`/`out-octets` counters grow with
  traffic; `oper-status` flips UP once packets observed.

## File map

```
p4/int.p4            P4-16 INT program: INT header+stack, per-port counters
p4/int.json          compiled artifact (p4c-bm2-ss), loaded by simple_switch
mn/topology_int.py   2 P4 switches + 3 hosts (INT path), + rules/CLI helpers
mn/topology_int_demo.py  run_all INT stage: receiver + steady + burst -> int_hops
mn/topology_ovs.py   OVS topo: sFlow export + softflowd v5/v10 -> collectors
mn/topology_snmp.py  OVS topo: snmpd on h4 + root-netns poller
tools/int_sender.py  UDP/4000 sender (loop / --burst)
tools/int_receiver.py scapy receiver: INT parse, latency/jitter, -> int_hops
tools/sflow_collector.py  UDP 6343 -> sflow_samples
tools/netflow_collector.py UDP 9995 -> netflow_flows
tools/ipfix_collector.py  UDP 9996, dynamic templates -> ipfix_flows
tools/snmp_poller.py  SNMPv2c GET walk -> snmp_stats
tools/gnmi_agent.py   emulated gNMI service (pygnmi) over P4Runtime counters
tools/gnmi_client.py  pygnmi Get/pull -> gnmi_stats
dashboard/app.py, db.py, templates/index.html   Flask app, /api/<source>,
                    /api/status badges, Chart.js tabs
db/telemetry.py     shared SQLite helper (schema, WAL, cleanup)
db/telemetry.db     shared database (gitignored)
run_all.sh          one-command E2E runner (task 11)
tasks/TASKS.md      12-step task index
```

## Known limitations

- **Per-switch clocks**: BMv2 `ingress_global_timestamp` is not
  synchronized across switches; the INT receiver calibrates the constant
  boot offset from the first packet, so *relative* per-hop latency and
  jitter are accurate, absolute ones are not (see `tools/int_receiver.py`).
- **Emulated gNMI**: this BMv2 build ships no native gNMI service
  (outcome B in `tasks/09-gnmi-client.md`); `tools/gnmi_agent.py` emulates
  the gNMI interface on top of the real P4Runtime port counters.
- **softflowd on WSL2**: its live libpcap capture receives no packets on
  this kernel, so exporters read a tcpdump -U packet FIFO (see
  `topology_ovs.py`); flow rows land after the ~10-60 s timeout.
- **sFlow counters**: `bandwidth_in_mbps` derives from OVS counter-poll
  deltas; carousel can under-report for very short bursts.
- **Emulation scale**: speeds, queue depths, and latency are Mininet/BMv2
  artifacts — great for teaching and demos, not production numbers.