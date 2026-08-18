#!/bin/bash
# Task 11 E2E: one command brings up the full telemetry stack and proves
# every protocol produces live data.
#
#   From the WSL shell in the project dir:   sudo bash run_all.sh
#
# Sequence:
#   1. INT        (mn/topology_int_demo.py: P4 switches + receiver/sender -> int_hops)
#   2. sFlow      (mn/topology_ovs.py: OVS sFlow -> sflow_samples)
#   3. NetFlow    (same OVS run: softflowd v5 on h1 -> netflow_flows)
#   4. IPFIX      (same OVS run: softflowd v10 on h3 -> ipfix_flows)
#   5. SNMP       (mn/topology_snmp.py: snmpd on h4 + poller -> snmp_stats)
#   6. gNMI       (scripts/wsl-tmp/e2e-gnmi.sh: agent+client over P4Runtime counters -> gnmi_stats)
#   7. Dashboard  (dashboard/app.py, kept alive at http://localhost:5000)
#   8. Assertion  every table has > 0 rows
#
# Log /tmp/run_all.log; dashboard log /tmp/dashboard.log.

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJ"
export PYTHONPATH="$PROJ/db"

log() { echo; echo "### $*"; }

run_step() {
    # $1 = label, $2 = proc name to count rows for, $3 = command line
    log "$1"
    eval "$3"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ]; then
        echo "  -> (step returned nonzero; continuing)"
    fi
}

count() { # $1 table
    python3 -c "
import sqlite3, sys
c = sqlite3.connect('$PROJ/db/telemetry.db')
n = c.execute('SELECT COUNT(*) FROM $1').fetchone()[0]
c.close()
print('%s=%d' % ('$1', n))
sys.exit(0 if n > 0 else 1)"
}

cleanup() {
    log "cleanup stale state"
    sudo mn -c >/dev/null 2>&1 || true
    ovs-vsctl --if-exists del-br s1 >/dev/null 2>&1 || true
    pkill -f sflow_collector 2>/dev/null || true
    pkill -f netflow_collector 2>/dev/null || true
    pkill -f ipfix_collector 2>/dev/null || true
    pkill -f snmp_poller 2>/dev/null || true
    pkill -f 'gnmi_agen[t]' 2>/dev/null || true
    pkill -f 'gnmi_clien[t]' 2>/dev/null || true
    pkill -f 'dashboard/app.py' 2>/dev/null || true
    pkill -f 'simple_switch' 2>/dev/null || true
    pkill -f iperf3 2>/dev/null || true
    ip netns del ns-a 2>/dev/null || true
    ip netns del ns-b 2>/dev/null || true
    sleep 3
    ln -sfn "$PROJ" /tmp/nt
}

fresh_db() {
    log "reset db/telemetry.db (schema exists, tables cleared)"
    python3 - <<'PY'
from telemetry import get_conn
conn = get_conn()
for t in ("int_hops", "sflow_samples", "netflow_flows",
          "ipfix_flows", "snmp_stats", "gnmi_stats"):
    conn.execute("DELETE FROM %s" % t)
conn.commit()
conn.close()
PY
}

echo "================ TELEMETRY E2E $(date -Is) ================"

cleanup
fresh_db

run_step "1/7 INT (2 P4 switches, receiver on h2, sender burst/steady)" \
    int_hops \
    "sudo timeout 300 python3 mn/topology_int_demo.py; count int_hops"

run_step "2/7 OVS sFlow + NetFlow + IPFIX (softflowd exporting h1->h4, h3->h4)" \
    sflow_samples \
    "sudo timeout 300 python3 mn/topology_ovs.py; count sflow_samples; count netflow_flows; count ipfix_flows"

run_step "3/7 SNMP (snmpd on h4, poller from root netns)" \
    snmp_stats \
    "sudo timeout 300 python3 mn/topology_snmp.py; count snmp_stats"

run_step "4/7 gNMI (pygnmi agent over P4Runtime counters, pull client)" \
    gnmi_stats \
    "bash scripts/wsl-tmp/e2e-gnmi.sh; count gnmi_stats"

log "5/7 dashboard (kept running on 0.0.0.0:5000)"
pkill -f 'dashboard/app.py' 2>/dev/null || true
sleep 1
setsid nohup python3 dashboard/app.py > /tmp/dashboard.log 2>&1 < /dev/null &
sleep 4
if curl -sf http://localhost:5000/api/status > /tmp/dash-status.json; then
    echo "dashboard reachable; /api/status OK"
else
    echo "FAIL: dashboard not reachable"; tail -5 /tmp/dashboard.log
fi

log "6/7 final DB assertion"
python3 - <<'PY'
import sqlite3, sys
conn = sqlite3.connect("db/telemetry.db")
counts = {}
for t in ("int_hops", "sflow_samples", "netflow_flows",
          "ipfix_flows", "snmp_stats", "gnmi_stats"):
    counts[t] = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
conn.close()
for t, n in counts.items():
    print("  %-14s %d" % (t, n))
ok = all(n > 0 for n in counts.values())
print("ALL 6 TABLES NON-EMPTY:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
PY

log "7/7 done. Dashboard: http://localhost:5000"