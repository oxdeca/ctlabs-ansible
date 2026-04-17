#!/usr/bin/env python3
"""
Automated Vault backup & restore for 'file' storage
"""

import os
import sys
import time
import shutil
import logging
import argparse
import subprocess
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
BACKUP_DIR     = "/var/backups/openbao"
DATA_DIR       = "/opt/openbao/data"       # The path in your storage "file" { path = "..." } block
CONFIG_DIR     = "/etc/openbao.d"          # Where your openbao.hcl and certs live
OPENBAO_USER   = "openbao"                 # The Linux user that runs the Vault service
OPENBAO_GROUP  = "openbao"                 # The Linux group for the Vault service
RETENTION_DAYS = 30
LOG_FILE       = "/var/log/openbao-backup.log"

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_root():
    if os.geteuid() != 0:
        logging.error("This script must be run as root or with sudo.")
        sys.exit(1)

def run_cmd(cmd_list, shell=False):
    """Executes a system command and logs any errors."""
    try:
        subprocess.run(cmd_list, check=True, shell=shell, 
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {' '.join(cmd_list)}\nOutput: {e.stdout}")
        sys.exit(1)

def clear_directory(dir_path):
    """Empties a directory without deleting the directory itself."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return
    for filename in os.listdir(dir_path):
        file_path = os.path.join(dir_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logging.error(f"Failed to delete {file_path}. Reason: {e}")
            sys.exit(1)

def cleanup_old_backups():
    logging.info(f"Cleaning up backups older than {RETENTION_DAYS} days...")
    now = time.time()
    cutoff_time = now - (RETENTION_DAYS * 86400)
    
    if not os.path.exists(BACKUP_DIR):
        return

    for filename in os.listdir(BACKUP_DIR):
        if filename.startswith("openbao-") and filename.endswith(".tar.gz"):
            filepath = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if file_mtime < cutoff_time:
                    os.remove(filepath)
                    logging.info(f"Deleted old backup: {filename}")

# ==========================================
# COMMAND LOGIC
# ==========================================
def backup_snap():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"openbao-snap-{timestamp}.tar.gz")
    
    logging.info("Starting SNAPSHOT Backup...")
    run_cmd(["systemctl", "stop", "openbao"])
    
    # tar -czvf backup_file -C DATA_DIR .
    run_cmd(["tar", "-czvf", backup_file, "-C", DATA_DIR, "."])
    
    run_cmd(["systemctl", "start", "openbao"])
    logging.info(f"Snapshot created successfully: {backup_file}")
    cleanup_old_backups()

def backup_full():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"openbao-full-{timestamp}.tar.gz")
    
    logging.info("Starting FULL Backup (Data + Config)...")
    run_cmd(["systemctl", "stop", "openbao"])
    
    # tar -czvf backup_file DATA_DIR CONFIG_DIR
    run_cmd(["tar", "-czvf", backup_file, DATA_DIR, CONFIG_DIR])
    
    run_cmd(["systemctl", "start", "openbao"])
    logging.info(f"Full backup created successfully: {backup_file}")
    cleanup_old_backups()

def restore_snap(filepath):
    if not filepath or not os.path.isfile(filepath):
        logging.error(f"Invalid backup file: {filepath}")
        sys.exit(1)
        
    logging.info(f"Starting SNAPSHOT Restore from {filepath}...")
    run_cmd(["systemctl", "stop", "openbao"])
    
    logging.info("Clearing existing data directory...")
    clear_directory(DATA_DIR)
    
    logging.info("Extracting snapshot...")
    run_cmd(["tar", "-xzvf", filepath, "-C", DATA_DIR])
    
    logging.info("Fixing permissions...")
    run_cmd(["chown", "-R", f"{OPENBAO_USER}:{OPENBAO_GROUP}", DATA_DIR])
    
    run_cmd(["systemctl", "start", "openbao"])
    logging.info("Snapshot restore complete. You must now unseal Vault.")

def restore_full(filepath):
    if not filepath or not os.path.isfile(filepath):
        logging.error(f"Invalid backup file: {filepath}")
        sys.exit(1)
        
    logging.info(f"Starting FULL Restore from {filepath}...")
    run_cmd(["systemctl", "stop", "openbao"])
    
    logging.info("Clearing existing data and config directories...")
    clear_directory(DATA_DIR)
    clear_directory(CONFIG_DIR)
    
    logging.info("Extracting full backup...")
    # Extract to root (/) because absolute paths were used during backup_full
    run_cmd(["tar", "-xzvf", filepath, "-C", "/"])
    
    logging.info("Fixing permissions...")
    run_cmd(["chown", "-R", f"{OPENBAO_USER}:{OPENBAO_GROUP}", DATA_DIR])
    run_cmd(["chown", "-R", f"{OPENBAO_USER}:{OPENBAO_GROUP}", CONFIG_DIR])
    
    run_cmd(["systemctl", "start", "openbao"])
    logging.info("Full restore complete. You must now unseal Vault.")

# ==========================================
# MAIN ENTRY POINT
# ==========================================
if __name__ == "__main__":
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Automated Vault backup & restore for 'file' storage")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    
    # Backup commands
    subparsers.add_parser("backup-snap", help="Backs up ONLY the Vault data directory")
    subparsers.add_parser("backup-full", help="Backs up Vault data AND configuration directory")
    
    # Restore commands
    parser_rs = subparsers.add_parser("restore-snap", help="Restores ONLY the Vault data directory")
    parser_rs.add_argument("file", help="The .tar.gz snapshot file to restore")
    
    parser_rf = subparsers.add_parser("restore-full", help="Restores Vault data AND configuration directory")
    parser_rf.add_argument("file", help="The .tar.gz full backup file to restore")
    
    args = parser.parse_args()
    
    check_root()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    if args.command == "backup-snap":
        backup_snap()
    elif args.command == "backup-full":
        backup_full()
    elif args.command == "restore-snap":
        restore_snap(args.file)
    elif args.command == "restore-full":
        restore_full(args.file)
