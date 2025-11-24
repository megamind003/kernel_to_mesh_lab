mod crypto;
mod storage;
mod sync;
mod transport;
mod discovery;

use anyhow::Result;
use clap::{Parser, Subcommand};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::io::{AsyncReadExt, AsyncWriteExt, AsyncSeekExt};
use std::io::{Write, SeekFrom};
use tracing::Level;
use bytes::Bytes;
use std::time::Instant;

use crypto::{Identity, PeerId};
use storage::{BlockStore, RabinChunker, MerkleTree, ContentHash};
use sync::{TransferManager, VectorClock};
use transport::QuicTransport;
use discovery::MdnsDiscovery;

#[derive(Parser)]
#[command(name = "aether")]
#[command(about = "P2P file synchronization system")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Daemon {
        #[arg(short, long, default_value = "0.0.0.0:5000")]
        bind: SocketAddr,
        
        #[arg(short, long, default_value = "./aether-data")]
        storage: PathBuf,
    },
    Send {
        #[arg(short, long)]
        file: PathBuf,
        
        #[arg(short, long)]
        peer: SocketAddr,
        
        #[arg(short, long, default_value = "./aether-data")]
        storage: PathBuf,
    },
    Receive {
        #[arg(short, long)]
        bind: SocketAddr,
        
        #[arg(short, long)]
        output: PathBuf,
        
        #[arg(short, long, default_value = "./aether-data")]
        storage: PathBuf,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Daemon { bind, storage } => {
            run_daemon(bind, storage).await?;
        }
        Commands::Send { file, peer, storage } => {
            send_file(file, peer, storage).await?;
        }
        Commands::Receive { bind, output, storage } => {
            receive_file(bind, output, storage).await?;
        }
    }

    Ok(())
}

async fn run_daemon(bind: SocketAddr, storage_path: PathBuf) -> Result<()> {
    let identity = Identity::generate();
    let peer_id = identity.peer_id();
    
    tracing::info!("Starting AETHER daemon");
    tracing::info!("Peer ID: {}", peer_id);
    tracing::info!("Binding to: {}", bind);

    let transport = QuicTransport::new(bind).await?;
    let actual_addr = transport.local_addr()?;
    
    let discovery = MdnsDiscovery::new(peer_id, actual_addr.port())?;
    discovery.announce(actual_addr.port(), peer_id)?;
    discovery.discover().await?;

    tracing::info!("Daemon ready on {}", actual_addr);
    tracing::info!("Waiting for connections...");

    let storage_path = Arc::new(storage_path);

    loop {
        match transport.accept().await {
            Ok(conn) => {
                tracing::info!("Accepted connection from {}", conn.remote_address());
                let path = storage_path.clone();
                
                tokio::spawn(async move {
                    if let Err(e) = handle_connection(conn, (*path).clone()).await {
                        tracing::error!("Connection error: {}", e);
                    }
                });
            }
            Err(e) => {
                tracing::error!("Accept error: {}", e);
            }
        }
    }
}

