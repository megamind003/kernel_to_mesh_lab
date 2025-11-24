#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== GhostFS Basic Functional Test ==="

TEST_CARRIERS="/tmp/ghostfs_test_carriers"
MOUNT_POINT="/tmp/ghostfs_mount"
PASSWORD="test123"
GHOSTFS_BIN="$PROJECT_ROOT/bin/ghostfs"

echo "[1] Setup..."
rm -rf "$MOUNT_POINT"
mkdir -p "$MOUNT_POINT"

echo "[2] Mounting GhostFS..."
timeout 5 "$GHOSTFS_BIN" "$TEST_CARRIERS" "$MOUNT_POINT" -o password="$PASSWORD" -f &
FUSE_PID=$!
sleep 2

if ! mountpoint -q "$MOUNT_POINT"; then
  echo "FAIL: Mount failed"
  kill $FUSE_PID 2>/dev/null || true
  exit 1
fi

echo "[3] Writing test file..."
echo "GhostFS Test Data - $(date)" > "$MOUNT_POINT/test.txt"
sync
sleep 1

echo "[4] Reading test file..."
if cat "$MOUNT_POINT/test.txt" | grep -q "GhostFS Test Data"; then
  echo "SUCCESS: File written and read successfully"
else
  echo "FAIL: Cannot read test file"
  fusermount -u "$MOUNT_POINT" 2>/dev/null || true
  exit 1
fi

echo "[5] Cleanup..."
fusermount -u "$MOUNT_POINT" || umount "$MOUNT_POINT"
wait  $FUSE_PID 2>/dev/null || true

echo
echo "Basic functional test PASSED"
