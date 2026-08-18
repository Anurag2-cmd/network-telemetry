#!/usr/bin/env python3
"""Task 04: Mininet topology with 2 P4 switches (INT path).

Topology: h1 -- s1 -- s2 -- h2, plus s2 -- h3.
s1/s2 run simple_switch (BMv2) with p4/int.json; INT UDP/4000 packets get one
metadata stack entry per switch (switch_id 1, then 2).

Run as root in WSL:
    cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
    sudo python3 mn/topology_int.py
"""
import os
import struct
import subprocess
import time

from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import Host, Switch
from mininet.topo import Topo
from mininet.util import waitListening

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P4_JSON = os.path.join(PROJECT, "p4", "int.json")
INT_SENDER = os.path.join(PROJECT, "tools", "int_sender.py")


class P4Switch(Switch):
    """BMv2 simple_switch running as a Mininet switch (no controller)."""

    def __init__(self, name, thrift_port=9090, device_id=1, **opts):
        Switch.__init__(self, name, **opts)
        self.thrift_port = thrift_port
        self.device_id = device_id
        self.log_file = "/tmp/%s.log" % name

    def start(self, controllers):
        info("*** starting %s (thrift %d)\n" % (self.name, self.thrift_port))
        args = [
            "simple_switch", "--device-id", str(self.device_id),
            "--log-console", "--thrift-port", str(self.thrift_port),
        ]
        for port in sorted(self.intfs):
            intf = self.intfs[port]
            self.cmd("ip link set", intf.name, "up")
            args += ["--interface", "%d@%s" % (port, intf.name)]
        args += ['"%s"' % P4_JSON]
        self.cmd(" ".join(args) + " > /tmp/%s.out 2>&1 &" % self.name)
        waitListening(port=self.thrift_port, timeout=30)

    def stop(self):
        self.cmd('pkill -f "simple_switch.*--thrift-port %d"' % self.thrift_port)


class IntTopo(Topo):
    def build(self):
        h1 = self.addHost("h1", ip="10.0.1.1/24")
        h2 = self.addHost("h2", ip="10.0.1.2/24")
        h3 = self.addHost("h3", ip="10.0.1.3/24")
        s1 = self.addSwitch("s1", thrift_port=9090, device_id=1)
        s2 = self.addSwitch("s2", thrift_port=9091, device_id=2)
        self.addLink(h1, s1, port1=0, port2=0)
        self.addLink(s1, s2, port1=1, port2=0)
        self.addLink(s2, h2, port1=1, port2=0)
        self.addLink(s2, h3, port1=2, port2=0)


S1_RULES = [
    "table_add ipv4_lpm set_egress_port 10.0.1.1/32 => 0",
    "table_add ipv4_lpm set_egress_port 10.0.1.2/32 => 1",
    "table_add ipv4_lpm set_egress_port 10.0.1.3/32 => 1",
    "table_set_default swid_table set_swid 1",
    "table_set_default int_table add_int_metadata",
]

S2_RULES = [
    "table_add ipv4_lpm set_egress_port 10.0.1.1/32 => 0",
    "table_add ipv4_lpm set_egress_port 10.0.1.2/32 => 1",
    "table_add ipv4_lpm set_egress_port 10.0.1.3/32 => 2",
    "table_set_default swid_table set_swid 2",
    "table_set_default int_table add_int_metadata",
]


