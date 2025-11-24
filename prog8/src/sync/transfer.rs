use anyhow::Result;
use bytes::Bytes;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use parking_lot::RwLock;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::io::Write;

use crate::storage::{ContentHash, BlockStore};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TransferState {
    pub file_hash: ContentHash,
    pub total_chunks: usize,
    pub received_chunks: HashSet<usize>,
    pub chunk_hashes: Vec<ContentHash>,
}

impl TransferState {
    pub fn new(file_hash: ContentHash, chunk_hashes: Vec<ContentHash>) -> Self {
        TransferState {
            file_hash,
            total_chunks: chunk_hashes.len(),
            received_chunks: HashSet::new(),
            chunk_hashes,
        }
    }

    pub fn mark_received(&mut self, chunk_index: usize) {
        self.received_chunks.insert(chunk_index);
    }

    pub fn is_complete(&self) -> bool {
        self.received_chunks.len() == self.total_chunks
    }

    pub fn progress(&self) -> f64 {
        self.received_chunks.len() as f64 / self.total_chunks as f64
    }

    pub fn missing_chunks(&self) -> Vec<usize> {
        (0..self.total_chunks)
            .filter(|i| !self.received_chunks.contains(i))
            .collect()
    }
}

#[derive(Clone)]
pub struct TransferManager {
    active_transfers: Arc<RwLock<HashMap<ContentHash, TransferState>>>,
    block_store: Arc<BlockStore>,
}

impl TransferManager {
    pub fn new(block_store: Arc<BlockStore>) -> Self {
        TransferManager {
            active_transfers: Arc::new(RwLock::new(HashMap::new())),
            block_store,
        }
    }

    pub fn start_transfer(&self, file_hash: ContentHash, chunk_hashes: Vec<ContentHash>) -> TransferState {
        let existing_chunks: HashSet<usize> = chunk_hashes
            .iter()
            .enumerate()
            .filter(|(_, hash)| self.block_store.has(hash))
            .map(|(i, _)| i)
            .collect();

        let mut state = TransferState::new(file_hash.clone(), chunk_hashes);
        state.received_chunks = existing_chunks;

        self.active_transfers.write().insert(file_hash, state.clone());
        
        state
    }

    pub fn receive_chunk(&self, file_hash: &ContentHash, chunk_index: usize, data: Bytes) -> Result<bool> {
        println!("receive_chunk called for index {}", chunk_index);
        std::io::stdout().flush().unwrap();
        let mut transfers = self.active_transfers.write();
        
        if let Some(state) = transfers.get_mut(file_hash) {
            if chunk_index >= state.total_chunks {
                println!("Chunk index {} out of bounds", chunk_index);
                return Ok(false);
            }

            let expected_hash = &state.chunk_hashes[chunk_index];
            let actual_hash = ContentHash::from_bytes(&data);

            if expected_hash != &actual_hash {
                println!("Hash mismatch for chunk {}: expected {:?}, got {:?}", chunk_index, expected_hash, actual_hash);
                return Ok(false);
            }

            self.block_store.put(expected_hash, data)?;
            state.mark_received(chunk_index);
            
            println!("Chunk {} received and verified. Progress: {:.2}%", chunk_index, state.progress() * 100.0);

            Ok(state.is_complete())
        } else {
            println!("No active transfer for file hash {:?}", file_hash);
            Ok(false)
        }
    }

    pub fn get_state(&self, file_hash: &ContentHash) -> Option<TransferState> {
        self.active_transfers.read().get(file_hash).cloned()
    }

    pub fn complete_transfer(&self, file_hash: &ContentHash) -> Option<TransferState> {
        self.active_transfers.write().remove(file_hash)
    }

    pub fn reconstruct_file(&self, state: &TransferState) -> Result<Bytes> {
        let mut file_data = Vec::new();

        for chunk_hash in &state.chunk_hashes {
            let chunk = self.block_store.get(chunk_hash)?
                .ok_or_else(|| anyhow::anyhow!("Missing chunk"))?;
            file_data.extend_from_slice(&chunk);
        }

        Ok(Bytes::from(file_data))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_transfer_state() {
        let file_hash = ContentHash::from_bytes(b"file");
        let chunk1 = ContentHash::from_bytes(b"chunk1");
        let chunk2 = ContentHash::from_bytes(b"chunk2");
        
        let mut state = TransferState::new(file_hash, vec![chunk1, chunk2]);
        
        assert!(!state.is_complete());
        assert_eq!(state.progress(), 0.0);
        
        state.mark_received(0);
        assert_eq!(state.progress(), 0.5);
        
        state.mark_received(1);
        assert!(state.is_complete());
        assert_eq!(state.progress(), 1.0);
    }

    #[test]
    fn test_transfer_resume() {
        let dir = tempdir().unwrap();
        let block_store = Arc::new(BlockStore::new(dir.path()).unwrap());
        let manager = TransferManager::new(block_store.clone());

        let chunk1_data = Bytes::from("chunk1");
        let chunk1_hash = ContentHash::from_bytes(&chunk1_data);
        block_store.put(&chunk1_hash, chunk1_data).unwrap();

        let chunk2_hash = ContentHash::from_bytes(b"chunk2");
        let file_hash = ContentHash::from_bytes(b"file");

        let state = manager.start_transfer(file_hash, vec![chunk1_hash, chunk2_hash]);
        
        assert_eq!(state.received_chunks.len(), 1);
        assert!(state.received_chunks.contains(&0));
    }
}
