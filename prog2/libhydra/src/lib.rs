use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int};
use std::sync::{Arc, Mutex};
use std::path::Path;

mod wal;
mod memtable;
mod sstable;
mod engine;

use engine::Engine;

// Global engine instance
lazy_static::lazy_static! {
    static ref ENGINE: Mutex<Option<Arc<Engine>>> = Mutex::new(None);
}

#[no_mangle]
pub extern "C" fn hydra_open(path: *const c_char) -> c_int {
    if path.is_null() {
        return -1;
    }
    let c_path = unsafe { CStr::from_ptr(path) };
    let path_str = match c_path.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let engine = match Engine::open(Path::new(path_str)) {
        Ok(e) => e,
        Err(_) => return -3,
    };

    let mut global_engine = ENGINE.lock().unwrap();
    *global_engine = Some(Arc::new(engine));
    
    0
}

#[no_mangle]
pub extern "C" fn hydra_put(key: *const c_char, val: *const c_char, val_len: c_int) -> c_int {
    let global_engine = ENGINE.lock().unwrap();
    let engine = match global_engine.as_ref() {
        Some(e) => e,
        None => return -10, // Engine not initialized
    };

    if key.is_null() || val.is_null() {
        return -1;
    }

    let c_key = unsafe { CStr::from_ptr(key) };
    let key_str = match c_key.to_str() {
        Ok(s) => s.to_string(),
        Err(_) => return -2,
    };

    let val_slice = unsafe { std::slice::from_raw_parts(val as *const u8, val_len as usize) };
    let val_vec = val_slice.to_vec();

    match engine.put(key_str, val_vec) {
        Ok(_) => 0,
        Err(_) => -5,
    }
}

#[no_mangle]
pub extern "C" fn hydra_get(key: *const c_char, val_out: *mut c_char, max_len: c_int) -> c_int {
    let global_engine = ENGINE.lock().unwrap();
    let engine = match global_engine.as_ref() {
        Some(e) => e,
        None => return -10,
    };

    if key.is_null() || val_out.is_null() {
        return -1;
    }

    let c_key = unsafe { CStr::from_ptr(key) };
    let key_str = match c_key.to_str() {
        Ok(s) => s,
        Err(_) => return -2,
    };

    match engine.get(key_str) {
        Ok(Some(data)) => {
            let len = data.len();
            if len > max_len as usize {
                return -3; // Buffer too small
            }
            unsafe {
                std::ptr::copy_nonoverlapping(data.as_ptr(), val_out as *mut u8, len);
            }
            len as c_int
        },
        Ok(None) => -4, // Not found
        Err(_) => -5, // IO Error
    }
}

#[no_mangle]
pub extern "C" fn hydra_close() -> c_int {
    let mut global_engine = ENGINE.lock().unwrap();
    *global_engine = None;
    0
}
