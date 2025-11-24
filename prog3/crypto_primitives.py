import hashlib
import hmac
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


@dataclass
class MerkleProof:
    leaf_index: int
    leaf_hash: bytes
    siblings: List[Tuple[bytes, bool]]
    root: bytes


class MerkleTree:
    def __init__(self, leaves: List[bytes]):
        if not leaves:
            raise ValueError("Cannot create Merkle tree with empty leaves")
        
        self.leaves = leaves
        self.leaf_count = len(leaves)
        self.tree = self._build_tree()
        self.root = self.tree[0][0] if self.tree else b''
    
    def _hash(self, data: bytes) -> bytes:
        return hashlib.sha256(data).digest()
    
    def _hash_pair(self, left: bytes, right: bytes) -> bytes:
        return self._hash(left + right)
    
    def _build_tree(self) -> List[List[bytes]]:
        current_level = [self._hash(leaf) for leaf in self.leaves]
        tree = [current_level[:]]
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(self._hash_pair(left, right))
            current_level = next_level
            tree.insert(0, current_level)
        
        return tree
    
    def get_proof(self, leaf_index: int) -> MerkleProof:
        if leaf_index < 0 or leaf_index >= self.leaf_count:
            raise ValueError(f"Invalid leaf index: {leaf_index}")
        
        siblings = []
        current_index = leaf_index
        
        for level in range(len(self.tree) - 1, 0, -1):
            level_data = self.tree[level]
            is_right = current_index % 2 == 1
            
            if is_right:
                sibling_index = current_index - 1
            else:
                sibling_index = current_index + 1
            
            if sibling_index < len(level_data):
                siblings.append((level_data[sibling_index], is_right))
            else:
                siblings.append((level_data[current_index], is_right))
            
            current_index //= 2
        
        leaf_hash = self.tree[-1][leaf_index]
        return MerkleProof(
            leaf_index=leaf_index,
            leaf_hash=leaf_hash,
            siblings=siblings,
            root=self.root
        )
    
    @staticmethod
    def verify_proof(proof: MerkleProof, leaf_data: bytes) -> bool:
        current_hash = hashlib.sha256(leaf_data).digest()
        
        if current_hash != proof.leaf_hash:
            return False
        
        for sibling_hash, is_right in proof.siblings:
            if is_right:
                current_hash = hashlib.sha256(sibling_hash + current_hash).digest()
            else:
                current_hash = hashlib.sha256(current_hash + sibling_hash).digest()
        
        return current_hash == proof.root


class NullifierGenerator:
    @staticmethod
    def generate(secret_key: bytes, election_id: str) -> bytes:
        return hmac.new(
            secret_key,
            election_id.encode('utf-8'),
            hashlib.sha256
        ).digest()
    
    @staticmethod
    def verify(nullifier: bytes, secret_key: bytes, election_id: str) -> bool:
        expected = NullifierGenerator.generate(secret_key, election_id)
        return hmac.compare_digest(nullifier, expected)


class KeyPairGenerator:
    @staticmethod
    def generate() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key
    
    @staticmethod
    def serialize_public_key(public_key: ed25519.Ed25519PublicKey) -> bytes:
        return public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    @staticmethod
    def serialize_private_key(private_key: ed25519.Ed25519PrivateKey) -> bytes:
        return private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    @staticmethod
    def load_public_key(key_bytes: bytes) -> ed25519.Ed25519PublicKey:
        return ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)
    
    @staticmethod
    def load_private_key(key_bytes: bytes) -> ed25519.Ed25519PrivateKey:
        return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)


def generate_random_bytes(length: int = 32) -> bytes:
    return os.urandom(length)
