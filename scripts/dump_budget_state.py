"""Dump the live budget state structure + values for analysis."""
import requests, sys, json, os
sys.stdout.reconfigure(encoding='utf-8')

SERVER = os.environ.get("PIF_SERVER", "https://pif.iupif.org")
PIN = os.environ.get("PIF_DASHBOARD_PIN", "")
if not PIN:
    sys.exit("PIF_DASHBOARD_PIN env var is required")
s = requests.Session()
s.post(f"{SERVER}/login", json={"pin": PIN}, timeout=30)
st = s.get(f"{SERVER}/budget/api/state", timeout=30).json()
data = st['data'] or {}

print("=" * 70)
print("BUDGET STATE — top-level keys:")
for k in sorted(data.keys()):
    v = data[k]
    if isinstance(v, dict):
        info = f"dict ({len(v)} keys)"
    elif isinstance(v, list):
        info = f"list ({len(v)} items)"
    else:
        info = repr(v)
    print(f"  {k:<22} {info}")

def show(title, obj, depth=0):
    print(f"\n--- {title} ---")
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str)[:4000])

show("profil", data.get('profil'))
show("credit (fara scadentar)", {k: v for k, v in (data.get('credit') or {}).items() if k != 'scadentar'})
sc = (data.get('credit') or {}).get('scadentar') or []
print(f"\n--- credit.scadentar: {len(sc)} rate ---")
for row in sc[:3]:
    print(f"  {row}")
print("  ...")
for row in sc[-2:]:
    print(f"  {row}")

show("categoriiVar", data.get('categoriiVar'))
show("categoriiVenit", data.get('categoriiVenit'))

ven = data.get('venituri') or {}
print(f"\n--- venituri: {len(ven)} luni ---")
for mk in sorted(ven.keys())[:3]:
    print(f"  {mk}: {ven[mk]}")

chl = data.get('cheltuieli') or {}
print(f"\n--- cheltuieli: {len(chl)} luni ---")
for mk in sorted(chl.keys())[:3]:
    print(f"  {mk}: {chl[mk]}")

show("vwce (fara serii)", {k: v for k, v in (data.get('vwce') or {}).items()
                            if k not in ('tranzactii', 'alimentari', 'priceHistory')})
print(f"  vwce.tranzactii: {len((data.get('vwce') or {}).get('tranzactii') or [])}")
print(f"  vwce.alimentari: {len((data.get('vwce') or {}).get('alimentari') or [])}")

show("goals", data.get('goals'))
show("tezaur", data.get('tezaur'))
show("fondUrgenta", data.get('fondUrgenta'))
show("evolutie", data.get('evolutie'))
print(f"\nemisiuniTezaur: {data.get('emisiuniTezaur')}")
print(f"reguliCategorizare: {len(data.get('reguliCategorizare') or [])} reguli")
