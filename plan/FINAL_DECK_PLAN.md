# Final Deck Plan — Network Telemetry

Hand-off brief for whoever builds the slides. Everything needed is here: exact
copy, layout wireframes, asset paths, speaker notes, and the number sheet the
copy must not drift from.

- **Purpose:** final project presentation / viva defence
- **Audience:** faculty panel + supervisor. Assume they know networking basics
  but have not read the paper.
- **Slot:** ~10 minutes + Q&A → **10 main slides + 2 backup slides**
- **Aspect:** 16:9 (13.333 × 7.5 in)
- **Deliverable:** `.pptx` with speaker notes in the notes pane
- **Source of truth for every number:** `paper/LATEST/Telemetry_Testbed_IEEE_Conference_Paper Latest.docx`
  (Tables I–III, Fig. 4). If a number is not in the sheet in §7, it does not go on a slide.

> This deck replaces `Network_Telemetry_PPT_v2.pptx`. Do not reuse that file's
> template, its 30-pt bullet layouts, or its synopsis wording — v2 describes the
> project as "in progress"; this deck reports a finished, measured result.

---

## 1. The argument the deck has to land

One sentence, and every slide is either setup or evidence for it:

> **A single emulated network produced all four generations of telemetry at once,
> and one 41.5 ms microburst proved — with numbers, not adjectives — that polling
> cannot see what in-band telemetry records packet by packet.**

Structure is therefore: problem → what exists → how we built it → what we
measured → what it does not prove → what it means.

Three numbers carry the talk. They appear on the title slide and are re-paid on
slide 6: **41.5 ms**, **59 packets**, **0.8 %**.

---

## 2. Design system

Do not use a stock Office theme. The look is **technical editorial**: warm paper,
heavy ink, one signal colour, monospace for anything numeric.

### Canvas and grid

| Item | Value |
|---|---|
| Slide | 13.333 × 7.5 in |
| Outer margin | 0.62 in left/right, 0.42 in top |
| Content width | 12.09 in |
| Baseline rhythm | 0.2 in steps; nothing lands on half-inches |
| Safe zone | all text inside 0.62 in margins; figures may bleed to 0.45 in |

### Palette

| Role | Hex | Use |
|---|---|---|
| Paper (background) | `#FBFAF7` | every slide background |
| Ink | `#141412` | headlines, rules, dark bands |
| Muted | `#6B6961` | body text, captions, labels |
| Rule | `#D9D6CC` | hairline separators |
| **Accent** | `#C02E1A` | one idea per slide only: the claim number, the INT row, the burst |
| Blue | `#1F4EA8` | optional; only to echo the latency line in `fig3.png` |
| Panel | `#F1EEE5` | tinted callout boxes, table highlight |

Rules: the accent is not decoration. Maximum one accent element per slide. Never
accent two competing ideas.

### Type

| Level | Font | Size | Weight |
|---|---|---|---|
| Slide headline | Segoe UI | 30–36 pt | Bold, ink, line spacing 1.04 |
| Deck subtitle / sub-head | Segoe UI | 14.5 pt | Regular, muted, 1.15 |
| Body | Segoe UI | 12–13.5 pt | Regular, muted |
| Lead-in body | Segoe UI | 15 pt | Bold, ink |
| Data / labels / captions | Consolas | 9–11 pt | Regular, uppercase, +1.2 pt letter-spacing |
| Hero numbers | Consolas | 26–60 pt | Regular |

Segoe UI and Consolas ship with Windows; the panel machine is Windows 11, so no
font embedding is needed. Do not substitute a display font.

### Recurring furniture (identical on every slide)

- Top-left, mono 10 pt, muted: section label, e.g. `05 · RESULT 1 — THE MICROBURST`
- Top-right, mono 9 pt, muted: `NETWORK TELEMETRY`
- Bottom: hairline rule at y = 7.02 in, then left `Final presentation · K.R. Mangalam University · Nov 2026`, right `06 / 10`
- Everything left-aligned to the 0.62 in margin. No centred body copy anywhere.

