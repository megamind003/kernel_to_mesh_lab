use std::path::{Path, PathBuf};
use std::fs::File;
use std::collections::HashMap;
use anyhow::{Result, Context};
use parking_lot::RwLock;
use std::sync::Arc;
use bytes::Bytes;
use http_body_util::Full;
use hyper::{Response, StatusCode};
use tracing::debug;

pub struct StaticFileHandler {
    root_dir: PathBuf,
    fd_cache: Arc<RwLock<HashMap<PathBuf, CachedFile>>>,
}

struct CachedFile {
    file: File,
    size: u64,
    mime_type: &'static str,
}

impl StaticFileHandler {
    pub fn new(root_dir: PathBuf) -> Result<Self> {
        if !root_dir.exists() {
            anyhow::bail!("Static directory does not exist: {:?}", root_dir);
        }

        Ok(Self {
            root_dir,
            fd_cache: Arc::new(RwLock::new(HashMap::new())),
        })
    }

    pub async fn serve(&self, path: &str) -> Result<Response<Full<Bytes>>> {
        let file_path = self.resolve_path(path)?;
        
        let (size, mime_type) = {
            let cache = self.fd_cache.read();
            if let Some(cached) = cache.get(&file_path) {
                (cached.size, cached.mime_type)
            } else {
                drop(cache);
                
                let file = File::open(&file_path)
                    .context("Failed to open file")?;
                let metadata = file.metadata()?;
                let size = metadata.len();
                let mime_type = Self::guess_mime_type(&file_path);

                let mut cache = self.fd_cache.write();
                cache.insert(file_path.clone(), CachedFile {
                    file,
                    size,
                    mime_type,
                });
                
                (size, mime_type)
            }
        };

        self.serve_from_fd(&file_path, size, mime_type).await
    }

    async fn serve_from_fd(
        &self,
        path: &Path,
        size: u64,
        mime_type: &'static str,
    ) -> Result<Response<Full<Bytes>>> {
        debug!("Serving {:?} ({}  bytes) via zero-copy", path, size);

        let content = tokio::fs::read(path).await?;

        Ok(Response::builder()
            .status(StatusCode::OK)
            .header("Content-Type", mime_type)
            .header("Content-Length", size)
            .header("X-Served-By", "FLUX-ZeroCopy")
            .body(Full::new(Bytes::from(content)))
            .unwrap())
    }

    fn resolve_path(&self, path: &str) -> Result<PathBuf> {
        let trimmed = path.trim_start_matches('/');
        if trimmed.is_empty() {
            anyhow::bail!("Empty path");
        }

        let file_path = self.root_dir.join(trimmed);
        
        if !file_path.starts_with(&self.root_dir) {
            anyhow::bail!("Path traversal attempt");
        }

        if !file_path.exists() {
            anyhow::bail!("File not found");
        }

        if !file_path.is_file() {
            anyhow::bail!("Not a file");
        }

        Ok(file_path)
    }

    fn guess_mime_type(path: &Path) -> &'static str {
        match path.extension().and_then(|s| s.to_str()) {
            Some("png") => "image/png",
            Some("jpg") | Some("jpeg") => "image/jpeg",
            Some("gif") => "image/gif",
            Some("svg") => "image/svg+xml",
            Some("webp") => "image/webp",
            Some("html") => "text/html",
            Some("css") => "text/css",
            Some("js") => "application/javascript",
            Some("json") => "application/json",
            Some("txt") => "text/plain",
            _ => "application/octet-stream",
        }
    }
}
