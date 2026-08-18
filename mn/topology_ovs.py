#!/usr/bin/env python3
"""Tasks 06+07: Mininet topology with OVS sFlow, NetFlow v5 + IPFIX.

Topology: h1 h2 h3 h4 -- s1 (OVS, standalone/learning switch).

Task 6 - OVS exports sFlow v5 (sampling=1, header=128, polling=10) to
127.0.0.1:6343 where tools/sflow_collector.py stores parsed samples in
db/telemetry.db -> sflow_samples.

Task 7 - softflowd exporters run inside hosts: h1 exports NetFlow v5
to 10.0.1.4:9995, h3 exports IPFIX (v10) to 10.0.1.4:9996; the
netflow/ipfix collectors run on h4 (dedicated collector host) and
store parsed flows in netflow_flows / ipfix_flows.

WSL2 note: softflowd's live libpcap capture receives no packets on
this kernel, so capture is delegated to tcpdump -U writing a pcap FIFO
that softflowd reads with -r (see start_flow_exporters).

Run as root in WSL:
    cd "/mnt/c/Users/ASUS/Desktop/Network telementry"
    sudo python3 mn/topology_ovs.py
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
SFLOW_COLLECTOR = os.path.join(PROJECT, "tools", "sflow_collector.py")
# Mininet's cmd() splits strings on whitespace (no shell quoting), so paths
# containing spaces break; /tmp/nt is a space-free symlink to PROJECT.
NETFLOW_COLLECTOR = "/tmp/nt/tools/netflow_collector.py"
IPFIX_COLLECTOR = "/tmp/nt/tools/ipfix_collector.py"
DB_PATH = os.path.join(PROJECT, "db", "telemetry.db")


class OvTopo(Topo):
    def build(self):
        for i in range(1, 5):
            self.addHost("h%d" % i, ip="10.0.1.%d/24" % i)
        self.addSwitch("s1")
        for i in range(1, 5):
            self.addLink("h%d" % i, "s1")


def agent_ip():
    """IP of eth0 (used as sFlow agent address; informational)."""
    try:
        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "eth0"],
            capture_output=True, text=True, timeout=5).stdout
        return out.split()[3].split("/")[0]
    except Exception:
        return "127.0.0.1"


def enable_sflow():
    ip = agent_ip()
    info("*** enabling sFlow on s1 (agent=%s, target=127.0.0.1:6343)\n" % ip)
    cmd = ["ovs-vsctl", "--", "--id=@s", "create", "sflow",
           "agent=%s" % ip, 'target="127.0.0.1:6343"',
           "sampling=1", "header=128", "polling=10",
           "--", "set", "bridge", "s1", "sflow=@s"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("sFlow config failed:\n%s" % (proc.stdout + proc.stderr))
        return False
    out = subprocess.run(["ovs-vsctl", "list", "sflow"],
                         capture_output=True, text=True).stdout
    info("sFlow config: %s\n" % " ".join(out.split()) or "(empty)")
    return True


def start_collector():
    subprocess.run(["pkill", "-f", "sflow_collector.py"],
                   capture_output=True)
    time.sleep(0.5)
    log = open("/tmp/sflow-collector.log", "w")
    proc = subprocess.Popen(
        ["python3", SFLOW_COLLECTOR], cwd=PROJECT,
        stdout=log, stderr=subprocess.STDOUT)
    time.sleep(2)
    return proc


def stop_collector(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    subprocess.run(["pkill", "-f", "sflow_collector.py"], capture_output=True)


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


def start_flow_collectors(net):
    """Task 7 (option A): NetFlow v5 + IPFIX collectors run on h4.

    softflowd on h1 exports to 10.0.1.4:9995, on h3 to 10.0.1.4:9996.
    """
    h4 = net.get("h4")
    h4.cmd("pkill -f netflow_collector; pkill -f ipfix_collector")
    time.sleep(0.5)
    h4.cmd("nohup python3 %s > /tmp/netflow-collector.log 2>&1 &"
           % NETFLOW_COLLECTOR)
    h4.cmd("nohup python3 %s > /tmp/ipfix-collector.log 2>&1 &"
           % IPFIX_COLLECTOR)
    time.sleep(2)


def start_flow_exporters(net):
    """Task 7: softflowd exporters inside h1 (NetFlow v5) and h3 (IPFIX).

    WSL2 quirk: softflowd's live libpcap capture receives no packets on
    this kernel, while tcpdump's capture works. So each host runs
    tcpdump -U (packet-buffered flush) writing a pcap FIFO that
    softflowd reads with -r (it blocks on the FIFO instead of exiting
    at EOF; stopping tcpdump triggers the final flow export).
    """
    info("*** softflowd exporters: h1 NetFlow v5 -> h4:9995, "
         "h3 IPFIX -> h4:9996\n")
    h1, h3 = net.get("h1"), net.get("h3")
    for h in (h1, h3):
        h.cmd("pkill -x softflowd; pkill -f tcpdump")
    time.sleep(0.5)
    h1.cmd("rm -f /tmp/nf5.pcap /tmp/sf5.ctl")
    h3.cmd("rm -f /tmp/ipfix.pcap /tmp/sf10.ctl")
    h1.cmd("mkfifo /tmp/nf5.pcap 2>/dev/null")
    h3.cmd("mkfifo /tmp/ipfix.pcap 2>/dev/null")
    # Exclude each host's own export traffic so softflowd doesn't re-export
    # its own datagrams (feedback loop).
    h1.cmd("tcpdump -U -i h1-eth0 -w /tmp/nf5.pcap "
           "'not port 9995 and not port 9996' "
           "> /tmp/tcpdump-h1.log 2>&1 &")
    h3.cmd("tcpdump -U -i h3-eth0 -w /tmp/ipfix.pcap "
           "'not port 9996 and not port 9995' "
           "> /tmp/tcpdump-h3.log 2>&1 &")
    time.sleep(1)
    h1.cmd("softflowd -r /tmp/nf5.pcap -v 5 -n 10.0.1.4:9995 "
           "-t tcp=60 -t tcp.fin=10 -c /tmp/sf5.ctl -d "
           "> /tmp/softflowd-h1.log 2>&1 &")
    h3.cmd("softflowd -r /tmp/ipfix.pcap -v 10 -n 10.0.1.4:9996 "
           "-t tcp=60 -t tcp.fin=10 -c /tmp/sf10.ctl -d "
           "> /tmp/softflowd-h3.log 2>&1 &")
    time.sleep(2)


def stop_flow_exporters(net):
    """Kill tcpdump first: FIFO EOF makes softflowd export all flows."""
    h1, h3 = net.get("h1"), net.get("h3")
    h1.cmd("pkill -f tcpdump")
    h3.cmd("pkill -f tcpdump")
    time.sleep(5)
    h1.cmd("pkill -x softflowd")
    h3.cmd("pkill -x softflowd")


def stop_flow_collectors(net):
    h4 = net.get("h4")
    h4.cmd("pkill -f netflow_collector; pkill -f ipfix_collector")


def verify_flows():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    nf_total = conn.execute("SELECT COUNT(*) FROM netflow_flows").fetchone()[0]
    nf_h1h2 = conn.execute(
        "SELECT COUNT(*) FROM netflow_flows "
        "WHERE src_ip='10.0.1.1' AND dst_ip='10.0.1.2' AND proto=6"
    ).fetchone()[0]
    nf_bytes = conn.execute(
        "SELECT COALESCE(SUM(bytes),0) FROM netflow_flows").fetchone()[0]
    ip_total = conn.execute("SELECT COUNT(*) FROM ipfix_flows").fetchone()[0]
    ip_h3 = conn.execute(
        "SELECT COUNT(*) FROM ipfix_flows "
        "WHERE src_ip='10.0.1.3' AND dst_ip='10.0.1.2' AND proto=6"
    ).fetchone()[0]
    ip_bytes = conn.execute(
        "SELECT COALESCE(SUM(bytes),0) FROM ipfix_flows").fetchone()[0]
    sample_nf = [dict(r) for r in conn.execute(
        "SELECT src_ip, dst_ip, src_port, dst_port, proto, packets, bytes "
        "FROM netflow_flows ORDER BY ts DESC LIMIT 3")]
    sample_ip = [dict(r) for r in conn.execute(
        "SELECT src_ip, dst_ip, src_port, dst_port, proto, packets, bytes "
        "FROM ipfix_flows ORDER BY ts DESC LIMIT 3")]
    conn.close()

    print("  netflow: rows=%d h1->h2 tcp=%d bytes=%d" %
          (nf_total, nf_h1h2, nf_bytes))
    for r in sample_nf:
        print("    %s -> %s:%s proto=%s pkts=%s bytes=%s"
              % (r["src_ip"], r["dst_ip"], r["dst_port"], r["proto"],
                 r["packets"], r["bytes"]))
    print("  ipfix: rows=%d h3->h2 tcp=%d bytes=%d" %
          (ip_total, ip_h3, ip_bytes))
    for r in sample_ip:
        print("    %s -> %s:%s proto=%s pkts=%s bytes=%s"
              % (r["src_ip"], r["dst_ip"], r["dst_port"], r["proto"],
                 r["packets"], r["bytes"]))
    return nf_total > 0 and nf_h1h2 > 0 and nf_bytes > 0 \
        and ip_total > 0 and ip_h3 > 0 and ip_bytes > 0


def verify():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM sflow_samples").fetchone()[0]
    flows = conn.execute(
        "SELECT COUNT(*) FROM sflow_samples "
        "WHERE src_ip='10.0.1.1' AND dst_ip='10.0.1.2' AND proto=6").fetchone()[0]
    bw_rows = conn.execute(
        "SELECT COUNT(*) FROM sflow_samples WHERE bandwidth_in_mbps > 0").fetchone()[0]
    bw_max = conn.execute(
        "SELECT MAX(bandwidth_in_mbps) FROM sflow_samples").fetchone()[0] or 0.0
    sample = [dict(r) for r in conn.execute(
        "SELECT ts, agent, src_ip, dst_ip, src_port, dst_port, proto, "
        "bytes_sampled, in_port, out_port FROM sflow_samples "
        "WHERE src_ip IS NOT NULL ORDER BY ts DESC LIMIT 3")]
    conn.close()

    print("  rows total: %d | h1->h2 tcp flows: %d | bw rows: %d | max in: %.1f Mb/s"
          % (total, flows, bw_rows, bw_max))
    for r in sample:
        print("  %s -> %s:%s proto=%s bytes=%s in_port=%s out_port=%s"
              % (r["src_ip"], r["dst_ip"], r["dst_port"], r["proto"],
                 r["bytes_sampled"], r["in_port"], r["out_port"]))
    return total > 100 and flows > 0 and bw_rows > 0


def pre_cleanup():
    """Remove stale state from crashed runs (veths, OVS bridge, iperf)."""
    subprocess.run(["mn", "-c"], capture_output=True, timeout=60)
    subprocess.run(["ovs-vsctl", "--if-exists", "del-br", "s1"],
                   capture_output=True)
    subprocess.run(["pkill", "-f", "iperf3"], capture_output=True)
    subprocess.run(["pkill", "-f", "sflow_collector.py"], capture_output=True)
    subprocess.run(["pkill", "-f", "netflow_collector.py"], capture_output=True)
    subprocess.run(["pkill", "-f", "ipfix_collector.py"], capture_output=True)
    # Space-free symlink so Mininet host cmd() can reference tool paths.
    subprocess.run(["ln", "-sfn", PROJECT, "/tmp/nt"], capture_output=True)
    time.sleep(1)


def main():
    setLogLevel("info")
    pre_cleanup()
    topo = OvTopo()
    net = None
    collector = None
    results = {}
    try:
        net = Mininet(topo=topo, host=Host, switch=OVSSwitch, link=TCLink,
                      controller=None, autoStaticArp=True)
        net.start()
        # No controller: put the OVS bridge in standalone mode so it acts as
        # a learning switch (secure mode with empty flows would drop all).
        subprocess.run(["ovs-vsctl", "set-fail-mode", "s1", "standalone"],
                       capture_output=True)
        collector = start_collector()
        results["sflow cfg"] = enable_sflow()
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM sflow_samples")
        conn.execute("DELETE FROM netflow_flows")
        conn.execute("DELETE FROM ipfix_flows")
        conn.commit()
        conn.close()

        info("*** ping all hosts\n")
        results["pingAll"] = (net.pingAll() == 0)

        start_flow_collectors(net)
        start_flow_exporters(net)
        results["exporters up"] = True

        run_iperf(net, seconds=15, src="h1", dst="h2")
        run_iperf(net, seconds=15, src="h3", dst="h2")
        # Wait >1 full counter-poll cycle (10 s) so the post-iperf poll is
        # received and flushed; otherwise bandwidth rows can land after verify.
        info("*** waiting for final counter poll (12s)\n")
        time.sleep(12)

        info("*** stopping exporters: tcpdump first, softflowd flushes on EOF\n")
        stop_flow_exporters(net)
        time.sleep(3)

        results["sflow"] = verify()
        results["netflow+ipfix"] = verify_flows()
        stop_flow_collectors(net)
        info("*** summary\n")
        for k, v in results.items():
            print("  %-10s %s" % (k, "OK" if v else "FAIL"))
    finally:
        if collector:
            stop_collector(collector)
        if net:
            info("*** stopping network\n")
            net.stop()
        subprocess.run(["ovs-vsctl", "--if-exists", "clear", "bridge", "s1",
                        "sflow"], capture_output=True)


if __name__ == "__main__":
    main()
