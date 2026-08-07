#!/usr/bin/env python3
"""Comprehensive test suite for pif-dashboard - static analysis + API smoke tests."""

import json, os, re, sqlite3, sys, requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "pif_dashboard.db"
BASE_URL = "http://localhost:5000"

results = {"pass": [], "fail": [], "warn": []}

def log(pt, msg):
    prefix = {"pass": "[PASS]", "fail": "[FAIL]", "warn": "[WARN]"}[pt]
    print(f"  {prefix} {msg}")
    results[pt].append(msg)

def static_analysis():
    print("\n=== STATIC ANALYSIS ===\n")
    js_function_check()
    api_route_check()
    db_table_check()

def js_function_check():
    print("--- JS Function Check ---")
    js_files = ["static/app.js", "static/core.js", "static/mobile.js"]
    onclick_pattern = re.compile(r'onclick\s*=\s*"([^"]+)"')
    issues = []
    
    for jsf in js_files:
        p = PROJECT_ROOT / jsf
        if not p.exists(): continue
        content = p.read_text(encoding='utf-8')
        for m in onclick_pattern.finditer(content):
            handler = m.group(1).strip()
            if '(' in handler and not handler.startswith('${'):
                fn = handler.split('(')[0].strip().split('.')[-1]
                if fn and fn not in KNOWN_GLOBAL_FUNCTIONS:
                    issues.append(f"onclick handler '{fn}()' may not be globally defined")
    
    if issues:
        for i in issues[:10]: log("warn", i)
        if len(issues) > 10: log("warn", f"... and {len(issues)-10} more onclick handlers")
    else:
        log("pass", "All onclick handlers are defined")

KNOWN_GLOBAL_FUNCTIONS = {
    'String', 'Number', 'Boolean', 'Array', 'Object', 'JSON', 'Math', 'Date',
    'encodeURIComponent', 'decodeURIComponent', 'parseInt', 'parseFloat', 'isNaN',
    'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval', 'console.log',
    'formatDuration', 'if', 'else', 'return', 'showProjectDetail', 'toggleProjectSelection',
    'toggleTodoDoneCollapse', 'changeProjectStatus', 'deleteSubtask', 'deleteJurnalEntry',
    'downloadAllAttachments', 'openPreview', 'toggleTodo', 'addTodo', 'deleteTodo',
    'editCurrentProject', 'deleteCurrentProject', 'saveServiceField', 'addSubtask',
    'toggleSubtask', 'editGtTask', 'deleteGtTask', 'addSubtaskInline', 'addSubtaskInlineGt',
    'toggleGtTimerInline', 'toggleInlineSubtaskAdd', 'toggleInlineSubtaskAddGt',
    'toggleTaskTimerInline', 'cycleGtStatus', 'cycleGtPriority', 'cycleTodoStatus',
    'cycleTodoPriority', 'confirmAction', 'openTaskEditModal', 'closeTaskEditModal',
    'saveTaskFromModal', 'deleteTaskFromModal', 'selectTaskPriority', 'filterClientList',
    'editClientFromList', 'deleteClientFromList', 'openLongTextEditor', 'closeLongTextEditor',
    'saveLongText', 'copyLongTextContent', 'openFaultModal', 'closeFaultModal',
    'editParamValue', 'deleteParam', 'editEchipament', 'deleteEchipament',
    'faultSelectFamilie', 'faultSelectProducator', 'faultChangePage', 'batchDeleteProjects',
    'batchUpdateStatus', 'clearLocalCache', 'exportExcel', 'exportMarkdown',
    'exportCurrentProjectPDF', 'exportClientPDF', 'exportBackup', 'closeConfirmModal',
    'closeGlobalSearch', 'closeAddClientModal', 'closeClientListModal', 'closeManualsModal',
    'closeManualTimeModal', 'closeImportParamsModal', 'closeParamModal', 'closePreview',
    'closeObsidianSearch', 'doObsidianSearch', 'doGlobalSearch', 'forceSWUpdate',
    'confirmCallback', 'confirmParamValue', 'applyImportedParams', 'stopPropagation',
    'downloadAttachment', 'deleteAttachment', 'toggleGtDoneCollapse', 'restoreTask',
    'switchTab', 'addChecklistCategory', 'deleteChecklistItem', 'getElementById',
    'toggleEchipamentCard', 'selectParam', 'selectClient', 'addNewClientFromAutocomplete',
    'deleteTimerSession', 'toggleChecklistCategoryCollapse', 'addChecklistItem',
    'hideEchipamentForm', 'saveEchipament', 'triggerImportParams', 'toggleAllImportParams',
    'paramSelectProducator', 'paramSelectFamilie', 'openParamModal', '_tcardToggleExpand',
    'switchProjectFilter', 'mobileParamSelectProducator', 'mobileParamSelectFamilie',
    'openMobileParamModal', 'mobileFaultSelectProducator', 'mobileFaultSelectFamilie',
    'openMobileFaultDetail', 'stopTimerFromHome', 'stopMobileTimer', 'startMobileTimer',
    'openMobileManualTime', 'deleteMobileTimerSession', 'deleteMobileChecklistItem',
    'addMobileChecklistItem', 'toggleMobileChecklistCat'
}

