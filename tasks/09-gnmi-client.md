# Task 09: gNMI client (streaming model-driven telemetry)

## Goal
Show **gNMI** (gRPC Network Management Interface) as the modern streaming
protocol: a Python gNMI client uses `gnmi.Get` to pull OpenConfig-style state
(interface counters / queue state) from a BMv2 `simple_switch_grpc` instance,
polled every 2 s into `db/telemetry.db` table `gnmi_stats`.

## Context
- BMv2 built with `--with-pi` (task 02) → `simple_switch_grpc` available.
- pygnmi 0.8.15 installed (client + server support).
- gNMI = model-driven, push/pull over gRPC with OpenConfig data models —
  the natural successor to SNMP (this is the "streaming telemetry" story).

## Part 1 — gNMI-capable switch
Investigate first: `simple_switch_grpc --help` and the BMv2 docs
(`~/p4tools/behavioral-model/README.md` / `targets/simple_switch_grpc`) for
gNMI support (it ships an OpenConfig gNMI service; flags such as
`--gnmi-openconfig-dir` may exist). Possible outcomes:

- **A) BMv2 gNMI works**: start `simple_switch_grpc --grpc-server-addr 0.0.0.0:9559
  --cpu-port 64 [--gnmi-* flags] int.json`, then:
  - run `tools/gnmi_client.py` using pygnmi:
    ```python
    from pygnmi.client import gNMIclient
    with gNMIclient(target=("127.0.0.1", 9339), username="admin", password="admin", insecure=True) as c:
        resp = c.get(path=["/interfaces/interface/state/counters"])
    ```
  - poll every 2 s: store per-interface in-octets/out-octets + errors.

- **B) BMv2 gNMI not available in this build** (acceptable): demonstrate gNMI
  with pygnmi's own server:
  ```python
  from pygnmi.spec.simple_server import SimpleServer
  ```
  Implement a tiny gNMI server that mirrors the switch's JSON port state
  (from `simple_switch_CLI` counter output read each poll), and the same client
  code polls it. Document in README that the emulated agent implements gNMI.

## Storage
```sql
CREATE TABLE IF NOT EXISTS gnmi_stats (
    ts INTEGER, path TEXT, key TEXT, value TEXT, int_value INTEGER
);
```
(push data also arrives if we later implement Subscribe; Get/poll is enough.)

## Verification (Definition of Done)
- `gnmi_client.py` returns a GetResponse with interface counter values.
- `sqlite3 db/telemetry.db "SELECT * FROM gnmi_stats ORDER BY ts DESC LIMIT 10"`
  shows rows every 2 s; counters grow while traffic is injected
  (ping or iperf through the grpc switch).

## Troubleshooting
- gRPC port conflicts: use distinct ports (9559 P4Runtime, 9339 gNMI).
- pygnmi client errors on TLS: always `insecure=True` for the demo.
- If `SimpleServer` API differs in installed version, read its docstring
  (`python3 -c "import pygnmi.spec.simple_server as s; print(s.__doc__)"`).

## On success
Update `tasks/TASKS.md` (task 9 DONE) → task 10.
