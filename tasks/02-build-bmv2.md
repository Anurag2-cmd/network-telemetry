# Task 02: Build BMv2 (behavioral-model) with P4Runtime/gRPC

## Goal
Install BMv2 so these binaries exist: `simple_switch`, `simple_switch_grpc`, `simple_switch_CLI`.

## Context
- Repo cloned at `~/p4tools/behavioral-model` (submodules included).
- Deps installed: libnanomsg, libevent, libpcap, libssl, libgrpc, protobuf, thrift?? NOT INSTALLED (see below).
- Build time ~15-30 min on 16 cores. MUST run inside tmux.

## Steps
1. Install the two missing deps (thrift + boost via apt — required by BMv2):
   ```bash
   sudo apt-get install -y libthrift-dev python3-thrift
   ```
   (boost, gmp, pcap, grpc, protobuf already installed in task-0 setup.)
2. Clean + configure + build in tmux:
   ```bash
   pkill -9 -f "behavioral-model" || true
   tmux kill-session -t bmbuild 2>/dev/null || true
   cd ~/p4tools/behavioral-model && tmux new-session -d -s bmbuild \
     "./autogen.sh && ./configure --with-pi --with-nanomsg --with-thrift --enable-debugger && make -j16 && sudo make install && sudo ldconfig && echo '=== BMV2 COMPLETE ===' 2>&1 | tee /tmp/bmv2-build.log"
   ```
   Note: `--with-pi` enables P4Runtime (needed for gNMI task 09) and pulls
   in grpc deps. If `--with-pi` configure fails on missing grpc dev files,
   reinstall: `sudo apt-get install -y libgrpc-dev libgrpc++-dev protobuf-compiler-grpc libprotobuf-dev`.
3. Poll: `wsl -d Ubuntu -- bash -c "tail -3 /tmp/bmv2-build.log; tmux ls"`
   Expect `=== BMV2 COMPLETE ===`.

## Verification (Definition of Done)
```bash
which simple_switch simple_switch_grpc simple_switch_CLI
simple_switch --version
simple_switch_grpc --version
```
All three must resolve. `simple_switch_grpc --help` should show a `--grpc-server-addr` flag
(proves P4Runtime is compiled in).

## Troubleshooting
- `configure: error: cannot find libthrift` → apt install `libthrift-dev` first.
- gRPC version mismatch errors → fine to proceed if configure succeeded; grpc 1.51 vs
  generated protos may warn only.
- `make install` permission denied → use `sudo make install` + `sudo ldconfig`.

## On success
Update `tasks/TASKS.md` (task 2 DONE) → task 03.
