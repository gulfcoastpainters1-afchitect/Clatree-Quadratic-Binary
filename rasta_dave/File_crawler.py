import os
import shutil

# --- CONFIGURATION (Adjust these paths as needed) ---

# The root directory where your logic files are scattered.
# We assume this is the directory where this script is run.
PROJECT_ROOT = os.getcwd()

# The target directory structure for the agent
TARGET_DIR = os.path.join(PROJECT_ROOT, "rasta_dave")

# Define file extensions and where they should be copied
# This maps file extensions to the target sub-directory within rasta_dave
FILE_TARGET_MAP = {
    # Core AGI Logic, Brain, and Actions
    '.py': 'brain',         # Python scripts (The AGI logic, brain search, actions)
    '.json': 'brain',       # JSON data models or configuration (e.g., data schemas)
    '.yaml': '',            # YAML config (docker-compose, main environment settings)
    '.yml': '',

    # Proxy and Front-End/Interface Logic (for visualization of Wisdom)
    '.html': 'proxy',       # HTML files (Front-end interface)
    '.js': 'proxy',         # JavaScript files (Client-side actions/visualization)
    '.css': 'proxy',        # CSS files
}

# Directories to skip during crawl
SKIP_DIRS = {'.git', '__pycache__', 'node_modules'}

# --- FUNCTIONS ---

def consolidate_files():
    """Recursively searches for specified files and copies them into the target agent structure.

    Files are NEVER overwritten — if a file with the same name already exists at
    the destination it is left untouched and reported as SKIPPED.
    """

    if not os.path.exists(TARGET_DIR):
        print(f"Error: Target directory '{TARGET_DIR}' not found. Please create it first.")
        return

    print(f"Starting recursive crawl from: {PROJECT_ROOT}")
    files_copied = 0
    files_skipped = 0

    # os.walk generates the file names in a directory tree
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Prune directories we never want to descend into
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        # Skip the target directory itself to avoid copying files back into themselves
        if os.path.abspath(root).startswith(os.path.abspath(TARGET_DIR)):
            continue

        for filename in files:
            file_path = os.path.join(root, filename)
            _, ext = os.path.splitext(filename)

            # Check if the file extension is in our map
            if ext.lower() in FILE_TARGET_MAP:
                target_subdir = FILE_TARGET_MAP[ext.lower()]

                # Determine the final destination folder
                if target_subdir:
                    destination_folder = os.path.join(TARGET_DIR, target_subdir)
                else:
                    destination_folder = TARGET_DIR  # Top-level config

                # Ensure the destination folder exists
                os.makedirs(destination_folder, exist_ok=True)

                destination_path = os.path.join(destination_folder, filename)

                # Never overwrite an existing file
                if os.path.exists(destination_path):
                    print(f"  SKIPPED (exists): {filename}")
                    files_skipped += 1
                    continue

                try:
                    # Use shutil.copy2 to preserve metadata (like timestamps)
                    shutil.copy2(file_path, destination_path)
                    print(f"  COPIED: {filename} -> {os.path.relpath(destination_path, PROJECT_ROOT)}")
                    files_copied += 1
                except Exception as e:
                    print(f"  ERROR copying {filename}: {e}")

    print(f"\n--- Consolidation Complete ---")
    print(f"Files copied  : {files_copied}")
    print(f"Files skipped : {files_skipped} (already present, not overwritten)")
    print("Agent core files are now populated and ready for execution.")

# --- EXECUTION ---
if __name__ == "__main__":
    consolidate_files()