def api_route_check():
    print("\n--- API Route Check ---")
    routes_defined = set()
    routes_called = set()
    
    rdef = re.compile(r"@([a-zA-Z_][a-zA-Z0-9_]*)\.route\(['\"]([^'\"]+)['\"]")
    rcall = re.compile(r"fetch\(['\"]([^'\"]+)['\"]")
    
    blueprint_prefixes = {}
    for pyp in [PROJECT_ROOT / "app.py"] + list((PROJECT_ROOT / "blueprints").glob("*.py")):
        if not pyp.exists(): continue
        # encoding EXPLICIT: pe Windows read_text() cade pe cp1252, iar sursele
        # noastre au diacritice si ghilimele romanesti in comentarii. Testul
        # crapa cu UnicodeDecodeError inainte sa verifice ceva.
        txt = pyp.read_text(encoding='utf-8')
        
        bp_prefix_match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Blueprint\([^)]*url_prefix\s*=\s*['\"]([^'\"]+)['\"]", txt)
        if bp_prefix_match:
            bp_name = bp_prefix_match.group(1)
            bp_prefix = bp_prefix_match.group(2)
            blueprint_prefixes[bp_name] = bp_prefix
        
        for m in rdef.finditer(txt):
            bp_name = m.group(1)
            route = m.group(2)
            if bp_name in blueprint_prefixes:
                full_route = blueprint_prefixes[bp_name] + route
            elif bp_name == 'app':
                full_route = route
            else:
                full_route = route
            routes_defined.add(full_route)
    
    for jsf in ["static/app.js", "static/core.js", "static/mobile.js"]:
        p = PROJECT_ROOT / jsf
        if not p.exists(): continue
        for m in rcall.finditer(p.read_text(encoding='utf-8')):
            route = m.group(1).split('?')[0]
            if route.startswith('/'):
                # apiGet('/proiecte') uses API_BASE='/api' prefix — normalize
                if not route.startswith('/api'):
                    route = '/api' + route
                routes_called.add(route)
    
    missing = routes_called - routes_defined
    if missing:
        for r in sorted(missing): log("fail", f"Route {r} called but not defined")
    else:
        log("pass", "All API routes are defined")

def db_table_check():
    print("\n--- DB Table Check ---")
    if not DB_PATH.exists():
        log("fail", "Database not found"); return
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        actual = {r[0] for r in cur.fetchall()}
        conn.close()
    except Exception as e:
        log("fail", f"Cannot access DB: {e}"); return
    
    # VALID_TABLES traieste in utils.py (a fost mutat din app.py la extragerea
    # blueprint-urilor) — citim de acolo, altfel testul da mereu warn.
    with open(PROJECT_ROOT / "utils.py", 'r', encoding='utf-8') as f:
        content = f.read()

    valid_match = re.search(r"VALID_TABLES\s*=\s*\{([^}]+)\}", content)
    if valid_match:
        valid_tables = set(re.findall(r"'([a-zA-Z_][a-zA-Z0-9_]*)'", valid_match.group(1)))
        missing_valid = valid_tables - actual
        if missing_valid:
            for t in sorted(missing_valid):
                log("fail", f"Table '{t}' in VALID_TABLES but missing from DB")
        else:
            log("pass", "All VALID_TABLES exist in DB")
    else:
        log("warn", "Could not find VALID_TABLES definition")

