# Major Project Synopsis Report

# NETWORK TELEMETRY

**A Six-Protocol Emulated Monitoring Stack (SNMP, NetFlow v5, sFlow, IPFIX, gNMI, INT)**

Project Category: University Based Project / Deep-tech

Projexa Team Id- __________

Submitted in partial fulfilment of the requirement of the degree of

Master of Computer Applications

with

Specialization AI & DS (Section -A)

to

K.R Mangalam University

by

Student Name (Roll) Student Name (Roll)

Under the supervision of

Supervisor Name

Department of Computer Science and Engineering School of Engineering and Technology

K.R Mangalam University, Gurugram- 122001, India August 2026

---

## INDEX

| S.No | Section | Page No. |
|---|---|---|
| 1 | Abstract | |
| 2 | Introduction (description of broad topic) | |
| 3 | Motivation | |
| 4 | Literature Review | |
| 5 | Gap Analysis | |
| 6 | Problem Statement | |
| 7 | Objectives | |
| 8 | Tools/Technologies Used | |
| 9 | Methodology | |
| 10 | References | |

---

# ABSTRACT

Network telemetry is the automated collection of measurement data from
network devices — counters, state, flow records, or per-packet metadata —
its transport to collectors, and its analysis to understand a network's
behaviour. Traditional network monitoring (SNMP polling) asks a device
"are you OK?" every few seconds and receives coarse counters back; it
cannot see what happens *between* polls. This project builds a complete,
runnable miniature of the modern alternative: an emulated network
(Mininet + P4/BMv2 + Open vSwitch) that exports **six telemetry
technologies — SNMP, NetFlow v5, sFlow, IPFIX, gNMI and In-band Network
Telemetry (INT)** — all funneled into a single SQLite database and
visualized on a real-time Flask dashboard with one tab per protocol.

The project covers all four generations of telemetry evolution: pull-based
SNMP (generation 1), flow-based NetFlow/sFlow/IPFIX (generation 2),
streaming model-driven gNMI over gRPC (generation 3), and INT (generation
4), where each P4 switch stamps packets in flight with its switch ID,
ingress timestamp and egress queue depth. The INT path demonstrates the
core motivation of the entire field: a 1000-packet microburst builds a
queue 43–45 packets deep on switch 2 in under a second — an event a 5 s
SNMP poll completely misses, but which the INT receiver records
packet-by-packet, together with the resulting ~22 ms per-hop queueing
delay.

**KEYWORDS:** Network Telemetry, SNMP, NetFlow, sFlow, IPFIX, gNMI, In-band Network Telemetry (INT), P4, Mininet, Software-Defined Networking

---

# INTRODUCTION

Network telemetry is the automated collection of measurement data from
network devices and its delivery to collectors for analysis. Where
traditional management asked "is the device up?" every few minutes, modern
telemetry asks "what is actually happening inside the network right now?"
— down to individual packets and per-hop queue states. Its role is
foundational across modern networking:

| Domain | Why telemetry matters there |
|---|---|
| Cloud data centers | Fast, fine-grained feedback for load balancing and loss detection |
| SDN (Software-Defined Networking) | The control plane needs live data-plane state to make decisions |
| 5G/6G & edge | Strict latency budgets require sub-second visibility into queueing |
| IoT / large-scale fleets | Millions of devices need low-overhead, streaming status collection |

The discipline has evolved through four generations:

1. **Generation 1 — SNMP (1990s):** pull-based request/response; the
   manager polls an agent for MIB counters. Coarse and slow (poll
   intervals of 5–300 s are typical).
2. **Generation 2 — Flow-based (NetFlow 1995, sFlow 2003, IPFIX 2008):**
   devices export *flow records* (who talks to whom, packets, bytes) or
   *sampled packet headers* instead of raw counters — aggregate views
   without full capture.
3. **Generation 3 — Streaming, model-driven (gNMI/gRPC/YANG, 2016+):**
   devices push OpenConfig-modeled state over gRPC; the schema is
   negotiated, subscriptions replace polling, updates are sub-second.
4. **Generation 4 — In-band Network Telemetry (INT with P4, 2016+):**
   switches *stamp packets in flight*, appending metadata (switch ID,
   ingress timestamp, queue depth) to the packet itself — per-hop
   visibility with zero additional network load.

This project implements **all four generations** on one emulated network:
a P4/BMv2 data plane for INT, Open vSwitch as an sFlow exporter,
softflowd agents exporting NetFlow v5 and IPFIX, snmpd as an SNMP agent,
and an emulated gNMI service over the P4 switches' real port counters.
Every collector writes to the same SQLite database, so all six protocols
can be compared side by side on the same traffic, on the same timeline,
in one dashboard.

