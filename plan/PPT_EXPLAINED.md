# Network Telemetry — Presentation Explained (For Non-Networking Folks)

This document walks through all 8 slides of the "Network Telemetry" presentation in plain language. No networking background needed — just curiosity.

---

## Slide 1 — Title Slide

**What it says:** "Network Telemetry" — Second Year Project Synopsis, submitted by ROLL 2501560023, NAME ZIGGYZAG, Faculty Mentor: Mr. Amit Kumar Singh.

**What it means:** This is the cover slide. It tells you the project name (Network Telemetry), that it's a second-year university project, who's on the team (roll number 2501560023, team name ZIGGYZAG), and who's supervising (Mr. Amit Kumar Singh at K.R. Mangalam University).

---

## Slide 2 — Summary (The Big Picture)

**What it says:** "A Six-Protocol Emulated Monitoring Stack: SNMP, NetFlow v5, sFlow, IPFIX, gNMI, INT."

**What it means:** The project builds a small, pretend computer network (an *emulated* network — think of it as a network simulated inside a computer, built with tools called Mininet, P4/BMv2, and Open vSwitch). That pretend network speaks six different "languages" (protocols) that real networks use to report what's happening inside them. All six languages feed their information into one shared database (a SQLite file — think of it as a simple spreadsheet on disk) and one live web page (a Flask dashboard — a page that updates itself in real time).

**Why it matters:** The project proves, with actual measured numbers, that newer ways of watching a network (streaming and in-band telemetry) are better than the old way (SNMP polling).

**Three key takeaways:**
1. **6 protocols, 4 generations — one unified dashboard.** Six different technologies, spanning four eras of networking history, all visible on a single screen.
2. **Emulated network, real protocol implementations.** The network is simulated, but the monitoring tools are the real deal — not fake stand-ins.
3. **One command (`run_all.sh`) brings the whole stack to life.** A single script starts everything — network, collectors, database, dashboard.

---

## Slide 3 — Four Generations of Network Telemetry

**What it says:** Telemetry evolved from coarse device polling to per-packet, per-hop visibility.

**What it means:** "Telemetry" just means "measuring things from a distance." Network telemetry means measuring what's happening inside a network. Over ~30 years, this has gotten dramatically more detailed. Think of it like the difference between checking your car's dashboard once in a while (old way) vs. having GPS track every meter of your journey (new way).

**The four generations:**

- **Gen 1 — SNMP (1990s):** The granddaddy of network monitoring. A central server *asks* a device "how are you doing?" every 5 to 300 seconds, and the device replies with numbers (CPU usage, memory, etc.). This is called *pull-based* — the server pulls information by asking. The problem: if something weird happens between questions, nobody ever knows. It's like checking your car's dashboard only once an hour — you'd miss a sudden spike in temperature.

- **Gen 2 — Flow (1995–2008):** Instead of asking "how are you?", devices start *telling* the server about conversations happening on the network. NetFlow, sFlow, and IPFIX are three flavors of this. They export "flow records" — summaries of who talked to whom, how much data moved, and when. sFlow also samples actual packet headers (like taking photos of a few cars on a highway). This gives an *aggregate* view — you see the overall pattern, but not every single packet.

- **Gen 3 — Streaming (2016+):** gNMI (gRPC Network Management Interface) is a modern way for devices to push their current state to a collector automatically, using subscriptions. Instead of the server asking over and over, the device says "tell me what you want to know, and I'll send you updates whenever something changes." It's model-driven (organized like a structured form) and based on OpenConfig (an industry standard for how that form looks).

- **Gen 4 — INT (2016+):** In-band Network Telemetry is the most detailed. The network switches themselves stamp each packet *while it's flying through the network* with metadata: which switch it passed through, when it entered that switch, and how long it waited in line (queue depth). It's like every car on the highway getting a GPS tracker that records every toll booth it passes and how long it waited at each one.

---

## Slide 4 — Protocol Table (What Exactly Is Implemented)

**What it says:** "Which protocols do we implement?"

**What it means:** This slide is the detailed spec sheet. Here's what each protocol does in plain terms:

- **SNMP (RFC 1157):** The classic. A monitoring server polls an `snmpd` agent (a small program running on a network device) every 5 seconds and gets back CPU, memory, and interface counters. Pull-based — the server has to ask.

- **NetFlow v5 (Cisco):** A host (named h1 in the lab) runs a program called `softflowd` that watches traffic and exports flow records to UDP port 9995. UDP is a fast, connectionless way to send data — like dropping letters in a mailbox without waiting for a receipt.

- **sFlow v5 (RFC 3176):** Open vSwitch (a software switch) samples packets and also polls interface counters, sending everything to UDP port 6343. sFlow is the "take a statistical sample" approach.

- **IPFIX (RFC 7011):** A more modern, template-based version of NetFlow. Host h3 runs `softflowd` to export flow records to UDP port 9996. "Template-based" means the exporter first sends a form describing what the data will look like, then sends the actual data.

- **gNMI (OpenConfig):** Uses gRPC (a fast remote-procedure-call system) to fetch P4Runtime port counters, refreshed every 2 seconds. This is the streaming generation — no polling, just regular updates.

- **INT (P4 data plane):** The P4 switches (programmable switches) stamp each packet with per-hop metadata: switch ID, ingress timestamp, and queue depth. Every packet carries its own travel diary.

- **Shared database:** All six collectors write into one SQLite file (`db/telemetry.db`) in WAL mode (a way of writing that lets readers and writers work at the same time without stepping on each other). One database, six sources — that's the "unified" part.

