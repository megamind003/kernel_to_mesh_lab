use std::env;
use std::path::Path;
use std::sync::{Arc, RwLock};
use log::{info, error};
use env_logger::Env;

mod carrier;
mod crypto;
mod fs;
mod metadata;

use carrier::CarrierPool;
use crypto::Crypto;
use fs::GhostFS;
use metadata::MetadataManager;

fn main() -> anyhow::Result<()> {
    env_logger::Builder::from_env(Env::default().default_filter_or("info")).init();

    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("Usage: {} <host_dir> <mountpoint>", args[0]);
        std::process::exit(1);
    }

    let host_dir = Path::new(&args[1]);
    let mountpoint = Path::new(&args[2]);
    let password = "ghostfs_default_password";

    info!("Initializing Carrier Pool from {}", host_dir.display());
    let pool = Arc::new(RwLock::new(CarrierPool::new(host_dir)?));

    // Try to load metadata
    let salt = [0u8; 16]; // Temporary salt for initial check? 
    // No, load reads salt from Block 0.
    // But we need to know if we should init.
    // Let's try to read Block 0.
    
    let mut sb_buf = vec![0u8; metadata::BLOCK_SIZE];
    {
        let pool_guard = pool.read().unwrap();
        if let Err(_) = pool_guard.read_bytes(0, &mut sb_buf) {
            // If we can't read block 0, we can't do anything.
            // Maybe pool is empty?
            if pool_guard.total_capacity_bytes < metadata::BLOCK_SIZE {
                anyhow::bail!("Carrier pool too small");
            }
        }
    }

    // Check for magic (decrypted)
    // We don't know the salt yet.
    // But `MetadataManager::load` reads salt from Block 0 (plaintext part).
    
    let metadata_mgr = match MetadataManager::load(&pool.read().unwrap(), password) {
        Ok(mgr) => {
            info!("Filesystem loaded successfully.");
            Arc::new(RwLock::new(mgr))
        }
        Err(e) => {
            info!("Could not load filesystem ({}). Initializing new...", e);
            let salt = [0xAA; 16]; // Fixed salt for now, or random.
            // Ideally random.
            // let salt: [u8; 16] = rand::random();
            let crypto = Crypto::new(password, &salt);
            let mgr = MetadataManager::init(&mut pool.write().unwrap(), &crypto, salt)?;
            Arc::new(RwLock::new(mgr))
        }
    };

    // Re-create crypto with the correct salt
    let salt = metadata_mgr.read().unwrap().salt;
    let crypto = Arc::new(Crypto::new(password, &salt));

    let fs = GhostFS {
        pool: pool.clone(),
        metadata_mgr: metadata_mgr.clone(),
        crypto: crypto.clone(),
    };

    info!("Mounting GhostFS at {}", mountpoint.display());
    
    // Mount options
    let options = vec![
        fuser::MountOption::RW,
        fuser::MountOption::FSName("ghostfs".to_string()),
        fuser::MountOption::AutoUnmount,
    ];

    // Handle Ctrl+C to sync
    let pool_clone = pool.clone();
    ctrlc::set_handler(move || {
        info!("Received Ctrl+C. Syncing carriers...");
        if let Ok(pool) = pool_clone.read() {
            if let Err(e) = pool.sync() {
                error!("Failed to sync: {}", e);
            } else {
                info!("Sync successful.");
            }
        }
        std::process::exit(0);
    }).expect("Error setting Ctrl-C handler");

    fuser::mount2(fs, mountpoint, &options)?;

    // Sync on unmount
    info!("Unmounted. Syncing carriers...");
    pool.read().unwrap().sync()?;

    Ok(())
}
