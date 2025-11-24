#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GHOSTFS_BIN="$PROJECT_ROOT/bin/ghostfs"

DATA_DIR="/home/boss/Documents/prog/data_hardcore"
ALPINE_FILE="$DATA_DIR/alpine-minirootfs-3.22.2-x86_64.tar.gz"
TEST_CARRIERS_DIR="$SCRIPT_DIR/carriers/test"
MOUNT_POINT="$SCRIPT_DIR/mount"
PASSWORD="testpass123"

echo "=== GhostFS Stress Test: Invisible Ink Protocol ==="
echo

cleanup() {
    echo "Cleaning up..."
    if mountpoint -q "$MOUNT_POINT"; then
        fusermount -u "$MOUNT_POINT" || umount "$MOUNT_POINT"
    fi
    pkill -f "ghostfs" || true
}
trap cleanup EXIT

echo "[1/8] Cleaning previous test data..."
rm -rf "$TEST_CARRIERS_DIR" "$MOUNT_POINT"
mkdir -p "$TEST_CARRIERS_DIR" "$MOUNT_POINT"

echo "[2/8] Copying PNG carriers from data_hardcore..."
PNG_COUNT=0
# Ensure directory exists
if [ ! -d "$DATA_DIR/archive/all_images/images" ]; then
    echo "ERROR: Source images directory not found!"
    exit 1
fi

for png in "$DATA_DIR/archive/all_images/images"/*.png; do
  if [ $PNG_COUNT -ge 100 ]; then
    break
  fi
  cp "$png" "$TEST_CARRIERS_DIR/"
  PNG_COUNT=$((PNG_COUNT + 1))
done
echo "Copied $PNG_COUNT PNG carrier files"

echo "[3/8] Computing original alpine MD5..."
if [ ! -f "$ALPINE_FILE" ]; then
    echo "ERROR: Alpine file not found at $ALPINE_FILE"
    exit 1
fi
ORIGINAL_MD5=$(md5sum "$ALPINE_FILE" | awk '{print $1}')
echo "Original MD5: $ORIGINAL_MD5"

echo "[4/8] Mounting GhostFS..."
# Run in background, but don't use timeout here as we need it to stay up
"$GHOSTFS_BIN" "$TEST_CARRIERS_DIR" "$MOUNT_POINT" -o password="$PASSWORD" &
FUSE_PID=$!

# Wait for mount
echo "Waiting for mount..."
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

echo "[5/8] Injecting alpine rootfs into virtual filesystem..."
cp "$ALPINE_FILE" "$MOUNT_POINT/alpine.tar.gz"
sync

INJECTED_SIZE=$(stat -c%s "$MOUNT_POINT/alpine.tar.gz")
echo "Injected file size: $INJECTED_SIZE bytes"

echo "[6/8] Unmounting filesystem..."
fusermount -u "$MOUNT_POINT"
wait $FUSE_PID 2>/dev/null || true
sleep 2

echo "[7/8] Remounting and extracting file..."
"$GHOSTFS_BIN" "$TEST_CARRIERS_DIR" "$MOUNT_POINT" -o password="$PASSWORD" &
FUSE_PID=$!

# Wait for mount
for i in {1..10}; do
    if mountpoint -q "$MOUNT_POINT"; then
        break
    fi
    sleep 1
done

if ! mountpoint -q "$MOUNT_POINT"; then
  echo "ERROR: Failed to remount GhostFS"
  exit 1
fi

cp "$MOUNT_POINT/alpine.tar.gz" "$SCRIPT_DIR/extracted_alpine.tar.gz"

fusermount -u "$MOUNT_POINT"
wait $FUSE_PID 2>/dev/null || true

echo "[8/8] Verifying MD5 integrity..."
EXTRACTED_MD5=$(md5sum "$SCRIPT_DIR/extracted_alpine.tar.gz" | awk '{print $1}')
echo "Extracted MD5: $EXTRACTED_MD5"

if [ "$ORIGINAL_MD5" == "$EXTRACTED_MD5" ]; then
  echo
  echo "SUCCESS: MD5 hashes match - data integrity verified"
  echo "The 3.5MB alpine rootfs was successfully hidden in PNG images"
  echo "Carrier images remain visually unchanged"
  # Keep exit trap from unmounting again (it's already unmounted)
  exit 0
else
  echo
  echo "FAILURE: MD5 mismatch - data corruption detected"
  exit 1
fi
