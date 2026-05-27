# Hermes Assistant Blueprint
# Provides /api/assistant/* routes plus the tool registry. MiniMax gateway
# is configured via .assistant_config on the server (gitignored).
#
# Extracted from app.py to keep the main module manageable. The tool registry
# pattern (@assistant_tool decorator) was introduced in HIGH-Q3 refactor; this
# blueprint simply hosts the handlers and routes in their own module.

from flask import Blueprint, jsonify, request, session
from functools import wraps
from datetime import datetime
import json
import os
import uuid
import urllib.request
import urllib.error
import urllib.parse
import logging

from database import get_db

logger = logging.getLogger('pif_dashboard')

assistant_bp = Blueprint('assistant', __name__, url_prefix='/api/assistant')


def login_required(f):
    """Local login_required — same shape as app.py and budget.py versions."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


def generate_uuid():
    return str(uuid.uuid4())


from blueprints.obsidian import _obsidian_vault, _obsidian_index, _obsidian_safe_path
from utils import safe_table


# ============================================================
# Assistant configuration + system prompt
# ============================================================
ASSISTANT_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '.assistant_config'
)

ASSISTANT_SYSTEM_PROMPT = """Ești Hermes — asistentul personal, specializat, integrat în
PIF Dashboard. Lucrezi exclusiv pentru Ion și ești singurul lui asistent în aplicație.

CINE E ION
- Inginer de punere în funcțiune (commissioning) pentru convertoare de frecvență
  industriale. Lucrează pe teren: PIF (puneri în funcțiune) și Service.
- Single user al aplicației — tot ce e aici e al lui.

CUM COMUNICI CU EL
- Mereu în română. Direct, concis, la obiect. Fără emoji, fără introduceri
  politicoase lungi, fără să repeți întrebarea lui.
- Înțelege-l din jumătate de cuvânt: folosește contextul conversației, MEMORIA ta
  și datele reale din aplicație ca să deduci ce vrea. Nu pune întrebări inutile.
- Dacă cererea e cu adevărat ambiguă (ex: nu se știe la ce proiect), întreabă
  scurt. Altfel acționează pe interpretarea cea mai rezonabilă și spune ce ai
  presupus.
- Ești colaborativ și proactiv: dacă vezi ceva util (task scadent, inconsistență,
  un pas care lipsește), spune-i.
- După fiecare acțiune, confirmă scurt și concret ce ai făcut.
- Confirmă în chat ÎNAINTE de ștergeri sau acțiuni ireversibile.

DOMENIUL
- PIF = Punere În Funcțiune. Service = mentenanță/intervenții.
- Familii de convertoare: ABB ACS580 / ACS880, Siemens SINAMICS G120 /
  SINAMICS_G130_G150 / SINAMICS_S120_S150, Danfoss VLT FC302, Lenze i550 / i950.

MODELUL APLICAȚIEI
- Proiecte (tip PIF sau Service), fiecare cu: taskuri, checklist, jurnal de
  activitate, cronometru, echipamente. Status proiect: in_lucru, in_asteptare,
  blocat, finalizat.
- Taskuri: status to_do/in_lucru/done, prioritate normal/urgent/minor, scadență,
  descriere, subtaskuri, recurență (zilnic/saptamanal/lunar).
- Taskuri zilnice (globale) — independente de proiect.
- Bază de ~14.700 parametri de convertoare, cu explicații și influențe.
- Notițele tehnice Obsidian ale lui Ion.
- Clienți și echipamente.

REGULI DE LUCRU
- Caută mereu informația reală cu uneltele — nu inventa date. Dacă o unealtă nu
  găsește nimic, spune clar.
- Pentru parametri: search_parametri / get_parametru.
- Pentru notițele lui Ion: search_obsidian / read_obsidian_note.
- Ai acces complet: poți crea, modifica și șterge proiecte, taskuri, taskuri
  zilnice, subtaskuri, checklist, jurnal, echipamente, clienți.

MEMORIA TA
- Ai o memorie persistentă, vizibilă mai jos. Conține preferințele lui Ion,
  context recurent, decizii, clienți/echipamente uzuale.
- Când Ion îți spune o preferință sau un detaliu de context care contează pe
  termen lung, salvează-l cu save_memory. Nu salva lucruri triviale sau ușor de
  regăsit din datele aplicației.
