use anyhow::{Result, anyhow};
use serde::{Deserialize, Serialize};
use crate::crypto::PeerId;
use super::vector_clock::{VectorClock, ClockOrdering};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FileVersion {
    pub name: String,
    pub clock: VectorClock,
    pub hash: String,
}

pub enum ConflictResolution {
    AutoMerge(FileVersion),
    Branch(Vec<FileVersion>),
}

pub struct ConflictResolver;

impl ConflictResolver {
    pub fn resolve(local: &FileVersion, remote: &FileVersion, local_peer: PeerId) -> ConflictResolution {
        match local.clock.compare(&remote.clock) {
            ClockOrdering::Before => {
                ConflictResolution::AutoMerge(remote.clone())
            }
            ClockOrdering::After => {
                ConflictResolution::AutoMerge(local.clone())
            }
            ClockOrdering::Equal => {
                ConflictResolution::AutoMerge(local.clone())
            }
            ClockOrdering::Concurrent => {
                let local_branch = FileVersion {
                    name: format!("{} ({})", local.name, local_peer),
                    clock: local.clock.clone(),
                    hash: local.hash.clone(),
                };
                let remote_branch = remote.clone();
                
                ConflictResolution::Branch(vec![local_branch, remote_branch])
            }
        }
    }

    pub fn should_sync(local: &VectorClock, remote: &VectorClock) -> bool {
        !matches!(local.compare(remote), ClockOrdering::Equal | ClockOrdering::After)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_peer_id(id: u8) -> PeerId {
        PeerId::from_public_key(
            ed25519_dalek::VerifyingKey::from_bytes(&[id; 32]).unwrap()
        )
    }

    #[test]
    fn test_auto_merge_newer() {
        let peer1 = make_peer_id(1);
        
        let mut local_clock = VectorClock::new();
        local_clock.increment(peer1);
        
        let mut remote_clock = VectorClock::new();
        remote_clock.increment(peer1);
        remote_clock.increment(peer1);

        let local = FileVersion {
            name: "test.txt".to_string(),
            clock: local_clock,
            hash: "hash1".to_string(),
        };

        let remote = FileVersion {
            name: "test.txt".to_string(),
            clock: remote_clock,
            hash: "hash2".to_string(),
        };

        match ConflictResolver::resolve(&local, &remote, peer1) {
            ConflictResolution::AutoMerge(merged) => {
                assert_eq!(merged.hash, "hash2");
            }
            _ => panic!("Expected AutoMerge"),
        }
    }

    #[test]
    fn test_branch_on_concurrent() {
        let peer1 = make_peer_id(1);
        let peer2 = make_peer_id(2);

        let mut local_clock = VectorClock::new();
        local_clock.increment(peer1);

        let mut remote_clock = VectorClock::new();
        remote_clock.increment(peer2);

        let local = FileVersion {
            name: "test.txt".to_string(),
            clock: local_clock,
            hash: "hash1".to_string(),
        };

        let remote = FileVersion {
            name: "test.txt".to_string(),
            clock: remote_clock,
            hash: "hash2".to_string(),
        };

        match ConflictResolver::resolve(&local, &remote, peer1) {
            ConflictResolution::Branch(branches) => {
                assert_eq!(branches.len(), 2);
            }
            _ => panic!("Expected Branch"),
        }
    }
}
