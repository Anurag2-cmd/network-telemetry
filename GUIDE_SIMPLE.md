# GUIDE_SIMPLE.md — explain this project in plain English

A talking guide for a demo or viva. Read top to bottom; every section is what you'd actually say.

---

## 1. The one-sentence version

> "We built a small fake network on one laptop where **six different monitoring systems all watch the same traffic**, write into **one shared database**, and show up on **one dashboard** — so you can directly compare how differently each one sees the same event."

---

## 2. Why this project exists (the problem)

Network operators need telemetry — data about what's happening inside the network. Two
things make this hard in real life:

1. **Different tools show different pictures.** A company uses SNMP, NetFlow, sFlow, and
   more, each from a different vendor, each with its own dashboard. Nobody ever sees them
   side by side on the *same* traffic.
2. **Old-style polling misses fast problems.** SNMP asks a device "how are you?" every few
   seconds. A network hiccup that lasts 40 milliseconds can start and finish *between two
   questions* — so it never appears in the data.

We built one testbed that makes both problems visible and measurable.

---

## 3. The four "generations" of telemetry (memorize this list)

| Gen | Protocol(s) | Idea in one line | Weakness |
|---|---|---|---|
| 1 — Polling | **SNMP** | Manager asks every 5 s: "packet count?" | Blind between polls; counters only give averages |
| 2 — Flow/sample | **NetFlow v5, sFlow, IPFIX** | Device summarises traffic into flows, or samples packets | Great for "who talked to whom", blind to queue delays inside the switch |
| 3 — Streaming | **gNMI** | Device *pushes* updates continuously over gRPC | Depends on what the vendor chooses to export |
| 4 — In-band | **INT** (our P4 program) | Every packet carries its own measurements (switch id, timestamp, queue depth) as it travels | Adds bytes to every packet; needs a programmable switch |

Ours covers **all four generations — six protocols total — on one network, one traffic, one database.**

---

## 4. What we actually built (the how)

- **The fake network:** Mininet simulates 4 computers (h1–h4) and 2 P4 switches (s1, s2)
  on one laptop, inside WSL (Windows Subsystem for Linux).
- **The INT part (our own work):** we wrote a P4 program (`p4/int.p4`). Each switch appends
  a 12-byte "sticky note" to every packet: *which switch, what time, how full its queue was*.
  A receiver on h2 reads all the sticky notes.
- **The six collectors:** six small Python programs, each listening for one protocol and
  inserting rows into one SQLite file (`db/telemetry.db`).
- **The dashboard:** a Flask web app with six tabs, one per protocol, refreshing every
  5 seconds with a green/red "live" badge.
- **One command** (`run_all.sh`) starts everything in order and checks that all six tables
  received data.

```
        one emulated network ──► six telemetry protocols ──► ONE SQLite database ──► ONE dashboard
```

---

## 5. The experiment and the headline result

**What we did:** h1 blasts 1,000 packets back-to-back at switch s2 (a "microburst") while a
slow link forces packets to queue up. All six protocols observe this same event.

**What we found:**

- The burst lasted **41.5 ms**, queue peaked at **59 packets**, peak delay **36.8 ms**.
- SNMP polls every 5 s → chance of catching the burst mid-flight: **41.5 ms / 5000 ms ≈ 0.8%**.
  In practice SNMP's nearest polls were *tens of seconds* apart and saw none of it.
- **INT saw all 80 samples of it** — because each packet reported its own experience.
- The flow-based protocols (NetFlow/sFlow/IPFIX) saw the traffic *happened* but not the
  queue build-up inside the switch.
- Counts differ on purpose: sFlow samples (hundreds of thousands of rows), NetFlow summarises
  (6 flow records), SNMP polls (10 rows) — same traffic, six different lenses.

**The punchline:** *the six protocols don't disagree — they each answer a different
question. This testbed is the only place you see all their answers on the same event.*

---

## 6. Demo script (3 minutes, in this order)

Run first (from the project folder in WSL): `sudo bash run_all.sh` (~7 min), or if it's
already running just open the dashboard.

1. **Show the network idea** → Fig. 1 in the paper (or `paper/figs/figure1*.png`): one
   network, six collectors, one database.
2. **Open http://localhost:5000** → click through all six tabs, point at the green
   "live · N rows/24h" badges.
3. **INT tab → queue-occupancy chart**: "this is the burst — 0 to 59 packets, 41.5 ms."
4. **Say the numbers**: 36.8 ms peak delay vs SNMP's 0.8% chance of ever seeing it.
5. **Close on the comparison**: six tabs, six answers, one truth.

---

## 7. Likely questions, short answers

- **"Why not just use one protocol?"** — each generation answers a different question
  (existence vs. volume vs. trend vs. per-packet experience). Operators run several; nobody
  compares them on the same traffic — that's our point.
- **"Is INT perfect?"** — no: it adds ~12 bytes/hop to packets and needs programmable
  (P4) switches. We say this openly in the paper's limitations section.
- **"Why emulated, not real hardware?"** — reproducibility on one laptop, one command,
  same numbers every run.
- **"Why do row counts differ so much (6 vs 385,000)?"** — sampling rates and export
  intervals are deliberate; it's the protocols' design, not a bug (paper §4.1/Table 2).
- **"What's original here?"** — the side-by-side six-protocol comparison on one traffic
  event, the P4 INT data plane, and the single-database design that makes comparison fair.
- **"What are the clocks like?"** — BMv2 switches have unsynchronised clocks; the receiver
  calibrates per-switch boot offsets, so latencies are relative but consistent per switch.

---

## 8. Words you may need (mini-glossary)

- **Telemetry** — measurements a network produces about itself.
- **Polling** — asking a device for stats on a timer (SNMP).
- **Flow record** — a summary of one conversation: who, how many bytes, when (NetFlow/IPFIX).
- **Sampling** — looking at only some packets and extrapolating (sFlow).
- **Microburst** — a very short flood of packets that overflows a queue for a few
  milliseconds; invisible to slow monitoring.
- **INT** — In-band Network Telemetry: packets carry their own measurements.
- **P4 / BMv2 / Mininet** — language for writing switch logic / software switch / fake-network tool.
- **gNMI** — gRPC-based protocol for streaming config & state data.

---

## 9. Where everything lives

| I want to… | Open |
|---|---|
| The story & architecture (README-level) | `README.md` |
| Step-by-step run instructions | `QUICKSTART.md`, `RUN_COMMANDS.md` |
| The full technical reference | `DOCUMENTATION.md` |
| The written report / paper | `report.md`, `paper/paper.html` (PDF/DOCX beside it) |
| What each file does / fresh-PC setup | `GUIDE_FILES.md` |
