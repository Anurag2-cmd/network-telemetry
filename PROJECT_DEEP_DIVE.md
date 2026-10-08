# Network Telemetry — Complete Codebase Deep Dive & Architectural Guide

This document provides a comprehensive, file-by-file breakdown of the entire **Network Telemetry Stack** project. It explains the networking principles, database architecture, binary protocols, Python & P4 implementations, and execution workflows required to understand every line of code.

---

## Table of Contents

1. [Executive Summary & Concept Overview](#1-executive-summary--concept-overview)
2. [System Architecture & Data Flow](#2-system-architecture--data-flow)
3. [Database Layer (`db/telemetry.py`)](#3-database-layer-dbtelemetrypy)
4. [Protocol 1: In-Band Network Telemetry (INT)](#4-protocol-1-in-band-network-telemetry-int)
   - [`p4/int.p4`](#p4intp4)
   - [`mn/topology_int.py` & `mn/topology_int_demo.py`](#mntopology_intpy--mntopology_int_demopy)
   - [`tools/int_sender.py` & `tools/int_receiver.py`](#toolsint_senderpy--toolsint_receiverpy)
5. [Protocol 2: sFlow v5](#5-protocol-2-sflow-v5)
   - [`tools/sflow_collector.py`](#toolssflow_collectorpy)
6. [Protocols 3 & 4: NetFlow v5 & IPFIX (v10)](#6-protocols-3--4-netflow-v5--ipfix-v10)
   - [`mn/topology_ovs.py`](#mntopology_ovspy)
   - [`tools/netflow_collector.py`](#toolsnetflow_collectorpy)
   - [`tools/ipfix_collector.py`](#toolsipfix_collectorpy)
7. [Protocol 5: SNMP v2c](#7-protocol-5-snmp-v2c)
   - [`mn/topology_snmp.py`](#mntopology_snmppy)
   - [`tools/snmp_poller.py`](#toolssnmp_pollerpy)
8. [Protocol 6: gNMI (gRPC Network Management Interface)](#8-protocol-6-gnmi-grpc-network-management-interface)
   - [`tools/gnmi_agent.py`](#toolsgnmi_agentpy)
   - [`tools/gnmi_client.py`](#toolsgnmi_clientpy)
9. [Dashboard & API Layer](#9-dashboard--api-layer)
   - [`dashboard/db.py` & `dashboard/app.py`](#dashboarddbpy--dashboardapppy)
10. [End-to-End Execution Flow (`run_all.sh`)](#10-end-to-end-execution-flow-run_allsh)
11. [Complete File-by-File Summary Table](#11-complete-file-by-file-summary-table)

---

## 1. Executive Summary & Concept Overview

Traditional network monitoring relies on **pull-based SNMP polling** (e.g., asking a switch for total byte counters every 5 seconds). While sufficient for basic device uptime, polling is blind to micro-burst congestion, transient packet drops, and short-lived flow dynamics.

Modern telemetry moves from **polling** to **streaming, flow exporting, and in-band packet stamping**:

| Telemetry Generation | Protocol | Primary Mechanism | Data Granularity |
|---|---|---|---|
| **Gen 1: Legacy Polling** | **SNMP** | Pull-based SNMPv2c GET queries every 5s | Device aggregates (CPU, Mem, Interface totals) |
| **Gen 2: Flow & Sampling** | **sFlow** | 1:1 packet header sampling + counter export | Sampled packet headers & interface deltas |
| **Gen 2: Flow Aggregation** | **NetFlow v5** | Aggregated flow record export on connection end | L3/L4 5-tuple, packet/byte counts |
| **Gen 2: Dynamic Flow** | **IPFIX (v10)** | Template-driven flexible flow record export | Extensible L3/L4 metrics & IPv6 support |
| **Gen 3: Streaming Model** | **gNMI** | gRPC/OpenConfig model-driven state streaming | Structured interface counters & operational state |
| **Gen 4: In-Band Hardware** | **INT** | Custom P4 headers appended per packet at wire speed | Per-packet, per-hop latency, jitter, queue depth |

This project builds an emulated network in **WSL2 / Mininet**, runs all 6 protocols concurrently over identical synthetic traffic streams, writes all telemetry into a shared SQLite database, and presents the real-time metrics on a unified web dashboard.

---

## 2. System Architecture & Data Flow

```
                         +-------- Emulated Network (Mininet, WSL2) -------+
                                              |
   INT Path              |  h1 -- s1 (P4) -- s2 (P4) -- h2              |
   UDP/4000 + Stack      |                                          h3  |
   (1 entry per switch)  |                                          h4  |
                         +----------------------------------------------+
                        (all collectors funnel metrics into SQLite DB)

  INT:      h1 --int_sender--> P4 switches stamp metadata --> int_receiver (h2)
  sFlow:    OVS s1 samples packets --> 127.0.0.1:6343 ---------> sflow_collector
  NetFlow:  softflowd(h1, v5) ---------> 127.0.0.1:9995 -------> netflow_collector
  IPFIX:    softflowd(h3, v10) --------> 127.0.0.1:9996 -------> ipfix_collector
  SNMP:     snmpd(h4 agent) <-- 5s poll ------------------------> snmp_poller
  gNMI:     gnmi_agent (P4Runtime counters) <-- 2s pull --------> gnmi_client

                all ---> db/telemetry.db (SQLite WAL Mode)
                                  |
                           dashboard/app.py ---> http://localhost:5000
```

---

## 3. Database Layer (`db/telemetry.py`)

The database module manages concurrent writes from six independent collector processes and reads from the Flask application.

### Key Code Mechanisms:
1. **WAL Mode (`PRAGMA journal_mode=WAL`)**:
   - Standard SQLite locking blocks writers when another process is reading or writing.
   - **Write-Ahead Logging (WAL)** allows multiple collectors to write simultaneously while the Flask dashboard reads without throwing "database locked" errors.
2. **Busy Timeout (`sqlite3.connect(..., timeout=30)`)**:
   - Waits up to 30 seconds if a write transaction is temporarily queued.
3. **Batch Insertion (`insert_rows`)**:
   - Uses `executemany` for high-throughput batch insertions.
4. **Automatic Retention Cleanup (`cleanup_old_rows`)**:
   - Automatically deletes rows older than 24 hours (`ts < current_time - 86400`) on collector startup and periodic flushes.

### Schema Summary:
- `int_hops`: `(ts, flow, hop_idx, switch_id, ingress_ts, hop_latency_us, jitter_us, queue_occupancy)`
- `sflow_samples`: `(ts, agent, src_ip, dst_ip, src_port, dst_port, proto, bytes_sampled, in_port, out_port, if_in_octets, if_out_octets, bandwidth_in_mbps, bandwidth_out_mbps)`
- `netflow_flows`: `(ts, src_ip, dst_ip, src_port, dst_port, proto, tcp_flags, packets, bytes, first_ts, last_ts)`
- `ipfix_flows`: `(ts, src_ip, dst_ip, src_port, dst_port, proto, packets, bytes, first_ts, last_ts)`
- `snmp_stats`: `(ts, device, cpu_load, mem_used_pct, if_octets_in, if_octets_out, bw_in_mbps, bw_out_mbps, uptime)`
- `gnmi_stats`: `(ts, path, key, value, int_value)`

---

## 4. Protocol 1: In-Band Network Telemetry (INT)

### 4.1 Dataplane: `p4/int.p4`
A P4-16 program compiled into `p4/int.json` and loaded into BMv2 (`simple_switch`).

- **Custom Headers**:
  - `int_header_t` (4 bytes): Contains `ver=0xF`, `count` (number of hop stack entries), `length` (bytes = $12 \times \text{count}$).
  - `int_metadata_t` (12 bytes): `{switch_id (4B), ingress_ts (4B), enq_qdepth (2B), padding (2B)}`.
- **Egress Processing (`MyEgress`)**:
  - *Why Egress?* In BMv2's `v1model`, `standard_metadata.enq_qdepth` (queue depth) is only populated **after** ingress processing when the packet enters the egress queue.
  - Adds a new 12-byte metadata entry to `int_meta[count]`.
  - Increments `count` by 1 and updates `ipv4.totalLen` and `udp.length` by $+12$ bytes.
  - Sets `udp.checksum = 0` (valid for IPv4: checksum 0 means checksum disabled).

### 4.2 Topology: `mn/topology_int.py` & `mn/topology_int_demo.py`
- Instantiates a Mininet network with 2 P4 switches (`s1`, `s2`) and 3 hosts (`h1`, `h2`, `h3`).
- Programs flow tables via `simple_switch_CLI`:
  - Sets `swid_table` to output `switch_id=1` for `s1` and `switch_id=2` for `s2`.
- `topology_int_demo.py`:
  - Runs `int_receiver.py` on `h2`.
  - Throttles `s2` egress queue rate to 500 pps using `simple_switch_CLI set_queue_rate 500`.
  - Fires a 1,000-packet burst from `h1` using `int_sender.py --burst` to trigger enqueued packet accumulation and verify queue occupancy spikes in `int_hops`.

### 4.3 Endpoints: `tools/int_sender.py` & `tools/int_receiver.py`
- **Sender (`int_sender.py`)**:
  - Generates UDP/4000 packets with an initial 4-byte INT header (`0xF0000000`, `count=0`).
- **Receiver (`int_receiver.py`)**:
  - Sniffs UDP port 4000 on host `h2` using Scapy.
  - **Clock Calibration**: BMv2 switches use independent, non-synchronized boot clocks (`ingress_global_timestamp` in $\mu$s since switch boot).
  - The receiver uses the first packet of a flow to record the baseline clock offset between switch pairs:
    $$\text{offset}_{i} = \text{ts}_{\text{switch}_i} - \text{ts}_{\text{switch}_{i-1}}$$
  - Subsequent packet latency is calculated as $\text{latency} = \text{raw\_delta} - \text{offset}$.
  - Calculates jitter as $\text{jitter} = |\text{latency}_{\text{current}} - \text{latency}_{\text{previous}}|$.
  - Inserts individual hop records into `int_hops`.

---

## 5. Protocol 2: sFlow v5

### Code File: `tools/sflow_collector.py`
Listens for sFlow v5 UDP datagrams exported by Open vSwitch on port `6343`.

- **Datagram Layout & Binary Unpacking**:
  - Unpacks the sFlow header (`version=5`, `agent_address`, `num_samples`).
  - **Sample Type 1 (Flow Sample)**: Unpacks raw sampled Ethernet/IPv4 packet headers to extract source/destination IPs, ports, protocol, and sampling rate.
  - **Sample Type 2 (Counters Sample)**: Unpacks generic interface counters (`ifInOctets`, `ifOutOctets`).
- **`BandwidthTracker`**:
  - Tracks previous octet counts for each `(agent, ifIndex)` pair.
  - Computes throughput between samples:
    $$\text{bandwidth\_in\_mbps} = \frac{(\text{ifInOctets}_{\text{new}} - \text{ifInOctets}_{\text{old}}) \times 8}{\Delta t \times 10^6}$$
- Batches and inserts parsed records into `sflow_samples`.

---

## 6. Protocols 3 & 4: NetFlow v5 & IPFIX (v10)

### Topology & WSL2 Workaround: `mn/topology_ovs.py`
- Creates an OVS learning switch network connecting hosts `h1`, `h2`, `h3`, `h4`.
- **WSL2 Kernel Workaround**:
  - `softflowd` live libpcap packet capture receives 0 packets under WSL2's virtual network interface driver.
  - **Solution**: `mn/topology_ovs.py` starts `tcpdump -U` (line-buffered packet flush) writing to a named pipe FIFO (`/tmp/nf5.pcap` and `/tmp/ipfix.pcap`).
  - `softflowd -r /tmp/nf5.pcap` reads the FIFO and exports flow datagrams to collector host `h4`.

### 6.1 NetFlow v5 Collector: `tools/netflow_collector.py`
- Listens on UDP port `9995`.
- Unpacks fixed 24-byte header followed by $N \times 48\text{-byte}$ flow records (`src_ip`, `dst_ip`, `src_port`, `dst_port`, `proto`, `tcp_flags`, `packets`, `bytes`, `first_ts`, `last_ts`).
- Batches and writes parsed flows into `netflow_flows`.

### 6.2 IPFIX Collector: `tools/ipfix_collector.py`
- Listens on UDP port `9996`.
- **Dynamic Template Decoder**:
  - NetFlow v5 uses rigid fields, but IPFIX (NetFlow v10) uses dynamic templates.
  - `ipfix_collector.py` parses Set ID `2` (Template Sets) to build an in-memory mapping of Information Elements (e.g. IE 8 = `sourceIPv4Address`, IE 27 = `sourceIPv6Address`, IE 1 = `octetDeltaCount`).
  - Parses Set ID $\ge 256$ (Data Sets) using the dynamic template maps.
  - Formats IPv4 and IPv6 strings and inserts flow records into `ipfix_flows`.

---

## 7. Protocol 5: SNMP v2c

### 7.1 Topology & Root Namespace Port: `mn/topology_snmp.py`
- Host `h4` runs the `snmpd` daemon with a minimal configuration (`rocommunity public`).
- **OVS Internal Port (`nt0`)**: Mininet hosts reside in isolated network namespaces (`netns`). To allow `snmp_poller.py` running in the root WSL namespace to reach `h4` (`10.0.1.4`), `topology_snmp.py` adds an OVS internal port `nt0` with IP `10.0.1.254/24` in the root netns.

### 7.2 Poller: `tools/snmp_poller.py`
- Runs an asynchronous polling loop using `pysnmp` every 5 seconds.
- `fetch_scalars`: Issues an SNMP GET request for 1-minute CPU load (`1.3.6.1.4.1.2021.10.1.5.1`), total memory, available memory, and system uptime (`1.3.6.1.2.1.1.3.0`).
- `walk_octets`: Issues an SNMP BULK WALK request for `ifInOctets` (`1.3.6.1.2.1.2.2.1.10`) and `ifOutOctets` (`1.3.6.1.2.1.2.2.1.16`).
- Identifies the active interface (largest octet count) and calculates throughput deltas, writing results to `snmp_stats`.

---

## 8. Protocol 6: gNMI (gRPC Network Management Interface)

### 8.1 gNMI Server: `tools/gnmi_agent.py`
- Implements a full gRPC server matching the official `gnmi.proto` specification (`Get`, `Capabilities`, `Subscribe`).
- **`SwitchCounterPoller`**: A background thread periodically executes `simple_switch_CLI counter_read port_counters_in <port>` on the BMv2 P4 switch.
- Maps internal P4 counters to standard OpenConfig data model paths:
  - `/interfaces/interface[name=<port>]/state/counters/in-octets`
  - `/interfaces/interface[name=<port>]/state/counters/out-octets`
  - `/interfaces/interface[name=<port>]/state/oper-status`

### 8.2 gNMI Pull Client: `tools/gnmi_client.py`
- Uses `pygnmi` to issue gNMI `Get` requests to `127.0.0.1:9339` every 2 seconds over an insecure gRPC channel.
- Flattens the returned hierarchical OpenConfig JSON tree into key-value pairs and writes them to `gnmi_stats`.

---

## 9. Dashboard & API Layer

### 9.1 Database Abstraction: `dashboard/db.py`
- `last_rows(table, n=200)`: Retrieves the 200 most recent records ordered chronologically (`ts ASC`).
- `status()`: Queries `MAX(ts)` across all 6 tables to determine protocol liveness (badge turns green if data was received within the active window).

### 9.2 Flask Server: `dashboard/app.py`
- Serves the dashboard on `http://localhost:5000`.
- **API Endpoints**:
  - `GET /`: Serves `dashboard/templates/index.html`.
  - `GET /api/<source>`: Returns JSON telemetry rows for `int`, `sflow`, `netflow`, `ipfix`, `snmp`, or `gnmi`.
  - `GET /api/status`: Returns protocol liveness metrics for the frontend badges.

---

## 10. End-to-End Execution Flow (`run_all.sh`)

When `sudo bash run_all.sh` is executed, the orchestrator executes the following pipeline:

```
[run_all.sh]
   │
   ├── 1. Pre-flight Cleanup: Terminates stale Mininet, OVS, iperf3, and collector processes.
   ├── 2. Database Reset: Wipes existing rows across all tables in db/telemetry.db.
   ├── 3. Stage 1 (INT): Executes topology_int_demo.py -> Runs P4 switch + receiver + traffic burst.
   │      └── Assertion: SELECT COUNT(*) FROM int_hops > 0
   ├── 4. Stage 2 (OVS Flows): Executes topology_ovs.py -> Runs sFlow + softflowd + iperf3 streams.
   │      └── Assertion: SELECT COUNT(*) FROM sflow_samples / netflow_flows / ipfix_flows > 0
   ├── 5. Stage 3 (SNMP): Executes topology_snmp.py -> Launches snmpd + snmp_poller.py + iperf3.
   │      └── Assertion: SELECT COUNT(*) FROM snmp_stats > 0
   ├── 6. Stage 4 (gNMI): Executes scripts/wsl-tmp/e2e-gnmi.sh -> Starts gNMI agent & pull client.
   │      └── Assertion: SELECT COUNT(*) FROM gnmi_stats > 0
   ├── 7. Stage 5 (Dashboard): Spawns Flask web server (dashboard/app.py) on port 5000.
   └── 8. Verification Summary: Verifies all 6 database tables contain non-zero row counts.
```

---

## 11. Complete File-by-File Summary Table

| File Path | Component | Description & Responsibilities |
|---|---|---|
| `run_all.sh` | Orchestration | Automated shell script running end-to-end tests across all 6 protocols and validating DB table insertions. |
| `db/telemetry.py` | Storage | Shared SQLite helper enabling WAL mode, schema initialization, batch insertions, and automated record pruning. |
| `p4/int.p4` | Dataplane | P4-16 program defining INT headers, parser logic, port counter state, and egress metadata insertion. |
| `mn/topology_int.py` | Topology | Mininet script defining 2 P4 switch topology (`s1`, `s2`) and programming forwarding table rules. |
| `mn/topology_int_demo.py` | Automation | Runs INT end-to-end test stage with queue rate throttling to demonstrate queue occupancy spikes under burst traffic. |
| `mn/topology_ovs.py` | Topology | Mininet script defining OVS learning topology, sFlow export config, and host `softflowd` FIFO capture streams. |
| `mn/topology_snmp.py` | Topology | Mininet script configuring `snmpd` inside host `h4` and creating root namespace internal bridge port `nt0`. |
| `tools/int_sender.py` | Traffic Gen | Constructs UDP/4000 packets with INT base headers in standard or `--burst` queue-saturation mode. |
| `tools/int_receiver.py` | Collector | Scapy sniffer parsing INT headers, calibrating inter-switch boot clock offsets, and calculating latency/jitter. |
| `tools/sflow_collector.py` | Collector | UDP/6343 binary parser extracting sFlow v5 packet header samples and calculating interface bandwidth deltas. |
| `tools/netflow_collector.py` | Collector | UDP/9995 binary parser processing fixed 48-byte NetFlow v5 flow records into `netflow_flows`. |
| `tools/ipfix_collector.py` | Collector | UDP/9996 dynamic template decoder parsing IPFIX (v10) flow records (IPv4 & IPv6) into `ipfix_flows`. |
| `tools/snmp_poller.py` | Collector | Asynchronous SNMPv2c poller querying CPU, memory, interface octets, and uptime every 5 seconds. |
| `tools/gnmi_agent.py` | Agent | gRPC server implementing gNMI (`Get`/`Subscribe`) over BMv2 P4Runtime interface counters using OpenConfig models. |
| `tools/gnmi_client.py` | Collector | `pygnmi` client polling `gnmi_agent.py` every 2 seconds and storing key-value state in `gnmi_stats`. |
| `dashboard/db.py` | Backend Helper | Query functions retrieving last 200 rows per source and evaluating per-protocol liveness status. |
| `dashboard/app.py` | Web Server | Flask server providing REST API endpoints (`/api/<source>`, `/api/status`) and serving Chart.js frontend. |
| `dashboard/templates/index.html` | Frontend | Single-page UI with tabbed Chart.js plots and status badges for real-time visualization. |
