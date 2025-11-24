import argparse
import time
import requests
import json
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from crypto_primitives import KeyPairGenerator, NullifierGenerator
from voter_registry import FastVoterRegistry
from ballot import BallotCreator, Ballot
from homomorphic import PaillierPublicKey
from zk_circuit import VotingCircuit


class VotingClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.private_key: Optional[ed25519.Ed25519PrivateKey] = None
        self.public_key: Optional[ed25519.Ed25519PublicKey] = None
        self.election_info: Optional[dict] = None
    
    def fetch_election_info(self):
        response = requests.get(f"{self.server_url}/info")
        response.raise_for_status()
        self.election_info = response.json()
        print(f"Election ID: {self.election_info['election_id']}")
        print(f"Options: {self.election_info['num_options']}")
        print(f"Total ballots: {self.election_info['total_ballots']}")
    
    def generate_keys(self):
        self.private_key, self.public_key = KeyPairGenerator.generate()
        pub_key_bytes = KeyPairGenerator.serialize_public_key(self.public_key)
        print(f"Generated key pair")
        print(f"Public key: {pub_key_bytes.hex()[:32]}...")
    
    def load_keys(self, private_key_hex: str):
        private_key_bytes = bytes.fromhex(private_key_hex)
        self.private_key = KeyPairGenerator.load_private_key(private_key_bytes)
        self.public_key = self.private_key.public_key()
        print("Loaded existing key pair")
    
    def cast_vote(self, option_index: int, voter_registry: FastVoterRegistry):
        if not self.private_key or not self.election_info:
            raise ValueError("Client not initialized. Generate keys and fetch election info first.")
        
        public_key_bytes = KeyPairGenerator.serialize_public_key(self.public_key)
        merkle_root = voter_registry.get_merkle_root()
        
        merkle_proof = voter_registry.get_membership_proof(public_key_bytes)
        leaf_index = voter_registry.get_leaf_index(public_key_bytes)
        
        private_key_bytes = KeyPairGenerator.serialize_private_key(self.private_key)
        
        circuit = VotingCircuit(merkle_depth=20)
        
        siblings = [sibling for sibling, _ in merkle_proof.siblings]
        
        zk_proof = circuit.create_membership_proof(
            private_key_bytes,
            siblings,
            merkle_root,
            leaf_index,
            self.election_info['election_id']
        )
        
        public_key_obj = PaillierPublicKey(
            n=self.election_info['public_key_n'],
            g=self.election_info['public_key_g'],
            n_squared=self.election_info['public_key_n'] ** 2
        )
        
        ballot_creator = BallotCreator(public_key_obj, self.election_info['num_options'])
        ballot = ballot_creator.create_ballot(
            option_index,
            zk_proof,
            self.election_info['election_id'],
            time.time()
        )
        
        response = requests.post(
            f"{self.server_url}/submit_ballot",
            json={'ballot_json': ballot.to_json()}
        )
        
        if response.status_code == 200:
            print(f"Vote cast successfully for option {option_index}")
            return True
        else:
            print(f"Vote rejected: {response.json()['detail']}")
            return False
    
    def get_tally(self):
        response = requests.get(f"{self.server_url}/tally")
        response.raise_for_status()
        tally = response.json()
        
        print("\nElection Results:")
        print(f"Total votes: {tally['total_votes']}")
        for i, count in enumerate(tally['decrypted_tally']):
            print(f"  Option {i}: {count} votes")
        
        return tally
    
    def get_audit_log(self):
        response = requests.get(f"{self.server_url}/audit")
        response.raise_for_status()
        audit = response.json()
        
        print("\nAudit Log:")
        print(f"Total ballots: {audit['total_ballots']}")
        print(f"All verified: {audit['all_verified']}")
        
        return audit


def main():
    parser = argparse.ArgumentParser(description="AIGIS Voting Client")
    parser.add_argument('--server', default='http://localhost:8000', help='Server URL')
    parser.add_argument('--generate-keys', action='store_true', help='Generate new key pair')
    parser.add_argument('--vote', type=int, help='Cast vote for option index')
    parser.add_argument('--tally', action='store_true', help='Get current tally')
    parser.add_argument('--audit', action='store_true', help='Get audit log')
    
    args = parser.parse_args()
    
    client = VotingClient(args.server)
    
    if args.generate_keys:
        client.generate_keys()
    
    if args.tally:
        client.fetch_election_info()
        client.get_tally()
    
    if args.audit:
        client.get_audit_log()


if __name__ == "__main__":
    main()
