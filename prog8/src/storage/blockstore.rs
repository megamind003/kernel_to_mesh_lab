use anyhow::Result;
use bytes::Bytes;
use parking_lot::RwLock;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::fs;
use std::io::Write;

use super::merkle::ContentHash;

pub struct BlockStore {
    base_path: PathBuf,
}

impl BlockStore {
    pub fn new<P: AsRef<Path>>(base_path: P) -> Result<Self> {
        let base_path = base_path.as_ref().to_path_buf();
        fs::create_dir_all(&base_path)?;

        Ok(BlockStore {
            base_path,
        })
    }

    pub fn put(&self, hash: &ContentHash, data: Bytes) -> Result<()> {
        let path = self.hash_to_path(hash);
        
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut file = fs::File::create(&path)?;
        file.write_all(&data)?;
        file.sync_all()?;

        // self.cache.insert(hash.clone(), Arc::new(data)); // Removed caching

        Ok(())
    }

    pub fn get(&self, hash: &ContentHash) -> Result<Option<Bytes>> {
        // if let Some(cached) = self.cache.get(hash) {
        //     return Ok(Some((**cached).clone()));
        // }

        let path = self.hash_to_path(hash);
        
        if !path.exists() {
            return Ok(None);
        }

        let data = fs::read(&path)?;
        let bytes = Bytes::from(data);
        
        // self.cache.insert(hash.clone(), Arc::new(bytes.clone()));

        Ok(Some(bytes))
    }

    pub fn has(&self, hash: &ContentHash) -> bool {
        let exists = self.hash_to_path(hash).exists();
        if exists {
            println!("BlockStore::has({}) -> true (disk: {:?})", hash, self.hash_to_path(hash));
        }
        exists
    }

    fn hash_to_path(&self, hash: &ContentHash) -> PathBuf {
        let hex = hash.to_hex();
        let prefix = &hex[0..2];
        let suffix = &hex[2..];
        
        self.base_path.join(prefix).join(suffix)
    }

    pub fn size(&self) -> Result<u64> {
        let mut total = 0u64;
        
        for entry in fs::read_dir(&self.base_path)? {
            let entry = entry?;
            let metadata = entry.metadata()?;
            
            if metadata.is_dir() {
                for sub_entry in fs::read_dir(entry.path())? {
                    let sub_entry = sub_entry?;
                    total += sub_entry.metadata()?.len();
                }
            }
        }

        Ok(total)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_block_store() {
        let dir = tempdir().unwrap();
        let store = BlockStore::new(dir.path()).unwrap();
        
        let data = Bytes::from("test data");
        let hash = ContentHash::from_bytes(&data);
        
        store.put(&hash, data.clone()).unwrap();
        assert!(store.has(&hash));
        
        let retrieved = store.get(&hash).unwrap().unwrap();
        assert_eq!(data, retrieved);
    }
}
