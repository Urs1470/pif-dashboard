import sqlite3, os
db_path = os.path.join(os.path.dirname(__file__), '..', 'pif_dashboard.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()
# Check if column already exists
cur.execute("PRAGMA table_info(timer_sessions)")
cols = [r[1] for r in cur.fetchall()]
if 'subtask_id' not in cols:
    cur.execute("ALTER TABLE timer_sessions ADD COLUMN subtask_id TEXT REFERENCES task_subtasks(id)")
    print("Added subtask_id column to timer_sessions")
else:
    print("subtask_id column already exists")
conn.commit()
conn.close()