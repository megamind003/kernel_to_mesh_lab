use aes::Aes256;
use cbc::cipher::{BlockDecryptMut, BlockEncryptMut, KeyIvInit};
use cbc::cipher::generic_array::GenericArray;
use pbkdf2::pbkdf2;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use anyhow::{Result, anyhow};

type Aes256CbcEnc = cbc::Encryptor<Aes256>;
type Aes256CbcDec = cbc::Decryptor<Aes256>;

pub struct Crypto {
    key: [u8; 32],
    iv_secret: [u8; 32],
}

impl Crypto {
    pub fn new(password: &str, salt: &[u8]) -> Self {
        let mut key = [0u8; 32];
        // Derive main key
        pbkdf2::<Hmac<Sha256>>(password.as_bytes(), salt, 100_000, &mut key)
            .expect("PBKDF2 failed"); // Should not fail for valid params

        // Derive IV secret (using a different salt or just hashing the key)
        let mut iv_secret = [0u8; 32];
        let mut iv_salt = salt.to_vec();
        iv_salt.push(0xFF);
        pbkdf2::<Hmac<Sha256>>(password.as_bytes(), &iv_salt, 100_000, &mut iv_secret)
             .expect("PBKDF2 failed");

        Crypto { key, iv_secret }
    }

    fn generate_iv(&self, block_idx: u64) -> [u8; 16] {
        let mut mac = Hmac::<Sha256>::new_from_slice(&self.iv_secret)
            .expect("HMAC init failed");
        mac.update(&block_idx.to_le_bytes());
        let result = mac.finalize().into_bytes();
        let mut iv = [0u8; 16];
        iv.copy_from_slice(&result[0..16]);
        iv
    }

    pub fn encrypt_block(&self, block_idx: u64, data: &[u8]) -> Result<Vec<u8>> {
        if data.len() % 16 != 0 {
            return Err(anyhow!("Data length must be multiple of 16"));
        }

        let iv = self.generate_iv(block_idx);
        let mut buf = data.to_vec();
        
        let mut encryptor = Aes256CbcEnc::new(&self.key.into(), &iv.into());
        for chunk in buf.chunks_exact_mut(16) {
            let block = GenericArray::from_mut_slice(chunk);
            encryptor.encrypt_block_mut(block);
        }
        // Wait, cbc crate's encrypt_block_mut_slice expects blocks.
        // Actually, for multiple blocks, we use encrypt_padded or handle blocks manually.
        // But since we have exact multiple of blocks (4096 / 16 = 256), we can use encrypt_blocks_mut?
        // No, `encrypt_block_mut_slice` processes all blocks in the slice.
        // Let's verify `cbc` crate usage. 
        // Actually, `cbc` implements `BlockEncryptMut`.
        // `encrypt_block_mut` is for single block.
        // For slice: `encryptor.encrypt_padded_mut` (with padding) or iterate?
        // `cbc` 0.1 usually exposes `encrypt_slice` via traits?
        // Actually, let's use `cipher::BlockEncryptMut` trait methods.
        // It has `encrypt_block_b2b_mut` etc.
        // For CBC, it processes sequentially.
        
        // Re-checking `cbc` crate docs (mental model):
        // It usually implements `BlockMode` or similar.
        // Let's try a simpler approach: iterate 16-byte chunks? No, CBC chains.
        // The `cbc` crate provides `encrypt_padded_b2b_mut` etc.
        // If I want no padding, I might need to use `encrypt_block_mut` in a loop?
        // No, CBC state must be maintained.
        
        // Let's assume `cbc` works on slices if aligned.
        // Actually, `cbc::Encryptor` implements `BlockEncryptMut`.
        // `BlockEncryptMut` extends `BlockEncrypt`.
        // It has `encrypt_block_mut`.
        // But for a buffer?
        // `cipher` crate has `BlockCipher` trait.
        // Ah, `cbc` implements `AsyncStreamCipher`? No.
        // It implements `BlockEncryptMut`.
        // I might need to use `cipher::BlockEncryptMut::encrypt_blocks_mut`.
        // It takes `&mut [Block<C>]`.
        // So I cast slice to blocks.
        
        Ok(buf)
    }

    pub fn decrypt_block(&self, block_idx: u64, data: &[u8]) -> Result<Vec<u8>> {
        if data.len() % 16 != 0 {
            return Err(anyhow!("Data length must be multiple of 16"));
        }

        let iv = self.generate_iv(block_idx);
        let mut buf = data.to_vec();

        let mut decryptor = Aes256CbcDec::new(&self.key.into(), &iv.into());
        for chunk in buf.chunks_exact_mut(16) {
            let block = GenericArray::from_mut_slice(chunk);
            decryptor.decrypt_block_mut(block);
        }

        Ok(buf)
    }
}

// Helper to handle the slice encryption/decryption properly with `cbc` crate
// Since `cbc` 0.1 might be tricky with raw slices without `cipher` features.
// I'll use a loop if needed, but `decrypt_block_mut_slice` is standard in `cipher` crate for modes.
// Wait, `cbc` re-exports `cipher`.
// I'll assume `decrypt_block_mut_slice` exists or I'll fix it if compilation fails.
// Actually, `cbc` implements `BlockDecryptMut` which has `decrypt_block_mut`.
// To decrypt a slice, one usually uses `decrypt_padded_mut` or casts to blocks.
// `GenericArray` usage is needed.