---

# MOTIVATION

Traditional monitoring is blind to transient events. The classic failure
example — reproduced with real numbers in this project — is the
**microburst**: a short burst of packets (here, 1000 packets sent
back-to-back in under a second) causes a queue to build up and packets to
be dropped. An SNMP poller sampling every 5 s sees only the final counter
values; the *transient queue spike* itself is invisible. Our INT receiver,
by contrast, recorded the queue filling in real time:

```
switch_id=2 lat_us=22392.0 qdepth=43
switch_id=2 lat_us=22848.0 qdepth=44
switch_id=2 lat_us=23350.0 qdepth=45
```

enq_qdepth jumped to 43–45 during the burst, and only ~130 of the 1000
packets got through — the rest were dropped. This is exactly the gap
modern streaming telemetry was invented to fill.

Beyond the microburst, four practical problems motivated this work:

- **Coarse granularity:** SNMP-style polling cannot see sub-second events
  on high-speed links; per-packet metadata is required.
- **No per-hop visibility:** operators cannot tell *which* switch on a
  path caused a delay or drop with conventional protocols.
- **Tool fragmentation:** every protocol traditionally ships its own
  collector and dashboard — there is no unified picture.
- **Hard to compare generations:** studying SNMP vs gNMI vs INT side by
  side normally requires different lab setups.

An emulated, reproducible environment (Mininet + P4 + OVS on a single
laptop) lets all six approaches be built, run, and compared on one
dataset — which is what this project delivers.

---

# LITERATURE REVIEW

The project builds on four decades of network management research and
standardization:

**SNMP — the pull baseline (RFC 1157, 1990).** The Simple Network
Management Protocol defines a manager/agent request-response model over
UDP. Management Information Bases (MIBs) expose counters as OIDs. It
remains the most deployed management protocol, but its polling
granularity (typically 30–300 s) fundamentally cannot observe transient
events.

**NetFlow v5 (Cisco, 1995) and IPFIX (RFC 7011, 2008).** Flow-based
monitoring aggregates packets into records (5-tuple, packets, bytes) and
exports them on flow end or timeout. IPFIX is the standardized,
template-based successor (NetFlow v10). Flow records give cheap traffic
analytics but lose per-packet detail.

**sFlow v5 (RFC 3176, 2003).** A push-based sampling technology: switches
sample packets at a configured rate and poll their own interface counters,
exporting both as datagrams. Sampled headers provide a continuous traffic
view at high link speeds, at the cost of statistical coverage.

**gNMI and OpenConfig (2016+).** The gRPC Network Management Interface
negotiates a schema via Capabilities and supports Get/Set/Subscribe; the
OpenConfig data models provide vendor-neutral device state. Streaming,
model-driven telemetry is the industry's stated successor to SNMP.

**In-band Network Telemetry (INT; P4.org specification, 2016).** Rather
than exporting data out-of-band, each switch appends metadata to the
packet itself. Research (e.g., the original INT work by Kim et al.) shows
per-hop queue occupancy and latency can be recovered at the receiver with
no extra monitoring traffic — the strongest possible answer to "where did
the delay go?"

**Emulation tooling.** Mininet (Lantz et al., SIGCOMM 2010) enables
realistic virtual networks on one host; the P4 language (Bosshart et al.,
SIGCOMM 2014) with the BMv2 reference switch (p4lang/behavioral-model)
allows programmable data planes to be compiled and run in software —
making the INT data plane buildable and testable on a laptop.

---

# GAP ANALYSIS

Existing work and off-the-shelf tools leave several gaps that this
project closes:

1. **Polling blind spots.** SNMP-based systems (and even gNMI pollers at
   multi-second intervals) cannot observe sub-second queue buildup.
   Most literature acknowledges this but does not demonstrate it with a
   side-by-side, reproducible experiment on the same traffic.
2. **No unified view.** NetFlow, sFlow, IPFIX, SNMP and gNMI each ship
   separate collectors, exporters and dashboards. Comparing them requires
   manual cross-referencing of unrelated tools.
3. **Per-hop visibility missing.** Conventional protocols report device
   or flow aggregates; none reveal *which hop* introduced latency or
   queueing — INT does, but requires a programmable data plane (P4) that
   is rarely integrated with the other protocols.
4. **gNMI on real switches is hard to obtain.** Most environments ship no
   gNMI service; this project emulates the gNMI service on top of real
   P4Runtime counters, making generation-3 telemetry available in the
   same lab as the other five protocols.

