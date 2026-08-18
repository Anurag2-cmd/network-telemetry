# Task 01: Finish building p4c (P4 compiler) and install

## Goal
Have `p4c` (and `p4c-bm2-ss`) on PATH inside WSL, verified with `p4c --version`.

## Context
- Repo cloned at `~/p4tools/p4c` (with submodules).
- A previous build was killed by the shell tool (Hangup) — there may be a
  stale `build/` dir and running cmake/make processes. Clean them first.
- All build dependencies are installed (cmake 4.2, gcc/g++ 15+16, bison, flex,
  libboost-all-dev, protobuf 3.21, nlohmann-json, rapidjson, libgmp, libfl, etc.).
- Build time: ~20-40 min on 16 cores. MUST run inside tmux.

## Steps
1. Clean stale state:
   ```bash
   pkill -9 -f "p4c" || true
   pkill -9 -f "frontend" || true
   rm -rf ~/p4tools/p4c/build
   ```
2. Start build in tmux (single command, survives disconnects):
   ```bash
   tmux kill-session -t p4build 2>/dev/null || true
   cd ~/p4tools/p4c && tmux new-session -d -s p4build \
     "mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=RELEASE -DENABLE_GTESTS=OFF -DENABLE_BMV2=ON && make -j16 && sudo make install && echo '=== P4C COMPLETE ===' 2>&1 | tee /tmp/p4c-build.log"
   ```
3. Poll until done (from PowerShell):
   `wsl -d Ubuntu -- bash -c "tail -3 /tmp/p4c-build.log; tmux ls"`
   Expect: `[100%]` lines then `=== P4C COMPLETE ===`. If the tmux session
   disappeared without COMPLETE, read `/tmp/p4c-build.log` for the error
   (missing dep → `sudo apt-get install -y <pkg>`, then rerun step 2).

## Verification (Definition of Done)
```bash
which p4c && p4c --version
p4c-bm2-ss --version
```
Both must print a version (e.g. `p4c 1.2.x`). `p4c-bm2-ss` MUST exist
(it is the BMv2 backend used in task 03).

## Troubleshooting
- `Could not find a package configuration file ... Protobuf` → `sudo apt-get install -y libprotobuf-dev protobuf-compiler`
- gRPC errors → `sudo apt-get install -y libgrpc-dev libgrpc++-dev protobuf-compiler-grpc`
- Submodule missing (`p4c/backends/...` errors) → `cd ~/p4tools/p4c && git submodule update --init --recursive`

## On success
Update the Status table in `tasks/TASKS.md` (mark task 1 DONE) and proceed to task 02.