def api_smoke_test():
    print("\n=== API SMOKE TEST ===\n")
    
    try:
        r = requests.get(f"{BASE_URL}/api/healthz", timeout=5)
        if r.status_code != 200: log("fail", "Server health check failed"); return
        log("pass", "GET /api/healthz -> 200 (JSON ok)")
    except requests.exceptions.ConnectionError:
        log("fail", "Server not running on port 5000"); return
    except Exception as e:
        log("fail", f"Server error: {e}"); return
    
    pin = os.environ.get('PIF_DASHBOARD_PIN', '')
    if not pin:
        log("fail", "PIF_DASHBOARD_PIN env var is required"); return
    try:
        r = requests.post(f"{BASE_URL}/login", json={"pin": pin}, timeout=5)
        if r.status_code == 401: log("fail", "Login failed - invalid PIN"); return
        if r.status_code != 200: log("fail", f"Login returned {r.status_code}"); return
        log("pass", "Login successful")
    except Exception as e:
        log("fail", f"Login request failed: {e}"); return
    
    cookie_value = r.cookies.get('session')
    if not cookie_value:
        log("fail", "No session cookie received"); return
    
    headers = {"Cookie": f"session={cookie_value}"}
    
    endpoints = [
        ("/api/proiecte", 200),
        ("/api/global-tasks", 200),
        ("/api/clienti", 200),
        ("/api/stats", 200),
    ]
    
    for ep, exp in endpoints:
        try:
            r = requests.get(f"{BASE_URL}{ep}", headers=headers, timeout=5)
            if r.status_code == exp:
                try:
                    j = r.json()
                    log("pass", f"GET {ep} -> {r.status_code}, {len(j) if isinstance(j, list) else 'ok'}")
                except (ValueError, KeyError):
                    log("pass", f"GET {ep} -> {r.status_code}")
            else:
                log("fail", f"GET {ep} -> {r.status_code} (expected {exp})")
        except Exception as e:
            log("fail", f"GET {ep} -> ERROR: {e}")

