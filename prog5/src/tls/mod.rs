use anyhow::Result;
use std::path::PathBuf;
use std::sync::Arc;
use parking_lot::RwLock;
use rustls::{Certificate, PrivateKey, ServerConfig};
use tokio_rustls::TlsAcceptor;
use tracing::info;

pub struct TlsManager {
    acceptor: Arc<RwLock<TlsAcceptor>>,
    cert_path: PathBuf,
    key_path: PathBuf,
}

impl TlsManager {
    pub fn new(cert_path: PathBuf, key_path: PathBuf) -> Result<Self> {
        let acceptor = Self::load_tls_config(&cert_path, &key_path)?;
        
        Ok(Self {
            acceptor: Arc::new(RwLock::new(acceptor)),
            cert_path,
            key_path,
        })
    }

    pub fn acceptor(&self) -> TlsAcceptor {
        self.acceptor.read().clone()
    }

    pub fn reload_certificates(&self) -> Result<()> {
        info!("Reloading TLS certificates");
        let new_acceptor = Self::load_tls_config(&self.cert_path, &self.key_path)?;
        *self.acceptor.write() = new_acceptor;
        info!("TLS certificates reloaded successfully");
        Ok(())
    }

    fn load_tls_config(cert_path: &PathBuf, key_path: &PathBuf) -> Result<TlsAcceptor> {
        let certs = Self::load_certs(cert_path)?;
        let key = Self::load_private_key(key_path)?;

        let config = ServerConfig::builder()
            .with_safe_defaults()            .with_no_client_auth()
            .with_single_cert(certs, key)?;

        Ok(TlsAcceptor::from(Arc::new(config)))
    }

    fn load_certs(path: &PathBuf) -> Result<Vec<Certificate>> {
        let cert_file = std::fs::File::open(path)?;
        let mut reader = std::io::BufReader::new(cert_file);
        let certs = rustls_pemfile::certs(&mut reader)?
            .iter()
            .map(|v| Certificate(v.clone()))
            .collect();
        Ok(certs)
    }

    fn load_private_key(path: &PathBuf) -> Result<PrivateKey> {
        let key_file = std::fs::File::open(path)?;
        let mut reader = std::io::BufReader::new(key_file);
        
        let keys = rustls_pemfile::pkcs8_private_keys(&mut reader)?;
        if !keys.is_empty() {
            return Ok(PrivateKey(keys[0].clone()));
        }
        
        anyhow::bail!("No private key found")
    }

    pub fn generate_self_signed(domain: &str) -> Result<(Vec<u8>, Vec<u8>)> {
        let cert = rcgen::generate_simple_self_signed(vec![domain.to_string()])?;
        let cert_pem = cert.serialize_pem()?.into_bytes();
        let key_pem = cert.serialize_private_key_pem().into_bytes();
        Ok((cert_pem, key_pem))
    }
}
