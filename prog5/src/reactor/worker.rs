use anyhow::Result;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use tracing::info;

use crate::reactor::affinity;

pub struct Worker {
    id: usize,
    shutdown: Arc<AtomicBool>,
}

impl Worker {
    pub fn new(id: usize, shutdown: Arc<AtomicBool>) -> Result<Self> {
        Ok(Self {
            id,
            shutdown,
        })
    }

    pub async fn run(self) -> Result<()> {
        affinity::pin_to_core(self.id);
        
        info!("Worker {} started", self.id);

        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()?;

        runtime.block_on(async {
            while !self.shutdown.load(Ordering::Relaxed) {
                tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
            }
        });

        info!("Worker {} shutting down", self.id);
        Ok(())
    }
}