def sfera_leak_test():
    """Sferele (munca/personal, v38) — modul de esec e SCURGEREA: o interogare
    pe global_tasks fara filtru varsa personalul intr-o suprafata de munca.
    Fiecare asertie de aici corespunde unei suprafete."""
    print("\n=== SFERA (munca/personal) ===\n")
    pin = os.environ.get('PIF_DASHBOARD_PIN', '')
    if not pin:
        log("fail", "PIF_DASHBOARD_PIN required for sfera test"); return
    s = requests.Session()
    try:
        r = s.post(f"{BASE_URL}/login", json={"pin": pin}, timeout=5)
        if r.status_code != 200:
            log("fail", f"sfera: login -> {r.status_code}"); return
    except Exception as e:
        log("fail", f"sfera: login failed: {e}"); return

    def hdr():
        # Double-submit CSRF: cookie-ul se citeste si se intoarce in header.
        return {"X-CSRF-Token": s.cookies.get('csrf_token', '')}

    from datetime import date
    today = date.today().isoformat()
    created = []
    try:
        # 1) Creare personal + vizibilitate pe lista
        r = s.post(f"{BASE_URL}/api/global-tasks", headers=hdr(), timeout=5,
                   json={"titlu": "__proba_sfera_azi__", "sfera": "personal",
                         "status": "to_do", "data_scadenta": today})
        if r.status_code != 201:
            log("fail", f"sfera: POST personal -> {r.status_code}"); return
        pid = r.json()['id']; created.append(pid)

        r = s.post(f"{BASE_URL}/api/global-tasks", headers=hdr(), timeout=5,
                   json={"titlu": "__proba_sfera_fara_termen__", "sfera": "personal",
                         "status": "to_do"})
        pid2 = r.json()['id']; created.append(pid2)

        ids_default = {t['id'] for t in s.get(f"{BASE_URL}/api/global-tasks", timeout=5).json()}
        ids_pers = {t['id'] for t in s.get(f"{BASE_URL}/api/global-tasks?sfera=personal", timeout=5).json()}
        if pid in ids_default or pid2 in ids_default:
            log("fail", "sfera: personal LEAKS into default /api/global-tasks")
        else:
            log("pass", "GET /api/global-tasks (default) excludes personal")
        if pid in ids_pers and pid2 in ids_pers:
            log("pass", "GET /api/global-tasks?sfera=personal returns personal")
        else:
            log("fail", "sfera: personal tasks missing from ?sfera=personal")

        # 2) Valoare necunoscuta -> 400 (fail-closed, nu coercitie)
        r = s.get(f"{BASE_URL}/api/global-tasks?sfera=xyz", timeout=5)
        log("pass" if r.status_code == 400 else "fail", f"GET ?sfera=xyz -> {r.status_code} (expected 400)")

        # 3) Boardul Astazi: personal in `personale`, nu in `items`
        ag = s.get(f"{BASE_URL}/api/agenda/today?today={today}", timeout=5).json()
        in_items = any(x['id'] == pid for x in ag.get('items', []))
        in_pers = any(x['id'] == pid for x in ag.get('personale', []))
        if in_items:
            log("fail", "sfera: personal LEAKS into agenda items (work board)")
        elif in_pers:
            log("pass", "agenda/today: personal in `personale`, not in `items`")
        else:
            log("fail", "sfera: personal task due today missing from `personale`")

        # 4) Pickerul boardului de munca nu ofera taskuri personale
        cand = s.get(f"{BASE_URL}/api/agenda/candidates?today={today}", timeout=5).json()
        if any(x['id'] == pid2 for x in cand.get('items', [])):
            log("fail", "sfera: personal LEAKS into agenda candidates")
        else:
            log("pass", "agenda/candidates excludes personal")

        # 5) Planificatorul (banda Globale + backlog) e doar munca
        plan = s.get(f"{BASE_URL}/api/plan", timeout=5).json()
        plan_ids = {t['id'] for lane in plan.get('lanes', []) for t in lane.get('tasks', [])}
        plan_ids |= {t['id'] for t in plan.get('backlog', [])}
        if pid in plan_ids or pid2 in plan_ids:
            log("fail", "sfera: personal LEAKS into /api/plan")
        else:
            log("pass", "/api/plan excludes personal")

        # 6) Recurenta pastreaza sfera (altfel taskul migreaza la munca la bifare)
        r = s.post(f"{BASE_URL}/api/global-tasks", headers=hdr(), timeout=5,
                   json={"titlu": "__proba_sfera_recurenta__", "sfera": "personal",
                         "status": "to_do", "data_scadenta": today, "recurenta": "zilnic"})
        rid = r.json()['id']; created.append(rid)
        r = s.put(f"{BASE_URL}/api/global-tasks/{rid}", headers=hdr(), timeout=5,
                  json={"status": "done"})
        spawned = r.json().get('recurring_spawned')
        if not spawned:
            log("fail", "sfera: recurring personal task did not spawn")
        else:
            created.append(spawned)
            sp = s.get(f"{BASE_URL}/api/global-tasks/{spawned}", timeout=5).json()
            log("pass" if sp.get('sfera') == 'personal' else "fail",
                f"recurring spawn keeps sfera ({sp.get('sfera')})")

        # 7) ICS: feedul implicit fara personal; feedul personal doar cu el;
        #    fara sesiune si fara cheie -> 401
        ics = s.get(f"{BASE_URL}/api/export/ics", timeout=5).text
        if '__proba_sfera_azi__' in ics:
            log("fail", "sfera: personal LEAKS into work ICS feed")
        else:
            log("pass", "ICS default (munca) excludes personal")
        ics_p = s.get(f"{BASE_URL}/api/export/ics?sfera=personal", timeout=5).text
        log("pass" if '__proba_sfera_azi__' in ics_p else "fail", "ICS ?sfera=personal contains personal")
        anon = requests.get(f"{BASE_URL}/api/export/ics?key=gresit", timeout=5)
        log("pass" if anon.status_code == 401 else "fail", f"ICS wrong key -> {anon.status_code} (expected 401)")
        key = s.get(f"{BASE_URL}/api/export/ics-key", timeout=5).json().get('key', '')
        anon2 = requests.get(f"{BASE_URL}/api/export/ics?sfera=personal&key={key}", timeout=5)
        log("pass" if anon2.status_code == 200 else "fail", f"ICS with feed key -> {anon2.status_code} (expected 200)")
    finally:
        for tid in created:
            try: s.delete(f"{BASE_URL}/api/global-tasks/{tid}", headers=hdr(), timeout=5)
            except Exception: pass

