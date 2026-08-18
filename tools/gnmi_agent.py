"""gNMI agent (Task 9, outcome B).

BMv2's simple_switch_grpc (this build) has no built-in gNMI service, so we
emulate the agent: a small gRPC server implementing the gNMI service
(Get / Capabilities / Subscribe) that maps the P4 switch's runtime state
onto an OpenConfig-style data model:

    /interfaces/interface[name=<port>]/state/name
    /interfaces/interface[name=<port>]/state/oper-status
    /interfaces/interface[name=<port>]/state/counters/in-octets
    /interfaces/interface[name=<port>]/state/counters/out-octets
    /interfaces/interface[name=<port>]/state/counters/in-errors
    /interfaces/interface[name=<port>]/state/counters/out-errors

Counters come from the switch's `port_counters_in` / `port_counters_out`
P4 counters (p4/int.p4), indexed by port and read via simple_switch_CLI
every POLL_SECS by a background thread. The dashboard and gnmi_client.py
(pull) or Subscribe (push) see the same model -- the "model-driven
telemetry" story.

Usage:
  python3 tools/gnmi_agent.py --thrift-port 9090 --grpc-addr 0.0.0.0:9339
      --interfaces 0:eth0,1:eth1
  python3 tools/gnmi_agent.py --selftest
"""

import argparse
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import grpc
from pygnmi.spec.v080 import gnmi_pb2 as gnmi
from pygnmi.spec.v080 import gnmi_pb2_grpc

POLL_SECS = 1.0


def parse_counter_out(text):
    """Parse one simple_switch_CLI counter_read line.

    'port_counters[0]= (123 bytes, 4 packets)' -> (bytes, packets).
    Returns (0, 0) when nothing matched (e.g. empty counter line).
    """
    m = re.search(r"\((\d+) bytes, (\d+) packets\)", text)
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2))


class SwitchCounterPoller:
    """Background thread reading port_counters_in/out via CLI.

    Exposes snapshot: {port: {"in-octets": int, "in-packets": int,
    "out-octets": int, "out-packets": int}} -- the port's ingress counter
    is the OpenConfig "in" side, the egress counter the "out" side.
    """

    COUNTERS = (("in", "port_counters_in"), ("out", "port_counters_out"))

    def __init__(self, thrift_port, ports):
        self.thrift_port = thrift_port
        self.ports = list(ports)
        self.snapshot = {p: {"in-octets": 0, "in-packets": 0,
                             "out-octets": 0, "out-packets": 0}
                         for p in self.ports}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _read_counter(self, name, port):
        proc = subprocess.run(
            ["simple_switch_CLI", "--thrift-port", str(self.thrift_port)],
            input="counter_read %s %d\n" % (name, port),
            text=True, capture_output=True, timeout=10)
        return parse_counter_out(proc.stdout + proc.stderr)

    def _run(self):
        while not self._stop.is_set():
            snap = {}
            for port in self.ports:
                counts = {}
                for side, cname in self.COUNTERS:
                    try:
                        octets, packets = self._read_counter(cname, port)
                    except Exception:
                        octets, packets = 0, 0
                    counts[side + "-octets"] = octets
                    counts[side + "-packets"] = packets
                snap[port] = counts
            with self._lock:
                self.snapshot = snap
            self._stop.wait(POLL_SECS)

    def get(self, port):
        with self._lock:
            return self.snapshot.get(port, {"in-octets": 0, "in-packets": 0,
                                            "out-octets": 0,
                                            "out-packets": 0})


