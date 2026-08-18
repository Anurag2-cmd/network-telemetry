# Task 12: Written report (assignment objectives)

## Goal
Produce `report.md` (project root, in the language the course requires — ask the
user; Vietnamese and English drafts both fine) covering the 4 problem objectives,
grounded in THIS project's implementation. Use diagrams where useful.

## Outline (map 1:1 to the assignment)
1. **Definition & role** — define network telemetry; role in modern networks
   (cloud DCs, SDN, 5G/6G, edge, IoT). Cite this project: emulated topology,
   streaming per-packet INT data, model-driven gNMI.
2. **Telemetry vs traditional monitoring** — table comparing:
   SNMP polling (pull, 5-30 s granularity, coarse counters, request/response)
   vs streaming telemetry (push, sub-second, fine-grained, event-driven).
   Include the classic example: SNMP misses microbursts, INT sees queue depth
   per packet per hop (show the burst→enq_qdepth spike from our demo as evidence).
3. **Evolution** — timeline with the 4 generations:
   SNMP (1990s, pull) → flow-based (NetFlow 1996 / sFlow 2003 / IPFIX 2008:
   sampled aggregates, flow records) → streaming telemetry (gNMI/gRPC, YANG
   models, 2016+, push, model-driven) → In-Band Network Telemetry (INT, P4,
   2016+: metadata inside packets, per-hop visibility, zero extra network load).
   Each generation: how our project demonstrates it (we built ALL FOUR).
4. **Architecture components** — with our mapping:
   - telemetry-enabled devices (P4 simple_switch with INT, OVS with sFlow,
     softflowd agents, snmpd agent, simple_switch_grpc gNMI agent)
   - collectors (Python UDP/SNMP/gRPC collectors → SQLite)
   - analytics (per-hop latency/jitter, queue occupancy, bandwidth from counters,
     top flows)
   - visualization (Flask + Chart.js tabs)
   Include an ASCII architecture diagram.

## Extra material that earns credit
- Comparison table of the 6 protocols used: mechanism (pull/push/in-band),
  granularity, overhead, typical data, "what problem it solved".
- Limitation notes: bmv2 per-switch timestamps (not synchronized), sampling
  bias of sFlow, flow timeout effects in softflowd, SNMP polling interval vs
  microbursts — a "lessons learned" section shows depth.
- Screenshots section: dashboard tabs, tcpdump INT bytes, sqlite queries.

## Verification (Definition of Done)
- report.md covers all 4 objectives with sections referencing actual demo
  results (real numbers from our runs: e.g., "s1 reported enq_qdepth 45 during
  burst", "sFlow bandwidth matched iperf 92 Mb/s").
- README links to report.md.

## Notes
- The report should be understandable by the instructor WITHOUT running code:
  define terms, include the tables and diagrams.
- Don't fabricate numbers: pull real ones from sqlite / dashboard screenshots.