def google_sync_test():
    """Integrarea Google Calendar, FARA cont Google: starea neconfigurata e
    curata, fluxul OAuth respinge ce trebuie, iar backup-ul nu scurge chei
    `google_*` (refresh token-ul da acces la calendarul lui Ion)."""
    print("\n=== GOOGLE CALENDAR (neconfigurat) ===\n")
    pin = os.environ.get('PIF_DASHBOARD_PIN', '')
    if not pin:
        log("fail", "PIF_DASHBOARD_PIN required for google test"); return
    if os.environ.get('GOOGLE_CLIENT_ID'):
        log("warn", "GOOGLE_CLIENT_ID set in test env — skipping unconfigured-state checks"); return
    s = requests.Session()
    r = s.post(f"{BASE_URL}/login", json={"pin": pin}, timeout=5)
    if r.status_code != 200:
        log("fail", f"google: login -> {r.status_code}"); return

    def hdr():
        return {"X-CSRF-Token": s.cookies.get('csrf_token', '')}

    # 1) Status: neconfigurat, fara tokens in raspuns
    st = s.get(f"{BASE_URL}/api/google/status", timeout=5)
    if st.status_code != 200:
        log("fail", f"google: status -> {st.status_code}")
    else:
        j = st.json()
        log("pass" if j.get('configurat') is False and j.get('conectat') is False else "fail",
            f"status: configurat={j.get('configurat')}, conectat={j.get('conectat')}")
        if any('token' in k for k in j):
            log("fail", "google: status expune campuri de token")

    # 2) /oauth/google/start fara sesiune -> redirect la /login
    anon = requests.get(f"{BASE_URL}/oauth/google/start", allow_redirects=False, timeout=5)
    log("pass" if anon.status_code in (301, 302) and '/login' in anon.headers.get('Location', '')
        else "fail", f"oauth/start fara sesiune -> {anon.status_code} {anon.headers.get('Location', '')}")

    # 3) Cu sesiune dar neconfigurat -> inapoi in SPA cu google=eroare
    r = s.get(f"{BASE_URL}/oauth/google/start", allow_redirects=False, timeout=5)
    log("pass" if r.status_code in (301, 302) and 'google=eroare' in r.headers.get('Location', '')
        else "fail", f"oauth/start neconfigurat -> {r.headers.get('Location', '')}")

    # 4) Callback cu state fals -> eroare (nu atinge schimbul de token)
    r = s.get(f"{BASE_URL}/oauth/google/callback?state=fals&code=x", allow_redirects=False, timeout=5)
    log("pass" if r.status_code in (301, 302) and 'google=eroare' in r.headers.get('Location', '')
        else "fail", f"oauth/callback state fals -> {r.headers.get('Location', '')}")

    # 5) Resync neconectat -> 400
    r = s.post(f"{BASE_URL}/api/google/resync", headers=hdr(), json={}, timeout=5)
    log("pass" if r.status_code == 400 else "fail", f"resync neconectat -> {r.status_code} (expected 400)")

    # 6) Configurare din UI: PUT /api/google/credentials
    r = s.put(f"{BASE_URL}/api/google/credentials", headers=hdr(), json={"json": "nu-e-json"}, timeout=5)
    log("pass" if r.status_code == 400 else "fail", f"credentials JSON invalid -> {r.status_code} (expected 400)")
    r = s.put(f"{BASE_URL}/api/google/credentials", headers=hdr(),
              json={"json": json.dumps({"installed": {"client_id": "x", "client_secret": "y"}})}, timeout=5)
    log("pass" if r.status_code == 400 else "fail", f"credentials tip Desktop -> {r.status_code} (expected 400)")
    r = s.put(f"{BASE_URL}/api/google/credentials", headers=hdr(),
              json={"json": json.dumps({"web": {"client_id": "fals.apps.test", "client_secret": "SECRET-FALS"}})}, timeout=5)
    if r.status_code != 200:
        log("fail", f"credentials valide -> {r.status_code} (expected 200)")
    else:
        j = r.json()
        log("pass" if j.get('configurat') is True and j.get('sursa') == 'setari' else "fail",
            f"credentials salvate: configurat={j.get('configurat')}, sursa={j.get('sursa')}")
        if 'SECRET-FALS' in r.text:
            log("fail", "credentials: raspunsul ecoua secretul")
        # oauth/start e acum configurat -> 302 catre Google, nu google=eroare
        r2 = s.get(f"{BASE_URL}/oauth/google/start", allow_redirects=False, timeout=5)
        log("pass" if r2.status_code in (301, 302) and 'accounts.google.com' in r2.headers.get('Location', '')
            else "fail", f"oauth/start configurat -> {r2.headers.get('Location', '')[:60]}")

    # 7) Backup-ul nu contine chei google_* (pinneaza filtrul anti-scurgere);
    #    credentialele false de la pasul 6 sunt inca in app_settings — perfect
    #    ca proba, se curata la final.
    import sqlite3 as _sq
    db = os.environ.get('PIF_DB_PATH') or str(DB_PATH)
    try:
        c = _sq.connect(db)
        c.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('google_refresh_token', 'FALS-PENTRU-TEST', '')")
        c.commit()
        bk = s.get(f"{BASE_URL}/api/backup", timeout=15).json()
        chei = {r0.get('key') for r0 in bk.get('app_settings', [])}
        scurse = {k for k in chei if str(k).startswith('google_')}
        log("pass" if not scurse else "fail",
            "backup exclude cheile google_*" if not scurse else f"backup SCURGE {scurse}")
        dump = json.dumps(bk)
        if 'FALS-PENTRU-TEST' in dump or 'SECRET-FALS' in dump:
            log("fail", "backup contine valori de secrete google")
    finally:
        try:
            c.execute("DELETE FROM app_settings WHERE key LIKE 'google!_%' ESCAPE '!'")
            c.commit(); c.close()
        except Exception:
            pass


