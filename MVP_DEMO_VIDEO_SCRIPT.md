# MVP Demo Video — Script & Recording Guide

**Length:** 3 min 30 s – 4 min  •  **Format:** screen recording + voice-over (no face needed)
**Goal:** show that an emulated network can run six telemetry protocols at once, store all of them in one database, and prove with one measured event that in-band telemetry sees what SNMP polling misses.

This is **not** a "web app tour". The product here is the *testbed*: scripts + a Flask dashboard are the way you demonstrate it. Record the terminal, the dashboard, and one diagram — that is a legitimate MVP demo.

---

## 1. The one message to repeat

> "One network, six telemetry protocols, one database, one dashboard — so you can compare how each protocol sees the *same* event."

Supporting headline result (from `paper/paper.html`, Fig. 4 & Fig. 5):
- A 1,000-packet microburst filled switch s2's egress queue **0 → 59 packets in 41.5 ms**, with **36.8 ms** peak queueing delay.
- A 5-second SNMP poll had only a **0.8%** chance of sampling any instant inside that window — and even then would see only the final counter, not the queue growth.

---

## 2. Pre-flight checklist (do this before recording)

1. **Back up the database** — `run_all.sh` wipes the six tables on startup:
   ```bash
   cp db/telemetry.db /tmp/telemetry.db.bak
   ```
2. **Run the full demo once** (takes ~7 min; record only the interesting parts, or fast-forward it in editing):
   ```bash
   sudo bash run_all.sh
   ```
   Watch each stage's own summary — the final `PASS` only checks that each table has > 0 rows.
3. **Check all six tables have data:**
   ```bash
   python3 -c "
   import sqlite3
   c = sqlite3.connect('db/telemetry.db')
   for t in ('int_hops','sflow_samples','netflow_flows','ipfix_flows','snmp_stats','gnmi_stats'):
       print('%-15s %d' % (t, c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]))
   "
   curl -s http://localhost:5000/api/status
   ```
4. **Open the dashboard in Windows Chrome:** `http://localhost:5000`.
   - **Click a tab immediately** — the first load is blank until you do (known bug, `RUN_LOG.md` §5.1).
   - Chart.js comes from a CDN, so keep the machine online.
   - Badges will say `offline · last 9:xx` once the run ends. That is correct, not a failure; say so in the video.
   - NetFlow/IPFIX flush 10–60 s after traffic, so their rows appear late by design.
5. **Optional but recommended for a clean recording:** apply the two one-line fixes in `RUN_LOG.md` §5.1 and §5.2 before recording (blank first pane; gNMI in-octets chart). Otherwise skip the broken gNMI chart on camera.
6. Have these ready to show on screen:
   - `paper/figs/figure1_testbed_architecture.png` (architecture)
   - `paper/figs/fig4.png`-style queue chart / Fig. 4–5 from `paper/paper.html` (microburst evidence)
   - `p4/int.p4` opened in an editor (the INT stamping logic)
   - the repo folder in File Explorer (`README.md`, `run_all.sh`, `db/`, `dashboard/`, `tools/`)

---

## 3. Recording setup

**Easiest good-quality option: OBS Studio (free, Windows).**
- Settings → Output → Output Mode: **Simple**; Recording Format **MP4**, Encoder **H.264 (NVENC or x264)**, Rate Control **CBR**, Bitrate **6000 Kbps**, Resolution **1920×1080**, FPS **30**.
  A 4-minute recording at 6 Mbps is about **180 MB** — safely under the form's 1000 MB limit.
- Audio: microphone at 44.1/48 kHz; enable Noise Suppression if available.
- Create three Scenes:
  1. **Terminal** — window capture of the WSL/Windows terminal, full screen.
  2. **Dashboard** — window capture of the Chrome window at `localhost:5000`.
  3. **Split** — Dashboard as the base, Terminal as a small Picture-in-Picture in the corner.
- Use hotkeys to switch scenes; **record in one continuous take** and trim later. If you must stop, keep the raw clips.

**No OBS?** Windows Game Bar: `Win + G` → Record (`Win + Alt + R`) captures the foreground app. Capture the browser and terminal in separate clips and join them in Clipchamp.

**No mic / don't want to speak?** Record the same shots, then add a voice-over track with Windows Voice Recorder or a text-to-speech tool, and burn in captions during editing. Narration silence with captions is acceptable.

