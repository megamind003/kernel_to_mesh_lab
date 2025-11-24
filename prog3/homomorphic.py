import random
from typing import List, Tuple
from dataclasses import dataclass
import math


def is_prime(n: int, k: int = 5) -> bool:
    if n < 2:
        return False
    if n == 2 or n == 3:
        return True
    if n % 2 == 0:
        return False
    
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2
    
    for _ in range(k):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        
        if x == 1 or x == n - 1:
            continue
        
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    
    return True


def generate_prime(bits: int) -> int:
    while True:
        p = random.getrandbits(bits)
        p |= (1 << bits - 1) | 1
        if is_prime(p):
            return p


def lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)


def mod_inverse(a: int, m: int) -> int:
    def extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
        if a == 0:
            return b, 0, 1
        gcd, x1, y1 = extended_gcd(b % a, a)
        x = y1 - (b // a) * x1
        y = x1
        return gcd, x, y
    
    gcd, x, _ = extended_gcd(a % m, m)
    if gcd != 1:
        raise ValueError("Modular inverse does not exist")
    return (x % m + m) % m


@dataclass
class PaillierPublicKey:
    n: int
    g: int
    n_squared: int
    
    def encrypt(self, plaintext: int) -> int:
        if plaintext < 0 or plaintext >= self.n:
            raise ValueError(f"Plaintext must be in range [0, {self.n})")
        
        r = random.randrange(1, self.n)
        while math.gcd(r, self.n) != 1:
            r = random.randrange(1, self.n)
        
        c = (pow(self.g, plaintext, self.n_squared) * pow(r, self.n, self.n_squared)) % self.n_squared
        return c
    
    def add_encrypted(self, c1: int, c2: int) -> int:
        return (c1 * c2) % self.n_squared
    
    def multiply_encrypted_by_constant(self, ciphertext: int, constant: int) -> int:
        return pow(ciphertext, constant, self.n_squared)


@dataclass
class PaillierPrivateKey:
    lambda_val: int
    mu: int
    public_key: PaillierPublicKey
    
    def decrypt(self, ciphertext: int) -> int:
        n = self.public_key.n
        n_squared = self.public_key.n_squared
        
        u = pow(ciphertext, self.lambda_val, n_squared)
        l = (u - 1) // n
        m = (l * self.mu) % n
        return m


class PaillierCryptosystem:
    def __init__(self, key_size: int = 512):
        self.key_size = key_size
        self.public_key: PaillierPublicKey = None
        self.private_key: PaillierPrivateKey = None
    
    def generate_keypair(self) -> Tuple[PaillierPublicKey, PaillierPrivateKey]:
        p = generate_prime(self.key_size // 2)
        q = generate_prime(self.key_size // 2)
        
        while p == q:
            q = generate_prime(self.key_size // 2)
        
        n = p * q
        n_squared = n * n
        g = n + 1
        
        lambda_val = lcm(p - 1, q - 1)
        
        u = pow(g, lambda_val, n_squared)
        l = (u - 1) // n
        mu = mod_inverse(l, n)
        
        public_key = PaillierPublicKey(n=n, g=g, n_squared=n_squared)
        private_key = PaillierPrivateKey(lambda_val=lambda_val, mu=mu, public_key=public_key)
        
        self.public_key = public_key
        self.private_key = private_key
        
        return public_key, private_key


class HomomorphicTally:
    def __init__(self, public_key: PaillierPublicKey):
        self.public_key = public_key
        self.encrypted_votes: List[int] = []
    
    def add_vote(self, encrypted_vote: int):
        self.encrypted_votes.append(encrypted_vote)
    
    def compute_tally(self) -> int:
        if not self.encrypted_votes:
            return self.public_key.encrypt(0)
        
        result = self.encrypted_votes[0]
        for vote in self.encrypted_votes[1:]:
            result = self.public_key.add_encrypted(result, vote)
        
        return result
    
    def decrypt_tally(self, private_key: PaillierPrivateKey) -> int:
        encrypted_tally = self.compute_tally()
        return private_key.decrypt(encrypted_tally)


class MultiOptionBallot:
    def __init__(self, public_key: PaillierPublicKey, num_options: int):
        self.public_key = public_key
        self.num_options = num_options
    
    def encode_vote(self, option_index: int) -> List[int]:
        if option_index < 0 or option_index >= self.num_options:
            raise ValueError(f"Invalid option index: {option_index}")
        
        encrypted_ballot = []
        for i in range(self.num_options):
            vote_value = 1 if i == option_index else 0
            encrypted_ballot.append(self.public_key.encrypt(vote_value))
        
        return encrypted_ballot
    
    @staticmethod
    def tally_multi_option(ballots: List[List[int]], public_key: PaillierPublicKey) -> List[int]:
        if not ballots:
            return []
        
        num_options = len(ballots[0])
        tallies = []
        
        for option_idx in range(num_options):
            tally = HomomorphicTally(public_key)
            for ballot in ballots:
                tally.add_vote(ballot[option_idx])
            tallies.append(tally.compute_tally())
        
        return tallies
    
    @staticmethod
    def decrypt_tallies(encrypted_tallies: List[int], private_key: PaillierPrivateKey) -> List[int]:
        return [private_key.decrypt(ct) for ct in encrypted_tallies]
