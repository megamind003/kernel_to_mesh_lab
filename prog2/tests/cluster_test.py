import subprocess
import time
import os
import signal
import shutil

HYDRA_BIN = "./hydra"
NODE1_DIR = "./tmp/node1"
NODE2_DIR = "./tmp/node2"

def setup():
    if os.path.exists(NODE1_DIR):
        shutil.rmtree(NODE1_DIR)
    if os.path.exists(NODE2_DIR):
        shutil.rmtree(NODE2_DIR)
    os.makedirs(NODE1_DIR)
    os.makedirs(NODE2_DIR)

def start_node(id, addr, data_dir, join=None):
    cmd = [HYDRA_BIN, "--id", id, "--addr", addr, "--data-dir", data_dir]
    if join:
        cmd.extend(["--join", join])
    
    print(f"[TEST] Starting {id} on {addr}...")
    env = os.environ.copy()
    cwd = os.getcwd()
    lib_path = os.path.join(cwd, "libhydra/target/release")
    env["LD_LIBRARY_PATH"] = lib_path + ":" + env.get("LD_LIBRARY_PATH", "")
    
    return subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )

def test_cluster():
    setup()
    
    p1 = start_node("node1", "127.0.0.1:9191", NODE1_DIR)
    time.sleep(2) # Wait for node1 to start
    
    p2 = start_node("node2", "127.0.0.1:9192", NODE2_DIR, join="127.0.0.1:9191")
    time.sleep(5) # Wait for gossip
    
    # Check logs
    print("[TEST] Checking logs...")
    
    # Kill nodes
    os.killpg(os.getpgid(p1.pid), signal.SIGKILL)
    os.killpg(os.getpgid(p2.pid), signal.SIGKILL)
    
    out1, _ = p1.communicate()
    out2, _ = p2.communicate()
    
    log1 = out1.decode()
    log2 = out2.decode()
    
    print("--- Node 1 Log ---")
    print(log1)
    print("--- Node 2 Log ---")
    print(log2)
    
    if "Node node2 joined the cluster" in log1 or "Node node2 (127.0.0.1:9092) requesting to join" in log1:
        print("[TEST] SUCCESS: Node 1 saw Node 2 join")
    else:
        print("[TEST] FAILURE: Node 1 did not see Node 2")
        exit(1)

    if "Joined cluster successfully" in log2 or "Added seed node" in log2:
        print("[TEST] SUCCESS: Node 2 joined successfully")
    else:
        print("[TEST] FAILURE: Node 2 did not report success")
        exit(1)

if __name__ == "__main__":
    test_cluster()
