"""Upload local pif_dashboard.db to server via /api/admin/db-upload."""
import requests, sys, pathlib, time

SERVER = "https://pif.iupif.org"
PIN = "pif2024"
DB_PATH = pathlib.Path("pif_dashboard.db")

if not DB_PATH.exists():
    print("DB not found:", DB_PATH)
    sys.exit(1)

print(f"1/3 Logging in to {SERVER}...")
session = requests.Session()
r = session.post(f"{SERVER}/login", json={"pin": PIN}, timeout=30)
if not r.json().get("success"):
    print("LOGIN FAILED:", r.text)
    sys.exit(1)
print("    OK")

print(f"2/3 Uploading {DB_PATH} ({DB_PATH.stat().st_size // 1024} KB)...")
t0 = time.time()
with open(DB_PATH, "rb") as f:
    r = session.post(
        f"{SERVER}/api/admin/db-upload",
        files={"db": ("pif_dashboard.db", f, "application/octet-stream")},
        timeout=300,
    )
elapsed = time.time() - t0
print(f"    Response ({elapsed:.1f}s): {r.status_code} {r.text[:200]}")

if r.status_code == 200:
    print("3/3 Upload successful!")
else:
    print("3/3 Upload FAILED")
    sys.exit(1)
