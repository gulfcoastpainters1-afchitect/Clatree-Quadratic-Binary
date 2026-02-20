Ctree_War_lib.py

war_lib.py

Claytree-specific utility library for Rasta Dave and Wardrobe Runtime

All custom tools, states, utils, and processors go here

Hashtags = Descriptive comments only. Not placeholders.

import os import json from datetime import datetime

-----------------------

State Polarity Orientator (SPO)

-----------------------

def state_polarity_orientator(state_name: str, value: float) -> str: """Determines the polarity of a given state. Positive:  0.1 to 1.0 Negative: -0.1 to -1.0 Neutral: between -0.1 and 0.1 (exclusive) """ if value >= 0.1: return f"{state_name}_positive" elif value <= -0.1: return f"{state_name}_negative" else: return f"{state_name}_neutral"

-----------------------

Log memory event to file

-----------------------

def log_event(log_path: str, event: str) -> None: with open(log_path, 'a') as log_file: log_file.write(f"[{datetime.now()}] {event}\n")

-----------------------

JSON utility loader/saver

-----------------------

def load_json(file_path: str): with open(file_path, 'r') as f: return json.load(f)

def save_json(file_path: str, data): with open(file_path, 'w') as f: json.dump(data, f, indent=2)

-----------------------

File crawler (deep scan)

-----------------------

def deep_scan_files(root_dir: str, extensions: tuple = ('.py', '.json', '.txt')): matches = [] for dirpath, dirnames, filenames in os.walk(root_dir): for file in filenames: if file.endswith(extensions): matches.append(os.path.join(dirpath, file)) return matches

-----------------------

Example of future utility (stubs)

-----------------------

def checksum_file(path): pass

def parse_chat_memory(file): pass

def run_learning_cycle(context): pass

def visualize_gradient(): pass

End of war_lib.py


