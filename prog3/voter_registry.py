from typing import List, Dict, Optional
import pickle
from dataclasses import dataclass
from crypto_primitives import MerkleTree, MerkleProof, KeyPairGenerator
from cryptography.hazmat.primitives.asymmetric import ed25519


@dataclass
class VoterRecord:
    voter_id: str
    public_key_bytes: bytes
    
    def __hash__(self):
        return hash(self.voter_id)


class VoterRegistry:
    def __init__(self):
        self.voters: Dict[str, VoterRecord] = {}
        self.merkle_tree: Optional[MerkleTree] = None
        self.public_key_to_index: Dict[bytes, int] = {}
    
    def register_voter(self, voter_id: str, public_key: ed25519.Ed25519PublicKey):
        public_key_bytes = KeyPairGenerator.serialize_public_key(public_key)
        
        if voter_id in self.voters:
            raise ValueError(f"Voter {voter_id} already registered")
        
        voter_record = VoterRecord(voter_id=voter_id, public_key_bytes=public_key_bytes)
        self.voters[voter_id] = voter_record
        
        self._rebuild_merkle_tree()
    
    def _rebuild_merkle_tree(self):
        if not self.voters:
            self.merkle_tree = None
            self.public_key_to_index = {}
            return
        
        sorted_voters = sorted(self.voters.values(), key=lambda v: v.voter_id)
        leaves = [voter.public_key_bytes for voter in sorted_voters]
        
        self.merkle_tree = MerkleTree(leaves)
        
        self.public_key_to_index = {
            voter.public_key_bytes: idx 
            for idx, voter in enumerate(sorted_voters)
        }
    
    def get_merkle_root(self) -> bytes:
        if self.merkle_tree is None:
            raise ValueError("No voters registered")
        return self.merkle_tree.root
    
    def get_membership_proof(self, public_key: ed25519.Ed25519PublicKey) -> MerkleProof:
        public_key_bytes = KeyPairGenerator.serialize_public_key(public_key)
        
        if public_key_bytes not in self.public_key_to_index:
            raise ValueError("Public key not found in registry")
        
        leaf_index = self.public_key_to_index[public_key_bytes]
        return self.merkle_tree.get_proof(leaf_index)
    
    def verify_membership(self, public_key: ed25519.Ed25519PublicKey) -> bool:
        public_key_bytes = KeyPairGenerator.serialize_public_key(public_key)
        return public_key_bytes in self.public_key_to_index
    
    def get_voter_count(self) -> int:
        return len(self.voters)
    
    def save_to_file(self, filepath: str):
        data = {
            'voters': self.voters,
            'public_key_to_index': self.public_key_to_index
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    @staticmethod
    def load_from_file(filepath: str) -> 'VoterRegistry':
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        registry = VoterRegistry()
        registry.voters = data['voters']
        registry.public_key_to_index = data['public_key_to_index']
        registry._rebuild_merkle_tree()
        
        return registry
    
    def get_all_public_keys(self) -> List[bytes]:
        sorted_voters = sorted(self.voters.values(), key=lambda v: v.voter_id)
        return [voter.public_key_bytes for voter in sorted_voters]


class FastVoterRegistry:
    def __init__(self, public_keys: List[bytes]):
        if not public_keys:
            raise ValueError("Cannot create registry with empty public keys")
        
        self.public_keys = public_keys
        self.merkle_tree = MerkleTree(public_keys)
        self.public_key_to_index = {pk: idx for idx, pk in enumerate(public_keys)}
    
    def get_merkle_root(self) -> bytes:
        return self.merkle_tree.root
    
    def get_membership_proof(self, public_key: bytes) -> MerkleProof:
        if public_key not in self.public_key_to_index:
            raise ValueError("Public key not found in registry")
        
        leaf_index = self.public_key_to_index[public_key]
        return self.merkle_tree.get_proof(leaf_index)
    
    def get_leaf_index(self, public_key: bytes) -> int:
        if public_key not in self.public_key_to_index:
            raise ValueError("Public key not found in registry")
        return self.public_key_to_index[public_key]
