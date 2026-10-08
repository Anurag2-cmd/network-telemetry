"""Shared DB helpers for the telemetry dashboard (task 10).

Reaches the collectors' shared database at PROJECT/db/telemetry.db and
exposes last-N-row queries + per-source liveness status. Every query is
guarded so a missing table or a dead collectors process never crashes the
dashboard — it just reports "no data".
"""

import os
import sqlite3
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT, "db", "telemetry.db")

SOURCES = {
    "int": "int_hops",
    "sflow": "sflow_samples",
    "netflow": "netflow_flows",
    "ipfix": "ipfix_flows",
    "snmp": "snmp_stats",
    "gnmi": "gnmi_stats",
}

LIVE_WINDOW_S = int(os.environ.get("LIVE_WINDOW_S", "86400"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone() is not None


def last_rows(table, n=200):
    """{columns, rows} of the last n rows, oldest->newest. Empty on error."""
    try:
        conn = get_conn()
        if not table_exists(conn, table):
            return {"columns": [], "rows": []}
        columns = [c[1] for c in conn.execute("PRAGMA table_info(%s)" % table)]
        # expose rowid as __rid: newer SQLite (3.50+) rejects rowid in the
        # outer ORDER BY of an unaliased subquery (older versions allowed it)
        rows = conn.execute(
            "SELECT * FROM (SELECT *, rowid AS __rid FROM %s "
            "ORDER BY ts DESC, rowid DESC LIMIT ?) "
            "ORDER BY ts ASC, __rid ASC" % table, (n,)).fetchall()
        conn.close()
        return {"columns": columns, "rows": [list(r) for r in rows]}
    except Exception:
        return {"columns": [], "rows": []}


def status():
    """Per-source {live, rows_60s, last_ts}. 'live' = a row arrived recently."""
    now = int(time.time())
    out = {}
    try:
        conn = get_conn()
        for name, table in SOURCES.items():
            if not table_exists(conn, table):
                out[name] = {"live": False, "rows_60s": 0,
                             "last_ts": None, "error": "no table"}
                continue
            last = conn.execute("SELECT MAX(ts) FROM %s" % table).fetchone()[0]
            n = conn.execute(
                "SELECT COUNT(*) FROM %s WHERE ts >= ?" % table,
                (now - LIVE_WINDOW_S,)).fetchone()[0]
            out[name] = {
                "live": last is not None and (now - last) <= LIVE_WINDOW_S,
                "rows_60s": n,
                "last_ts": last,
            }
        conn.close()
    except Exception as exc:
        for name in SOURCES:
            out[name] = {"live": False, "rows_60s": 0,
                         "last_ts": None, "error": str(exc)}
    return out