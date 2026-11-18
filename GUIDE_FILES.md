# GUIDE_FILES.md — what every file in this repo is, and how to run it elsewhere

Scope: inventory of `Network telementry/`. Researched 2026-10-08 against git `b06609b`;
current HEAD is `326c9d6`. Categories: **source** / **doc** / **generated** / **personal**.
Where something could not be verified, it says so.

> **Staleness note (2026-11-18).** Three commits have landed since `b06609b`, so the
> inventory below still describes that tree. Deltas that matter for a handoff:
> - `scripts/wsl-tmp/` is no longer wholesale-ignored: `.gitignore` keeps
>   `e2e-gnmi.sh` and `e2e-check.sh` via `!` rules, and both are now path-portable.
>   The "fresh clone cannot complete the gNMI stage" gap in §C is **fixed**.
> - `LIVE_WINDOW_S` defaults to 86,400 s (24 h), not 60 s; `/api/status` returns
>   `rows_window` + `window_s`, and the badge prints the real window.
> - The gNMI "Per-interface in-octets" chart bug (§5.2 of `RUN_LOG.md`) is **fixed**.
> Treat file counts and git state below as `b06609b` history, not current truth.

---

## A. What is in this repo, file by file

### Top level

| Path | What it is | Category | Keep? |
|---|---|---|---|
| `README.md` | Main overview: architecture, assignment mapping, file map, limitations (modified, uncommitted) | doc | yes |
| `QUICKSTART.md` | Copy-paste run guide: preflight, one-command run, verification, troubleshooting | doc | **yes — currently UNTRACKED, commit it** |
| `DOCUMENTATION.md` | Full reference: protocols, DB schema (§4), file map (§5), setup (§6), troubleshooting (§11) | doc | yes |
| `RUN_LOG.md` | Log of one verified E2E run + the two dashboard bugs (§5). **UNTRACKED** | doc | yes |
| `RUN_COMMANDS.md` | Every command labelled PowerShell vs WSL vs browser. **UNTRACKED** | doc | yes |
| `report.md` | Written assignment report (tracked, modified) | doc/personal | yes |
| `synopsis.md` | Project synopsis (tracked, modified) | doc/personal | yes |
| `run_all.sh` | Main orchestrator: cleanup → wipes 6 tables → INT → sFlow/NetFlow/IPFIX → SNMP → gNMI → dashboard → row-count assert | source | yes |
| `requirements.txt` | `flask` + `psutil` only. **Incomplete/legacy** — the real deps are `scapy flask pysnmp pygnmi grpcio` (README §Prerequisites); `psutil` is used only by the legacy `collector.py` | source (stale) | yes, but fix it |
| `.gitignore` | Ignores `__pycache__/`, `*.db*`, `p4/int.json`, `scripts/wsl-tmp/`, `.env`, venvs | source | yes |
| `app.py` | **Legacy** 34-line Flask app for the old ping prototype (`DB_PATH="telemetry.db"`), not used by the demo | source (legacy) | optional — remove or keep with warning |
| `collector.py` | **Legacy** Windows ping/psutil collector feeding the old root `telemetry.db` | source (legacy) | optional |
| `telemetry.db` (root, 196 KB) | Leftover DB of the legacy prototype (`samples` table) | generated | **no — delete** |
| `C??Users?ASUS?…?db?telemetry.db` (0 bytes) | Stray empty file: someone passed a Windows path as a *relative* SQLite path and it got created as a literal filename | generated | **no — delete** |
| `make_ppt.py` | Generates the two PPTX decks via `python-pptx`. **UNTRACKED** | source (personal) | optional |
| `Network_Telemetry_PPT_v2.pptx`, `Network_Telemetry_Synopsis.pptx` | Generated presentation decks. **UNTRACKED** | personal | optional (deliverable) |
| `PPT.txt` | 9-line slide outline for the deck. **UNTRACKED** | personal | optional |
| `GUIDE_FILES.md` | This file | doc | yes |

### Subfolders (one line each; details in section B)

