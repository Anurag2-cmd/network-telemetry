# Network Telemetry — Written Report

An emulated 6-protocol telemetry stack (SNMP, NetFlow v5, sFlow, IPFIX,
gNMI, INT) built on Mininet + P4/BMv2 + Open vSwitch, feeding one SQLite
database and a real-time Flask dashboard.

*Course assignment — written report covering the four problem objectives.
All figures cited below come from actual runs of this project (the
task-11 end-to-end run and the per-protocol demos).*

---

## 1. Definition & role of network telemetry

**Network telemetry** is the automated collection of measurement data from
network devices — counters, state, flows, or per-packet metadata — its
transport to collectors, and its analysis to understand a network's
behavior. It answers one question that traditional management cannot:
*what is actually happening inside the network right now?*

Its role in modern networks is foundational:

| Domain | Why telemetry matters there |
|---|---|
| Cloud data centers | Fast, fine-grained feedback for load balancing and loss detection |
| SDN (Software-Defined Networking) | The control plane needs live state from the data plane to make decisions |
| 5G/6G & edge | Strict latency budgets (URLLC) require sub-second visibility into queueing |
| IoT / large-scale fleets | Millions of devices need low-overhead, streaming status collection |

**This project is a complete miniature of that idea.** An emulated network
with six telemetry technologies exports data to a shared database, and a
dashboard visualizes it in real time. The most modern technique, INT
(In-band Network Telemetry), literally stamps each packet as it crosses
each switch, so the collector learns per-hop queue occupancy and latency —
the network carries its own diagnostics.

## 2. Telemetry vs. traditional monitoring

The classic contrast is **pull** (request/response) vs. **push**
(device-initiated stream):

| Aspect | Traditional (SNMP polling) | Streaming telemetry (gNMI, INT) |
|---|---|---|
| Direction | Poller asks, agent answers | Device pushes continuously |
| Granularity | Poll interval (here 5 s; typically 30-300 s) | Sub-second; INT is per-packet |
| Data | Coarse counters (CPU, octets) | Fine-grained: queue depth, per-hop latency |
| Microburst detection | Misses bursts shorter than the poll interval | Sees every packet's queue depth |
| Protocol | SNMP over UDP, request/response | gRPC/gNMI; metadata in-band (INT) |

**The classic failure example — and our demo's evidence.** A microburst
(1000 packets in <1 s) can cause queue buildup and drops that a 5 s SNMP
poll completely misses: the interface counters *eventually* reflect the
octets, but the *transient queue spike* is invisible.

Our INT demo reproduces exactly this. We throttled switch s2's egress
rate (`set_queue_rate 500`) and sent a 1000-packet burst back-to-back.
The receiver's records show the queue filling in real time:

```
switch_id=2 lat_us=22392.0 qdepth=43
switch_id=2 lat_us=22848.0 qdepth=44
switch_id=2 lat_us=23350.0 qdepth=45
```

**enq_qdepth jumped to 43-45** during the burst (the tail of the burst is
drained after; only ~130 of the 1000 packets got through — the rest were
dropped). SNMP, polling every 5 s, would see only the final counter values
and never the queue itself. The INT tab of the dashboard shows the spike
live; the SNMP tab shows only slow counter deltas. **This is the
motivation for the entire field of modern telemetry.**

## 3. Evolution of network telemetry (all four generations built here)

### Generation 1 — SNMP (1990s, pull)
Management Information Bases (MIBs) exposed as OIDs; a manager polls an
agent. Still ubiquitous for basic health, but coarse and slow.

**In our project:** `snmpd` runs inside host h4 (the "network device");
`tools/snmp_poller.py` polls it every 5 s over SNMPv2c (`public`) and
stores CPU load, memory %, interface octets, and bandwidth derived from
octet deltas into `snmp_stats`. In the task-8 demo the poller measured
**up to 2.4 Gb/s** on `bw_in_mbps` while iperf ran into the device —
visible as slow, counter-based curves on the dashboard's SNMP tab.

