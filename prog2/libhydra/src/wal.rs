use std::fs::{File, OpenOptions};
use std::io::{self, Write, Read, Seek, SeekFrom};
use std::path::Path;
use std::sync::Mutex;

pub struct WAL {
    file: Mutex<File>,
}

impl WAL {
    pub fn open(path: &Path) -> io::Result<Self> {
        let file = OpenOptions::new()
            .create(true)
            .read(true)
            .append(true)
            .open(path)?;
        
        Ok(WAL {
            file: Mutex::new(file),
        })
    }

    pub fn append(&self, key: &str, value: &[u8]) -> io::Result<()> {
        let mut file = self.file.lock().unwrap();
        
        // Simple format: len_key(4 bytes) | key | len_val(4 bytes) | val
        let key_len = key.len() as u32;
        let val_len = value.len() as u32;

        file.write_all(&key_len.to_le_bytes())?;
        file.write_all(key.as_bytes())?;
        file.write_all(&val_len.to_le_bytes())?;
        file.write_all(value)?;
        file.flush()?;
        
        Ok(())
    }

    pub fn recover<F>(&self, mut callback: F) -> io::Result<()> 
    where F: FnMut(String, Vec<u8>) 
    {
        let mut file = self.file.lock().unwrap();
        file.seek(SeekFrom::Start(0))?;

        loop {
            let mut len_buf = [0u8; 4];
            
            // Read key length
            if let Err(e) = file.read_exact(&mut len_buf) {
                if e.kind() == io::ErrorKind::UnexpectedEof {
                    break;
                }
                return Err(e);
            }
            let key_len = u32::from_le_bytes(len_buf) as usize;

            // Read key
            let mut key_buf = vec![0u8; key_len];
            file.read_exact(&mut key_buf)?;
            let key = String::from_utf8(key_buf).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;

            // Read value length
            file.read_exact(&mut len_buf)?;
            let val_len = u32::from_le_bytes(len_buf) as usize;

            // Read value
            let mut val_buf = vec![0u8; val_len];
            file.read_exact(&mut val_buf)?;

            callback(key, val_buf);
        }

        // Seek back to end for appending
        file.seek(SeekFrom::End(0))?;
        
        Ok(())
    }
}