### Headline rule (most important instruction)

**Every headline is a claim, not a label.**

| Don't | Do |
|---|---|
| "Architecture" | "Six producers, one database, one dashboard" |
| "Results" | "A 41.5 ms burst, recorded packet by packet" |
| "Limitations" | "What this testbed does not prove" |
| "Conclusion" | "Telemetry is not one question." |

### Imagery

Five figures from `paper/figs/` — do not redraw them, do not recolour them:

| File | Size | Use on | Treatment |
|---|---|---|---|
| `figure1_testbed_architecture.png` | 3420×2430 | slide 4 | 7.35 in wide, left; thin `#D9D6CC` 0.75 pt border |
| `int_diagram.png` | 2055×1179 | slide 5 | near full-width (10.85 in), no border, sits on paper |
| `fig2.png` | 980×440 | slide 6 (left) | 5.92 in wide, border |
| `fig3.png` | 980×440 | slide 6 (right) | 5.92 in wide, border |
| `dashboard.png` | 1100×731 | slide 7 (right) | 4.4 in wide, border |

Ignore `*_old.png` and the two HTML files. Figures are light-background charts;
that is why the deck background is paper-white, not dark.

---

## 3. Slide-by-slide

### Slide 1 — Title

```
┌──────────────────────────────────────────────────────────────┐
│ K.R. MANGALAM UNIVERSITY · MCA (AI & DS) ·   NOVEMBER 2026   │  mono 9.5
├──────────────────────────────────────────────────────────────┤  ink rule 1.5pt
│                                                              │
│  A SIX-PROTOCOL TESTBED                    accent, mono, spaced
│  Network Telemetry                                           │  66pt bold ink
│  Six protocols, four generations, one dashboard — and one    │  21pt muted
│  41.5 ms microburst that proves the difference.              │
│  ──────────────────────────────────────────────────────────  │
│  Anurag Ramola · 2501560023 · Projexa Team 2604057   41.5  59   0.8 % │
│  Supervisor: Dr. Feroz Ahmed                          ms   pkts  %  │
│  School of Engineering and Technology                        │  hero stats
└──────────────────────────────────────────────────────────────┘
```

- Hero stats bottom-right, three of them, `Consolas 30 pt`, thin rule above each:
  `41.5` `ms — microburst duration` / `59` `packets queued at s2` /
  `0.8` (accent) `% chance a 5-s poll sees it`
- Bottom-left mono 10 pt: *Every number in this deck was produced by this testbed and is reproducible with one command.*

**Notes (1 min):** Open with the one-sentence claim — one small network, all six
protocols, so a comparison everyone quotes can actually be measured. Point at the
three numbers: they are the whole talk. Housekeeping: 10 minutes, deck then
questions, live demo available if the lab cooperates.

⚠ **Checks before export:** supervisor name (v2 deck said Mr. Amit Kumar Singh,
latest paper says Dr. Feroz Ahmed) and the team/brand label (paper says
"ZiggyZag Team", v2 says "Projexa Team ID 2604057"). Use whichever the submission
form requires, consistently.

---

### Slide 2 — The problem

**Headline:** `The network knows what broke.` / `The monitoring stack asks too late.`

Left column, three numbered items (mono accent numerals `01 02 03`, bold lead-in,
two lines of body):

1. **Polling samples time — it does not record it**
   SNMP asks a device how it is every 5 s. An event shorter than the poll interval
   is a lottery ticket, and the answer is whatever the counter holds when the
   question arrives.
2. **Flows summarise — they do not observe**
   NetFlow and IPFIX collapse thousands of packets into one record on timeout;
   sFlow exports a sample. Both answer who talked and how much — neither answers
   what the queue did.
3. **Counters are cumulative**
   SNMP and gNMI octet counters rise and fall smoothly. A 40 ms queue spike
   leaves almost no fingerprint once it is averaged over a poll window.

