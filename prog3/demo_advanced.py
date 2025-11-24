import time
import random
from threshold_crypto import ThresholdPaillier
from trusted_setup import TrustedSetup
from consensus import RaftNode
from homomorphic import PaillierPublicKey

def run_demo():
    print("="*80)
    print("AIGIS ADVANCED FEATURES DEMO")
    print("="*80)
    
    # 1. Trusted Setup
    print("\n[PHASE 1] Trusted Setup Ceremony (MPC)")
    setup = TrustedSetup(circuit_size=1000)
    
    participants = ["Alice", "Bob", "Charlie", "Dave"]
    for p in participants:
        rand = random.getrandbits(256)
        contribution = setup.contribute(p, rand)
        print(f"  - {p} contributed randomness. Chain Hash: {contribution.randomness_hash[:16]}...")
        
    crs = setup.finalize()
    print(f"  > Ceremony Finalized. CRS: {str(crs)[:32]}...")
    print(f"  > Chain Integrity Verified: {setup.verify_chain()}")
    
    # 2. Threshold Key Generation
    print("\n[PHASE 2] Threshold Key Generation (3-of-5)")
    t_paillier = ThresholdPaillier(key_size=512, num_participants=5, threshold=3)
    shares = t_paillier.generate_keypair()
    
    print(f"  > Public Key (n): {t_paillier.public_key.n}")
    print(f"  > Generated {len(shares)} key shares")
    for share in shares:
        print(f"    Share {share.index}: {str(share.value)[:16]}...")
        
    # 3. Distributed Consensus
    print("\n[PHASE 3] Distributed Consensus (Raft)")
    nodes = []
    # Create 3 nodes
    node1 = RaftNode(1, [])
    node2 = RaftNode(2, [])
    node3 = RaftNode(3, [])
    
    all_nodes = [node1, node2, node3]
    for n in all_nodes:
        n.peers = all_nodes
        n.start()
        
    print("  > Nodes started. Waiting for leader election...")
    time.sleep(2)
    
    leader = None
    for n in all_nodes:
        if n.state.name == "LEADER":
            leader = n
            print(f"  > Node {n.node_id} is LEADER")
            break
            
    if leader:
        print("  > Replicating ballot via Consensus...")
        leader.replicate("BALLOT_DATA_XYZ")
        time.sleep(1)
        
        for n in all_nodes:
            print(f"    Node {n.node_id} Log: {[e.command for e in n.log]}")
            
    for n in all_nodes:
        n.stop()
        
    # 4. Threshold Decryption
    print("\n[PHASE 4] Threshold Decryption")
    # Encrypt a vote (e.g., 1)
    vote = 12345
    ciphertext = t_paillier.public_key.encrypt(vote)
    print(f"  > Encrypted Vote: {vote}")
    print(f"  > Ciphertext: {str(ciphertext)[:32]}...")
    
    # Partial Decryptions (need 3)
    print("  > Collecting partial decryptions from shares 1, 3, 5...")
    selected_shares = [shares[0], shares[2], shares[4]] # Indices 1, 3, 5
    
    # Reconstruct and decrypt
    decrypted = t_paillier.combine_shares(ciphertext, selected_shares)
    print(f"  > Decrypted Result: {decrypted}")
    
    assert decrypted == vote
    print("  > Decryption SUCCESS")
    
    print("\n" + "="*80)
    print("ADVANCED DEMO COMPLETE")
    print("="*80)

if __name__ == "__main__":
    run_demo()