This project fills the gaps by implementing all six protocols against one
emulated network, one database, and one dashboard, and by reproducing the
pull-vs-push microburst evidence (queue spike 43–45) that no polling
scheme can capture — proving the argument with data rather than asserting
it.

---

# PROBLEM STATEMENT

Network operators today face a visibility problem: they cannot see what
is actually happening inside the network at the moment it happens. The
traditional tool — SNMP polling every 5–300 s — reports coarse counters
and entirely misses transient events such as microbursts, queue buildup
and per-hop queueing delay. Flow-based tools (NetFlow/sFlow/IPFIX) give
aggregate traffic views but lose per-packet detail and per-hop
information. Streaming protocols (gNMI) and in-band telemetry (INT) solve
these problems but are rarely studied together, and each tool traditionally
requires its own dashboard, making comparison impractical.

The problem this project addresses: **build a single emulated network
that exports all six telemetry technologies — SNMP, NetFlow v5, sFlow,
IPFIX, gNMI and INT — into one shared database with one real-time
dashboard, and demonstrate, with real measured data, why modern streaming
and in-band telemetry outperform traditional polling for detecting
transient network events.**

---

# OBJECTIVES

1. To design and build an emulated network (Mininet + P4/BMv2 + Open
   vSwitch) that serves as a realistic telemetry data source for six
   protocols: SNMP, NetFlow v5, sFlow, IPFIX, gNMI and INT.
2. To write a P4-16 INT program (compiled with p4c for BMv2) that stamps
   every packet with a per-hop metadata entry — switch ID, ingress
   timestamp and egress queue depth (enq_qdepth) — with zero additional
   monitoring traffic.
3. To implement Python collectors that parse each protocol — UDP
   collectors for sFlow (6343), NetFlow v5 (9995) and IPFIX (9996), an
   SNMPv2c poller (every 5 s), a pygnmi pull client (every 2 s), and a
   scapy INT receiver computing per-hop latency and jitter — storing all
   data in one shared SQLite database (WAL mode).
4. To build a real-time Flask dashboard with a tab per protocol, live
   green/red liveness badges (60 s window) and 5 s auto-refreshing
   Chart.js graphs, reachable from any browser at localhost:5000.
5. To run an end-to-end test (one command: `run_all.sh`) proving every
   one of the six database tables receives live data, and to demonstrate
   a microburst that SNMP cannot see but INT records packet-by-packet
   (queue depth 43–45, ~22 ms queueing delay).

---

# TOOLS/PLATFORM USED

| Tool | Role in the project |
|---|---|
| Python 3 | All collectors, pollers, the P4 control helpers and the dashboard are written in Python |
| P4-16 + p4c (1.2.5.15) | High-level language and compiler for the programmable INT data plane (`p4/int.p4` → `int.json`) |
| BMv2 (behavioral-model 1.15.4) | `simple_switch` runs the compiled INT switch; `simple_switch_grpc` adds P4Runtime (gNMI data source); `simple_switch_CLI` reads port counters |
| Mininet | Emulates hosts and switches (h1–h4, s1–s2) with real kernel networking |
| Open vSwitch | Learning switch used as the sFlow exporter (sampling=1, counter polls) |
| softflowd | Flow exporter inside hosts: NetFlow v5 on h1, IPFIX v10 on h3 |
| snmpd | SNMP agent running inside host h4 (the "network device") |
| scapy | Packet sniffing and parsing in the INT receiver; synthetic packets in selftests |
| pysnmp | SNMPv2c polling of the agent (CPU, memory, interface octets) |
| pygnmi + gRPC | The emulated gNMI service and its pull client |
| Flask + Chart.js | Dashboard backend and frontend charts |
| SQLite (WAL) | Single shared database `db/telemetry.db` with six tables |
| tcpdump, iperf3 | Packet capture for the softflowd FIFO pipeline; traffic generation |
| Windows 11 + WSL2 (Ubuntu) | Host environment: everything runs inside WSL, dashboard opens in the Windows browser |

---

# METHODOLOGY

## Architecture

