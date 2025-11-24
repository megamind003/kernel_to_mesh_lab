use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::io;
use std::fs;

use crate::wal::WAL;
use crate::memtable::MemTable;
use crate::sstable::SSTable;

pub struct Engine {
    path: PathBuf,
    wal: Arc<WAL>,
    memtable: Arc<MemTable>,
    sstables: Arc<Mutex<Vec<PathBuf>>>, // List of SSTable files
}

impl Engine {
    pub fn open(path: &Path) -> io::Result<Self> {
        if !path.exists() {
            fs::create_dir_all(path)?;
        }

        let wal_path = path.join("hydra.wal");
        let wal = WAL::open(&wal_path)?;
        let memtable = MemTable::new();

        // Recover from WAL
        println!("[RUST] Recovering from WAL...");
        wal.recover(|key, val| {
            memtable.put(key, val);
        })?;

        Ok(Engine {
            path: path.to_path_buf(),
            wal: Arc::new(wal),
            memtable: Arc::new(memtable),
            sstables: Arc::new(Mutex::new(Vec::new())), // TODO: Load existing SSTables
        })
    }

    pub fn put(&self, key: String, value: Vec<u8>) -> io::Result<()> {
        self.wal.append(&key, &value)?;
        self.memtable.put(key, value);
        
        // Simple flush policy: if memtable > 1MB, flush
        if self.memtable.size() > 1024 * 1024 {
            self.flush()?;
        }
        
        Ok(())
    }

    pub fn get(&self, key: &str) -> io::Result<Option<Vec<u8>>> {
        // 1. Check MemTable
        if let Some(val) = self.memtable.get(key) {
            return Ok(Some(val));
        }

        // 2. Check SSTables (reverse order - newest first)
        // TODO: Implement SSTable checking
        // For now, we only check memtable as per MVP
        
        Ok(None)
    }

    pub fn flush(&self) -> io::Result<()> {
        println!("[RUST] Flushing MemTable to SSTable...");
        let data = self.memtable.iter();
        if data.is_empty() {
            return Ok(());
        }

        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        
        let sst_name = format!("sst_{}.hydra", timestamp);
        let sst_path = self.path.join(sst_name);
        
        SSTable::create(&sst_path, &data)?;
        
        {
            let mut ssts = self.sstables.lock().unwrap();
            ssts.push(sst_path);
        }

        // Clear memtable and rotate WAL (omitted for MVP, just clearing memtable)
        self.memtable.clear();
        
        Ok(())
    }
}
