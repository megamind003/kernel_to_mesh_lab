import time
import sys
from crypto_primitives import MerkleTree, KeyPairGenerator
from voter_registry import FastVoterRegistry
from homomorphic import PaillierCryptosystem
from zk_circuit import VotingCircuit
import config


def benchmark_merkle_tree(num_leaves: int):
    print(f"\nBenchmark: Merkle Tree ({num_leaves} leaves)")
    
    leaves = [f"voter_{i}".encode() for i in range(num_leaves)]
    
    start = time.time()
    tree = MerkleTree(leaves)
    build_time = time.time() - start
    
    start = time.time()
    proof = tree.get_proof(num_leaves // 2)
    proof_time = time.time() - start
    
    start = time.time()
    valid = MerkleTree.verify_proof(proof, leaves[num_leaves // 2])
    verify_time = time.time() - start
    
    print(f"  Build time: {build_time*1000:.2f}ms")
    print(f"  Proof generation: {proof_time*1000:.2f}ms")
    print(f"  Proof verification: {verify_time*1000:.2f}ms")
    
    return build_time, proof_time, verify_time


def benchmark_paillier(key_size: int, num_operations: int):
    print(f"\nBenchmark: Paillier ({key_size}-bit, {num_operations} ops)")
    
    start = time.time()
    crypto = PaillierCryptosystem(key_size=key_size)
    public_key, private_key = crypto.generate_keypair()
    keygen_time = time.time() - start
    
    start = time.time()
    ciphertexts = [public_key.encrypt(1) for _ in range(num_operations)]
    encrypt_time = time.time() - start
    
    start = time.time()
    result = ciphertexts[0]
    for ct in ciphertexts[1:]:
        result = public_key.add_encrypted(result, ct)
    add_time = time.time() - start
    
    start = time.time()
    plaintext = private_key.decrypt(result)
    decrypt_time = time.time() - start
    
    print(f"  Key generation: {keygen_time*1000:.2f}ms")
    print(f"  Encryption ({num_operations}x): {encrypt_time*1000:.2f}ms ({encrypt_time/num_operations*1000:.2f}ms each)")
    print(f"  Homomorphic addition ({num_operations-1}x): {add_time*1000:.2f}ms")
    print(f"  Decryption: {decrypt_time*1000:.2f}ms")
    print(f"  Result: {plaintext}")
    
    return keygen_time, encrypt_time, add_time, decrypt_time


def benchmark_zk_proof(num_voters: int):
    print(f"\nBenchmark: ZK Proof Generation ({num_voters} voters)")
    
    public_keys = [f"voter_{i}".encode() for i in range(num_voters)]
    registry = FastVoterRegistry(public_keys)
    
    target_pk = public_keys[num_voters // 2]
    
    start = time.time()
    merkle_proof = registry.get_membership_proof(target_pk)
    merkle_proof_time = time.time() - start
    
    private_key, _ = KeyPairGenerator.generate()
    private_key_bytes = KeyPairGenerator.serialize_private_key(private_key)
    
    circuit = VotingCircuit(merkle_depth=config.MERKLE_DEPTH)
    siblings = [sibling for sibling, _ in merkle_proof.siblings]
    leaf_index = registry.get_leaf_index(target_pk)
    
    start = time.time()
    zk_proof = circuit.create_membership_proof(
        private_key_bytes,
        siblings,
        registry.get_merkle_root(),
        leaf_index,
        config.ELECTION_ID
    )
    proof_gen_time = time.time() - start
    
    start = time.time()
    valid = circuit.verify_membership_proof(zk_proof, registry.get_merkle_root())
    verify_time = time.time() - start
    
    print(f"  Merkle proof extraction: {merkle_proof_time*1000:.2f}ms")
    print(f"  ZK proof generation: {proof_gen_time*1000:.2f}ms")
    print(f"  ZK proof verification: {verify_time*1000:.2f}ms")
    print(f"  Valid: {valid}")
    
    return merkle_proof_time, proof_gen_time, verify_time


def main():
    print("="*80)
    print("AIGIS PERFORMANCE BENCHMARKS")
    print("="*80)
    
    benchmark_merkle_tree(1000)
    benchmark_merkle_tree(10000)
    benchmark_merkle_tree(100000)
    
    benchmark_paillier(512, 10)
    benchmark_paillier(512, 100)
    
    benchmark_zk_proof(100)
    benchmark_zk_proof(1000)
    benchmark_zk_proof(10000)
    
    print("\n" + "="*80)
    print("BENCHMARKS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
