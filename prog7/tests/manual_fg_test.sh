#!/bin/bash
# Quick manual test with FUSE foreground

cd /home/boss/Documents/prog/prog7

# Cleanup
fusermount -u tests/mount || true
rm -rf tests/carriers/test tests/mount
mkdir -p tests/carriers/test tests/mount

# Copy carriers
for png in /home/boss/Documents/prog/data_hardcore/archive/all_images/images/*.png; do
  cp "$png" tests/carriers/test/
  break # Just 1 for quick test
done

# Run FUSE in foreground (will block)
echo "Starting GhostFS in foreground. Press Ctrl+C after testing."
echo "In another terminal, run: touch /home/boss/Documents/prog/prog7/tests/mount/test.txt"
./bin/ghostfs tests/carriers/test tests/mount -f -o password=test
