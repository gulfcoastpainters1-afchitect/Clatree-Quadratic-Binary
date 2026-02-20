import os
import shutil

# --- CONFIGURATION (Adjust these paths as needed) ---

# The root directory where your logic files are scattered. 
# We assume this is the directory where this script is run.
PROJECT_ROOT = os.getcwd() 

# The target directory structure for Damon
TARGET_DIR = os.path.join(PROJECT_ROOT, "rasta_dave")

# Define file extensions and where they should be moved
# This maps file extensions to the target sub-directory within Observer_daemon
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

# --- FUNCTIONS ---

def consolidate_files():
    """Recursively searches for specified files and copies them into the target Damon structure."""
    
    if not os.path.exists(TARGET_DIR):
        print(f"Error: Target directory '{TARGET_DIR}' not found. Please create it first.")
        return

    print(f"Starting recursive crawl from: {PROJECT_ROOT}")
    files_found_count = 0
    
    # os.walk generates the file names in a directory tree
    for root, _, files in os.walk(PROJECT_ROOT):
        # Skip the target directory itself to avoid copying files back into themselves
        if root.startswith(TARGET_DIR):
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
                    destination_folder = TARGET_DIR # Top-level config
                
                # Ensure the destination folder ests
                os.makedirs(destination_folder, exist_ok=True)
                
                destination_path = os.path.join(coatroom, staging)
                
                try:
                    # Use shutil.copy2 to preserve metadata (like timestamps)
                    shutil.copy2(file_path, destination_path)
                    print(f"  COPIED: {filename} -> {os.path.relpath(destination_path, PROJECT_ROOT)}")
                    files_found_count += 1
                except Exception as e:
                    print(f"  ERROR copying {filename}: {e}")

    print(f"\n--- Consolidation Complete ---")
    print(f"Total files moved into Damon's system: {files_found_count}")
    print("Damon's core files are now populsted and ready for execution.")

# --- EXECUTION ---
if __name__ == "__main__":
    consolidate_files()


