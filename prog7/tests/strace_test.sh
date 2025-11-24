#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== GhostFS Strace Debug Test ==="

# Cleanup
fusermount -u "$SCRIPT_DIR/mount" 2>/dev/null || true
pkill -f ghostfs || true
rm -rf "$SCRIPT_DIR/carriers/test" "$SCRIPT_DIR/mount"
mkdir -p "$SCRIPT_DIR/carriers/test" "$SCRIPT_DIR/mount"

# Copy one carrier
cp /home/boss/Documents/prog/data_hardcore/archive/all_images/images/*.png "$SCRIPT_DIR/carriers/test/" 2>/dev/null | head -1 || true

# Mount in background
echo "Mounting GhostFS..."
"$PROJECT_ROOT/bin/ghostfs" "$SCRIPT_DIR/carriers/test" "$SCRIPT_DIR/mount" -o password=test &
FUSE_PID=$!

# Wait for mount
for i in {1..10}; do
    if mountpoint -q "$SCRIPT_DIR/mount"; then
        echo "Mounted."
        break
    fi
    sleep 1
done

if ! mountpoint -q "$SCRIPT_DIR/mount"; then
    echo "ERROR: Mount failed"
    exit 1
fi

echo "Running strace on touch..."
strace -e trace=file,desc -f touch "$SCRIPT_DIR/mount/test.txt" 2>&1 | grep -E "(open|creat|mknod|stat|access)" | head -20

# Cleanup
echo "Cleaning up..."
fusermount -u "$SCRIPT_DIR/mount" 2>/dev/null || true
wait $FUSE_PID 2>/dev/null || true
