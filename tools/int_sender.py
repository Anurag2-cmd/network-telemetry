"""INT sender (Task 5): streams INT-marked UDP/4000 packets.

  python3 tools/int_sender.py 10.0.1.2          # 60s, 10 pkt/s
  python3 tools/int_sender.py 10.0.1.2 --burst  # 1000 pkts back-to-back in ~1s
"""

import argparse
import socket
import struct
import time

INT_HDR = struct.pack("!I", 0xF0000000)  # ver=0xF, count=0, length=0, ins=0


def main():
    ap = argparse.ArgumentParser(description="INT sender")
    ap.add_argument("dst", help="destination IP (e.g. 10.0.1.2)")
    ap.add_argument("--burst", action="store_true",
                    help="1000 packets back-to-back (queue-occupancy demo)")
    ap.add_argument("--duration", type=float, default=60.0,
                    help="loop duration in seconds (ignored with --burst)")
    ap.add_argument("--pps", type=float, default=10.0,
                    help="packets per second (ignored with --burst)")
    args = ap.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    i = 0
    if args.burst:
        t0 = time.time()
        for i in range(1000):
            s.sendto(INT_HDR + b"burst-%d" % i, (args.dst, 4000))
        print("burst done: 1000 pkts in %.3fs" % (time.time() - t0))
        return

    interval = 1.0 / args.pps
    t_end = time.time() + args.duration
    while time.time() < t_end:
        s.sendto(INT_HDR + b"payload-%d" % i, (args.dst, 4000))
        i += 1
        time.sleep(interval)
    print("sent %d packets to %s:4000 over %.0fs" % (i, args.dst, args.duration))


if __name__ == "__main__":
    main()