Italic ink 13 pt below the list: *Four generations of telemetry exist to close that
gap. Almost nobody runs all four side by side on identical traffic — which is what
this project does.*

Right: panel `#F1EEE5` (4.16 × 3.05 in) containing
- label `THE BLIND SPOT, QUANTIFIED`
- `0.8 %` at 60 pt accent
- *probability that a 5-second SNMP poll lands inside a 41.5 ms microburst*
- hairline, then mono: `41.5 ms / 5000 ms  =  0.0083`

**Notes (1.5 min):** Three mechanisms fail three different ways. Then the number:
41.5 ms inside 5 s is 0.8 %. Say plainly that this is arithmetic on the poll
period, not a measured miss rate — the honest version of the claim.

---

### Slide 3 — Four generations

**Headline:** `Four generations — all six protocols implemented here`
**Sub-head:** *Every generation is a real implementation in the testbed, not a token mention on a slide.*

Four equal cards (2.86 in wide, 0.24 in gutters). Each card: 0.11 in colour bar on
top, `GEN n` in mono, bold name, monospace protocol names, mechanism in two lines,
hairline, `IN THIS TESTBED` label, implementation line.

| | Gen 1 | Gen 2 | Gen 3 | Gen 4 |
|---|---|---|---|---|
| Bar colour | `#C5C1B5` | `#9C978B` | `#556274` | **`#C02E1A`** |
| Name | Polling | Flow & sample export | Streaming, model-driven | In-band telemetry |
| Protocol | SNMP | NetFlow v5 · sFlow · IPFIX | gNMI | INT |
| Mechanism | A manager polls MIB counters over UDP on a fixed interval. Coarse, universal, still everywhere. | The device decides what to export: complete flows on timeout, or sampled packet headers plus counters. | Schema-negotiated OpenConfig state over gRPC. Subscriptions replace polling. | Every switch stamps the packet it is already forwarding with its own state. No extra monitoring traffic at all. |
| In this testbed | `snmpd` on h4 · 5-s pysnmp poll | `softflowd` h1/h3 · OVS s1, sampling=1 | `pygnmi` agent over P4Runtime · 2-s Get | P4-16 on BMv2 · 12-byte entry per hop |

Italic muted footer: *Same physical network, same traffic, same wall-clock window —
the only thing that changes is the observation mechanism.*

**Notes (1 min):** Do not read the cards. History moved from asking a device, to
the device exporting summaries, to streaming modelled state, to the packet carrying
its own telemetry. The kicker: all four generations run in one lab, which is why
the comparison is fair.

---

### Slide 4 — Architecture

**Headline:** `Six producers, one database, one dashboard`

- Left: `figure1_testbed_architecture.png`, 7.35 in wide at x = 0.45, y = 1.72.
- Right column x = 8.05, width 4.55: label `DATA FLOW`, ink rule, then four steps
  (mono accent numerals, 14 pt bold title, 11.5 pt body):

| | Step | Body |
|---|---|---|
| 01 | Traffic | iperf3 flows plus a scripted 1000-packet INT burst on UDP/4000. |
| 02 | Export | P4 switches, OVS, softflowd, snmpd and the gNMI agent each produce their own protocol. |
| 03 | Collect | Five decoders write into `db/telemetry.db` — SQLite in WAL mode, 24-hour retention. |
| 04 | Serve | Flask exposes `/api/<source>` and `/api/status`; six tabs refresh every 5 seconds. |

- Bottom-right, panel strip, 10.5 pt bold ink: *One shared schema — that is what
  makes it a comparison.*

**Notes (1.5 min):** Walk the figure once, top to bottom. Stress that the six
protocols share a database schema and a clock, not a switch or a vendor dashboard
— that is the only reason the outputs can be compared. Mention each stage is torn
down and rebuilt, and `run_all.sh` asserts rows at the end.

---

### Slide 5 — The INT data plane

Near-full-bleed figure slide. Header shrinks to a mono kicker only:
`04 · THE INT DATA PLANE — HOW A PACKET REPORTS ITSELF`

