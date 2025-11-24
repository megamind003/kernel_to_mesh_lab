use anyhow::Result;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use tracing::info;

pub mod event_loop;
pub mod worker;
pub mod affinity;

pub use worker::Worker;

pub struct Reactor {
    workers: Vec<Worker>,
    shutdown: Arc<AtomicBool>,
}

impl Reactor {
    pub fn new(num_workers: usize) -> Result<Self> {
        let shutdown = Arc::new(AtomicBool::new(false));
        let mut workers = Vec::new();

        for i in 0..num_workers {
            let worker = Worker::new(i, shutdown.clone())?;
            workers.push(worker);
        }

        Ok(Self {
            workers,
            shutdown,
        })
    }

    pub async fn run(self) -> Result<()> {
        info!("Starting {} reactor workers", self.workers.len());

        let handles: Vec<_> = self.workers
            .into_iter()
            .map(|worker| {
                tokio::spawn(async move {
                    worker.run().await
                })
            })
            .collect();

        for handle in handles {
            handle.await??;
        }

        Ok(())
    }

    pub fn shutdown(&self) {
        self.shutdown.store(true, Ordering::SeqCst);
    }
}
