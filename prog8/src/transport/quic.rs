use anyhow::Result;
use quinn::{Endpoint, ServerConfig, ClientConfig, Connection};
use std::sync::Arc;
use std::net::SocketAddr;
use tokio::sync::RwLock;
use std::time::SystemTime;

pub struct QuicTransport {
    endpoint: Endpoint,
    connections: Arc<RwLock<Vec<Connection>>>,
}

impl QuicTransport {
    pub async fn new(bind_addr: SocketAddr) -> Result<Self> {
        let (cert, key) = generate_self_signed_cert()?;
        
        let server_config = configure_server(cert.clone(), key.clone())?;
        let mut endpoint = Endpoint::server(server_config, bind_addr)?;

        let client_crypto = configure_client_skip_verification();
        let client_config = quinn::ClientConfig::new(Arc::new(client_crypto));
        endpoint.set_default_client_config(client_config);

        Ok(QuicTransport {
            endpoint,
            connections: Arc::new(RwLock::new(Vec::new())),
        })
    }

    pub async fn connect(&self, addr: SocketAddr) -> Result<Connection> {
        let conn = self.endpoint.connect(addr, "aether")?.await?;
        self.connections.write().await.push(conn.clone());
        Ok(conn)
    }

    pub async fn accept(&self) -> Result<Connection> {
        let conn = self.endpoint.accept().await
            .ok_or_else(|| anyhow::anyhow!("Endpoint closed"))?
            .await?;
        self.connections.write().await.push(conn.clone());
        Ok(conn)
    }

    pub fn local_addr(&self) -> Result<SocketAddr> {
        Ok(self.endpoint.local_addr()?)
    }

    pub async fn active_connections(&self) -> usize {
        self.connections.read().await.len()
    }
}

fn generate_self_signed_cert() -> Result<(rustls::Certificate, rustls::PrivateKey)> {
    let cert = rcgen::generate_simple_self_signed(vec!["aether".to_string()])?;
    let key = rustls::PrivateKey(cert.serialize_private_key_der());
    let cert_der = rustls::Certificate(cert.serialize_der()?);
    
    Ok((cert_der, key))
}

fn configure_server(cert: rustls::Certificate, key: rustls::PrivateKey) -> Result<ServerConfig> {
    let mut server_crypto = rustls::ServerConfig::builder()
        .with_safe_defaults()
        .with_no_client_auth()
        .with_single_cert(vec![cert], key)?;
    
    server_crypto.alpn_protocols = vec![b"h3".to_vec()];
    
    let mut server_config = ServerConfig::with_crypto(Arc::new(server_crypto));
    
    let mut transport_config = quinn::TransportConfig::default();
    transport_config.max_concurrent_uni_streams(100_u32.into());
    transport_config.max_concurrent_bidi_streams(100_u32.into());
    
    server_config.transport_config(Arc::new(transport_config));
    
    Ok(server_config)
}

fn configure_client_skip_verification() -> rustls::ClientConfig {
    let mut client_crypto = rustls::ClientConfig::builder()
        .with_safe_defaults()
        .with_custom_certificate_verifier(Arc::new(SkipServerVerification))
        .with_no_client_auth();

    client_crypto.alpn_protocols = vec![b"h3".to_vec()];
    
    client_crypto
}

#[derive(Debug)]
struct SkipServerVerification;

impl rustls::client::ServerCertVerifier for SkipServerVerification {
    fn verify_server_cert(
        &self,
        _end_entity: &rustls::Certificate,
        _intermediates: &[rustls::Certificate],
        _server_name: &rustls::ServerName,
        _scts: &mut dyn Iterator<Item = &[u8]>,
        _ocsp_response: &[u8],
        _now: SystemTime,
    ) -> Result<rustls::client::ServerCertVerified, rustls::Error> {
        Ok(rustls::client::ServerCertVerified::assertion())
    }

    fn verify_tls12_signature(
        &self,
        _message: &[u8],
        _cert: &rustls::Certificate,
        _dss: &rustls::DigitallySignedStruct,
    ) -> Result<rustls::client::HandshakeSignatureValid, rustls::Error> {
        Ok(rustls::client::HandshakeSignatureValid::assertion())
    }

    fn verify_tls13_signature(
        &self,
        _message: &[u8],
        _cert: &rustls::Certificate,
        _dss: &rustls::DigitallySignedStruct,
    ) -> Result<rustls::client::HandshakeSignatureValid, rustls::Error> {
        Ok(rustls::client::HandshakeSignatureValid::assertion())
    }

    fn supported_verify_schemes(&self) -> Vec<rustls::SignatureScheme> {
        vec![
            rustls::SignatureScheme::RSA_PKCS1_SHA1,
            rustls::SignatureScheme::ECDSA_SHA1_Legacy,
            rustls::SignatureScheme::RSA_PKCS1_SHA256,
            rustls::SignatureScheme::ECDSA_NISTP256_SHA256,
            rustls::SignatureScheme::RSA_PKCS1_SHA384,
            rustls::SignatureScheme::ECDSA_NISTP384_SHA384,
            rustls::SignatureScheme::RSA_PKCS1_SHA512,
            rustls::SignatureScheme::ECDSA_NISTP521_SHA512,
            rustls::SignatureScheme::RSA_PSS_SHA256,
            rustls::SignatureScheme::RSA_PSS_SHA384,
            rustls::SignatureScheme::RSA_PSS_SHA512,
            rustls::SignatureScheme::ED25519,
            rustls::SignatureScheme::ED448,
        ]
    }
}
