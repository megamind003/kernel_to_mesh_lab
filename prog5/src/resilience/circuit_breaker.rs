use std::sync::Arc;
use std::time::{Duration, Instant};
use parking_lot::RwLock;
use dashmap::DashMap;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum CircuitState {
    Closed,
    Open,
    HalfOpen,
}

#[derive(Clone)]
pub struct CircuitBreaker {
    state: Arc<RwLock<CircuitState>>,
    failure_count: Arc<RwLock<u32>>,
    last_failure_time: Arc<RwLock<Option<Instant>>>,
    failure_threshold: u32,
    timeout: Duration,
}

impl CircuitBreaker {
    pub fn new(failure_threshold: u32, timeout_secs: u64) -> Self {
        Self {
            state: Arc::new(RwLock::new(CircuitState::Closed)),
            failure_count: Arc::new(RwLock::new(0)),
            last_failure_time: Arc::new(RwLock::new(None)),
            failure_threshold,
            timeout: Duration::from_secs(timeout_secs),
        }
    }

    pub fn can_attempt(&self) -> bool {
        let state = *self.state.read();
        
        match state {
            CircuitState::Closed => true,
            CircuitState::HalfOpen => true,
            CircuitState::Open => {
                if let Some(last_time) = *self.last_failure_time.read() {
                    if last_time.elapsed() > self.timeout {
                        let mut state_lock = self.state.write();
                        *state_lock = CircuitState::HalfOpen;
                        *self.failure_count.write() = 0;
                        return true;
                    }
                }
                false
            }
        }
    }

    pub fn record_success(&self) {
        let mut state_lock = self.state.write();
        *state_lock = CircuitState::Closed;
        *self.failure_count.write() = 0;
    }

    pub fn record_failure(&self) {
        let mut count = self.failure_count.write();
        *count += 1;
        *self.last_failure_time.write() = Some(Instant::now());

        if *count >= self.failure_threshold {
            *self.state.write() = CircuitState::Open;
        }
    }

    pub fn state(&self) -> CircuitState {
        *self.state.read()
    }
}

pub struct CircuitBreakerRegistry {
    breakers: DashMap<String, CircuitBreaker>,
    default_threshold: u32,
    default_timeout: u64,
}

impl CircuitBreakerRegistry {
    pub fn new(default_threshold: u32, default_timeout: u64) -> Self {
        Self {
            breakers: DashMap::new(),
            default_threshold,
            default_timeout,
        }
    }

    pub fn get_or_create(&self, backend: &str) -> CircuitBreaker {
        if let Some(breaker) = self.breakers.get(backend) {
            breaker.clone()
        } else {
            let breaker = CircuitBreaker::new(self.default_threshold, self.default_timeout);
            self.breakers.insert(backend.to_string(), breaker.clone());
            breaker
        }
    }
}
