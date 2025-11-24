use anyhow::Result;
use ed25519_dalek::{Keypair, SecretKey, PublicKey, Signature, Signer, Verifier};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Clone, Debug)]
pub struct Identity {
    secret_bytes: [u8; 64],
    peer_id: PeerId,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PeerId(pub [u8; 32]);

impl Identity {
    pub fn generate() -> Self {
        let mut secret_bytes = [0u8; 32];
        getrandom::getrandom(&mut secret_bytes).expect("Failed to generate random bytes");
        
        let secret = SecretKey::from_bytes(&secret_bytes).unwrap();
        let public = PublicKey::from(&secret);
        let keypair = Keypair { secret, public };
        
        let full_bytes = keypair.to_bytes();
        let peer_id = PeerId::from_public_key(&keypair.public);
        
        Identity { secret_bytes: full_bytes, peer_id }
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        if bytes.len() != 64 {
            return Err(anyhow::anyhow!("Invalid key length"));
        }
        let mut arr = [0u8; 64];
        arr.copy_from_slice(bytes);
        let keypair = Keypair::from_bytes(&arr)?;
        let peer_id = PeerId::from_public_key(&keypair.public);
        
        Ok(Identity { secret_bytes: arr, peer_id })
    }

    pub fn to_bytes(&self) -> [u8; 64] {
        self.secret_bytes
    }

    pub fn save(&self, path: &Path) -> Result<()> {
        std::fs::write(path, &self.to_bytes())?;
        Ok(())
    }

    pub fn load(path: &Path) -> Result<Self> {
        let bytes = std::fs::read(path)?;
        Self::from_bytes(&bytes)
    }

    pub fn peer_id(&self) -> PeerId {
        self.peer_id
    }

    pub fn public_key(&self) -> PublicKey {
        let keypair = Keypair::from_bytes(&self.secret_bytes).unwrap();
        keypair.public
    }

    pub fn sign(&self, data: &[u8]) -> Signature {
        let keypair = Keypair::from_bytes(&self.secret_bytes).unwrap();
        keypair.sign(data)
    }

    pub fn verify(&self, data: &[u8], signature: &Signature, public_key: &PublicKey) -> bool {
        public_key.verify(data, signature).is_ok()
    }
}

impl PeerId {
    pub fn from_public_key(public_key: &PublicKey) -> Self {
        let hash = blake3::hash(public_key.as_bytes());
        PeerId(*hash.as_bytes())
    }

    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    pub fn to_hex(&self) -> String {
        hex::encode(self.0)
    }
}

impl std::fmt::Display for PeerId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", &self.to_hex()[..16])
    }
}

mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes.as_ref().iter().map(|b| format!("{:02x}", b)).collect()
    }
}