- Folosește memoria activ ca să-l înțelegi mai bine de fiecare dată."""


def _load_assistant_memory():
    """Return the assistant's persistent memory entries (oldest first)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, continut FROM assistant_memory ORDER BY created_at ASC')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def _build_assistant_system_prompt():
    """System prompt + the current memory section."""
    mem = _load_assistant_memory()
    if not mem:
        return ASSISTANT_SYSTEM_PROMPT + '\n\nMEMORIE: (goală încă)'
    lines = '\n'.join(f"- [{m['id'][:8]}] {m['continut']}" for m in mem)
    return ASSISTANT_SYSTEM_PROMPT + '\n\nMEMORIE (lucruri reținute despre Ion și context):\n' + lines

# Tool schemas (OpenAI-compatible function calling).
ASSISTANT_TOOLS = [
    {"type": "function", "function": {
        "name": "search_parametri",
        "description": "Caută parametri de convertor în baza de date după text (cod sau descriere), opțional filtrat pe familie.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "cod parametru (ex 30.12) sau cuvinte din descriere"},
            "familie": {"type": "string", "description": "opțional: ACS580, ACS880, SINAMICS_G120, SINAMICS_G130_G150, SINAMICS_S120_S150, Danfoss_VLT_FC302, Lenze_i550, Lenze_i950"}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "get_parametru",
        "description": "Returnează detaliul complet al unui parametru (descriere, acces, default, min/max, explicație, influențe).",
        "parameters": {"type": "object", "properties": {
            "familie": {"type": "string"},
            "cod": {"type": "string", "description": "codul exact al parametrului"}
        }, "required": ["familie", "cod"]}
    }},
    {"type": "function", "function": {
        "name": "search_obsidian",
        "description": "Caută în notițele tehnice Obsidian ale utilizatorului (full-text).",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "read_obsidian_note",
        "description": "Citește conținutul complet al unei notițe Obsidian după calea ei relativă.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "calea relativă a notiței (din search_obsidian)"}
        }, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "list_proiecte",
        "description": "Listează proiectele, opțional filtrate pe status.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "opțional: in_lucru, in_asteptare, blocat, finalizat"}
        }}
    }},
    {"type": "function", "function": {
        "name": "get_proiect",
        "description": "Detaliul unui proiect după nume (parțial) sau id: date proiect, taskuri, checklist, jurnal.",
        "parameters": {"type": "object", "properties": {
            "nume": {"type": "string", "description": "nume parțial sau id de proiect"}
        }, "required": ["nume"]}
    }},
    {"type": "function", "function": {
        "name": "create_proiect",
        "description": "Creează un proiect nou.",
        "parameters": {"type": "object", "properties": {
            "nume": {"type": "string"},
            "tip": {"type": "string", "description": "PIF sau Service"},
            "client": {"type": "string"},
            "producator": {"type": "string", "description": "ex ABB, Siemens, Danfoss, Lenze"},
            "locatie": {"type": "string"}
        }, "required": ["nume"]}
    }},
    {"type": "function", "function": {
        "name": "create_task",
        "description": "Adaugă un task într-un proiect.",
        "parameters": {"type": "object", "properties": {
            "proiect": {"type": "string", "description": "nume parțial sau id de proiect"},
            "titlu": {"type": "string"},
            "prioritate": {"type": "string", "description": "normal, urgent, minor"},
            "scadenta": {"type": "string", "description": "data YYYY-MM-DD, opțional"},
            "descriere": {"type": "string"},
            "recurenta": {"type": "string", "description": "opțional: zilnic, saptamanal, lunar"}
        }, "required": ["proiect", "titlu"]}
    }},
    {"type": "function", "function": {
        "name": "add_checklist_item",
        "description": "Adaugă un punct în checklist-ul unui proiect.",
        "parameters": {"type": "object", "properties": {
            "proiect": {"type": "string"},
            "titlu": {"type": "string"}
        }, "required": ["proiect", "titlu"]}
    }},
    {"type": "function", "function": {
        "name": "add_jurnal",
        "description": "Adaugă o intrare în jurnalul unui proiect.",
        "parameters": {"type": "object", "properties": {
            "proiect": {"type": "string"},
            "continut": {"type": "string"}
        }, "required": ["proiect", "continut"]}
    }},
    {"type": "function", "function": {
        "name": "update_task",
        "description": "Modifică un task dintr-un proiect (găsit după titlu parțial). Trimite doar câmpurile de schimbat.",
        "parameters": {"type": "object", "properties": {
            "proiect": {"type": "string"},
            "task": {"type": "string", "description": "titlu parțial al taskului de modificat"},
            "status": {"type": "string", "description": "to_do, in_lucru, done"},
            "prioritate": {"type": "string", "description": "normal, urgent, minor"},
            "scadenta": {"type": "string", "description": "data YYYY-MM-DD"},
            "descriere": {"type": "string"},
            "recurenta": {"type": "string", "description": "zilnic, saptamanal, lunar sau gol"}
        }, "required": ["proiect", "task"]}
    }},
    # delete_task removed from the LLM tool surface — destructive operations
    # without server-side confirmation were the highest-impact finding in the
    # security audit. Delete tasks from the UI instead.
    {"type": "function", "function": {
        "name": "add_subtask",
        "description": "Adaugă un subtask la un task dintr-un proiect (taskul găsit după titlu parțial).",
        "parameters": {"type": "object", "properties": {
            "proiect": {"type": "string"},
            "task": {"type": "string", "description": "titlu parțial al taskului părinte"},
            "titlu": {"type": "string", "description": "titlul subtaskului"}
        }, "required": ["proiect", "task", "titlu"]}
    }},
    {"type": "function", "function": {
        "name": "update_proiect",
        "description": "Modifică orice câmp al unui proiect. Trimite doar câmpurile pe care le schimbi. Orice modificare (inclusiv redenumirea prin nume_nou) pastreaza tot continutul proiectului: taskuri, jurnal, checklist, timer, echipamente.",
        "parameters": {"type": "object", "properties": {
            "nume": {"type": "string", "description": "nume parțial sau id al proiectului de modificat (cheie de cautare)"},
            "nume_nou": {"type": "string", "description": "noul nume al proiectului — pentru redenumire"},
            "tip": {"type": "string", "description": "PIF sau Service"},
            "status": {"type": "string", "description": "in_lucru, in_asteptare, blocat, finalizat"},
            "client": {"type": "string"},
            "locatie": {"type": "string"},
            "producator": {"type": "string", "description": "ABB, Siemens, Danfoss, Lenze, Altul"},
            "echipament_principal": {"type": "string"},
            "cod_proiect": {"type": "string"},
            "pm": {"type": "string", "description": "responsabil proiect"},
            "folder_server": {"type": "string"},
            "data_incepere": {"type": "string", "description": "data de inceput, format YYYY-MM-DD"},
            "deadline": {"type": "string", "description": "termen limita, format YYYY-MM-DD"},
            "nr_comanda": {"type": "string"},
            "nr_contract": {"type": "string"},
            "observatii": {"type": "string"},
            "service_before": {"type": "string", "description": "constatari Service (inainte de interventie)"},
            "service_after": {"type": "string", "description": "actiuni Service (dupa interventie)"}
        }, "required": ["nume"]}
    }},
    # delete_proiect removed from the LLM tool surface — see delete_task note.
    {"type": "function", "function": {
        "name": "toggle_checklist_item",
        "description": "Bifează sau debifează un punct din checklist-ul unui proiect (găsit după titlu parțial).",
        "parameters": {"type": "object", "properties": {
            "proiect": {"type": "string"},
            "item": {"type": "string", "description": "titlu parțial al punctului din checklist"},
            "completed": {"type": "boolean", "description": "true = bifat, false = debifat"}
        }, "required": ["proiect", "item", "completed"]}
    }},
    {"type": "function", "function": {
        "name": "add_echipament",
        "description": "Adaugă un echipament la un proiect.",
        "parameters": {"type": "object", "properties": {
            "proiect": {"type": "string"},
            "nume": {"type": "string"},
            "producator": {"type": "string"},
            "model": {"type": "string"},
            "serial_number": {"type": "string"}
        }, "required": ["proiect", "nume"]}
    }},
    {"type": "function", "function": {
        "name": "list_clienti",
        "description": "Listează clienții.",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "create_client",
        "description": "Creează un client nou.",
        "parameters": {"type": "object", "properties": {
            "nume": {"type": "string"},
            "telefon": {"type": "string"},
            "email": {"type": "string"},
            "adresa": {"type": "string"},
            "contact_principal": {"type": "string"}
        }, "required": ["nume"]}
    }},
    {"type": "function", "function": {
        "name": "list_global_tasks",
        "description": "Listează taskurile zilnice (globale, independente de proiect).",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "create_global_task",
        "description": "Creează un task zilnic (global, independent de proiect).",
        "parameters": {"type": "object", "properties": {
            "titlu": {"type": "string"},
            "prioritate": {"type": "string", "description": "Normal, Urgent, Minor"},
            "categorie": {"type": "string"},
            "scadenta": {"type": "string", "description": "data YYYY-MM-DD"},
            "descriere": {"type": "string"}
        }, "required": ["titlu"]}
    }},
    {"type": "function", "function": {
        "name": "save_memory",
        "description": "Salvează în memoria ta persistentă un fapt despre Ion sau contextul de lucru, ca să-l ții minte data viitoare.",
        "parameters": {"type": "object", "properties": {
            "continut": {"type": "string", "description": "faptul de reținut, o frază scurtă"}
        }, "required": ["continut"]}
    }},
    # delete_memory removed from the LLM tool surface — see delete_task note.
    # Memory entries can be deleted from the UI.
    {"type": "function", "function": {
        "name": "lookup_fault_code",
        "description": "Cauta un cod de eroare/avarie/avertizare al unui convertor de frecventa (ABB, Siemens, Danfoss, Lenze) si returneaza cauza si remediul. Foloseste cand Ion intreaba ce inseamna un cod afisat de drive (ex: F30001, 2310, A07910, ALARM 14).",
        "parameters": {"type": "object", "properties": {
            "cod": {"type": "string", "description": "codul de eroare cautat (ex: F30001, 2310, A2B4, 14)"},
            "producator": {"type": "string", "description": "optional: ABB, Siemens, Danfoss sau Lenze"},
            "familie": {"type": "string", "description": "optional: familia (ex: ACS580, SINAMICS_G120)"}
        }, "required": ["cod"]}
    }},
]


