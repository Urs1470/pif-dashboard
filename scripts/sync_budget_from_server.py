"""Pull the server's budget_state + budget_audit into the local pif_dashboard.db.

The shared SQLite file holds BOTH the VFD parameter database and the budget
app data. The budget side changes live on the server (the user edits it from
phone/PC). This script refreshes the local copy's budget tables so a
parameter-only DB upload never reverts the user's budget data.

Usage:  python scripts/sync_budget_from_server.py
"""
import requests, sqlite3, tempfile, os, sys

sys.stdout.reconfigure(encoding='utf-8')

SERVER = os.environ.get("PIF_SERVER", "https://pif.iupif.org")
PIN = os.environ.get("PIF_DASHBOARD_PIN", "")
if not PIN:
    sys.exit("PIF_DASHBOARD_PIN env var is required")
LOCAL_DB = "pif_dashboard.db"
BUDGET_TABLES = ("budget_state", "budget_audit")


def pull_budget_tables():
    s = requests.Session()
    r = s.post(f"{SERVER}/login", json={"pin": PIN}, timeout=30)
    if not r.json().get("success"):
        sys.exit("Login failed")

    # Download the live server DB (hot backup)
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    r = s.get(f"{SERVER}/api/admin/db-dump", timeout=300)
    with open(tmp.name, "wb") as f:
        f.write(r.content)
    with open(tmp.name, "rb") as f:
        if f.read(15) != b"SQLite format 3":
            os.unlink(tmp.name)
            sys.exit("ERROR: downloaded file is not a SQLite database")

    local = sqlite3.connect(LOCAL_DB)
    local.execute("ATTACH ? AS srv", (tmp.name,))
    for tbl in BUDGET_TABLES:
        before = local.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        srv_updated = None
        if tbl == "budget_state":
            row = local.execute("SELECT updated FROM srv.budget_state WHERE user='ion'").fetchone()
            srv_updated = row[0] if row else None
        local.execute(f"DELETE FROM {tbl}")
        local.execute(f"INSERT INTO {tbl} SELECT * FROM srv.{tbl}")
        after = local.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        extra = f"  (server updated={srv_updated})" if srv_updated else ""
        print(f"  {tbl}: {before} -> {after} rows from server{extra}")
    local.commit()
    local.execute("DETACH srv")
    local.close()
    os.unlink(tmp.name)
    print("Local budget tables synced from server.")


if __name__ == "__main__":
    pull_budget_tables()
