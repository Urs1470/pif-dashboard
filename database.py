import sqlite3
import os
import logging

logger = logging.getLogger('pif_dashboard')

# PIF_DB_PATH permite rularea pe o baza de unica folosinta (vezi scripts/smoke_ui.py,
# care porneste aplicatia pe o copie ca sa nu atinga baza de lucru). Neselectat =
# baza normala, langa cod.
DATABASE_PATH = os.environ.get('PIF_DB_PATH') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'pif_dashboard.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.row_factory = sqlite3.Row
    # Track the connection on the Flask request context so close_db can close
    # any that a handler forgot to close. Explicit conn.close() in handlers
    # still works — closing an already-closed connection is a harmless no-op.
    try:
        from flask import g, has_app_context
        if has_app_context():
            conns = getattr(g, '_db_conns', None)
            if conns is None:
                conns = []
                g._db_conns = conns
            conns.append(conn)
    except Exception:
        pass
    return conn

def close_db(exc=None):
    """Teardown safety net — close any request connections left open."""
    try:
        from flask import g
        conns = getattr(g, '_db_conns', None)
        if conns:
            for c in conns:
                try:
                    c.close()
                except Exception:
                    pass
            g._db_conns = []
    except Exception:
        pass

# ============ PHASE 2c: DATABASE MIGRATIONS ============
# Schema version history:
# v1: Initial schema (proiecte, tasks, checklist_pif, jurnal, timer_sessions, atasamente, global_tasks)
# v5: Added checklist_categorii table (per-project dynamic categories for checklist_pif)
#     + nullable categorie_id column on checklist_pif
# v2: Added clienti, echipamente, project_templates tables
# v3: Added ordine to tasks, notify_on_complete/deadline to proiecte
# v4: Added budget_state, budget_audit tables for Budget Tracker
# v10: Added fault_codes table (drive fault/alarm/warning codes from manuals)
# v11: Added global_task_sessions table (timer for daily/global tasks)
# v12: Dropped redundant indexes + orphan tables (audit_log, parametri_std),
#      added prune_budget_audit trigger (cap 5000 rows/user)
# v20: Dropped Budget Tracker tables (budget_state, budget_audit)
# v21: Added data_planificata + ordine_agenda to tasks & global_tasks
#      (Home "Astazi" daily planner board)
# v22: Dropped timer & jurnal features (jurnal, timer_sessions,
#      global_task_sessions) — orele se ponteaza in e100, jurnalul in observatii
# v28: Dropped parametri_master, fault_codes, echipamente, atasamente —
#      restrangere de scop la organizare/monitorizare de proiecte. Parametrii si
#      fault-urile se iau din manual (trasabilitate la sursa), backup-urile de
#      drive stau brute in vault unde le citeste skill-ul drive-backup.

# v29: datele calendaristice sunt normalizate la ISO, iar intrarea e pazita de
#      utils.norm_date() — nu mai stocam o data pe care nu o putem citi.
SCHEMA_VERSION = 29

def get_schema_version():
    """Get current schema version from schema_version table"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        version = row['version'] if row else 1
    except Exception:
        version = 1
    conn.close()
    return version

def set_schema_version(version):
    """Set schema version in schema_version table"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM schema_version')
    cursor.execute('INSERT INTO schema_version (version) VALUES (?)', (version,))
    conn.commit()
    conn.close()

def migrate_v1_to_v2():
    """Migration from v1 to v2: Add clienti, echipamente, project_templates tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Clienti table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clienti (
            id TEXT PRIMARY KEY,
            nume TEXT NOT NULL,
            adresa TEXT,
            telefon TEXT,
            email TEXT,
            contact_principal TEXT,
            note TEXT,
            created_at TEXT
        )
    ''')
    
    # Echipamente table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS echipamente (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            nume TEXT NOT NULL,
            producator TEXT,
            model TEXT,
            serial_number TEXT,
            params_json TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
        )
    ''')
    
    # Project templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tip TEXT DEFAULT 'PIF',
            default_checklist_json TEXT,
            default_tasks_json TEXT,
            created_at TEXT
        )
    ''')
    
    # Add tip_atasament column to atasamente if not exists
    try:
        cursor.execute("ALTER TABLE atasamente ADD COLUMN tip_atasament TEXT DEFAULT 'fisier'")
    except Exception:
        pass
    
    # Performance indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_status ON proiecte(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_producator ON proiecte(producator)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_tip ON proiecte(tip)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_proiect_id ON tasks(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_global_tasks_status ON global_tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_proiect ON tasks(proiect_id)')
    # jurnal / timer_sessions nu mai exista pe DB-uri noi (v22) — indexam doar daca tabelele exista
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('jurnal', 'timer_sessions')")
    legacy = {row[0] for row in cursor.fetchall()}
    if 'jurnal' in legacy:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jurnal_proiect ON jurnal(proiect_id)')
    if 'timer_sessions' in legacy:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timer_proiect ON timer_sessions(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_atasamente_proiect ON atasamente(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_echipamente_proiect ON echipamente(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_clienti_nume ON clienti(nume)')
    
    conn.commit()
    conn.close()
    logger.info("Migration v1->v2 completed: Added clienti, echipamente, project_templates tables")

def migrate_v2_to_v3():
    """Migration from v2 to v3: Add ordine to tasks, notify_on_complete/deadline to proiecte"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Add ordine column to tasks table if not exists
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN ordine INTEGER DEFAULT 0")
    except Exception:
        pass
    
    # Add notify_on_complete to proiecte if not exists
    try:
        cursor.execute("ALTER TABLE proiecte ADD COLUMN notify_on_complete INTEGER DEFAULT 1")
    except Exception:
        pass
    
    # Add notify_on_deadline to proiecte if not exists
    try:
        cursor.execute("ALTER TABLE proiecte ADD COLUMN notify_on_deadline INTEGER DEFAULT 1")
    except Exception:
        pass
    
    conn.commit()
    conn.close()
    logger.info("Migration v2->v3 completed: Added ordine to tasks, notify_on_complete/deadline to proiecte")

