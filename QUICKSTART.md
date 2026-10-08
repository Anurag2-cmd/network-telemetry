# QUICKSTART.md — start the Network Telemetry stack

A working, copy-pasteable guide to getting this project running. It assumes you are on the
same Windows 11 + WSL2 machine this project was built and tested on.

**Related documents:** [`README.md`](README.md) — what the project is and its architecture ·
[`DOCUMENTATION.md`](DOCUMENTATION.md) — full reference (protocols, DB schema, verification,
troubleshooting) · [`RUN_LOG.md`](RUN_LOG.md) — the log of the verified end-to-end run ·
[`report.md`](report.md) — the written report.

---

## The one thing to understand first

This project has **two halves that live in different places**:

| Half | Where it runs | How you use it |
|---|---|---|
| The emulated network (Mininet + P4/BMv2 + OVS, exporters, collectors) | **inside WSL2 Ubuntu, as root** | `sudo` commands in a WSL shell |
| The dashboard | Flask inside WSL, but you open it | your normal Windows browser |

So: **every command below runs in WSL, never in PowerShell, CMD or Git Bash.** Those have no
`mn`, `p4c` or `simple_switch`. The dashboard is the only part you touch from Windows.

> **Verified environment** (this is what a successful run was confirmed on): WSL2 · Ubuntu
> 26.04 LTS · kernel `6.18.33.1-microsoft-standard-WSL2` · Python 3.14.4 · p4c 1.2.5.15 ·
> Mininet 2.3.0 · OVS 3.7.1 · iperf3 3.20 · Flask 3.1.3 · scapy 2.7.0 · pysnmp 7.1.27 ·
> pygnmi 0.8.15 · grpcio 1.83.0. Full details in [`RUN_LOG.md`](RUN_LOG.md) §1.

---

## 0. Preflight — 30 seconds, run this first

Open a WSL shell and check that everything the demo needs is present:

```bash
wsl.exe -d Ubuntu            # from Windows; you are now in WSL as user 'anurag'
```

```bash
# inside WSL
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
for t in python3 p4c simple_switch simple_switch_grpc simple_switch_CLI \
         mn ovs-vsctl softflowd snmpd snmpget iperf3 tcpdump curl; do
    printf '%-20s %s\n' "$t" "$(command -v "$t" || echo MISSING)"
done
python3 -m pip list 2>/dev/null | grep -iE '^(Flask|psutil|scapy|pysnmp|pygnmi|grpcio) '
ls p4/int.json            # compiled artifact — compile it once, see the note below
```

Every tool should print a path, all six Python packages should appear, and `p4/int.json`
should be listed — on a **brand-new checkout it will not be**, until you compile it (next
note).

> **First-time step: compile the P4 program.** `p4/int.json` is deliberately **gitignored**
> (see `.gitignore` → "Generated P4 artifacts"), so a fresh checkout never contains it and
> nothing will run until it exists. Compile it once, using the same command this project
> documents in [`tasks/03-compile-p4-int.md`](tasks/03-compile-p4-int.md):
>
> ```bash
> (cd "/mnt/c/Users/ASUS/Desktop/Network telementry/p4" \
>   && p4c-bm2-ss --arch v1model int.p4 -o int.json)   # subshell: leaves your cwd alone
> ```
>
> p4c/BMv2 themselves are large builds — see [`DOCUMENTATION.md`](DOCUMENTATION.md) §6 and
> [`scripts/build-bmv2.sh`](scripts/build-bmv2.sh) for the exact build steps used here.

Two things to confirm as well:

- **`sudo` is passwordless** for this user — the whole demo runs as root.
- **Port 5000 is free** — `ss -ltn | grep :5000` should print nothing; if it does,
  `sudo pkill -f dashboard/app.py`.

## 1. Run the whole demo (the normal path)

One command brings up all six protocol pipelines and leaves the dashboard running:

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
sudo bash run_all.sh
```

It runs, in order, checking after each stage that rows actually landed in the database:

1. **INT** — 2 P4 switches, receiver on h2, steady flow + burst → `int_hops`
2. **sFlow + NetFlow + IPFIX** — OVS topology, softflowd exporters, iperf traffic
3. **SNMP** — `snmpd` on h4, poller every 5 s → `snmp_stats`
4. **gNMI** — emulated gNMI agent over P4Runtime counters, pull client every 2 s → `gnmi_stats`
5. **Dashboard** — starts `dashboard/app.py` and keeps it alive
6. **Assertion** — every table must have > 0 rows

**What to expect:** about **7 minutes** end to end on the machine this was verified on — a
single observation rather than a guarantee, since softflowd's flush delays and host speed both
move it. Steps keep going if one fails, so read the per-step output rather than trusting that
it finished. Logs: `/tmp/run_all.log`, and the
dashboard's at `/tmp/dashboard.log`.

> ⚠️ **`run_all.sh` deletes all existing rows** in the six telemetry tables when it starts
> (`fresh_db`). If you care about the current data, back it up first:
> ```bash
> cp db/telemetry.db /tmp/telemetry.db.bak
> ```

## 2. Open the dashboard

From Windows (any browser — don't open it inside WSL):

```
http://localhost:5000
```

WSL2 forwards `localhost` to Windows automatically. **Click a tab to see anything** — see
Known issue #1 below; the pane is hidden until you do.

What a good run looks like per tab: charts drawn, tables populated, and a badge reading
`live · N rows/60s` while that protocol's traffic is still flowing. Once the run has finished
the badges correctly fall back to `offline · last <time>` — that is not an error.

## 3. Run just one stage (when you're iterating)

Each stage is a self-contained Mininet script:

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"

sudo python3 mn/topology_int_demo.py    # INT only
sudo python3 mn/topology_ovs.py         # sFlow + NetFlow + IPFIX
sudo python3 mn/topology_snmp.py        # SNMP
bash scripts/wsl-tmp/e2e-gnmi.sh        # gNMI (local helper script)
python3 dashboard/app.py                # dashboard alone
```