- `int_diagram.png` at x = 1.25, y = 0.86, 10.85 in wide (≈ 6.22 in tall). No border.
- Mono 9.5 pt caption under it, muted: *Boot-offset calibration on the first packet
  makes per-hop latency comparable across switches with unsynchronised clocks.*

**Notes (1.5 min):** Technical centrepiece. h1 emits UDP/4000 with an INT header;
s1 appends 12 bytes in the egress pipeline — switch id, ingress timestamp, egress
queue depth; s2 appends its own; the receiver at h2 walks the stack and computes
per-hop latency and jitter. Volunteer the two caveats before they are asked:
timestamps are per-switch boot clocks (calibrated, so relative latency is valid),
and the entry is 12 bytes of pure overhead per packet.

---

### Slide 6 — Result 1: the microburst

**Headline:** `A 41.5 ms burst, recorded packet by packet`
**Sub-head:** *s2 throttled to 500 packets/s; 1000 packets sent back to back; 80 INT samples aligned to the first packet of the burst.*

```
┌──────────── fig2.png ────────────┐  ┌──────────── fig3.png ────────────┐
│  queue 0 → 59 packets            │  │  delay 1.6 → 36.8 ms             │
└──────────────────────────────────┘  └──────────────────────────────────┘
 EGRESS QUEUE AT s2 · 0 → 59 PKTS      PER-HOP QUEUEING DELAY AT s2 · 1.6 → 36.8 ms
 ────────────  ────────────  ────────────  ────────────
 41.5 ms       59            36.8 ms       0.8 %
 burst dur.    peak queue    peak delay    poll catch
```

- Both figures 5.92 in wide, y = 1.98, captions at 4.68 in (mono 9 pt, spaced caps).
- Four hero stats in a row at y = 5.05, each with an ink rule above; the fourth
  (`0.8 %`) in accent.
- Italic 13 pt at 6.35: *Queue depth and hop latency rise and fall together: this is
  queueing delay measured inside the switch, not inferred from a counter delta.*

**Notes (1.5 min):** The demo slide. Left: 80 samples, queue climbs monotonically
from empty to 59 packets in 41.5 ms. Right: the delay that queue adds, up to
36.8 ms. They are the same packets, so the causal link is visible. Punchline: a
5-second poll had a 0.8 % chance of landing inside this window, and no counter
average would have preserved the shape anyway.

---

### Slide 7 — Result 2: six lenses

**Headline:** `Same burst. Six protocols. Six different answers.`
**Sub-head:** *Measured on the same network during the same event — not quoted from separate studies.*

Editorial table (no boxes, hairline rows, mono uppercase column labels), left,
7.45 in wide:

| PROTOCOL | WHAT ONE ROW IS | DID IT SEE THE BURST? |
|---|---|---|
| SNMP (gen 1) | interface counters, every 5 s | No — 0.8 % chance |
| NetFlow v5 / IPFIX (gen 2) | one completed flow | Only as one aggregate record |
| sFlow (gen 2) | one sampled packet header | Sampled packets only |
| gNMI (gen 3) | one OpenConfig leaf, every 2 s | Cumulative counters only |
| **INT (gen 4)** | **one hop of one packet** | **Yes — packet by packet** |

- The INT row gets the panel tint plus a 0.05 in accent bar on its left edge.
- Right: `dashboard.png` 4.4 in wide at x = 8.35, y = 2.02, then 10.5 pt muted
  caption: *One Flask dashboard, six tabs, one database: every protocol is read
  from the same wall-clock window.*
- Full-width panel at 6.25 in, 12.5 pt bold ink: *None of these replaces the
  others. INT answers "where did it queue?", flows answer "who and how much",
  SNMP answers "is the device alive".*

**Notes (1 min):** Read the last column only — that is the result. INT is the only
row that saw the event as an event. Then block the obvious objection: this is not
a ranking; each protocol has a different cost and a different question. The value
of the testbed is that the differences are visible on one screen instead of argued
in prose.

