#!/usr/bin/env python3
"""Task 11 E2E: persistent INT demo (tasks 04+05).

Reuses topology_int.py's P4Switch/IntTopo/rule tables, then runs the real
collector path that writes db/telemetry.db -> int_hops:

  - tools/int_receiver.py on h2 (scapy sniff + INT stack parse -> DB)
  - tools/int_sender.py on h1: 10 s of 10 pps, then a 1000-pkt burst with
    s2's egress rate throttled (set_queue_rate 500) so enq_qdepth spikes.

Counts int_hops rows, prints them, and exits (rows stay in the DB for the
dashboard). Run as root in WSL:

    cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
    sudo python3 mn/topology_int_demo.py
"""
import os
import sqlite3
import subprocess
import time

from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import Host

from topology_int import IntTopo, P4Switch, S1_RULES, S2_RULES, program_switch

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT, "db", "telemetry.db")
# Space-free symlink so Mininet host cmd() (whitespace-split) can cd into
# the project (see scripts/wsl-tmp note in topology_ovs.py).
NT = "/tmp/nt"


def set_queue_rate(thrift_port, rate):
    subprocess.run(
        ["simple_switch_CLI", "--thrift-port", str(thrift_port)],
        input="set_queue_rate %d\n" % rate, text=True, capture_output=True)


def count_rows():
    conn = sqlite3.connect(DB_PATH)
    n = conn.execute("SELECT COUNT(*) FROM int_hops").fetchone()[0]
    sample = conn.execute(
        "SELECT switch_id, hop_latency_us, queue_occupancy FROM int_hops "
        "ORDER BY ts DESC LIMIT 6").fetchall()
    conn.close()
    return n, sample


def main():
    setLogLevel("info")
    subprocess.run(["ln", "-sfn", PROJECT, NT], check=False)
    topo = IntTopo()
    net = Mininet(
        topo=topo, host=Host, switch=P4Switch, link=TCLink,
        controller=None, autoSetMacs=True, autoStaticArp=True,
    )
    try:
        net.start()
        program_switch(9090, S1_RULES, "s1")
        program_switch(9091, S2_RULES, "s2")

        info("*** ping all hosts\n")
        net.pingAll()

        h1, h2 = net.get("h1"), net.get("h2")
        info("*** INT receiver on h2 (scapy -> int_hops)\n")
        h2.cmd("cd %s && nohup python3 %s/tools/int_receiver.py "
               "> /tmp/int-receiver.log 2>&1 &" % (NT, NT))
        time.sleep(2)

        info("*** steady INT flow h1 -> h2 (10 pps, 10 s)\n")
        h1.cmd("cd %s && python3 %s/tools/int_sender.py 10.0.1.2 "
               "--duration 10 --pps 10 > /tmp/int-steady.log 2>&1"
               % (NT, NT))
        time.sleep(3)

        info("*** burst: throttle s2 to 500 pps, 1000 pkts back-to-back\n")
        set_queue_rate(9091, 500)
        time.sleep(1)
        h1.cmd("cd %s && python3 %s/tools/int_sender.py 10.0.1.2 "
               "--burst > /tmp/int-burst.log 2>&1" % (NT, NT))
        # Let the receiver flush rows, then ease the rate back.
        time.sleep(5)
        set_queue_rate(9091, 1000)

        time.sleep(3)
        info("*** stopping INT receiver\n")
        h2.cmd("pkill -f int_receiver.py")

        n, sample = count_rows()
        print("\nint_hops rows: %d" % n)
        for r in sample:
            print("  switch_id=%d lat_us=%.1f qdepth=%d" % tuple(r))
    finally:
        info("*** stopping network\n")
        net.stop()


if __name__ == "__main__":
    main()