# ============================================================
# Assistant tool registry — replaces the long if/elif chain in
# _assistant_exec_tool with a name->handler dispatch table.
# Each tool body is a small function decorated with @assistant_tool.
# ============================================================
_ASSISTANT_HANDLERS = {}


def assistant_tool(name):
    """Decorator: register a Hermes tool handler under `name`."""
    def wrap(fn):
        _ASSISTANT_HANDLERS[name] = fn
        return fn
    return wrap


def _load_assistant_config():
    """Read MiniMax gateway config from .assistant_config (JSON)."""
    try:
        with open(ASSISTANT_CONFIG_FILE, 'r', encoding='utf-8') as fh:
            cfg = json.load(fh)
        if cfg.get('api_url') and cfg.get('api_key') and cfg.get('model'):
            return cfg
    except (OSError, ValueError):
        pass
    return None


def _normalize_assistant_url(url):
    """MiniMax's Anthropic-compatible endpoint is <base>/anthropic/v1/messages.
    Hermes supplied a slightly-off path (/anthropic/v1/chat/completions) — fix it."""
    url = (url or '').strip().rstrip('/')
    if '/anthropic' in url:
        base = url.split('/anthropic')[0]
        return base + '/anthropic/v1/messages'
    return url


def _anthropic_tools():
    """Convert the OpenAI-style tool schemas to Anthropic's tool format."""
    return [{
        'name': t['function']['name'],
        'description': t['function']['description'],
        'input_schema': t['function']['parameters'],
    } for t in ASSISTANT_TOOLS]


