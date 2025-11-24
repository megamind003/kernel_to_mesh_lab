import random
from threshold_crypto import ThresholdPaillier, KeyShare

def test_lagrange():
    print("Testing Lagrange Interpolation...")
    
    # Setup
    tp = ThresholdPaillier(key_size=512, num_participants=5, threshold=3)
    
    # Manually simulate generation to know the secret
    secret = 123456789
    coeffs = [secret] + [random.randint(1, 1000) for _ in range(2)] # Degree 2 (threshold 3)
    
    shares = []
    for i in range(1, 6):
        val = 0
        for exp, coeff in enumerate(coeffs):
            val += coeff * (i ** exp)
        shares.append(KeyShare(index=i, value=val))
        
    print(f"Secret: {secret}")
    print(f"Shares: {[s.value for s in shares]}")
    
    # Reconstruct
    selected_shares = [shares[0], shares[2], shares[4]] # 1, 3, 5
    print(f"Selected indices: {[s.index for s in selected_shares]}")
    
    # Copy-paste logic from threshold_crypto.py
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
        
    print(f"Final Num: {final_num}")
    print(f"Final Den: {final_den}")
    
    if final_num % final_den != 0:
        print("ERROR: Not divisible")
    else:
        reconstructed = final_num // final_den
        print(f"Reconstructed: {reconstructed}")
        assert reconstructed == secret
        print("SUCCESS")

if __name__ == "__main__":
    test_lagrange()
