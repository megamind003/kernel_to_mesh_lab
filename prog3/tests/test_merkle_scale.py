import pytest
import time
import csv
from typing import Set, List
from crypto_primitives import MerkleTree, KeyPairGenerator
from voter_registry import FastVoterRegistry
from zk_circuit import VotingCircuit
import config
import sys

csv.field_size_limit(sys.maxsize)


def extract_unique_emails(csv_path: str, max_rows: int = None) -> Set[str]:
    import re
    unique_emails = set()
    
    print(f"Extracting unique emails from {csv_path}")
    start_time = time.time()
    
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break
            
            if 'message' in row and row['message']:
                message = row['message']
                found_emails = email_pattern.findall(message)
                for email in found_emails:
                    email = email.strip().lower()
                    unique_emails.add(email)
            
            if (i + 1) % 10000 == 0:
                print(f"  Processed {i + 1} rows, found {len(unique_emails)} unique emails")
    
    elapsed = time.time() - start_time
    print(f"Extraction complete: {len(unique_emails)} unique emails in {elapsed:.2f}s")
    
    return unique_emails


def test_merkle_scale_full():
    print("\n" + "="*80)
    print("STRESS TEST: Merkle Scale (Full Dataset)")
    print("="*80)
    
    unique_emails = extract_unique_emails(config.STRESS_TEST_DATA_PATH)
    
    print(f"\nBuilding Merkle tree from {len(unique_emails)} emails...")
    
    email_list = sorted(list(unique_emails))
    public_keys = [email.encode('utf-8') for email in email_list]
    
    tree_start = time.time()
    registry = FastVoterRegistry(public_keys)
    tree_time = time.time() - tree_start
    
    print(f"Merkle tree built in {tree_time:.3f}s")
    print(f"Merkle root: {registry.get_merkle_root().hex()[:32]}...")
    
    target_email = config.STRESS_TEST_TARGET_EMAIL
    
    if target_email not in unique_emails:
        print(f"\nWARNING: Target email '{target_email}' not found in dataset")
        print("Using first email instead for demonstration")
        target_email = email_list[0]
    
    print(f"\nGenerating ZK proof for: {target_email}")
    
    target_pk = target_email.encode('utf-8')
    
    proof_start = time.time()
    
    merkle_proof = registry.get_membership_proof(target_pk)
    
    private_key, public_key = KeyPairGenerator.generate()
    private_key_bytes = KeyPairGenerator.serialize_private_key(private_key)
    
    circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
    
    siblings = [sibling for sibling, _ in merkle_proof.siblings]
    leaf_index = registry.get_leaf_index(target_pk)
    
    zk_proof = circuit.create_membership_proof(
        private_key_bytes,
        siblings,
        registry.get_merkle_root(),
        leaf_index,
        config.ELECTION_ID
    )
    
    proof_time = time.time() - proof_start
    
    print(f"Proof generated in {proof_time:.3f}s")
    print(f"Nullifier: {zk_proof.nullifier.hex()[:32]}...")
    
    verify_start = time.time()
    is_valid = circuit.verify_membership_proof(zk_proof, registry.get_merkle_root())
    verify_time = time.time() - verify_start
    
    print(f"Proof verified in {verify_time:.3f}s")
    print(f"Proof valid: {is_valid}")
    
    print("\n" + "="*80)
    print("RESULTS:")
    print(f"  Total unique emails: {len(unique_emails)}")
    print(f"  Merkle tree construction: {tree_time:.3f}s")
    print(f"  Proof generation: {proof_time:.3f}s")
    print(f"  Proof verification: {verify_time:.3f}s")
    print(f"  Target: {config.STRESS_TEST_MAX_TIME}s")
    print("="*80)
    
    assert is_valid, "Proof verification failed"
    assert proof_time < config.STRESS_TEST_MAX_TIME, \
        f"Proof generation took {proof_time:.3f}s, exceeds {config.STRESS_TEST_MAX_TIME}s limit"
    
    print("\nSTRESS TEST PASSED")


def test_merkle_scale_subset():
    print("\n" + "="*80)
    print("STRESS TEST: Merkle Scale (Subset - 50k emails)")
    print("="*80)
    
    unique_emails = extract_unique_emails(config.STRESS_TEST_DATA_PATH, max_rows=50000)
    
    email_list = sorted(list(unique_emails))
    public_keys = [email.encode('utf-8') for email in email_list]
    
    tree_start = time.time()
    registry = FastVoterRegistry(public_keys)
    tree_time = time.time() - tree_start
    
    print(f"Merkle tree built in {tree_time:.3f}s")
    
    target_email = email_list[0] if email_list else "test@example.com"
    target_pk = target_email.encode('utf-8')
    
    proof_start = time.time()
    
    merkle_proof = registry.get_membership_proof(target_pk)
    private_key, _ = KeyPairGenerator.generate()
    private_key_bytes = KeyPairGenerator.serialize_private_key(private_key)
    
    circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
    siblings = [sibling for sibling, _ in merkle_proof.siblings]
    leaf_index = registry.get_leaf_index(target_pk)
    
    zk_proof = circuit.create_membership_proof(
        private_key_bytes,
        siblings,
        registry.get_merkle_root(),
        leaf_index,
        config.ELECTION_ID
    )
    
    proof_time = time.time() - proof_start
    
    print(f"Proof generated in {proof_time:.3f}s")
    
    is_valid = circuit.verify_membership_proof(zk_proof, registry.get_merkle_root())
    
    assert is_valid
    assert proof_time < config.STRESS_TEST_MAX_TIME
    
    print("SUBSET TEST PASSED")


if __name__ == "__main__":
    test_merkle_scale_subset()
    test_merkle_scale_full()
