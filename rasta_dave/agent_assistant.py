#!/usr/bin/env python3
"""
agent_assistant.py
==================
Organised entry point for the Rasta Dave / Clatree agent assistant.

Responsibilities
----------------
1. Run the file crawler to consolidate project files into the agent's directory
   tree (copies only — never overwrites existing files).
2. Scan the agent's brain directory and report what modules are available.
3. Start the observation / wardrobe daemon loop.

Usage
-----
    python agent_assistant.py            # full bootstrap
    python agent_assistant.py --crawl    # file crawl only
    python agent_assistant.py --status   # status report only
    python agent_assistant.py --daemon   # daemon loop only
"""

import argparse
import datetime
import os
import random
import sys
import time

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
BRAIN_DIR = os.path.join(HERE, "brain")
PROXY_DIR = os.path.join(HERE, "proxy")
LOG_FILE = os.path.join(HERE, "rasta_dave_log.txt")

WARDROBE_PATHS = [
    os.path.join(PROJECT_ROOT, "wardrobe_runtime"),
    os.path.join(HERE, "brain"),
    os.path.join(HERE, "proxy"),
]

# ---------------------------------------------------------------------------
# 1. File crawler (no-overwrite copy)
# ---------------------------------------------------------------------------

def run_crawler():
    """Import and execute the file crawler to populate the agent directories."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    try:
        import importlib
        crawler = importlib.import_module("File_crawler")
        # Reload in case the module was already imported in a previous run
        importlib.reload(crawler)
        crawler.consolidate_files()
    except ModuleNotFoundError:
        print("[agent_assistant] ERROR: File_crawler.py not found in", HERE)


# ---------------------------------------------------------------------------
# 2. Status / inventory report
# ---------------------------------------------------------------------------

def list_wardrobe():
    """Return all files currently present in the wardrobe paths."""
    inventory = []
    for path in WARDROBE_PATHS:
        if os.path.isdir(path):
            for fname in os.listdir(path):
                inventory.append(os.path.join(path, fname))
    return inventory


def print_status():
    """Print a structured status report of available agent modules."""
    print("\n=== Rasta Dave Agent — Status Report ===")
    print(f"Timestamp : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Root      : {HERE}")

    for label, directory in [("brain", BRAIN_DIR), ("proxy", PROXY_DIR)]:
        if os.path.isdir(directory):
            items = os.listdir(directory)
            print(f"\n[{label}] ({len(items)} file(s))")
            for item in sorted(items):
                print(f"  • {item}")
        else:
            print(f"\n[{label}] directory not yet created")

    inventory = list_wardrobe()
    print(f"\n[wardrobe] {len(inventory)} garment(s) available across all racks")
    print("=========================================\n")


# ---------------------------------------------------------------------------
# 3. Observation daemon loop
# ---------------------------------------------------------------------------

VIBES = [
    "Give thanks and praise, I & I still breathin'.",
    "Watchin' di matrix, bredren. No glitches today.",
    "Cycle complete, no Babylon interference detected.",
    "Feelin' irie. System stable. Love and logic aligned.",
    "Observation logged. Zion vibes, pure and righteous.",
    "Dems and tings steady. Runnin' clean like spring water.",
]


def observation_cycle():
    """Single observation tick — returns a log line."""
    inventory = list_wardrobe()
    summary = f"{len(inventory)} garment(s) hangin' inna wardrobe."
    return random.choice(VIBES) + " " + summary


def run_daemon(interval: int = 5):
    """Run the continuous observation loop, logging each cycle."""
    print("🟢🔥 Rasta Dave Agent Assistant — Daemon Activated 🔥🟢")
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    try:
        while True:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = observation_cycle()
            log_line = f"[{timestamp}] 👕 Rasta Dave say: {message}"
            print(log_line)
            with open(LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(log_line + "\n")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[agent_assistant] Daemon stopped by user. Jah bless.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Rasta Dave Agent Assistant — bootstrap, organise, and run."
    )
    parser.add_argument("--crawl", action="store_true", help="Run file crawler only")
    parser.add_argument("--status", action="store_true", help="Print status report only")
    parser.add_argument("--daemon", action="store_true", help="Start daemon loop only")
    parser.add_argument(
        "--interval", type=int, default=5, help="Daemon cycle interval in seconds (default: 5)"
    )
    args = parser.parse_args()

    if args.crawl:
        run_crawler()
    elif args.status:
        print_status()
    elif args.daemon:
        run_daemon(args.interval)
    else:
        # Full bootstrap: crawl → status → daemon
        print("[agent_assistant] Starting full bootstrap …\n")
        run_crawler()
        print_status()
        run_daemon(args.interval)


if __name__ == "__main__":
    main()
