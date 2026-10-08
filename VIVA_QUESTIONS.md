# VIVA / INTERVIEW QUESTIONS — Network Telemetry Testbed

This is a complete Q&A for the project. Covers basics, design, topologies, monitoring, results, and likely cross-questions.

---

## A. Basic Concepts (Fundamentals)

**Q1. What is network telemetry?**
*A:* Network telemetry is the automated collection, transmission, and analysis of real-time data from network devices to monitor health, performance, and behaviour. Unlike logs or manual checks, telemetry focuses on continuous, high-granularity visibility (counters, flows, samples, or per-packet info).

**Q2. Why do we need to compare these six protocols together?**
*A:* Different protocols answer different questions. SNMP polls, flows summarise, sFlow samples, gNMI streams counters, INT adds per-packet hop info. In reality they co-exist, but each has blind spots. By running all six on the **same network, same traffic, same event**, we can see those blind spots side by side.

**Q3. What are the six protocols used and which "generation" do they fall under?**
*A:* Polling (Gen1) → **SNMP**. Flow/Sample (Gen2) → **NetFlow v5, sFlow, IPFIX**. Streaming (Gen3) → **gNMI**. In-band (Gen4) → **INT** (P4). Together they cover all four generations.

**Q4. What is the difference between SNMP, NetFlow, sFlow, IPFIX, gNMI and INT in one line each?**
- **SNMP:** Pull-based — manager polls device counters at fixed intervals.
- **NetFlow v5:** Aggregates packets into 5-tuple flows and exports on timeout/flow-end.
- **sFlow:** Samples 1-in-N packets and exports sample headers/metadata (statistical estimation).
- **IPFIX:** NetFlow v9's IETF standard — template-based flow export (more flexible fields).
- **gNMI:** Push-based streaming of YANG-modeled state (e.g. OpenConfig interface counters) over gRPC.
- **INT:** In-band — every packet carries its own per-hop measurements (switch_id, ingress/egress timestamps, queue depth) as it travels.

**Q5. Why is INT called "in-band" telemetry?**
*A:* Because the measurement data travels **inside the data packet itself** (appended headers/metadata) along the same path. Traditional telemetry is "out-of-band" (separate UDP flows to collectors). INT makes each packet self-describing about its own experience.

---

## B. Project Objective & Design

**Q6. What is the main objective of this project?**
*A:* To build a unified testbed that runs SNMP, NetFlow v5, sFlow, IPFIX, gNMI and INT on the same emulated network and traffic, stores all results in one SQLite DB, and visualises them on one dashboard — to compare their visibility of the same microburst event.

