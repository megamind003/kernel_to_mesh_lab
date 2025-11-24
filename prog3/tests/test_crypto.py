import pytest
from crypto_primitives import MerkleTree, MerkleProof, NullifierGenerator, KeyPairGenerator
from homomorphic import PaillierCryptosystem, HomomorphicTally, MultiOptionBallot
import hashlib


def test_merkle_tree_basic():
    leaves = [b"voter1", b"voter2", b"voter3", b"voter4"]
    tree = MerkleTree(leaves)
    
    assert tree.root is not None
    assert tree.leaf_count == 4
    
    proof = tree.get_proof(0)
    assert MerkleTree.verify_proof(proof, b"voter1")
    
    proof2 = tree.get_proof(2)
    assert MerkleTree.verify_proof(proof2, b"voter3")


def test_merkle_tree_odd_leaves():
    leaves = [b"voter1", b"voter2", b"voter3"]
    tree = MerkleTree(leaves)
    
    assert tree.root is not None
    
    for i in range(3):
        proof = tree.get_proof(i)
        assert MerkleTree.verify_proof(proof, leaves[i])


def test_merkle_proof_invalid():
    leaves = [b"voter1", b"voter2", b"voter3", b"voter4"]
    tree = MerkleTree(leaves)
    
    proof = tree.get_proof(0)
    
    assert not MerkleTree.verify_proof(proof, b"wrong_voter")


def test_nullifier_generation():
    secret_key = b"my_secret_key_12345678901234567890"
    election_id = "election_2025"
    
    nullifier1 = NullifierGenerator.generate(secret_key, election_id)
    nullifier2 = NullifierGenerator.generate(secret_key, election_id)
    
    assert nullifier1 == nullifier2
    
    assert NullifierGenerator.verify(nullifier1, secret_key, election_id)


def test_nullifier_uniqueness():
    secret_key = b"my_secret_key_12345678901234567890"
    
    nullifier1 = NullifierGenerator.generate(secret_key, "election_1")
    nullifier2 = NullifierGenerator.generate(secret_key, "election_2")
    
    assert nullifier1 != nullifier2


def test_keypair_generation():
    private_key, public_key = KeyPairGenerator.generate()
    
    assert private_key is not None
    assert public_key is not None
    
    pub_bytes = KeyPairGenerator.serialize_public_key(public_key)
    assert len(pub_bytes) == 32
    
    priv_bytes = KeyPairGenerator.serialize_private_key(private_key)
    assert len(priv_bytes) == 32


def test_paillier_encryption():
    crypto = PaillierCryptosystem(key_size=512)
    public_key, private_key = crypto.generate_keypair()
    
    plaintext = 42
    ciphertext = public_key.encrypt(plaintext)
    
    decrypted = private_key.decrypt(ciphertext)
    assert decrypted == plaintext


def test_paillier_homomorphic_addition():
    crypto = PaillierCryptosystem(key_size=512)
    public_key, private_key = crypto.generate_keypair()
    
    c1 = public_key.encrypt(10)
    c2 = public_key.encrypt(20)
    
    c_sum = public_key.add_encrypted(c1, c2)
    
    decrypted_sum = private_key.decrypt(c_sum)
    assert decrypted_sum == 30


def test_paillier_scalar_multiplication():
    crypto = PaillierCryptosystem(key_size=512)
    public_key, private_key = crypto.generate_keypair()
    
    c = public_key.encrypt(5)
    c_mult = public_key.multiply_encrypted_by_constant(c, 3)
    
    decrypted = private_key.decrypt(c_mult)
    assert decrypted == 15


def test_homomorphic_tally():
    crypto = PaillierCryptosystem(key_size=512)
    public_key, private_key = crypto.generate_keypair()
    
    tally = HomomorphicTally(public_key)
    
    tally.add_vote(public_key.encrypt(1))
    tally.add_vote(public_key.encrypt(1))
    tally.add_vote(public_key.encrypt(0))
    tally.add_vote(public_key.encrypt(1))
    
    result = tally.decrypt_tally(private_key)
    assert result == 3


def test_multi_option_ballot():
    crypto = PaillierCryptosystem(key_size=512)
    public_key, private_key = crypto.generate_keypair()
    
    ballot_encoder = MultiOptionBallot(public_key, num_options=3)
    
    ballot1 = ballot_encoder.encode_vote(0)
    ballot2 = ballot_encoder.encode_vote(1)
    ballot3 = ballot_encoder.encode_vote(0)
    
    assert len(ballot1) == 3
    
    ballots = [ballot1, ballot2, ballot3]
    tallies = MultiOptionBallot.tally_multi_option(ballots, public_key)
    
    decrypted = MultiOptionBallot.decrypt_tallies(tallies, private_key)
    
    assert decrypted[0] == 2
    assert decrypted[1] == 1
    assert decrypted[2] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