def data_integrity():
    print("\n=== DATA INTEGRITY ===\n")
    if not DB_PATH.exists():
        log("fail", "DB not found"); return
    try:
        conn = sqlite3.connect(str(DB_PATH)); conn.row_factory = sqlite3.Row
        cur = conn.cursor()
    except Exception as e:
        log("fail", f"Cannot connect: {e}"); return
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    
    checks = [
        ('tasks', 'proiecte', 'proiect_id', 'tasks'),
        ('task_subtasks', 'tasks', 'task_id', 'subtasks'),
        ('atasamente', 'proiecte', 'proiect_id', 'attachments'),
    ]
    
    for child, parent, fk, label in checks:
        if child in tables and parent in tables:
            cur.execute(f"SELECT COUNT(*) FROM {child} c LEFT JOIN {parent} p ON c.{fk}=p.id WHERE p.id IS NULL AND c.{fk} IS NOT NULL")
            n = cur.fetchone()[0]
            if n > 0: log("warn", f"{n} {label} have orphaned references")
            else: log("pass", f"No orphaned {label}")
    
    cur.execute("SELECT COUNT(*) FROM proiecte")
    total = cur.fetchone()[0]
    if total == 0: log("warn", "No projects in database")
    else:
        cur.execute("SELECT COUNT(DISTINCT proiect_id) FROM tasks WHERE proiect_id IS NOT NULL")
        with_tasks = cur.fetchone()[0]
        if with_tasks == 0: log("warn", "All projects have no tasks")
        else: log("pass", "Projects have tasks assigned")
    
    conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("  PIF DASHBOARD - TEST SUITE")
    print("=" * 50)
    
    # `--static` sare peste proba pe API, singura care cere un server pornit pe
    # :5000 SI PIN-ul real din mediu. Poarta de verificare (.claude/hooks/gate.py)
    # o foloseste: PIN-ul n-are unde sa stea fara sa ajunga intr-un fisier
    # versionat, iar partea de rulare o acopera oricum smoke_ui.py, care isi
    # porneste singur aplicatia, pe portul lui si pe o copie a bazei.
    static_analysis()
    if '--static' not in sys.argv:
        api_smoke_test()
        sfera_leak_test()
        google_sync_test()
    data_integrity()
    
    print("\n" + "=" * 50)
    print("  SUMMARY")
    print("=" * 50)
    print(f"  Passed:  {len(results['pass'])}")
    print(f"  Failed:  {len(results['fail'])}")
    print(f"  Warnings: {len(results['warn'])}")
    
    if results['fail']:
        print("\n  FAILURES:")
        for m in results['fail']: print(f"    - {m}")
        sys.exit(1)
    else:
        print("\n  All tests passed!")
        sys.exit(0)