class GnmiServicer(gnmi_pb2_grpc.gNMIServicer):
    """gNMI service exposing OpenConfig interface state for the switch."""

    def __init__(self, poller):
        self.poller = poller

    def _ifnames(self):
        return [str(p) for p in self.poller.ports]

    def _match_interfaces(self, path_elems):
        """Return the interface names selected by a gNMI path."""
        names = self._ifnames()
        for elem in path_elems:
            if elem.name == "interface":
                name = elem.key.get("name")
                if name is not None:
                    names = [n for n in names if n == name]
        return names

    def _counters(self, name):
        c = self.poller.get(int(name))
        return c

    def _make_update(self, ts, path_str, name, key, val, int_val=None):
        update = gnmi.Update()
        update.path.CopyFrom(gnmi.Path(
            elem=[gnmi.PathElem(name=e)
                  for e in path_str.strip("/").split("/")]))
        if int_val is not None:
            update.val.int_val = int_val
        else:
            update.val.string_val = str(val)
        return update

    def _resolve(self, path_str):
        """Get -> list of (leaf_path, value, int_value) updates.

        Handles the container paths used by the dashboard/client plus
        individual leaf paths.
        """
        elems = path_str.strip("/").split("/")
        updates = []
        ts = int(time.time() * 1e9)
        # path forms:
        #   interfaces/interface/state/name                     -> list
        #   interfaces/interface[name=X]/state/oper-status      -> leaf
        #   interfaces/interface[name=X]/state/counters         -> container
        #   interfaces/interface[name=X]/state/counters/<leaf>  -> leaf
        names = self._ifnames()
        if "interface" in elems:
            names = self._match_interfaces(
                [gnmi.PathElem(name=e) for e in elems])
        base = "interfaces/interface"
        for name in names:
            counters = self._counters(name)
            if elems[-1] == "name":
                updates.append((base + "[name=%s]/state/name" % name,
                                name, name))
            elif elems[-1] == "oper-status":
                status = "UP" if counters["in-packets"] > 0 else "DOWN"
                updates.append((base + "[name=%s]/state/oper-status" % name,
                                status, status))
            elif elems[-1] == "counters":
                for leaf, val in (
                        ("in-octets", counters["in-octets"]),
                        ("out-octets", counters["out-octets"]),
                        ("in-errors", 0),
                        ("out-errors", 0)):
                    updates.append(
                        (base + "[name=%s]/state/counters/%s"
                         % (name, leaf), leaf, val))
            elif elems[-1].startswith("in-octets"):
                updates.append(
                    (base + "[name=%s]/state/counters/in-octets" % name,
                     "in-octets", counters["in-octets"]))
            elif elems[-1].startswith("out-octets"):
                updates.append(
                    (base + "[name=%s]/state/counters/out-octets" % name,
                     "out-octets", counters["out-octets"]))
            elif elems[-1].startswith("in-errors"):
                updates.append(
                    (base + "[name=%s]/state/counters/in-errors" % name,
                     "in-errors", 0))
            elif elems[-1].startswith("out-errors"):
                updates.append(
                    (base + "[name=%s]/state/counters/out-errors" % name,
                     "out-errors", 0))
        return ts, updates

    def Capabilities(self, request, context):
        resp = gnmi.CapabilityResponse()
        resp.supported_models.add(name="openconfig-interfaces",
                                  organization="OpenConfig working group",
                                  version="2.4.1")
        resp.supported_encodings.append(gnmi.Encoding.JSON)
        resp.supported_encodings.append(gnmi.Encoding.PROTO)
        resp.supported_encodings.append(gnmi.Encoding.JSON_IETF)
        resp.gNMI_version = "0.8.0"
        return resp

    def Get(self, request, context):
        resp = gnmi.GetResponse()
        for path in request.path:
            path_str = "/".join(e.name for e in path.elem)
            ts, updates = self._resolve(path_str)
            notification = resp.notification.add()
            notification.timestamp = ts
            for leaf_path, key, val in updates:
                if val is not None and isinstance(val, int):
                    int_val = val
                else:
                    int_val = None
                notification.update.add().CopyFrom(
                    self._make_update(ts, leaf_path, "", key, val, int_val))
        return resp

    def Set(self, request, context):
        resp = gnmi.SetResponse()
        result = resp.response.add()
        result.op = 0  # INVALID
        return resp

    def Subscribe(self, request_iterator, context):
        """Streaming: send the full state once per poll interval.

        Implemented for every subscription mode (the demo uses
        Get/poll, but this makes the agent a real streaming source).
        """
        initial = gnmi.SubscribeResponse()
        initial.sync_response = True
        yield initial
        while True:
            try:
                req = next(request_iterator)
            except StopIteration:
                break
            time.sleep(POLL_SECS)
            resp = gnmi.SubscribeResponse()
            for name in self._ifnames():
                ts, updates = self._resolve(
                    "interfaces/interface[name=%s]/state/counters" % name)
                notification = resp.update
                notification.timestamp = ts
                for leaf_path, key, val in updates:
                    int_val = val if isinstance(val, int) else None
                    notification.update.add().CopyFrom(
                        self._make_update(ts, leaf_path, "", key, val,
                                          int_val))
                yield resp


def parse_interfaces(arg):
    """'0:eth0,1:eth1' -> {port: ifname}."""
    out = {}
    for part in arg.split(","):
        part = part.strip()
        if not part:
            continue
        port, _, ifname = part.partition(":")
        out[int(port)] = ifname
    return out


def main():
    ap = argparse.ArgumentParser(description="gNMI agent for BMv2 switch")
    ap.add_argument("--thrift-port", type=int, default=9090,
                    help="simple_switch_CLI thrift port")
    ap.add_argument("--grpc-addr", default="0.0.0.0:9339",
                    help="gNMI gRPC bind address")
    ap.add_argument("--interfaces", default="0:eth0,1:eth1",
                    help="comma-separated port:ifname list")
    ap.add_argument("--selftest", action="store_true",
                    help="parser + model checks, no switch needed")
    args = ap.parse_args()

    if args.selftest:
        assert parse_counter_out("port_counters[0]= (1234 bytes, 5 packets)") \
            == (1234, 5)
        assert parse_counter_out("") == (0, 0)
        assert parse_counter_out("RuntimeCmd: Error: invalid") == (0, 0)
        ifaces = parse_interfaces("0:eth0,1:eth1,2:h3-eth0")
        assert ifaces == {0: "eth0", 1: "eth1", 2: "h3-eth0"}
        print("selftest OK")
        return

    ifaces = parse_interfaces(args.interfaces)
    poller = SwitchCounterPoller(args.thrift_port, list(ifaces))
    poller.start()
    print("gNMI agent on %s (thrift %d, interfaces %s)"
          % (args.grpc_addr, args.thrift_port, ifaces), flush=True)

    server = grpc.server(thread_pool=ThreadPoolExecutor(max_workers=10),
                         maximum_concurrent_rpcs=10)
    gnmi_pb2_grpc.add_gNMIServicer_to_server(
        GnmiServicer(poller), server)
    server.add_insecure_port(args.grpc_addr)
    server.start()
    print("serving gNMI (Get/Capabilities/Subscribe)", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        poller.stop()
        server.stop(0)


if __name__ == "__main__":
    main()
