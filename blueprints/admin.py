# Admin Blueprint
# Statistici, backup/restore al datelor, administrarea fisierului bazei (upload / dump) si
# calendarul. Exportul PDF si cautarea globala au plecat pe 2026-10-03
# (nu le mai chema nimic); starea de dinainte e eticheta git `inainte-de-retragere`.

import os
import shutil
import tempfile
import re
import logging
import sqlite3
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, send_file

from utils import (
    safe_table, login_required, get_json_or_400,
    TASK_PROIECT_VIU,
)
from database import get_db, row_to_dict, DATABASE_PATH

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

# Chei `app_settings` care NU parasesc masina si NU se sterg la restore:
#   push_* — cheia VAPID privata + abonamentele telefoanelor
# Backup-ul se descarca in browser si se plimba pe discuri; astea sunt stare
# per-masina, nu date de proiect. (db-dump ramane baza bruta — asumat.)
# `google_*` a plecat odata cu integrarea (2026-08-10); migrarea v40 sterge
# randurile ramase, tocmai ca sa nu inceapa sa curga in backup dupa relaxarea
# filtrului de aici.
CHEI_PROTEJATE = ('push_',)
CHEI_PROTEJATE_SQL = "key LIKE 'push!_%' ESCAPE '!'"

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@admin_bp.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'pregatire' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'finalizat' THEN 1 ELSE 0 END) as finished
        FROM proiecte
    """)
    row = cursor.fetchone()
    conn.close()
    return jsonify({
        'total': row['total'] or 0,
        'active': row['active'] or 0,
        'finished': row['finished'] or 0
    })


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

# Tabelele din backup, in ordinea in care se pot reinsera: parintii inaintea copiilor (cheile
# straine din `tasks`, `implementari` si `calcule` arata spre `proiecte`, cele din
# `task_dependencies` spre `tasks` si `proiecte`). Backup-ul exporta fiecare tabela cu TOATE
# coloanele ei (`SELECT *`); restaurarea le pune inapoi pe toate.
TABELE_BACKUP = ('proiecte', 'tasks', 'task_subtasks', 'task_dependencies',
                 'implementari', 'calcule', 'global_tasks', 'clienti', 'app_settings')


@admin_bp.route('/api/backup', methods=['GET'])
@login_required
def backup_database():
    conn = get_db()
    cursor = conn.cursor()

    backup = {}

    # sarim tabelele absente
    # ca sa nu pice backup-ul cu 500.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {row[0] for row in cursor.fetchall()}
    for table in TABELE_BACKUP:
        if table not in existing:
            backup[table] = []
            continue
        cursor.execute(f'SELECT * FROM {safe_table(table)}')
        rows = [row_to_dict(row) for row in cursor.fetchall()]
        if table == 'app_settings':
            # Vezi CHEI_PROTEJATE: secretele nu intra in fisierul de backup.
            rows = [r for r in rows if not str(r.get('key', '')).startswith(CHEI_PROTEJATE)]
        backup[table] = rows

    conn.close()

    return jsonify(backup)


# ---- restaurarea: coloanele vin din schema, nu dintr-o lista scrisa in cod ----------------
#
# DE CE. INSERT-urile de mana ale restaurarii enumerau coloanele, iar o coloana adaugata
# dupa ele nu se mai restaura: backup-ul o exporta (`SELECT *`), restore-ul o arunca in
# tacere. Asa s-au pierdut `proiecte.data_finalizare`, `vault_folder` si `notify_on_complete`,
# `global_tasks.ora` si `tasks.data_start` / `progres` / `is_milestone` — auditul din
# 2026-10-03 a facut backup apoi restore si le-a gasit goale. Acum fiecare INSERT ia
# coloanele din `PRAGMA table_info`: ce are si tabela, si randul din fisier, se scrie ca atare
# (inclusiv NULL si ''); ce lipseste din rand (backup mai vechi decat coloana) ramane pe
# valoarea implicita a coloanei; ce are randul si tabela nu mai are (coloane scoase de
# migrari: `prioritate`, `data_planificata`, ...) se ignora. Un test de dus-intors
# (`teste/test_backup_restore.py`) compara toate coloanele tuturor tabelelor, ca o coloana
# viitoare sa nu se mai piarda.

def _reinsereaza(cursor, tabela, randuri, ajusteaza=None):
    """Pune `randuri` (din fisierul de backup) in `tabela`, cu fiecare coloana comuna.

    `ajusteaza(rand)` modifica o COPIE a randului inainte de scriere (reguli de compatibilitate
    cu backup-uri vechi)."""
    nume = safe_table(tabela)
    coloane = [r[1] for r in cursor.execute(f'PRAGMA table_info({nume})')]
    for rand in randuri:
        rand = dict(rand)
        if ajusteaza:
            ajusteaza(rand)
        comune = [c for c in coloane if c in rand]
        cursor.execute(
            'INSERT INTO %s (%s) VALUES (%s)' % (
                nume, ', '.join('"%s"' % c for c in comune), ', '.join('?' * len(comune))),
            [rand[c] for c in comune])


def _termen_din_planificata(rand):
    """Backup-uri dinainte de v33 aveau `data_planificata` pe langa termen; taskul are acum o
    singura data (`data_scadenta`), deci acolo unde termenul lipseste planul devine termen."""
    if not rand.get('data_scadenta') and rand.get('data_planificata'):
        rand['data_scadenta'] = rand['data_planificata']


def _ajusteaza_global(rand):
    _termen_din_planificata(rand)
    rand['sfera'] = rand.get('sfera') or 'munca'


def _ajusteaza_perioada(rand):
    rand['locatie'] = rand.get('locatie') or 'site'
    rand['faza'] = rand.get('faza') or 'implementare'
    rand['confirmata'] = 1 if rand.get('confirmata') else 0


def _ajusteaza_dependenta(rand):
    rand['tip'] = rand.get('tip') or 'FS'


# Tabelele care nu mai exista (jurnal, timer_sessions din v22; checklist_pif, checklist_categorii,
# project_templates, assistant_memory din v23) pot aparea in backup-uri vechi: restore-ul citeste
# doar tabelele din TABELE_BACKUP, deci le ignora.
AJUSTARI_RESTORE = {
    'tasks': _termen_din_planificata,
    'global_tasks': _ajusteaza_global,
    'implementari': _ajusteaza_perioada,
    'task_dependencies': _ajusteaza_dependenta,
}


@admin_bp.route('/api/restore', methods=['POST'])
@login_required
def restore_database():
    data = get_json_or_400()

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Run the whole clear + restore inside ONE transaction, so a bad payload
        # rolls the deletes back instead of leaving the database wiped.
        conn.execute('BEGIN TRANSACTION')
        # Abonamentele push traiesc DOAR pe masina asta (chei `push_*`, excluse
        # din backup). Le citim inainte de stergere si le reinseram la final —
        # altfel orice restore ar rupe in tacere notificarile de pe telefon.
        cursor.execute("SELECT key, value, updated_at FROM app_settings "
                       "WHERE " + CHEI_PROTEJATE_SQL)
        protejate_pastrate = [tuple(r) for r in cursor.fetchall()]
        # Clear existing data (skip tables absent on this deploy)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
        for table in TABELE_BACKUP:
            if table in existing:
                cursor.execute(f'DELETE FROM {safe_table(table)}')

        # Toate tabelele in afara de `app_settings`, parintii inaintea copiilor. Perioadele
        # (`implementari`) lipseau din backup pana in 2026-07-27: un restore le pierdea in tacere.
        # Campurile JSON din `calcule` (v37) se scriu ca text, asa cum stau in tabela.
        for table in TABELE_BACKUP:
            if table != 'app_settings':
                _reinsereaza(cursor, table, data.get(table, []), AJUSTARI_RESTORE.get(table))

        # Restore app_settings (vault Obsidian, cheile de idempotenta debrief).
        # Cheile protejate din FISIER se ignora si ele: backup-ul nu le contine
        # niciodata (filtrate la export), deci un rand `push_*` intr-un fisier
        # de restore e editat de mana — nu acceptam un secret injectat.
        _reinsereaza(cursor, 'app_settings',
                     [s for s in data.get('app_settings', [])
                      if not str(s.get('key', '')).startswith(CHEI_PROTEJATE)])

        # Starea per-masina (push) se pastreaza peste restore (vezi citirea de
        # dinainte de DELETE).
        for key, value, updated_at in protejate_pastrate:
            cursor.execute('INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)',
                           (key, value, updated_at))

        conn.commit()
        conn.close()

        logger.info("Database restored successfully")
        return jsonify({'message': 'Database restored successfully'})
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error restoring database: {e}")
        return jsonify({'error': 'Restaurare esuata — modificarile au fost anulate.'}), 500

# ---------------------------------------------------------------------------
# Admin DB management
# ---------------------------------------------------------------------------

@admin_bp.route('/admin/db-upload', methods=['GET'])
@login_required
def admin_db_upload_page():
    """Minimal HTML form for uploading a local DB file.

    Stilul si scriptul sunt inline, deci poarta nonce-ul cererii (`request._csp_nonce`, pus in
    `before_request` din app.py): politica de continut a serverului nu lasa nimic inline fara el."""
    return '''<!doctype html>
<html><head><meta charset="utf-8"><title>DB upload</title>
<style nonce="__NONCE__">
body{background:#0a0d12;color:#e3e8ef;font-family:system-ui,sans-serif;
     max-width:560px;margin:60px auto;padding:0 24px}
h1{font-size:20px;margin:0 0 16px}
.box{background:#161c26;border:1px solid #232a36;border-radius:10px;padding:24px}
input[type=file]{margin:16px 0;color:#e3e8ef}
button{background:#58d1c9;color:#0a0d12;border:0;padding:10px 18px;
       border-radius:8px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}
.note{color:#9aa4b2;font-size:13px;margin-top:14px}
pre{background:#0a0d12;border:1px solid #232a36;border-radius:6px;
    padding:10px;font-size:12px;overflow:auto;max-height:280px}
.ok{color:#66d19e}.err{color:#f97066}
</style></head>
<body><div class="box">
<h1>Upload DB SQLite</h1>
<form id="f">
<input type="file" name="db" accept=".db" required>
<br><button id="submit" type="submit">Upload (inlocuieste DB serverului)</button>
</form>
<div class="note">DB-ul curent va fi salvat in <code>backups/</code> automat inainte de inlocuire.</div>
<pre id="out"></pre>
</div>
<script nonce="__NONCE__">
const f=document.getElementById('f'),btn=document.getElementById('submit'),out=document.getElementById('out');
f.addEventListener('submit',async e=>{
  e.preventDefault();btn.disabled=true;out.textContent='Uploading...';
  const fd=new FormData(f);
  try{
    const r=await fetch('/api/admin/db-upload',{method:'POST',body:fd});
    const j=await r.json();
    out.textContent=JSON.stringify(j,null,2);
    out.className=r.ok?'ok':'err';
  }catch(err){out.textContent=err.message;out.className='err';}
  btn.disabled=false;
});
</script>
</body></html>'''.replace('__NONCE__', getattr(request, '_csp_nonce', ''))


@admin_bp.route('/api/admin/db-upload', methods=['POST'])
@login_required
def admin_db_upload():
    """Replace the server SQLite DB with an uploaded copy.
    Expects a multipart form field named 'db' with a .db file.
    Validates SQLite header, backs up the existing DB, then atomic-replaces it.
    """
    if 'db' not in request.files:
        return jsonify({'error': "missing form field 'db'"}), 400
    f = request.files['db']
    if not f or f.filename == '':
        return jsonify({'error': 'empty file'}), 400

    dir_name = os.path.dirname(DATABASE_PATH) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='dbupload_', suffix='.db', dir=dir_name)
    os.close(fd)
    try:
        f.save(tmp_path)
        with open(tmp_path, 'rb') as fh:
            magic = fh.read(16)
        if not magic.startswith(b'SQLite format 3'):
            os.unlink(tmp_path)
            return jsonify({'error': 'not a valid SQLite database'}), 400

        # Beyond the magic header: verify the file is a sound SQLite DB and
        # actually looks like a PIF database before replacing the live one.
        try:
            _chk = sqlite3.connect(tmp_path)
            _integrity = _chk.execute('PRAGMA integrity_check').fetchone()
            _has_core = _chk.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='proiecte'"
            ).fetchone()
            _chk.close()
        except (sqlite3.Error, OSError):
            os.unlink(tmp_path)
            return jsonify({'error': 'fisierul nu este o baza SQLite utilizabila'}), 400
        if not _integrity or _integrity[0] != 'ok':
            os.unlink(tmp_path)
            return jsonify({'error': 'baza incarcata a esuat integrity_check'}), 400
        if not _has_core:
            os.unlink(tmp_path)
            return jsonify({'error': 'baza incarcata nu contine structura PIF (tabelul proiecte)'}), 400

        backups_dir = os.path.join(dir_name, 'backups')
        os.makedirs(backups_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backups_dir, f'pif_dashboard_pre_upload_{stamp}.db')
        if os.path.exists(DATABASE_PATH):
            shutil.copy2(DATABASE_PATH, backup_path)

        # Checkpoint WAL into the main DB file so the *-wal/*-shm files are
        # truncated. Without this, the OLD WAL can persist after replace and
        # corrupt reads against the NEW DB.
        try:
            from database import close_db
            conn = get_db()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            close_db(None)
        except Exception as e:
            logger.warning(f"WAL checkpoint before db replace failed: {e}")

        os.replace(tmp_path, DATABASE_PATH)

        return jsonify({
            'status': 'ok',
            'backup': backup_path,
            'replaced': DATABASE_PATH,
            'size': os.path.getsize(DATABASE_PATH),
        })
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.error(f"db-upload failed: {e}")
        return jsonify({'error': 'Incarcarea bazei a esuat.'}), 500


@admin_bp.route('/api/admin/db-dump', methods=['GET'])
@login_required
def admin_db_dump():
    """Stream o copie consistenta a DB-ului SQLite pentru audit local.
    Foloseste sqlite3 backup API ca sa nu blocheze scrieri concurente.
    """
    import sqlite3 as _sql3
    from flask import after_this_request

    if not os.path.exists(DATABASE_PATH):
        return jsonify({'error': 'DB not found on server'}), 404

    # Hot backup la un fisier temporar (safe vs WAL)
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    src = _sql3.connect(DATABASE_PATH)
    dst = _sql3.connect(tmp.name)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    # Schedule cleanup of the temp file once the response is sent -- without
    # this the temp dir slowly fills up (~40 MB per download).
    @after_this_request
    def _cleanup(response):
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        return response

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f'pif_dashboard_{timestamp}.db',
        mimetype='application/octet-stream',
    )


@admin_bp.route('/api/calendar', methods=['GET'])
@login_required
def calendar_view():
    """Calendarul personal: unde esti in fiecare zi.

    Ion e o singura persoana, iar planificarea lui reala sunt PERIOADELE de
    implementare, fiecare cu faza ei (pregatire / implementare in site).
    Deci intrebarea la care raspunde ecranul asta e „unde sunt marti", si tot
    aici stau si deciziile — nu intr-o lista separata.

    `necesita_decizie` = perioada s-a terminat, dar proiectul n-a fost mutat.
    Ori s-a facut si trebuie inchis, ori a alunecat si trebuie replanificat.

    `neplanificate` = proiecte active fara nicio perioada viitoare. Ele stau in
    banda laterala, de unde se trag pe o zi ca sa devina perioade.
    """
    start = (request.args.get('start') or '').strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', start):
        start = datetime.now().date().replace(day=1).isoformat()
    try:
        zile = int(request.args.get('zile') or 42)
    except (TypeError, ValueError):
        zile = 42
    zile = max(7, min(zile, 200))
    start_d = datetime.strptime(start, '%Y-%m-%d').date()
    end_s = (start_d + timedelta(days=zile)).isoformat()

    conn = get_db()
    cursor = conn.cursor()

    # O perioada intra in fereastra daca se intersecteaza cu ea, nu doar daca
    # incepe in ea — altfel un bloc de 4 zile care trece peste 1 ale lunii dispare.
    # Proiect FINALIZAT inainte de vreme: zilele ramase nu mai au ce cauta in
    # calendar — nu vei fi acolo. Dar trecutul ramane: chiar ai fost. Deci pentru
    # proiectele inchise taiem perioada la ZIUA DE AZI si excludem complet ce
    # incepe dupa. (Ion: „daca am finalizat un proiect inainte de vreme nu se
    # scoate din calendar".)
    cursor.execute("""
        SELECT i.id, i.data_start,
               CASE WHEN p.status = 'finalizat'
                     AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) > date(COALESCE(NULLIF(p.data_finalizare, ''), date('now')))
                    THEN date(COALESCE(NULLIF(p.data_finalizare, ''), date('now')))
                    ELSE i.data_sfarsit END AS data_sfarsit,
               i.eticheta, i.locatie, i.faza, COALESCE(i.confirmata, 0) AS confirmata,
               p.id AS proiect_id, p.nume, p.client, p.locatie AS locatie_proiect,
               p.status, p.tip,
               (SELECT COUNT(*) FROM tasks t
                 WHERE t.proiect_id = p.id AND t.status != 'done') AS taskuri_deschise,
               (CASE WHEN p.status != 'finalizat'
                      AND COALESCE(i.confirmata, 0) = 0
                      AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) < date('now')
                     THEN 1 ELSE 0 END) AS necesita_decizie
        FROM implementari i JOIN proiecte p ON p.id = i.proiect_id
        WHERE (p.status != 'finalizat' OR date(i.data_start) <= date(COALESCE(NULLIF(p.data_finalizare, ''), date('now'))))
          AND date(i.data_start) < date(?)
          AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date(?)
        ORDER BY i.data_start, p.client, p.nume
    """, (end_s, start))
    perioade = [dict(r) for r in cursor.fetchall()]

    # Tot ce cere o decizie, chiar daca a ramas in urma ferestrei afisate —
    # altfel navighezi pe luna viitoare si semnalul dispare. Aceeasi conditie ca
    # `necesita_decizie` de mai sus: perioadele bifate au primit raspuns si nu
    # mai intreaba (v39).
    cursor.execute("""
        SELECT i.id, i.data_start, i.data_sfarsit, i.eticheta, i.locatie, i.faza,
               p.id AS proiect_id, p.nume, p.client, p.status
        FROM implementari i JOIN proiecte p ON p.id = i.proiect_id
        WHERE p.status NOT IN ('finalizat', 'anulat')
          AND COALESCE(i.confirmata, 0) = 0
          AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) < date('now')
        ORDER BY i.data_start
    """)
    de_decis = [dict(r) for r in cursor.fetchall()]

    # „DE PLANIFICAT" INSEAMNA ACUM: N-A AVUT NICIODATA O PERIOADA.
    #
    # Conditia era „nicio zi DE AZI INAINTE", deci un proiect caruia i s-a facut
    # deplasarea si care a ramas deschis — pentru PV-uri, pentru o vizita nedatata
    # — se intorcea in sertar a doua zi dupa ce ai fost acolo. Sertarul se umplea
    # cu lucruri care nu mai asteptau nimic, iar cele care chiar n-au fost
    # planificate niciodata se pierdeau printre ele.
    #
    # Ion, 2026-08-27: „proiectele care au avut o perioada de implementare
    # efectuata sa nu mai apara ca proiecte de planificat, doar cele care nu au
    # avut deloc. Chiar daca s-a implementat o perioada si nu s-a inchis
    # proiectul, voi mai adauga manual daca va trebui."
    #
    # Deci sertarul e o COADA DE INTRARE, nu o lista de restante: un proiect intra
    # in el o singura data, si iese definitiv cand primeste prima zi. A doua
    # deplasare se adauga din pagina proiectului sau tragand pe o zi — nu prin
    # reaparitia lui aici.
    cursor.execute("""
        SELECT id AS proiect_id, nume, client, status, tip
        FROM proiecte p
        WHERE p.status NOT IN ('finalizat', 'anulat')
          AND NOT EXISTS (SELECT 1 FROM implementari i WHERE i.proiect_id = p.id)
        ORDER BY p.status DESC, p.nume
    """)
    neplanificate = [dict(r) for r in cursor.fetchall()]

    # ZIUA E INTREAGA: UNDE ESTI **SI** CE AI DE FACUT.
    #
    # Pana acum calendarul stia doar perioade, iar taskurile stateau in
    # Planificator. Rezultatul se putea citi pe 25 august 2026: panoul zilei
    # scria „Liber." — corect despre perioade — in timp ce trei taskuri erau
    # scadente chiar atunci. Doua pagini, doua jumatati de adevar despre aceeasi
    # zi. Cu Planificatorul scos, jumatatea cu taskuri n-ar mai fi avut unde sa
    # stea, deci vine aici.
    #
    # CONDITIILE SUNT CELE DE PE BOARDUL „ASTĂZI", CUVANT CU CUVANT — din proiectele
    # inchise doar ce s-a adaugat dupa inchidere (`TASK_PROIECT_VIU`, utils.py),
    # task nefinalizat, fara ocurentele viitoare ale unei recurente, iar globalele
    # doar `sfera = 'munca'`. Au venit din `/api/plan`, scos pe 2026-08-26: aceeasi
    # intrebare nu poate avea doua raspunsuri pe doua rute care hranesc acelasi
    # ecran, altfel „ce am de facut" isi schimba tacit inţelesul.
    #
    # Se intorc taskurile din TOATA fereastra, nu doar din ziua selectata: panoul
    # isi alege ziua fara sa mai ceara nimic, iar fereastra e de 49 de zile cu
    # cateva zeci de randuri in ea.
    cursor.execute("""
        SELECT t.id, 'proiect' AS tip, t.titlu, t.status, t.data_scadenta,
               COALESCE(t.recurenta, '') AS recurenta, '' AS categorie,
               p.id AS proiect_id, p.nume AS proiect_nume
        FROM tasks t JOIN proiecte p ON p.id = t.proiect_id
        WHERE """ + TASK_PROIECT_VIU + """
          AND t.status != 'done'
          AND t.data_scadenta IS NOT NULL AND TRIM(t.data_scadenta) <> ''
          AND date(t.data_scadenta) >= date(?) AND date(t.data_scadenta) < date(?)
          AND NOT (t.recurenta IS NOT NULL AND TRIM(t.recurenta) <> ''
                   AND date(t.data_scadenta) > date('now'))
        ORDER BY t.data_scadenta, t.titlu
    """, (start, end_s))
    taskuri = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT g.id, 'global' AS tip, g.titlu, g.status, g.data_scadenta,
               COALESCE(g.recurenta, '') AS recurenta,
               COALESCE(g.categorie, '') AS categorie,
               NULL AS proiect_id, NULL AS proiect_nume
        FROM global_tasks g
        WHERE g.sfera = 'munca'
          AND g.status != 'done'
          AND g.data_scadenta IS NOT NULL AND TRIM(g.data_scadenta) <> ''
          AND date(g.data_scadenta) >= date(?) AND date(g.data_scadenta) < date(?)
          AND NOT (g.recurenta IS NOT NULL AND TRIM(g.recurenta) <> ''
                   AND date(g.data_scadenta) > date('now'))
        ORDER BY g.data_scadenta, g.titlu
    """, (start, end_s))
    taskuri += [dict(r) for r in cursor.fetchall()]
    taskuri.sort(key=lambda t: ((t['data_scadenta'] or '')[:10], (t['titlu'] or '').lower()))

    # Nimic nu dispare in tacere. O data pe care SQLite nu o poate interpreta
    # (`date()` intoarce NULL) nu se aseaza pe nicio zi, deci randul lipseste din
    # calendar FARA niciun semn — asa a stat `23.02.2026` nevazut pe un proiect.
    # De la v29 intrarea e pazita de utils.norm_date(), dar o restaurare dintr-un
    # backup vechi sau o scriere directa in baza pot reintroduce asa ceva.
    probleme = []
    cursor.execute("""
        SELECT p.id AS proiect_id, p.nume, 'perioada' AS unde,
               CASE WHEN date(i.data_start) IS NULL THEN 'inceput' ELSE 'sfarsit' END AS camp,
               CASE WHEN date(i.data_start) IS NULL THEN i.data_start ELSE i.data_sfarsit END AS valoare
        FROM implementari i JOIN proiecte p ON p.id = i.proiect_id
        WHERE p.status != 'anulat'
          AND (date(i.data_start) IS NULL
               OR (TRIM(COALESCE(i.data_sfarsit, '')) <> '' AND date(i.data_sfarsit) IS NULL))
    """)
    probleme += [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT p.id AS proiect_id, p.nume, 'task' AS unde, 'termen' AS camp,
               t.data_scadenta AS valoare
        FROM tasks t JOIN proiecte p ON p.id = t.proiect_id
        WHERE t.status != 'done'
          AND t.data_scadenta IS NOT NULL AND TRIM(t.data_scadenta) <> ''
          AND date(t.data_scadenta) IS NULL
    """)
    probleme += [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify({
        'start': start,
        'zile': zile,
        'today': datetime.now().date().isoformat(),
        'perioade': perioade,
        'taskuri': taskuri,
        'de_decis': de_decis,
        'neplanificate': neplanificate,
        'probleme': probleme,
    })