def program_switch(thrift_port, rules, name):
    info("*** programming %s (thrift %d)\n" % (name, thrift_port))
    proc = subprocess.run(
        ["simple_switch_CLI", "--thrift-port", str(thrift_port)],
        input="\n".join(rules) + "\n", text=True, capture_output=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    if out:
        print(out)
    return proc.returncode == 0


def cli_check(thrift_port, name):
    info("*** CLI check %s (thrift %d)\n" % (name, thrift_port))
    proc = subprocess.run(
        ["simple_switch_CLI", "--thrift-port", str(thrift_port)],
        input="table_dump ipv4_lpm\n", text=True, capture_output=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    print(out if out else "(no output)")
    return proc.returncode == 0


def parse_pcap(path):
    """Minimal pcap (little-endian, Ethernet) reader -> list of frames."""
    with open(path, "rb") as f:
        data = f.read()
    frames = []
    off = 24
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from("<IIII", data, off)
        off += 16
        if off + incl > len(data):
            break
        frames.append(data[off:off + incl])
        off += incl
    return frames


def parse_int(frame):
    """Extract INT info from an Ethernet frame carrying UDP/4000."""
    if len(frame) < 42 or frame[12:14] != b"\x08\x00":
        return None
    ip = frame[14:]
    if ip[9] != 17:
        return None
    ihl = (ip[0] & 0x0F) * 4
    udp = ip[ihl:]
    sport, dport = struct.unpack_from("!HH", udp, 0)
    payload = udp[8:]
    if len(payload) < 4:
        return None
    ver = payload[0] >> 4
    count = payload[1]
    length = payload[2]
    entries = []
    for i in range(min(count, 4)):
        e = payload[4 + i * 12: 4 + (i + 1) * 12]
        if len(e) < 12:
            break
        swid, ts = struct.unpack("!II", e[:8])
        qdepth, _pad = struct.unpack("!HH", e[8:12])
        entries.append((swid, ts, qdepth))
    return {
        "sport": sport, "dport": dport, "ver": ver,
        "count": count, "length": length, "entries": entries,
    }


def run_int_test(net):
    info("*** INT test: h1 -> h2 (udp/4000), capture on h2-eth0\n")
    h1, h2 = net.get("h1"), net.get("h2")
    cap = "/tmp/int-cap.pcap"
    h2.cmd("rm -f %s" % cap)
    h2.cmd("tcpdump -i h2-eth0 -U -w %s -c 10 udp port 4000 "
           "> /tmp/tcpdump.err 2>&1 &" % cap)
    time.sleep(1)
    h1.cmd("python3 '%s' 10.0.1.2" % INT_SENDER)
    time.sleep(3)
    h2.cmd('pkill -f "tcpdump.*h2-eth0"')
    time.sleep(1)

    parsed = [parse_int(f) for f in parse_pcap(cap)]
    parsed = [p for p in parsed if p is not None]
    if not parsed:
        print("FAIL: no INT packets captured")
        return False

    p = parsed[0]
    print("captured %d INT packets (showing first):" % len(parsed))
    print("  INT hdr: ver=0x%X count=%d length=%d"
          % (p["ver"], p["count"], p["length"]))
    for swid, ts, qdepth in p["entries"]:
        print("  entry: switch_id=%d ts=%d qdepth=%d" % (swid, ts, qdepth))

    ok = (p["ver"] == 0xF and p["count"] == 2 and p["length"] == 24
          and [e[0] for e in p["entries"]] == [1, 2])
    print("INT test: %s" % ("PASS" if ok else "FAIL"))
    return ok


def main():
    setLogLevel("info")
    topo = IntTopo()
    net = Mininet(
        topo=topo, host=Host, switch=P4Switch, link=TCLink,
        controller=None, autoSetMacs=True, autoStaticArp=True,
    )
    results = {}
    try:
        net.start()
        results["s1 tables"] = program_switch(9090, S1_RULES, "s1")
        results["s2 tables"] = program_switch(9091, S2_RULES, "s2")

        info("*** ping all hosts\n")
        pinged = net.pingAll()
        results["pingAll"] = (pinged == 0)

        results["int"] = run_int_test(net)
        results["cli"] = cli_check(9090, "s1")

        info("*** summary\n")
        for k, v in results.items():
            print("  %-10s %s" % (k, "OK" if v else "FAIL"))
    finally:
        info("*** stopping network\n")
        net.stop()


if __name__ == "__main__":
    main()
