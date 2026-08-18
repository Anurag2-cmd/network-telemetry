"""gNMI pull client (Task 9).

Polls a gNMI agent (tools/gnmi_agent.py) every POLL_SECS with pygnmi
(Get, insecure channel) and stores one row per leaf in
db/telemetry.db -> gnmi_stats:

    ts INTEGER, path TEXT, key TEXT, value TEXT, int_value INTEGER

The agent exposes OpenConfig-style interface counters for the P4 switch
(in-octets / out-octets / in-errors / out-errors / oper-status), so this
is the pull/streaming counterpart of the SNMP poller (task 08).

Usage:
  python3 tools/gnmi_client.py                        # poll every 2s forever
  python3 tools/gnmi_client.py --duration 60
  python3 tools/gnmi_client.py --target 127.0.0.1:9339
  python3 tools/gnmi_client.py --get-once             # one poll, print, exit
  python3 tools/gnmi_client.py --selftest             # path parsing, no agent
"""

import argparse
import json
import os
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, "db"))
from telemetry import cleanup_table, insert_rows  # noqa: E402

POLL_SECS = 2.0
USERNAME = "admin"
PASSWORD = "admin"

COUNTERS_PATH = "interfaces/interface[name=%s]/state/counters"
STATE_PATHS = [
    "interfaces/interface/state/name",
]


def build_rows(ts, updates, ifname=None):
    """Flatten one Get response into gnmi_stats rows.

    updates: list of dicts {"path": str, "val": ...} (pygnmi shape).
    A leaf (val not a dict) becomes one row; a container (dict) is
    expanded into one row per child leaf.
    """
    rows = []
    for upd in updates:
        path = upd.get("path")
        val = upd.get("val")
        if not path:
            continue
        if isinstance(val, dict):
            for key, value in val.items():
                rows.append(_row(ts, path, key, value))
        else:
            key = path.rsplit("/", 1)[-1]
            rows.append(_row(ts, path, key, val))
    return rows


def _row(ts, path, key, value):
    int_val = None
    if isinstance(value, int):
        int_val = value
    elif isinstance(value, str):
        try:
            int_val = int(value)
        except (TypeError, ValueError):
            int_val = None
    return dict(ts=ts, path=path, key=key, value=json.dumps(value),
                int_value=int_val)


def get_interfaces(client):
    """Query the list of interface names via the OpenConfig list path."""
    names = []
    try:
        resp = client.get(path=STATE_PATHS)
        for notification in resp.get("notification", []):
            for upd in notification.get("update", []):
                val = upd.get("val")
                if isinstance(val, list):
                    names += [str(v) for v in val]
                elif isinstance(val, str) and val != "None":
                    names.append(val)
    except Exception as exc:
        print("  get interfaces failed: %s" % exc, flush=True)
    seen, dedup = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            dedup.append(n)
    return dedup


def poll_once(args, client=None):
    """One poll cycle -> list of rows. Returns (rows, ifnames)."""
    from pygnmi.client import gNMIclient

    own = client is None
    if own:
        client = gNMIclient(target=(args.host, args.port),
                            username=USERNAME, password=PASSWORD,
                            insecure=True)
        client.__enter__()
    try:
        names = get_interfaces(client) or args.interfaces.split(",")
        names = [n for n in names if n.strip()]
        rows = []
        ts = int(time.time())
        for name in names:
            resp = client.get(path=[COUNTERS_PATH % name,
                                    "interfaces/interface[name=%s]/state/oper-status" % name])
            updates = []
            for notification in resp.get("notification", []):
                updates += notification.get("update", [])
            rows += build_rows(ts, updates, name)
        return rows, names
    finally:
        if own:
            client.__exit__(None, None, None)


def run_poller(args):
    from pygnmi.client import gNMIclient

    with gNMIclient(target=(args.host, args.port), username=USERNAME,
                    password=PASSWORD, insecure=True) as client:
        t0 = time.time()
        n = 0
        print("gNMI client: %s:%d every %ds (insecure)"
              % (args.host, args.port, args.interval))
        while args.duration == 0 or time.time() - t0 < args.duration:
            start = time.monotonic()
            try:
                rows, names = poll_once(args, client)
                insert_rows("gnmi_stats", rows)
                n += 1
                tops = [(r["key"], r["int_value"]) for r in rows[:4]]
                print("  [%d] %d rows, ifaces=%s, %s"
                      % (n, len(rows), names, tops), flush=True)
            except Exception as exc:
                print("  poll %d failed: %s" % (n + 1, exc), flush=True)
            time.sleep(max(0.5, args.interval - (time.monotonic() - start)))
        print("done: %d polls" % n)


def selftest():
    """build_rows/_row flattening without a live agent."""
    from telemetry import get_conn

    conn = get_conn()
    conn.execute("DELETE FROM gnmi_stats")
    conn.commit()
    conn.close()

    rows = build_rows(
        1700000000,
        [{"path": "interfaces/interface[name=0]/state/counters/in-octets",
          "val": 1234},
         {"path": "interfaces/interface[name=0]/state/counters",
          "val": {"in-octets": 10, "out-octets": 20}},
         {"path": "interfaces/interface[name=0]/state/oper-status",
          "val": "UP"}])
    assert len(rows) == 4, rows
    by_key = {r["key"]: r for r in rows}
    assert by_key["in-octets"]["int_value"] == 10
    assert by_key["out-octets"]["int_value"] == 20
    assert by_key["oper-status"]["value"] == '"UP"'
    assert by_key["oper-status"]["int_value"] is None
    insert_rows("gnmi_stats", rows)

    conn = get_conn()
    got = list(conn.execute(
        "SELECT key, int_value, value FROM gnmi_stats ORDER BY ts"))
    conn.close()
    assert len(got) == 4, got
    print("selftest OK: %s" % [tuple(r) for r in got[:2]])


def main():
    ap = argparse.ArgumentParser(description="gNMI pull client")
    ap.add_argument("--target", default="127.0.0.1:9339",
                    help="agent address host:port")
    ap.add_argument("--interval", type=float, default=POLL_SECS,
                    help="poll interval in seconds")
    ap.add_argument("--duration", type=float, default=0.0,
                    help="run for N seconds (0 = forever)")
    ap.add_argument("--get-once", action="store_true",
                    help="single poll, print, exit")
    ap.add_argument("--interfaces", default="0,1",
                    help="fallback interface names if the list path is empty")
    ap.add_argument("--selftest", action="store_true",
                    help="row flattening + DB check, no agent")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    host, _, port = args.target.partition(":")
    args.host = host
    args.port = int(port or 9339)

    if args.get_once:
        rows, names = poll_once(args)
        print("ifaces=%s" % names)
        for r in rows:
            print("  %s = %s" % (r["path"], r["value"]))
        insert_rows("gnmi_stats", rows)
        return

    cleanup_table("gnmi_stats")
    run_poller(args)
    cleanup_table("gnmi_stats")


if __name__ == "__main__":
    main()
