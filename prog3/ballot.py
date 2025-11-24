from dataclasses import dataclass
from typing import List, Optional
import json
from zk_circuit import ZKProof
from homomorphic import PaillierPublicKey


@dataclass
class Ballot:
    encrypted_votes: List[int]
    zk_proof: ZKProof
    election_id: str
    timestamp: float
    
    def to_json(self) -> str:
        data = {
            'encrypted_votes': self.encrypted_votes,
            'zk_proof': self.zk_proof.to_json(),
            'election_id': self.election_id,
            'timestamp': self.timestamp
        }
        return json.dumps(data)
    
    @staticmethod
    def from_json(json_str: str) -> 'Ballot':
        data = json.loads(json_str)
        return Ballot(
            encrypted_votes=data['encrypted_votes'],
            zk_proof=ZKProof.from_json(data['zk_proof']),
            election_id=data['election_id'],
            timestamp=data['timestamp']
        )
    
    def get_nullifier(self) -> bytes:
        return self.zk_proof.nullifier


class BallotCreator:
    def __init__(self, public_key: PaillierPublicKey, num_options: int):
        self.public_key = public_key
        self.num_options = num_options
    
    def create_ballot(self, option_index: int, zk_proof: ZKProof, 
                     election_id: str, timestamp: float) -> Ballot:
        if option_index < 0 or option_index >= self.num_options:
            raise ValueError(f"Invalid option index: {option_index}")
        
        encrypted_votes = []
        for i in range(self.num_options):
            vote_value = 1 if i == option_index else 0
            encrypted_votes.append(self.public_key.encrypt(vote_value))
        
        return Ballot(
            encrypted_votes=encrypted_votes,
            zk_proof=zk_proof,
            election_id=election_id,
            timestamp=timestamp
        )


class BallotValidator:
    def __init__(self, merkle_root: bytes):
        self.merkle_root = merkle_root
    
    def validate_ballot(self, ballot: Ballot) -> bool:
        from zk_circuit import VotingCircuit
        
        if not ballot.encrypted_votes:
            return False
        
        circuit = VotingCircuit(merkle_depth=20)
        
        if not circuit.verify_membership_proof(ballot.zk_proof, self.merkle_root):
            return False
        
        return True
    
    def validate_vote_format(self, ballot: Ballot, expected_num_options: int) -> bool:
        return len(ballot.encrypted_votes) == expected_num_options