---

### Slide 8 — Result 3: end to end

**Headline:** `One command. Six tables. Every pipeline live.`
**Sub-head:** *run_all.sh brings up each stage, generates traffic, asserts rows, then leaves the dashboard running.*

Six tiles, 3 × 2 (3.9 × 1.68 in, 0.19 in gutters). Each: hero number in monospace
30 pt, table name in bold mono 12 pt, observation unit in 10.5 pt muted. Tiles are
panel-tinted; the first (`364`) stays paper with an accent top rule.

| 364 | 385,285 | 6 | 11 | 10 | 180 |
|---|---|---|---|---|---|
| `int_hops` | `sflow_samples` | `netflow_flows` | `ipfix_flows` | `snmp_stats` | `gnmi_stats` |
| one hop of one packet | one sampled header | one completed flow | one data record | one 5-second poll | one OpenConfig leaf |

- Ink band at 5.95 in, white mono 11 pt:
  `sudo bash run_all.sh  →  ALL 6 TABLES NON-EMPTY: PASS  ·  7 minutes end to end  ·  dashboard at localhost:5000`
- Italic muted 11 pt below: *Row counts differ by five orders of magnitude because
  the observation units differ. That is the finding, not an error.*

**Notes (45 s):** Do not read the table; say it. Six tables, five orders of
magnitude apart: 385k sampled headers against 6 completed flows. If asked why
sFlow dominates: sampling rate 1 in the emulator. The verdict line is the point —
all six wrote live rows in one run, seven minutes, one command.

---

### Slide 9 — Limitations

**Headline:** `What this testbed does not prove`
**Sub-head:** *Stated up front, because every one of these is a real constraint on how far the numbers travel.*

2 × 2 grid (5.94 × 1.9 in). Each cell: ink rule on top, mono accent label, 12.5 pt body.

| Label | Body |
|---|---|
| EMULATION, NOT HARDWARE | BMv2 models queues in software. The mechanism reproduces faithfully; the absolute values — 59 packets, 36.8 ms — do not transfer to an ASIC. |
| UNSYNCHRONISED CLOCKS | Each switch counts from its own boot. Per-hop latency is relative and offset-calibrated; a globally absolute end-to-end latency is not claimed. |
| gNMI IS EMULATED | An OpenConfig-shaped service over real P4Runtime counters. Genuine gRPC, but a far smaller leaf set than a vendor device exposes. |
| SAMPLING AND EXPORT DELAY | sFlow at rate 1 in an emulator flatters the result; production sampling misses more. softflowd flushes 10–60 s late through the WSL2 FIFO. |

Italic muted footer: *None of these hides the effect being demonstrated: within one
run, the six protocols are observed under identical conditions.*

**Notes (1 min):** Volunteer the limitations — fastest way to keep control of the
questions. Then the qualifier: the comparison is internally valid because all six
see the same network in the same run; the absolute numbers are what does not
travel.

---

### Slide 10 — Conclusion

**Headline:** `Telemetry is not one question.`

Left, three numbered takeaways (bold 15.5 pt lead + 12.5 pt body):

1. **Granularity is a design choice, not a ranking.** INT answers where a packet
   queued; flows answer who and how much; SNMP answers whether the box is alive.
   You deploy the one that matches the question you are paid to answer.
2. **The blind spot is measurable, not rhetorical.** 59 packets, 41.5 ms, 36.8 ms
   of queueing delay, 0.8 % chance of being polled — observed on one network in
   one run, not quoted from literature.
3. **A unified testbed is a teaching instrument.** Four generations, one command,
   reproducible on a laptop. It is the scaffold for the next experiment, not the
   end of one.

Right: panel with `THE ONE-LINE VERSION` label and italic 17 pt pull-quote:
*"Every packet can now report its own journey — and the old tools still cannot be
asked the question."*

Below the panel: `NEXT`, hairline, 11.5 pt: *Hardware INT on a Tofino-class switch;
PINT-style probabilistic sampling; streaming subscriptions instead of 2-s Gets.*

