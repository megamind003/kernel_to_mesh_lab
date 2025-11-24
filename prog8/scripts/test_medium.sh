#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

echo -e "${GREEN}Testing Medium File Transfer (100MB)${NC}"

# Create test directory
rm -rf test_env_medium
mkdir -p test_env_medium/peer1/storage
mkdir -p test_env_medium/peer2/storage
mkdir -p test_env_medium/data

# Create 100MB test file
echo "Creating 100MB test file..."
dd if=/dev/urandom of=test_env_medium/data/test_100mb.bin bs=1M count=100 2>/dev/null

# Start receiver
./target/release/aether daemon --bind 127.0.0.1:5003 --storage test_env_medium/peer1/storage >test_env_medium/peer1.log 2>&1 &
PEER1_PID=$!
echo "Peer 1 started (PID: $PEER1_PID)"

sleep 2

# Send file
echo "Sending 100MB file..."
START_TIME=$(date +%s%N)

./target/release/aether send --file test_env_medium/data/test_100mb.bin --peer 127.0.0.1:5003 --storage test_env_medium/peer2/storage >test_env_medium/sender.log 2>&1

END_TIME=$(date +%s%N)
DURATION=$((($END_TIME - $START_TIME) / 1000000))

echo "Transfer took ${DURATION}ms"

# Verify
sleep 2
if [ -f "test_env_medium/peer1/storage/test_100mb.bin" ]; then
    ORIG_HASH=$(sha256sum test_env_medium/data/test_100mb.bin | awk '{print $1}')
    RECV_HASH=$(sha256sum test_env_medium/peer1/storage/test_100mb.bin | awk '{print $1}')
    
    if [ "$ORIG_HASH" == "$RECV_HASH" ]; then
        echo -e "${GREEN}PASS: 100MB file transferred correctly${NC}"
        exit 0
    else
        echo -e "${RED}FAIL: Hash mismatch${NC}"
        exit 1
    fi
else
    echo -e "${RED}FAIL: File not received${NC}"
    exit 1
fi