Useful when the two long stages are already fine and you only care about one protocol.

## 4. Confirm data actually arrived

```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
python3 -c "
import sqlite3
c = sqlite3.connect('db/telemetry.db')
for t in ('int_hops','sflow_samples','netflow_flows','ipfix_flows','snmp_stats','gnmi_stats'):
    n, mx = c.execute('SELECT COUNT(*), MAX(ts) FROM '+t).fetchone()
    print('%-15s %-8d newest=%s' % (t, n, mx))
"
curl -s http://localhost:5000/api/status   # per-source live/rows_60s/last_ts as JSON
```

Note that `MAX(ts)` prints in **UTC** while dashboard badges use your local time
(UTC+5:30 here), so the two differ by 5.5 hours. A healthy run looks like this:

```
int_hops        352      newest=1789963823
sflow_samples   228923   newest=1789963894
netflow_flows   6        newest=1789963880
ipfix_flows     11       newest=1789963880
snmp_stats      3        newest=1789963938
gnmi_stats      180      newest=1789963989
```

> ⚠️ **`PASS` does not mean every stage was healthy.** `run_all.sh` only asserts that each
table has **more than 0** rows, so a stage that badly under-produced still passes. In the run
logged here, `snmp_stats` ended with just **3** rows, while `mn/topology_snmp.py`'s own check
requires **≥ 4** polls (`total >= 4 and mem_rows == total and bw_rows > 0`, line 183) — no
stage FAIL was printed. Read each stage's own summary, not just the final verdict.

## 5. Stop everything

```bash
# whichever applies
sudo pkill -f dashboard/app.py
sudo pkill -f 'topology_'
sudo pkill -f simple_switch
sudo mn -c                                  # clear Mininet veths
sudo ovs-vsctl --if-exists del-br s1
sudo pkill -f iperf3
```

`run_all.sh` does all of this itself at startup, so a crashed run can usually be fixed by
just running it again.

---

## Known issues

**1. The dashboard is blank until you click a tab.** This is a real bug in
`dashboard/templates/index.html`: `initTabs()` activates the tab but never the pane, and
`.pane { display: none }` — so on first load every pane is hidden. **Workaround:** click any
tab. **Fix** (documented in `RUN_LOG.md` §5.1): at the bottom of the script, replace
`refreshStatus(); refreshSource(activeTab);` with `switchTab(activeTab);`.

**2. The gNMI "Per-interface in-octets" chart never draws.** Also a real bug — the interface
name is parsed as `0]` and the filter then looks for `name=0]]`. See `RUN_LOG.md` §5.2 for
the one-character fix. The other gNMI chart works.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `mn: command not found`, `chdir(.../Network) failed` | you're in PowerShell/CMD/Git Bash, or the path's space split the command | run inside WSL; use the space-free `/tmp/nt` symlink (`ln -sfn "$PWD" /tmp/nt`) |
| Blank dashboard at `localhost:5000` | Known issue #1 — no pane activated | click a tab |
| All badges read `offline` | no traffic currently flowing; `LIVE_WINDOW_S` is 60 s | expected after a run finishes — re-run a stage to see `live` |
| Charts are empty boxes, Flask answers `200` | Chart.js is loaded from `cdn.jsdelivr.net` and you have no internet | give the machine internet, or vendor `chart.min.js` locally |
| NetFlow/IPFIX rows arrive late (10–60 s) | softflowd flush timeout | expected; wait, then refresh |
| Port 5000 already in use | an older dashboard is still running | `sudo pkill -f dashboard/app.py` |
| A stage prints FAIL but the run continues | `run_all.sh` deliberately continues on non-zero exit | read that stage's output; re-run the single stage (§3) |
| `snmp_stats` has fewer rows than expected | that stage's self-check wants ≥ 4 polls | re-run `sudo python3 mn/topology_snmp.py` alone and read its summary |
| P4 switches won't start | `p4/int.json` missing or a stale `simple_switch` is holding the thrift ports | recompile the P4 program; `sudo pkill -f simple_switch` |

Deeper troubleshooting (P4 build from source, BMv2 quirks, `softflowd` FIFO pipeline,
per-switch clock calibration) is in [`DOCUMENTATION.md`](DOCUMENTATION.md) §11–12 and
[`README.md`](README.md) "Known limitations".

---

## Where to go next

| I want to… | Read |
|---|---|
| understand what each protocol contributes and why | `README.md` → "Assignment mapping" |
| see the DB schema, field by field | `DOCUMENTATION.md` §4 |
| understand a stage's design and its debug scripts | `tasks/TASKS.md` and `tasks/01-*.md` … `12-*.md` |
| see the exact output of a verified run, and the two UI bugs | `RUN_LOG.md` |
| submit the written report | `report.md` / `synopsis.md` |
