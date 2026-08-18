#!/usr/bin/env python3
"""Task 8: Mininet topology with an SNMP agent + poller.

Topology: h1 h2 h3 h4 -- s1 (OVS, standalone/learning switch).

- snmpd runs INSIDE h4 (the "network device" with an SNMP agent), using a
  minimal config (rocommunity public, agentaddress udp:161) written to
  /tmp/snmpd.conf (Ubuntu's default config restricts read access).
- tools/snmp_poller.py runs in the WSL root netns and polls 10.0.1.4:161
  every 5 s. To reach the emulated network from the root netns, an OVS
  internal port (nt0) is added to s1 with IP 10.0.1.254/24.
- iperf h1 -> h4 (the SNMP device) so ifInOctets/ifOutOctets deltas make
  bandwidth rows non-zero; h3 -> h2 adds background traffic.
- Rows land in db/telemetry.db -> snmp_stats.

Run as root in WSL:
    cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
    sudo python3 mn/topology_snmp.py
"""
import os
import sqlite3
import subprocess
import sys
import time

from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch
from mininet.topo import Topo

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Mininet's cmd() splits on whitespace (no quoting), so use the space-free
# symlink to PROJECT.
SNMP_POLLER = "/tmp/nt/tools/snmp_poller.py"
DB_PATH = os.path.join(PROJECT, "db", "telemetry.db")
DEVICE_IP = "10.0.1.4"
ROOT_IP = "10.0.1.254"
SNMPD_CONF = "/tmp/snmpd.conf"

SNMPD_CONF_TEXT = "rocommunity public\nagentaddress udp:161\n"


class OvTopo(Topo):
    def build(self):
        for i in range(1, 5):
            self.addHost("h%d" % i, ip="10.0.1.%d/24" % i)
        self.addSwitch("s1")
        for i in range(1, 5):
            self.addLink("h%d" % i, "s1")


def pre_cleanup():
    """Remove stale state from crashed runs (veths, OVS bridge, iperf)."""
    subprocess.run(["mn", "-c"], capture_output=True, timeout=60)
    subprocess.run(["ovs-vsctl", "--if-exists", "del-br", "s1"],
                   capture_output=True)
    subprocess.run(["pkill", "-f", "iperf3"], capture_output=True)
    subprocess.run(["pkill", "-f", "snmp_poller.py"], capture_output=True)
    subprocess.run(["ln", "-sfn", PROJECT, "/tmp/nt"], capture_output=True)
    time.sleep(1)


def start_snmpd(net):
    """Run snmpd inside h4 (its netns) with a permissive minimal config.

    Mininet hosts share the root mount namespace, so the config file
    written to /tmp is visible inside h4.
    """
    with open(SNMPD_CONF, "w") as f:
        f.write(SNMPD_CONF_TEXT)
    h4 = net.get("h4")
    h4.cmd("pkill -x snmpd")
    time.sleep(0.5)
    info("*** snmpd on h4 (%s), config: rocommunity public, udp:161\n"
         % DEVICE_IP)
    # -C: skip the default /etc/snmp/snmpd.conf (it binds 127.0.0.1,[::1],
    # which makes a later 0.0.0.0:161 bind fail with EADDRINUSE).
    h4.cmd("snmpd -f -C -c %s -Lo > /tmp/snmpd.log 2>&1 &" % SNMPD_CONF)
    time.sleep(2)
    out = h4.cmd("snmpget -v2c -c public 127.0.0.1 1.3.6.1.2.1.1.3.0")
    ok = "Timeticks" in out
    if not ok:
        print("  snmpd self-check failed:\n%s" % h4.cmd("cat /tmp/snmpd.log"))
    return ok


