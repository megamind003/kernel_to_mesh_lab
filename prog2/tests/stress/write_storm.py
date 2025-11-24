import socket
import csv
import json
import time
import sys
import os

CSV_PATH = "../../../data_hardcore/btcusd_1-min_data.csv"
HOST = "127.0.0.1"
PORT = 9191

def connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    return s

def run_storm():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    print(f"Starting Write Storm using {CSV_PATH}...")
    
    count = 0
    start_time = time.time()
    
    try:
        s = connect()
        reader = csv.reader(open(CSV_PATH, 'r'))
        headers = next(reader) # Skip header
        
        # Use a buffered writer approach or just raw socket sends for speed
        # For simplicity, we'll do line by line but reuse connection
        
        for row in reader:
            if len(row) < 2: continue
            
            # Key: Timestamp, Value: JSON of row
            key = row[0]
            val = json.dumps(dict(zip(headers, row)))
            
            cmd = f"PUT {key} {val}\n"
            s.sendall(cmd.encode())
            
            # Wait for OK (synchronous for correctness, async for speed)
            # To test "Write Storm", we might want to pipeline, but our server is simple
            resp = s.recv(1024) 
            if b"OK" not in resp:
                print(f"Error on key {key}: {resp}")
            
            count += 1
            if count % 1000 == 0:
                elapsed = time.time() - start_time
                rate = count / elapsed
                print(f"\rProcessed {count} rows. Rate: {rate:.2f} ops/sec", end="")
                
            if count >= 10000: # Limit for quick verification
                break
                
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        s.close()
        
    total_time = time.time() - start_time
    print(f"\n\nDone. Total: {count} rows in {total_time:.2f}s. Avg Rate: {count/total_time:.2f} ops/sec")

if __name__ == "__main__":
    run_storm()
