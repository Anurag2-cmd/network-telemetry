# Network Telemetry Project — Full Documentation

A complete, runnable demonstration of modern network telemetry: an emulated
network (Mininet + P4/BMv2 + Open vSwitch) exports **six telemetry
technologies** — SNMP, NetFlow v5, sFlow, IPFIX, gNMI, and In-band Network
Telemetry (INT) — all funneled into a single SQLite database and rendered
on a real-time Flask dashboard.

This document explains what the project does, how it is built, and how to
use it. For a quick start see [`README.md`](README.md); for the assignment
report see [`report.md`](report.md).

---

## Table of contents

1. [Overview](#1-overview)
2. [System architecture](#2-system-architecture)
3. [The six protocols — what each one does](#3-the-six-protocols--what-each-one-does)
4. [Database schema](#4-database-schema)
5. [File map](#5-file-map)
6. [Prerequisites & setup](#6-prerequisites--setup)
7. [How to run — full demo](#7-how-to-run--full-demo)
8. [How to run — individual stages](#8-how-to-run--individual-stages)
9. [Using the dashboard](#9-using-the-dashboard)
10. [Verification](#10-verification)
11. [Troubleshooting](#11-troubleshooting)
12. [Known limitations](#12-known-limitations)
13. [Extending the project](#13-extending-the-project)
14. [References](#14-references)

---

## 1. Overview

**Network telemetry** is the automated collection of measurement data from
network devices — counters, state, flows, or per-packet metadata — its
transport to collectors, and its analysis to understand a network's
behavior. Traditional monitoring (SNMP polling) asks a device "are you
OK?" every few seconds and gets coarse counters back; modern telemetry
pushes or stamps fine-grained data continuously, down to *per packet per
hop*.

This project is a miniature of that idea, built entirely with open tools:

| Layer | Tools used |
|---|---|
| Emulated network | Mininet (virtual hosts/switches), P4 + BMv2 (`simple_switch`), Open vSwitch |
| Telemetry devices | P4 switches (INT + port counters), OVS (sFlow exporter), `softflowd` (NetFlow v5 + IPFIX), `snmpd` (SNMP agent), `simple_switch_grpc` + gNMI agent (gNMI) |
| Collectors | Python UDP collectors + SNMP poller + gNMI pull client (`tools/`) |
| Storage | One shared SQLite database, `db/telemetry.db` (WAL mode) |
| Visualization | Flask dashboard with a tab per protocol (`dashboard/`) |

The six protocols cover four generations of network telemetry evolution:

1. **SNMP** (1990s) — pull-based device health counters
2. **NetFlow v5 / sFlow / IPFIX** (1995–2008) — flow records and packet samples
3. **gNMI** (2016+) — streaming, model-driven device state over gRPC
4. **INT** (2016+) — in-band, per-packet-per-hop metadata stamped by the switches themselves

Everything runs inside WSL2 on Windows 11; the dashboard opens in a normal
browser at `http://localhost:5000`.

---

## 2. System architecture

```
                         +-------- emulated network (Mininet, WSL) -------+
                         |                                              |
   INT path              |  h1 -- s1 (P4) -- s2 (P4) -- h2              |
   UDP/4000 + stack      |                                          h3  |
   (1 entry per switch)  |                                          h4  |
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

### Component roles

| Component | Role | In this project |
|---|---|---|
| Telemetry-enabled devices | Produce the data | P4 `simple_switch` (INT + port counters), OVS `s1` (sFlow exporter), `softflowd` agents on h1/h3 (NetFlow v5 / IPFIX v10), `snmpd` on h4 (SNMP agent), `simple_switch_grpc` + `gnmi_agent` (gNMI service) |
| Collectors | Receive, decode, store | Python UDP collectors (ports 6343/9995/9996), SNMP poller, gNMI pull client — all writing `db/telemetry.db` |
| Analytics | Turn raw data into insight | Per-hop latency/jitter & queue occupancy (INT), bandwidth from counter deltas (sFlow/SNMP), flow records (NetFlow/IPFIX), interface counter growth (gNMI) |
| Visualization | Present it live | Flask `dashboard/app.py` + Chart.js: one tab per protocol, `/api/<source>` last-200 rows, live badges (60 s window), 5 s auto-refresh |

### Data flow

```
emulated network  --export-->  collector  --INSERT-->  SQLite  <--SELECT--  Flask API  <--fetch 5s--  browser (Chart.js)
```

- **Exporters** run inside the emulated network (Mininet hosts or switches).
- **Collectors** run as normal processes in the WSL root netns, listening on
  UDP sockets or polling, and insert rows into `db/telemetry.db`.
- **The dashboard** only ever *reads* the DB — it never interferes with
  collection, so you can kill it and restart it without losing data.
- Old rows (> 24 h) are cleaned up by each collector on startup and
  periodically, so the DB never grows unbounded.

---

## 3. The six protocols — what each one does

### 3.1 INT — In-band Network Telemetry (generation 4, the newest)

**Mechanism:** in-band — metadata rides *inside* the packets themselves.

The sender (`tools/int_sender.py`) emits UDP/4000 packets carrying an
INT header. Each P4 switch (`p4/int.p4` running on BMv2) appends a
12-byte stack entry `{switch_id, ingress_ts, enq_qdepth}` in the egress
pipeline. The receiver on h2 (`tools/int_receiver.py`) sniffs the packets,
parses the stack, and computes **per-hop latency** (from the per-switch
timestamps, with boot-offset calibration) and **jitter**, writing one row
per hop to `int_hops`.

**What you see:** the queue-occupancy line spikes when traffic bursts
(s2 is throttled to 500 pps in the demo, so a 1000-packet burst builds a
queue 43–45 packets deep — something SNMP can never see).

### 3.2 sFlow — sampled packets + interface counters (generation 2)

**Mechanism:** push — switch samples packets and polls its own counters.

Open vSwitch exports sFlow v5 (sampling=1, header=128 bytes, counter
polling every 10 s) to `127.0.0.1:6343`. `tools/sflow_collector.py`
parses **flow samples** (raw packet headers → L3/L4 tuple, in/out port)
and **counter samples** (octets → bandwidth since last poll) into
`sflow_samples`.

**What you see:** bandwidth lines jumping to multi-Gb/s during iperf,
and a packet-sample table with exact 5-tuples and byte counts.

### 3.3 NetFlow v5 — flow records (generation 2)

**Mechanism:** push — devices aggregate traffic into flow records and
export them on flow end / timeout.

`softflowd` runs inside h1 and exports fixed-format v5 datagrams
(24-byte header + 48-byte records) to h4:9995.
`tools/netflow_collector.py` parses them into `netflow_flows`:
src/dst IP + port, proto, TCP flags, packets, bytes, flow first/last time.

**What you see:** a row per flow (who talked to whom, how much) appearing
~10–60 s after the traffic, when softflowd flushes.

### 3.4 IPFIX — NetFlow v10 (generation 2, standardized/extensible)

**Mechanism:** push — same idea as NetFlow but with *dynamic templates*.

`softflowd` inside h3 exports IPFIX datagrams to h4:9996.
`tools/ipfix_collector.py` learns the **dynamic templates** (set_id 2),
decodes data sets, and supports IPv4 *and* IPv6 fields. Rows land in
`ipfix_flows`.

**What you see:** flow records like NetFlow, but template-encoded —
custom/extensible fields (e.g. `octetDeltaCount`, `packetDeltaCount`,
`flowStart/flowEnd`).

### 3.5 SNMP — the traditional pull baseline (generation 1)

**Mechanism:** pull — the poller asks, the agent answers.

`snmpd` runs inside h4 (the "network device"), configured with a minimal
config (`rocommunity public`, agentaddress udp:161).
`tools/snmp_poller.py` runs in the WSL root netns and polls `10.0.1.4:161`
every 5 s over SNMPv2c: CPU load, memory %, interface octet counters, and
bandwidth derived from octet deltas → `snmp_stats`.

**What you see:** slow, counter-based curves — and the contrast to the
streaming protocols. A 5 s poll cannot see a sub-second microburst that
INT records (see [report.md](report.md), section 2).

### 3.6 gNMI — streaming, model-driven state (generation 3)

**Mechanism:** push/pull over gRPC with a negotiated schema (YANG/OpenConfig).

This BMv2 build ships no native gNMI service, so `tools/gnmi_agent.py`
**emulates** the gNMI service (Get / Capabilities / Subscribe) on top of
the *real* P4Runtime port counters, exposing OpenConfig-style paths:

```
/interfaces/interface[name=<port>]/state/name
/interfaces/interface[name=<port>]/state/oper-status
/interfaces/interface[name=<port>]/state/counters/in-octets
/interfaces/interface[name=<port>]/state/counters/out-octets
/interfaces/interface[name=<port>]/state/counters/in-errors
/interfaces/interface[name=<port>]/state/counters/out-errors
```

`tools/gnmi_client.py` polls it every 2 s with pygnmi (Get over an
insecure gRPC channel), storing one row per leaf in `gnmi_stats`.

**What you see:** OpenConfig-style `in-octets`/`out-octets` counters
growing with traffic, `oper-status` flipping to UP once packets are
observed.

### The six protocols side by side

| Protocol | Mechanism | Granularity | Overhead | Typical data | Problem it solved |
|---|---|---|---|---|---|
| SNMP | Pull (request/response) | 5–300 s | Low | CPU, mem, octet counters | Basic device health — the 1990s baseline |
| NetFlow v5 | Push (flow records) | Per-flow, export on timeout | Low (aggregates) | 5-tuple flows, pkts, bytes | Traffic analysis without full capture |
| sFlow | Push (sampled packets + counters) | Every packet (sampling=1) / 10 s counters | Moderate | Sampled headers, ports, octets | Continuous traffic view on high-speed links |
| IPFIX | Push (flexible templates) | Per-flow | Low | Template-encoded flows, IPv6, custom IEs | Standardized, extensible flow export |
| gNMI | Push/Pull over gRPC, model-driven | Sub-second (2 s here) | Low | OpenConfig interface state | Streaming, schema-negotiated device state |
| INT | In-band (metadata in packets) | Per packet per hop | In-packet bytes only | switch_id, ingress_ts, queue depth | Per-hop, zero-network-load visibility |

---

## 4. Database schema

One database, `db/telemetry.db` (SQLite, WAL mode, 30 s busy timeout).
Schema is created automatically by `db/telemetry.py` (`get_conn()`);
collectors write, the dashboard only reads. All `ts` values are Unix
epoch seconds.

### `int_hops` — one row per hop per INT packet

| Column | Type | Meaning |
|---|---|---|
| ts | INTEGER | Receiver timestamp (epoch s) |
| flow | TEXT | Flow identifier (src/dst IP:port) |
| hop_idx | INTEGER | Hop position (1 = first switch) |
| switch_id | INTEGER | Which P4 switch stamped the entry (1 or 2) |
| ingress_ts | INTEGER | Switch's raw ingress timestamp (µs since switch boot) |
| hop_latency_us | REAL | Per-hop latency (µs), clock-offset calibrated |
| jitter_us | REAL | Packet-to-packet jitter at this hop (µs) |
| queue_occupancy | INTEGER | Egress queue depth at stamp time (enq_qdepth) |

### `sflow_samples` — one row per sFlow sample

| Column | Type | Meaning |
|---|---|---|
| ts | INTEGER | Epoch s |
| agent | TEXT | Exporter (switch) address |
| src_ip / dst_ip | TEXT | Packet's L3 tuple |
| src_port / dst_port | INTEGER | L4 tuple |
| proto | INTEGER | IP protocol number |
| bytes_sampled | INTEGER | Sampled packet length |
| in_port / out_port | INTEGER | Switch ports |
| if_in_octets / if_out_octets | INTEGER | Interface counters from counter samples |
| bandwidth_in_mbps / bandwidth_out_mbps | REAL | Bandwidth derived from counter deltas |

### `netflow_flows` — one row per NetFlow v5 record

| Column | Type | Meaning |
|---|---|---|
| ts | INTEGER | Epoch s (export time) |
| src_ip / dst_ip | TEXT | Flow endpoints |
| src_port / dst_port | INTEGER | L4 ports |
| proto | INTEGER | IP protocol |
| tcp_flags | INTEGER | TCP flags byte |
| packets / bytes | INTEGER | Flow aggregates |
| first_ts / last_ts | INTEGER | Flow start/end (ms since flow start of exporter) |

### `ipfix_flows` — one row per IPFIX data record

| Column | Type | Meaning |
|---|---|---|
| ts | INTEGER | Epoch s (export time) |
| src_ip / dst_ip | TEXT | Flow endpoints |
| src_port / dst_port | INTEGER | L4 ports |
| proto | INTEGER | IP protocol |
| packets / bytes | INTEGER | Flow aggregates |
| first_ts / last_ts | INTEGER | Flow start/end timestamps |

### `snmp_stats` — one row per poll (every 5 s)

| Column | Type | Meaning |
|---|---|---|
| ts | INTEGER | Epoch s |
| device | TEXT | Polled agent address |
| cpu_load | REAL | 1-min load × 100 (UCD OID 1.3.6.1.4.1.2021.10.1.5.1) |
| mem_used_pct | REAL | Memory usage % |
| if_octets_in / if_octets_out | INTEGER | Interface octet counters |
| bw_in_mbps / bw_out_mbps | REAL | Bandwidth from octet deltas |
| uptime | INTEGER | Device uptime (s) |

### `gnmi_stats` — one row per leaf per Get poll (every 2 s)

| Column | Type | Meaning |
|---|---|---|
| ts | INTEGER | Epoch s |
| path | TEXT | OpenConfig path, e.g. `/interfaces/interface[name=1]/state/counters/in-octets` |
| key | TEXT | Leaf key (e.g. `in-octets`, `oper-status`) |
| value | TEXT | Value as string (for non-integer leaves) |
| int_value | INTEGER | Value as integer (for counter leaves) |

---

## 5. File map

```
p4/int.p4                P4-16 INT program: INT header + 12B stack,
                         per-port counters (int.p4 -> int.json)
p4/int.json              compiled artifact (p4c-bm2-ss), loaded by simple_switch
mn/topology_int.py       2 P4 switches + 3 hosts (INT path), rules/CLI helpers
mn/topology_int_demo.py  run_all INT stage: receiver + steady flow + burst -> int_hops
mn/topology_ovs.py       OVS topo: sFlow export + softflowd v5 (h1) / v10 (h3)
mn/topology_snmp.py      OVS topo: snmpd on h4 + root-netns poller + iperf
tools/int_sender.py      UDP/4000 INT sender (loop / --burst)
tools/int_receiver.py    scapy receiver: INT parse, per-hop latency/jitter -> int_hops
tools/sflow_collector.py  UDP 6343 -> sflow_samples
tools/netflow_collector.py UDP 9995 -> netflow_flows
tools/ipfix_collector.py  UDP 9996, dynamic templates -> ipfix_flows
tools/snmp_poller.py      SNMPv2c GET walk -> snmp_stats
tools/gnmi_agent.py       emulated gNMI service (pygnmi) over P4Runtime counters
tools/gnmi_client.py      pygnmi Get/pull -> gnmi_stats
dashboard/app.py          Flask app: /, /api/<source>, /api/status
dashboard/db.py           SOURCES map, last_rows(), status() queries
dashboard/templates/index.html  one Chart.js tab per protocol, 5 s auto-refresh
db/telemetry.py           shared SQLite helper (schema, WAL, cleanup)
db/telemetry.db           shared database (gitignored)
run_all.sh                one-command E2E runner (task 11)
requirements.txt          Python deps for the dashboard (flask, psutil)
README.md                 quick-start guide
report.md                 assignment written report
tasks/                    TASKS.md index + 12 per-task spec files (01-12)
scripts/wsl-tmp/          dev/test scripts: e2e-check.sh, e2e-gnmi.sh,
                          debug helpers (not part of the demo; collectors
                          also carry built-in --selftest modes)
```

Notes:

- `scripts/wsl-tmp/*` are development and verification helpers. The only
  scripts you need for the demo itself are `run_all.sh`,
  `scripts/wsl-tmp/e2e-gnmi.sh`, and `scripts/wsl-tmp/e2e-check.sh`.
- The top-level `app.py`, `collector.py`, and `templates/` are leftovers
  from an earlier ping-monitor prototype and are **not** used by the demo
  (the dashboard lives in `dashboard/`).

---

## 6. Prerequisites & setup

### Environment facts (verified in this project)

- Host: **Windows 11**, WSL2 distro **Ubuntu** (user `anurag`).
- Passwordless sudo for `anurag` is enabled.
- Project folder is on the Windows side (note the space in the name):
  `/mnt/c/Users/ASUS/Desktop/Network telementry`
- From PowerShell, run Linux commands with:
  `wsl -d Ubuntu -- bash -c "command"` (or `wsl -d Ubuntu -- bash /path/script.sh`)
- WSL2 localhost forwarding: a server listening on `0.0.0.0:5000` inside
  WSL is reachable from Windows at `http://localhost:5000`.

### Required software (inside WSL)

| Component | Notes |
|---|---|
| `p4c` | P4 compiler (p4c 1.2.5.15 used); `p4c-bm2-ss` must be on PATH |
| BMv2 | `simple_switch`, `simple_switch_grpc`, `simple_switch_CLI` on PATH (BMv2 1.15.4 used) |
| Mininet | `mn` command |
| Open vSwitch | `ovs-vsctl` (sFlow export) |
| `softflowd` | NetFlow v5 + IPFIX exporter on hosts h1/h3 |
| `snmpd` | SNMP agent inside host h4 |
| `tcpdump`, `iperf3` | packet capture (softflowd FIFO) and traffic generation |
| Python 3 | + packages: `scapy flask pysnmp pygnmi grpcio psutil sqlite3` |

**Build notes** (for a fresh machine): p4c and BMv2 are large builds —
keep the clones in the Linux home (`~/p4tools/`) for speed, and always run
long builds inside `tmux` so they survive terminal disconnects. This repo
contains `scripts/build-bmv2.sh` (and `scripts/wsl-tmp/build-bmv2.sh`)
with the exact steps used.

---

## 7. How to run — full demo

One command executes the whole demonstration and keeps the dashboard up:

```bash
# WSL shell, from the project folder
sudo bash run_all.sh
```

What it does, step by step (each step counts rows to prove data landed):

| Step | What runs | Result table |
|---|---|---|
| 1/7 | INT: 2 P4 switches, receiver on h2, 10 s steady flow + 1000-pkt burst (s2 throttled) | `int_hops` |
| 2/7 | OVS topology: sFlow + softflowd v5 (h1) + softflowd v10 (h3), iperf h1/h3 → h2 | `sflow_samples`, `netflow_flows`, `ipfix_flows` |
| 3/7 | SNMP: snmpd on h4, poller every 5 s, iperf into h4 | `snmp_stats` |
| 4/7 | gNMI: emulated agent over P4Runtime counters, pull client every 2 s | `gnmi_stats` |
| 5/7 | Dashboard: starts `dashboard/app.py` on 0.0.0.0:5000, kept running | — |
| 6/7 | Final assertion: all 6 tables must be non-empty | — |
| 7/7 | Done — open http://localhost:5000 | — |

**Expected result** (from a real run, 2026-08-05):

```
int_hops       350
sflow_samples  170802
netflow_flows  4
ipfix_flows    9
snmp_stats     3
gnmi_stats     180
ALL 6 TABLES NON-EMPTY: PASS
```

(The exact row counts vary run to run — the assertion is that **every
table is non-empty**.)

Then open **http://localhost:5000** from Windows and watch the six tabs.

> **Long-running jobs in this environment:** the AI/shell tooling used to
> develop this project kills foreground processes on timeout/disconnect.
> Always run long jobs inside tmux:
>
> ```bash
> tmux new-session -d -s e2e 'sudo bash run_all.sh 2>&1 | tee /tmp/run_all.log'
> # poll with:
> tmux ls; tail -20 /tmp/run_all.log
> ```

---

## 8. How to run — individual stages

Run only the parts you want, each in its own terminal:

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"

sudo python3 mn/topology_int_demo.py   # INT only          -> int_hops
sudo python3 mn/topology_ovs.py        # sFlow+NetFlow+IPFIX -> sflow/netflow/ipfix tables
sudo python3 mn/topology_snmp.py       # SNMP only          -> snmp_stats
bash scripts/wsl-tmp/e2e-gnmi.sh       # gNMI only          -> gnmi_stats
python3 dashboard/app.py               # dashboard only     -> http://localhost:5000
```

Notes:

- `topology_int_demo.py` and `topology_ovs.py` are self-contained: they
  bring up Mininet, run the traffic, run the collectors, print row counts,
  and tear down. Rows stay in the DB afterwards.
- The collectors (e.g. `tools/int_receiver.py`, `tools/sflow_collector.py`)
  can also be run directly for a manual demo while a topology is up; see
  the docstring at the top of each `tools/*.py` file for its exact usage
  and arguments.
- To send INT traffic manually against a running topology:
  `python3 tools/int_sender.py 10.0.1.2` (60 s, 10 pkt/s) or
  `python3 tools/int_sender.py 10.0.1.2 --burst` (1000 packets back-to-back).

---

## 9. Using the dashboard

Start it with `python3 dashboard/app.py` inside WSL (or let `run_all.sh`
do it), then open **http://localhost:5000** from Windows.

### Tabs

One tab per protocol: **INT / sFlow / NetFlow / IPFIX / SNMP / gNMI**.
Each tab fetches its data every 5 s (no page reload) and plots the
relevant series with Chart.js:

- **INT** — per-hop latency, jitter, and queue occupancy. The demo
  centerpiece: the queue line spikes during a burst.
- **sFlow** — bandwidth lines and a packet-sample table.
- **NetFlow / IPFIX** — flow records (src/dst, proto, packets, bytes).
- **SNMP** — CPU, memory, interface octets, bandwidth per poll.
- **gNMI** — OpenConfig counter growth per interface.

### Live badges

The top of the page shows a green/red badge per source. A badge is green
if a row for that source arrived within the last **60 seconds**
(`LIVE_WINDOW_S` in `dashboard/db.py`). All-red means the collectors are
down or the run finished minutes ago — that is normal after `run_all.sh`
finishes, except gNMI which is often the freshest.

### HTTP API

| Endpoint | Response |
|---|---|
| `/` | Dashboard HTML |
| `/api/<source>` | `{columns: [...], rows: [[...]]}` — last 200 rows for `int`, `sflow`, `netflow`, `ipfix`, `snmp`, `gnmi` (oldest → newest; 404 for unknown source; empty on missing table) |
| `/api/status` | `{<source>: {live, rows_60s, last_ts}}` for all 6 sources |

```bash
curl -s http://localhost:5000/api/status
curl -s http://localhost:5000/api/int
```

---

## 10. Verification

### Quick row-count check

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
bash scripts/wsl-tmp/e2e-check.sh
```

Prints one line per table — every table should be > 0 after a run.

### Selftests

Each collector ships a built-in `--selftest` mode (synthetic input, no
Mininet or sockets needed). Run them all with:

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
for c in sflow_collector netflow_collector ipfix_collector \
         snmp_poller int_receiver gnmi_agent gnmi_client; do
  echo "== $c =="; python3 tools/$c.py --selftest || echo "FAIL: $c"
done
```

All print `selftest OK` = parsers and DB writes are correct without
needing Mininet.

### Raw SQL

```bash
sqlite3 db/telemetry.db "SELECT switch_id, hop_latency_us, queue_occupancy FROM int_hops ORDER BY ts DESC LIMIT 6"
sqlite3 db/telemetry.db "SELECT COUNT(*) FROM sflow_samples"
```

### Dashboard health

```bash
curl -sf http://localhost:5000/api/status   # expect JSON with 6 sources
```

### What a good run looks like

- All 6 tables non-empty (see [section 7](#7-how-to-run--full-demo)).
- During a run, the gNMI badge is green (2 s polls); the other badges go
  green while their collectors run.
- INT shows a queue spike (qdepth 40+) on switch 2 right after the burst.
- sFlow bandwidth lines jump to 1–2+ Gb/s during iperf phases.

---

## 11. Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `run_all.sh` step fails or tables stay empty | Run `sudo mn -c` to clean stale Mininet state, kill leftover collectors (`pkill -f sflow_collector` etc.), then rerun. `run_all.sh` does this automatically at startup. |
| Port already in use (5000/6343/9995/9996/9559/9090) | A previous run left a process behind. `pkill -f dashboard/app.py`, `pkill -f sflow_collector`, ... and retry. |
| Dashboard shows "no data yet" / all badges red | Collectors are not running (normal after a finished run) — run `run_all.sh` again, or check `/tmp/dashboard.log`. |
| Dashboard unreachable from Windows | Confirm it is listening: `curl -sf http://localhost:5000/api/status` inside WSL. WSL2 forwards localhost automatically; if not, verify `netstat -tlnp | grep 5000`. |
| INT latency values look strange | BMv2 per-switch clocks are **not synchronized**; the receiver calibrates the constant boot offset from the first packet, so *relative* per-hop latency/jitter are accurate, absolute ones are not (see `tools/int_receiver.py`). |
| NetFlow/IPFIX rows appear late or few | softflowd exports on flow end / timeout (~10–60 s). Short iperf flows → few rows. Expected behavior, see README limitations. |
| softflowd captures nothing | On this WSL2 kernel softflowd's live capture receives nothing; exporters read a `tcpdump -U` packet FIFO instead (see `mn/topology_ovs.py`). Do not replace this with a direct capture. |
| WSL shut down between commands | Each `wsl -d Ubuntu -- bash -c ...` call is a new session; keep a long-lived process (e.g. the dashboard, or tmux) alive to keep the VM up. |
| gNMI stage fails | Needs `simple_switch_grpc` built (task 02). Check `scripts/wsl-tmp/e2e-gnmi.sh` logs in `/tmp/gnmi-e2e-*.log`. |
| `p4c`/`simple_switch` not found | Task 01/02 builds not on PATH — see `scripts/build-bmv2.sh`. |

---

## 12. Known limitations

- **Per-switch clocks**: BMv2 `ingress_global_timestamp` is a per-switch
  µs counter since boot. INT latency is offset-calibrated per flow:
  *relative* per-hop latency and jitter are accurate, absolute values are
  not.
- **Emulated gNMI**: this BMv2 build ships no native gNMI service
  (outcome B, see `tasks/09-gnmi-client.md`). `tools/gnmi_agent.py`
  emulates the gNMI interface on top of the real P4Runtime port counters.
  The protocol interaction is genuine gRPC; the data source is real.
- **softflowd on WSL2**: live libpcap capture receives no packets on this
  kernel, so exporters read a tcpdump packet FIFO; flow rows land after
  the ~10–60 s timeout.
- **sFlow counters**: bandwidth derives from OVS counter-poll deltas and
  can under-report very short bursts.
- **Sampling**: with sampling=1 in an emulator everything is captured; on
  real high-speed links sFlow sampling is statistical and can miss rare
  events — exactly the gap INT fills.
- **Emulation scale**: speeds, queue depths, and latencies are
  Mininet/BMv2 artifacts — ideal for teaching and protocol comparison, not
  production numbers.

---

## 13. Extending the project

The project is designed so a new telemetry source slots in with four small
pieces (the dashboard picks it up automatically):

1. **Schema** — add a `CREATE TABLE IF NOT EXISTS <new_table> (...)` to
   `_SCHEMA` in `db/telemetry.py`.
2. **Collector** — write `tools/<new>_collector.py` that receives/polls
   the data and inserts rows via `db.telemetry.insert_row(table, row)`
   (imported as `from telemetry import get_conn, insert_row`).
3. **Exporter/topology** — extend a `mn/topology_*.py` (or add a new one)
   to emit the data from the emulated network.
4. **Dashboard** — add an entry to `SOURCES` in `dashboard/db.py`
   (`"name": "new_table"`) and a tab in
   `dashboard/templates/index.html`; `/api/<name>` and the live badge
   appear automatically.

Real ideas for extensions: a new protocol (e.g. ERSPAN or a second gNMI
subscription mode — `Subscribe` is already implemented in the agent), a
threshold/alert engine on top of `gnmi_stats`/`int_hops`, CSV export
buttons, or time-range filters in the dashboard.

For the step-by-step build history and per-task specs, see
[`tasks/TASKS.md`](tasks/TASKS.md).

---

## 14. References

| Document | Purpose |
|---|---|
| [`README.md`](README.md) | Quick start: prerequisites, one-command run, what to watch, file map |
| [`report.md`](report.md) | Assignment written report: 4 objectives, telemetry vs SNMP evidence, protocol generations, lessons learned |
| [`tasks/TASKS.md`](tasks/TASKS.md) | 12-task index: status table, dependencies, environment facts, parallel-execution plan |
| [`tasks/01-*.md`](tasks/01-finish-p4c-build.md) … [`tasks/12-*.md`](tasks/12-written-report.md) | Per-task specs: goal, exact steps, verification, troubleshooting |
| `scripts/wsl-tmp/` | Verification/dev scripts (`e2e-check.sh`, `e2e-gnmi.sh`, debug helpers); collectors carry built-in `--selftest` modes |

*How to reproduce every number in this document: `sudo bash run_all.sh`
in WSL, then open http://localhost:5000.*
