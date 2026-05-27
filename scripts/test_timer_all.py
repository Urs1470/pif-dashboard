#!/usr/bin/env python3
"""Test complet al tuturor funcțiilor de cronometru — PIF Dashboard."""
import requests
import time
import json
import sys
import os

BASE = os.environ.get("PIF_SERVER", "http://localhost:5000")
PIN = os.environ.get("PIF_DASHBOARD_PIN", "")
if not PIN:
    sys.exit("PIF_DASHBOARD_PIN env var is required")
PASS = 0
FAIL = 0
ERRORS = []
TOTAL = 0

def test(name, ok, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if ok:
        print(f"  ✅ [PASS] {name}")
        PASS += 1
    else:
        print(f"  ❌ [FAIL] {name}" + (f" — {detail}" if detail else ""))
        FAIL += 1
        ERRORS.append(f"{name}: {detail}")

def login():
    s = requests.Session()
    r = s.post(f"{BASE}/login", json={"pin": PIN})
    assert r.status_code == 200, f"Login failed: {r.status_code}"
    return s

# ═══════════════════════════════════════
print("=" * 60)
print("TESTARE COMPLETĂ CRONOMETRU — PIF DASHBOARD")
print("=" * 60)

try:
    s = login()
    test("Autentificare", True)
except Exception as e:
    test("Autentificare", False, str(e))
    sys.exit(1)

# ─── Setup: get/create test data ───
print("\n─── PREGĂTIRE DATE TEST ───")

r = s.get(f"{BASE}/api/proiecte")
proiecte = r.json() if r.status_code == 200 else []
if isinstance(proiecte, dict):
    proiecte = proiecte.get("proiecte", proiecte.get("data", []))

if proiecte:
    pid = proiecte[0]["id"]
    test("Găsire proiect", True, f"ID={pid}")
else:
    r = s.post(f"{BASE}/api/proiecte", json={"nume": "TEST TIMER", "localitate": "Test", "strada": "Test", "data_pif": "2026-05-26", "data_raport": "2026-05-26"})
    if r.status_code in (200, 201):
        pid = r.json()["id"]
        test("Creare proiect", True, f"ID={pid}")
    else:
        test("Creare proiect", False, f"HTTP {r.status_code}")
        sys.exit(1)

r = s.get(f"{BASE}/api/proiecte/{pid}/tasks")
tasks = r.json() if r.status_code == 200 else []
if isinstance(tasks, dict): tasks = tasks.get("tasks", tasks.get("data", []))
tid = tasks[0]["id"] if tasks else None
if not tid:
    r = s.post(f"{BASE}/api/proiecte/{pid}/tasks", json={"titlu": "Task Timer Test"})
    if r.status_code in (200, 201):
        tid = r.json()["id"]
        test("Creare task", True, f"ID={tid}")
    else:
        test("Creare task", False, f"HTTP {r.status_code}")
else:
    test("Găsire task", True, f"ID={tid}")

sid = None
if tid:
    r = s.get(f"{BASE}/api/proiecte/{pid}/tasks/{tid}")
    if r.status_code == 200:
        subtasks = r.json().get("subtasks", [])
        if subtasks:
            sid = subtasks[0]["id"]
            test("Găsire subtask", True, f"ID={sid}")

if not sid and tid:
    r = s.post(f"{BASE}/api/tasks/{tid}/subtasks", json={"titlu": "Subtask Timer Test", "responsabil": "Test"})
    if r.status_code in (200, 201):
        sid = r.json()["id"]
        test("Creare subtask", True, f"ID={sid}")
    else:
        test("Creare subtask", False, f"HTTP {r.status_code}")

r = s.get(f"{BASE}/api/global-tasks")
global_tasks = r.json() if r.status_code == 200 else []
gtid = global_tasks[0]["id"] if global_tasks else None
if not gtid:
    r = s.post(f"{BASE}/api/global-tasks", json={"titlu": "Global Timer Test", "responsabil": "Test"})
    if r.status_code in (200, 201):
        gtid = r.json()["id"]
        test("Creare global task", True, f"ID={gtid}")
    else:
        test("Creare global task", False, f"HTTP {r.status_code}")
else:
    test("Găsire global task", True, f"ID={gtid}")

print(f"\nDate test: project={pid}, task={tid}, subtask={sid}, global={gtid}")

# ═══════════════════════════════════════
# TESTS
# API field names: id (not session_id), durata_secunde (not duration_seconds)
# ═══════════════════════════════════════

# ─── 1. PROIECT TIMER ───
print("\n─── 1. TIMER PROIECT ───")

r = s.post(f"{BASE}/api/proiecte/{pid}/timer/start")
test("Start", r.status_code in (200, 201), f"HTTP {r.status_code}")
sid1 = r.json().get("id") if r.status_code in (200, 201) else None
test("id primit", bool(sid1), f"id={sid1}")

r = s.get(f"{BASE}/api/proiecte/{pid}/timer")
test("Get sessions", r.status_code == 200, f"HTTP {r.status_code}")

time.sleep(2)
r = s.post(f"{BASE}/api/proiecte/{pid}/timer/stop")
test("Stop", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    d = r.json().get("durata_secunde", 0)
    test(f"Durata {d}s >= 2s", d >= 2, f"={d}s")

# Stop with note
r = s.post(f"{BASE}/api/proiecte/{pid}/timer/start")
if r.status_code in (200, 201):
    time.sleep(1)
    r = s.post(f"{BASE}/api/proiecte/{pid}/timer/stop-with-note", json={"note": "test notă"})
    test("Stop cu notă", r.status_code == 200, f"HTTP {r.status_code}")

# ─── 2. TASK TIMER ───
print("\n─── 2. TIMER TASK ───")

if tid:
    r = s.post(f"{BASE}/api/tasks/{tid}/timer/start")
    test("Start task", r.status_code in (200, 201), f"HTTP {r.status_code}")
    if r.status_code in (200, 201):
        stid = r.json().get("id")
        test("id task", bool(stid))

        time.sleep(1)
        r = s.post(f"{BASE}/api/tasks/{tid}/timer/stop")
        test("Stop task", r.status_code == 200, f"HTTP {r.status_code}")
        if r.status_code == 200:
            d = r.json().get("durata_secunde", 0)
            test(f"Durata task {d}s >= 1s", d >= 1, f"={d}s")

    r = s.get(f"{BASE}/api/tasks/{tid}/timer")
    test("Get task timer", r.status_code == 200, f"HTTP {r.status_code}")

    r = s.post(f"{BASE}/api/tasks/999999/timer/start")
    test("Task 404", r.status_code == 404, f"HTTP {r.status_code}")

# ─── 3. SUBTASK TIMER ───
print("\n─── 3. TIMER SUBTASK ───")

if sid:
    r = s.get(f"{BASE}/api/subtasks/{sid}/timer")
    test("Get subtask", r.status_code == 200, f"HTTP {r.status_code}")

    r = s.post(f"{BASE}/api/subtasks/{sid}/timer/start")
    test("Start subtask", r.status_code in (200, 201), f"HTTP {r.status_code}")
    if r.status_code in (200, 201):
        sid2 = r.json().get("id")
        test("id subtask", bool(sid2))

        time.sleep(1)
        r = s.post(f"{BASE}/api/subtasks/{sid}/timer/stop")
        test("Stop subtask", r.status_code == 200, f"HTTP {r.status_code}")
        if r.status_code == 200:
            d = r.json().get("durata_secunde", 0)
            test(f"Durata subtask {d}s >= 1s", d >= 1, f"={d}s")

# ─── 4. MANUAL TIME (API expects 'durata_secunde' field) ───
print("\n─── 4. TIMP MANUAL ───")

if sid:
    r = s.post(f"{BASE}/api/subtasks/{sid}/timer/manual", json={"durata_secunde": 300})
    test("Manual subtask 300s", r.status_code in (200, 201), f"HTTP {r.status_code}")

if tid:
    r = s.post(f"{BASE}/api/tasks/{tid}/timer/manual", json={"durata_secunde": 600})
    test("Manual task 600s", r.status_code in (200, 201), f"HTTP {r.status_code}")

# ─── 5. GLOBAL TASK TIMER ───
print("\n─── 5. TIMER GLOBAL TASK ───")

if gtid:
    r = s.post(f"{BASE}/api/global-tasks/{gtid}/timer/start")
    test("Start global", r.status_code in (200, 201), f"HTTP {r.status_code}")
    if r.status_code in (200, 201):
        time.sleep(1)
        r = s.post(f"{BASE}/api/global-tasks/{gtid}/timer/stop")
        test("Stop global", r.status_code == 200, f"HTTP {r.status_code}")
        if r.status_code == 200:
            d = r.json().get("durata_secunde", 0)
            test(f"Durata global {d}s >= 1s", d >= 1, f"={d}s")

    r = s.get(f"{BASE}/api/global-tasks/{gtid}/timer")
    test("Get global", r.status_code == 200, f"HTTP {r.status_code}")

    r = s.post(f"{BASE}/api/global-tasks/999999/timer/start")
    test("Global 404", r.status_code == 404, f"HTTP {r.status_code}")

# ─── 6. ROLLUP (subtask → task) ───
print("\n─── 6. ROLLUP ───")

if sid and tid:
    r = s.post(f"{BASE}/api/subtasks/{sid}/timer/manual", json={"durata_secunde": 300})
    test("Adaug 300s subtask", r.status_code in (200, 201), f"HTTP {r.status_code}")

    r = s.get(f"{BASE}/api/tasks/{tid}/timer")
    test("Get task timer (after rollup)", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        total = d.get("total_secunde", 0)
        test(f"Task total_secunde={total} > 0", total > 0, f"={total}")

# ─── 7. EDGE CASES ───
print("\n─── 7. EDGE CASES ───")

r = s.post(f"{BASE}/api/proiecte/{pid}/timer/stop")
test("Double stop (no active)", r.status_code in (200, 404), f"HTTP {r.status_code}")

r = s.delete(f"{BASE}/api/timer/nonexistent-session-id")
test("Delete inexistent → 404", r.status_code == 404, f"HTTP {r.status_code}")

r = s.get(f"{BASE}/api/healthz")
test("Healthcheck", r.status_code == 200, f"HTTP {r.status_code}")

# ═══════════════════════════════════════
print("\n" + "=" * 60)
print(f"REZULTAT FINAL: {PASS}/{TOTAL} PASS, {FAIL} FAIL")
if ERRORS:
    print("\nErori:")
    for e in ERRORS:
        print(f"  • {e}")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