### Generation 2 — Flow-based (NetFlow 1995 / sFlow 2003 / IPFIX 2008)
Instead of raw counters, devices export **flow records** (who talks to
whom: IPs, ports, protocol, packets, bytes) or **sampled packet headers**.
Cheaper than per-packet capture, aggregate views, but sampled/aggregated —
detail is lost.

**In our project (we built all three):**

- **NetFlow v5** — `softflowd` on h1 exports flow records to
  `netflow_collector` (UDP/9995) on collector host h4. E2E run:
  `netflow_flows` table received the h1→h2 TCP flow records (6 rows in
  the task-11 run) with packets/bytes aggregates.
- **sFlow v5** — OVS switch s1 samples every packet (sampling=1) plus
  interface counters every 10 s to `sflow_collector` (UDP/6343). E2E run:
  **375,251 sample rows**; the task-6 full run recorded **172k rows
  including 167k h1→h2 TCP flow samples**, with bandwidth rows derived
  from counter-poll deltas.
- **IPFIX (NetFlow v10)** — `softflowd` on h3 exports to
  `ipfix_collector` (UDP/9996), which learns **dynamic templates** and
  decodes IPv4 *and* IPv6 fields. E2E run: 11 rows, template IE sets
  including octetDeltaCount/packetDeltaCount/flowStart/flowEnd.

### Generation 3 — Streaming / model-driven (gNMI + gRPC + YANG, 2016+)
Devices push OpenConfig-modeled state over gRPC. Model-driven: the schema
is negotiated (Capabilities), subscriptions replace polling, sub-second
updates.

**In our project:** `tools/gnmi_agent.py` implements the gNMI service
(Get / Capabilities / Subscribe) exposing OpenConfig-style interface state
(`/interfaces/interface[name=X]/state/counters/in-octets`, `oper-status`,
...) backed by the real P4Runtime port counters; `tools/gnmi_client.py`
pulls over gRPC every 2 s into `gnmi_stats`. E2E run: **540 rows**; the
task-9 demo showed counters growing with traffic — in-octets **0 → 1694**,
out-octets **1984 → 3440**, oper-status **UP** once packets were observed.

### Generation 4 — In-Band Network Telemetry (INT with P4, 2016+)
The device *stamps packets in flight*: each switch appends metadata
(switch ID, ingress timestamp, queue depth) to the packet itself. Per-hop
visibility with **zero extra network load** — no collectors to poll, no
export streams; the data rides the traffic.

**In our project:** `p4/int.p4` is a P4-16 v1model program for BMv2:
the sender emits UDP/4000 packets with an INT header; each of the two
P4 switches (s1, s2) appends a 12-byte stack entry `{switch_id,
ingress_ts, enq_qdepth}` in the egress pipeline; `tools/int_receiver.py`
on h2 sniffs, parses the stack, and computes **per-hop latency and
jitter** with clock-offset calibration, storing rows per hop in
`int_hops`. Task-11 E2E: 460 rows across both switches; our burst demo
showed the queue spike (Section 2). Latency between hops was
microseconds at rest and ~22 ms while the queue was 45 deep — queueing
delay is directly observable.

## 4. Architecture components (with our mapping)

