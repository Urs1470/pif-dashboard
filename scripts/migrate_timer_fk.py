#!/usr/bin/env python3
"""Migration: Add ON DELETE CASCADE to timer_sessions.subtask_id FK."""
import sqlite3
import os
import sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pif_dashboard.db')
DB = os.path.normpath(DB)

if not os.path.exists(DB):
    print(f"❌ DB not found: {DB}")
    sys.exit(1)

print(f"📦 DB: {DB} ({os.path.getsize(DB)//1024} KB)")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check current schema
c.execute("SELECT sql FROM sqlite_master WHERE name='timer_sessions'")
old_sql = c.fetchone()[0]
print(f"📋 Current schema:\n{old_sql}\n")

# Check for orphaned subtask_ids
c.execute("SELECT COUNT(*) FROM timer_sessions WHERE subtask_id IS NOT NULL AND subtask_id NOT IN (SELECT id FROM task_subtasks)")
orphans = c.fetchone()[0]
print(f"🔍 Orphaned subtask_ids: {orphans}")

if orphans > 0:
    print("⚠️  Setting orphaned subtask_ids to NULL...")
    c.execute("UPDATE timer_sessions SET subtask_id = NULL WHERE subtask_id IS NOT NULL AND subtask_id NOT IN (SELECT id FROM task_subtasks)")
    conn.commit()
    print(f"✅ Set {c.rowcount} orphaned subtask_ids to NULL")

# Create new table with proper FK
print("🔄 Creating new timer_sessions table with ON DELETE CASCADE...")
c.executescript('''
    PRAGMA foreign_keys = OFF;
    
    CREATE TABLE timer_sessions_new (
        id TEXT PRIMARY KEY,
        proiect_id TEXT NOT NULL REFERENCES proiecte(id) ON DELETE CASCADE,
        start_time TEXT NOT NULL,
        stop_time TEXT,
        durata_secunde INTEGER,
        task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
        subtask_id TEXT REFERENCES task_subtasks(id) ON DELETE SET NULL
    );
    
    INSERT INTO timer_sessions_new SELECT * FROM timer_sessions;
    
    DROP TABLE timer_sessions;
    
    ALTER TABLE timer_sessions_new RENAME TO timer_sessions;
    
    PRAGMA foreign_keys = ON;
''')

conn.commit()
print("✅ Migration complete!")

# Verify
c.execute("SELECT sql FROM sqlite_master WHERE name='timer_sessions'")
new_sql = c.fetchone()[0]
print(f"\n📋 New schema:\n{new_sql}")

conn.close()
print("\n✅ Done!")
