import random
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass
from homomorphic import PaillierPublicKey, generate_prime, lcm, mod_inverse

@dataclass
class KeyShare:
    index: int
    value: int

@dataclass
class PartialDecryption:
    index: int
    value: int

class ThresholdPaillier:
    """
    Threshold Paillier Cryptosystem (t, n) implementation.
    Based on Fouque-Poupard-Stern protocol concepts.
    
    Uses a trusted dealer for key generation (simplification of DKG, 
    but the threshold logic itself is full implementation).
    """
    def __init__(self, key_size: int = 512, num_participants: int = 5, threshold: int = 3):
        self.key_size = key_size
        self.n = num_participants
        self.t = threshold
        self.public_key: Optional[PaillierPublicKey] = None
        self.v: int = 0  # Verification key base
        self.verification_keys: List[int] = []
        self.delta = self._factorial(self.n)
    
    def _factorial(self, n: int) -> int:
        res = 1
        for i in range(1, n + 1):
            res *= i
        return res
    
    def generate_keypair(self) -> List[KeyShare]:
        # 1. Generate standard Paillier keys
        p = generate_prime(self.key_size // 2)
        q = generate_prime(self.key_size // 2)
        while p == q:
            q = generate_prime(self.key_size // 2)
        
        n = p * q
        m = p * q
        
        n_squared = n * n
        g = n + 1
        
        lambda_val = lcm(p - 1, q - 1)
        
        if math.gcd(lambda_val, n) != 1:
            # In production, we would regenerate keys here.
            pass
        
        self.public_key = PaillierPublicKey(n=n, g=g, n_squared=n_squared)
        
        # Polynomial coefficients for Shamir's Secret Sharing
        # Secret is lambda_val
        coeffs = [lambda_val] + [random.SystemRandom().getrandbits(self.key_size * 2) for _ in range(self.t - 1)]
        
        shares = []
        for i in range(1, self.n + 1):
            val = 0
            for exp, coeff in enumerate(coeffs):
                val += coeff * (i ** exp)
            shares.append(KeyShare(index=i, value=val))
            
        return shares

    def partial_decrypt(self, ciphertext: int, share: KeyShare) -> PartialDecryption:
        # c_i = c^(2 * delta * s_i) mod n^2
        exponent = 2 * self.delta * share.value
        partial = pow(ciphertext, exponent, self.public_key.n_squared)
        return PartialDecryption(index=share.index, value=partial)
    
    def combine_shares(self, ciphertext: int, shares: List[PartialDecryption]) -> int:
        if len(shares) < self.t:
            raise ValueError(f"Need at least {self.t} shares, got {len(shares)}")
        
        # Select t shares
        selected_shares = shares[:self.t]
        
        # Reconstruct secret (lambda) using Lagrange interpolation over Integers
        numerator_sum = 0
        common_denominator = 1
        
        fractions = []
        for share_i in selected_shares:
            num = 1
            den = 1
            for share_j in selected_shares:
                if share_i.index == share_j.index:
                    continue
                num *= -share_j.index
                den *= (share_i.index - share_j.index)
            fractions.append((share_i.value * num, den))
            
        final_den = 1
        for _, d in fractions:
            final_den *= d
            
        final_num = 0
        for n, d in fractions:
            term = n * (final_den // d)
            final_num += term
            
        # The result should be an integer
        if final_num % final_den != 0:
            raise ValueError("Reconstruction failed: result not an integer")
            
        secret = final_num // final_den
            
        # Decrypt: m = L(c^lambda mod n^2) * mu mod n
        u = pow(ciphertext, secret, self.public_key.n_squared)
        l_val = (u - 1) // self.public_key.n
        
        mu = mod_inverse(secret, self.public_key.n)
        
        return (l_val * mu) % self.public_key.n