**Framing tips:** maximise the browser window, zoom the browser to 125–150% (`Ctrl + +`) so charts are legible, hide bookmarks bar (`Ctrl + Shift + B`), close unrelated tabs, and use the mouse to point at the chart line you are discussing.

---

## 4. Shot-by-shot script

| # | Time | On screen | Narration (say this) | Notes |
|---|---|---|---|---|
| 1 | 0:00–0:18 | **Hook.** INT dashboard tab, queue-occupancy chart with the burst spike. Zoom in on the peak. | "This is a queue filling up inside a switch — 0 to 59 packets in 41.5 milliseconds. A normal SNMP poll has less than a one-percent chance of ever sampling this. Everything you're seeing was captured by a network we built on one laptop." | Start on the result, not the intro. Add a text overlay: **"0 → 59 packets in 41.5 ms"**. |
| 2 | 0:18–0:48 | Architecture diagram `paper/figs/figure1_testbed_architecture.png`. | "The problem is that network tools don't talk to each other. SNMP polls every few seconds and misses fast events. NetFlow, sFlow and IPFIX give you traffic summaries but not what happened inside a switch. gNMI and in-band telemetry fix that, but are usually studied alone, each with its own dashboard. We put all four generations — six protocols — on the *same* traffic, in one testbed." | Highlight the diagram: network → six collectors → one SQLite DB → one dashboard. |
| 3 | 0:48–1:15 | File Explorer: `p4/int.p4`, `tools/`, `db/telemetry.py`, `dashboard/app.py`, `run_all.sh`. Briefly open `p4/int.p4` at the egress metadata insertion. | "Our own contribution is the P4 data plane: each switch stamps a 12-byte note onto every packet — switch ID, timestamp and queue depth — as it leaves the switch. Six small Python collectors decode the six protocols and write to one SQLite database. The dashboard is a Flask app with a tab per protocol." | Show the code line where `enq_qdepth` is appended; don't read code aloud. |
| 4 | 1:15–1:40 | **Terminal:** `sudo bash run_all.sh`. Let it scroll; speed up 8–16× in editing. End on the `ALL 6 TABLES NON-EMPTY: PASS` line. | "The whole thing runs from one command. It starts the Mininet network, the P4 switches, the flow exporters, the SNMP and gNMI pollers, and finally the dashboard — then it checks that all six database tables actually received data." | Do **not** record the real 7 minutes. Capture 10–15 s and time-lapse it; overlay "≈7 min". |
| 5 | 1:40–2:20 | **Dashboard**, click through INT → sFlow → NetFlow → IPFIX → SNMP → gNMI. Pause ~3 s on each. Point at the green `live · N rows/24h` badges. | "Here is the payoff. Six tabs, six protocols, one dashboard refreshing every five seconds. INT shows per-hop delay and queue depth. sFlow shows sampled packets and bandwidth. NetFlow and IPFIX show who talked to whom. SNMP shows device counters. gNMI shows streaming OpenConfig state. Same network, same traffic, six different lenses — you can finally compare them side by side." | **Click a tab** or the pane is blank. Expect `offline` badges after the run — mention it or hide them. The gNMI right-hand per-interface chart is fixed — show it. |
| 6 | 2:20–2:55 | Back to **INT tab**, queue chart. Then show Fig. 4 / Fig. 5 from the paper if available. | "Here's why this matters. We throttled one switch's egress queue and sent a thousand packets back-to-back. INT recorded the queue growing for 41.5 milliseconds and the delay peaking at 36.8 milliseconds — packet by packet, hop by hop. SNMP's five-second poll would see only the aftermath. The flow protocols saw that traffic existed, but not the queue inside the switch." | Use the mouse to trace the rising line. Optional overlay: "0.8% chance a 5 s SNMP poll lands inside the burst". |
| 7 | 2:55–3:20 | **Split scene.** Terminal: the six-table SQL count + `curl -s http://localhost:5000/api/status`. Dashboard still visible. | "And it's all real data, not a mock-up. These are the row counts from the database — hundreds of thousands of sFlow samples, a few hundred INT hops, a handful of flows, ten SNMP polls and hundreds of gNMI leaves. The counts differ because the protocols deliberately observe at different rates." | Show the actual numbers from *your* run; don't read all of them aloud. |
| 8 | 3:20–3:35 | Hold on the six tabs; end card with title, repo URL and "Network & Communications". | "Six protocols, four generations, one database, one dashboard — and a measured example of why modern telemetry sees what traditional monitoring can't. It's all reproducible with one command from the repository. Thank you." | End card text: **Network Telemetry · Mininet + P4 + OVS · SNMP / NetFlow / sFlow / IPFIX / gNMI / INT**. |

