use anyhow::Result;
use mdns_sd::{ServiceDaemon, ServiceEvent, ServiceInfo};
use std::collections::HashMap;
use std::net::{IpAddr, SocketAddr};
use std::sync::Arc;
use tokio::sync::RwLock;
use crate::crypto::PeerId;

const SERVICE_TYPE: &str = "_aether._udp.local.";

#[derive(Clone, Debug)]
pub struct PeerInfo {
    pub peer_id: PeerId,
    pub address: SocketAddr,
}

pub struct MdnsDiscovery {
    daemon: ServiceDaemon,
    discovered_peers: Arc<RwLock<HashMap<PeerId, PeerInfo>>>,
    service_name: String,
}

impl MdnsDiscovery {
    pub fn new(peer_id: PeerId, port: u16) -> Result<Self> {
        let daemon = ServiceDaemon::new()?;
        let service_name = format!("aether-{}", peer_id);

        Ok(MdnsDiscovery {
            daemon,
            discovered_peers: Arc::new(RwLock::new(HashMap::new())),
            service_name,
        })
    }

    pub fn announce(&self, port: u16, peer_id: PeerId) -> Result<()> {
        let hostname = gethostname::gethostname();
        let hostname_str = hostname.to_string_lossy();
        
        let properties = HashMap::from([
            ("peer_id".to_string(), peer_id.to_hex()),
        ]);

        let service_info = ServiceInfo::new(
            SERVICE_TYPE,
            &self.service_name,
            &hostname_str,
            (),
            port,
            Some(properties),
        )?;

        self.daemon.register(service_info)?;

        Ok(())
    }

    pub async fn discover(&self) -> Result<()> {
        let receiver = self.daemon.browse(SERVICE_TYPE)?;
        let peers = self.discovered_peers.clone();

        tokio::spawn(async move {
            while let Ok(event) = receiver.recv_async().await {
                match event {
                    ServiceEvent::ServiceResolved(info) => {
                        if let Some(peer_id_hex) = info.get_property_val_str("peer_id") {
                            if let Ok(peer_id_bytes) = hex_decode(peer_id_hex) {
                                if peer_id_bytes.len() == 32 {
                                    let mut arr = [0u8; 32];
                                    arr.copy_from_slice(&peer_id_bytes);
                                    let peer_id = PeerId::from_bytes(&arr);

                                    for addr in info.get_addresses() {
                                        let socket_addr = SocketAddr::new(*addr, info.get_port());
                                        
                                        let peer_info = PeerInfo {
                                            peer_id,
                                            address: socket_addr,
                                        };

                                        peers.write().await.insert(peer_id, peer_info);
                                        tracing::info!("Discovered peer: {} at {}", peer_id, socket_addr);
                                    }
                                }
                            }
                        }
                    }
                    ServiceEvent::ServiceRemoved(_, name) => {
                        tracing::info!("Service removed: {}", name);
                    }
                    _ => {}
                }
            }
        });

        Ok(())
    }

    pub async fn get_peers(&self) -> Vec<PeerInfo> {
        self.discovered_peers.read().await.values().cloned().collect()
    }
}

impl PeerId {
    pub fn from_bytes(bytes: &[u8; 32]) -> Self {
        PeerId(*bytes)
    }
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

fn hex_decode(s: &str) -> Result<Vec<u8>, std::num::ParseIntError> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16))
        .collect()
}
