import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect('pif_dashboard.db')
cur = c.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'budget%'")
print("budget tables local:", [r[0] for r in cur.fetchall()])
try:
    cur.execute("SELECT user, updated, length(data) FROM budget_state")
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print("  local budget_state:", r)
    else:
        print("  local budget_state: EMPTY")
except Exception as e:
    print("  local budget_state error:", e)
c.close()