**Q7. Why use Mininet + BMv2 (P4) instead of real switches?**
*A:* 
- **Reproducibility:** Same traffic, same timing, tear-down/rebuild between stages — consistent numbers.
- **Programmability:** BMv2 lets us write our own P4 INT program (most real ASICs aren't freely programmable like this).
- **Cost & control:** No vendor lock-in, can create exact topologies, inject a controlled microburst, and inspect everything.
- **Practicality:** Comparing all 6 on real hardware would require wiring + multiple vendor configs. Emulation is cleaner for a comparative study.

**Q8. Why one shared SQLite DB and one dashboard?**
*A:* "Apples-to-apples". Every protocol writes to the same schema layout (timestamped rows). On the dashboard (6 tabs) you can switch between protocols and see the **same wall-clock window** around the burst — impossible if each protocol had its own vendor dashboard.

**Q9. What does `run_all.sh` do?**
*A:* Orchestrates the full E2E: checks WSL/requirements, backs up old DB, tears down Mininet, runs stages in order (INT → sFlow/NetFlow/IPFIX → SNMP → gNMI), starts collectors/dashboard, generates traffic (steady + burst), verifies all 6 tables are non-empty, and keeps dashboard up so you can inspect.

**Q10. Why do we tear down and rebuild topology between stages?**
*A:* Isolation. Each stage uses different daemons (softflowd exporters, snmpd, BMv2 switches, gNMI server). Mixing them on the same live network risks port conflicts, leftover processes, or polluting DB tables. Starting fresh gives clean, reproducible results per protocol.

---

## C. Topology, Controller, Traffic

**Q11. Are we using the same topology for all 6 protocols?**
*A:* **No.** We use three different topologies, rebuilt per stage:

- **INT:** `h1 — s1 — s2 — h2` (+ `h3` off `s2`) — needs 2 P4 switches in a row to show per-hop INT.
- **sFlow/NetFlow/IPFIX/SNMP:** 4-host **star** `h1-h4 — s1` (OVS, standalone). `h4` acts as collector (receives flows/sFlow/SNMP).
- **gNMI:** 2 network namespaces (`ns-a`, `ns-b`) + 1 BMv2 switch (minimal setup to stream OpenConfig counters).

**Q12. Why not keep a single fixed topology?**
*A:* In emulation, rebuilding is trivial and keeps each test minimal/clean. On **real hardware**, you'd do the opposite: keep **one fixed physical topology** and just change switch configs/daemons per stage (no rewiring). Both are logically the same experiment.

**Q13. Do we use an SDN controller? Why or why not?**
*A:* **No — `controller=None` in all Mininet topologies.** Reasons:
- Forwarding is static/pre-installed. For P4, rules are pushed via `simple_switch_CLI`. For OVS, standalone mode self-learns like a normal switch.
- No routing decisions needed (fixed paths: INT is h1→s1→s2→h2).
- Adding a controller (Ryu/ONOS) would add timing jitter, extra packet-in/control traffic, and nondeterminism — bad for reproducible comparison.
- Goal is **observability (telemetry)**, not **control**.

**Q14. What is the traffic we generate and why a microburst?**
*A:* Steady iperf from h1→h2, then a **back-to-back microburst** (short, high-rate) from h1→h2. We chose a microburst because:
- It's short (tens of ms) — long enough to create queue buildup but short enough that **poll-based** methods (SNMP) are very likely to miss it between polls.
- Creates measurable per-hop latency + queue depth (perfect for INT ground truth).
- Shows the contrast: packet-level (INT) vs sampled (sFlow) vs flow-aggregated (NetFlow/IPFIX) vs polled/counter-based (SNMP/gNMI).

**Q15. Why h1→s1→s2→h2 for INT specifically?**
*A:* To get **two hops**. Each P4 switch appends its own INT metadata. With 2 switches we see switch_id=1 and switch_id=2 both reporting `hop_latency_us`, `jitter_us`, `queue_occupancy`. With 1 switch you'd only see 1 hop — can't demonstrate "per-hop" visibility.

---

## D. What to Monitor on the Dashboard & Why

**Q16. What should we look at first on the dashboard to see the burst?**
*A:* Go to **INT tab** first. Look at:
- **Per-hop latency by switch**: sharp spike, larger at **switch_id=2 (s2)**.
- **Queue occupancy by switch**: jump up at s2 (queue fills at downstream switch).
- **Latency vs queue (switch_id=2, dual-Y)**: **latency and queue rise and fall together** — this is causal proof of congestion.

**Q17. What exactly does INT reveal that others don't?**
*A:* **Per-packet, per-hop ground truth.** For each INT-carrying packet: which switch, ingress/egress timestamps, hop latency, jitter, queue depth. You can literally see queue building up packet-by-packet during the microburst. Flow/sampled/counter methods aggregate or sample away that fine detail.

**Q18. What graph to watch on sFlow and what does it tell?**
*A:* **Bandwidth in/out (Mb/s)** — shows a short **pulse** (ramp up → peak → down). Also "Top source IPs by bytes" should show h1→h2 dominates, "Sampled traffic by proto" confirms TCP/iperf. sFlow sees *there was a burst and how big* but **not** per-hop queue/latency.

**Q19. Why do NetFlow/IPFIX show so few rows compared to sFlow?**
*A:* Aggregation. NetFlow/IPFIX group packets into **flows** (same 5-tuple) and export one record per flow (on timeout/flow end). One record can represent thousands of packets. sFlow exports **samples** — every sampled packet/event can produce rows. So 355k sFlow ≈ sampled view; ~6–11 NetFlow/IPFIX ≈ summarised accounting view. Same traffic, different granularity.

**Q20. What should we look for in SNMP graphs?**
*A:* 
- **Interface octets (cumulative):** slope steepens during burst window (more octets/sec).
- **Bandwidth in/out (Mb/s):** computed delta — often **rounded/smeared** across polling interval (coarser than sFlow). May miss the sharp peak entirely.
- **CPU/Memory/Uptime:** sanity checks (agent alive, consistent).

Key: SNMP's granularity = polling period. A 40–50ms burst can fall between polls → **low catch probability** (matches ~0.8% intuition).

**Q21. What should we look for in gNMI graphs?**
*A:* **Per-interface in-octets/out-octets** (cumulative). Look for **slope change on the correct interface** at burst time. gNMI is push/streamed (often nearer real-time than classic SNMP pull), structured via OpenConfig YANG. Still counter-based — no queue depth or per-hop latency like INT.

**Q22. How to "read" the dual-Y latency vs queue chart (INT)?**
*A:* X-axis = time relative to first INT packet (seconds). Left Y = `hop_latency_us` (blue), right Y = `queue_occupancy` (orange), filtered to **switch_id=2**. **When orange rises, blue rises. When orange drops, blue drops.** They track almost together. That means **queue buildup caused the extra hop latency** — direct causal link. This is the strongest visual proof for the paper.

**Q23. What are the "live" badge numbers telling us?**
*A:* `live · N rows/60s · HH:MM:SS` means that table received N new rows in the last 60 seconds and last row was at that timestamp. If badge goes **dead/offline** → collector stopped writing or DB stale. During the run, INT/sFlow will usually show higher rows/60s than NetFlow/IPFIX/SNMP (matching granularity).

**Q24. What are we looking for overall across all 6 tabs?**
*A:* **Correlation of the same event.**
- **INT:** shows *mechanism* (queue→latency, per-hop)
- **sFlow:** shows *magnitude/duration* (bandwidth pulse)
- **NetFlow/IPFIX:** show *existence + totals* (dominant h1→h2 flow)
- **SNMP/gNMI:** show *counter-based visibility* (did interface counters register the surge? how sharply?)

You're proving: **same microburst → 6 different lenses. INT sees deepest detail; polled/flow-aggregated see coarser or miss timing.**

---

## E. Results, Numbers, Viva Traps

**Q25. What were the headline numbers from your run?**
*A:* Burst duration **~41.5 ms**, queue peak **59 packets**, peak per-hop delay **~36.8 ms** at s2. sFlow produced **~355k** rows, NetFlow **~6**, IPFIX **~11**, SNMP **~10**, gNMI **~180**, INT **~350** hop rows (numbers vary slightly by run). Also "0.8% chance" for SNMP to catch a 41.5ms burst in a 5s poll window.

**Q26. Why "0.8% chance" for SNMP?**
*A:* Window of interest = burst length = 41.5 ms. Polling interval = 5000 ms. Simplest uniform view: probability a random poll falls inside (or overlaps meaningfully) that tiny window is ~41.5/5000 = 0.0083 = **0.83%**. In reality polling is periodic (not random aligned) — often misses entirely. That's the key point: **polling is fundamentally blind to sub-second transients.**

**Q27. Does sFlow "miss" anything vs INT?**
*A:* sFlow sees the **traffic pattern** (bandwidth pulse, top talkers, proto) but **doesn't see internal switch state**. It has no `enq_qdepth`, no per-hop latency/jitter. INT sees the *cause* inside the switch. sFlow estimates from samples — statistically correct for volume/timing of traffic, but not "what the queue did".

**Q28. Why are INT rows ≈ 2× packets (roughly)?**
*A:* Because traffic goes **h1→s1→s2→h2** = **2 hops**. Each packet that carries INT gets metadata appended at **s1** and again at **s2**. So the collector sees ~2 hop records per INT packet. That’s exactly what "per-hop" means.

**Q29. If we used a single switch for INT, what would change?**
*A:* Only **1 hop** (switch_id=1). You'd see hop latency/queue at s1 only — can't show that congestion builds differently across hops or that s2 is the bottleneck. The 2-hop chain makes the comparison clearer and matches "per-hop telemetry" better.

**Q30. Can we run all 6 on ONE real fixed topology without tearing down?**
*A:* **Yes — in principle.** Keep one wired topology (e.g. chain). Sequentially: run Stage 1 (INT) with its daemons, collect, stop INT daemons/reconfig, run Stage 2 (flow exporters + SNMP + gNMI config) on same switches/ports, collect, etc. 
**Constraints:**
- Switches must support everything needed on same hardware (P4-capable + sFlow/NetFlow/IPFIX + SNMP agent + gNMI server). Rare unless using software switches everywhere.
- Exporters/agents can coexist? Sometimes yes, sometimes you don't want them fighting. Easier to run sequentially (clean).
- On real ASICs, enabling multiple exporters has minimal overhead but we still want **controlled, sequential** runs for a fair comparison.

**Q31. What's the biggest practical advantage of this unified testbed?**
*A:* **Side-by-side comparison on identical conditions.** Before this, you'd read: "SNMP misses short bursts", "INT is fine-grained". Here you **see** it live: same microburst appears as a sharp dual-Y hill (INT), a clean pulse (sFlow), a couple of flow rows (NetFlow/IPFIX), and a possibly smoothed/absent blip (SNMP). That visual proof is powerful.

**Q32. Any weaknesses/limitations worth mentioning?**
*A:* 
- **Emulation vs reality:** BMv2 is software-based (slower, different timing vs real ASICs). Absolute numbers differ, but **relative comparison** (who sees what, granularity) holds.
- **Simplified topologies:** Lab setup, not a full ISP/datacenter mesh.
- **Single event type:** Only microburst tested (proves the point). Could test link flaps, congestion, routing changes too.
- **gNMI scope:** Limited to OpenConfig interface counters here (YANG paths chosen). Real gNMI can stream much more.

**Q33. If someone asks "which one is best?", what's the right answer?**
*A:* **It depends on the question you're asking.**
- **Need to debug per-packet queuing/congestion?** → **INT** (deepest, per-hop).
- **Need traffic volume, top talkers, network-wide usage?** → **sFlow/NetFlow/IPFIX** (scalable, lower overhead).
- **Need device health/utilization over minutes/hours?** → **SNMP** (universal, simple).
- **Need structured, programmatic streaming of device state?** → **gNMI** (modern, YANG-driven, automation-friendly).

**The testbed shows they complement, not replace each other.**

**Q34. Quick viva one-liner to end with?**
*A:* *"We built a single testbed to run six telemetry protocols on identical traffic — storing everything in one DB and showing on one dashboard. INT revealed the queue-driven latency per packet, sFlow captured the burst shape, flow protocols gave summaries, while SNMP/gNMI showed their counter granularity. The key finding: they don't conflict — each answers a different operational question."*

---

## F. Technical Quick Checks (traps to dodge)

**Q35. Is sFlow push or pull?**
*A:* **Push** (device/exporter sends samples to collector when sampled). NetFlow/IPFIX also push flows. **SNMP is pull** (manager polls). **gNMI** is typically **push** via subscriptions (streaming), though get/set exist. **INT** is in-band carried by data packets.

**Q36. What fields make NetFlow v5 "v5"?**
*A:* Fixed 5-tuple key: **src_ip, dst_ip, src_port, dst_port, proto** (plus interface, ToS, nexthop). v9/IPFIX are template-based (extensible). sFlow is packet-sample based.

**Q37. Why does SNMP sometimes show 0 rows around burst?**
*A:* Polling missed the interval. If collector polls every 5s and burst is at 12:00:00.041 (41ms long), nearest polls might be 11:59:55 and 12:00:00 — depending on alignment, the delta may not reflect the sharp spike, or the DB just has polls around it with small delta. Also "rows/60s" for SNMP stays low by design.

**Q38. Why is the dashboard X-axis "relative time" for INT?**
*A:* To align hop records from s1 and s2 to the **same burst start** (`ingress_ts - x0`). Makes the latency/queue curves line up clearly (easier to see s2 peak). sFlow/NetFlow use absolute wall-clock time (binned). INT needs per-packet alignment.

**Q39. What's the role of h4 in star topology?**
*A:* **Collector host.** Runs softflowd receivers? Actually in that stage: h4 receives **NetFlow v5 on :9995**, **IPFIX on :9996**, **sFlow on :6343**; runs **snmpd** (polled by root); iperf traffic is h1→h2 and h3→h2 (background). h4 is the sink/manager side.

**Q40. Why gNMI uses namespaces instead of full Mininet?**
*A:* Minimal, focused setup: create veth pair between ns-a/ns-b and BMv2 switch, run BMv2 with a simple config, start gNMI server (e.g. via `gNMI` tooling or switch binary), subscribe to OpenConfig paths. Avoids full Mininet overhead for just "stream counters from one switch" test. Same logical idea (2 endpoints + 1 switch).