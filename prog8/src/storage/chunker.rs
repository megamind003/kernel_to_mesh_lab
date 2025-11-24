use anyhow::Result;
use bytes::Bytes;
use std::io::Read;

const WINDOW_SIZE: usize = 64;
const MIN_CHUNK_SIZE: usize = 16 * 1024;
const AVG_CHUNK_SIZE: usize = 64 * 1024;
const MAX_CHUNK_SIZE: usize = 256 * 1024;

const POLYNOMIAL: u64 = 0x3DA3358B4DC173;
const MODULUS: u64 = AVG_CHUNK_SIZE as u64;

pub struct RabinChunker {
    window: [u8; WINDOW_SIZE],
    window_pos: usize,
    hash: u64,
    chunk_start: usize,
    position: usize,
    pow_table: [u64; 256],
}

impl RabinChunker {
    pub fn new() -> Self {
        let mut pow_table = [0u64; 256];
        for i in 0..256 {
            pow_table[i] = Self::calc_pow(i as u8);
        }

        RabinChunker {
            window: [0u8; WINDOW_SIZE],
            window_pos: 0,
            hash: 0,
            chunk_start: 0,
            position: 0,
            pow_table,
        }
    }

    fn calc_pow(byte: u8) -> u64 {
        let mut hash = byte as u64;
        for _ in 0..WINDOW_SIZE - 1 {
            hash = (hash.wrapping_mul(POLYNOMIAL)) & 0xFFFFFFFF;
        }
        hash
    }

    pub fn chunk_data(data: &[u8]) -> Vec<Bytes> {
        let mut chunker = Self::new();
        let mut chunks = Vec::new();
        let mut last_cut = 0;

        for (pos, &byte) in data.iter().enumerate() {
            if chunker.push_byte(byte) {
                let chunk_size = pos - last_cut + 1;
                if chunk_size >= MIN_CHUNK_SIZE {
                    chunks.push(Bytes::copy_from_slice(&data[last_cut..=pos]));
                    last_cut = pos + 1;
                }
            }
        }

        if last_cut < data.len() {
            chunks.push(Bytes::copy_from_slice(&data[last_cut..]));
        }

        chunks
    }

    pub fn chunk_reader<R: Read>(mut reader: R) -> Result<Vec<Bytes>> {
        let mut chunker = Self::new();
        let mut chunks = Vec::new();
        let mut buffer = Vec::new();
        let mut chunk_buffer = Vec::new();

        reader.read_to_end(&mut buffer)?;

        for (pos, &byte) in buffer.iter().enumerate() {
            chunk_buffer.push(byte);
            
            if chunker.push_byte(byte) && chunk_buffer.len() >= MIN_CHUNK_SIZE {
                chunks.push(Bytes::from(chunk_buffer.clone()));
                chunk_buffer.clear();
            } else if chunk_buffer.len() >= MAX_CHUNK_SIZE {
                chunks.push(Bytes::from(chunk_buffer.clone()));
                chunk_buffer.clear();
            }
        }

        if !chunk_buffer.is_empty() {
            chunks.push(Bytes::from(chunk_buffer));
        }

        Ok(chunks)
    }

    fn push_byte(&mut self, byte: u8) -> bool {
        let old_byte = self.window[self.window_pos];
        self.window[self.window_pos] = byte;
        self.window_pos = (self.window_pos + 1) % WINDOW_SIZE;

        self.hash = self.hash.wrapping_sub(self.pow_table[old_byte as usize]);
        self.hash = self.hash.wrapping_mul(POLYNOMIAL);
        self.hash = self.hash.wrapping_add(byte as u64);
        self.hash &= 0xFFFFFFFF;

        self.position += 1;

        (self.hash % MODULUS) == 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chunking_deterministic() {
        let data = vec![0u8; 1024 * 1024];
        let chunks1 = RabinChunker::chunk_data(&data);
        let chunks2 = RabinChunker::chunk_data(&data);
        
        assert_eq!(chunks1.len(), chunks2.len());
        for (c1, c2) in chunks1.iter().zip(chunks2.iter()) {
            assert_eq!(c1, c2);
        }
    }

    #[test]
    fn test_chunk_sizes() {
        let data: Vec<u8> = (0..1024 * 1024).map(|i| (i % 256) as u8).collect();
        let chunks = RabinChunker::chunk_data(&data);
        
        for chunk in &chunks {
            assert!(chunk.len() >= MIN_CHUNK_SIZE || chunk.len() == data.len() % MAX_CHUNK_SIZE);
        }
    }
}
