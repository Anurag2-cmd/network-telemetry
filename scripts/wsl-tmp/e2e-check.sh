#!/bin/bash
# Check E2E DB state: row counts per telemetry table.
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJ" || exit 1
python3 - <<'PY'
import sqlite3
c = sqlite3.connect("db/telemetry.db")
for t in ("int_hops", "sflow_samples", "netflow_flows",
          "ipfix_flows", "snmp_stats", "gnmi_stats"):
    try:
        n = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    except Exception as e:
        n = "ERR: %s" % e
    print("%-14s %s" % (t, n))
c.close()
PY
