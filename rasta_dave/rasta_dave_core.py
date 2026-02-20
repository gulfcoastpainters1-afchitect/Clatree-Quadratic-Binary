core/rasta_dave_core.py

# /core/rasta_dave_core.py
import time
from pathlib import Path
from core.identity_manager import create_identity, load_identity
from shared.memory_bridge import check_inbox

DAEMON_NAME = "rasta_dave"

# 1. ensure identity exists
create_identity(DAEMON_NAME)
identity = load_identity(DAEMON_NAME)
print(f"[{DAEMON_NAME}] loaded identity {identity['daemon_id'][:8]}…")

# 2. set up folders
BASE = Path(__file__).resolve().parent.parent
INBOX = BASE / "archives" / f"{DAEMON_NAME}_memory" / "inbox"
INBOX.mkdir(parents=True, exist_ok=True)

# 3. main loop
def main_loop():
    print(f"[{DAEMON_NAME}] entering loop.  press Ctrl+C to exit.")
    while True:
        msgs = check_inbox(DAEMON_NAME)
        if msgs:
            print(f"[{DAEMON_NAME}] received {len(msgs)} verified message(s):")
            for m in msgs:
                print("   →", m.get("task"), m.get("context"))
        time.sleep(5)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print(f"\n[{DAEMON_NAME}] shutting down cleanly.")
Memory_wheel_appender.py

def log_to_wheel(message):
    wheel_path = BASE / "archives" / f"{DAEMON_NAME}_memory" / "memory_wheel.jsonl"
    wheel_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "daemon": DAEMON_NAME,
        "message": message
    }
    with open(wheel_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
