import sys
import os
import time
from crypto_primitives import KeyPairGenerator
from voter_registry import VoterRegistry, FastVoterRegistry
from homomorphic import PaillierCryptosystem
from bulletin_board import BulletinBoard
from ballot import BallotCreator
from zk_circuit import VotingCircuit
import config


def main():
    print("="*80)
    print("AIGIS VOTING SYSTEM - DEMO")
    print("="*80)
    
    print("\n1. Setting up cryptographic parameters...")
    crypto = PaillierCryptosystem(key_size=config.PAILLIER_KEY_SIZE)
    public_key, private_key = crypto.generate_keypair()
    print(f"   Generated Paillier keypair ({config.PAILLIER_KEY_SIZE}-bit)")
    
    print("\n2. Registering voters...")
    num_voters = config.DEMO_NUM_VOTERS
    voters = []
    for i in range(num_voters):
        priv_key, pub_key = KeyPairGenerator.generate()
        voters.append((priv_key, pub_key))
    
    public_keys = [KeyPairGenerator.serialize_public_key(pub) for _, pub in voters]
    registry = FastVoterRegistry(public_keys)
    
    print(f"   Registered {num_voters} voters")
    print(f"   Merkle root: {registry.get_merkle_root().hex()[:32]}...")
    
    print("\n3. Initializing bulletin board...")
    db_path = "demo_bulletin.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    bulletin_board = BulletinBoard(db_path, registry.get_merkle_root())
    print(f"   Bulletin board initialized at {db_path}")
    
    print("\n4. Simulating voting...")
    num_votes = config.DEMO_NUM_VOTES
    votes_cast = [0, 0, 0]
    
    for i in range(num_votes):
        voter_idx = i % num_voters
        voter_priv, voter_pub = voters[voter_idx]
        voter_pub_bytes = KeyPairGenerator.serialize_public_key(voter_pub)
        
        vote_option = i % config.NUM_OPTIONS
        votes_cast[vote_option] += 1
        
        merkle_proof = registry.get_membership_proof(voter_pub_bytes)
        leaf_index = registry.get_leaf_index(voter_pub_bytes)
        
        circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
        voter_priv_bytes = KeyPairGenerator.serialize_private_key(voter_priv)
        siblings = [sibling for sibling, _ in merkle_proof.siblings]
        
        zk_proof = circuit.create_membership_proof(
            voter_priv_bytes,
            siblings,
            registry.get_merkle_root(),
            leaf_index,
            config.ELECTION_ID
        )
        
        ballot_creator = BallotCreator(public_key, num_options=config.NUM_OPTIONS)
        ballot = ballot_creator.create_ballot(
            vote_option,
            zk_proof,
            config.ELECTION_ID,
            time.time() + i
        )
        
        success = bulletin_board.append_ballot(ballot)
        if success:
            print(f"   Vote {i+1}/{num_votes}: Option {vote_option} (accepted)")
        else:
            print(f"   Vote {i+1}/{num_votes}: REJECTED")
    
    print(f"\n5. Computing tally...")
    ballots = bulletin_board.get_all_ballots()
    print(f"   Total ballots in bulletin board: {len(ballots)}")
    
    encrypted_tallies = [0, 0, 0]
    for ballot in ballots:
        for i in range(config.NUM_OPTIONS):
            if encrypted_tallies[i] == 0:
                encrypted_tallies[i] = ballot.encrypted_votes[i]
            else:
                encrypted_tallies[i] = public_key.add_encrypted(
                    encrypted_tallies[i],
                    ballot.encrypted_votes[i]
                )
    
    decrypted_tallies = [private_key.decrypt(ct) for ct in encrypted_tallies]
    
    print("\n6. Election Results:")
    print(f"   Expected: {votes_cast}")
    print(f"   Actual:   {decrypted_tallies}")
    
    for i in range(config.NUM_OPTIONS):
        print(f"   Option {i}: {decrypted_tallies[i]} votes")
    
    print("\n7. Verifying bulletin board integrity...")
    all_verified = bulletin_board.verify_all_ballots()
    print(f"   All ballots verified: {all_verified}")
    
    print("\n8. Testing double-voting prevention...")
    voter_priv, voter_pub = voters[0]
    voter_pub_bytes = KeyPairGenerator.serialize_public_key(voter_pub)
    
    merkle_proof = registry.get_membership_proof(voter_pub_bytes)
    leaf_index = registry.get_leaf_index(voter_pub_bytes)
    
    circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
    voter_priv_bytes = KeyPairGenerator.serialize_private_key(voter_priv)
    siblings = [sibling for sibling, _ in merkle_proof.siblings]
    
    zk_proof = circuit.create_membership_proof(
        voter_priv_bytes,
        siblings,
        registry.get_merkle_root(),
        leaf_index,
        config.ELECTION_ID
    )
    
    ballot_creator = BallotCreator(public_key, num_options=config.NUM_OPTIONS)
    duplicate_ballot = ballot_creator.create_ballot(
        0,
        zk_proof,
        config.ELECTION_ID,
        time.time() + 1000
    )
    
    success = bulletin_board.append_ballot(duplicate_ballot)
    print(f"   Duplicate vote rejected: {not success}")
    
    bulletin_board.close()
    
    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
