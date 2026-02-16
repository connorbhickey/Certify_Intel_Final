
"""
Backup Manager Module
Handles automated database backups and retention policies.
"""
import os
import shutil
import glob
from datetime import datetime
from pathlib import Path

# Configuration
BACKUP_DIR = "backups"
DB_FILE = "certify_intel.db"
MAX_BACKUPS = 7  # Keep last 7 days

def ensure_backup_dir():
    """Ensure backup directory exists."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created backup directory: {BACKUP_DIR}")

def create_backup():
    """Create a backup of the current database."""
    try:
        ensure_backup_dir()
        
        if not os.path.exists(DB_FILE):
            print(f"Warning: Database file {DB_FILE} not found. Skipping backup.")
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{BACKUP_DIR}/certify_intel_backup_{timestamp}.db"
        
        # Copy the file
        shutil.copy2(DB_FILE, backup_filename)
        print(f"Database backup created: {backup_filename}")
        
        # Prune old backups
        prune_old_backups()
        
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False

def prune_old_backups():
    """Remove backups older than MAX_BACKUPS."""
    try:
        # Get list of backup files
        backups = glob.glob(f"{BACKUP_DIR}/certify_intel_backup_*.db")
        
        # Sort by creation time (newest first)
        backups.sort(key=os.path.getctime, reverse=True)
        
        # Identify files to remove
        to_remove = backups[MAX_BACKUPS:]
        
        for file_path in to_remove:
            os.remove(file_path)
            print(f"Removed old backup: {file_path}")
            
    except Exception as e:
        print(f"Error pruning backups: {e}")

if __name__ == "__main__":
    # Manual test
    create_backup()