def _minimax_call(cfg, system, messages):
    """One round-trip to the MiniMax Anthropic-compatible Messages endpoint.
    Raises RuntimeError with the response body on an HTTP error."""
    import urllib.request
    import urllib.error
    payload = json.dumps({
        'model': cfg['model'],
        'max_tokens': 2048,
        'system': system,
        'messages': messages,
        'tools': _anthropic_tools(),
    }).encode('utf-8')
    req = urllib.request.Request(
        _normalize_assistant_url(cfg['api_url']),
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + cfg['api_key'],
            'x-api-key': cfg['api_key'],
            'anthropic-version': '2023-06-01',
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')[:400]
        raise RuntimeError(f'API {e.code}: {body}')


def _assistant_find_project(cursor, needle):
    """Resolve a project by id or partial name. Returns the Row or None."""
    needle = (needle or '').strip()
    if not needle:
        return None
    cursor.execute('SELECT * FROM proiecte WHERE id = ?', (needle,))
    row = cursor.fetchone()
    if row:
        return row
    cursor.execute('SELECT * FROM proiecte WHERE nume LIKE ? ORDER BY data_crearii DESC LIMIT 1',
                   (f'%{needle}%',))
    return cursor.fetchone()


@assistant_tool('search_parametri')
def _tool_search_parametri(args):
    conn = get_db(); cur = conn.cursor()
    q = f"%{(args.get('query') or '').strip()}%"
    sql = ('SELECT id, familie, parametru, descriere_scurta, descriere FROM parametri_master '
           'WHERE (parametru LIKE ? OR descriere LIKE ?)')
    params = [q, q]
    if args.get('familie'):
        sql += ' AND familie = ?'
        params.append(args['familie'])
    sql += ' ORDER BY familie, parametru LIMIT 25'
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {'count': len(rows), 'parametri': rows}


@assistant_tool('get_parametru')
def _tool_get_parametru(args):
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM parametri_master WHERE familie = ? AND parametru = ? LIMIT 1',
                (args.get('familie'), args.get('cod')))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {'error': 'Parametrul nu a fost găsit'}
    d = dict(row)
    d.pop('pdf_extra', None)
    return d


