import hashlib
import random
from typing import List, Dict
from dataclasses import dataclass
import time

@dataclass
class Contribution:
    participant_id: str
    previous_hash: str
    pubkey_point: int  # Simulated G1 point
    randomness_hash: str
    timestamp: float

class TrustedSetup:
    """
    MPC Ceremony for generating Common Reference String (CRS).
    Simulates a Powers of Tau ceremony.
    """
    def __init__(self, circuit_size: int):
        self.circuit_size = circuit_size
        self.contributions: List[Contribution] = []
        self.current_crs: int = 1  # Simulated G1 generator
        self.finalized = False
        
    def contribute(self, participant_id: str, randomness: int) -> Contribution:
        if self.finalized:
            raise ValueError("Ceremony is finalized")
            
        # In a real curve, this would be point multiplication: P_new = P_old ^ s
        # Here we simulate with modular exponentiation to show the accumulation logic
        # using a large prime to simulate the field.
        field_modulus = 2**256 - 2**32 - 977
        
        previous_hash = self._get_last_hash()
        
        # Update CRS
        self.current_crs = pow(self.current_crs * randomness, 1, field_modulus)
        
        contribution = Contribution(
            participant_id=participant_id,
            previous_hash=previous_hash,
            pubkey_point=self.current_crs,
            randomness_hash=hashlib.sha256(str(randomness).encode()).hexdigest(),
            timestamp=time.time()
        )
        
        self.contributions.append(contribution)
        return contribution
        
    def _get_last_hash(self) -> str:
        if not self.contributions:
            return "0" * 64
        
        last = self.contributions[-1]
        data = f"{last.participant_id}{last.pubkey_point}{last.randomness_hash}"
        return hashlib.sha256(data.encode()).hexdigest()
        
    def verify_chain(self) -> bool:
        """Verifies the hash chain of contributions"""
        prev_hash = "0" * 64
        for c in self.contributions:
            if c.previous_hash != prev_hash:
                return False
            
            data = f"{c.participant_id}{c.pubkey_point}{c.randomness_hash}"
            curr_hash = hashlib.sha256(data.encode()).hexdigest()
            prev_hash = curr_hash
            
        return True
        
    def finalize(self) -> int:
        self.finalized = True
        return self.current_crs
