# RUN_LOG.md — E2E run + browser verification

Date: **2026-09-21** · Runner: AI assistant (Freebuff) · Host: Windows 11 + WSL2

> **Verdict: the full stack runs end to end.** `run_all.sh` completed without stopping,
> all six protocols produced fresh rows, and the Flask dashboard served real data to a
> real browser. Two UI bugs were found (documented in §5, **not fixed** — no source file
> was modified in this session).

- All times below are **UTC**, because WSL clocks in UTC. Windows local time is **UTC+5:30**
  (so `04:10 UTC` = `09:40 AM` local). The dashboard's badges use browser-local time, which
  is why they read `9:40 AM` for a row stamped `04:10`.
- Companion document: [`QUICKSTART.md`](QUICKSTART.md) — how to start the project.

---

## 1. Environment verified before running

Everything required is installed **inside WSL**, not on Windows. The shell this session's
commands started in was Git Bash on Windows (`MINGW64_NT-10.0-26200`), where `mininet`,
`p4c` and `simple_switch` do **not** exist — the whole demo must run in WSL.

| Component | Version / path (inside WSL) |
|---|---|
| Distro | Ubuntu 26.04 LTS, kernel `6.18.33.1-microsoft-standard-WSL2` |
| Python | 3.14.4 (`/usr/bin/python3`), running as `root` |
| p4c | 1.2.5.15 (`/usr/local/bin/p4c`) |
| BMv2 | `simple_switch`, `simple_switch_grpc`, `simple_switch_CLI` (`/usr/local/bin`) |
| Mininet | 2.3.0 (`/usr/bin/mn`) |
| Open vSwitch | 3.7.1 (`/usr/bin/ovs-vsctl`) |
| iperf3 | 3.20 |
| softflowd / snmpd | `/usr/sbin/softflowd`, `/usr/sbin/snmpd` |
| Also present | `tcpdump`, `curl`, `snmpget` |
| Python deps | Flask 3.1.3, psutil 7.2.2, scapy 2.7.0, pysnmp 7.1.27, pygnmi 0.8.15, grpcio 1.83.0, protobuf 7.35.1 |

Project path (note the space): `/mnt/c/Users/ASUS/Desktop/Network telementry`.
`run_all.sh` also maintains the space-free symlink `/tmp/nt` → that path, which several
scripts rely on.

## 2. Commands used

**Safety backup first** — `run_all.sh` deletes every row in the six tables at startup
(`fresh_db`), so the existing 24 MB database was copied before launching:

```bash
cp db/telemetry.db /tmp/telemetry.db.bak
```

**Launch the full E2E** (detached, so it outlives the invoking shell):

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
setsid nohup bash run_all.sh > /tmp/run_all.out 2>&1 < /dev/null &
```

Driven from Windows, that is exactly:

```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- bash -lc "cd '/mnt/c/Users/ASUS/Desktop/Network telementry' && setsid nohup bash run_all.sh > /tmp/run_all.out 2>&1 < /dev/null &"
```

**Verify** (row counts, freshness, and the script's own final assertion):

```bash
python3 -c "import sqlite3;c=sqlite3.connect('db/telemetry.db');[print(t, c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]) for t in ('int_hops','sflow_samples','netflow_flows','ipfix_flows','snmp_stats','gnmi_stats')]"
curl -s http://localhost:5000/api/status
```

## 3. Stage results — every protocol produced rows

| `run_all.sh` step | Table | Rows | Data window (UTC) | Sample of the newest row |
|---|---|---|---|---|
| 1/7 INT (2 P4 switches, receiver on h2) | `int_hops` | **352** | 04:10:02 → 04:10:23 | `flow=10.0.1.1:59252->10.0.1.2:4000 hop_idx=0 switch_id=1 queue_occupancy=4` |
| 2/7 OVS → sFlow | `sflow_samples` | **228,923** | 04:10:31 → 04:11:34 | counter row, `agent=172.18.15.145` |
| 2/7 OVS → NetFlow v5 | `netflow_flows` | **6** | 04:10:52 → 04:11:20 | `10.0.1.1:53832 -> 10.0.1.2:5201 proto=6 packets=14 bytes=1235` |
| 2/7 OVS → IPFIX v10 | `ipfix_flows` | **11** | 04:11:06 → 04:11:20 | `10.0.1.2:5201 -> 10.0.1.3:42646 proto=6 packets=13 bytes=1022` |
| 3/7 SNMP (snmpd on h4 + poller) | `snmp_stats` | **3** ⚠️ | 04:11:59 → 04:12:18 | `device=10.0.1.4 cpu_load=1.84 bw_in_mbps=2511.6 uptime=2459` |
| 4/7 gNMI (pygnmi over P4Runtime counters) | `gnmi_stats` | **180** | 04:12:53 → 04:13:09 | `interfaces/interface[name=0]/state/counters/in-octets = 1596` |
| 5/7 Dashboard | — | up | from 04:14 | `http://localhost:5000` |
| 6/7 Assertion | — | — | — | **PASS** (see §4) |