```
                         +-------- emulated network (Mininet, WSL) -------+
                         |                                              |
   INT path              |  h1 -- s1 (P4) -- s2 (P4) -- h2              |
   UDP/4000 + stack      |                                          h3  |
   (1 entry per switch)  |                                              |
                         +----------------------------------------------+

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

| Component | Role | In this project |
|---|---|---|
| Telemetry-enabled devices | Produce the data | P4 `simple_switch` (INT + port counters), OVS `s1` (sFlow exporter), `softflowd` agents on h1/h3 (NetFlow v5 / IPFIX v10), `snmpd` on h4 (SNMP agent), `simple_switch_grpc` + `gnmi_agent` (gNMI service) |
| Collectors | Receive, decode, store | Python UDP collectors (6343/9995/9996), SNMP poller, gNMI pull client — all writing `db/telemetry.db` (SQLite, WAL) |
| Analytics | Turn raw data into insight | Per-hop latency/jitter & queue occupancy (INT), bandwidth from counter deltas (sFlow/SNMP), top flows (NetFlow/IPFIX), interface counter growth (gNMI) |
| Visualization | Present it live | Flask `dashboard/app.py` + Chart.js: one tab per protocol, `/api/<source>` last-200 rows, live badges (60 s window), 5 s auto-refresh |

## 5. The six protocols compared

| Protocol | Mechanism | Granularity | Overhead | Typical data | Problem it solved |
|---|---|---|---|---|---|
| SNMP | Pull (request/response) | 5-300 s | Low | CPU, mem, octet counters | Basic device health — the 1990s baseline |
| NetFlow v5 | Push (flow records) | Per-flow, export on timeout | Low (aggregates) | 5-tuple flows, pkts, bytes | Traffic analysis without full capture |
| sFlow | Push (sampled packets + counters) | Every packet (sampling=1) / 10 s counters | Moderate | Sampled headers, ports, octets | Continuous traffic view on high-speed links |
| IPFIX | Push (flexible templates) | Per-flow | Low | Template-encoded flows, IPv6, custom IEs | Standardized, extensible flow export |
| gNMI | Push/Pull over gRPC, model-driven | Sub-second (2 s here) | Low | OpenConfig interface state | Streaming, schema-negotiated device state |
| INT | In-band (metadata in packets) | Per packet per hop | In-packet bytes only | switch_id, ingress_ts, queue depth | Per-hop, zero-network-load visibility |

## 6. Lessons learned & limitations (honest assessment)

- **BMv2 clocks are not synchronized.** `ingress_global_timestamp` is a
  per-switch µs counter since switch boot. The receiver calibrates the
  constant boot offset from the first packet of each flow, so *relative*
  per-hop latency and jitter are accurate; absolute values are not.
- **Sampling bias (sFlow).** With sampling=1 in an emulator everything is
  captured, but on real high-speed links sampling is statistical — rare
  events (short bursts) can be missed. Counter-poll-based bandwidth is
  also an average over the poll window, not instantaneous.
- **Flow timeout effects (softflowd).** Flow records only appear when the
  flow ends or the ~10-60 s timeout fires, so short-lived flows show up
  with delay — acceptable for aggregates, misleading for real-time
  troubleshooting (the exact gap INT fills).
- **SNMP vs. microbursts.** The 5 s poll cannot see the 45-deep queue
  spike INT recorded (Section 2) — the fundamental pull-vs-push argument,
  demonstrated rather than asserted.
- **Emulated gNMI.** The BMv2 build ships no native gNMI service, so the
  agent emulates it over the real P4Runtime counters (documented in
  `tasks/09-gnmi-client.md`). The protocol interaction is genuine gRPC;
  the data source is the switch's real counters.
- **Emulation scale.** Speeds, queue depths and latencies are Mininet/BMv2
  artifacts — ideal for teaching and comparison, not production numbers.

## 7. Sample outputs (from real runs)

```text
$ python3 scripts/wsl-tmp/e2e-check.sh
int_hops       460        # task-11 E2E: 2-hop INT packets, both switches
sflow_samples  375251     # task-11 E2E: sampled packets + counter polls
netflow_flows  6          # softflowd v5 exports (h1 -> h4)
ipfix_flows    11         # softflowd v10 exports (h3 -> h4)
snmp_stats     10         # 5 s polls of the snmpd agent
gnmi_stats     540        # 2 s gNMI Get polls, OpenConfig counters
```

```text
$ sqlite3 db/telemetry.db "SELECT switch_id, hop_latency_us, queue_occupancy
                           FROM int_hops ORDER BY ts DESC LIMIT 6"
2 | 23350.0 | 45        # s2, burst tail: 45 packets queued, 22 ms delay
2 | 22848.0 | 44
2 | 22392.0 | 43
1 |     0.0 | 0
```

Dashboard: six tabs (INT / sFlow / NetFlow / IPFIX / SNMP / gNMI) each
polling `/api/<source>` every 5 s; the INT tab plots per-hop latency,
jitter, and queue occupancy — the queue spike of Section 2 is the demo
centerpiece. Live badges go green while collectors write rows.

---

*How to reproduce every number in this report: `sudo bash run_all.sh` in
WSL, then open http://localhost:5000 (see README.md).*