---

## Slide 5 — How It Works (Architecture)

**What it says:** "How does the project work?"

**What it means:** This slide shows a diagram of the whole system. In plain terms, here's what's happening:

1. **Virtual switches** (software switches running inside the lab) forward packets.
2. **Hardware switches** (or their emulated equivalents) also participate — in this lab, everything is emulated, but the architecture mirrors what a real network would look like.
3. The **telemetry stack** is the collection of collector programs that listen to each protocol and write what they see into the database.
4. The **controller** is the brain that configures the switches and tells them what to do (e.g., "start stamping INT metadata on packets").
5. The **analytics engine** reads the database and turns raw numbers into useful insights — like detecting microbursts and measuring queueing delays.

The data flows: switches generate telemetry → collectors gather it → database stores it → dashboard displays it.

---

## Slide 6 — What It Delivers (The Results)

**What it says:** "What does the project deliver?"

**What it means:** This slide is the proof that the project actually works. Three categories of deliverables:

**1. Dashboard (real-time):**
- Six tabs — one per protocol, so you can flip between SNMP, NetFlow, sFlow, IPFIX, gNMI, and INT views.
- `/api/status` liveness badges — little indicators that show each collector is alive and reporting (using a 60-second window: if a collector hasn't reported in 60 seconds, its badge turns red).
- Chart.js graphs that auto-refresh every 5 seconds — the charts update themselves without you clicking anything.
- Served at `http://localhost:5000` — open that address in a browser on the same machine and you see the dashboard.
- The API returns the last 200 rows per source — so the dashboard always shows recent history, not just the latest snapshot.

**2. Measured evidence (the cool part):**
- **Microburst detected:** A microburst is a sudden, short-lived flood of packets. The system caught one where the queue built up to 43–45 packets deep in under 1 second. That's like a traffic jam that appears and vanishes in the blink of an eye.
- **~22 ms per-hop queueing delay:** Each switch added about 22 milliseconds of delay while the burst was happening. INT recorded this precisely.
- **SNMP's 5-second poll missed the event entirely:** The old-generation tool was blind to the microburst because it only checks every 5 seconds — the burst came and went between checks.
- **INT recorded the burst packet by packet:** The new-generation tool saw everything, every single packet.
- **E2E run: all six tables non-empty — PASS:** An end-to-end test confirmed that all six protocols successfully wrote data into the database.

**3. Engineering (how it's built):**
- `run_all.sh` — one command that starts the entire demo from scratch.
- `--selftest` mode for every collector — each collector can test itself to make sure it's working.
- Shared SQLite with WAL mode and 24-hour row cleanup — the database doesn't grow forever; old data is removed after a day.
- Self-contained: the whole stack runs on one laptop — no special hardware needed.

---

## Slide 7 — Progress (About 65% Complete)

**What it says:** "Progress so far — about 65% complete."

**What it means:** The project is organized in three phases. Two are done, one is in progress:

- **Phase 1 — Data plane and collectors (done):** The containerlab topology (a way of wiring together virtual network devices) is live. SNMP, NetFlow v5, sFlow, and IPFIX agents run on every switch. INT telemetry (with 3 header options — three different ways of stamping packets) and gNMI streaming are wired end to end.

- **Phase 2 — Dashboard and pipeline (done):** The telemetry server ingests all six streams into SQLite. The dashboard shows live packets, microbursts (43-deep queue, ~22 ms/hop), per-protocol tables, and a REST API — all in one `./run_all.sh` run.

- **Phase 3 — Testing, docs and labs (in progress):** The team is rerunning the end-to-end pipeline, cross-checking counters (making sure different protocols agree with each other), and writing DOCUMENTATION.md, the synopsis, and this presentation.

---

## Slide 8 — Limitations (Being Honest About What It Can't Do)

**What it says:** "Limitations."

**What it means:** Every project has boundaries, and this slide is upfront about them:

- **Emulation scale only:** The containerlab lab is small — small flows, 600 packets per second for INT. A real production network would be much bigger. This is a proof of concept, not a production system.

- **Per-switch clocks:** The switches don't share a synchronized clock, so cross-device latency measurements use *relative* INT deltas (comparing timestamps within the same switch's data) rather than absolute end-to-end timing.

- **Emulated gNMI:** gNMI runs on P4Runtime in the lab rather than on a vendor's real agent. That means the project doesn't cover real YANG models (the structured data definitions that real devices use).

- **Delayed flow export:** `softflowd` on WSL2 (Windows Subsystem for Linux) feeds data through a `tcpdump` FIFO (a named pipe — a way to pass data between programs). This adds latency, so NetFlow, sFlow, and IPFIX records appear 10–60 seconds late.

- **Sampling is statistical:** sFlow and NetFlow can't see every packet — they sample. That's exactly the gap that INT fills: INT sees everything, while the flow-based tools see a statistical picture.

---

## TL;DR — The Whole Presentation in One Paragraph

The Network Telemetry project builds a small simulated network that speaks six different monitoring languages, from the 1990s-era SNMP (which asks "how are you?" every few seconds) all the way to cutting-edge INT (which stamps every packet with its travel history). All six feed into one database and one live dashboard. The project proves with real numbers that the new tools catch things the old tools miss — like a microburst that SNMP's polling completely overlooks but INT records packet by packet. It's about 65% done, runs on a single laptop with one command, and is honest about its limits: it's an emulation, not a production network.
