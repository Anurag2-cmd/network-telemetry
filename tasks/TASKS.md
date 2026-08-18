# Network Telemetry — Task Index

Assignment: monitor an emulated network with 6 telemetry protocols
(SNMP, NetFlow, sFlow, IPFIX, gNMI, INT) on Mininet + P4 + Python,
visualized on a real-time Flask dashboard.

## Environment facts (READ FIRST)

- Host: Windows 11. WSL2 distro **Ubuntu 26.04**, user `anurag`, passwordless sudo ENABLED.
- From PowerShell, run Linux commands with:
  `wsl -d Ubuntu -- bash -c "command"` (or `wsl -d Ubuntu -- bash /path/script.sh`)
- Long-running jobs: the AI shell tool **kills foreground processes on timeout/disconnect**.
  ALWAYS run long builds inside tmux:
  `wsl -d Ubuntu -- bash -c "tmux new-session -d -s NAME 'cmd 2>&1 | tee /tmp/name.log'"`
  then poll: `wsl -d Ubuntu -- bash -c "tail -5 /tmp/name.log; tmux ls"`
- WSL paths for this project (note the space in the folder name):
  `/mnt/c/Users/ASUS/Desktop/Network telementry`
- Build tools live in `~/p4tools/` (Linux home, fast disk).
  Source code (P4, Python, tasks) lives in the Windows project folder above.
- Dashboard runs inside WSL; Windows browser reaches it at `http://localhost:5000`
  (WSL2 localhost forwarding works automatically).
- `~/p4tools/p4c` and `~/p4tools/behavioral-model` are already cloned.

## Current status (as of session 2026-08-02)

| # | Task | Status |
|---|------|--------|
| 1 | Finish p4c build + install | DONE (p4c 1.2.5.15, p4c-bm2-ss on PATH) |
| 2 | Build BMv2 (behavioral-model) | DONE (BMv2 1.15.4, simple_switch/grpc/CLI + --grpc-server-addr) |
| 3 | P4 INT program | DONE (compile + sanity test; 12B stack entry) |
| 4 | Mininet topology | DONE (h1-s1-s2-h2+h3, pingAll 6/6, INT 2-hop: switch_id 1→2) |
| 5 | INT parser + collector | DONE (int_receiver.py: offset-calibrated latency, jitter, qdepth spike 63 via set_queue_rate; sender loop + --burst) |
| 6 | sFlow collector | DONE (OVS → sFlow v5 → collector → sflow_samples; full run: 172k rows, 167k h1→h2 TCP flows, bw rows OK; selftest passes) |
| 7 | NetFlow v5 + IPFIX collectors | DONE (softflowd in h1 (v5→h4:9995) + h3 (v10→h4:9996) via tcpdump-FIFO pipeline, collectors on h4, netflow_flows/ipfix_flows verified in e2e; selftests pass) |
| 8 | SNMP poller | DONE (snmpd in h4 with minimal -C config, OVS internal port 10.0.1.254 gives root netns access; snmp_poller.py polls 10.0.1.4:161 every 5s → snmp_stats; e2e: 10 rows, bw up to 2.4 Gb/s during iperf, snmpget OK; selftest passes) |
| 9 | gNMI client | DONE (outcome B: pygnmi-based gnmi_agent.py emulates the gNMI service over the BMv2 P4Runtime state — port_counters_in/out counters added to int.p4, read via simple_switch_CLI every 1s; gnmi_client.py polls every 2s → gnmi_stats. E2E on simple_switch_grpc (thrift 9090, grpc 9559): 9 polls, in-octets 0→1694, out-octets 1984→3440, oper-status UP, bidirectional traffic (iface 1 in-octets 1176); selftests pass) |
| 10 | Dashboard integration (6 protocol views) | DONE (dashboard/ app.py + db.py + templates/index.html; tabs INT/sFlow/NetFlow/IPFIX/SNMP/gNMI, /api/<source> last-200 rows, /api/status live badges (60s window); verified: all 6 endpoints return data, gnmi badge flips green while collector runs, JS syntax OK (node --check), Chart.js CDN reachable, Windows browser OK at localhost:5000, graceful "no data yet" when collectors down) |
| 11 | End-to-end test + README | DONE (run_all.sh: INT demo + OVS sFlow/NetFlow/IPFIX + SNMP + gNMI + dashboard, all sequential; E2E run landed int_hops=460, sflow_samples=375k, netflow_flows=6, ipfix_flows=11, snmp_stats=10, gnmi_stats=540; dashboard HTTP 200 from Windows at localhost:5000, all 6 sources present; README.md written) |
| 12 | Written report (assignment objectives) | DONE (report.md in English: 4 objectives — definition/role, telemetry vs SNMP pull monitoring with the enq_qdepth 43-45 burst evidence, 4-generation evolution mapped to the 6 built protocols, architecture + components table; extra: 6-protocol comparison, limitations/lessons, real numbers from task-11 E2E & task runs; README links to report.md) |

## Order & dependencies

- 1 → 2 strictly in order (p4c first; BMv2 needs nothing from p4c but both are big builds).
- 3 needs 1 (compile with p4c). 4 needs 2 (simple_switch binary).
- 5 needs 3+4 running.
- 6, 7, 8 are independent of 3-5 (they use Open vSwitch / host tools) — can run in parallel
  if given separate files, but the dashboard (10) needs all collectors defined.
- 9 needs 2 (simple_switch_grpc binary).
- 10 needs 5-9 (DB tables + collectors). 11 needs everything. 12 is writing only.

## Parallel execution plan (3-4 sessions max)

Rules:
1. **One session owns the WSL runtime at a time** (Mininet, test runs, port
   binding). Only builds inside tmux are safe to coexist — they're detached.
2. **Each session owns its own files** (no two sessions edit the same file).
   `db/telemetry.py` (shared DB helper) is owned by Session 1 — others only import it.
3. Session 11 (E2E) runs last, alone, after every other session reports DONE.
4. All sessions must update THIS status table when done.

Suggested split:

| Session | Tasks | Notes |
|---------|-------|-------|
| 1 (infrastructure) | 1 → 2 → 3 → 4 | Sequential; owns WSL builds + Mininet. Start FIRST. Also owns `db/telemetry.py` (create after task 5 file read). |
| 2 (INT analytics) | 5 | Parallel: write `tools/int_receiver.py` (no WSL runtime needed until session 1 has topology up). |
| 3 (OVS protocols) | 6, 7, 8 | Parallel: write `sflow_collector.py`, `netflow_collector.py`, `ipfix_collector.py`, `snmp_poller.py` — all file-writing only. |
| 4 (frontend + report) | 10, 12 | Parallel: dashboard uses the schemas already defined in task files 5-9; draft report structure. |
| 5 (gNMI) | 9 | Start after session 1 finishes task 2 (needs simple_switch_grpc binary). |
| 6 (integration) | 11 | Last, alone. |

Adjustment tip: if two sessions both hit the WSL at the same moment (e.g.,
`sudo apt install`), dpkg locks will block one — just retry the command.

## How to use this index with an AI

Give the AI session: this file + the specific `tasks/NN-*.md` file it should execute.
Each task file is self-contained: goal, context, exact steps, verification, troubleshooting.
Have the AI update the Status column of this table when a task is done.