Bottom-left: `Thank you — questions` (18 pt bold), then mono 10 pt contact line.

**Notes (1 min):** Three takeaways, one sentence each. Then the quote, then stop
talking and invite questions. If time is short, skip future work. Likely first
question: "is INT better than SNMP?" — answer with takeaway 1, do not hedge.

---

### Backup A — The six pipelines

**Kicker:** `BACKUP · THE SIX PIPELINES`
**Headline:** `Exporter, transport and collection interval for each protocol`

Table (paper Table I), 10.6 in wide:

| PROTOCOL | EXPORTER → COLLECTOR | INTERVAL |
|---|---|---|
| INT (gen 4) | P4 switches s1, s2 → Scapy sniffer on h2, UDP/4000 | every packet |
| sFlow (gen 2) | OVS s1, sampling = 1, 128-B headers → UDP/6343 | samples + 10-s counters |
| NetFlow v5 (gen 2) | softflowd on h1 → UDP/9995 | flow end / timeout |
| IPFIX (gen 2) | softflowd on h3 (v10) → UDP/9996 | template-driven |
| SNMP (gen 1) | snmpd on h4 (v2c) ← pysnmp poller | 5-s poll |
| gNMI (gen 3) | emulated agent over P4Runtime ← pygnmi client | 2-s Get |

Italic footer: *Intervals matter: they are the resolution limit of each generation.
Only INT has no interval — it is per packet.*

### Backup B — Reproduce and verify

**Kicker:** `BACKUP · REPRODUCE AND VERIFY`
**Headline:** `Everything shown runs from a clean checkout`

- Left `RUN` code panel (panel tint, Consolas 10.5 pt):
  ```
  cd "/mnt/c/.../Network telementry"
  sudo bash run_all.sh        # ~7 min, wipes + refills
  open http://localhost:5000  # from Windows
  ```
- Left `VERIFY` code panel (Consolas 9.5 pt):
  ```
  python3 -c "import sqlite3; c=sqlite3.connect('db/telemetry.db'); ..."
  curl -s http://localhost:5000/api/status
  ```
- Right `ENGINEERING NOTES` list (12 pt bold + 11 pt muted):
  - **Every collector has `--selftest`** — parsing and DB writes verified without Mininet
  - **One schema, WAL mode** — readers and writers coexist; 24-hour retention
  - **Stages rebuild cleanly** — no port collisions between protocols
  - **Bugs found and fixed** — dashboard first-load pane, gNMI path regex

---

## 4. Timing plan (10:00)

| Slide | Content | Time | Running |
|---|---|---|---|
| 1 | Title + claim + three numbers | 1:00 | 1:00 |
| 2 | Problem, 0.8 % panel | 1:30 | 2:30 |
| 3 | Four generations | 1:00 | 3:30 |
| 4 | Architecture | 1:30 | 5:00 |
| 5 | INT data plane | 1:30 | 6:30 |
| 6 | Microburst evidence | 1:30 | 8:00 |
| 7 | Six lenses | 1:00 | 9:00 |
| 8 | E2E numbers | 0:45 | 9:45 |
| 9 | Limitations | 1:00 | 10:45 |
| 10 | Conclusion + thanks | 1:00 | 11:45 |

Overrun policy: slide 3 and slide 9 are the only compressible ones (merge the four
cards into one spoken sentence; limitations can move to Q&A). Never compress
slides 5–6 — they are the evidence.

If the slot is strictly 10:00 including questions, cut slide 8 to one sentence and
pull slide 10's "NEXT" block.

---

## 5. Copy rules

- Headline is a claim, ≤ 12 words, no colon-and-list constructions.
- Body is sentence case, active voice, no bullet-list-of-nouns.
- Numbers always carry their unit and their scope ("59 packets **at s2**").
- Never write "very", "significant", "cutting-edge", "revolutionary".
- Never claim absolute latency numbers as physical truth — say "per-hop, relative,
  calibrated" when the number is on screen.
