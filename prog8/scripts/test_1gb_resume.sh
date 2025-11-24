#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

echo -e "${GREEN}Testing 1GB File Transfer with Resume${NC}"

# Create test directory
rm -rf test_env_1gb
mkdir -p test_env_1gb/peer1/storage
mkdir -p test_env_1gb/peer2/storage
mkdir -p test_env_1gb/data

# Create 1GB test file
echo "Creating 1GB test file..."
dd if=/dev/urandom of=test_env_1gb/data/test_1gb.bin bs=1M count=1024 2>/dev/null

TARGET_SIZE=$(stat -L -c%s test_env_1gb/data/test_1gb.bin)
CUTOFF_SIZE=$((TARGET_SIZE * 40 / 100))

echo "Target Size: $TARGET_SIZE"
echo "Cutoff Size (40%): $CUTOFF_SIZE"

# Start receiver
./target/release/aether daemon --bind 127.0.0.1:5004 --storage test_env_1gb/peer1/storage >test_env_1gb/peer1.log 2>&1 &
PEER1_PID=$!
echo "Peer 1 started (PID: $PEER1_PID)"

sleep 2

# Start sender in background
echo "Starting transfer..."
./target/release/aether send --file test_env_1gb/data/test_1gb.bin --peer 127.0.0.1:5004 --storage test_env_1gb/peer2/storage >test_env_1gb/sender1.log 2>&1 &
SENDER_PID=$!

# Wait for 40%
echo "Waiting for 40% progress..."
while true; do
    CURRENT_SIZE=$(du -sb test_env_1gb/peer1/storage 2>/dev/null | awk '{print $1}' || echo 0)
    if [ $CURRENT_SIZE -gt $CUTOFF_SIZE ]; then
        echo "Reached 40% ($CURRENT_SIZE bytes). Killing sender..."
        kill -9 $SENDER_PID 2>/dev/null || true
        break
    fi
    sleep 1
done

echo "Interruption successful."
sleep 2

# Resume
echo "Resuming transfer..."
./target/release/aether send --file test_env_1gb/data/test_1gb.bin --peer 127.0.0.1:5004 --storage test_env_1gb/peer2/storage >test_env_1gb/sender2.log 2>&1

echo "Transfer completed."

# Verify
sleep 2
if [ -f "test_env_1gb/peer1/storage/test_1gb.bin" ]; then
    FINAL_SIZE=$(stat -c%s test_env_1gb/peer1/storage/test_1gb.bin)
    if [ "$FINAL_SIZE" == "$TARGET_SIZE" ]; then
        echo -e "${GREEN}PASS: Size matches ($FINAL_SIZE bytes)${NC}"
        
        # Quick hash check of first/last 10MB
        head -c 10485760 test_env_1gb/data/test_1gb.bin | md5sum >orig_head.md5
        head -c 10485760 test_env_1gb/peer1/storage/test_1gb.bin | md5sum >recv_head.md5
        tail -c 10485760 test_env_1gb/data/test_1gb.bin | md5sum >orig_tail.md5
        tail -c 10485760 test_env_1gb/peer1/storage/test_1gb.bin | md5sum >recv_tail.md5
        
        if cmp -s orig_head.md5 recv_head.md5 && cmp -s orig_tail.md5 recv_tail.md5; then
            echo -e "${GREEN}PASS: Head/Tail hashes match${NC}"
            exit 0
        else
            echo -e "${RED}FAIL: Hash mismatch${NC}"
            exit 1
        fi
    else
        echo -e "${RED}FAIL: Size mismatch ($FINAL_SIZE != $TARGET_SIZE)${NC}"
        exit 1
    fi
else
    echo -e "${RED}FAIL: File not received${NC}"
    exit 1
fi
