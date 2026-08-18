"""Shared SQLite helpers for all telemetry collectors.

Database lives at db/telemetry.db (WAL mode, 30s busy timeout).
Collectors write; the dashboard only reads. Old rows (> 24h) are
cleaned up by each collector on startup and periodically.
"""

import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telemetry.db")

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS int_hops (
        ts INTEGER,
        flow TEXT,
        hop_idx INTEGER,
        switch_id INTEGER,
        ingress_ts INTEGER,
        hop_latency_us REAL,
        jitter_us REAL,
        queue_occupancy INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sflow_samples (
        ts INTEGER, agent TEXT, src_ip TEXT, dst_ip TEXT, src_port INTEGER,
        dst_port INTEGER, proto INTEGER, bytes_sampled INTEGER,
        in_port INTEGER, out_port INTEGER, if_in_octets INTEGER,
        if_out_octets INTEGER, bandwidth_in_mbps REAL, bandwidth_out_mbps REAL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS netflow_flows (
        ts INTEGER, src_ip TEXT, dst_ip TEXT, src_port INTEGER,
        dst_port INTEGER, proto INTEGER, tcp_flags INTEGER, packets INTEGER,
        bytes INTEGER, first_ts INTEGER, last_ts INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ipfix_flows (
        ts INTEGER, src_ip TEXT, dst_ip TEXT, src_port INTEGER,
        dst_port INTEGER, proto INTEGER, packets INTEGER, bytes INTEGER,
        first_ts INTEGER, last_ts INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS snmp_stats (
        ts INTEGER, device TEXT, cpu_load REAL, mem_used_pct REAL,
        if_octets_in INTEGER, if_octets_out INTEGER,
        bw_in_mbps REAL, bw_out_mbps REAL, uptime INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS gnmi_stats (
        ts INTEGER, path TEXT, key TEXT, value TEXT, int_value INTEGER
    );
    """,
]


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def insert_row(table, row):
    if not row:
        return
    cols = list(row.keys())
    qs = ",".join("?" * len(cols))
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(cols), qs)
    conn = get_conn()
    try:
        conn.execute(sql, list(row.values()))
        conn.commit()
    finally:
        conn.close()


def insert_rows(table, rows):
    if not rows:
        return
    cols = list(rows[0].keys())
    qs = ",".join("?" * len(cols))
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(cols), qs)
    conn = get_conn()
    try:
        conn.executemany(sql, [list(r.values()) for r in rows])
        conn.commit()
    finally:
        conn.close()


def cleanup_table(table, max_age_s=86400):
    cutoff = int(time.time() - max_age_s)
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM %s WHERE ts < ?" % table, (cutoff,))
        if cur.rowcount:
            conn.commit()
    finally:
        conn.close()


def cleanup_old_rows(max_age_s=86400, interval_s=600):
    for table in ("int_hops", "sflow_samples", "netflow_flows", "ipfix_flows",
                  "snmp_stats", "gnmi_stats"):
        cleanup_table(table, max_age_s)
