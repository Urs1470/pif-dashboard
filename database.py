import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger('pif_dashboard')

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pif_dashboard.db')

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

SCHEMA_VERSION = 13

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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_checklist_proiect ON checklist_pif(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jurnal_proiect ON jurnal(proiect_id)')
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
    import re
    pattern = re.compile(r'^\s*\((?:Only )?[Vv]isible\b[^)]*\)\s*')
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

    # Self-heal: a backup/restore can leave schema_version at the latest while
    # an earlier migration's structural changes never ran. Re-apply migrations
    # if their structures are missing — all are idempotent.
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checklist_categorii'")
    has_cat_table = cursor.fetchone() is not None
    cursor.execute("PRAGMA table_info(checklist_pif)")
    has_cat_col = any(row[1] == 'categorie_id' for row in cursor.fetchall())
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_subtasks'")
    has_subtask_table = cursor.fetchone() is not None
    cursor.execute("PRAGMA table_info(tasks)")
    tasks_cols = {row[1] for row in cursor.fetchall()}
    has_descriere = 'descriere' in tasks_cols
    has_tasks_recurenta = 'recurenta' in tasks_cols
    has_tasks_updated_at = 'updated_at' in tasks_cols
    cursor.execute("PRAGMA table_info(timer_sessions)")
    has_timer_task_id = any(row[1] == 'task_id' for row in cursor.fetchall())
    cursor.execute("PRAGMA table_info(global_tasks)")
    has_gt_recurenta = any(row[1] == 'recurenta' for row in cursor.fetchall())
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fault_codes'")
    has_fault_codes = cursor.fetchone() is not None
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='global_task_sessions'")
    has_gts = cursor.fetchone() is not None
    # parametri_master may not exist on fresh DBs — gate v7 self-heal on it.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    has_pdf_extra = True  # default true so we skip self-heal when table is absent
    if 'parametri_master' in existing_tables:
        cursor.execute("PRAGMA table_info(parametri_master)")
        has_pdf_extra = any(row[1] == 'pdf_extra' for row in cursor.fetchall())
    conn.close()
    if not has_cat_table or not has_cat_col:
        logger.warning("Self-heal: re-running v4->v5 (checklist_categorii / categorie_id missing)")
        migrate_v4_to_v5()
    if 'parametri_master' in existing_tables and not has_pdf_extra:
        logger.warning("Self-heal: re-running v6->v7 (parametri_master.pdf_extra missing)")
        migrate_v6_to_v7()
    if (not has_subtask_table or not has_descriere or not has_tasks_recurenta
            or not has_tasks_updated_at or not has_timer_task_id):
        logger.warning("Self-heal: re-running v7->v8 (task_subtasks / tasks.descriere|recurenta|updated_at / timer_sessions.task_id missing)")
        migrate_v7_to_v8()
    if not has_gt_recurenta:
        logger.warning("Self-heal: re-running v8->v9 (global_tasks.recurenta missing)")
        migrate_v8_to_v9()
    if not has_fault_codes:
        logger.warning("Self-heal: re-running v9->v10 (fault_codes missing)")
        migrate_v9_to_v10()
    if not has_gts:
        logger.warning("Self-heal: re-running v10->v11 (global_task_sessions missing)")
        migrate_v10_to_v11()

    if current_version == SCHEMA_VERSION:
        logger.info(f"Database schema is up to date (v{SCHEMA_VERSION})")
    else:
        logger.info(f"Database migrated to v{SCHEMA_VERSION}")


# Bump when data/fault_codes/*.json changes — forces a one-time re-seed on the
# next startup. The fault_codes table holds only generated data, never user
# data, so a full rebuild from the JSON is always safe.
FAULT_DATA_REV = 2


def seed_fault_codes():
    """Populate fault_codes from data/fault_codes/*.json.

    Seeds on first run (empty table) and re-seeds automatically whenever
    FAULT_DATA_REV is bumped. Makes the drive fault-code dataset self-deploying
    via git (the DB itself is gitignored).

    Crash-safe: accumulates ALL rows first, then runs DELETE + INSERT in a single
    explicit transaction. A mid-loop failure leaves the existing table untouched
    instead of wiping it."""
    import json
    import glob
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'data', 'fault_codes')
    if not os.path.isdir(data_dir):
        return
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM fault_codes')
        count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        conn.close()
        return
    cursor.execute("SELECT value FROM app_settings WHERE key = 'fault_data_rev'")
    row = cursor.fetchone()
    try:
        stored_rev = int(row[0]) if row else 0
    except (ValueError, TypeError):
        stored_rev = 0
    if count > 0 and stored_rev >= FAULT_DATA_REV:
        conn.close()
        return  # already up to date
    cols = ['producator', 'familie', 'cod', 'cod_secundar', 'tip', 'nume',
            'cauza', 'remediu', 'reactie', 'confirmare', 'extra_json',
            'pagina', 'sursa']
    placeholders = ','.join('?' * len(cols))

    # Phase 1: read ALL JSON files first. If anything fails, abort BEFORE
    # touching the table — a partial JSON parse must not wipe existing data.
    rows = []
    read_failed = False
    for path in sorted(glob.glob(os.path.join(data_dir, '*.json'))):
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as e:
            logger.warning(f"seed_fault_codes: aborting — failed to read {os.path.basename(path)}: {e}")
            read_failed = True
            break
        try:
            for d in data:
                extra = d.get('extra')
                extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
                rows.append((
                    d.get('producator'), d.get('familie'), d.get('cod'),
                    d.get('cod_secundar'), d.get('tip'), d.get('nume'),
                    d.get('cauza'), d.get('remediu'), d.get('reactie'),
                    d.get('confirmare'), extra_json, d.get('pagina'), d.get('sursa'),
                ))
        except Exception as e:
            logger.warning(f"seed_fault_codes: aborting — failed to parse {os.path.basename(path)}: {e}")
            read_failed = True
            break

    if read_failed or not rows:
        if not rows and not read_failed:
            logger.warning("seed_fault_codes: no rows found in data/fault_codes/*.json, leaving table untouched")
        conn.close()
        return

    # Phase 2: all reads succeeded — do DELETE + bulk INSERT in one transaction.
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor.execute('DELETE FROM fault_codes')
        cursor.executemany(
            f"INSERT INTO fault_codes ({','.join(cols)}) VALUES ({placeholders})",
            rows)
        cursor.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ('fault_data_rev', str(FAULT_DATA_REV), datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.warning(f"seed_fault_codes: transaction failed, rolled back: {e}")
        return
    conn.close()
    logger.info(f"Seeded fault_codes with {len(rows)} rows (rev {FAULT_DATA_REV})")


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
            notify_on_deadline INTEGER DEFAULT 1
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist_pif (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            titlu TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            note TEXT,
            ordine INTEGER DEFAULT 0,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jurnal (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            data TEXT NOT NULL,
            continut TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timer_sessions (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            task_id TEXT,
            subtask_id TEXT,
            start_time TEXT NOT NULL,
            stop_time TEXT,
            durata_secunde INTEGER,
            FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS atasamente (
            id TEXT PRIMARY KEY,
            proiect_id TEXT NOT NULL,
            nume_fisier TEXT NOT NULL,
            tip_fisier TEXT,
            dimensiune INTEGER,
            data TEXT,
            cale_locala TEXT NOT NULL,
            tip_atasament TEXT DEFAULT 'fisier',
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist_categorii (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proiect_id TEXT NOT NULL,
            nume TEXT NOT NULL,
            ordine INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')

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
            created_at TEXT
        )
    ''')

    # Persistent memory for the in-app AI assistant (Hermes).
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assistant_memory (
            id TEXT PRIMARY KEY,
            continut TEXT NOT NULL,
            created_at TEXT
        )
    ''')

    # Drive fault / alarm / warning codes extracted from the manufacturer manuals.
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

    # Time-tracking sessions for daily (global) tasks.
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

    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_status ON proiecte(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_producator ON proiecte(producator)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proiecte_tip ON proiecte(tip)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_proiect_id ON tasks(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_global_tasks_status ON global_tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_checklist_proiect ON checklist_pif(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jurnal_proiect ON jurnal(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timer_proiect ON timer_sessions(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timer_task ON timer_sessions(task_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timer_subtask ON timer_sessions(subtask_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_atasamente_proiect ON atasamente(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_echipamente_proiect ON echipamente(proiect_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_clienti_nume ON clienti(nume)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_budget_audit_user_ts ON budget_audit(user, ts DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fault_codes_fam ON fault_codes(producator, familie)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fault_codes_cod ON fault_codes(cod)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_gts_task ON global_task_sessions(global_task_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_subtasks_task_id ON task_subtasks(task_id)')

    # Cap budget_audit at 5000 most-recent rows per user. Fresh DBs get the trigger
    # here; existing DBs get it via migrate_v11_to_v12.
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

    # Run migrations after init to ensure schema is up to date
    run_migrations()

    # Self-deploying fault-code dataset: fill the table on first run.
    seed_fault_codes()

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

if __name__ == '__main__':
    init_db()
    print(f"Database initialized at: {DATABASE_PATH}")
