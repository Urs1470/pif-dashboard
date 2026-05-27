"""Verify budget app after deploy: login, check endpoints respond correctly."""
import requests, sys, time, os
sys.stdout.reconfigure(encoding='utf-8')

SERVER = os.environ.get("PIF_SERVER", "https://pif.iupif.org")
PIN = os.environ.get("PIF_DASHBOARD_PIN", "")
if not PIN:
    sys.exit("PIF_DASHBOARD_PIN env var is required")

s = requests.Session()
r = s.post(f"{SERVER}/login", json={"pin": PIN}, timeout=30)
print(f"login: {r.status_code} {r.json()}")

# Budget index
r = s.get(f"{SERVER}/budget/", timeout=30)
ok_index = r.status_code == 200 and 'budget-tracker.js' in r.text
print(f"GET /budget/  -> {r.status_code}  index ok: {ok_index}")
# Check cache version bumped
import re
m = re.search(r'budget-tracker\.js\?v=(\w+)', r.text)
print(f"  asset version: {m.group(1) if m else 'NOT FOUND'}")

# Budget state API
r = s.get(f"{SERVER}/budget/api/state", timeout=30)
js = r.json()
print(f"GET /budget/api/state  -> {r.status_code}  keys: {list(js.keys())}  updated: {js.get('updated')}")

# JS file loads
r = s.get(f"{SERVER}/budget/budget-tracker.js?v=20260521a", timeout=30)
print(f"GET budget-tracker.js  -> {r.status_code}  size: {len(r.text)} bytes")
print(f"  has handleSaveConflict: {'handleSaveConflict' in r.text}")
print(f"  has persistLocalBackup: {'persistLocalBackup' in r.text}")
print(f"  dead code gone (addEtf): {'function addEtf' not in r.text}")

# get_audit with bad limit (should not 500)
r = s.get(f"{SERVER}/budget/api/audit?limit=abc", timeout=30)
print(f"GET /budget/api/audit?limit=abc  -> {r.status_code} (expect 200, not 500)")

# Quote endpoint
r = s.get(f"{SERVER}/budget/api/quote/VWCE.DE?range=5d", timeout=30)
print(f"GET /budget/api/quote/VWCE.DE  -> {r.status_code}")

print("\nVERIFICATION DONE")
