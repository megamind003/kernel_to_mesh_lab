# GhostFS – Steganographic FUSE Filesystem

## Overview
GhostFS implements a plausible‑deniability filesystem that hides encrypted data inside the least‑significant bits of PNG images. It exposes a standard POSIX interface via FUSE, allowing you to mount a directory that transparently reads/writes to a pool of carrier images.

## Quick Start (Reproducibility)
1. **Install dependencies**
   ```bash
   sudo apt-get install -y libfuse-dev libpng-dev libssl-dev
   ```
2. **Build the project**
   ```bash
   cd /home/boss/Documents/prog/prog7
   make clean all
   ```
3. **Prepare a carrier pool** (use any PNG images, e.g. the provided sample set)
   ```bash
   mkdir -p tests/carriers/pool
   cp /home/boss/Documents/prog/data_hardcore/archive/all_images/images/*.png tests/carriers/pool/
   ```
4. **Mount the filesystem**
   ```bash
   mkdir -p tests/mount
   ./bin/ghostfs tests/carriers/pool tests/mount -o password=yourpassword -f -d
   ```
   *The `-f -d` flags run FUSE in the foreground with debug output, useful for troubleshooting.*
5. **Test basic operations**
   ```bash
   touch tests/mount/example.txt
   echo "Hello GhostFS" > tests/mount/example.txt
   cat tests/mount/example.txt
   ```
   If the commands succeed without `Input/output error`, the filesystem is functional.

## Stress Test (Invisible Ink)
The provided `stress_test.sh` automates the full protocol:
```bash
cd /home/boss/Documents/prog/prog7/tests
./stress_test.sh
```
It copies a payload (`alpine-minirootfs-3.22.2-x86_64.tar.gz`) into the carrier pool, then verifies the extracted MD5 hash.

## Configuration Highlights
- **Encryption**: AES‑256‑XTS (key size 64 bytes).
- **Key derivation**: PBKDF2‑HMAC‑SHA256 (100 000 iterations).
- **Block size**: 4 KB, automatically split across carriers.
- **Metadata**: Stored as a hidden fragment inside the carrier pool.

## Clean Up
```bash
fusermount -u tests/mount
rm -rf tests/mount tests/carriers/pool
```
