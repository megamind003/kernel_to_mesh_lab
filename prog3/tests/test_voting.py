import pytest
import os
import time
from crypto_primitives import KeyPairGenerator
from voter_registry import VoterRegistry, FastVoterRegistry
from ballot import BallotCreator, BallotValidator
from bulletin_board import BulletinBoard
from homomorphic import PaillierCryptosystem
from zk_circuit import VotingCircuit
import config


@pytest.fixture
def setup_election():
    crypto = PaillierCryptosystem(key_size=512)
    public_key, private_key = crypto.generate_keypair()
    
    voters = []
    for i in range(10):
        priv_key, pub_key = KeyPairGenerator.generate()
        voters.append((priv_key, pub_key))
    
    public_keys = [KeyPairGenerator.serialize_public_key(pub) for _, pub in voters]
    registry = FastVoterRegistry(public_keys)
    
    db_path = "test_bulletin.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    bulletin_board = BulletinBoard(db_path, registry.get_merkle_root())
    
    yield {
        'crypto': crypto,
        'public_key': public_key,
        'private_key': private_key,
        'voters': voters,
        'registry': registry,
        'bulletin_board': bulletin_board,
        'db_path': db_path
    }
    
    bulletin_board.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_end_to_end_voting(setup_election):
    setup = setup_election
    
    voter_priv, voter_pub = setup['voters'][0]
    voter_pub_bytes = KeyPairGenerator.serialize_public_key(voter_pub)
    
    merkle_proof = setup['registry'].get_membership_proof(voter_pub_bytes)
    leaf_index = setup['registry'].get_leaf_index(voter_pub_bytes)
    
    circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
    
    voter_priv_bytes = KeyPairGenerator.serialize_private_key(voter_priv)
    siblings = [sibling for sibling, _ in merkle_proof.siblings]
    
    zk_proof = circuit.create_membership_proof(
        voter_priv_bytes,
        siblings,
        setup['registry'].get_merkle_root(),
        leaf_index,
        config.ELECTION_ID
    )
    
    ballot_creator = BallotCreator(setup['public_key'], num_options=3)
    ballot = ballot_creator.create_ballot(
        option_index=1,
        zk_proof=zk_proof,
        election_id=config.ELECTION_ID,
        timestamp=time.time()
    )
    
    success = setup['bulletin_board'].append_ballot(ballot)
    assert success, "Ballot should be accepted"
    
    assert setup['bulletin_board'].get_ballot_count() == 1


def test_double_voting_prevention(setup_election):
    setup = setup_election
    
    voter_priv, voter_pub = setup['voters'][0]
    voter_pub_bytes = KeyPairGenerator.serialize_public_key(voter_pub)
    
    merkle_proof = setup['registry'].get_membership_proof(voter_pub_bytes)
    leaf_index = setup['registry'].get_leaf_index(voter_pub_bytes)
    
    circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
    voter_priv_bytes = KeyPairGenerator.serialize_private_key(voter_priv)
    siblings = [sibling for sibling, _ in merkle_proof.siblings]
    
    zk_proof = circuit.create_membership_proof(
        voter_priv_bytes,
        siblings,
        setup['registry'].get_merkle_root(),
        leaf_index,
        config.ELECTION_ID
    )
    
    ballot_creator = BallotCreator(setup['public_key'], num_options=3)
    
    ballot1 = ballot_creator.create_ballot(1, zk_proof, config.ELECTION_ID, time.time())
    success1 = setup['bulletin_board'].append_ballot(ballot1)
    assert success1
    
    ballot2 = ballot_creator.create_ballot(2, zk_proof, config.ELECTION_ID, time.time() + 1)
    success2 = setup['bulletin_board'].append_ballot(ballot2)
    assert not success2, "Second ballot with same nullifier should be rejected"


def test_tally_computation(setup_election):
    setup = setup_election
    
    votes = [0, 1, 1, 0, 2]
    
    for i, vote_option in enumerate(votes):
        voter_priv, voter_pub = setup['voters'][i]
        voter_pub_bytes = KeyPairGenerator.serialize_public_key(voter_pub)
        
        merkle_proof = setup['registry'].get_membership_proof(voter_pub_bytes)
        leaf_index = setup['registry'].get_leaf_index(voter_pub_bytes)
        
        circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
        voter_priv_bytes = KeyPairGenerator.serialize_private_key(voter_priv)
        siblings = [sibling for sibling, _ in merkle_proof.siblings]
        
        zk_proof = circuit.create_membership_proof(
            voter_priv_bytes,
            siblings,
            setup['registry'].get_merkle_root(),
            leaf_index,
            config.ELECTION_ID
        )
        
        ballot_creator = BallotCreator(setup['public_key'], num_options=3)
        ballot = ballot_creator.create_ballot(
            vote_option,
            zk_proof,
            config.ELECTION_ID,
            time.time() + i
        )
        
        setup['bulletin_board'].append_ballot(ballot)
    
    ballots = setup['bulletin_board'].get_all_ballots()
    assert len(ballots) == 5
    
    encrypted_tallies = [0, 0, 0]
    for ballot in ballots:
        for i in range(3):
            if encrypted_tallies[i] == 0:
                encrypted_tallies[i] = ballot.encrypted_votes[i]
            else:
                encrypted_tallies[i] = setup['public_key'].add_encrypted(
                    encrypted_tallies[i],
                    ballot.encrypted_votes[i]
                )
    
    decrypted_tallies = [setup['private_key'].decrypt(ct) for ct in encrypted_tallies]
    
    assert decrypted_tallies[0] == 2
    assert decrypted_tallies[1] == 2
    assert decrypted_tallies[2] == 1


def test_universal_verifiability(setup_election):
    setup = setup_election
    
    voter_priv, voter_pub = setup['voters'][0]
    voter_pub_bytes = KeyPairGenerator.serialize_public_key(voter_pub)
    
    merkle_proof = setup['registry'].get_membership_proof(voter_pub_bytes)
    leaf_index = setup['registry'].get_leaf_index(voter_pub_bytes)
    
    circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
    voter_priv_bytes = KeyPairGenerator.serialize_private_key(voter_priv)
    siblings = [sibling for sibling, _ in merkle_proof.siblings]
    
    zk_proof = circuit.create_membership_proof(
        voter_priv_bytes,
        siblings,
        setup['registry'].get_merkle_root(),
        leaf_index,
        config.ELECTION_ID
    )
    
    ballot_creator = BallotCreator(setup['public_key'], num_options=3)
    ballot = ballot_creator.create_ballot(1, zk_proof, config.ELECTION_ID, time.time())
    
    setup['bulletin_board'].append_ballot(ballot)
    
    all_verified = setup['bulletin_board'].verify_all_ballots()
    assert all_verified, "All ballots should be verifiable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
