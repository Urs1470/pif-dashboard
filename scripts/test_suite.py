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
        c.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('push_vapid_private', 'FALS-PUSH-TEST', '')")
        c.commit()
        bk = s.get(f"{BASE_URL}/api/backup", timeout=15).json()
        chei = {r0.get('key') for r0 in bk.get('app_settings', [])}
        scurse = {k for k in chei if str(k).startswith(('google_', 'push_'))}
        log("pass" if not scurse else "fail",
            "backup exclude cheile google_* si push_*" if not scurse else f"backup SCURGE {scurse}")
        dump = json.dumps(bk)
        if 'FALS-PENTRU-TEST' in dump or 'SECRET-FALS' in dump or 'FALS-PUSH-TEST' in dump:
            log("fail", "backup contine valori de secrete")
    finally:
        try:
            c.execute("DELETE FROM app_settings WHERE key LIKE 'google!_%' ESCAPE '!'")
            c.execute("DELETE FROM app_settings WHERE key LIKE 'push!_%' ESCAPE '!'")
            c.commit(); c.close()
        except Exception:
            pass


def push_notifications_test():
    """Notificarile zilnice — fara serviciu push real: expeditorul se injecteaza,
    iar tokenul si ruta de actiune se verifica direct."""
    print("\n=== NOTIFICARI PUSH ===\n")
    pin = os.environ.get('PIF_DASHBOARD_PIN', '')
    if not pin:
        log("fail", "PIF_DASHBOARD_PIN required for push test"); return
    s = requests.Session()
    r = s.post(f"{BASE_URL}/login", json={"pin": pin}, timeout=5)
    if r.status_code != 200:
        log("fail", f"push: login -> {r.status_code}"); return

    def hdr():
        return {"X-CSRF-Token": s.cookies.get('csrf_token', '')}

    # 1) Status
    st = s.get(f"{BASE_URL}/api/push/status", timeout=5)
    if st.status_code != 200:
        log("fail", f"push: status -> {st.status_code}")
    else:
        j = st.json()
        ok = j.get('ora') == '08:00' and 'abonamente' in j and 'disponibil' in j
        log("pass" if ok else "fail", f"status: ora={j.get('ora')}, disponibil={j.get('disponibil')}")

    # 2) Cheia VAPID e STABILA (regenerarea ar invalida abonamentele in tacere)
    k1 = s.get(f"{BASE_URL}/api/push/vapid-public", timeout=5)
    if k1.status_code == 503:
        log("warn", "pywebpush lipseste in mediul de test — sar peste probele HTTP de push")
    elif k1.status_code != 200:
        log("fail", f"vapid-public -> {k1.status_code}")
    else:
        k2 = s.get(f"{BASE_URL}/api/push/vapid-public", timeout=5)
        cheie = k1.json().get('cheie', '')
        log("pass" if cheie and cheie == k2.json().get('cheie') else "fail",
            "cheia VAPID e stabila intre apeluri")

        # 3) Abonare / dezabonare
        sub = {"endpoint": "https://fcm.googleapis.com/fake/T1",
               "keys": {"p256dh": "cheie-falsa", "auth": "auth-fals"}}
        n0 = s.get(f"{BASE_URL}/api/push/status", timeout=5).json()['abonamente']
        s.post(f"{BASE_URL}/api/push/subscribe", headers=hdr(), json=sub, timeout=5)
        n1 = s.get(f"{BASE_URL}/api/push/status", timeout=5).json()['abonamente']
        s.post(f"{BASE_URL}/api/push/subscribe", headers=hdr(), json=sub, timeout=5)
        n2 = s.get(f"{BASE_URL}/api/push/status", timeout=5).json()['abonamente']
        log("pass" if n1 == n0 + 1 and n2 == n1 else "fail",
            f"subscribe: {n0} -> {n1} -> {n2} (al doilea e upsert, nu duplicat)")
        bad = s.post(f"{BASE_URL}/api/push/subscribe", headers=hdr(), json={"endpoint": "nu-e-https"}, timeout=5)
        log("pass" if bad.status_code == 400 else "fail", f"subscribe invalid -> {bad.status_code} (expected 400)")
        s.post(f"{BASE_URL}/api/push/unsubscribe", headers=hdr(), json={"endpoint": sub['endpoint']}, timeout=5)
        n3 = s.get(f"{BASE_URL}/api/push/status", timeout=5).json()['abonamente']
        log("pass" if n3 == n0 else "fail", f"unsubscribe -> {n3} (inapoi la {n0})")
        # test fara abonamente -> 400 (un test „reusit" catre nimeni e o minciuna)
        if n3 == 0:
            t = s.post(f"{BASE_URL}/api/push/test", headers=hdr(), json={}, timeout=5)
            log("pass" if t.status_code == 400 else "fail", f"test fara abonamente -> {t.status_code} (expected 400)")

    # 4) Logica zilnica + tokenul, prin import direct (fara HTTP, fara push real)
    sys.path.insert(0, str(PROJECT_ROOT))
    import sqlite3 as _sq
    from datetime import datetime as _dt, timedelta as _td
    db = os.environ.get('PIF_DB_PATH') or str(DB_PATH)
    os.environ.setdefault('PIF_DB_PATH', db)
    try:
        from blueprints import push as pushmod
    except Exception as e:
        log("fail", f"push: import blueprints.push a esuat: {e}"); return

    pushmod._secret = b'secret-de-test'
    c = _sq.connect(db)
    tid = 'proba-push-0001'
    vechi = (_dt.now() - _td(days=3)).isoformat()
    proaspat = (_dt.now() - _td(days=1)).isoformat()
    try:
        c.execute("DELETE FROM app_settings WHERE key = 'push_daily_last'")
        c.execute("INSERT OR REPLACE INTO global_tasks (id, titlu, status, sfera, data_scadenta, created_at, updated_at) "
                  "VALUES (?, ?, 'to_do', 'personal', '', ?, ?)", (tid, '__proba_push__', vechi, vechi))
        c.commit()

        capturate = []
        azi8 = _dt.now().replace(hour=8, minute=5, second=0, microsecond=0)
        azi7 = azi8.replace(hour=7)

        r1 = pushmod.check_and_send_daily(now=azi7, trimite=capturate.append)
        log("pass" if r1 == 'devreme' and not capturate else "fail", f"inainte de ora 8 -> {r1}, {len(capturate)} trimise")

        r2 = pushmod.check_and_send_daily(now=azi8, trimite=capturate.append)
        unul = [p for p in capturate if p.get('title') == '__proba_push__']
        ok_forma = bool(unul) and unul[0]['tag'] == f'pif-task-{tid}' \
            and f'focus=global:{tid}' in unul[0]['url'] and unul[0].get('actions') is True
        log("pass" if r2 == 'trimis' and ok_forma else "fail",
            f"la ora 8 -> {r2}; notificare PER task cu tag/url/actiuni corecte: {ok_forma}")

        r3 = pushmod.check_and_send_daily(now=azi8, trimite=capturate.append)
        log("pass" if r3 == 'claimed-gata' else "fail", f"a doua rulare in aceeasi zi -> {r3} (fara dublura)")

        # Zi fara taskuri: claim consumat, zero notificari
        c.execute("DELETE FROM app_settings WHERE key = 'push_daily_last'")
        c.execute("UPDATE global_tasks SET status = 'done' WHERE id = ?", (tid,))
        c.commit()
        n_inainte = len(capturate)
        r4 = pushmod.check_and_send_daily(now=azi8, trimite=capturate.append)
        log("pass" if r4 == 'nimic' and len(capturate) == n_inainte else "fail", f"zi fara taskuri -> {r4}")

        # Marginea de varsta: 1 zi = prea proaspat
        c.execute("DELETE FROM app_settings WHERE key = 'push_daily_last'")
        c.execute("UPDATE global_tasks SET status = 'to_do', created_at = ? WHERE id = ?", (proaspat, tid))
        c.commit()
        r5 = pushmod.check_and_send_daily(now=azi8, trimite=capturate.append)
        log("pass" if r5 == 'nimic' else "fail", f"task de 1 zi -> {r5} (nu se notifica)")

        # 4b) LANTUL REAL DE TRIMITERE: cheia VAPID -> criptare -> semnare.
        # Verificarile de mai sus injecteaza un expeditor fals, deci NU ating
        # niciodata `webpush`. Exact acolo statea bugul: cheia era salvata ca
        # PKCS8 PEM, iar `py_vapid.from_string` cere scalarul brut (32 octeti
        # base64url) — semnarea crapa inainte de orice apel spre Google, si
        # „Trimite test" pica fara sa spuna de ce. Proba: un abonament fals dar
        # VALID criptografic, cu endpointul spre un host mort; daca ajungem la
        # retea, criptarea si semnarea au mers.
        if pushmod._PUSH_OK:
            import base64 as _b64m
            from cryptography.hazmat.primitives import serialization as _ser
            from cryptography.hazmat.primitives.asymmetric import ec as _ec
            priv, pub = pushmod._chei_vapid()
            brut_ok = '-----BEGIN' not in priv
            try:
                brut_ok = brut_ok and len(_b64m.urlsafe_b64decode(priv + '=' * (-len(priv) % 4))) == 32
            except Exception:
                brut_ok = False
            log("pass" if brut_ok else "fail",
                "cheia VAPID privata e in formatul citit de py_vapid (raw 32B)")

            _k = _ec.generate_private_key(_ec.SECP256R1())
            _p256dh = _b64m.urlsafe_b64encode(_k.public_key().public_bytes(
                encoding=_ser.Encoding.X962,
                format=_ser.PublicFormat.UncompressedPoint)).decode().rstrip('=')
            _auth = _b64m.urlsafe_b64encode(os.urandom(16)).decode().rstrip('=')
            from pywebpush import webpush as _wp
            try:
                _wp(subscription_info={'endpoint': 'https://fcm.googleapis.invalid:9/x',
                                       'keys': {'p256dh': _p256dh, 'auth': _auth}},
                    data=json.dumps({'title': 'proba'}),
                    vapid_private_key=priv,
                    vapid_claims={'sub': pushmod.PUSH_SUB},
                    timeout=3)
                log("warn", "proba de trimitere a reusit catre un host mort (neasteptat)")
            except Exception as _e:
                _t, _m = type(_e).__name__, str(_e)
                retea = ('Connection' in _t or 'Connection' in _m or 'Max retries' in _m
                         or 'resolve' in _m.lower() or 'timed out' in _m.lower())
                log("pass" if retea else "fail",
                    "criptare+semnare VAPID merg (a picat doar reteaua)" if retea
                    else f"trimiterea crapa INAINTE de retea: {_t}: {_m[:90]}")

        # 5) Tokenul
        tok = pushmod.mint_token(tid)
        log("pass" if pushmod.verifica_token(tok) == tid else "fail", "token: mint -> verifica")
        log("pass" if pushmod.verifica_token(tok[:-2] + 'xx') is None else "fail", "token alterat -> respins")
        expirat = pushmod.mint_token(tid, acum=_dt.now() - _td(hours=pushmod.TOKEN_VALABIL_ORE + 1))
        log("pass" if pushmod.verifica_token(expirat) is None else "fail", "token expirat -> respins")

        # 6) Ruta de actiune: FARA header CSRF (SW-ul nu poate citi cookie-ul),
        #    dar CU cookie de sesiune — pinneaza exceptia din csrf.py.
        c.execute("UPDATE global_tasks SET status='to_do', data_scadenta='' WHERE id = ?", (tid,))
        c.commit()
        # tokenul serverului foloseste SECRET_KEY-ul lui, nu pe al nostru; il
        # luam prin ruta, deci semnam cu secretul procesului server: aici
        # verificam doar respingerea, plus forma raspunsului.
        rej = s.post(f"{BASE_URL}/api/push/action", json={"token": "gunoi", "action": "done"}, timeout=5)
        log("pass" if rej.status_code == 403 else "fail", f"action cu token invalid -> {rej.status_code} (expected 403)")
        log("pass" if rej.status_code != 403 or 'CSRF' not in rej.text else "fail",
            "action e scutita de CSRF (a ajuns la validarea tokenului)")
    finally:
        try:
            c.execute("DELETE FROM global_tasks WHERE id = ?", (tid,))
            c.execute("DELETE FROM app_settings WHERE key LIKE 'push!_%' ESCAPE '!'")
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
        push_notifications_test()
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
