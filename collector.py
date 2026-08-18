"""Telemetry collector: pings targets, reads local stats, stores in SQLite."""

import re
import sqlite3
import subprocess
import time

import psutil

INTERVAL = 5
DB_PATH = "telemetry.db"
TARGETS = {
    "gateway": "192.168.1.1",
    "dns": "8.8.8.8",
}


def ping(host):
    try:
        result = subprocess.run(
            ["ping", "-n", "1", host],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        match = re.search(r"time[=<](\d+)ms", result.stdout)
        if match:
            return float(match.group(1)), 0.0
        return None, 100.0
    except (subprocess.TimeoutExpired, OSError):
        return None, 100.0


def net_speed(prev):
    now = time.time()
    counters = psutil.net_io_counters()
    delta_time = now - prev[0]
    if delta_time <= 0 or prev[1] == 0:
        return 0.0, 0.0, (now, counters.bytes_sent, counters.bytes_recv)
    up = (counters.bytes_sent - prev[1]) / delta_time / 1048576
    down = (counters.bytes_recv - prev[2]) / delta_time / 1048576
    return up, down, (now, counters.bytes_sent, counters.bytes_recv)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS samples (
            ts INTEGER PRIMARY KEY,
            gw_latency REAL, gw_loss REAL,
            dns_latency REAL, dns_loss REAL,
            cpu REAL, mem REAL,
            net_up REAL, net_down REAL
        )
        """
    )
    conn.commit()
    return conn


def collect(conn, prev_counters):
    ts = int(time.time())
    gw_latency, gw_loss = ping(TARGETS["gateway"])
    dns_latency, dns_loss = ping(TARGETS["dns"])
    cpu = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory().percent
    up, down, prev_counters = net_speed(prev_counters)
    conn.execute(
        """
        INSERT INTO samples VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, gw_latency, gw_loss, dns_latency, dns_loss, cpu, mem, up, down),
    )
    conn.commit()
    conn.execute("DELETE FROM samples WHERE ts < ?", (ts - 86400,))
    conn.commit()
    return prev_counters


def main():
    conn = init_db()
    counters = (time.time(), 0, 0)
    print("Collector running. Press Ctrl+C to stop.")
    while True:
        try:
            counters = collect(conn, counters)
        except Exception as exc:
            print(f"Error: {exc}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
