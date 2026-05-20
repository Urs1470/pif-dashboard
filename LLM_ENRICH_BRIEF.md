# LLM Enrichment Brief — pentru HERMES

> Status la **2026-05-20**. Brief rescris dupa ce Claude (Claude Code pe Windows) a terminat ABB + Siemens.

## Ce e GATA (NU atinge)

| Familie | Coverage `explicatie` | Cine |
|---|---|---|
| ACS580 | 100% (1273/1273) | Claude |
| ACS880 | 100% (1682/1682) | Claude |
| SINAMICS_G120 | 99% (1458/1461) | Claude |
| SINAMICS_G130_G150 | 100% (2096/2096) | Claude |
| SINAMICS_S120_S150 | 100% (3499/3499) | Claude |

DB-ul de pe server a fost deja inlocuit cu versiunea care contine toate astea (upload prin `/admin/db-upload`, backup `backups/pif_dashboard_pre_upload_20260520_121812.db`). **Tu lucrezi pe acelasi `pif_dashboard.db`** — modificarile tale merg LIVE direct, fara upload.

## Task-ul tau (HERMES) — REFACERE COMPLETA

Regenereaza `explicatie` + `influenteaza` + `categorie` pentru cele 3 familii ramase.
**ATENTIE: refacere de la ZERO** — explicatiile existente la aceste familii sunt vechi
(generate cu calitate slaba inainte) si trebuie INLOCUITE toate, nu doar completate golurile.

| Familie | Params (TOTI) | Format cod param |
|---|---|---|
| Danfoss_VLT_FC302 | **1297** | `0-01`, `3-41` (grup-index) |
| Lenze_i550 | **1638** | `0x0000` (hex) |
| Lenze_i950 | **1799** | `0x1000` (hex) |

Total: **4734 params**. Ordine recomandata: Danfoss intai (cel mai mic), apoi i550, apoi i950.

**NU atinge** campurile PDF-derived: `parametru, descriere_scurta, descriere, acces, tip_date, valoare_default_str, valoare_default, min, max, unitate, pagina, pdf_extra`.

### PAS OBLIGATORIU inainte de enrichment: golire campuri

`llm_batch_enrich.py` are `quality_check` care PASTREAZA explicatiile existente daca par OK
(-> decizie "keep"). Ca sa forteze refacerea de la zero, sterge intai cele 3 campuri LLM
pentru aceste 3 familii (DOAR pentru ele — NU atinge ABB/Siemens):

```bash
cd ~/Projects/pif-dashboard
python - <<'EOF'
import sqlite3
conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()
fams = ('Danfoss_VLT_FC302','Lenze_i550','Lenze_i950')
for f in fams:
    cur.execute("UPDATE parametri_master SET explicatie='', influenteaza='', categorie='' WHERE familie=?", (f,))
    print(f, cur.rowcount, 'campuri golite')
conn.commit(); conn.close()
EOF
```

Dupa golire, fiecare param va trece prin `quality_check` -> "new" -> regenerare completa.

## Cum rulezi

```bash
cd ~/Projects/pif-dashboard
git pull origin master          # ia ultimele scripts de la Claude
git status                      # TREBUIE curat (vezi anti-coliziune)
cp pif_dashboard.db pif_dashboard.db.before-hermes-$(date +%Y%m%d_%H%M%S)

# PAS OBLIGATORIU: goleste campurile LLM pentru cele 3 familii (vezi mai sus)
# ... ruleaza blocul de golire ...

python scripts/llm_batch_enrich.py --familie Danfoss_VLT_FC302 --field explicatie
python scripts/llm_batch_enrich.py --familie Lenze_i550 --field explicatie
python scripts/llm_batch_enrich.py --familie Lenze_i950 --field explicatie
```

`llm_batch_enrich.py` scrie direct in DB (`write_row`), face `git commit + push` automat la fiecare 100 params. Dupa golirea campurilor, `quality_check` returneaza "new" pentru toti params -> regenerare completa de la zero. Familiile ABB/Siemens NU sunt afectate (nu le golesti, deci raman "keep").

## Reguli stil explicatie

- Limba: **romana FARA diacritice** (`a a i t s` simple, niciun `â ă î ț ș`)
- 2-3 propozitii, max ~250 chars, ton commissioner (Ion e inginer de camp)
- Formule electrotehnice cu LaTeX inline `$...$`, KaTeX render in UI:
  - indici `$T_n$ $P_n$ $L_d$`, fractii `$\dfrac{a}{b}$` (nu `\frac`), `\cdot` (nu `*`), unitati `$T_n\,[\text{Nm}]$`
  - NU LaTeX pentru valori simple (`1500 rpm`, `100%`) sau coduri (`3-41`, `0x2900`)
- `influenteaza`: CSV coduri params corelate, ex `"3-41, 3-42"`. Surse: `pdf_extra.refer_to`, coduri din `descriere`. Regex: Danfoss `\b\d+-\d+\b`, Lenze `\b0x[0-9A-F]{4,5}\b`. Gol daca nu exista.
- `categorie`: exact una din `Motor | Limite | Rampe | I/O | Comunicatii | Protectii | Diagnostic | Altul`

## Anti-coliziune (CRITIC)

- Worktree-ul de pe server TREBUIE curat inainte sa pornesti — altfel webhook-ul auto-deploy al lui Claude crapa cu 500 si push-urile lui se blocheaza pe GitHub. Daca ai WIP: `git stash` sau commit+push.
- Commit per batch (scriptul o face automat). Push imediat.
- Daca `git pull` da conflict pe `scripts/`, rezolva inainte de a rula enrichment.

## Verificare dupa fiecare familie

```sql
SELECT COUNT(*) FROM parametri_master
WHERE familie='Lenze_i550' AND (explicatie IS NULL OR explicatie='');
-- trebuie 0
```

Sample 3 params random: fara diacritice, LaTeX `$...$` matched, categorie din lista fixa, coduri `influenteaza` valide.

## Done state

Toate 8 familiile la 100% `explicatie`. Cum tu rulezi pe DB-ul live de pe server, nu mai e nevoie de upload — schimbarile sunt deja vizibile pe `https://pif.iupif.org` (eventual dupa refresh cache stale-while-revalidate).
