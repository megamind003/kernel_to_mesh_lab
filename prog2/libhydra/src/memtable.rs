use std::collections::BTreeMap;
use std::sync::RwLock;

pub struct MemTable {
    map: RwLock<BTreeMap<String, Vec<u8>>>,
    size: RwLock<usize>,
}

impl MemTable {
    pub fn new() -> Self {
        MemTable {
            map: RwLock::new(BTreeMap::new()),
            size: RwLock::new(0),
        }
    }

    pub fn put(&self, key: String, value: Vec<u8>) {
        let mut map = self.map.write().unwrap();
        let mut size = self.size.write().unwrap();
        
        let key_len = key.len();
        let val_len = value.len();

        if let Some(old_val) = map.insert(key, value) {
            *size -= old_val.len();
        } else {
            *size += key_len;
        }
        *size += val_len;
    }

    pub fn get(&self, key: &str) -> Option<Vec<u8>> {
        let map = self.map.read().unwrap();
        map.get(key).cloned()
    }

    pub fn size(&self) -> usize {
        *self.size.read().unwrap()
    }

    pub fn clear(&self) {
        let mut map = self.map.write().unwrap();
        let mut size = self.size.write().unwrap();
        map.clear();
        *size = 0;
    }
    
    pub fn iter(&self) -> Vec<(String, Vec<u8>)> {
        let map = self.map.read().unwrap();
        map.iter().map(|(k, v)| (k.clone(), v.clone())).collect()
    }
}
