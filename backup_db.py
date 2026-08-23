#!/usr/bin/env python3
"""
Database Backup Script for PIF Dashboard
Creates timestamped backups, keeps last 30, logs to backup.log
"""
import os
import shutil
import sqlite3
from datetime import datetime

# Paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, 'pif_dashboard.db')
BACKUP_DIR = os.path.join(PROJECT_DIR, 'backups')
LOG_FILE = os.path.join(BACKUP_DIR, 'backup.log')

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)


def log(message):
    """Log message to backup.log"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)
    print(log_entry.strip())


def get_db_path():
    """Get the database path - handles WAL mode"""
    return DB_PATH


def create_backup():
    """Create a timestamped backup of the database"""
    if not os.path.exists(DB_PATH):
        log(f"ERROR: Database not found at {DB_PATH}")
        return False
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_name = f"pif_dashboard_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    try:
        # Close any existing connections by vacuuming the database first
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA wal_checkpoint(FULL)')
        conn.close()
        
        # Copy the database file
        shutil.copy2(DB_PATH, backup_path)
        
        # Also copy WAL and SHM files if they exist
        wal_path = DB_PATH + '-wal'
        shm_path = DB_PATH + '-shm'
        if os.path.exists(wal_path):
            shutil.copy2(wal_path, backup_path + '-wal')
        if os.path.exists(shm_path):
            shutil.copy2(shm_path, backup_path + '-shm')
        
        log(f"SUCCESS: Created backup {backup_name}")
        return True
        
    except Exception as e:
        log(f"ERROR: Failed to create backup: {str(e)}")
        return False


def cleanup_old_backups(max_backups=30):
    """Remove backups older than the most recent 30"""
    try:
        # Get list of all backup files
        backup_files = []
        for f in os.listdir(BACKUP_DIR):
            if f.startswith('pif_dashboard_') and f.endswith('.db'):
                filepath = os.path.join(BACKUP_DIR, f)
                backup_files.append((filepath, os.path.getmtime(filepath)))
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        # Keep only the most recent max_backups
        to_delete = backup_files[max_backups:]
        
        deleted_count = 0
        for filepath, _ in to_delete:
            try:
                os.remove(filepath)
                # Also remove associated WAL and SHM files
                if os.path.exists(filepath + '-wal'):
                    os.remove(filepath + '-wal')
                if os.path.exists(filepath + '-shm'):
                    os.remove(filepath + '-shm')
                log(f"Deleted old backup: {os.path.basename(filepath)}")
                deleted_count += 1
            except Exception as e:
                log(f"ERROR: Failed to delete {filepath}: {str(e)}")
        
        if deleted_count > 0:
            log(f"Cleanup complete: removed {deleted_count} old backups")
        
        return deleted_count
        
    except Exception as e:
        log(f"ERROR: Failed to cleanup old backups: {str(e)}")
        return 0


def list_backups():
    """List all available backups"""
    try:
        backups = []
        for f in os.listdir(BACKUP_DIR):
            if f.startswith('pif_dashboard_') and f.endswith('.db'):
                filepath = os.path.join(BACKUP_DIR, f)
                stat = os.stat(filepath)
                backups.append({
                    'name': f,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        backups.sort(key=lambda x: x['modified'], reverse=True)
        return backups
        
    except Exception as e:
        log(f"ERROR: Failed to list backups: {str(e)}")
        return []


def main():
    """Main backup function"""
    log("=" * 50)
    log("Starting database backup")
    
    # Create new backup
    success = create_backup()
    
    if success:
        # Cleanup old backups
        cleanup_old_backups(30)
        
        # List current backups
        backups = list_backups()
        log(f"Total backups available: {len(backups)}")
    else:
        log("Backup failed - skipping cleanup")
    
    log("Backup process complete")
    log("=" * 50)


if __name__ == '__main__':
    main()
