use std::sync::Arc;
use std::time::{Duration, Instant};
use parking_lot::RwLock;

pub struct TokenBucket {
    capacity: u32,
    tokens: Arc<RwLock<f64>>,
    refill_rate: f64,
    last_refill: Arc<RwLock<Instant>>,
}

impl TokenBucket {
    pub fn new(capacity: u32, refill_per_sec: f64) -> Self {
        Self {
            capacity,
            tokens: Arc::new(RwLock::new(capacity as f64)),
            refill_rate: refill_per_sec,
            last_refill: Arc::new(RwLock::new(Instant::now())),
        }
    }

    pub fn try_acquire(&self) -> bool {
        self.refill();
        
        let mut tokens = self.tokens.write();
        if *tokens >= 1.0 {
            *tokens -= 1.0;
            true
        } else {
            false
        }
    }

    fn refill(&self) {
        let now = Instant::now();
        let mut last_refill = self.last_refill.write();
        let elapsed = now.duration_since(*last_refill).as_secs_f64();
        
        if elapsed > 0.0 {
            let mut tokens = self.tokens.write();
            let new_tokens = (*tokens + elapsed * self.refill_rate).min(self.capacity as f64);
            *tokens = new_tokens;
            *last_refill = now;
        }
    }
}

pub struct RateLimiter {
    global_bucket: TokenBucket,
}

impl RateLimiter {
    pub fn new(requests_per_sec: u32) -> Self {
        Self {
            global_bucket: TokenBucket::new(requests_per_sec * 2, requests_per_sec as f64),
        }
    }

    pub fn allow_request(&self) -> bool {
        self.global_bucket.try_acquire()
    }
}
