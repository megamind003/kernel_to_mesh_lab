use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};
use anyhow::{Result, Context};
use crate::carrier::CarrierPool;
use crate::crypto::Crypto;
use log::{info, debug};

pub const BLOCK_SIZE: usize = 4096;
pub const MAGIC: u64 = 0x47484F5354465331; // GHOSTFS1

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Superblock {
    pub magic: u64,
    pub metadata_len: u64,
    pub salt: [u8; 16],
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub enum FileType {
    File,
    Directory,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Inode {
    pub id: u64,
    pub mode: u16,
    pub uid: u32,
    pub gid: u32,
    pub size: u64,
    pub atime: u64,
    pub mtime: u64,
    pub ctime: u64,
    pub kind: FileType,
    pub blocks: Vec<u64>, // List of block indices
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Metadata {
    pub inodes: HashMap<u64, Inode>,
    pub root_inode: u64,
    pub next_inode_id: u64,
    pub directory_tree: HashMap<u64, HashMap<String, u64>>, // Parent Inode -> {Name -> Child Inode}
    pub free_blocks: Vec<u64>, // Bitmap might be better, but Vec is easier for now
    pub total_blocks: u64,
}

impl Metadata {
    pub fn new(total_blocks: u64) -> Self {
        let mut inodes = HashMap::new();
        let root_id = 1;
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
        
        inodes.insert(root_id, Inode {
            id: root_id,
            mode: 0o755,
            uid: 1000, // Default to 1000
            gid: 1000,
            size: 0,
            atime: now,
            mtime: now,
            ctime: now,
            kind: FileType::Directory,
            blocks: Vec::new(),
        });

        let mut directory_tree = HashMap::new();
        directory_tree.insert(root_id, HashMap::new());

        // Blocks 0 is Superblock.
        // We'll reserve some blocks for metadata initially, but dynamic is better.
        // For simplicity: Metadata is stored in blocks 1..N.
        // Data blocks start at N+1.
        // We'll initialize free_blocks later when we know how much space metadata takes.
        
        Metadata {
            inodes,
            root_inode: root_id,
            next_inode_id: 2,
            directory_tree,
            free_blocks: Vec::new(), // Populated on save/load or init
            total_blocks,
        }
    }
}

pub struct MetadataManager {
    pub metadata: Metadata,
    pub salt: [u8; 16],
}

impl MetadataManager {
    pub fn init(pool: &mut crate::carrier::CarrierPool, crypto: &Crypto, salt: [u8; 16]) -> Result<Self> {
        let total_bytes = pool.total_capacity_bytes;
        let total_blocks = (total_bytes / BLOCK_SIZE) as u64;
        
        let mut metadata = Metadata::new(total_blocks);
        
        // Initialize free blocks.
        // Reserve block 0 for Superblock.
        // Reserve blocks 1..100 for Metadata (arbitrary limit for now).
        // Realistically, we should calculate this.
        // Let's say blocks 0-255 are reserved.
        let reserved = 256;
        for i in reserved..total_blocks {
            metadata.free_blocks.push(i);
        }
        // Reverse so we pop from the end (lower indices first? No, higher. Doesn't matter).
        
        let mgr = MetadataManager { metadata, salt };
        mgr.save(pool, crypto)?;
        Ok(mgr)
    }

    pub fn load(pool: &crate::carrier::CarrierPool, password: &str) -> Result<Self> {
        // Read Superblock from Block 0
        let mut sb_buf = vec![0u8; BLOCK_SIZE];
        pool.read_bytes(0, &mut sb_buf)?;
        
        // Decrypt Superblock? 
        // Problem: We need salt to derive key to decrypt.
        // So Superblock must be unencrypted or salt must be plaintext.
        // The C code stored salt in plaintext in Superblock.
        // Let's assume Block 0 is: [Salt (16 bytes)] [Encrypted Superblock (Rest)]
        // Or just [Salt] [Encrypted Metadata Info].
        
        let mut salt = [0u8; 16];
        salt.copy_from_slice(&sb_buf[0..16]);
        
        let crypto = Crypto::new(password, &salt);
        
        // Decrypt the rest of Block 0
        let encrypted_sb = &sb_buf[16..];
        // We need to decrypt this. But wait, `crypto` uses block index for IV.
        // Let's use index 0 for this special block.
        // But `encrypt_block` expects full block.
        // Let's say Block 0 is encrypted with IV(0).
        // But the first 16 bytes are plaintext salt.
        // So we decrypt the whole block 0, ignore the first 16 bytes of plaintext?
        // No, that corrupts the first 16 bytes of ciphertext.
        
        // Better: Block 0 is NOT encrypted using the standard `encrypt_block`.
        // It contains: Salt (16) + Magic (8) + MetadataLen (8) + Padding.
        // Only Magic and Len need protection? 
        // Actually, if we want to hide the FS existence, Block 0 should look like random noise.
        // But we need the Salt.
        // If Salt is random, it looks like noise.
        // So: Block 0 = Salt (16) + Encrypted(Magic + MetadataLen + Padding).
        // Encrypted part uses Key derived from Password + Salt.
        // IV can be derived from Salt too.
        
        // Let's stick to the C implementation's spirit but fix it.
        // C: `memcpy(fs->sb.salt, crypto_ctx.salt, 16);`
        // It wrote the superblock to the buffer.
        
        // My Plan:
        // Block 0:
        // Bytes 0-15: Salt (Plaintext)
        // Bytes 16-4095: Encrypted payload (Magic, MetadataLen).
        // Payload encrypted with Key(Pass, Salt) and IV(Hash(Salt)).
        
        // Decrypt payload
        let iv_seed = salt; // Use salt as seed for IV
        // Actually `crypto` struct handles IV generation by block index.
        // Let's just use `crypto.decrypt_block(0, &full_block0)`?
        // If we overwrite the first 16 bytes with Salt *after* encryption?
        // No.
        
        // Let's just read the salt first.
        // Then reconstruct crypto.
        // Then decrypt block 0 (assuming the whole block was encrypted, but we overwrote the first 16 bytes with plaintext salt).
        // This means the first 16 bytes of decrypted data are garbage.
        // But Magic and Len are stored after that.
        
        let decrypted_sb_block = crypto.decrypt_block(0, &sb_buf)?;
        
        // Parse Superblock from decrypted data (offset 16)
        // Wait, if I overwrote the first 16 bytes of ciphertext with salt, I can't decrypt the first block correctly if it's one chain (CBC).
        // If I use ECB or CTR, I can.
        // If I use CBC, the first block is corrupted.
        // But `Aes256Cbc` decrypts 16-byte blocks.
        // If I overwrite bytes 0-15 (first block), the first block decryption is garbage.
        // The second block (bytes 16-31) decryption depends on the first block of ciphertext (which is now Salt).
        // So it works! The first block of plaintext is lost, but subsequent blocks are fine (using Salt as previous ciphertext).
        // So Magic must be at offset 16 or later.
        
        let magic_bytes = &decrypted_sb_block[16..24];
        let magic = u64::from_le_bytes(magic_bytes.try_into()?);
        
        if magic != MAGIC {
            anyhow::bail!("Invalid password or not a GhostFS filesystem");
        }
        
        let len_bytes = &decrypted_sb_block[24..32];
        let metadata_len = u64::from_le_bytes(len_bytes.try_into()?);
        
        // Read Metadata Blocks
        let num_metadata_blocks = (metadata_len + BLOCK_SIZE as u64 - 1) / BLOCK_SIZE as u64;
        let mut metadata_bytes = Vec::new();
        
        for i in 0..num_metadata_blocks {
            let block_idx = 1 + i; // Metadata starts at Block 1
            let mut buf = vec![0u8; BLOCK_SIZE];
            pool.read_bytes((block_idx * BLOCK_SIZE as u64) as usize, &mut buf)?;
            let decrypted = crypto.decrypt_block(block_idx, &buf)?;
            metadata_bytes.extend_from_slice(&decrypted);
        }
        
        metadata_bytes.truncate(metadata_len as usize);
        
        let metadata: Metadata = bincode::deserialize(&metadata_bytes)?;
        
        Ok(MetadataManager { metadata, salt })
    }

    pub fn save(&self, pool: &mut crate::carrier::CarrierPool, crypto: &Crypto) -> Result<()> {
        // Serialize Metadata
        let metadata_bytes = bincode::serialize(&self.metadata)?;
        let metadata_len = metadata_bytes.len() as u64;
        
        // Write Superblock (Block 0)
        let mut sb_payload = vec![0u8; BLOCK_SIZE];
        // We want Magic at offset 16, Len at 24.
        sb_payload[16..24].copy_from_slice(&MAGIC.to_le_bytes());
        sb_payload[24..32].copy_from_slice(&metadata_len.to_le_bytes());
        
        // Encrypt Block 0
        let encrypted_sb = crypto.encrypt_block(0, &sb_payload)?;
        
        // Overwrite first 16 bytes with Salt
        let mut final_sb = encrypted_sb;
        final_sb[0..16].copy_from_slice(&self.salt);
        
        pool.write_bytes(0, &final_sb)?;
        
        // Write Metadata Blocks (starting at Block 1)
        let chunks = metadata_bytes.chunks(BLOCK_SIZE);
        for (i, chunk) in chunks.enumerate() {
            let block_idx = 1 + i as u64;
            let mut block_data = vec![0u8; BLOCK_SIZE];
            block_data[0..chunk.len()].copy_from_slice(chunk);
            // Encrypt
            let encrypted = crypto.encrypt_block(block_idx, &block_data)?;
            pool.write_bytes((block_idx * BLOCK_SIZE as u64) as usize, &encrypted)?;
        }
        
        Ok(())
    }
}
