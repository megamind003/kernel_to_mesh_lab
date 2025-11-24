use anyhow::Result;
use std::sync::Arc;
use std::time::Duration;
use tokio::time;
use tokio::net::TcpStream;
use tracing::info;
use crate::backend::BackendPool;
use crate::config::Backend;

pub struct HealthChecker {
    pool: Arc<BackendPool>,
    interval: Duration,
}

impl HealthChecker {
    pub fn new(pool: Arc<BackendPool>, interval_secs: u64) -> Self {
        Self {
            pool,
            interval: Duration::from_secs(interval_secs),
        }
    }

    pub async fn run(self) {
        info!("Health checker started with {}s interval", self.interval.as_secs());
        
        let mut interval = time::interval(self.interval);
        
        loop {
            interval.tick().await;
            self.check_all_backends().await;
        }
    }

    async fn check_all_backends(&self) {
        for backend in &self.pool.backends {
            match self.check_backend(&backend).await {
                Ok(true) => {
                    self.pool.mark_healthy(&backend.addr);
                }
                Ok(false) | Err(_) => {
                    self.pool.mark_unhealthy(&backend.addr);
                }
            }
        }
    }

    async fn check_backend(&self, backend: &Backend) -> Result<bool> {
        let timeout = Duration::from_secs(2);
        
        match tokio::time::timeout(timeout, TcpStream::connect(&backend.addr)).await {
            Ok(Ok(_)) => Ok(true),
            _ => Ok(false),
        }
    }
}
