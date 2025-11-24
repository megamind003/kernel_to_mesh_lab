use anyhow::{Result, anyhow};
use bytes::{Bytes, BytesMut, BufMut};
use ed25519_dalek::PublicKey;
use rand::{RngCore, rngs::OsRng};
use curve25519_dalek::montgomery::MontgomeryPoint;
use curve25519_dalek::scalar::Scalar;

const NOISE_PROTOCOL: &str = "Noise_XX_25519_ChaChaPoly_BLAKE2s";

pub struct NoiseSession {
    send_cipher: ChaCha20Poly1305,
    recv_cipher: ChaCha20Poly1305,
    remote_public_key: Option<PublicKey>,
}

pub struct NoiseHandshake {
    state: HandshakeState,
}

enum HandshakeState {
    Initiator(InitiatorState),
    Responder(ResponderState),
    Complete,
}

struct InitiatorState {
    ephemeral_private: [u8; 32],
    ephemeral_public: [u8; 32],
}

struct ResponderState {
    ephemeral_private: [u8; 32],
    ephemeral_public: [u8; 32],
}

use chacha20poly1305::{
    aead::{Aead, KeyInit, Payload},
    ChaCha20Poly1305, Nonce,
};

impl NoiseHandshake {
    pub fn new_initiator() -> Self {
        let mut ephemeral_private = [0u8; 32];
        OsRng.fill_bytes(&mut ephemeral_private);
        let ephemeral_public = Self::x25519_scalarmult(&ephemeral_private);

        NoiseHandshake {
            state: HandshakeState::Initiator(InitiatorState {
                ephemeral_private,
                ephemeral_public,
            }),
        }
    }

    pub fn new_responder() -> Self {
        let mut ephemeral_private = [0u8; 32];
        OsRng.fill_bytes(&mut ephemeral_private);
        let ephemeral_public = Self::x25519_scalarmult(&ephemeral_private);

        NoiseHandshake {
            state: HandshakeState::Responder(ResponderState {
                ephemeral_private,
                ephemeral_public,
            }),
        }
    }

    fn x25519_scalarmult(scalar: &[u8; 32]) -> [u8; 32] {
        const X25519_BASEPOINT_BYTES: [u8; 32] = [
            9, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        ];
        
        let scalar_obj = Scalar::from_bytes_mod_order(*scalar);
        let point = MontgomeryPoint(X25519_BASEPOINT_BYTES);
        (scalar_obj * point).to_bytes()
    }

    pub fn create_handshake_message(&mut self, local_static_public: &[u8]) -> Result<Bytes> {
        match &self.state {
            HandshakeState::Initiator(state) => {
                let mut buf = BytesMut::new();
                buf.put_slice(&state.ephemeral_public);
                buf.put_slice(local_static_public);
                Ok(buf.freeze())
            }
            HandshakeState::Responder(state) => {
                let mut buf = BytesMut::new();
                buf.put_slice(&state.ephemeral_public);
                buf.put_slice(local_static_public);
                Ok(buf.freeze())
            }
            HandshakeState::Complete => Err(anyhow!("Handshake already complete")),
        }
    }

    pub fn process_handshake_message(&mut self, message: &[u8]) -> Result<NoiseSession> {
        if message.len() < 64 {
            return Err(anyhow!("Invalid handshake message length"));
        }

        let remote_ephemeral = &message[0..32];
        let remote_static = &message[32..64];

        let shared_secret = match &self.state {
            HandshakeState::Initiator(state) => {
                Self::x25519_dh(&state.ephemeral_private, remote_ephemeral)
            }
            HandshakeState::Responder(state) => {
                Self::x25519_dh(&state.ephemeral_private, remote_ephemeral)
            }
            HandshakeState::Complete => return Err(anyhow!("Handshake already complete")),
        };

        let send_key = blake3::derive_key("aether-send", &shared_secret);
        let recv_key = blake3::derive_key("aether-recv", &shared_secret);

        let send_cipher = ChaCha20Poly1305::new((&send_key).into());
        let recv_cipher = ChaCha20Poly1305::new((&recv_key).into());

        let remote_public_key = PublicKey::from_bytes(remote_static)?;

        self.state = HandshakeState::Complete;

        Ok(NoiseSession {
            send_cipher,
            recv_cipher,
            remote_public_key: Some(remote_public_key),
        })
    }

    fn x25519_dh(private_key: &[u8; 32], public_key: &[u8]) -> [u8; 32] {
        let scalar = Scalar::from_bytes_mod_order(*private_key);
        let point = MontgomeryPoint(*arrayref::array_ref![public_key, 0, 32]);
        (scalar * point).to_bytes()
    }
}

impl NoiseSession {
    pub fn encrypt(&self, plaintext: &[u8]) -> Result<Bytes> {
        let mut nonce_bytes = [0u8; 12];
        OsRng.fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = self.send_cipher
            .encrypt(nonce, plaintext)
            .map_err(|e| anyhow!("Encryption failed: {}", e))?;

        let mut output = BytesMut::with_capacity(12 + ciphertext.len());
        output.put_slice(&nonce_bytes);
        output.put_slice(&ciphertext);

        Ok(output.freeze())
    }

    pub fn decrypt(&self, ciphertext: &[u8]) -> Result<Bytes> {
        if ciphertext.len() < 12 {
            return Err(anyhow!("Ciphertext too short"));
        }

        let nonce = Nonce::from_slice(&ciphertext[0..12]);
        let ct = &ciphertext[12..];

        let plaintext = self.recv_cipher
            .decrypt(nonce, ct)
            .map_err(|e| anyhow!("Decryption failed: {}", e))?;

        Ok(Bytes::from(plaintext))
    }

    pub fn remote_public_key(&self) -> Option<&PublicKey> {
        self.remote_public_key.as_ref()
    }
}
