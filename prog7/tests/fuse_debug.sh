#!/bin/bash

# Manual FUSE debug test - Run in foreground with debug output

cd /home/boss/Documents/prog/prog7

# Cleanup
fusermount -u tests/mount 2>/dev/null || true
rm -rf tests/carriers/test tests/mount
mkdir -p tests/carriers/test tests/mount

# Copy 5 carriers
count=0
for png in /home/boss/Documents/prog/data_hardcore/archive/all_images/images/*.png; do
    if [ $count -ge 5 ]; then break; fi
    cp "$png" tests/carriers/test/
    count=$((count + 1))
done

echo "========================================"
echo "FUSE Debug Mode - Running in foreground"
echo "In another terminal run:"
echo "  touch /home/boss/Documents/prog/prog7/tests/mount/test.txt"
echo "========================================"
echo ""

./bin/ghostfs tests/carriers/test tests/mount -f -d -o password=test
