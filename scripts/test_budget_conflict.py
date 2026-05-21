"""Test the 409 concurrency check WITHOUT mutating real data.
A POST with a stale base_updated is rejected BEFORE any DB write."""
import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

SERVER = "https://pif.iupif.org"
s = requests.Session()
s.post(f"{SERVER}/login", json={"pin": "pif2024"}, timeout=30)

# Current state + version token
st = s.get(f"{SERVER}/budget/api/state", timeout=30).json()
token_before = st['updated']
print(f"Current updated token: {token_before}")

# POST with a deliberately STALE base_updated -> must be rejected with 409,
# and must NOT change anything (rejection happens before any write).
r = s.post(f"{SERVER}/budget/api/state", json={
    'data': st['data'],
    'base_updated': 'STALE-WRONG-TOKEN-9999',
}, timeout=30)
print(f"POST with stale token -> {r.status_code} (expect 409)")
body = r.json()
print(f"  error: {body.get('error')}")
print(f"  conflict payload has current.updated: {bool(body.get('current', {}).get('updated'))}")

# Confirm nothing changed
token_after = s.get(f"{SERVER}/budget/api/state", timeout=30).json()['updated']
print(f"Token after rejected POST: {token_after}")
print(f"  unchanged: {token_before == token_after}")

ok = r.status_code == 409 and body.get('error') == 'conflict' and token_before == token_after
print(f"\n409 CONFLICT CHECK: {'PASS' if ok else 'FAIL'}")
