use std::fs::{File, OpenOptions};
use std::io::{self, Write, Read, Seek, SeekFrom};
use std::path::Path;

pub struct SSTable {
    file: File,
}

impl SSTable {
    pub fn create(path: &Path, data: &[(String, Vec<u8>)]) -> io::Result<Self> {
        let mut file = OpenOptions::new()
            .create(true)
            .write(true)
            .read(true)
            .truncate(true)
            .open(path)?;

        // Simple SSTable format:
        // [Magic: 4 bytes] [Count: 4 bytes]
        // [KeyLen: 4] [Key] [ValLen: 4] [Val] ...
        
        file.write_all(b"HYDR")?; // Magic
        let count = data.len() as u32;
        file.write_all(&count.to_le_bytes())?;

        for (key, value) in data {
            let key_len = key.len() as u32;
            let val_len = value.len() as u32;

            file.write_all(&key_len.to_le_bytes())?;
            file.write_all(key.as_bytes())?;
            file.write_all(&val_len.to_le_bytes())?;
            file.write_all(value)?;
        }
        
        file.sync_all()?;

        Ok(SSTable { file })
    }

    pub fn open(path: &Path) -> io::Result<Self> {
        let file = OpenOptions::new().read(true).open(path)?;
        Ok(SSTable { file })
    }

    pub fn get(&mut self, search_key: &str) -> io::Result<Option<Vec<u8>>> {
        self.file.seek(SeekFrom::Start(0))?;
        
        let mut magic = [0u8; 4];
        self.file.read_exact(&mut magic)?;
        if &magic != b"HYDR" {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Invalid SSTable magic"));
        }

        let mut count_buf = [0u8; 4];
        self.file.read_exact(&mut count_buf)?;
        let count = u32::from_le_bytes(count_buf);

        for _ in 0..count {
            let mut len_buf = [0u8; 4];
            
            // Read Key
            self.file.read_exact(&mut len_buf)?;
            let key_len = u32::from_le_bytes(len_buf) as usize;
            let mut key_buf = vec![0u8; key_len];
            self.file.read_exact(&mut key_buf)?;
            
            // Read Value
            self.file.read_exact(&mut len_buf)?;
            let val_len = u32::from_le_bytes(len_buf) as usize;
            
            // Optimization: if key doesn't match, skip value
            // In a real SSTable, we'd use an index block to skip faster
            if key_buf == search_key.as_bytes() {
                let mut val_buf = vec![0u8; val_len];
                self.file.read_exact(&mut val_buf)?;
                return Ok(Some(val_buf));
            } else {
                self.file.seek(SeekFrom::Current(val_len as i64))?;
            }
        }

        Ok(None)
    }
}
