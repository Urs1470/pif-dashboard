"""Upload local pif_dashboard.db to server via /api/admin/db-upload.

Usage:  python scripts/upload_db.py
"""
import requests, sys, pathlib, time, os

SERVER = os.environ.get("PIF_SERVER", "https://pif.iupif.org")
PIN = os.environ.get("PIF_DASHBOARD_PIN", "")
if not PIN:
    sys.exit("PIF_DASHBOARD_PIN env var is required")
DB_PATH = pathlib.Path("pif_dashboard.db")


def login():
    s = requests.Session()
    r = s.post(f"{SERVER}/login", json={"pin": PIN}, timeout=30)
    if not r.json().get("success"):
        sys.exit(f"LOGIN FAILED: {r.text}")
    return s


def main():
    if not DB_PATH.exists():
        sys.exit(f"DB not found: {DB_PATH}")

    print(f"1/2 Logging in to {SERVER}...")
    session = login()
    print("    OK")

    print(f"2/2 Uploading {DB_PATH} ({DB_PATH.stat().st_size // 1024} KB)...")
    t0 = time.time()
    with open(DB_PATH, "rb") as f:
        r = session.post(
            f"{SERVER}/api/admin/db-upload",
            files={"db": ("pif_dashboard.db", f, "application/octet-stream")},
            timeout=300,
        )
    print(f"    Response ({time.time() - t0:.1f}s): {r.status_code} {r.text[:200]}")

    if r.status_code == 200:
        print("Upload successful.")
    else:
        sys.exit("Upload FAILED")


if __name__ == "__main__":
    main()
