#!/bin/bash
# Task 9 E2E: gNMI agent + client against simple_switch_grpc with real traffic.
set -e
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJ"

echo "=== cleanup ==="
ip netns del ns-a 2>/dev/null || true
ip netns del ns-b 2>/dev/null || true
ip link del sw-va 2>/dev/null || true
ip link del sw-vb 2>/dev/null || true
pkill -f 'simple_switch_grpc --device' 2>/dev/null || true
pkill -f 'tools/gnmi_agen[t]' 2>/dev/null || true
sleep 2

echo "=== netns + veth ==="
ip netns add ns-a
ip netns add ns-b
ip link add sw-va type veth peer name va
ip link add sw-vb type veth peer name vb
ip link set va netns ns-a
ip link set vb netns ns-b
ip link set sw-va up
ip link set sw-vb up
ip netns exec ns-a ip addr add 10.0.1.1/24 dev va
ip netns exec ns-b ip addr add 10.0.1.2/24 dev vb
ip netns exec ns-a ip link set va up
ip netns exec ns-b ip link set vb up
ip netns exec ns-a ip link set lo up
ip netns exec ns-b ip link set lo up
ip netns exec ns-a ip route add default dev va
ip netns exec ns-b ip route add default dev vb
# pin MACs so switch-forwarded frames match the kernel's NIC
ip netns exec ns-a ip link set va address 02:00:00:00:00:01
ip netns exec ns-b ip link set vb address 02:00:00:00:00:02
ip netns exec ns-a arp -s 10.0.1.2 02:00:00:00:00:02
ip netns exec ns-b arp -s 10.0.1.1 02:00:00:00:00:01

echo "=== start switch (thrift 9090, grpc 9559) ==="
cp "$PROJ/p4/int.json" /tmp/int.json
setsid nohup simple_switch_grpc --device-id 1 --thrift-port 9090 \
  -i 0@sw-va -i 1@sw-vb /tmp/int.json \
  -- --grpc-server-addr 0.0.0.0:9559 --cpu-port 64 \
  > /tmp/gnmi-e2e-sw.log 2>&1 < /dev/null &
sleep 5
simple_switch_CLI --thrift-port 9090 <<'EOF'
table_add ipv4_lpm set_egress_port 10.0.1.2/32 => 1
table_add ipv4_lpm set_egress_port 10.0.1.1/32 => 0
table_set_default swid_table set_swid 1
table_set_default int_table add_int_metadata
EOF

echo "=== start gNMI agent ==="
setsid nohup python3 tools/gnmi_agent.py --thrift-port 9090 \
  --grpc-addr 0.0.0.0:9339 --interfaces 0:eth0,1:eth1 \
  > /tmp/gnmi-e2e-agent.log 2>&1 < /dev/null &
sleep 3

echo "=== start gNMI poller (background, 18s) ==="
timeout 20 python3 tools/gnmi_client.py --target 127.0.0.1:9339 \
  --interval 2 --duration 18 > /tmp/gnmi-e2e-client.log 2>&1 &
CLIENT_PID=$!
sleep 3

echo "=== inject traffic (ping flood + iperf3 8s h1->h2) ==="
ip netns exec ns-b timeout 16 iperf3 -s > /tmp/iperf-e2e-srv.log 2>&1 &
sleep 1
ip netns exec ns-a bash -c 'for i in $(seq 1 6); do ping -c 10 -W 0.2 10.0.1.2 > /dev/null 2>&1; sleep 0.4; done' &
ip netns exec ns-a sleep 0.5
ip netns exec ns-a timeout 10 iperf3 -c 10.0.1.2 -t 8 -w 256K \
  > /tmp/iperf-e2e-cli.log 2>&1 || true

echo "=== wait for poller ==="
wait $CLIENT_PID || true
echo "--- client log ---"
cat /tmp/gnmi-e2e-client.log | tail -10
echo "--- iperf client result ---"
grep -E "sender|receiver|SUM" /tmp/iperf-e2e-cli.log | head -5

echo "=== DB check ==="
python3 - <<'PY'
import sqlite3
conn = sqlite3.connect("db/telemetry.db")
conn.row_factory = sqlite3.Row
rows = list(conn.execute(
    "SELECT ts, path, key, value, int_value FROM gnmi_stats "
    "ORDER BY ts DESC LIMIT 12"))
conn.close()
print("%d rows (last 12):" % len(rows))
for r in rows:
    print("  %s %s=%s" % (r["key"], r["path"].split("/")[-2], r["value"]))

inct = [r["int_value"] for r in rows if r["key"] == "in-octets"]
if inct and inct[0] > 0:
    print("PASS: counters grew (in-octets=%d)" % inct[0])
else:
    print("FAIL: counters did not grow")
PY

echo "=== cleanup ==="
pkill -f 'tools/gnmi_agen[t]' 2>/dev/null || true
pkill -f 'simple_switch_grpc --device' 2>/dev/null || true
ip netns del ns-a 2>/dev/null || true
ip netns del ns-b 2>/dev/null || true
ip link del sw-va 2>/dev/null || true
ip link del sw-vb 2>/dev/null || true
echo "done"
