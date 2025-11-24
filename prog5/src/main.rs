use anyhow::Result;
use std::path::PathBuf;

mod config;
mod server;
mod backend;
mod health;
mod sendfile;
mod reactor;
mod static_files;
mod protocol;
mod resilience;
mod tls;
// mod wasm;  // Requires Rust 1.76+ via wasmtime

use config::Config;
use server::Server;
use protocol::quic::QuicServer;
use backend::BackendPool;
use health::HealthChecker;
use std::sync::Arc;
// use wasm::runtime::WasmRuntime;  // Requires Rust 1.76+

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    let config_path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "flux.yaml".to_string());

    let config = Config::load(&config_path)?;
    
    tracing::info!("FLUX Load Balancer starting");
    tracing::info!("Bind address: {}", config.bind_addr);
    tracing::info!("Workers: {}", config.workers);
    tracing::info!("Backends: {}", config.backends.len());

    // Wasm Runtime: Requires Rust 1.76+ (wasmtime transitive deps)
    // let wasm_runtime = WasmRuntime::new()?;
    // wasm_runtime.run_example()?;

    // Initialize backend pool for health checking
    let backend_pool = Arc::new(BackendPool::new(config.backends.clone()));
    let health_checker = HealthChecker::new(
        backend_pool.clone(),
        config.health_check_interval_secs,
    );
    
    // Start health checker
    tokio::spawn(async move {
        health_checker.run().await;
    });

    // Start TCP/HTTP Server
    let server = Server::new(config.clone()).await?;
    let tcp_handle = tokio::spawn(async move {
        if let Err(e) = server.run().await {
            eprintln!("Server error: {}", e);
        }
    });

    // Start QUIC Server
    let bind_addr = config.bind_addr.parse()?;
    let quic_server = QuicServer::new(bind_addr).await?;
    let quic_handle = tokio::spawn(async move {
        if let Err(e) = quic_server.run().await {
            eprintln!("QUIC Server error: {}", e);
        }
    });

    // Wait for both
    let _ = tokio::join!(tcp_handle, quic_handle);

    Ok(())
}
