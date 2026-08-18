# Task 10: Unified dashboard — 6 protocol views (Flask + Chart.js + SQLite)

## Goal
One Flask app (served from WSL, browsable at `http://localhost:5000` from
Windows) with a tab per telemetry source: **INT / sFlow / NetFlow / IPFIX /
SNMP / gNMI**, each with live-updating charts and a recent-records table.
A separate `/api/<source>` endpoint per source; charts refresh every 2-5 s.

## Context
- A working Flask+Chart.js dashboard already exists on the Windows side
  (`C:\Users\ASUS\Desktop\Network telementry\app.py`, `templates/index.html`,
  collector.py) — reuse its styling/patterns; the new app lives at
  `/mnt/c/Users/ASUS/Desktop/Network telementry/dashboard/` inside WSL.
- All collectors (tasks 5-9) write to the SAME sqlite DB
  `db/telemetry.db` with tables: int_hops, sflow_samples, netflow_flows,
  ipfix_flows, snmp_stats, gnmi_stats.
- WSL2 localhost forwarding: Flask bound to 0.0.0.0:5000 in WSL is reachable
  from Windows at localhost:5000.

## Structure
```
dashboard/
  app.py            # Flask: / , /api/int, /api/sflow, /api/netflow,
                    #         /api/ipfix, /api/snmp, /api/gnmi, /api/status
  db.py             # (shared) get_conn(), query helpers, per-table last N rows
  templates/index.html   # tabs + charts (Chart.js from CDN) + live tables
```
- `/api/<source>` returns JSON: `{columns:[...], rows:[[...],...]}` (last 200 rows,
  oldest→newest) so the browser can chart time series.
- `/api/status` returns per-source: last row ts, row count in last 60 s
  (drives the green/red "live" badges per tab).

## Dashboard content per tab
- **INT**: chart "per-hop latency (µs)" with one line per switch_id; chart
  "queue occupancy (enq_qdepth)"; table of latest hop rows. Jitter from task 05.
- **sFlow**: chart "sampled traffic (bytes/s)", chart "bandwidth in/out (Mb/s)",
  table: agent, src→dst, proto, ports, bytes.
- **NetFlow**: chart "top flows by bytes" (table), chart flows/min; table with
  src→dst, proto, packets, bytes.
- **IPFIX**: same as NetFlow tab (own table).
- **SNMP**: charts cpu_load + mem_used_pct over time; chart bw in/out; table.
- **gNMI**: chart per path (interface counters in/out octets); table of latest
  values per path.

## Running
```bash
# in WSL, from the project dir:
python3 dashboard/app.py &
```
Access: Windows browser → `http://localhost:5000`.

## Verification (Definition of Done)
- All 6 tabs render data; every tab's "last update" badge is green while its
  collector runs and traffic is being generated.
- Charts visibly update every 5 s (no page reload).
- The dashboard survives collectors restarting (reads fail gracefully → show
  "no data yet").

## Troubleshooting
- Port 5000 busy (old Windows dashboard running): stop the old `python app.py`
  on Windows, or bind 5001 and open localhost:5001.
- Windows browser can't reach WSL Flask: verify inside WSL
  `curl http://localhost:5000/api/status`; if only Windows-side fails, check
  WSL localhostForwarding (default ON; `wsl --shutdown` fixes stale NAT).
- Chart.js CDN blocked: download chart.umd.js into dashboard/static/ and serve locally.

## On success
Update `tasks/TASKS.md` (task 10 DONE) → task 11.