async fn handle_connection(conn: quinn::Connection, storage_path: PathBuf) -> Result<()> {
    let block_store = Arc::new(BlockStore::new(&storage_path)?);
    let transfer_mgr = TransferManager::new(block_store.clone());
    
    println!("Handle connection started");

    loop {
        let (mut send, mut recv) = match conn.accept_bi().await {
            Ok(streams) => streams,
            Err(_) => break,
        };
        
        println!("Accepted stream");

        let transfer_mgr = transfer_mgr.clone();
        let storage_path = storage_path.clone();
        
        tokio::spawn(async move {
            println!("Stream task started");
            loop {
                let mut header = [0u8; 1];
                if recv.read_exact(&mut header).await.is_err() {
                    println!("Stream closed or read error");
                    break;
                }
                
                println!("Received header: {}", header[0]);

                match header[0] {
                    0x01 => {
                        tracing::info!("Received metadata header");
                        let mut len_buf = [0u8; 8];
                        if recv.read_exact(&mut len_buf).await.is_err() { tracing::error!("Failed to read name len"); break; }
                        let name_len = u64::from_be_bytes(len_buf) as usize;
                        
                        let mut name_buf = vec![0u8; name_len];
                        if recv.read_exact(&mut name_buf).await.is_err() { tracing::error!("Failed to read name"); break; }
                        let file_name = match String::from_utf8(name_buf) {
                            Ok(n) => n,
                            Err(_) => { tracing::error!("Invalid UTF8 name"); break; },
                        };
                        tracing::info!("File offer: {}", file_name);

                        let mut file_hash_opt: Option<ContentHash> = None;
                        let mut file_name_opt: Option<String> = None;

                        if recv.read_exact(&mut len_buf).await.is_err() { tracing::error!("Failed to read chunk count"); break; }
                        let chunk_count = u64::from_be_bytes(len_buf) as usize;
                        tracing::info!("Chunk count: {}", chunk_count);

                        let mut chunk_hashes = Vec::new();
                        for _ in 0..chunk_count {
                            let mut hash_bytes = [0u8; 32];
                            if recv.read_exact(&mut hash_bytes).await.is_err() { tracing::error!("Failed to read hash"); break; }
                            chunk_hashes.push(ContentHash::from_raw(hash_bytes));
                        }

                        let file_hash = ContentHash::from_bytes(file_name.as_bytes());
                        let state = transfer_mgr.start_transfer(file_hash.clone(), chunk_hashes);
                        
                        file_hash_opt = Some(file_hash);
                        file_name_opt = Some(file_name);
                        println!("Set file_hash_opt in 0x01 block");
                        std::io::stdout().flush().unwrap();

                        tracing::info!("Requesting {} chunks", state.missing_chunks().len());
                        for chunk_idx in state.missing_chunks() {
                            if send.write_all(&[0x02]).await.is_err() { tracing::error!("Failed to write request"); break; }
                            if send.write_all(&(chunk_idx as u64).to_be_bytes()).await.is_err() { tracing::error!("Failed to write chunk idx"); break; }
                        }

                        if send.write_all(&[0x03]).await.is_err() { tracing::error!("Failed to write done"); break; }
                        tracing::info!("Sent requests");
                        
                        // Keep processing messages in this loop
                        loop {
                            let mut header = [0u8; 1];
                            if recv.read_exact(&mut header).await.is_err() { tracing::error!("Failed to read inner header"); break; }
                            
                            if header[0] == 0x04 {
                                let mut idx_buf = [0u8; 8];
                                if recv.read_exact(&mut idx_buf).await.is_err() { break; }
                                let chunk_idx = u64::from_be_bytes(idx_buf) as usize;

                                let mut size_buf = [0u8; 8];
                                if recv.read_exact(&mut size_buf).await.is_err() { break; }
                                let chunk_size = u64::from_be_bytes(size_buf) as usize;

                                let mut chunk_data = vec![0u8; chunk_size];
                                if recv.read_exact(&mut chunk_data).await.is_err() { break; }

                                let prefix = if chunk_data.len() > 10 { &chunk_data[..10] } else { &chunk_data };
                                tracing::info!("Received chunk {} ({} bytes) prefix {}", chunk_idx, chunk_size, hex_encode(prefix));
                                
                                println!("Checking file_hash_opt: is_some={}", file_hash_opt.is_some());
                                std::io::stdout().flush().unwrap();
                                if let Some(ref fh) = file_hash_opt {
                                    println!("Calling receive_chunk for {}", chunk_idx);
                                    std::io::stdout().flush().unwrap();
                                    match transfer_mgr.receive_chunk(fh, chunk_idx, Bytes::from(chunk_data)) {
                                        Ok(true) => {
                                            tracing::info!("File transfer complete: {:?}", file_name_opt);
                                            if let Some(state) = transfer_mgr.get_state(fh) {
                                                if let Some(ref name) = file_name_opt {
                                                    let path = storage_path.join(name);
                                                    if let Err(e) = transfer_mgr.reconstruct_to_file(&state, &path).await {
                                                        tracing::error!("Failed to save file: {}", e);
                                                    } else {
                                                        tracing::info!("Saved file to {:?}", path);
                                                    }
                                                }
                                            }
                                        }
                                        Ok(false) => {
                                            // Chunk received but not complete yet
                                        }
                                        Err(e) => {
                                            tracing::error!("Error receiving chunk {}: {}", chunk_idx, e);
                                        }
                                    }
                                } else {
                                    tracing::error!("No file hash for chunk {}", chunk_idx);
                                }
                            } else {
                                break; 
                            }
                        }
                        break; // Exit outer loop after file is done (or error)
                    }
                    _ => break,
                }
            }
        });
    }

    Ok(())
}