| Path | What it is | Category | Keep? |
|---|---|---|---|
| `dashboard/` | Flask app: `app.py` (routes `/`, `/api/<source>`, `/api/status`), `db.py` (queries, `LIVE_WINDOW_S`), `templates/index.html` (Chart.js UI) | source | yes |
| `db/` | `telemetry.py` = shared SQLite helper, creates all 6 tables (`CREATE TABLE IF NOT EXISTS`); `telemetry.db` = the 24 MB data file | source + generated | yes / **no** (db ignored) |
| `mn/` | 4 Mininet topologies: `topology_int.py` (P4 switches), `topology_int_demo.py` (run_all INT stage), `topology_ovs.py` (sFlow+NetFlow+IPFIX), `topology_snmp.py` (SNMP) | source | yes |
| `p4/` | `int.p4` = P4-16 INT program; `int.json` = compiled output, **gitignored** | source / generated | yes / no (json) |
| `tools/` | One script per protocol: `int_sender/int_receiver`, `sflow_collector`, `netflow_collector`, `ipfix_collector`, `snmp_poller`, `gnmi_agent`, `gnmi_client` — all write to `db/telemetry.db` | source | yes |
| `scripts/` | `build-bmv2.sh` (BMv2 build) tracked; `wsl-tmp/` = **58 dev/debug shell scripts, gitignored** — but `wsl-tmp/e2e-gnmi.sh` is *required* by `run_all.sh` step 4/7 | source / dev scratch | build script: yes; wsl-tmp: see §C |
| `tasks/` | `TASKS.md` + 12 per-task specs (`01-…` … `12-…`), incl. exact p4c/BMv2 build commands | doc | yes |
| `paper/` | Research paper: `paper.html` (source) → `convert.ps1` (Word COM → DOCX+PDF) → `*.docx`/`*.pdf` (generated); `figs/` = screenshots + charts, incl. `*_old.png` backups, `~$paper.html` (Word lock file) | mixed | html+ps1+figs yes; docx/pdf/`_old`/lock optional |
| `templates/index.html` | **Leftover** UI from the old prototype (tracked; different hash than `dashboard/templates/index.html`) — DOCUMENTATION §5 says it is unused | source (legacy) | **no — candidate for removal** |
| `plan/PPT_EXPLAINED.md` | Plain-language walkthrough of the 8 PPT slides. **UNTRACKED** | personal/doc | optional |
| `.freebuff/` | `desktop.db` (+`-wal`/`-shm`, ~6 MB total): an unrelated SQLite DB left by tooling. Gitignored via `*.db` | generated | **no — delete** |
| `__pycache__/`, `dashboard/__pycache__`, … | Python bytecode caches | generated | no (ignored) |
| `.git/` | Repo data | — | yes |

---

## B. Folder map

```
dashboard/   Flask server + REST API + Chart.js single-page UI  (port 5000)
db/          shared SQLite helper (schema/WAL/cleanup) + telemetry.db (ignored, ~24 MB)
mn/          Mininet topologies — one script per demo stage
p4/          P4 source (int.p4) + compiled int.json (ignored)
tools/       8 collectors/senders — one per telemetry protocol, all → db/telemetry.db
scripts/     build-bmv2.sh (tracked) + wsl-tmp/ dev scripts (ignored, 58 files)
tasks/       TASKS.md index + 12 build specs (how each piece was made)
paper/       research paper: HTML source, PowerShell converter, DOCX/PDF, figures
plan/        PPT companion write-up (untracked)
templates/   leftover old dashboard HTML (unused)
.freebuff/   stray unrelated SQLite DB (ignored)
```

---

## C. Repo essentials — commit vs ignore

**Currently tracked (51 files):** code (`dashboard/`, `db/telemetry.py`, `mn/`, `p4/int.p4`,
`tools/`, `run_all.sh`, `scripts/build-bmv2.sh`), docs (`README.md`, `DOCUMENTATION.md`,
`report.md`, `synopsis.md`), `tasks/`, `paper/` (HTML+DOCX/PDF+figs), plus **legacy**
`app.py`, `collector.py`, `templates/index.html`.

**Gitignored (`.gitignore`):** `__pycache__/`, `*.db`/`*.db-shm`/`*.db-wal`,
`p4/int.json`, `scripts/wsl-tmp/`, `.env`, `.venv/`, `venv/`.

**Working-tree state (uncommitted):** modified `README.md`, `dashboard/db.py`,
`dashboard/templates/index.html`, `report.md`, `synopsis.md`; staged-new `paper/*`;
untracked-but-not-ignored: `QUICKSTART.md`, `RUN_LOG.md`, `RUN_COMMANDS.md`, `make_ppt.py`,
both PPTX, `PPT.txt`, `plan/`, `paper/figs/*_old.png`, `paper/figs/figure1_testbed_architecture.png`,
`paper/~$paper.html`.

**Should be committed:** `QUICKSTART.md`, `RUN_LOG.md`, `RUN_COMMANDS.md` (core run docs —
a fresh clone has no way to run the project without them), `plan/PPT_EXPLAINED.md` +
`make_ppt.py` (if the PPTs are deliverables), and the pending edits above.

