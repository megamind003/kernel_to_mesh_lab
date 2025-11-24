#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Ensure cleanup
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

echo -e "${GREEN}Starting Test 1: Ping (Small File Transfer)${NC}"

# Setup environment
./scripts/test_setup.sh

echo "Checking test_env:"
ls -R test_env

# Start Peer 1 (Receiver)
./target/release/aether daemon --bind 127.0.0.1:5001 --storage test_env/peer1/storage > test_env/peer1.log 2>&1 &
PEER1_PID=$!
echo "Peer 1 started (PID: $PEER1_PID)"

sleep 2

# Start Peer 2 (Sender)
# We'll use the send command directly
echo "Sending small file..."
START_TIME=$(date +%s%N)

./target/release/aether send --file test_env/data/small_file.tar.gz --peer 127.0.0.1:5001 --storage test_env/sender_storage > test_env/sender.log 2>&1

END_TIME=$(date +%s%N)
DURATION=$((($END_TIME - $START_TIME) / 1000000))

echo "Transfer took ${DURATION}ms"

# Verify file
# Wait for file to appear (max 5 seconds)
for i in {1..50}; do
    if [ -f "test_env/peer1/storage/small_file.tar.gz" ]; then
        break
    fi
    sleep 0.1
done

if [ -f "test_env/peer1/storage/small_file.tar.gz" ]; then
    echo "PASS: File received"
    
    # Verify hash
    ORIG_HASH=$(sha256sum test_env/data/small_file.tar.gz | awk '{print $1}')
    RECV_HASH=$(sha256sum test_env/peer1/storage/small_file.tar.gz | awk '{print $1}')
    
    if [ "$ORIG_HASH" == "$RECV_HASH" ]; then
        echo "PASS: Hash matches"
        exit 0
    else
        echo "FAIL: Hash mismatch"
        echo "Original: $ORIG_HASH"
        echo "Received: $RECV_HASH"
        exit 1
    fi
else
    echo -e "${RED}FAIL: File not received${NC}"
    exit 1
fi
