#!/bin/bash
set -e

IMAGES_DIR="./tmp/titan/images"
IMAGE_NAME="busybox"
ROOTFS="$IMAGES_DIR/$IMAGE_NAME"

rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"/{bin,proc,sys,dev,etc,tmp}

# Copy busybox
if [ -f /usr/bin/busybox ]; then
    cp /usr/bin/busybox "$ROOTFS/bin/busybox"
else
    echo "Error: busybox not found"
    exit 1
fi

# Create symlinks
cd "$ROOTFS/bin"
for cmd in sh ls ps mount hostname cat echo sleep ip ping ifconfig route; do
    ln -s busybox $cmd
done

echo "Base Image created at $ROOTFS"