**Should NOT be in the repo / should be cleaned up:**
- root `telemetry.db` (196 KB legacy DB), the 0-byte `C??Users?…` stray file, `.freebuff/` — all ignored already, but they are dead weight on disk.
- `paper/~$paper.html` — Word lock file, never commit.
- `paper/figs/*_old.png` — image backups.
- `templates/index.html`, `app.py`, `collector.py` — leftover prototype (DOCUMENTATION §5 states they are unused); removing them needs a doc update, so this is a decision, not an oversight.
- Generated `paper/*.docx` / `*.pdf` (~1.1 MB) — tracked binaries; keep only if submission requires it.
- Root `requirements.txt` does not describe the real dependencies (see §D).

**✅ Former repo gap, fixed in `e80698f`:** `run_all.sh:96` runs
`bash scripts/wsl-tmp/e2e-gnmi.sh`. At `b06609b` that file was ignored, so a fresh
clone could not complete the gNMI stage. `.gitignore` now keeps `e2e-gnmi.sh` and
`e2e-check.sh` via `!` rules, and both derive their project root from
`${BASH_SOURCE[0]}`, so a clone anywhere works.

---

## D. Run this project on someone else's PC

Target: clean **Windows 11 + WSL2 (Ubuntu)**, internet access. Everything except the browser
runs **inside WSL as root**; only the dashboard is opened from Windows.

### 1. Prerequisites

- Windows 11, WSL2, an Ubuntu distro, internet (also needed at runtime for the Chart.js CDN).
- Heavy: `p4c` and BMv2 are **built from source** (~long builds; run them inside `tmux`).
  Exact steps: `tasks/01-finish-p4c-build.md`, `tasks/02-build-bmv2.sh`/`02-build-bmv2.md`,
  `scripts/build-bmv2.sh`. Verified versions in `RUN_LOG.md` §1: p4c 1.2.5.15, BMv2 1.15.4,
  Mininet 2.3.0, OVS 3.7.1, Python 3.14.4, Ubuntu 26.04.
- ⚠ The docs do **not** contain a single ready-made apt line for the runtime tools; the
  package names below are the tools the docs require (apt names shown are the standard
  Ubuntu ones — verify with `apt search` if unsure).

### 2. Install (exact order)

**(a) PowerShell — install WSL2 + Ubuntu:**
```powershell
wsl --install -d Ubuntu
# reboot if prompted, then create the Linux user
wsl -d Ubuntu
```

**(b) WSL — system packages:**
```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch softflowd snmpd snmp-mibs-downloader \
                    iperf3 tcpdump curl python3-pip git tmux
```
Build deps explicitly named in `tasks/01` / `tasks/02` (only needed if you build p4c/BMv2):
```bash
sudo apt install -y libprotobuf-dev protobuf-compiler libgrpc-dev libgrpc++-dev \
                    protobuf-compiler-grpc libthrift-dev python3-thrift
```
Then build p4c + BMv2 per `tasks/01-*.md` / `tasks/02-*.md` using `scripts/build-bmv2.sh`
(`~/p4tools/` is where this project kept the clones; builds belong in `tmux`).
`p4c-bm2-ss`, `simple_switch`, `simple_switch_grpc`, `simple_switch_CLI` must end up on PATH.

**(c) WSL — Python packages** (the real list from README §Prerequisites — `requirements.txt` is incomplete):
```bash
pip3 install scapy flask pysnmp pygnmi grpcio psutil
```

**(d) WSL — passwordless sudo** (the whole demo runs as root and `run_all.sh` calls `sudo` internally):
```bash
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/$USER && sudo chmod 440 /etc/sudoers.d/$USER
```

### 3. First-run gotchas

1. **Compile `p4/int.json`** — gitignored; nothing P4-related runs until it exists:
   ```bash
   cd "/mnt/c/Users/ASUS/Desktop/Network telementry/p4"
   p4c-bm2-ss --arch v1model int.p4 -o int.json
   ```
   (Adapt the path to wherever the clone lives.)
2. **`scripts/wsl-tmp/e2e-gnmi.sh`** — tracked (see §C), so there is nothing to copy
   on a fresh clone.
3. **Path contains spaces** — always quote `cd "/mnt/c/.../Network telementry"`. `run_all.sh`
   creates a space-free symlink `/tmp/nt` that several scripts rely on.
4. **Passwordless sudo** must already work (step 2d).
5. **Port 5000 free:** `ss -ltn | grep :5000` → empty; otherwise `sudo pkill -f dashboard/app.py`.
6. **Chart.js loads from `cdn.jsdelivr.net`** — with no internet the dashboard returns 200
   but charts stay empty boxes.