---

## 5. Clean teleprompter version (read straight through)

> This is a queue filling up inside a switch — zero to 59 packets in 41.5 milliseconds. A normal SNMP poll has less than a one-percent chance of ever sampling this. Everything you're seeing was captured by a network we built on one laptop.
>
> The problem is that network tools don't talk to each other. SNMP polls every few seconds and misses fast events. NetFlow, sFlow and IPFIX give you traffic summaries but not what happened inside a switch. gNMI and in-band telemetry fix that, but are usually studied alone, each with its own dashboard. We put all four generations — six protocols — on the same traffic, in one testbed.
>
> Our own contribution is the P4 data plane: each switch stamps a 12-byte note onto every packet — switch ID, timestamp and queue depth — as it leaves the switch. Six small Python collectors decode the six protocols and write to one SQLite database. The dashboard is a Flask app with a tab per protocol.
>
> The whole thing runs from one command. It starts the Mininet network, the P4 switches, the flow exporters, the SNMP and gNMI pollers, and finally the dashboard — then checks that all six database tables actually received data.
>
> Here is the payoff. Six tabs, six protocols, one dashboard refreshing every five seconds. INT shows per-hop delay and queue depth. sFlow shows sampled packets and bandwidth. NetFlow and IPFIX show who talked to whom. SNMP shows device counters. gNMI shows streaming OpenConfig state. Same network, same traffic, six different lenses — you can finally compare them side by side.
>
> Here's why this matters. We throttled one switch's egress queue and sent a thousand packets back-to-back. INT recorded the queue growing for 41.5 milliseconds and the delay peaking at 36.8 milliseconds — packet by packet, hop by hop. SNMP's five-second poll would see only the aftermath. The flow protocols saw that traffic existed, but not the queue inside the switch.
>
> And it's all real data, not a mock-up. These are the row counts from the database — hundreds of thousands of sFlow samples, a few hundred INT hops, a handful of flows, ten SNMP polls and hundreds of gNMI leaves. The counts differ because the protocols deliberately observe at different rates.
>
> Six protocols, four generations, one database, one dashboard — and a measured example of why modern telemetry sees what traditional monitoring can't. It's all reproducible with one command from the repository. Thank you.

---

## 6. Editing & export

1. **Trim** the dead air at the start/end; keep the run_all.sh segment but time-lapse it.
2. **Cut on narration**, not on mouse movement; keep each dashboard tab shot 2–4 s.
3. **Add captions** (Clipchamp, CapCut, or DaVinci Resolve auto-captions) — reviewers often watch muted.
4. **Add two overlays only:** the headline number (0 → 59 / 41.5 ms) and the repo URL at the end. Avoid clutter.
5. **Export:** 1080p, 30 fps, H.264 MP4, 5–6 Mbps, AAC audio. Target **3–4 minutes, < 200 MB** (form limit is 1000 MB).
6. **Watch it once muted** — if the charts aren't readable, redo the dashboard shots at higher browser zoom.

---

## 7. Common mistakes to avoid

- **Recording before the data exists** → empty charts. Run `run_all.sh` first.
- **Blank dashboard on first load** → click any tab (known bug #1).
- **All badges `offline`** → expected after the run; explain it or re-run one stage to get green badges while recording.
- **Trying to show a "live deployment"** → the dashboard is local by design; say "runs locally at localhost:5000". If the form requires a link, either use a temporary tunnel (`ngrok http 5000`) during recording or point to the GitHub repo — don't invent a public URL.
- **Claiming production numbers** → these are Mininet/BMv2 emulation figures; say "emulated, mechanism faithfully reproduced".
- **Inconsistent numbers** → `report.md` quotes an older run (queue 43–45, ~22 ms); the paper and figures quote 0 → 59 in 41.5 ms and 36.8 ms. Use the paper figures in the video so the narration matches figures 4 and 5.

---

## 8. Submission checklist

- [ ] MP4 exported, 3–4 min, under 1000 MB
- [ ] Charts legible, captions burned in
- [ ] Repo URL visible on the end card
- [ ] Links: GitHub repo + a real deployment link (or explicit "local dashboard" note)
- [ ] Form fields: Domain, Problem Statement, Implementation Details filled
- [ ] Submit once — the form is single-submission
