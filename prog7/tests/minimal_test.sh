#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GHOSTFS_BIN="$PROJECT_ROOT/bin/ghostfs"

DATA_DIR="/home/boss/Documents/prog/data_hardcore"
TEST_CARRIERS_DIR="$SCRIPT_DIR/carriers/test"
MOUNT_POINT="$SCRIPT_DIR/mount"
PASSWORD="testpass123"

echo "=== GhostFS Minimal Test ==="

cleanup() {
    echo "Cleaning up..."
    if mountpoint -q "$MOUNT_POINT"; then
        fusermount -u "$MOUNT_POINT" || umount "$MOUNT_POINT"
    fi
    pkill -f "ghostfs" || true
}
trap cleanup EXIT

echo "[1/5] Cleaning previous test data..."
rm -rf "$TEST_CARRIERS_DIR" "$MOUNT_POINT"
mkdir -p "$TEST_CARRIERS_DIR" "$MOUNT_POINT"

echo "[2/5] Copying PNG carriers..."
PNG_COUNT=0
for png in "$DATA_DIR/archive/all_images/images"/*.png; do
  if [ $PNG_COUNT -ge 10 ]; then
    break
  fi
  cp "$png" "$TEST_CARRIERS_DIR/"
  PNG_COUNT=$((PNG_COUNT + 1))
done
echo "Copied $PNG_COUNT PNG carrier files"

echo "[3/5] Mounting GhostFS..."
"$GHOSTFS_BIN" "$TEST_CARRIERS_DIR" "$MOUNT_POINT" -o password="$PASSWORD" &
FUSE_PID=$!

for i in {1..10}; do
    if mountpoint -q "$MOUNT_POINT"; then
        echo "Mounted successfully."
        break
    fi
    sleep 1
done

if ! mountpoint -q "$MOUNT_POINT"; then
  echo "ERROR: Failed to mount GhostFS"
  exit 1
fi

echo "[4/5] Testing file creation..."
echo "Creating empty file..."
if ! touch "$MOUNT_POINT/testfile.txt" 2>&1; then
    echo "ERROR: Failed to create file"
    exit 1
fi
echo "File created successfully"

echo "Writing small data..."
if ! echo "Hello World" > "$MOUNT_POINT/testfile.txt" 2>&1; then
    echo "ERROR: Failed to write data"
    exit 1
fi
echo "Data written successfully"

echo "Reading back..."
CONTENT=$(cat "$MOUNT_POINT/testfile.txt")
echo "Read: $CONTENT"

echo "[5/5] Unmounting..."
fusermount -u "$MOUNT_POINT"
wait $FUSE_PID 2>/dev/null || true

echo
echo "SUCCESS: Basic file operations work!"
