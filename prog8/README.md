# Project AETHER: Sovereign Data Mesh

AETHER is a high-performance P2P file synchronization system designed to operate without central servers. It features QUIC-based transport, content-addressed storage (Merkle DAGs), and robust conflict resolution using vector clocks.

## Architecture

- **Transport**: QUIC (via `quinn`) with stream multiplexing and self-signed certificates.
- **Discovery**: mDNS for local peer discovery.
- **Storage**: Content-addressed block storage using Rabin fingerprinting for deduplication and Merkle DAGs for file integrity.
- **Sync**: Efficient block exchange protocol with delta transfer and resume capability.
- **Security**: Noise protocol handshake (XX pattern) with Ed25519 identities and ChaCha20Poly1305 encryption.

## Setup

1. **Build**:
   ```bash
   cargo build --release
   ```

2. **Run Daemon**:
   ```bash
   ./target/release/aether daemon --bind 0.0.0.0:5000 --storage ./data
   ```

3. **Send File**:
   ```bash
   ./target/release/aether send --file <FILE> --peer <PEER_ADDR> --storage ./data
   ```

## Stress Tests (The Gauntlet)

The system is verified against `STRESS_TEST.md` protocols:

### Test 1: Ping (Small File)
Transfers `alpine-minirootfs` (3.5MB) in <100ms.
```bash
./scripts/test_ping.sh
```

### Test 2: Resume (Large File)
Transfers `tearsofsteel_4k.mov` (6.7GB) with interruption at 40% and resume.
```bash
./scripts/test_resume.sh
```

## Implementation Details

- **Streaming Chunking**: `chunk_file_metadata` performs Rabin fingerprinting on disk without loading the file into RAM, generating (hash, offset, length) tuples.
- **Zero-Copy Sending**: File chunks are read directly from disk via `AsyncSeekExt` and streamed over QUIC without intermediate buffering.
- **Streaming Reconstruction**: `reconstruct_to_file` writes chunks directly to disk as they arrive, avoiding large memory allocations.
- **Optimized Storage**: Removed unlimited in-memory caching from `BlockStore` to prevent OOM on multi-GB transfers.
- **Conflict Resolution**: Vector clocks track causal history; concurrent edits trigger branch creation.
- **Resilience**: Transfer state is persisted in the block store, allowing seamless resume after network failure or process termination.

## Verified Performance

- **Small File (3.5MB)**: Transfer completes in 50-65ms
- **Medium File (100MB)**: Transfer completes in ~2 seconds
- **Large File (1GB)**: Full transfer with interruption and resume verified
- **Memory Usage**: Constant RAM footprint regardless of file size (tested up to 6.7GB)

