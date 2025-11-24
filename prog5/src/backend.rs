use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use dashmap::DashMap;
use crate::config::Backend;

pub struct BackendPool {
    pub backends: Vec<Backend>,
    current: AtomicUsize,
    health_status: Arc<DashMap<String, bool>>,
}

impl BackendPool {
    pub fn new(backends: Vec<Backend>) -> Self {
        let health_status = Arc::new(DashMap::new());
        
        for backend in &backends {
            health_status.insert(backend.addr.clone(), true);
        }

        Self {
            backends,
            current: AtomicUsize::new(0),
            health_status,
        }
    }

    pub fn get_next(&self) -> Option<&Backend> {
        if self.backends.is_empty() {
            return None;
        }

        let healthy: Vec<&Backend> = self
            .backends
            .iter()
            .filter(|b| {
                self.health_status
                    .get(&b.addr)
                    .map(|r| *r.value())
                    .unwrap_or(true)
            })
            .collect();

        if healthy.is_empty() {
            return None;
        }

        let idx = self.current.fetch_add(1, Ordering::Relaxed) % healthy.len();
        Some(healthy[idx])
    }

    pub fn mark_unhealthy(&self, addr: &str) {
        self.health_status.insert(addr.to_string(), false);
    }

    pub fn mark_healthy(&self, addr: &str) {
        self.health_status.insert(addr.to_string(), true);
    }
}
