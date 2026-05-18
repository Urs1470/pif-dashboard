import sqlite3
import os
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pif_dashboard.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.row_factory = sqlite3.Row
    return conn

def close_db(exc=None):
    """No-op for compatibility — Flask closes connections automatically."""
    pass

# ============ PHASE 2c: DATABASE MIGRATIONS ============
# Schema version history:
# v1: Initial schema (proiecte, tasks, checklist_pif, jurnal, timer_sessions, atasamente, global_tasks)
# v5: Added checklist_categorii table (per-project dynamic categories for checklist_pif)
#     + nullable categorie_id column on checklist_pif
# v2: Added clienti, echipamente, project_templates tables
# v3: Added ordine to tasks, notify_on_complete/deadline to proiecte
# v4: Added budget_state, budget_audit tables for Budget Tracker

SCHEMA_VERSION = 5

def get_schema_version():
    """Get current schema version from schema_version table"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        version = row['version'] if row else 1
    except:
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
    except:
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
    print("Migration v1->v2 completed: Added clienti, echipamente, project_templates tables")

def migrate_v2_to_v3():
    """Migration from v2 to v3: Add ordine to tasks, notify_on_complete/deadline to proiecte"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Add ordine column to tasks table if not exists
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN ordine INTEGER DEFAULT 0")
    except:
        pass
    
    # Add notify_on_complete to proiecte if not exists
    try:
        cursor.execute("ALTER TABLE proiecte ADD COLUMN notify_on_complete INTEGER DEFAULT 1")
    except:
        pass
    
    # Add notify_on_deadline to proiecte if not exists
    try:
        cursor.execute("ALTER TABLE proiecte ADD COLUMN notify_on_deadline INTEGER DEFAULT 1")
    except:
        pass
    
    conn.commit()
    conn.close()
    print("Migration v2->v3 completed: Added ordine to tasks, notify_on_complete/deadline to proiecte")

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
    print("Migration v3->v4 completed: Added budget_state, budget_audit tables")

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
    print("Migration v4->v5 completed: Added checklist_categorii + categorie_id column")

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

    if current_version == SCHEMA_VERSION:
        print(f"Database schema is up to date (v{SCHEMA_VERSION})")
    else:
        print(f"Database migrated to v{SCHEMA_VERSION}")

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

    # Create indexes
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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_budget_audit_user_ts ON budget_audit(user, ts DESC)')

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
