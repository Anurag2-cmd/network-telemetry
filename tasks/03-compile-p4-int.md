# Task 03: Compile the P4 INT program

## Goal
`p4/int.p4` (already written, in the project folder) compiles to
`p4/int.json` that `simple_switch` can load.

## Context
- P4 program implements **INT over UDP**: hosts send UDP/4000 whose payload starts
  with an INT header (count=0); each switch appends one 8-byte metadata entry
  `{switch_id, ingress_ts(µs), enq_qdepth}`. Receiver parses the stack.
- Requires p4c with BMv2 backend (task 01 DONE).
- Project WSL path: `/mnt/c/Users/ASUS/Desktop/Network telementry`

## Steps (run inside WSL)
```bash
cd "/mnt/c/Users/ASUS/Desktop/Network telementry/p4"
p4c-bm2-ss --arch v1model int.p4 -o int.json
```
- On success you get `int.json` (~hundreds of KB). 
- On compile errors, fix them in `int.p4` and recompile. Expected possible issues:
  - `enq_qdepth` / `ingress_global_timestamp` unknown → they ARE in BMv2's
    v1model standard_metadata (check `grep -r enq_qdepth ~/p4tools/p4c/p4include/v1model.p4`).
  - checksum extern name differences → v1model uses `update_checksum` exactly as written.
  - header stack `b.extract(hdr.int_meta.next)` loop → v1model supports it; if p4c
    rejects infinite-stack parse, parse a fixed number (see troubleshooting).

## Sanity test WITHOUT Mininet (single switch, two host namespaces)
1. `sudo ip netns add ns-a; sudo ip netns add ns-b`
2. `sudo ip link add va type veth peer name vb`
3. Move ends into namespaces, give IPs 10.0.1.1/24 and 10.0.1.2/24.
4. Start switch: `sudo simple_switch --thrift-port 9090 int.json`
5. Pipe veth ends into the switch:
   `sudo simple_switch_CLI --thrift-port 9090 <<< "add-port 0 va; add-port 1 vb"`
   (va/vb must be up: `sudo ip link set va up; sudo ip link set vb up`)
6. Program forwarding: default route on hosts + CLI:
   `table_add ipv4_lpm set_egress_port 10.0.1.2/32 => 1`
   `table_add ipv4_lpm set_egress_port 10.0.1.1/32 => 0`
   `table_set_default swid_table set_swid 1`
7. In ns-b: `tcpdump -i vb -c 5 -X` ; in ns-a: run `tools/int_sender.py` (below).

## tools/int_sender.py (create it; sender side)
```python
import socket, struct, sys
DST = sys.argv[1] if len(sys.argv) > 1 else "10.0.1.2"
INT_HDR = struct.pack("!I", 0xF0000000)   # ver=0xF, count=0, length=0
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(10):
    s.sendto(INT_HDR + b"payload-%d" % i, (DST, 4000))
    import time; time.sleep(0.2)
```
Raw socket path alternative (needed if the UDP send is intercepted before the
INT bytes matter — INT bytes are just payload, so plain UDP socket is fine).

## Verification (Definition of Done)
- `int.json` exists (compile OK).
- tcpdump on ns-b shows UDP/4000 packets whose payload begins `f0 00 00 00`
  followed by one 8-byte stack entry `00 00 00 01` (switch_id=1) + 4-byte ts
  + 2-byte qdepth + 2 bytes padding, and `count` byte = 1, `length` byte = 8.

## On success
Update `tasks/TASKS.md` (task 3 DONE) → task 04.