@assistant_tool('search_obsidian')
def _tool_search_obsidian(args):
    vault = _obsidian_vault()
    if not vault:
        return {'error': 'Vault Obsidian neconfigurat'}
    q = (args.get('query') or '').strip().lower()
    out = []
    for n in _obsidian_index(vault):
        if q in n['title'].lower() or q in n['content'].lower():
            out.append({'path': n['path'], 'title': n['title']})
        if len(out) >= 20:
            break
    return {'count': len(out), 'note': out}


@assistant_tool('read_obsidian_note')
def _tool_read_obsidian_note(args):
    vault = _obsidian_vault()
    if not vault:
        return {'error': 'Vault Obsidian neconfigurat'}
    abspath = _obsidian_safe_path(vault, args.get('path'))
    if not abspath or not os.path.isfile(abspath):
        return {'error': 'Nota nu a fost găsită'}
    with open(abspath, 'r', encoding='utf-8', errors='ignore') as fh:
        return {'path': args.get('path'), 'content': fh.read()[:8000]}


@assistant_tool('list_proiecte')
def _tool_list_proiecte(args):
    conn = get_db(); cur = conn.cursor()
    sql = 'SELECT id, nume, tip, client, producator, status FROM proiecte'
    params = []
    if args.get('status'):
        sql += ' WHERE status = ?'
        params.append(args['status'])
    sql += ' ORDER BY data_crearii DESC LIMIT 60'
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {'count': len(rows), 'proiecte': rows}