def add_root_port():
    """Bridge s1 into the root netns: internal port nt0 = 10.0.1.254/24.

    OVS bridges live in the root netns, so an internal port gives the
    poller (and snmpget) a path to the emulated hosts.
    """
    out = subprocess.run(["ovs-vsctl", "add-port", "s1", "nt0", "--",
                          "set", "interface", "nt0", "type=internal"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print("add-port failed: %s" % (out.stdout + out.stderr))
        return False
    subprocess.run(["ip", "addr", "flush", "dev", "nt0"], capture_output=True)
    subprocess.run(["ip", "addr", "add", "%s/24" % ROOT_IP, "dev", "nt0"],
                   capture_output=True)
    subprocess.run(["ip", "link", "set", "nt0", "up"], capture_output=True)
    time.sleep(1)
    # Warm ARP for the SNMP device (learning switch broadcasts until learned).
    ping = subprocess.run(["ping", "-c", "1", "-W", "2", DEVICE_IP],
                          capture_output=True, text=True)
    return ping.returncode == 0


def start_poller():
    subprocess.run(["pkill", "-f", "snmp_poller.py"], capture_output=True)
    time.sleep(0.5)
    log = open("/tmp/snmp-poller.log", "w")
    proc = subprocess.Popen(
        ["python3", SNMP_POLLER, "--host", DEVICE_IP, "--interval", "5"],
        cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT)
    time.sleep(2)
    return proc


def stop_poller(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    subprocess.run(["pkill", "-f", "snmp_poller.py"], capture_output=True)


def run_iperf(net, seconds=15, src="h1", dst="h2"):
    info("*** iperf3: %s -> %s (%ds)\n" % (src, dst, seconds))
    h_src, h_dst = net.get(src), net.get(dst)
    h_dst.cmd("pkill -f iperf3; iperf3 -s -D")
    h_src.cmd("timeout %d iperf3 -c 10.0.1.%s -t %d -J "
              "> /tmp/iperf-%s.json 2>&1" % (seconds + 10, dst[1], seconds,
                                             src))
    h_dst.cmd("pkill -f iperf3")
    try:
        import json
        with open("/tmp/iperf-%s.json" % src) as f:
            report = json.load(f)
        mbps = report.get("end", {}).get("sum_received", {}).get(
            "bits_per_second", 0) / 1e6
        print("iperf3 %s throughput: %.1f Mb/s" % (src, mbps))
    except Exception as exc:
        print("iperf3 report parse failed: %s" % exc)


def verify():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM snmp_stats").fetchone()[0]
    mem_rows = conn.execute(
        "SELECT COUNT(*) FROM snmp_stats "
        "WHERE cpu_load BETWEEN 0 AND 100 AND mem_used_pct BETWEEN 0 AND 100"
    ).fetchone()[0]
    bw_rows = conn.execute(
        "SELECT COUNT(*) FROM snmp_stats WHERE bw_in_mbps > 0").fetchone()[0]
    bw_max = conn.execute(
        "SELECT MAX(bw_in_mbps) FROM snmp_stats").fetchone()[0] or 0.0
    ts_min, ts_max = conn.execute(
        "SELECT MIN(ts), MAX(ts) FROM snmp_stats").fetchone()
    sample = [dict(r) for r in conn.execute(
        "SELECT ts, device, cpu_load, mem_used_pct, if_octets_in, "
        "if_octets_out, bw_in_mbps, bw_out_mbps, uptime "
        "FROM snmp_stats ORDER BY ts DESC LIMIT 4")]
    conn.close()

    print("  rows: %d | valid cpu/mem: %d | bw>0 rows: %d | max bw_in: %.1f Mb/s"
          % (total, mem_rows, bw_rows, bw_max))
    if ts_min and ts_max:
        span = ts_max - ts_min
        interval = span / max(total - 1, 1) if total > 1 else 0
        print("  span: %ds, avg poll interval: %.1fs" % (span, interval))
    for r in sample:
        print("  %s cpu=%.2f mem=%.1f%% in=%s out=%s bw_in=%.3f bw_out=%.3f "
              "uptime=%s"
              % (r["device"], r["cpu_load"] or 0, r["mem_used_pct"] or 0,
                 r["if_octets_in"], r["if_octets_out"], r["bw_in_mbps"],
                 r["bw_out_mbps"], r["uptime"]))
    return total >= 4 and mem_rows == total and bw_rows > 0


def verify_snmpget():
    """DoD: snmpget from the WSL host (root netns) proves the agent responds."""
    out = subprocess.run(
        ["snmpget", "-v2c", "-c", "public", DEVICE_IP,
         "1.3.6.1.2.1.1.3.0"],
        capture_output=True, text=True)
    ok = out.returncode == 0 and "Timeticks" in out.stdout
    print("  snmpget from WSL host: %s%s"
          % ("OK: " if ok else "FAIL: ", out.stdout.strip() or out.stderr))
    return ok


def main():
    setLogLevel("info")
    pre_cleanup()
    topo = OvTopo()
    net = None
    poller = None
    results = {}
    try:
        net = Mininet(topo=topo, host=Host, switch=OVSSwitch, link=TCLink,
                      controller=None, autoStaticArp=True)
        net.start()
        subprocess.run(["ovs-vsctl", "set-fail-mode", "s1", "standalone"],
                       capture_output=True)
        results["snmpd up"] = start_snmpd(net)
        results["root port"] = add_root_port()
        poller = start_poller()
        results["poller up"] = True

        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM snmp_stats")
        conn.commit()
        conn.close()

        info("*** ping all hosts\n")
        results["pingAll"] = (net.pingAll() == 0)

        # iperf TO h4 (the SNMP device) so its interface counters move;
        # h3 -> h2 adds background traffic.
        run_iperf(net, seconds=15, src="h1", dst="h4")
        run_iperf(net, seconds=15, src="h3", dst="h2")
        # Let >= 4 poll cycles (5 s each) land after traffic stops.
        info("*** waiting for final polls (20s)\n")
        time.sleep(20)

        results["snmpget"] = verify_snmpget()
        results["poller db"] = verify()
        stop_poller(poller)
        poller = None

        info("*** summary\n")
        for k, v in results.items():
            print("  %-10s %s" % (k, "OK" if v else "FAIL"))
    finally:
        if poller:
            stop_poller(poller)
        if net:
            info("*** stopping network\n")
            net.stop()


if __name__ == "__main__":
    main()
