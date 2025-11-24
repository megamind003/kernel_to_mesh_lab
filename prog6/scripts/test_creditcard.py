#!/usr/bin/env python3

import pandas as pd
import asyncio
import httpx
import time
import sys
from datetime import datetime
import numpy as np


async def load_creditcard_data(csv_path: str, limit: int = None):
    print(f"Loading creditcard.csv from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    if limit:
        df = df.head(limit)
    
    print(f"Loaded {len(df)} transactions")
    print(f"Fraud cases (Class=1): {(df['Class'] == 1).sum()}")
    print(f"Normal cases (Class=0): {(df['Class'] == 0).sum()}")
    
    return df


async def send_transaction(client: httpx.AsyncClient, row: pd.Series, index: int):
    payload = {
        "idempotency_key": f"creditcard_test_{index}_{int(time.time()*1000000)}",
        "user_id": int(index % 10000) + 1,
        "amount": float(abs(row['Amount'])) if row['Amount'] > 0 else 1.0,
        "currency": "EUR",
        "merchant_id": f"merchant_{int(index % 1000):05d}",
        "merchant_category": "retail",
        "location": {
            "latitude": 45.4642 + (index % 100) * 0.01,
            "longitude": 9.1900 + (index % 100) * 0.01
        }
    }
    
    start_time = time.perf_counter()
    
    try:
        response = await client.post(
            "http://localhost:8000/api/v1/transaction",
            json=payload,
            timeout=5.0
        )
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            actual_fraud = row['Class'] == 1
            detected_fraud = data.get('status') == 'blocked'
            
            return {
                'success': True,
                'latency_ms': latency_ms,
                'actual_fraud': actual_fraud,
                'detected_fraud': detected_fraud,
                'fraud_score': data.get('fraud_score', 0),
                'false_negative': actual_fraud and not detected_fraud,
                'false_positive': not actual_fraud and detected_fraud
            }
        else:
            return {
                'success': False,
                'latency_ms': latency_ms,
                'error': response.status_code
            }
    
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            'success': False,
            'latency_ms': latency_ms,
            'error': str(e)
        }


async def run_stress_test(csv_path: str, batch_size: int = 100, total_requests: int = 1000):
    df = await load_creditcard_data(csv_path, total_requests)
    
    print(f"\nStarting stress test with {total_requests} requests...")
    print("Checking API health...")
    
    async with httpx.AsyncClient() as client:
        try:
            health_response = await client.get("http://localhost:8000/health")
            if health_response.status_code == 200:
                print("API is healthy")
            else:
                print(f"WARNING: API health check returned {health_response.status_code}")
        except Exception as e:
            print(f"ERROR: Cannot connect to API: {e}")
            print("Make sure the API is running: uvicorn src.api.main:app --host 0.0.0.0 --port 8000")
            sys.exit(1)
        
        results = []
        start_time = time.time()
        
        for batch_start in range(0, len(df), batch_size):
            batch_end = min(batch_start + batch_size, len(df))
            batch_df = df.iloc[batch_start:batch_end]
            
            tasks = [
                send_transaction(client, row, batch_start + idx)
                for idx, (_, row) in enumerate(batch_df.iterrows())
            ]
            
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            completed = len(results)
            print(f"Progress: {completed}/{len(df)} ({completed/len(df)*100:.1f}%)", end='\r')
        
        total_time = time.time() - start_time
    
    print(f"\n\nTest completed in {total_time:.2f} seconds")
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    if successful:
        latencies = [r['latency_ms'] for r in successful]
        false_negatives = [r for r in successful if r.get('false_negative')]
        false_positives = [r for r in successful if r.get('false_positive')]
        
        print("\n" + "="*80)
        print("PANOPTICON STRESS TEST RESULTS")
        print("="*80)
        print(f"\nTotal Requests: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print(f"Success Rate: {len(successful)/len(results)*100:.2f}%")
        print(f"Throughput: {len(results)/total_time:.2f} TPS")
        
        print(f"\nLatency Statistics:")
        print(f"  Min: {min(latencies):.2f}ms")
        print(f"  Mean: {np.mean(latencies):.2f}ms")
        print(f"  Median (P50): {np.percentile(latencies, 50):.2f}ms")
        print(f"  P95: {np.percentile(latencies, 95):.2f}ms")
        print(f"  P99: {np.percentile(latencies, 99):.2f}ms")
        print(f"  Max: {max(latencies):.2f}ms")
        
        print(f"\nFraud Detection:")
        print(f"  False Negatives: {len(false_negatives)}")
        print(f"  False Positives: {len(false_positives)}")
        
        p99_latency = np.percentile(latencies, 99)
        
        print("\n" + "="*80)
        print("PASS CRITERIA VALIDATION")
        print("="*80)
        
        p99_target = 50.0
        print(f"\n1. P99 Latency < {p99_target}ms")
        if p99_latency < p99_target:
            print(f"   ✓ PASS: {p99_latency:.2f}ms < {p99_target}ms")
        else:
            print(f"   ✗ FAIL: {p99_latency:.2f}ms >= {p99_target}ms")
        
        print(f"\n2. No False Negatives on Class=1")
        if len(false_negatives) == 0:
            print(f"   ✓ PASS: 0 false negatives")
        else:
            print(f"   ✗ FAIL: {len(false_negatives)} false negatives detected")
        
        print("\n" + "="*80)
        
        if p99_latency < p99_target and len(false_negatives) == 0:
            print("FINAL RESULT: ✓ ALL TESTS PASSED")
        else:
            print("FINAL RESULT: ✗ SOME TESTS FAILED")
        
        print("="*80)
        
        return p99_latency < p99_target and len(false_negatives) == 0
    
    else:
        print("ERROR: No successful requests")
        return False


if __name__ == "__main__":
    csv_path = "/home/boss/Documents/prog/data_hardcore/creditcard.csv"
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    num_requests = 1000
    if len(sys.argv) > 2:
        num_requests = int(sys.argv[2])
    
    passed = asyncio.run(run_stress_test(csv_path, batch_size=100, total_requests=num_requests))
    
    sys.exit(0 if passed else 1)
