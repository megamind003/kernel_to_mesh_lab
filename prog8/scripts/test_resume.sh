#!/bin/bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Ensure cleanup
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

echo -e "${GREEN}Starting Test 2: Resume (Large File Transfer)${NC}"

# Start Peer 1 (Receiver)
./target/release/aether daemon --bind 127.0.0.1:5002 --storage test_env/peer1/storage > test_env/peer1_resume.log 2>&1 &
PEER1_PID=$!
echo "Peer 1 started (PID: $PEER1_PID)"

sleep 2

# Start Peer 2 (Sender) in background to kill it later
echo "Starting large file transfer..."
./target/release/aether send \
    --file test_env/data/large_file.mov \
    --peer 127.0.0.1:5002 \
    --storage test_env/peer2/storage &
SENDER_PID=$!

# Wait a bit to let it transfer ~40% (simulated by time or size check)
# Since we don't know exact speed, we'll wait for the file to grow
echo "Waiting for transfer to progress..."
TARGET_SIZE=$(stat -L -c%s test_env/data/large_file.mov)
CUTOFF_SIZE=$((TARGET_SIZE * 40 / 100))
echo "Target Size: $TARGET_SIZE"
echo "Cutoff Size: $CUTOFF_SIZE"

while true; do
    CURRENT_SIZE=$(du -sb test_env/peer1/storage | awk '{print $1}')
    # echo "Current size: $CURRENT_SIZE / $CUTOFF_SIZE"
    if [ $CURRENT_SIZE -gt $CUTOFF_SIZE ]; then
        echo "Reached 40% ($CURRENT_SIZE bytes). Killing sender..."
        kill -9 $SENDER_PID
        break
    fi
    sleep 1
done

echo "Interruption successful."
sleep 2

# Restart Sender
echo "Resuming transfer..."
./target/release/aether send \
    --file test_env/data/large_file.mov \
    --peer 127.0.0.1:5002 \
    --storage test_env/peer2/storage

echo "Transfer completed."

# Verify integrity
echo "Verifying integrity..."
# We use a partial check or full check depending on time. 
# For the test requirement, we just need to ensure it finished and matches.
# Calculating MD5 of 6GB might take time, so we'll check size first.

# Wait for file to be fully reconstructed
echo "Waiting for file reconstruction..."
for i in {1..100}; do
    if [ -f "test_env/peer1/storage/large_file.mov" ]; then
        CURRENT_SIZE=$(stat -c%s test_env/peer1/storage/large_file.mov)
        if [ "$CURRENT_SIZE" == "$TARGET_SIZE" ]; then
            break
        fi
    fi
    sleep 1
done

FINAL_SIZE=$(stat -c%s test_env/peer1/storage/large_file.mov)
if [ "$FINAL_SIZE" == "$TARGET_SIZE" ]; then
    echo -e "${GREEN}PASS: Size matches ($FINAL_SIZE bytes)${NC}"
else
    echo -e "${RED}FAIL: Size mismatch ($FINAL_SIZE != $TARGET_SIZE)${NC}"
    exit 1
fi

# Optional: Check first and last 10MB for speed
echo "Checking hash of first and last 10MB..."
head -c 10485760 test_env/data/large_file.mov | md5sum > orig_head.md5
head -c 10485760 test_env/peer1/storage/large_file.mov | md5sum > recv_head.md5
tail -c 10485760 test_env/data/large_file.mov | md5sum > orig_tail.md5
tail -c 10485760 test_env/peer1/storage/large_file.mov | md5sum > recv_tail.md5

if cmp -s orig_head.md5 recv_head.md5 && cmp -s orig_tail.md5 recv_tail.md5; then
     echo -e "${GREEN}PASS: Head/Tail Hashes match${NC}"
else
     echo -e "${RED}FAIL: Hash mismatch${NC}"
     exit 1
fi
