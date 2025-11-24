use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::crypto::PeerId;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VectorClock {
    clock: HashMap<PeerId, u64>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ClockOrdering {
    Before,
    After,
    Concurrent,
    Equal,
}

impl VectorClock {
    pub fn new() -> Self {
        VectorClock {
            clock: HashMap::new(),
        }
    }

    pub fn increment(&mut self, peer_id: PeerId) {
        let counter = self.clock.entry(peer_id).or_insert(0);
        *counter += 1;
    }

    pub fn get(&self, peer_id: &PeerId) -> u64 {
        self.clock.get(peer_id).copied().unwrap_or(0)
    }

    pub fn merge(&mut self, other: &VectorClock) {
        for (peer_id, &timestamp) in &other.clock {
            let entry = self.clock.entry(*peer_id).or_insert(0);
            *entry = (*entry).max(timestamp);
        }
    }

    pub fn compare(&self, other: &VectorClock) -> ClockOrdering {
        let all_peers: std::collections::HashSet<_> = self.clock.keys()
            .chain(other.clock.keys())
            .collect();

        let mut self_greater = false;
        let mut other_greater = false;

        for peer_id in all_peers {
            let self_ts = self.get(peer_id);
            let other_ts = other.get(peer_id);

            if self_ts > other_ts {
                self_greater = true;
            } else if other_ts > self_ts {
                other_greater = true;
            }
        }

        match (self_greater, other_greater) {
            (true, false) => ClockOrdering::After,
            (false, true) => ClockOrdering::Before,
            (false, false) => ClockOrdering::Equal,
            (true, true) => ClockOrdering::Concurrent,
        }
    }

    pub fn is_concurrent(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), ClockOrdering::Concurrent)
    }

    pub fn happens_before(&self, other: &VectorClock) -> bool {
        matches!(self.compare(other), ClockOrdering::Before)
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
    fn test_vector_clock_ordering() {
        let peer1 = make_peer_id(1);
        let peer2 = make_peer_id(2);

        let mut clock1 = VectorClock::new();
        clock1.increment(peer1);

        let mut clock2 = VectorClock::new();
        clock2.increment(peer1);
        clock2.increment(peer2);

        assert_eq!(clock1.compare(&clock2), ClockOrdering::Before);
        assert_eq!(clock2.compare(&clock1), ClockOrdering::After);
    }

    #[test]
    fn test_concurrent_clocks() {
        let peer1 = make_peer_id(1);
        let peer2 = make_peer_id(2);

        let mut clock1 = VectorClock::new();
        clock1.increment(peer1);

        let mut clock2 = VectorClock::new();
        clock2.increment(peer2);

        assert_eq!(clock1.compare(&clock2), ClockOrdering::Concurrent);
        assert!(clock1.is_concurrent(&clock2));
    }
}
