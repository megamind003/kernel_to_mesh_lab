use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use anyhow::Result;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Config {
    pub bind_addr: String,
    pub workers: usize,
    pub backends: Vec<Backend>,
    pub http2_max_streams: Option<u32>,
    pub http2_window_size: Option<u32>,
    pub static_dir: Option<PathBuf>,
    pub health_check_interval_secs: u64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Backend {
    pub addr: String,
    pub weight: u32,
}

impl Config {
    pub fn load(path: &str) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: Config = serde_yaml::from_str(&content)?;
        Ok(config)
    }

    pub fn default_config() -> Self {
        Config {
            bind_addr: "0.0.0.0:8080".to_string(),
            workers: num_cpus::get(),
            backends: vec![],
            static_dir: Some(PathBuf::from("../data_hardcore/archive/all_images/images")),
            health_check_interval_secs: 5,
            http2_max_streams: None,
            http2_window_size: None,
        }
    }
}
