#!/bin/bash
# Task 02: Build BMv2 (behavioral-model) with P4Runtime/gRPC support.
# Run inside tmux:  tmux new-session -d -s bmbuild 'bash /path/to/build-bmv2.sh 2>&1 | tee /tmp/bmv2-build.log'
set -e

cd ~/p4tools/behavioral-model

echo "=== autogen.sh ==="
./autogen.sh

echo "=== configure ==="
./configure --with-pi --with-nanomsg --with-thrift --enable-debugger

echo "=== make -j16 ==="
make -j16

echo "=== make install ==="
sudo make install
sudo ldconfig

echo "=== BMV2 COMPLETE ==="
