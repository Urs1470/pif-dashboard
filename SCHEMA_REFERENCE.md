# PIF Dashboard — Schema & API Reference

> Generat pentru a servi ca briefing pentru un alt LLM care va construi un endpoint de import structurat.

---

## 1. Schema completă SQLite (din `database.py` → `init_db()`)

### PROIECTE
```sql
CREATE TABLE IF NOT EXISTS proiecte (
    id TEXT PRIMARY KEY,                       -- UUID v4 (generate_uuid())
    tip TEXT NOT NULL,                          -- 'PIF' | 'Service'
    nume TEXT NOT NULL,
    client TEXT,                                -- text liber (nume client, NU foreign key)
    locatie TEXT,
    echipament_principal TEXT,
    producator TEXT,                            -- 'ABB' | 'Siemens' | 'Danfoss' | 'Lenze' | 'Altul'
    cod_proiect TEXT,
    pm TEXT,                                    -- project manager
    folder_server TEXT,
    data_incepere TEXT,                         -- ISO date string 'YYYY-MM-DD'
    deadline TEXT,                              -- ISO date string
    data_crearii TEXT,                          -- ISO date string
    status TEXT DEFAULT 'in_lucru',             -- enum mai jos
    observatii TEXT,
    nr_comanda TEXT,
    nr_contract TEXT,
    service_before TEXT,                        -- Service only: stare echipament inainte
    service_after TEXT,                         -- Service only: stare echipament dupa
    confirmat_client INTEGER DEFAULT 0,         -- 0/1 boolean
    client_nume_confirmare TEXT,
    created_at TEXT,                            -- ISO datetime
    updated_at TEXT,                            -- ISO datetime
    notify_on_complete INTEGER DEFAULT 1,
    notify_on_deadline INTEGER DEFAULT 1,
    vault_folder TEXT                           -- folder în vault-ul Obsidian, ex. 'wiki/job/projects/<slug>' (v27)
);
```

**Câmpuri obligatorii la INSERT**: `tip` (NOT NULL), `nume` (NOT NULL). Restul au defaults sau sunt nullable.
**ID**: UUID v4 text, generat server-side sau poate fi furnizat de client.

### CLIENTI
```sql
CREATE TABLE IF NOT EXISTS clienti (
    id TEXT PRIMARY KEY,                        -- UUID v4
    nume TEXT NOT NULL,
    adresa TEXT,
    telefon TEXT,
    email TEXT,
    contact_principal TEXT,
    note TEXT,
    created_at TEXT                             -- ISO datetime
);
```

**Relația cu proiecte**: NICIUNA (NU e foreign key). `proiecte.client` e text liber. Un proiect poate exista fără client. Tabela `clienti` e un registru independent pentru autocompletare.

> **Tabele șterse.** v23: `checklist_pif`, `checklist_categorii`,
> `project_templates`, `assistant_memory` (Hermes AI) — cod mort, zero UI.
> **v28: `parametri_master`, `fault_codes`, `echipamente`, `atasamente`** —
> restrângere de scop; parametrii și fault-urile se iau din manual, backup-urile
> de drive stau în vault (`raw/projects/<slug>/`), citite de skill-ul
> `drive-backup`. Datele au fost arhivate în vault la
> `raw/pif-dashboard/2026-07-27-inainte-de-v28/`. Fișierele urcate NU au fost
> șterse de pe disc — doar tabela. Toate sunt `DROP TABLE IF EXISTS`, idempotente.

### TASKS (per proiect)
```sql
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,                        -- UUID v4
    proiect_id TEXT NOT NULL,                   -- FK -> proiecte.id ON DELETE CASCADE
    titlu TEXT NOT NULL,
    status TEXT DEFAULT 'to_do',                -- 'to_do' | 'in_progress' | 'done'
    prioritate TEXT DEFAULT 'normal',           -- 'normal' | 'urgent' | 'minor'
    data_scadenta TEXT,
    data_finalizare TEXT,
    ordine INTEGER DEFAULT 0,
    descriere TEXT,
    recurenta TEXT,                              -- 'zilnic' | 'saptamanal' | 'lunar' | null
    updated_at TEXT,
    created_at TEXT,
    FOREIGN KEY (proiect_id) REFERENCES proiecte(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,                        -- UUID v4
    task_id TEXT NOT NULL,                      -- referinta la tasks.id (fara FK constraint!)
    titlu TEXT NOT NULL,
    done INTEGER DEFAULT 0,
    ordine INTEGER DEFAULT 0,
    created_at TEXT
);
```

### GLOBAL TASKS (independente de proiecte)
```sql
-- Setul efectiv de coloane (CREATE TABLE-ul din init_db e incomplet:
-- `recurenta`, `ordine_agenda` si `sfera` vin din migrari — v9, v21, v38).
CREATE TABLE IF NOT EXISTS global_tasks (
    id TEXT PRIMARY KEY,                        -- UUID v4
    titlu TEXT NOT NULL,
    descriere TEXT,
    status TEXT DEFAULT 'to_do',                -- 'to_do' | 'done' (v34)
    categorie TEXT DEFAULT 'General',           -- text liber
    sfera TEXT DEFAULT 'munca',                 -- 'munca' | 'personal' (v38)
    data_scadenta TEXT,
    data_finalizare TEXT,
    recurenta TEXT,                              -- 'zilnic' | 'saptamanal' | 'lunar' | null
    ordine_agenda INTEGER DEFAULT 0,             -- ordinea pe boardul „Astăzi"
    created_at TEXT,
    updated_at TEXT
);
-- `prioritate` a plecat in v34, `data_planificata` in v33.
-- `sfera` separa taskurile personale de cele de munca; TOATE interogarile pe
-- global_tasks filtreaza explicit (lipsa parametrului = 'munca', fail-closed).
```