def migrate_v3_to_v4():
    """Migration from v3 to v4: Add budget_state, budget_audit tables for Budget Tracker"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_state (
            user TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            user TEXT NOT NULL,
            action TEXT NOT NULL,
            field TEXT,
            old_value TEXT,
            new_value TEXT
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_budget_audit_user_ts ON budget_audit(user, ts DESC)')

    conn.commit()
    conn.close()
    logger.info("Migration v3->v4 completed: Added budget_state, budget_audit tables")

def migrate_v4_to_v5():
    """v4 -> v5: per-project dynamic checklist categories.

    Adds a new table `checklist_categorii(id, proiect_id, nume, ordine, created_at)`
    and a nullable `categorie_id` column on the existing `checklist_pif` table.
    Legacy items keep categorie_id = NULL and surface in a virtual "Fara categorie"
    bucket on the client. Migration is idempotent — running it twice is a no-op.
    """
    conn = get_db()
    cursor = conn.cursor()

    # checklist_pif a fost sters (v23) — pe un DB nou tabela nu mai exista,
    # deci nu e nimic de migrat. v23 oricum face DROP dupa lantul de migratii.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checklist_pif'")
    if cursor.fetchone() is None:
        conn.close()
        return

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist_categorii (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proiect_id TEXT NOT NULL,
            nume TEXT NOT NULL,
            ordine INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')

    # Add nullable FK column on checklist_pif if it does not exist already.
    cursor.execute("PRAGMA table_info(checklist_pif)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'categorie_id' not in cols:
        cursor.execute("ALTER TABLE checklist_pif ADD COLUMN categorie_id INTEGER")

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_checklist_categorii_proiect ON checklist_categorii(proiect_id, ordine)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_checklist_pif_categorie ON checklist_pif(categorie_id)')

    conn.commit()
    conn.close()
    logger.info("Migration v4->v5 completed: Added checklist_categorii + categorie_id column")


def migrate_v5_to_v6():
    """Remove unused `interconexiuni` column from parametri_master.
    Requires SQLite 3.35+ (March 2021) for ALTER TABLE DROP COLUMN.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parametri_master'")
    if not cursor.fetchone():
        logger.info("Migration v5->v6: parametri_master does not exist yet, skipping")
        conn.close()
        return
    cursor.execute("PRAGMA table_info(parametri_master)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'interconexiuni' in cols:
        cursor.execute('ALTER TABLE parametri_master DROP COLUMN interconexiuni')
        conn.commit()
        logger.info("Migration v5->v6: dropped parametri_master.interconexiuni")
    else:
        logger.info("Migration v5->v6: interconexiuni already absent")
    conn.close()


def migrate_v6_to_v7():
    """Add `pdf_extra` JSON column to parametri_master for value enums,
    notes, dependencies, examples, formulae extracted from PDF manuals.
    Format: see HERMES.md / audit_pdf.py for schema."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parametri_master'")
    if not cursor.fetchone():
        logger.info("Migration v6->v7: parametri_master does not exist yet, skipping")
        conn.close()
        return
    cursor.execute("PRAGMA table_info(parametri_master)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'pdf_extra' not in cols:
        cursor.execute('ALTER TABLE parametri_master ADD COLUMN pdf_extra TEXT')
        conn.commit()
        logger.info("Migration v6->v7: added parametri_master.pdf_extra")
    else:
        logger.info("Migration v6->v7: pdf_extra already present")
    conn.close()


def migrate_v7_to_v8():
    """v7 -> v8: elaborate project tasks.
      - tasks: + descriere, + recurenta, + updated_at
      - timer_sessions: + task_id (per-task time tracking)
      - new table task_subtasks (lightweight checklist items under a task)
    Idempotent — column existence checked, CREATE IF NOT EXISTS."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(tasks)")
    tcols = {row[1] for row in cursor.fetchall()}
    if 'descriere' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN descriere TEXT')
    if 'recurenta' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN recurenta TEXT')
    if 'updated_at' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN updated_at TEXT')

    # timer_sessions e istoric (drop in v22) — altereaza doar daca mai exista
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timer_sessions'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(timer_sessions)")
        scols = {row[1] for row in cursor.fetchall()}
        if 'task_id' not in scols:
            cursor.execute('ALTER TABLE timer_sessions ADD COLUMN task_id TEXT')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_subtasks (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            titlu TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            ordine INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_subtasks_task ON task_subtasks(task_id, ordine)')

    conn.commit()
    conn.close()
    logger.info("Migration v7->v8: elaborate tasks (descriere, recurenta, subtasks, per-task timer)")


def migrate_v8_to_v9():
    """v8 -> v9: recurrence on daily (global) tasks. Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(global_tasks)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'recurenta' not in cols:
        cursor.execute('ALTER TABLE global_tasks ADD COLUMN recurenta TEXT')
        conn.commit()
        logger.info("Migration v8->v9: added global_tasks.recurenta")
    else:
        logger.info("Migration v8->v9: global_tasks.recurenta already present")
    conn.close()


def migrate_v9_to_v10():
    """v9 -> v10: drive fault / alarm / warning codes extracted from the
    manufacturer manuals. Sibling dataset to parametri_master. Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fault_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producator TEXT NOT NULL,
            familie TEXT NOT NULL,
            cod TEXT NOT NULL,
            cod_secundar TEXT,
            tip TEXT,
            nume TEXT,
            cauza TEXT,
            remediu TEXT,
            reactie TEXT,
            confirmare TEXT,
            extra_json TEXT,
            pagina INTEGER,
            sursa TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fault_codes_fam ON fault_codes(producator, familie)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fault_codes_cod ON fault_codes(cod)')
    conn.commit()
    conn.close()
    logger.info("Migration v9->v10: added fault_codes table")


def migrate_v10_to_v11():
    """v10 -> v11: time tracking for daily (global) tasks. A separate table so
    timer_sessions (proiect_id NOT NULL, FK to proiecte) stays untouched.
    Manual time entries land here too, with stop_time set up-front. Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_task_sessions (
            id TEXT PRIMARY KEY,
            global_task_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            stop_time TEXT,
            durata_secunde INTEGER,
            FOREIGN KEY (global_task_id) REFERENCES global_tasks(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_gts_task ON global_task_sessions(global_task_id)')
    conn.commit()
    conn.close()
    logger.info("Migration v10->v11: added global_task_sessions table")


def migrate_v11_to_v12():
    """v11 -> v12: housekeeping.
      - Drop redundant indexes (idx_parametri_master_familie, idx_parametri_master_parametru,
        idx_tasks_proiect, idx_budget_audit_user) — equivalents already exist
        (idx_param_familie, idx_param_cod, idx_tasks_proiect_id, idx_budget_audit_user_ts).
      - Drop orphan tables (audit_log, parametri_std) — superseded by budget_audit
        and parametri_master respectively.
      - Add prune_budget_audit trigger to cap budget_audit at 5000 most-recent
        entries per user (prevents unbounded growth).

    NOTE: task_subtasks.task_id has no FK constraint. Adding one requires
    table recreation in SQLite. Application code must DELETE orphan rows
    when deleting tasks (see delete_global_task fix in app.py).
    Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('DROP INDEX IF EXISTS idx_parametri_master_familie')
    cursor.execute('DROP INDEX IF EXISTS idx_parametri_master_parametru')
    cursor.execute('DROP INDEX IF EXISTS idx_tasks_proiect')
    cursor.execute('DROP INDEX IF EXISTS idx_budget_audit_user')
    cursor.execute('DROP TABLE IF EXISTS audit_log')
    cursor.execute('DROP TABLE IF EXISTS parametri_std')

    # Ensure task_subtasks has an index on task_id (orphans must be cleaned by app code).
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_subtasks_task_id ON task_subtasks(task_id)')

    # Cap budget_audit at 5000 most-recent rows per user.
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS prune_budget_audit
        AFTER INSERT ON budget_audit
        BEGIN
          DELETE FROM budget_audit WHERE id IN (
            SELECT id FROM budget_audit
            WHERE user = NEW.user
            ORDER BY id ASC
            LIMIT MAX(0, (SELECT COUNT(*) FROM budget_audit WHERE user = NEW.user) - 5000)
          );
        END;
    ''')

    conn.commit()
    conn.close()
    logger.info("Migration v11->v12: dropped redundant indexes/orphan tables, added prune_budget_audit trigger")


def migrate_v12_to_v13():
    """v12 -> v13: clean ABB parameter descriptions.
    349 params had "(Only visible when ...)" or "(Visible when ...)" prefixes
    baked into `descriere` from ABB manual parsing. Extract these into a new
    `conditie_vizibilitate` column and strip them from the description.
    Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parametri_master'")
    if not cursor.fetchone():
        conn.close()
        logger.info("Migration v12->v13: parametri_master does not exist yet, skipping")
        return

    # Add column if missing
    cursor.execute("PRAGMA table_info(parametri_master)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'conditie_vizibilitate' not in cols:
        cursor.execute('ALTER TABLE parametri_master ADD COLUMN conditie_vizibilitate TEXT')

    # Extract "(Only visible ...)" / "(Visible when ...)" from descriere
    # Also strip residual punctuation (e.g. ". Temperature..." -> "Temperature...")
    import re
    pattern = re.compile(r'^\s*\((?:Only )?[Vv]isible\b[^)]*\)[\s.,;:]*')
    cursor.execute("SELECT id, descriere FROM parametri_master WHERE descriere LIKE '%(Only visible%' OR descriere LIKE '%(Visible when%'")
    rows = cursor.fetchall()
    updated = 0
    for row_id, desc in rows:
        m = pattern.match(desc or '')
        if m:
            condition = m.group(0).strip().strip('()')
            clean_desc = desc[m.end():].strip()
            # Capitalize first letter of cleaned description
            if clean_desc and clean_desc[0].islower():
                clean_desc = clean_desc[0].upper() + clean_desc[1:]
            cursor.execute('UPDATE parametri_master SET descriere = ?, conditie_vizibilitate = ? WHERE id = ?',
                           (clean_desc, condition, row_id))
            updated += 1

    conn.commit()
    conn.close()
    logger.info(f"Migration v12->v13: added conditie_vizibilitate, cleaned {updated} param descriptions")


def migrate_v13_to_v14():
    """v13 -> v14: add FOREIGN KEY + ON DELETE CASCADE to task_subtasks.task_id.
    SQLite requires table recreation. Idempotent — skips if FK already exists."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_subtasks'")
    if not cursor.fetchone():
        conn.close()
        return

    cursor.execute("PRAGMA foreign_key_list(task_subtasks)")
    if cursor.fetchone():
        conn.close()
        return

    cursor.execute("BEGIN")
    cursor.execute('''
        CREATE TABLE task_subtasks_new (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            titlu TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            ordine INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("INSERT INTO task_subtasks_new SELECT id, task_id, titlu, done, ordine, created_at FROM task_subtasks")
    cursor.execute("DROP TABLE task_subtasks")
    cursor.execute("ALTER TABLE task_subtasks_new RENAME TO task_subtasks")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_subtasks_task_id ON task_subtasks(task_id)")
    cursor.execute("COMMIT")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()
    logger.info("Migration v13->v14: added FK constraint on task_subtasks.task_id")


def migrate_v14_to_v15():
    """v14 -> v15: add enum_labels column to parametri_master.

    Stores JSON blob with value→label mapping extracted from drive backups.
    Example: {"0": "Off", "1": "On", "2": "Above limit"}
    Idempotent — skips if column already exists.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parametri_master'")
    if not cursor.fetchone():
        logger.info("Migration v14->v15: parametri_master does not exist yet, skipping")
        conn.close()
        return
    cursor.execute("PRAGMA table_info(parametri_master)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'enum_labels' not in cols:
        cursor.execute('ALTER TABLE parametri_master ADD COLUMN enum_labels TEXT')
        conn.commit()
        logger.info("Migration v14->v15: added enum_labels column to parametri_master")
    conn.close()


def migrate_v15_to_v16():
    """v15 -> v16: add descrieri_json column to echipamente.

    Stores {parametru_code: description} extracted from drive backups/parser.
    Used to display parameter descriptions even when parametri_master doesn't
    have them — the backup XML often includes names that the DB lacks.
    Idempotent — skips if column already exists.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(echipamente)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'descrieri_json' not in cols:
        cursor.execute('ALTER TABLE echipamente ADD COLUMN descrieri_json TEXT')
        conn.commit()
        logger.info("Migration v15->v16: added descrieri_json column to echipamente")
    conn.close()


def migrate_v16_to_v17():
    """v16 -> v17: add performance indexes on timer_sessions for task_id and
    subtask_id columns. These are hit by the project-task list query and
    subtask timer lookups. Idempotent (CREATE INDEX IF NOT EXISTS)."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    # timer_sessions e istoric (drop in v22) — indexeaza doar daca mai exista
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timer_sessions'")
    if cursor.fetchone():
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timer_sessions_task_id ON timer_sessions(task_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timer_sessions_subtask_id ON timer_sessions(subtask_id)')
    conn.commit()
    conn.close()
    logger.info("Migration v16->v17: added timer_sessions indexes on task_id, subtask_id")


def migrate_v17_to_v18():
    """v17 -> v18: per-task attachments. Rebuild atasamente with nullable
    proiect_id plus task_id / global_task_id columns (FK CASCADE). Table
    rebuild is required because SQLite cannot drop NOT NULL on proiect_id."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(atasamente)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'task_id' not in cols:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute('''
            CREATE TABLE atasamente_new (
                id TEXT PRIMARY KEY,
                proiect_id TEXT,
                task_id TEXT,
                global_task_id TEXT,
                nume_fisier TEXT NOT NULL,
                tip_fisier TEXT,
                dimensiune INTEGER,
                data TEXT,
                cale_locala TEXT NOT NULL,
                tip_atasament TEXT DEFAULT 'fisier',
                FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (global_task_id) REFERENCES global_tasks(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            INSERT INTO atasamente_new (id, proiect_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala, tip_atasament)
            SELECT id, proiect_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala, tip_atasament FROM atasamente
        ''')
        cursor.execute('DROP TABLE atasamente')
        cursor.execute('ALTER TABLE atasamente_new RENAME TO atasamente')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_atasamente_proiect ON atasamente(proiect_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_atasamente_task ON atasamente(task_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_atasamente_global_task ON atasamente(global_task_id)')
        conn.commit()
        logger.info("Migration v17->v18: atasamente rebuilt with task_id/global_task_id, proiect_id nullable")
    conn.close()


def migrate_v18_to_v19():
    """v18 -> v19: drop the FK on task_subtasks.task_id. task_subtasks is shared
    by BOTH project tasks (tasks.id) and global tasks (global_tasks.id), so the FK
    to tasks(id) added in v14 wrongly rejects global-task subtasks (500 on insert).
    Orphan cleanup on task delete is handled in app code (delete_task /
    delete_global_task). Idempotent — skips if the table already has no FK."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_subtasks'")
    if not cursor.fetchone():
        conn.close()
        return

    cursor.execute("PRAGMA foreign_key_list(task_subtasks)")
    if not cursor.fetchone():
        conn.close()
        return  # no FK — nothing to do

    cursor.execute("BEGIN")
    cursor.execute('''
        CREATE TABLE task_subtasks_new (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            titlu TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            ordine INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    cursor.execute("INSERT INTO task_subtasks_new SELECT id, task_id, titlu, done, ordine, created_at FROM task_subtasks")
    cursor.execute("DROP TABLE task_subtasks")
    cursor.execute("ALTER TABLE task_subtasks_new RENAME TO task_subtasks")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_subtasks_task ON task_subtasks(task_id, ordine)")
    cursor.execute("COMMIT")
    conn.close()
    logger.info("Migration v18->v19: removed FK on task_subtasks.task_id (shared project+global tasks)")


def migrate_v19_to_v20():
    """v19 -> v20: permanently remove the Budget Tracker feature. Drops the
    prune_budget_audit trigger, the idx_budget_audit_user_ts index, and the
    budget_audit / budget_state tables (created in v4/v12). Idempotent —
    DROP ... IF EXISTS, so it's a no-op once the objects are gone."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TRIGGER IF EXISTS prune_budget_audit")
    cursor.execute("DROP INDEX IF EXISTS idx_budget_audit_user_ts")
    cursor.execute("DROP INDEX IF EXISTS idx_budget_audit_user")
    cursor.execute("DROP TABLE IF EXISTS budget_audit")
    cursor.execute("DROP TABLE IF EXISTS budget_state")
    conn.commit()
    conn.close()
    logger.info("Migration v19->v20: dropped Budget Tracker tables (budget_state, budget_audit)")


def migrate_v20_to_v21():
    """v20 -> v21: daily planner ("Astazi" board on Home). Adds a planned-date
    column (data_planificata) INDEPENDENT of the deadline (data_scadenta), plus a
    board-only ordering column (ordine_agenda), on both project tasks (tasks) and
    daily/global tasks (global_tasks). Planning never touches data_scadenta.
    Idempotent — each ALTER is guarded by PRAGMA table_info."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tasks)")
    tcols = {row[1] for row in cursor.fetchall()}
    if 'data_planificata' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN data_planificata TEXT')
    if 'ordine_agenda' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN ordine_agenda INTEGER DEFAULT 0')
    cursor.execute("PRAGMA table_info(global_tasks)")
    gcols = {row[1] for row in cursor.fetchall()}
    if 'data_planificata' not in gcols:
        cursor.execute('ALTER TABLE global_tasks ADD COLUMN data_planificata TEXT')
    if 'ordine_agenda' not in gcols:
        cursor.execute('ALTER TABLE global_tasks ADD COLUMN ordine_agenda INTEGER DEFAULT 0')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_planificata ON tasks(data_planificata) WHERE data_planificata IS NOT NULL AND data_planificata != ''")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_global_tasks_planificata ON global_tasks(data_planificata) WHERE data_planificata IS NOT NULL AND data_planificata != ''")
    conn.commit()
    conn.close()
    logger.info("Migration v20->v21: added data_planificata + ordine_agenda to tasks & global_tasks")


def migrate_v21_to_v22():
    """v21 -> v22: permanently remove the timer & jurnal features. Orele se
    ponteaza in e100 (softul intern de pontaj), iar intrarile de jurnal se scriu
    in observatiile proiectului. Drops jurnal, timer_sessions,
    global_task_sessions and their indexes. Idempotent — DROP ... IF EXISTS."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    for idx in ('idx_jurnal_proiect', 'idx_timer_proiect', 'idx_timer_task',
                'idx_timer_subtask', 'idx_timer_sessions_task_id',
                'idx_timer_sessions_subtask_id', 'idx_gts_task'):
        cursor.execute(f'DROP INDEX IF EXISTS {idx}')
    cursor.execute('DROP TABLE IF EXISTS jurnal')
    cursor.execute('DROP TABLE IF EXISTS timer_sessions')
    cursor.execute('DROP TABLE IF EXISTS global_task_sessions')
    conn.commit()
    conn.close()
    logger.info("Migration v21->v22: dropped timer & jurnal tables (jurnal, timer_sessions, global_task_sessions)")


def migrate_v22_to_v23():
    """v22 -> v23: sterge complet features moarte (fara UI): Checklist PIF,
    Template-uri proiect si Hermes (asistentul AI). Drops checklist_pif,
    checklist_categorii, project_templates, assistant_memory + indexurile lor.
    Idempotent — DROP ... IF EXISTS."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    for idx in ('idx_checklist_proiect', 'idx_checklist_categorii_proiect',
                'idx_checklist_pif_categorie'):
        cursor.execute(f'DROP INDEX IF EXISTS {idx}')
    cursor.execute('DROP TABLE IF EXISTS checklist_pif')
    cursor.execute('DROP TABLE IF EXISTS checklist_categorii')
    cursor.execute('DROP TABLE IF EXISTS project_templates')
    cursor.execute('DROP TABLE IF EXISTS assistant_memory')
    conn.commit()
    conn.close()
    logger.info("Migration v22->v23: dropped checklist_pif, checklist_categorii, project_templates, assistant_memory")


def migrate_v23_to_v24():
    """v23 -> v24: Gantt de proiect. Adauga pe taskurile de proiect coloane de
    planificare explicita (data_start, progres 0-100, is_milestone) si un tabel de
    dependente task_dependencies (predecesor -> succesor, tip FS/SS/FF/SF, lag in
    zile). Dependentele sunt STRICT intre taskuri de proiect. Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tasks)")
    tcols = {row[1] for row in cursor.fetchall()}
    if 'data_start' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN data_start TEXT')
    if 'progres' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN progres INTEGER DEFAULT 0')
    if 'is_milestone' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN is_milestone INTEGER DEFAULT 0')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            predecessor_id TEXT NOT NULL,
            successor_id TEXT NOT NULL,
            tip TEXT DEFAULT 'FS',
            lag INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE,
            FOREIGN KEY (predecessor_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (successor_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_deps_proiect ON task_dependencies(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_deps_succ ON task_dependencies(successor_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_deps_pred ON task_dependencies(predecessor_id)')
    conn.commit()
    conn.close()
    logger.info("Migration v23->v24: tasks.data_start/progres/is_milestone + task_dependencies")


def migrate_v24_to_v25():
    """v24 -> v25: Gantt phases (Plane-style cycles). Adds an optional phase label
    on project tasks so the Gantt can group them under collapsible summary bars.
    Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tasks)")
    tcols = {row[1] for row in cursor.fetchall()}
    if 'faza' not in tcols:
        cursor.execute('ALTER TABLE tasks ADD COLUMN faza TEXT')
    conn.commit()
    conn.close()
    logger.info("Migration v24->v25: added tasks.faza")


def migrate_v25_to_v26():
    """v25 -> v26: implementation periods per project (separate from tasks). Each
    has a start/end + a location (site = santier / sediu = birou EGB). Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS implementari (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            data_start TEXT,
            data_sfarsit TEXT,
            locatie TEXT DEFAULT 'site',
            eticheta TEXT,
            ordine INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_implementari_proiect ON implementari(proiect_id)')
    conn.commit()
    conn.close()
    logger.info("Migration v25->v26: added implementari table")


def migrate_v26_to_v27():
    """v26 -> v27: link a project to its Obsidian vault folder (wiki notes).
    vault_folder holds a vault-relative folder path, e.g.
    'wiki/job/projects/imsat-biochem-podari'. The column was added manually on
    the production DB before this migration existed, so it may already be
    present. Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(proiecte)")
    pcols = {row[1] for row in cursor.fetchall()}
    if 'vault_folder' not in pcols:
        cursor.execute('ALTER TABLE proiecte ADD COLUMN vault_folder TEXT')
    conn.commit()
    conn.close()
    logger.info("Migration v26->v27: added proiecte.vault_folder")


def migrate_v27_to_v28():
    """v27 -> v28: restrangere de scop — scoate biblioteca tehnica din aplicatie.

    Sterge:
      - parametri_master  (~14.800 randuri) si fault_codes (~3.850) — catalog de
        referinta fara nicio legatura cu proiectele. Parametrii si codurile de
        eroare se iau din manualul producatorului, unde ai sursa citabila.
      - echipamente — reintroducere manuala a ceva ce skill-ul drive-backup
        extrage determinist din .dcparamsbak / STARTER, in wiki.
      - atasamente — backup-urile brute stau in vault (raw/projects/<slug>/),
        nu in DB-ul aplicatiei.

    Datele au fost arhivate inainte in vault:
    raw/pif-dashboard/2026-07-27-inainte-de-v28/ (JSON + CSV per tabela +
    snapshot integral). Fisierele urcate raman pe disc in UPLOAD_FOLDER —
    migratia nu sterge nimic din filesystem.

    Idempotenta. clienti ramane (alimenteaza autocomplete-ul de Client).
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    for idx in ('idx_atasamente_proiect', 'idx_atasamente_task',
                'idx_atasamente_global_task', 'idx_echipamente_proiect',
                'idx_fault_codes_fam', 'idx_fault_codes_cod'):
        cursor.execute(f'DROP INDEX IF EXISTS {idx}')
    for table in ('parametri_master', 'fault_codes', 'echipamente', 'atasamente'):
        cursor.execute(f'DROP TABLE IF EXISTS {table}')
    conn.commit()
    conn.close()
    logger.info("Migration v27->v28: dropped parametri_master, fault_codes, "
                "echipamente, atasamente")


# Coloanele care tin o data calendaristica. `notify_on_deadline` NU e aici: e un
# boolean al carui nume contine „deadline". `created_at`/`data_crearii` sunt
# timestampuri scrise de cod, nu de utilizator.
COLOANE_DATA = (
    ('proiecte', ('data_incepere', 'deadline')),
    ('tasks', ('data_scadenta', 'data_planificata', 'data_start', 'data_finalizare')),
    ('global_tasks', ('data_scadenta', 'data_planificata', 'data_finalizare')),
    ('implementari', ('data_start', 'data_sfarsit')),
)


def migrate_v28_to_v29():
    """v28 -> v29: normalizeaza datele care nu sunt ISO.

    API-ul stoca pana acum orice string primit, fara validare, asa ca in baza au
    ajuns `23.02.2026` (deadline de proiect) si `02.07.2026` (scadenta de task).
    Nu erau gresite pentru un om, dar erau invizibile pentru aplicatie: Calendarul
    si Planificatorul nu le puteau aseza pe nicio zi si le sareau in tacere.

    De acum intrarea e pazita de utils.norm_date(), chemata din get_json_or_400().
    Migratia asta curata ce s-a scris inainte de paza.

    Idempotenta: atinge doar valorile care NU incep cu AAAA-LL-ZZ. Ce nu poate
    converti ramane neatins si e raportat in log — mai bine o valoare ciudata pe
    care o vezi decat una pe care am ghicit-o gresit.
    """
    from utils import norm_date   # import tarziu: utils importa database

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    schimbate, nereusite = 0, []

    tabele = {r['name'] for r in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}

    for tabel, coloane in COLOANE_DATA:
        if tabel not in tabele:
            continue
        existente = {r[1] for r in cursor.execute(f'PRAGMA table_info({tabel})')}
        for col in coloane:
            if col not in existente:
                continue
            randuri = cursor.execute(
                f'SELECT id, "{col}" AS v FROM "{tabel}" '
                f'WHERE "{col}" IS NOT NULL AND "{col}" != "" '
                f'AND "{col}" NOT GLOB "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*"'
            ).fetchall()
            for r in randuri:
                try:
                    nou = norm_date(r['v'], col)
                except ValueError:
                    nereusite.append(f'{tabel}.{col}={r["v"]!r} (id {r["id"]})')
                    continue
                cursor.execute(f'UPDATE "{tabel}" SET "{col}" = ? WHERE id = ?',
                               (nou, r['id']))
                schimbate += 1
                logger.info(f'Migration v28->v29: {tabel}.{col} {r["v"]!r} -> {nou!r}')

    conn.commit()
    conn.close()
    logger.info(f'Migration v28->v29: normalized {schimbate} date value(s)')
    if nereusite:
        logger.warning('Migration v28->v29: could not parse, left untouched: '
                       + '; '.join(nereusite))


def run_migrations():
    """Check current schema version and apply needed migrations"""
    current_version = get_schema_version()

    if current_version < 2:
        migrate_v1_to_v2()
        set_schema_version(2)
        current_version = 2

    if current_version < 3:
        migrate_v2_to_v3()
        set_schema_version(3)
        current_version = 3

    if current_version < 4:
        migrate_v3_to_v4()
        set_schema_version(4)
        current_version = 4

    if current_version < 5:
        migrate_v4_to_v5()
        set_schema_version(5)
        current_version = 5

    if current_version < 6:
        migrate_v5_to_v6()
        set_schema_version(6)
        current_version = 6

    if current_version < 7:
        migrate_v6_to_v7()
        set_schema_version(7)
        current_version = 7

    if current_version < 8:
        migrate_v7_to_v8()
        set_schema_version(8)
        current_version = 8

    if current_version < 9:
        migrate_v8_to_v9()
        set_schema_version(9)
        current_version = 9

    if current_version < 10:
        migrate_v9_to_v10()
        set_schema_version(10)
        current_version = 10

    if current_version < 11:
        migrate_v10_to_v11()
        set_schema_version(11)
        current_version = 11

    if current_version < 12:
        migrate_v11_to_v12()
        set_schema_version(12)
        current_version = 12

    if current_version < 13:
        migrate_v12_to_v13()
        set_schema_version(13)
        current_version = 13

    if current_version < 14:
        migrate_v13_to_v14()
        set_schema_version(14)
        current_version = 14

    if current_version < 15:
        migrate_v14_to_v15()
        set_schema_version(15)
        current_version = 15

    if current_version < 16:
        migrate_v15_to_v16()
        set_schema_version(16)
        current_version = 16

    if current_version < 17:
        migrate_v16_to_v17()
        set_schema_version(17)
        current_version = 17

    if current_version < 18:
        migrate_v17_to_v18()
        set_schema_version(18)
        current_version = 18

    if current_version < 19:
        migrate_v18_to_v19()
        set_schema_version(19)
        current_version = 19

    if current_version < 20:
        migrate_v19_to_v20()
        set_schema_version(20)
        current_version = 20

    if current_version < 21:
        migrate_v20_to_v21()
        set_schema_version(21)
        current_version = 21

    if current_version < 22:
        migrate_v21_to_v22()
        set_schema_version(22)
        current_version = 22

    if current_version < 23:
        migrate_v22_to_v23()
        set_schema_version(23)
        current_version = 23

    if current_version < 24:
        migrate_v23_to_v24()
        set_schema_version(24)
        current_version = 24

    if current_version < 25:
        migrate_v24_to_v25()
        set_schema_version(25)
        current_version = 25

    if current_version < 26:
        migrate_v25_to_v26()
        set_schema_version(26)
        current_version = 26

    if current_version < 27:
        migrate_v26_to_v27()
        set_schema_version(27)
        current_version = 27

    if current_version < 28:
        migrate_v27_to_v28()
        set_schema_version(28)
        current_version = 28

    if current_version < 29:
        migrate_v28_to_v29()
        set_schema_version(29)
        current_version = 29

    # Self-heal: a backup/restore can leave schema_version at the latest while
    # an earlier migration's structural changes never ran. Re-apply migrations
    # if their structures are missing — all are idempotent.
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_subtasks'")
    has_subtask_table = cursor.fetchone() is not None
    cursor.execute("PRAGMA table_info(tasks)")
    tasks_cols = {row[1] for row in cursor.fetchall()}
    has_descriere = 'descriere' in tasks_cols
    has_tasks_recurenta = 'recurenta' in tasks_cols
    has_tasks_updated_at = 'updated_at' in tasks_cols
    has_task_planificata = 'data_planificata' in tasks_cols and 'ordine_agenda' in tasks_cols
    cursor.execute("PRAGMA table_info(global_tasks)")
    gt_cols = {row[1] for row in cursor.fetchall()}
    has_gt_recurenta = 'recurenta' in gt_cols
    has_gt_planificata = 'data_planificata' in gt_cols and 'ordine_agenda' in gt_cols
    # Nota: nu mai exista self-heal pentru fault_codes / parametri_master —
    # v28 le sterge intentionat, iar un self-heal le-ar reinvia la fiecare pornire.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    if (not has_subtask_table or not has_descriere or not has_tasks_recurenta
            or not has_tasks_updated_at):
        logger.warning("Self-heal: re-running v7->v8 (task_subtasks / tasks.descriere|recurenta|updated_at missing)")
        migrate_v7_to_v8()
    if not has_gt_recurenta:
        logger.warning("Self-heal: re-running v8->v9 (global_tasks.recurenta missing)")
        migrate_v8_to_v9()
    if not has_task_planificata or not has_gt_planificata:
        logger.warning("Self-heal: re-running v20->v21 (data_planificata / ordine_agenda missing)")
        migrate_v20_to_v21()
    has_gantt_cols = {'data_start', 'progres', 'is_milestone'}.issubset(tasks_cols)
    has_deps_table = 'task_dependencies' in existing_tables
    if not has_gantt_cols or not has_deps_table:
        logger.warning("Self-heal: re-running v23->v24 (tasks.data_start/progres/is_milestone or task_dependencies missing)")
        migrate_v23_to_v24()
    if 'faza' not in tasks_cols:
        logger.warning("Self-heal: re-running v24->v25 (tasks.faza missing)")
        migrate_v24_to_v25()
    if 'implementari' not in existing_tables:
        logger.warning("Self-heal: re-running v25->v26 (implementari table missing)")
        migrate_v25_to_v26()
    cursor2 = get_db().cursor()
    cursor2.execute("PRAGMA table_info(proiecte)")
    proiecte_cols = {row[1] for row in cursor2.fetchall()}
    cursor2.connection.close()
    if 'vault_folder' not in proiecte_cols:
        logger.warning("Self-heal: re-running v26->v27 (proiecte.vault_folder missing)")
        migrate_v26_to_v27()

    if current_version == SCHEMA_VERSION:
        logger.info(f"Database schema is up to date (v{SCHEMA_VERSION})")
    else:
        logger.info(f"Database migrated to v{SCHEMA_VERSION}")


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Create schema_version table first
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proiecte (
            id TEXT PRIMARY KEY,
            tip TEXT NOT NULL,
            nume TEXT NOT NULL,
            client TEXT,
            locatie TEXT,
            echipament_principal TEXT,
            producator TEXT,
            cod_proiect TEXT,
            pm TEXT,
            folder_server TEXT,
            data_incepere TEXT,
            deadline TEXT,
            data_crearii TEXT,
            status TEXT DEFAULT 'in_lucru',
            observatii TEXT,
            nr_comanda TEXT,
            nr_contract TEXT,
            service_before TEXT,
            service_after TEXT,
            confirmat_client INTEGER DEFAULT 0,
            client_nume_confirmare TEXT,
            created_at TEXT,
            updated_at TEXT,
            notify_on_complete INTEGER DEFAULT 1,
            notify_on_deadline INTEGER DEFAULT 1,
            vault_folder TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            titlu TEXT NOT NULL,
            status TEXT DEFAULT 'to_do',
            prioritate TEXT DEFAULT 'normal',
            data_scadenta TEXT,
            data_finalizare TEXT,
            ordine INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
        )
    ''')

    # Gantt de proiect: dependente intre taskuri (predecesor -> succesor).
    # Coloanele Gantt (data_start/progres/is_milestone) se adauga prin migratia v28.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_dependencies (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            predecessor_id TEXT NOT NULL,
            successor_id TEXT NOT NULL,
            tip TEXT DEFAULT 'FS',
            lag INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE,
            FOREIGN KEY (predecessor_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (successor_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    ''')

    # Perioade de implementare per proiect (separate de taskuri): Site / Sediu EGB.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS implementari (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            data_start TEXT,
            data_sfarsit TEXT,
            locatie TEXT DEFAULT 'site',
            eticheta TEXT,
            ordine INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_tasks (
            id TEXT PRIMARY KEY,
            titlu TEXT NOT NULL,
            descriere TEXT,
            prioritate TEXT DEFAULT 'Normal',
            status TEXT DEFAULT 'to_do',
            categorie TEXT DEFAULT 'General',
            data_scadenta TEXT,
            data_finalizare TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clienti (
            id TEXT PRIMARY KEY,
            nume TEXT NOT NULL,
            adresa TEXT,
            telefon TEXT,
            email TEXT,
            contact_principal TEXT,
            note TEXT,
            created_at TEXT
        )
    ''')

    # Generic key/value app settings (Obsidian vault path, future config).
    # Created with IF NOT EXISTS so it always exists without a dedicated migration.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    ''')

    # Lightweight subtasks (checklist items) under a project task.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_subtasks (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            titlu TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            ordine INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    ''')

    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_status ON proiecte(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_producator ON proiecte(producator)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_tip ON proiecte(tip)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_proiect_id ON tasks(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_global_tasks_status ON global_tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_clienti_nume ON clienti(nume)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_subtasks_task_id ON task_subtasks(task_id)')

    conn.commit()
    conn.close()

    # Run migrations after init to ensure schema is up to date
    run_migrations()

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

if __name__ == '__main__':
    init_db()
    print(f"Database initialized at: {DATABASE_PATH}")