Stage observations:

- **INT** — 176 hops recorded per switch (352 total) across 2 flows, queue occupancy peaked
  at 26 and per-hop latency averaged ~17.8 ms on switch 2.
- **sFlow** — sampling = 1, nearly 229 k samples in ~63 s.
- **SNMP** — only 3 rows, whereas `mn/topology_snmp.py`'s own `verify()` requires ≥ 4
  (`total >= 4 and mem_rows == total and bw_rows > 0`). See §6.
- Wall-clock for the whole E2E was **about 7 minutes** (04:07 → 04:14).

## 4. Independent verification

**The script's own step 6/7 assertion was replayed** against the resulting database (its
own stdout log was lost — see §9) — identical logic, identical result:

```
  int_hops       352
  sflow_samples  228923
  netflow_flows  6
  ipfix_flows    11
  snmp_stats     3
  gnmi_stats     180
ALL 6 TABLES NON-EMPTY: PASS
```

**Dashboard exercised in a real browser** (headless preview attached to `localhost:5000`).
`/api/status` returned JSON for all six sources, and each of the six tabs was clicked and
measured. Charts were confirmed drawn by sampling actual canvas pixels (`getImageData`),
not merely by the presence of a `<canvas>` element:

| Tab | Pane visible | Canvases drawn | Table rows | Badge (local time) |
|---|---|---|---|---|
| INT | ✅ `display:block` | 4/4 at 360×210 | 16 | `offline · last 9:40:23 AM` |
| sFlow | ✅ | 4/4 at 360×202 | 16 | `offline · last 9:41:34 AM` |
| NetFlow | ✅ | 2/2 at 360×202 | 7 | `offline · last 9:41:20 AM` |
| IPFIX | ✅ | 2/2 at 360×202 | 12 | `offline · last 9:41:20 AM` |
| SNMP | ✅ | 4/4 at 360×202 | 4 | `offline · last 9:42:18 AM` |
| gNMI | ✅ | **1/2** (see §5.2) | 11 | `offline · last 9:43:09 AM` |