- Em dashes fine; en dashes for ranges (10–60 s). Use real `→` and `·`.
- Every number must exist in §7.

---

## 6. Assets not to use

- `paper/figs/*_old.png`, `fig2.html`, `fig3.html` — superseded.
- `Network_Telemetry_Synopsis.pptx`, `Network_Telemetry_PPT_v2.pptx` — synopsis-era
  template and wording ("about 65 % complete", containerlab references). This deck
  reports a finished project on Mininet/BMv2; that file contradicts it.
- `plan/PPT_EXPLAINED.md` — plain-language walkthrough of the *old* deck; useful
  for phrasing ideas only, not as content.

---

## 7. Number sheet (single source of truth)

All from `paper/LATEST/…Latest.docx` — Table II, Fig. 4, Section V.

### Microburst experiment

| Quantity | Value | Notes |
|---|---|---|
| Burst size | 1000 packets, back to back | UDP/4000, h1 → h2 |
| s2 egress throttle | 500 packets/s | `set_queue_rate 500` |
| Burst duration as recorded | 41.5 ms | first to last INT sample |
| INT samples in the burst | 80 | aligned to burst start |
| Peak egress queue at s2 | 59 packets | from 0 |
| Peak per-hop queueing delay | 36.8 ms | at s2; steady state ≈ 1.6 ms |
| SNMP poll catch probability | 0.8 % | 41.5 / 5000 |

### End-to-end run (Table II)

| Protocol | Table | Rows | One row is |
|---|---|---|---|
| INT | `int_hops` | 364 | one hop of one packet |
| sFlow | `sflow_samples` | 385,285 | one sampled header |
| NetFlow v5 | `netflow_flows` | 6 | one completed flow |
| IPFIX | `ipfix_flows` | 11 | one data record |
| SNMP | `snmp_stats` | 10 | one 5-s poll |
| gNMI | `gnmi_stats` | 180 | one OpenConfig leaf |

### Environment

| Component | Version |
|---|---|
| Host | Windows 11 + WSL2, Ubuntu |
| P4 compiler | p4c 1.2.5.15 |
| Software switch | BMv2 1.15.4 (`simple_switch`, `simple_switch_grpc`) |
| Emulator | Mininet 2.3.0 |
| Software switch (sFlow) | Open vSwitch 3.7.1 |
| Topology | 4 hosts, 2 P4 switches (INT); 4-host star on OVS for flow/SNMP |
| Full run time | ≈ 7 minutes |
| Dashboard | Flask, `localhost:5000`, 6 tabs, 5-s refresh, 60-s liveness window |

⚠ Older documents in the repo report different counts (e.g. `report.md`:
460 / 375,251 / 6 / 11 / 10 / 540; `RUN_LOG.md`: 352 / 228,923 / 6 / 11 / 3 / 180;
`db/telemetry.db` on disk: 386 / 325,531 / 6 / 11 / 8 / 180). Row counts vary per
run and the burst peaks vary too. If the panel asks, say so plainly: *counts vary
by run; the paper's numbers are one recorded run, and the mechanism reproduces.*
Do not mix tables from different documents inside the deck.

---

## 8. Acceptance checklist

- [ ] 12 slides, 16:9, no stock Office theme visible
- [ ] Every headline is a claim (re-read slide 4, 8, 9)
- [ ] One accent element maximum per slide
- [ ] Speaker notes present on all 10 main slides, matching §3 wording
- [ ] No figure scaled above its native resolution (check `dashboard.png` at 4.4 in)
- [ ] All numbers match §7; no two sources mixed
- [ ] Supervisor / team / roll-number fields verified against the submission form
- [ ] Title slide, footer and page numbers consistent (`nn / 10`, backup slides
      labelled `BACKUP`, unnumbered or `B1/B2`)
- [ ] Exported to PDF as a fallback for the presentation machine
- [ ] Rehearsed once against §4 timing with a visible timer