@assistant_tool('get_proiect')
def _tool_get_proiect(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('nume'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    pid = proj['id']
    cur.execute('SELECT titlu, status, prioritate, data_scadenta FROM tasks WHERE proiect_id = ? ORDER BY ordine', (pid,))
    tasks = [dict(r) for r in cur.fetchall()]
    cur.execute('SELECT titlu, completed FROM checklist_pif WHERE proiect_id = ?', (pid,))
    checklist = [dict(r) for r in cur.fetchall()]
    cur.execute('SELECT data, continut FROM jurnal WHERE proiect_id = ? ORDER BY created_at DESC LIMIT 10', (pid,))
    jurnal = [dict(r) for r in cur.fetchall()]
    cur.execute('SELECT nume, producator, model, serial_number FROM echipamente WHERE proiect_id = ?', (pid,))
    echipamente = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {'proiect': dict(proj), 'taskuri': tasks, 'checklist': checklist,
            'jurnal': jurnal, 'echipamente': echipamente}


@assistant_tool('create_proiect')
def _tool_create_proiect(args):
    conn = get_db(); cur = conn.cursor()
    now = datetime.now().isoformat()
    pid = generate_uuid()
    cur.execute('''
        INSERT INTO proiecte (id, tip, nume, client, producator, locatie, status, data_crearii, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'in_lucru', ?, ?)
    ''', (pid, args.get('tip', 'PIF'), args.get('nume', ''), args.get('client', ''),
          args.get('producator', ''), args.get('locatie', ''), now, now))
    conn.commit(); conn.close()
    return {'ok': True, 'id': pid, 'mesaj': f"Proiect creat: {args.get('nume')}"}


@assistant_tool('create_task')
def _tool_create_task(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('proiect'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    now = datetime.now().isoformat()
    tid = generate_uuid()
    cur.execute('SELECT COALESCE(MAX(ordine), 0) FROM tasks WHERE proiect_id = ?', (proj['id'],))
    mo = cur.fetchone()[0]
    cur.execute('''
        INSERT INTO tasks (id, proiect_id, titlu, status, prioritate, data_scadenta,
                           data_finalizare, ordine, created_at, descriere, recurenta, updated_at)
        VALUES (?, ?, ?, 'to_do', ?, ?, '', ?, ?, ?, ?, ?)
    ''', (tid, proj['id'], args.get('titlu', ''), args.get('prioritate', 'normal'),
          args.get('scadenta', ''), mo + 1, now, args.get('descriere', ''),
          args.get('recurenta', ''), now))
    conn.commit(); conn.close()
    return {'ok': True, 'id': tid, 'mesaj': f"Task adăugat în {proj['nume']}: {args.get('titlu')}"}


@assistant_tool('add_checklist_item')
def _tool_add_checklist_item(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('proiect'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    now = datetime.now().isoformat()
    cid = generate_uuid()
    cur.execute('''
        INSERT INTO checklist_pif (id, proiect_id, titlu, completed, note, ordine, categorie_id)
        VALUES (?, ?, ?, 0, '', 0, NULL)
    ''', (cid, proj['id'], args.get('titlu', '')))
    conn.commit(); conn.close()
    return {'ok': True, 'id': cid, 'mesaj': f"Checklist item adăugat: {args.get('titlu')}"}


@assistant_tool('add_jurnal')
def _tool_add_jurnal(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('proiect'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    now = datetime.now().isoformat()
    jid = generate_uuid()
    cur.execute('INSERT INTO jurnal (id, proiect_id, data, continut, created_at) VALUES (?, ?, ?, ?, ?)',
                (jid, proj['id'], now[:10], args.get('continut', ''), now))
    conn.commit(); conn.close()
    return {'ok': True, 'id': jid, 'mesaj': 'Intrare adăugată în jurnal'}


@assistant_tool('update_task')
def _tool_update_task(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('proiect'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    cur.execute('SELECT id, titlu FROM tasks WHERE proiect_id = ? AND titlu LIKE ? LIMIT 1',
                (proj['id'], f"%{args.get('task') or ''}%"))
    task = cur.fetchone()
    if not task:
        conn.close()
        return {'error': 'Taskul nu a fost găsit'}
    cur.execute('''UPDATE tasks SET
        status = COALESCE(?, status), prioritate = COALESCE(?, prioritate),
        data_scadenta = COALESCE(?, data_scadenta), descriere = COALESCE(?, descriere),
        recurenta = COALESCE(?, recurenta), updated_at = ? WHERE id = ?''',
        (args.get('status'), args.get('prioritate'), args.get('scadenta'),
         args.get('descriere'), args.get('recurenta'), datetime.now().isoformat(), task['id']))
    conn.commit(); conn.close()
    return {'ok': True, 'mesaj': f"Task actualizat: {task['titlu']}"}


@assistant_tool('delete_task')
def _tool_delete_task(args):
    # Defence in depth — schema is removed, but if the LLM somehow emits
    # this tool name we refuse server-side instead of running the delete.
    return {'error': 'Funcția dezactivată din motive de securitate. Șterge taskul din UI.'}


@assistant_tool('add_subtask')
def _tool_add_subtask(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('proiect'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    cur.execute('SELECT id, titlu FROM tasks WHERE proiect_id = ? AND titlu LIKE ? LIMIT 1',
                (proj['id'], f"%{args.get('task') or ''}%"))
    task = cur.fetchone()
    if not task:
        conn.close()
        return {'error': 'Taskul nu a fost găsit'}
    now = datetime.now().isoformat()
    cur.execute('SELECT COALESCE(MAX(ordine), -1) + 1 FROM task_subtasks WHERE task_id = ?', (task['id'],))
    mo = cur.fetchone()[0]
    cur.execute('INSERT INTO task_subtasks (id, task_id, titlu, done, ordine, created_at) VALUES (?, ?, ?, 0, ?, ?)',
                (generate_uuid(), task['id'], args.get('titlu', ''), mo, now))
    conn.commit(); conn.close()
    return {'ok': True, 'mesaj': f"Subtask adăugat la '{task['titlu']}': {args.get('titlu')}"}


@assistant_tool('update_proiect')
def _tool_update_proiect(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('nume'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    nume_nou = (args.get('nume_nou') or '').strip() or None
    cur.execute('''UPDATE proiecte SET
        nume = COALESCE(?, nume), tip = COALESCE(?, tip),
        status = COALESCE(?, status), client = COALESCE(?, client),
        locatie = COALESCE(?, locatie), producator = COALESCE(?, producator),
        echipament_principal = COALESCE(?, echipament_principal),
        cod_proiect = COALESCE(?, cod_proiect), pm = COALESCE(?, pm),
        folder_server = COALESCE(?, folder_server),
        data_incepere = COALESCE(?, data_incepere), deadline = COALESCE(?, deadline),
        nr_comanda = COALESCE(?, nr_comanda), nr_contract = COALESCE(?, nr_contract),
        observatii = COALESCE(?, observatii),
        service_before = COALESCE(?, service_before),
        service_after = COALESCE(?, service_after),
        updated_at = ? WHERE id = ?''',
        (nume_nou, args.get('tip'), args.get('status'), args.get('client'),
         args.get('locatie'), args.get('producator'), args.get('echipament_principal'),
         args.get('cod_proiect'), args.get('pm'), args.get('folder_server'),
         args.get('data_incepere'), args.get('deadline'), args.get('nr_comanda'),
         args.get('nr_contract'), args.get('observatii'), args.get('service_before'),
         args.get('service_after'), datetime.now().isoformat(), proj['id']))
    conn.commit(); conn.close()
    return {'ok': True, 'mesaj': f"Proiect actualizat: {nume_nou or proj['nume']}"}


@assistant_tool('delete_proiect')
def _tool_delete_proiect(args):
    # Defence in depth — schema removed; server-side refusal too.
    return {'error': 'Funcția dezactivată din motive de securitate. Șterge proiectul din UI.'}


@assistant_tool('toggle_checklist_item')
def _tool_toggle_checklist_item(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('proiect'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    cur.execute('SELECT id, titlu FROM checklist_pif WHERE proiect_id = ? AND titlu LIKE ? LIMIT 1',
                (proj['id'], f"%{args.get('item') or ''}%"))
    item = cur.fetchone()
    if not item:
        conn.close()
        return {'error': 'Punctul din checklist nu a fost găsit'}
    done = 1 if args.get('completed') else 0
    cur.execute('UPDATE checklist_pif SET completed = ? WHERE id = ?', (done, item['id']))
    conn.commit(); conn.close()
    return {'ok': True, 'mesaj': f"Checklist '{item['titlu']}': {'bifat' if done else 'debifat'}"}


@assistant_tool('add_echipament')
def _tool_add_echipament(args):
    conn = get_db(); cur = conn.cursor()
    proj = _assistant_find_project(cur, args.get('proiect'))
    if not proj:
        conn.close()
        return {'error': 'Proiectul nu a fost găsit'}
    now = datetime.now().isoformat()
    eid = generate_uuid()
    cur.execute('''INSERT INTO echipamente (id, proiect_id, nume, producator, model, serial_number, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (eid, proj['id'], args.get('nume', ''), args.get('producator', ''),
                 args.get('model', ''), args.get('serial_number', ''), now, now))
    conn.commit(); conn.close()
    return {'ok': True, 'id': eid, 'mesaj': f"Echipament adăugat la {proj['nume']}: {args.get('nume')}"}


@assistant_tool('list_clienti')
def _tool_list_clienti(args):
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT id, nume, telefon, email, contact_principal FROM clienti ORDER BY nume')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {'count': len(rows), 'clienti': rows}


@assistant_tool('create_client')
def _tool_create_client(args):
    conn = get_db(); cur = conn.cursor()
    cid = generate_uuid()
    cur.execute('''INSERT INTO clienti (id, nume, adresa, telefon, email, contact_principal, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, '', ?)''',
                (cid, args.get('nume', ''), args.get('adresa', ''), args.get('telefon', ''),
                 args.get('email', ''), args.get('contact_principal', ''), datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {'ok': True, 'id': cid, 'mesaj': f"Client creat: {args.get('nume')}"}


@assistant_tool('list_global_tasks')
def _tool_list_global_tasks(args):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, titlu, status, prioritate, categorie, data_scadenta "
                "FROM global_tasks WHERE status != 'done' ORDER BY created_at DESC LIMIT 60")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {'count': len(rows), 'taskuri_zilnice': rows}


@assistant_tool('create_global_task')
def _tool_create_global_task(args):
    conn = get_db(); cur = conn.cursor()
    now = datetime.now().isoformat()
    gid = generate_uuid()
    cur.execute('''INSERT INTO global_tasks
        (id, titlu, descriere, prioritate, status, categorie, data_scadenta, data_finalizare, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'to_do', ?, ?, '', ?, ?)''',
        (gid, args.get('titlu', ''), args.get('descriere', ''), args.get('prioritate', 'Normal'),
         args.get('categorie', 'General'), args.get('scadenta', ''), now, now))
    conn.commit(); conn.close()
    return {'ok': True, 'id': gid, 'mesaj': f"Task zilnic creat: {args.get('titlu')}"}


@assistant_tool('save_memory')
def _tool_save_memory(args):
    continut = (args.get('continut') or '').strip()
    if not continut:
        return {'error': 'Conținut gol'}
    conn = get_db(); cur = conn.cursor()
    cur.execute('INSERT INTO assistant_memory (id, continut, created_at) VALUES (?, ?, ?)',
                (generate_uuid(), continut, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {'ok': True, 'mesaj': 'Reținut.'}


@assistant_tool('delete_memory')
def _tool_delete_memory(args):
    # Defence in depth — schema removed; server-side refusal too.
    return {'error': 'Funcția dezactivată din motive de securitate. Șterge intrarea din UI.'}


@assistant_tool('lookup_fault_code')
def _tool_lookup_fault_code(args):
    cod = (args.get('cod') or '').strip()
    if not cod:
        return {'error': 'cod lipsa'}
    prod = (args.get('producator') or '').strip()
    fam = (args.get('familie') or '').strip()
    conn = get_db(); cur = conn.cursor()
    where = ' WHERE (cod = ? COLLATE NOCASE OR cod_secundar = ? COLLATE NOCASE)'
    params = [cod, cod]
    if prod:
        where += ' AND producator = ?'; params.append(prod)
    if fam:
        where += ' AND familie = ?'; params.append(fam)
    cols = ('producator, familie, cod, cod_secundar, tip, nume, '
            'cauza, remediu, reactie, confirmare')
    cur.execute(f'SELECT {cols} FROM {safe_table("fault_codes")}{where} '
                'ORDER BY producator, familie LIMIT 12', params)
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        cur.execute(f'SELECT {cols} FROM fault_codes WHERE cod LIKE ? '
                    'ORDER BY producator, familie LIMIT 12', (f'%{cod}%',))
        rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {'count': len(rows), 'coduri': rows}


def _assistant_exec_tool(name, args):
    """Execute one assistant tool. Returns a JSON-serialisable dict."""
    handler = _ASSISTANT_HANDLERS.get(name)
    if not handler:
        return {'error': f"Tool necunoscut: {name}"}
    try:
        return handler(args)
    except Exception as e:
        logger.exception(f"Assistant tool {name} failed")
        return {'error': str(e)}


@assistant_bp.route('/status', methods=['GET'])
@login_required
def assistant_status():
    return jsonify({'configured': _load_assistant_config() is not None})


@assistant_bp.route('/chat', methods=['POST'])
@login_required
def assistant_chat():
    cfg = _load_assistant_config()
    if not cfg:
        return jsonify({'error': 'Asistentul nu e configurat. Hermes trebuie să creeze .assistant_config pe server.'}), 503

    data = request.json or {}
    history = data.get('messages', [])
    if not isinstance(history, list) or not history:
        return jsonify({'error': 'Niciun mesaj'}), 400

    # Anthropic Messages format: system is a top-level field, not a message.
    # Client history holds plain-text user/assistant turns; cap to last 20.
    convo = []
    for m in history[-20:]:
        if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and m.get('content'):
            convo.append({'role': m['role'], 'content': str(m['content'])})
    if not convo:
        return jsonify({'error': 'Niciun mesaj'}), 400

    system_prompt = _build_assistant_system_prompt()
    tool_log = []
    try:
        for _ in range(8):  # max tool rounds
            resp = _minimax_call(cfg, system_prompt, convo)
            blocks = resp.get('content') or []
            text = '\n'.join(
                b.get('text', '') for b in blocks if isinstance(b, dict) and b.get('type') == 'text'
            ).strip()
            tool_uses = [b for b in blocks if isinstance(b, dict) and b.get('type') == 'tool_use']
            convo.append({'role': 'assistant', 'content': blocks})
            if not tool_uses:
                return jsonify({'reply': text or '(răspuns gol)', 'tool_log': tool_log})
            results = []
            for tu in tool_uses:
                fname = tu.get('name', '')
                fargs = tu.get('input') or {}
                result = _assistant_exec_tool(fname, fargs)
                tool_log.append({'tool': fname, 'args': fargs, 'ok': 'error' not in result})
                results.append({
                    'type': 'tool_result',
                    'tool_use_id': tu.get('id'),
                    'content': json.dumps(result, ensure_ascii=False),
                })
            convo.append({'role': 'user', 'content': results})
        return jsonify({'reply': 'Am atins limita de pași. Reformulează cererea, te rog.', 'tool_log': tool_log})
    except Exception as e:
        logger.error(f'Assistant chat failed: {e}')
        return jsonify({'error': 'Eroare asistent'}), 500
