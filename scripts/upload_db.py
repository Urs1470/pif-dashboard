"""Upload local pif_dashboard.db to server via /api/admin/db-upload.

IMPORTANT: the shared SQLite file holds BOTH the VFD parameter database and
the live budget app data (budget_state / budget_audit). The budget side is
edited live on the server. To avoid reverting the user's budget when uploading
parameter changes, this script FIRST pulls the server's current budget tables
into the local DB, then uploads. The upload therefore carries the latest
budget data, never a stale local copy.

Usage:  python scripts/upload_db.py
"""
import requests, sys, pathlib, time, sqlite3, tempfile, os

SERVER = os.environ.get("PIF_SERVER", "https://pif.iupif.org")
PIN = os.environ.get("PIF_DASHBOARD_PIN", "")
if not PIN:
    sys.exit("PIF_DASHBOARD_PIN env var is required")
DB_PATH = pathlib.Path("pif_dashboard.db")
BUDGET_TABLES = ("budget_state", "budget_audit")


def login():
    s = requests.Session()
    r = s.post(f"{SERVER}/login", json={"pin": PIN}, timeout=30)
    if not r.json().get("success"):
        sys.exit(f"LOGIN FAILED: {r.text}")
    return s


def preserve_budget_tables(session):
    """Copy the server's live budget tables into the local DB before upload."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        r = session.get(f"{SERVER}/api/admin/db-dump", timeout=300)
        with open(tmp.name, "wb") as f:
            f.write(r.content)
        with open(tmp.name, "rb") as f:
            if f.read(15) != b"SQLite format 3":
                sys.exit("ERROR: server DB dump is not valid SQLite — aborting upload")
        local = sqlite3.connect(DB_PATH)
        local.execute("ATTACH ? AS srv", (tmp.name,))
        for tbl in BUDGET_TABLES:
            local.execute(f"DELETE FROM {tbl}")
            local.execute(f"INSERT INTO {tbl} SELECT * FROM srv.{tbl}")
            n = local.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"    {tbl}: {n} rows pulled from server")
        local.commit()
        local.execute("DETACH srv")
        local.close()
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


def main():
    if not DB_PATH.exists():
        sys.exit(f"DB not found: {DB_PATH}")

    print(f"1/4 Logging in to {SERVER}...")
    session = login()
    print("    OK")

    print("2/4 Preserving live budget tables (pull from server)...")
    preserve_budget_tables(session)

    print(f"3/4 Uploading {DB_PATH} ({DB_PATH.stat().st_size // 1024} KB)...")
    t0 = time.time()
    with open(DB_PATH, "rb") as f:
        r = session.post(
            f"{SERVER}/api/admin/db-upload",
            files={"db": ("pif_dashboard.db", f, "application/octet-stream")},
            timeout=300,
        )
    print(f"    Response ({time.time() - t0:.1f}s): {r.status_code} {r.text[:200]}")

    if r.status_code == 200:
        print("4/4 Upload successful (budget data preserved).")
    else:
        sys.exit("4/4 Upload FAILED")


if __name__ == "__main__":
    main()
