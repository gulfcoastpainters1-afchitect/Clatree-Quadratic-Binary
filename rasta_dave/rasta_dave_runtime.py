# rasta_dave_runtime.py

# Daemon assistant for file traversal, memory wheel logging, and AI lifecycle tracking.

import os
import time
import hashlib
import json
from datetime import datetime

# SETTINGS

WATCH_DIR = "/"
MEMORY_DIR = "/storage/kotrune/rasta_dave/memory_wheels"
SCAN_TYPES = [".py", ".json", ".txt", ".log", ".gguf"]
CYCLE_LENGTH = 136  # seconds


def hash_file(path):
    try:
        with open(path, 'rb') as f:
            data = f.read()
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return None


def scan_files():
    scanned = []
    for root, _, files in os.walk(WATCH_DIR):
        for file in files:
            if any(file.endswith(ext) for ext in SCAN_TYPES):
                full_path = os.path.join(root, file)
                file_hash = hash_file(full_path)
                if file_hash:
                    scanned.append({
                        "path": full_path,
                        "hash": file_hash,
                        "timestamp": datetime.utcnow().isoformat()
                    })
    return scanned


def save_memory_wheel(data):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    filename = f"wheel_{int(time.time())}.json"
    full_path = os.path.join(MEMORY_DIR, filename)
    with open(full_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[+] Saved memory wheel to {full_path}")


def run_cycle():
    print("[+] Rasta Dave is traversing the system...")
    memory_data = scan_files()
    save_memory_wheel(memory_data)
    print(f"[✓] Cycle complete. Next pass in {CYCLE_LENGTH} seconds.")


if __name__ == "__main__":
    while True:
        run_cycle()
        time.sleep(CYCLE_LENGTH)
