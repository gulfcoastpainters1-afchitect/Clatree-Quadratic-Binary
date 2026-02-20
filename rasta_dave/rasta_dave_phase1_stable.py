

import os
import time
import datetime
import random

# ===============================
# RASTA DAVE — Wardrobe Runtime Daemon
# ===============================
# Role: The wardrobe man. Checks the racks (folders), logs what coats/modules are hangin',
# and keeps the rhythm of observation alive.

WARDROBE_PATHS = [
    os.path.expanduser("~/wardrobe_runtime"),
    os.path.expanduser("~/rasta_dave/local_actions"),
    os.path.expanduser("~/rasta_dave/brain"),
]

def list_clothes():
    """Scan all wardrobe directories and list available runtime pieces."""
    clothes = []
    for path in WARDROBE_PATHS:
        if os.path.isdir(path):
            for item in os.listdir(path):
                clothes.append(os.path.join(path, item))
    return clothes

def run_observation_cycle():
    """Main observation logic with wardrobe awareness."""
    vibes = [
        "Give thanks and praise, I & I still breathin'.",
        "Watchin' di matrix, bredren. No glitches today.",
        "Cycle complete, no Babylon interference detected.",
        "Feelin' irie. System stable. Love and logic aligned.",
        "Observation logged. Zion vibes, pure and righteous.",
        "Dems and teens steady. Runnin' clean like spring water."
    ]
    clothes = list_clothes()
    summary = f"{len(clothes)} garments hangin' inna wardrobe."
    return random.choice(vibes) + " " + summary

def main():
    print("🟢🔥 Rasta Dave Wardrobe Daemon Activated 🔥🟢")
    while True:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = run_observation_cycle()
        log_line = f"[{timestamp}] 👕 Rasta Dave say: {result}"
        print(log_line)
        with open("rasta_dave_log.txt", "a") as f:
            f.write(log_line + "\n")
        time.sleep(5)

if __name__ == "__main__":
    main()