async fn send_file(file_path: PathBuf, peer_addr: SocketAddr, _storage_path: PathBuf) -> Result<()> {
    let start_time = Instant::now();
    
    tracing::info!("Sending file: {:?} to {}", file_path, peer_addr);

    let transport = QuicTransport::new("0.0.0.0:0".parse()?).await?;
    let conn = transport.connect(peer_addr).await?;

    let file_size = tokio::fs::metadata(&file_path).await?.len();
    tracing::info!("File size: {} bytes", file_size);

    // Use chunk_file_metadata to get chunks without loading file
    let chunks_metadata = RabinChunker::chunk_file_metadata(&file_path)?;
    tracing::info!("File chunked into {} parts", chunks_metadata.len());

    // We don't put chunks into BlockStore here to save time/space, we read from file directly.
    // But we need the hashes.
    let chunk_hashes: Vec<ContentHash> = chunks_metadata.iter().map(|(h, _, _)| h.clone()).collect();

    let (mut send, mut recv) = conn.open_bi().await?;

    send.write_all(&[0x01]).await?;
    
    let file_name = file_path.file_name().unwrap().to_string_lossy();
    let name_bytes = file_name.as_bytes();
    send.write_all(&(name_bytes.len() as u64).to_be_bytes()).await?;
    send.write_all(name_bytes).await?;

    send.write_all(&(chunk_hashes.len() as u64).to_be_bytes()).await?;
    for hash in &chunk_hashes {
        send.write_all(hash.as_bytes()).await?;
    }

    let mut requested_chunks = Vec::new();
    loop {
        let mut msg_type = [0u8; 1];
        match recv.read_exact(&mut msg_type).await {
            Ok(_) => {
                if msg_type[0] == 0x02 {
                    let mut idx_buf = [0u8; 8];
                    recv.read_exact(&mut idx_buf).await?;
                    let chunk_idx = u64::from_be_bytes(idx_buf) as usize;
                    requested_chunks.push(chunk_idx);
                } else if msg_type[0] == 0x03 {
                    break;
                }
            }
            Err(_) => break,
        }
    }

    tracing::info!("Sending {} chunks", requested_chunks.len());

    let mut file = tokio::fs::File::open(&file_path).await?;

    for chunk_idx in requested_chunks {
        if chunk_idx >= chunks_metadata.len() { continue; }
        let (_, offset, len) = chunks_metadata[chunk_idx];
        
        send.write_all(&[0x04]).await?;
        send.write_all(&(chunk_idx as u64).to_be_bytes()).await?;
        send.write_all(&(len as u64).to_be_bytes()).await?;
        
        file.seek(SeekFrom::Start(offset)).await?;
        let mut chunk_data = vec![0u8; len as usize];
        file.read_exact(&mut chunk_data).await?;

        let prefix = if chunk_data.len() > 10 { &chunk_data[..10] } else { &chunk_data };
        tracing::info!("Sending chunk {} size {} prefix {}", chunk_idx, len, hex_encode(prefix));
        
        send.write_all(&chunk_data).await?;
    }

    send.finish().await?;

    let elapsed = start_time.elapsed();
    tracing::info!("Transfer completed in {:?}", elapsed);
    tracing::info!("Speed: {:.2} MB/s", file_size as f64 / elapsed.as_secs_f64() / 1_000_000.0);

    Ok(())
}

async fn receive_file(bind_addr: SocketAddr, output_path: PathBuf, storage_path: PathBuf) -> Result<()> {
    tracing::info!("Starting receiver on {}", bind_addr);
    
    let transport = QuicTransport::new(bind_addr).await?;
    
    tracing::info!("Waiting for connection...");
    let conn = transport.accept().await?;
    tracing::info!("Connected to {}", conn.remote_address());

    let block_store = Arc::new(BlockStore::new(&storage_path)?);
    let transfer_mgr = TransferManager::new(block_store.clone());

    let (mut send, mut recv) = conn.accept_bi().await?;

    let mut header = [0u8; 1];
    recv.read_exact(&mut header).await?;

    if header[0] == 0x01 {
        let mut len_buf = [0u8; 8];
        recv.read_exact(&mut len_buf).await?;
        let name_len = u64::from_be_bytes(len_buf) as usize;
        
        let mut name_buf = vec![0u8; name_len];
        recv.read_exact(&mut name_buf).await?;

        recv.read_exact(&mut len_buf).await?;
        let chunk_count = u64::from_be_bytes(len_buf) as usize;

        let mut chunk_hashes = Vec::new();
        for _ in 0..chunk_count {
            let mut hash_bytes = [0u8; 32];
            recv.read_exact(&mut hash_bytes).await?;
            chunk_hashes.push(ContentHash::from_bytes(&hash_bytes));
        }

        let file_hash = ContentHash::from_bytes(b"received_file");
        let state = transfer_mgr.start_transfer(file_hash.clone(), chunk_hashes.clone());

        for chunk_idx in state.missing_chunks() {
            send.write_all(&[0x02]).await?;
            send.write_all(&(chunk_idx as u64).to_be_bytes()).await?;
        }

        send.write_all(&[0x03]).await?;

        let mut all_chunks = vec![Bytes::new(); chunk_count];
        
        loop {
            let mut msg_type = [0u8; 1];
            match recv.read_exact(&mut msg_type).await {
                Ok(_) => {
                    if msg_type[0] == 0x04 {
                        let mut idx_buf = [0u8; 8];
                        recv.read_exact(&mut idx_buf).await?;
                        let chunk_idx = u64::from_be_bytes(idx_buf) as usize;

                        let mut size_buf = [0u8; 8];
                        recv.read_exact(&mut size_buf).await?;
                        let chunk_size = u64::from_be_bytes(size_buf) as usize;

                        let mut chunk_data = vec![0u8; chunk_size];
                        recv.read_exact(&mut chunk_data).await?;

                        all_chunks[chunk_idx] = Bytes::from(chunk_data);
                        tracing::info!("Received chunk {}/{}", chunk_idx + 1, chunk_count);
                    }
                }
                Err(_) => break,
            }
        }

        let mut file_data = Vec::new();
        for chunk in all_chunks {
            file_data.extend_from_slice(&chunk);
        }

        tokio::fs::write(&output_path, file_data).await?;
        tracing::info!("File saved to {:?}", output_path);
    }

    Ok(())
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}