7. **Paths are portable.** `e2e-gnmi.sh` and `e2e-check.sh` derive `PROJ` from
   `${BASH_SOURCE[0]}`, so there is no hardcoded `/mnt/c/...` line to edit.

### 4. Three commands: fresh clone → running dashboard

**WSL:**
```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
# one-time per clone: compile P4 (section 3.1) if p4/int.json is missing
sudo bash run_all.sh            # ~7 min; wipes the 6 tables first, then refills them
```
**Windows browser:** open `http://localhost:5000` and **click a tab** (bug #1: panes are hidden until clicked).

### 5. Verify (WSL)

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
python3 -c "
import sqlite3
c = sqlite3.connect('db/telemetry.db')
for t in ('int_hops','sflow_samples','netflow_flows','ipfix_flows','snmp_stats','gnmi_stats'):
    n, mx = c.execute('SELECT COUNT(*), MAX(ts) FROM '+t).fetchone()
    print('%-15s %-8d newest=%s' % (t, n, mx))
"
curl -s http://localhost:5000/api/status
```
Healthy run (real numbers from `QUICKSTART.md` §4 — exact counts vary):
`int_hops ~352`, `sflow_samples ~228923`, `netflow_flows ~6`, `ipfix_flows ~11`,
`snmp_stats ~3`, `gnmi_stats ~180`; `/api/status` shows all six sources with
`rows_window > 0` (and `window_s`, default 86400).
`run_all.sh` itself prints `ALL 6 TABLES NON-EMPTY: PASS` — note PASS only means "> 0 rows".

### 6. Stop / cleanup (WSL)

```bash
sudo pkill -f dashboard/app.py
sudo pkill -f 'topology_'
sudo pkill -f simple_switch
sudo mn -c
sudo ovs-vsctl --if-exists del-br s1
sudo pkill -f iperf3
```
`run_all.sh` does all of this at startup, so a crashed run is usually fixed by re-running it.

---

## E. Common first-run failures (grounded in the docs)

| Symptom | Fix |
|---|---|
| `mn: command not found` or `chdir(.../Network) failed` | You're in PowerShell/CMD/Git Bash, or the space split the path — run inside WSL, quote the path, or use `/tmp/nt` |
| P4 switches won't start | `p4/int.json` missing (recompile) or a stale `simple_switch` holds the thrift ports (`sudo pkill -f simple_switch`) |
| gNMI stage fails / `e2e-gnmi.sh: No such file` | Script should be tracked; if missing, `git checkout -- scripts/wsl-tmp/e2e-gnmi.sh`. Also needs `simple_switch_grpc` built (`tasks/02`) |
| Dashboard blank at localhost:5000 | Known bug (`initTabs()` never activates a pane) — click any tab. Fix: call `switchTab(activeTab)` (`RUN_LOG.md` §5.1) |
| gNMI "Per-interface in-octets" chart never draws | **Fixed 2026-11-18** — the capture used to include the `]` (`RUN_LOG.md` §5.2); if it reappears check `/name=([^\]]+)/` |
| Charts are empty boxes, HTTP 200 | No internet → Chart.js CDN unreachable; get online or vendor `chart.min.js` |
| Port 5000 already in use | Old dashboard still running → `sudo pkill -f dashboard/app.py` |
| All badges read `offline` | Expected once the last row is older than `LIVE_WINDOW_S` (default 24 h) — re-run a stage; not an error |
| NetFlow/IPFIX rows arrive 10–60 s late | softflowd flush timeout — expected, wait and refresh |
| Stage prints FAIL but run continues | `run_all.sh` deliberately continues on non-zero exit; read that stage's output and re-run it alone (`QUICKSTART` §3) |
| `snmp_stats` has too few rows | Run's PASS only checks ">0"; the stage's own check wants ≥4 polls — re-run `sudo python3 mn/topology_snmp.py` |
| Tables stay empty after a messy run | `sudo mn -c`, kill leftover collectors, re-run `run_all.sh` (it also cleans up at startup) |
| softflowd captures nothing | Known WSL2 limitation — the code uses a `tcpdump -U` FIFO; don't "fix" it back to live capture |
| Wrong timezone in output | `MAX(ts)` is UTC, dashboard badges are local time — differs by your UTC offset |

*Not verified here:* exact apt package names for Mininet/OVS/softflowd on a fresh Ubuntu
(the docs list the required tools but no single install command), and whether the p4c/BMv2
source builds still succeed on a brand-new distro — follow `tasks/01`–`02`.
