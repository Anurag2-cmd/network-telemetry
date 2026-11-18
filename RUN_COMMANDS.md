# RUN_COMMANDS.md — how to run this project, and where

Every command below says **WHERE** to run it. The project has three parts:

| Part | Where it runs |
|---|---|
| Emulated network + exporters + collectors (Mininet, P4/BMv2, OVS) | **WSL2 Ubuntu, as root** |
| Dashboard (Flask) | WSL2 **or** Windows PowerShell (both work) |
| Viewing the dashboard | **Windows browser** → http://localhost:5000 |
| Building the paper (DOCX + PDF) | **Windows PowerShell** |

Full guide with explanations: [`QUICKSTART.md`](QUICKSTART.md) · architecture: [`README.md`](README.md)

> Note: the `app.py` in the project ROOT is a legacy 34-line script — do not use it.
> The real dashboard is **`dashboard/app.py`**.

---

## 1. Is it running? (status check)

**PowerShell (Windows):**

```powershell
# dashboard up?
try { (Invoke-WebRequest http://localhost:5000/api/status -TimeoutSec 5 -UseBasicParsing).Content }
catch { "dashboard NOT running" }

# testbed (Mininet/collectors) up?
wsl.exe -d Ubuntu -e bash -c "pgrep -af 'run_all|topology_|simple_switch|softflowd' || echo 'testbed NOT running'"
```

**WSL (bash):**

```bash
curl -s http://localhost:5000/api/status          # dashboard + per-protocol data
pgrep -af 'run_all|topology_|simple_switch|softflowd' || echo 'testbed NOT running'
```

Healthy dashboard output: JSON with all six protocols (`int, sflow, netflow, ipfix, snmp, gnmi`),
each showing `rows_window > 0`. Badge `live` means "rows arrived within `LIVE_WINDOW_S`"
(default 24 h), **not** that traffic is flowing right now.

---

## 2. Run the whole demo (one command)

**Where: WSL2, as normal user (sudo prompts inside the script)**

```bash
wsl.exe -d Ubuntu            # from Windows — you are now in WSL
```
```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
sudo bash run_all.sh
```

Brings up all six protocol pipelines in order (INT → sFlow/NetFlow/IPFIX → SNMP → gNMI →
dashboard) and asserts every table got rows. ~7 minutes.

> ⚠️ It **wipes** the six telemetry tables first (`fresh_db`). Back up if needed:
> `cp db/telemetry.db /tmp/telemetry.db.bak`

---

## 3. Run the dashboard only

Option A — **WSL (bash)**, from the project root:

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
python3 dashboard/app.py
```

Option B — **PowerShell (Windows)**, from the dashboard folder:

```powershell
cd "C:\Users\ASUS\Desktop\Network telementry\dashboard"
python app.py
```

Then open **http://localhost:5000** in a Windows browser. Click a tab (first load shows no pane
until you do). Useful env var (set before starting):

- `LIVE_WINDOW_S` — how many seconds of recency counts as `live` (default `86400` = 24 h).
  PowerShell: `$env:LIVE_WINDOW_S='604800'` · WSL: `LIVE_WINDOW_S=604800 python3 dashboard/app.py`

If port 5000 is busy: `taskkill /PID <pid> /F` (Windows) or `pkill -f dashboard/app.py` (WSL).

---

## 4. Run a single stage (WSL, project root, after `cd` as above)

```bash
sudo python3 mn/topology_int_demo.py     # INT only (P4 switches + burst)
sudo python3 mn/topology_ovs.py          # sFlow + NetFlow + IPFIX
sudo python3 mn/topology_snmp.py         # SNMP
bash scripts/wsl-tmp/e2e-gnmi.sh         # gNMI
python3 dashboard/app.py                 # dashboard alone (see §3)
```

---

## 5. Verify data arrived (WSL, project root)

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('db/telemetry.db')
for t in ('int_hops','sflow_samples','netflow_flows','ipfix_flows','snmp_stats','gnmi_stats'):
    n, mx = c.execute('SELECT COUNT(*), MAX(ts) FROM '+t).fetchone()
    print('%-15s %-8d newest=%s' % (t, n, mx))
"
```

Or from Windows: `Invoke-WebRequest http://localhost:5000/api/status -UseBasicParsing`

---

## 6. Stop everything

**WSL (bash):**

```bash
sudo pkill -f dashboard/app.py
sudo pkill -f 'topology_'
sudo pkill -f simple_switch
sudo mn -c
sudo ovs-vsctl --if-exists del-br s1
sudo pkill -f iperf3
```

**PowerShell** (if dashboard runs on Windows):

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen | ForEach-Object { taskkill /PID $_.OwningProcess /F }
```

---

## 7. Build the paper (PowerShell only)

```powershell
Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force   # avoid file lock
& "C:\Users\ASUS\Desktop\Network telementry\paper\convert.ps1"
```

Outputs `paper\Network_Telemetry_Research_Paper.docx` + `.pdf` (5 figures embedded).

---

## Troubleshooting quick table

| Symptom | Fix |
|---|---|
| `mn: command not found` | you're in PowerShell — use WSL (§2) |
| Blank dashboard, but HTTP 200 | click a tab (known UI quirk) |
| All badges `offline` | expected after a run finishes; re-run a stage to see `live` |
| Empty chart boxes | no internet → Chart.js CDN blocked; go online or vendor `chart.min.js` |
| Port 5000 in use | kill the old dashboard (§6) |
| `p4/int.json` missing | compile once: `(cd p4 && p4c-bm2-ss --arch v1model int.p4 -o int.json)` |

More: [`QUICKSTART.md`](QUICKSTART.md) → Troubleshooting · [`DOCUMENTATION.md`](DOCUMENTATION.md) §11–12