---

## 2. Cum se creează un proiect — cod real

**Fișier**: `blueprints/projects.py`, linia 64

```python
@projects_bp.route('/api/proiecte', methods=['POST'])
@login_required
def create_proiect():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    project_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO proiecte (
            id, tip, nume, client, locatie, echipament_principal, producator,
            cod_proiect, pm, folder_server, data_incepere, deadline, data_crearii,
            status, observatii, nr_comanda, nr_contract, service_before, service_after,
            confirmat_client, client_nume_confirmare, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id,
        data.get('tip', 'PIF'),                  # 'PIF' sau 'Service'
        data.get('nume', ''),                     # obligatoriu logic
        data.get('client', ''),
        data.get('locatie', ''),
        data.get('echipament_principal', ''),
        data.get('producator', 'Altul'),
        data.get('cod_proiect', ''),
        data.get('pm', ''),
        data.get('folder_server', ''),
        data.get('data_incepere', ''),
        data.get('deadline', ''),
        data.get('data_crearii', now[:10]),
        data.get('status', 'in_lucru'),
        data.get('observatii', ''),
        data.get('nr_comanda', ''),
        data.get('nr_contract', ''),
        data.get('service_before', ''),
        data.get('service_after', ''),
        data.get('confirmat_client', 0),
        data.get('client_nume_confirmare', ''),
        now, now
    ))
    conn.commit()
    conn.close()
    return jsonify({'id': project_id, 'message': 'Project created'}), 201
```

---

## 3. Endpointuri existente de import/bulk/batch

| Endpoint | Verb | Ce face | Import? |
|---|---|---|---|
| `/api/proiecte/batch` | POST | Batch update status sau batch delete pe mai multe proiecte | NU |
| `/api/parametri/bulk` | GET | Read-only dump de parametri pentru cache offline mobil | NU |
| `/api/import-params/preview` | POST | Preview import parametri din fișier export producător (parsează, nu scrie) | Partial |

**Nu există endpoint de import/upsert structurat. Trebuie creat de la zero.**

---

## 4. Enumuri și valori fixe

### Tipul proiectului
```
'PIF'       — Punere În Funcțiune
'Service'   — Intervenție Service
```

### Statusul proiectului
```
'in_lucru'      — În lucru (default)
'blocat'        — Blocat
'in_asteptare'  — În așteptare (atenție: cu diacritice, "ș")
'finalizat'     — Finalizat
'anulat'        — Anulat
```

### Statusul taskului (project tasks + global tasks)
```
'to_do'         — De făcut (default)
'in_progress'   — În progres
'done'          — Finalizat
```

### Prioritate task
```
-- Project tasks (lowercase):
'normal'   | 'urgent'  | 'minor'

-- Global tasks (capitalized):
'Normal'   | 'Urgent'  | 'Minor'
```

### Producători hardcodați
```
'ABB'  | 'Siemens'  | 'Danfoss'  | 'Lenze'  | 'Altul'
```

### Recurență (tasks)
```
'zilnic'      | 'saptamanal'  | 'lunar'  | null (fără recurență)
```

### Tip atașament
```
'fisier'   — default
```

---

## 5. ~~Structura checklist PIF~~ (ȘTERS v23)

Feature-ul Checklist PIF (tabelele `checklist_pif` + `checklist_categorii`,
rutele `/api/proiecte/<id>/checklist*`, secțiunea din export PDF) a fost șters
în v23 — era cod mort fără niciun UI în SPA. La fel `project_templates`
(`/api/templates`) și `assistant_memory` (Hermes AI). Migrația v22→v23 face DROP.

---

## 6. Sistem de identificare

| Entitate | Tip ID | Generat cum |
|---|---|---|
| proiecte | UUID v4 text | `str(uuid.uuid4())` server-side, sau furnizat de client |
| clienti | UUID v4 text | idem |
| tasks | UUID v4 text | idem |
| task_subtasks | UUID v4 text | idem |
| global_tasks | UUID v4 text | idem |

Toate endpoint-urile acceptă `"id"` în JSON body — dacă e furnizat, îl folosesc; altfel generează UUID nou.

---

---

## 8. Validări și logică de business

### Un proiect poate exista fără client?
**Da.** `client` e `TEXT` nullable, nu FK. Un proiect cu `client = ""` e valid.

### Cascade deletes
Când un proiect se șterge (via batch delete):
1. Se șterg explicit: `task_subtasks` (ale task-urilor proiectului), apoi `tasks`
2. FK CASCADE ar face o parte din treabă, dar codul face și explicit pentru siguranță
3. Directorul proiectului din `UPLOAD_FOLDER` se șterge de pe disc
3. Fișierele fizice ale atașamentelor se șterg de pe disk (`shutil.rmtree`)

### Unicitate
- Toate ID-urile sunt PK → unice
- Nu există unique constraints pe nume, cod_proiect, serial_number — pot exista duplicate
- `clienti.nume` are index dar NU unique

### CSRF
Toate endpoint-urile POST/PUT/DELETE necesită header `X-CSRF-Token` (double-submit cookie pattern). Token-ul se citește din cookie-ul `csrf_token`. Webhook-ul `/webhook/deploy` e exempt.

---

## 9. Indexuri existenți

```sql
idx_proiecte_status          ON proiecte(status)
idx_proiecte_producator      ON proiecte(producator)
idx_proiecte_tip             ON proiecte(tip)
idx_tasks_proiect_id         ON tasks(proiect_id)
idx_tasks_status             ON tasks(status)
idx_global_tasks_status      ON global_tasks(status)
idx_clienti_nume             ON clienti(nume)
idx_task_subtasks_task_id    ON task_subtasks(task_id)
idx_implementari_proiect     ON implementari(proiect_id)
```
