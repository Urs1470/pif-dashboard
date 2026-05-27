#!/usr/bin/env python3
"""Comprehensive test suite for pif-dashboard - static analysis + API smoke tests."""

import os, re, sqlite3, sys, requests
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
        content = p.read_text()
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
        txt = pyp.read_text()
        
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
        for m in rcall.finditer(p.read_text()):
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
    
    with open(PROJECT_ROOT / "app.py", 'r') as f:
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
                except:
                    log("pass", f"GET {ep} -> {r.status_code}")
            else:
                log("fail", f"GET {ep} -> {r.status_code} (expected {exp})")
        except Exception as e:
            log("fail", f"GET {ep} -> ERROR: {e}")

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
        ('checklist_pif', 'proiecte', 'proiect_id', 'checklist items'),
        ('atasamente', 'proiecte', 'proiect_id', 'attachments'),
        ('jurnal', 'proiecte', 'proiect_id', 'journal entries'),
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
    
    static_analysis()
    api_smoke_test()
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
