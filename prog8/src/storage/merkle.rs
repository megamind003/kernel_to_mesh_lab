use anyhow::Result;
use blake3::Hash;
use bytes::Bytes;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct ContentHash([u8; 32]);

impl ContentHash {
    pub fn from_bytes(data: &[u8]) -> Self {
        let hash = blake3::hash(data);
        ContentHash(*hash.as_bytes())
    }

    pub fn from_hash(hash: Hash) -> Self {
        ContentHash(*hash.as_bytes())
    }

    pub fn from_raw(bytes: [u8; 32]) -> Self {
        ContentHash(bytes)
    }

    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    pub fn to_hex(&self) -> String {
        hex::encode(self.0)
    }
}

impl std::fmt::Display for ContentHash {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", &self.to_hex()[..16])
    }
}

#[derive(Clone, Debug)]
pub struct FileNode {
    pub chunks: Vec<ContentHash>,
    pub total_size: u64,
}

#[derive(Clone, Debug)]
pub struct DirectoryNode {
    pub entries: HashMap<String, Entry>,
}

#[derive(Clone, Debug)]
pub enum Entry {
    File(FileNode),
    Directory(ContentHash),
}

#[derive(Clone, Debug)]
pub struct MerkleTree {
    root: ContentHash,
    files: HashMap<ContentHash, FileNode>,
    chunks: HashMap<ContentHash, Bytes>,
}

impl MerkleTree {
    pub fn new() -> Self {
        let root_bytes = b"empty";
        let root_hash = ContentHash::from_bytes(root_bytes);

        MerkleTree {
            root: root_hash,
            files: HashMap::new(),
            chunks: HashMap::new(),
        }
    }

    pub fn add_file(&mut self, path: &str, chunks: Vec<(ContentHash, Bytes)>) -> Result<ContentHash> {
        for (hash, data) in &chunks {
            self.chunks.insert(hash.clone(), data.clone());
        }

        let file_node = FileNode {
            chunks: chunks.iter().map(|(h, _)| h.clone()).collect(),
            total_size: chunks.iter().map(|(_, d)| d.len() as u64).sum(),
        };

        let file_hash = ContentHash::from_bytes(path.as_bytes());
        self.files.insert(file_hash.clone(), file_node);

        Ok(file_hash)
    }

    pub fn get_file(&self, hash: &ContentHash) -> Option<&FileNode> {
        self.files.get(hash)
    }

    pub fn get_chunk(&self, hash: &ContentHash) -> Option<&Bytes> {
        self.chunks.get(hash)
    }

    pub fn root_hash(&self) -> &ContentHash {
        &self.root
    }

    pub fn list_files(&self) -> Vec<String> {
        self.files.keys().map(|h| h.to_hex()).collect()
    }
}

mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes.as_ref().iter().map(|b| format!("{:02x}", b)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_content_hash() {
        let data = b"test data";
        let hash1 = ContentHash::from_bytes(data);
        let hash2 = ContentHash::from_bytes(data);
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_merkle_tree() {
        let mut tree = MerkleTree::new();
        let chunk_data = Bytes::from("test chunk");
        let chunk_hash = ContentHash::from_bytes(&chunk_data);
        
        tree.add_file("test.txt", vec![(chunk_hash.clone(), chunk_data.clone())]).unwrap();
        
        let files = tree.list_files();
        assert!(files.contains(&"test.txt".to_string()));
    }
}
