"""Verify budget v2 deploy: new logic present, page loads."""
import requests, sys, re, time, os
sys.stdout.reconfigure(encoding='utf-8')

SERVER = os.environ.get("PIF_SERVER", "https://pif.iupif.org")
PIN = os.environ.get("PIF_DASHBOARD_PIN", "")
if not PIN:
    sys.exit("PIF_DASHBOARD_PIN env var is required")
s = requests.Session()
s.post(f"{SERVER}/login", json={"pin": PIN}, timeout=30)

r = s.get(f"{SERVER}/budget/", timeout=30)
m = re.search(r'budget-tracker\.js\?v=(\w+)', r.text)
print(f"index: {r.status_code}  asset version: {m.group(1) if m else 'N/A'}")

r = s.get(f"{SERVER}/budget/budget-tracker.js?v=20260521b", timeout=30)
js = r.text
checks = {
    'luniReprezentative defined':    'function luniReprezentative' in js,
    'migrateCleanDeadFields defined':'function migrateCleanDeadFields' in js,
    'getSoldCurent simplified':      'always derived from the amortisation' in js,
    'updateCreditSold removed':      'function updateCreditSold' not in js,
    'no credit.rata read':           'formatRON(cr.rata)' not in js,
    'Rata curenta label':            'Rata curenta (capital+dob.)' in js or 'Rată curentă' in js,
}
print(f"JS: {r.status_code}  ({len(js)} bytes)")
for k, v in checks.items():
    print(f"  [{'OK' if v else 'FAIL'}] {k}")

st = s.get(f"{SERVER}/budget/api/state", timeout=30).json()
print(f"\nstate: updated={st.get('updated')}")
all_ok = all(checks.values())
print(f"\n{'ALL CHECKS PASS' if all_ok else 'SOME CHECKS FAILED'}")