```
                         +-------- emulated network (Mininet, WSL) -------+
                         |                                              |
   INT path              |  h1 -- s1 (P4) -- s2 (P4) -- h2              |
   UDP/4000 + stack      |                                          h3  |
   (1 entry per switch)  |                                          h4  |
                         +----------------------------------------------+
                        (every path below this line hits the same DB)

 INT:   h1 --int_sender--> P4 switches add metadata --> int_receiver on h2
 sFlow: OVS s1 samples every pkt --> 127.0.0.1:6343 --> sflow_collector
 NetFlow: softflowd(h1, v5) --> h4:9995 ----------------> netflow_collector
 IPFIX:  softflowd(h3, v10) --> h4:9996 ----------------> ipfix_collector
 SNMP:   snmpd(h4, agent) <-- 5s poll <-- snmp_poller (root netns)
 gNMI:   gnmi_agent (emulated gNMI svc over P4Runtime counters) <-- 2s
           <-- gnmi_client (pygnmi Get, gRPC)

              all -> db/telemetry.db (SQLite, WAL) -> dashboard/app.py
                                                        -> http://localhost:5000
```

*Figure 1: Architectural diagram.*

## INT data plane (P4)

`p4/int.p4` is a P4-16 v1model program. The sender emits UDP/4000 packets
carrying an INT header; in the **egress** pipeline each of the two P4
switches appends a 12-byte stack entry `{switch_id, ingress_ts,
enq_qdepth}` (queue depth is only readable at egress, so metadata
insertion moved there). The receiver on h2 sniffs with scapy, parses the
stack, and computes per-hop latency with boot-offset calibration (BMv2
per-switch clocks are not synchronized, so relative latencies are
accurate). A 1000-packet burst with s2 throttled (`set_queue_rate 500`)
produces the queue spike that motivates the whole project.

## Collectors and database

Each collector parses its protocol and inserts rows through the shared
helper `db/telemetry.py` into `db/telemetry.db` (SQLite, WAL mode, 24 h
row cleanup). Six tables: `int_hops` (per hop: switch_id, latency, jitter,
queue_occupancy), `sflow_samples` (5-tuples + interface counters +
bandwidth), `netflow_flows` and `ipfix_flows` (flow records), `snmp_stats`
(CPU, memory, octets, bandwidth per 5 s poll), `gnmi_stats` (one row per
OpenConfig leaf per 2 s Get). Every collector ships a `--selftest` mode
that verifies parsing and DB writes without Mininet.

## Dashboard

`dashboard/app.py` serves the page and two APIs: `/api/<source>` returns
the last 200 rows per table, `/api/status` returns live badges (a source
is *live* if a row arrived in the last 60 s). Six tabs, 5 s auto-refresh,
Chart.js rendering.

## End-to-end verification

`run_all.sh` runs the full stack in sequence — INT demo, OVS
sFlow/NetFlow/IPFIX, SNMP, gNMI, then the dashboard — and asserts every
table is non-empty. A representative real run:

```
int_hops       350
sflow_samples  170802
netflow_flows  4
ipfix_flows    9
snmp_stats     3
gnmi_stats     180
ALL 6 TABLES NON-EMPTY: PASS
```

The dashboard is then reachable from a normal browser at
http://localhost:5000.

---

# REFERENCES

1. Case, J., Fedor, M., Schoffstall, M., & Davin, J. (1990). *A Simple
   Network Management Protocol (SNMP)*. RFC 1157. https://doi.org/10.17487/RFC1157
2. Claise, B. (Ed.). (2008). *Specification of the IP Flow Information
   Export (IPFIX) Protocol*. RFC 5101. https://doi.org/10.17487/RFC5101
3. Phaal, P., Panchen, S., & McKee, N. (2001). *InMon Corporation's
   sFlow: A Method for Monitoring Traffic in Switched and Routed
   Networks*. RFC 3176. https://doi.org/10.17487/RFC3176
4. Cisco Systems. (2001). *NetFlow Services Export Version 9*. RFC 3954.
   https://doi.org/10.17487/RFC3954
5. OpenConfig / gNMI Working Group. (2016). *gRPC Network Management
   Interface (gNMI) Specification*. https://github.com/openconfig/gnmi
6. P4.org. (2016). *In-band Network Telemetry (INT) Dataplane
   Specification*. https://github.com/p4lang/p4-applications
7. Bosshart, P., Daly, D., Gibb, G., et al. (2014). *P4: Programming
   Protocol-Independent Packet Processors*. ACM SIGCOMM Computer
   Communication Review, 44(3), 87–95.
8. Lantz, B., Heller, B., & McKeown, N. (2010). *A Network in a Laptop:
   Rapid Prototyping for Software-Defined Networks*. ACM SIGCOMM
   CoNEXT 2010.
9. p4lang. *behavioral-model (BMv2) reference switch*.
   https://github.com/p4lang/behavioral-model
10. Mininet Project. https://mininet.org