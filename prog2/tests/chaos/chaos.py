import subprocess
import time
import socket
import os
import signal
import shutil

HYDRA_BIN = "../hydra"
DATA_DIR = "../tmp/hydra_chaos_test"
PORT = 9191
ADDR = f"127.0.0.1:{PORT}"

def setup():
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
    os.makedirs(DATA_DIR)

def start_node():
    print(f"[CHAOS] Starting Hydra node on {ADDR}...")
    env = os.environ.copy()
    # Ensure library path is set for the child process
    cwd = os.getcwd()
    lib_path = os.path.join(cwd, "libhydra/target/release")
    env["LD_LIBRARY_PATH"] = lib_path + ":" + env.get("LD_LIBRARY_PATH", "")
    
    proc = subprocess.Popen(
        [HYDRA_BIN, "--id", "node1", "--addr", ADDR, "--data-dir", DATA_DIR],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid # Create new process group for easy killing
    )
    time.sleep(1) # Wait for startup
    return proc

def send_cmd(cmd):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("127.0.0.1", PORT))
            s.sendall(f"{cmd}\n".encode())
            data = s.recv(1024)
            return data.decode().strip()
    except Exception as e:
        return f"ERROR: {e}"

def test_chaos():
    setup()
    proc = start_node()
    
    try:
        print("[CHAOS] 1. Writing keys...")
        resp = send_cmd("PUT key1 value1")
        if resp != "OK":
            print(f"FAILED: Expected OK, got '{resp}'")
            print("STDOUT:", proc.stdout.read().decode())
            print("STDERR:", proc.stderr.read().decode())
            assert resp == "OK"
        
        resp = send_cmd("PUT key2 value2")
        assert resp == "OK"
        
        print("[CHAOS] 2. Verifying keys...")
        resp = send_cmd("GET key1")
        assert resp == "VALUE value1"
        
        print("[CHAOS] 3. KILLING NODE (SIGKILL)...")
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait()
        
        print("[CHAOS] 4. Restarting node...")
        proc = start_node()
        
        print("[CHAOS] 5. Verifying persistence (WAL Recovery)...")
        val = send_cmd("GET key1")
        print(f"[CHAOS] Got: {val}")
        assert val == "VALUE value1"
        assert send_cmd("GET key2") == "VALUE value2"
        
        print("[CHAOS] SUCCESS: Data survived process death!")
        
    finally:
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)

if __name__ == "__main__":
    test_chaos()