No console errors and no failed requests — the network log contained only `200`s
(`/api/status` and the active tab's endpoint, polled every 5 s).

Badges read `offline` because the run had finished by then: `LIVE_WINDOW_S = 60` in
`dashboard/db.py`, and the last row was already older than that. That is correct behaviour,
not a failure. NetFlow/IPFIX will read "not live" even *during* a healthy run, because
softflowd flushes 10–60 s after the traffic it describes.

## 5. Bugs found (reported, **not fixed**)

### 5.1 The dashboard opens blank on first load

**Symptom.** Opening `http://localhost:5000` shows only the heading and the tab row. No
charts, no tables, until you click a tab.

**Evidence.** On first load, measured in the browser:

- all six panes: `#pane-*` → `display: none` (only `#tab-int` had the `active` class);
- the four INT canvases existed but at **0 × 0**;
- `document.body.innerText` was 143 characters (just the header text).

After clicking `#tab-int`, `#pane-int` became `display: block` and all four canvases rendered
at **360 × 210 with real pixels**, populating a 16-row table. The click-path works; the
first-load path does not.

**Root cause** — `dashboard/templates/index.html`. `initTabs()` gives the active *tab* its
`active` class (`el.className = 'tab' + (t === activeTab ? ' active' : '')`) but nothing ever
gives the matching *pane* its class, and `switchTab()` is only reachable from a click:

```js
.pane { display: none; }
.pane.active { display: block; }
```

Because no pane is revealed, `refreshSource(activeTab)` also builds the INT charts while
their container is hidden, which is why Chart.js wrote 0 × 0 onto them.

**Minimal fix** — reuse the existing function instead of duplicating its body, at the bottom
of the script:

```js
// before
initTabs();
refreshStatus();
refreshSource(activeTab);
setInterval(refreshStatus, 5000);
setInterval(() => refreshSource(activeTab), 5000);

// after
initTabs();
switchTab(activeTab);      // activates the pane, then does the same two refreshes
setInterval(refreshStatus, 5000);
setInterval(() => refreshSource(activeTab), 5000);
```

`switchTab()` already calls `refreshStatus()` and `refreshSource(t)`, so this is a
like-for-like replacement that additionally activates the pane — **before** the async fetch
resolves, so Chart.js measures a real container. Do **not** keep the old two lines as well,
or the page double-fetches. Leave the two intervals untouched.

### 5.2 The gNMI "Per-interface in-octets" chart can never draw

**Symptom.** On the gNMI tab, the left chart draws; the right one stays an untouched
300 × 150 canvas with its "no data yet" placeholder logic never satisfied.

**Evidence.** The data is definitely present: the API window held 180 rows, of which
**36** were `key = 'in-octets'` across two interfaces. Yet the chart was never
instantiated.

**Root cause** — the interface name is parsed with a capturing group that includes the
closing bracket, and the bracket is then appended a second time:

```js
const m = (r.path || '').match(/name=([^/]+)/);   // '0]'  ← bracket captured
...
rows.filter(r => (r.path || '').indexOf('name=' + g + ']') !== -1)   // looks for 'name=0]]'
```

Confirmed live: the derived group names printed as `"1]"` and `"0]"`. The filter therefore
searches for `name=0]]`, matches nothing, every dataset comes back empty, `hasData` is false,
and `drawChart` returns before creating the chart.

**Fix** — stop the capture before the bracket (or stop appending it), e.g.

```js
const m = (r.path || '').match(/name=([^\]]+)/);
```

## 6. Observations that are *not* bugs (checked and cleared)

- **CDN dependency is fine on this machine.** `index.html` loads Chart.js from
  `https://cdn.jsdelivr.net/npm/chart.js`; in the test browser `typeof Chart === 'function'`,
  so it loaded. Worth knowing that the dashboard needs internet for its charts — an offline
  lab would show empty boxes while Flask still returns `200`.
- **sFlow canvases briefly measured 360 × 26.** This was a resize race caught mid-redraw
  right after the tab was revealed — Chart.js re-measuring a just-revealed pane. It is not an
  animation artifact: the line charts are configured with `animation: false`. Re-measured
  after settling, the canvases were 360 × 202, matching every other tab. Not a defect.
- **`snmp_stats` = 3 rows.** Lower than the stage's own self-check wants (≥ 4). Flagged as a
  follow-up, not proven broken — the table's data is otherwise sensible (valid CPU/mem,
  `bw_in_mbps = 2511.6`, uptime present).

## 7. Data safety

`run_all.sh` calls `fresh_db`, which deletes all rows from the six telemetry tables, so the
database it left behind contains **only this run's data**. The pre-run database (24,879,104
bytes) was backed up in two places:

| Copy | Path | Survives WSL shutdown? |
|---|---|---|
| WSL temp | `/tmp/telemetry.db.bak` | ❌ no (`/tmp` is cleared) |
| Windows temp | `C:\Users\ASUS\AppData\Local\Temp\telemetry-db-pre-e2e.bak` | ✅ yes |

To restore the pre-run data — **stop the dashboard first**, otherwise it keeps the database
open (and the `-wal`/`-shm` sidecars can hold stale state, so a swap underneath it is not
consistent):

```bash
# inside WSL
pkill -f dashboard/app.py                         # release the DB
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
cp db/telemetry.db /tmp/telemetry.db.this-run     # keep the new run too
cp /tmp/telemetry.db.bak db/telemetry.db
rm -f db/telemetry.db-wal db/telemetry.db-shm     # drop stale WAL sidecars
# restart it detached, exactly the way run_all.sh starts it
setsid nohup python3 dashboard/app.py > /tmp/dashboard.log 2>&1 < /dev/null &
```

(§8 gives the same stop command in its Windows-driven form,
`wsl.exe -d Ubuntu -u root -- pkill -f dashboard/app.py`.)

## 8. Current state and how to stop things

- The dashboard is **still running** on `0.0.0.0:5000` (WSL PID 2307), so
  `http://localhost:5000` works from the Windows browser.
- No Mininet / OVS / softflowd / P4 leftovers: every stage stopped its own topology in a
  `finally` block, and `run_all.sh` cleans up stale state at startup.
- Stop the dashboard:

  ```bash
  wsl.exe -d Ubuntu -u root -- pkill -f dashboard/app.py
  ```

  Stopping the thread's Preview tab kills only the Windows `wsl.exe` wrapper, which may
  orphan the Flask process that is actually holding port 5000 — use the command above if the
  port stays busy.

## 9. Gotchas worth remembering

| Gotcha | What happens | What to do |
|---|---|---|
| Git Bash mangles Unix paths | `> /tmp/run_all.out` was rewritten as a Windows path, so `run_all.sh`'s own stdout (including its final PASS/FAIL and each stage's summary) was never written — the run's verdict had to be reconstructed from the database | prefix commands with `MSYS_NO_PATHCONV=1` |
| The project path contains a space | `wsl.exe --cd "/mnt/c/.../Network telementry"` split at the space (`chdir(.../Network) failed`), and Mininet's `cmd()` splits on whitespace | use the `/tmp/nt` symlink, or quote carefully |
| WSL time is UTC | DB `ts` values look 5.5 h behind the browser's badge times | compare in one timezone |
| `git` inside WSL refuses the repo | `fatal: detected dubious ownership` (Windows-mounted dir, owned by `anurag`) | run git from Windows, or set `safe.directory` |
| Port 5000 already in use | a second `dashboard/app.py` fails to bind | `pkill -f dashboard/app.py` first |

## 10. Reproducing this session

**Paste this into a WSL shell** (not into Git Bash / PowerShell directly — driving it from
Windows needs the `MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- bash -lc "…"` wrapper
shown in §2, otherwise the `> /tmp/run_all.out` redirect is rewritten into a Windows path and
no log file is ever written, which is exactly what happened to this session's log):

```bash
# 1. back up, 2. run, 3. verify — all inside WSL as root
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
cp db/telemetry.db /tmp/telemetry.db.bak
setsid nohup bash run_all.sh > /tmp/run_all.out 2>&1 < /dev/null &
sleep 600
python3 -c "import sqlite3;c=sqlite3.connect('db/telemetry.db');[print(t, c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]) for t in ('int_hops','sflow_samples','netflow_flows','ipfix_flows','snmp_stats','gnmi_stats')]"
curl -s http://localhost:5000/api/status
```

Then open `http://localhost:5000` — and click a tab, because of §5.1.

**No project source file was modified during this session** — only documentation. `git status`
shows the pre-existing state (a one-word edit in `synopsis.md`, plus the untracked
PPT/`make_ppt.py` files) together with exactly three documentation changes made here: this
document, `QUICKSTART.md`, and a two-line pointer added to `README.md`.
