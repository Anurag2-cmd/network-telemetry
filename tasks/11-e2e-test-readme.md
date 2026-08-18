# Task 11: End-to-end test + README

## Goal
One command brings up the FULL stack and every protocol produces live data;
a `README.md` documents architecture, how to run, and what each protocol demo shows.

## One-command runner `run_all.sh` (WSL, run with sudo)
Starts, in order, with cleanup + staggered starts (each needs a few seconds):
1. `sudo mn -c` (clean stale mininet state), stop any old collectors/dashboard.
2. **INT demo** (task 03-05): `sudo python3 mn/topology_int.py &`
   → wait for pings to pass → start `tools/int_receiver.py` on h2 →
   start `tools/int_sender.py` burst+steady on h1.
3. **OVS + sFlow + NetFlow/IPFIX + SNMP** (tasks 06-08): second topology
   `mn/topology_ovs.py` can share the same process run: write a single combined
   topology script `mn/topology_all.py` (4 OVS hosts + OVS switch s1, PLUS the 2
   P4 switches s2/s3 with h1,h2 for INT — or run the two demos as two separate
   Mininet invocations and keep both alive; whichever is simpler to make stable).
   - enable OVS sflow → start `tools/sflow_collector.py` (WSL host)
   - start softflowd v5 (h1) + v10 (h3), collectors `netflow_collector.py`,
     `ipfix_collector.py` on h4
   - start snmpd on h4, `tools/snmp_poller.py` (WSL host)
   - start iperf3 server h2 / client h1 (background, 5 min)
4. **gNMI** (task 09): start simple_switch_grpc + `tools/gnmi_client.py`.
5. **Dashboard** (task 10): `python3 dashboard/app.py &`
6. Wait 60 s, then assert:
   ```bash
   sqlite3 db/telemetry.db "SELECT 'int',count(*) FROM int_hops
     UNION ALL SELECT 'sflow',count(*) FROM sflow_samples
     UNION ALL SELECT 'netflow',count(*) FROM netflow_flows
     UNION ALL SELECT 'ipfix',count(*) FROM ipfix_flows
     UNION ALL SELECT 'snmp',count(*) FROM snmp_stats
     UNION ALL SELECT 'gnmi',count(*) FROM gnmi_stats"
   ```
   every table > 0.

## README.md content (project root, Windows folder)
- Title + assignment mapping (objectives → what each part of the project proves)
- Architecture diagram (ASCII): hosts/switches; INT path; OVS sFlow path;
  softflowd NetFlow/IPFIX path; SNMP polling path; gNMI path; all → SQLite → Flask
- How to run (the exact 3-4 commands), prerequisites (WSL, tasks 01-02 builds)
- Per-protocol "what to watch" (e.g., burst → queue occupancy spike on INT tab)
- File map: p4/, mn/, tools/, dashboard/, db/
- Known limitations (bmv2 timestamps per-switch, sampling rates, emulation)

## Verification (Definition of Done)
- `./run_all.sh` completes with all 6 tables > 0 rows and dashboard reachable
  at localhost:5000 from Windows.
- README exists and a stranger could run the project following it.

## On success
Update `tasks/TASKS.md` (task 11 DONE) → task 12.
