# LLM Enrichment Brief — pentru sesiunea Sonnet

## Context rapid

DB `parametri_master` pe PIF Dashboard are **14.745 params** după audit PDF complet (sesiunile Claude Opus 4.6, 18-19 mai 2026). Toate câmpurile PDF-derived sunt populate:
- `parametru`, `descriere_scurta`, `descriere`, `acces`, `tip_date`, `valoare_default_str`, `min`, `max`, `unitate`, `pagina`, `pdf_extra` (JSON).

**Task-ul tău (Sonnet)**: completare câmpuri LLM-only:
- `explicatie` — RO commissioning text cu LaTeX pentru formule electrotehnice
- `influenteaza` — CSV cu coduri params (ex: `"30.12, 21.13"`)
- `categorie` — din lista fixă: `Motor | Limite | Rampe | I/O | Comunicatii | Protectii | Diagnostic | Altul`

**NU atinge**: parametru, descriere_scurta, descriere, acces, tip_date, valoare_default_str, valoare_default, min, max, unitate, pagina, pdf_extra. TOATE sunt PDF-derived și validate.

## Pași concreți la start

1. `cd D:\Projects\pif-dashboard`
2. `git pull && git log --oneline -10` — verifică ai ultimele commit-uri (`b002bb7` apply_explicatii.py)
3. Citește `HERMES.md` secțiunea "Audit parametri (status la 2026-05-18)" + regulile 5b LaTeX
4. Verifică `scripts/sample_explicatii.json` — 30 params deja procesate (NU le refaci). Sunt artifact-ul format-ului așteptat.

## Format input/output (pentru fiecare batch)

**Citește un batch din DB**:
```python
import sqlite3
conn = sqlite3.connect('pif_dashboard.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
  SELECT id, familie, parametru, descriere_scurta, descriere,
         valoare_default_str, min, max, unitate, pdf_extra
  FROM parametri_master
  WHERE familie = ?
    AND descriere IS NOT NULL AND TRIM(descriere) != ''
    AND (explicatie IS NULL OR explicatie = '')
  ORDER BY id
  LIMIT 100
""", ('ACS580',))
```

**Generează JSON** în același format ca `scripts/sample_explicatii.json`:
```json
[
  {
    "id": 15333,
    "familie": "ACS580",
    "parametru": "26.08",
    "descriere_scurta": "Minimum torque reference",
    "GENERATED": {
      "explicatie": "Limita inferioara... $T_n = \\dfrac{9550 \\cdot P_n}{n_n}$ ...",
      "influenteaza": "30.19, 99.12",
      "categorie": "Limite"
    }
  }
]
```

**Apply la DB**:
```bash
python scripts/apply_explicatii.py path/to/batch.json
```

## Reguli stil

- **Limba**: română FĂRĂ DIACRITICE (`â, ă, î, ț, ș` interzise — Ion preferă fără)
- **Lungime**: 2-3 propoziții, max ~250 chars
- **Tone**: commissioner-friendly (Ion e inginer câmp, nu academic)
- **Formule LaTeX inline**: `$...$` (vezi reguli mai jos)
- **Citează alte params**: cu cod (e.g. `Vezi 30.12 pentru limita superioara`)
- **Skip nimic**: dacă param-ul are descriere existentă în PDF, generează explicatie. Doar params cu `descriere IS NULL` skip.

## LaTeX pentru formule (KaTeX render în UI)

Frontend folosește KaTeX. Sintaxă:

| Tip | Cum scrii | Render |
|---|---|---|
| Variabile cu indici | `$T_n$, $P_n$, $L_d$, $i_q$, $\omega_e$, $\Psi$` | $T_n$ |
| Fracții | `$\dfrac{a}{b}$` (NU `\frac` — mai bun inline) | $\dfrac{a}{b}$ |
| Unități | `$T_n\,[\text{Nm}]$` (cu `\,` separator) | $T_n\,[\text{Nm}]$ |
| Multiplicare | `\cdot` (NU `*`) | $\cdot$ |
| Intervale | `$[10\%, 300\%]$` | |
| Derivate | `$\dfrac{di_d}{dt}$` | |

**NU folosi LaTeX** pentru:
- Valori simple (`30.12`, `1500 rpm`, `100%`)
- Coduri (`p0500`, `99.04`)

**Exemple bune** (din sample-ul deja procesat):
- 26.08: `Limita inferioara a referintei de cuplu, exprimata in procente din cuplul nominal motor $T_n = \dfrac{9550 \cdot P_n\,[\text{kW}]}{n_n\,[\text{rpm}]}\,[\text{Nm}]$. Pentru limita absoluta hard, vezi 30.19.`
- 98.13: `Inductanta de axa directa $L_d$ pentru motoare cu magneti permanenti, in $\text{mH}$. Folosita in modelul motor pentru control vectorial precis ($u_d = R_s i_d + L_d \frac{di_d}{dt} - \omega_e L_q i_q$).`
- 32.31: `Histerezis pentru supervizarea 3: actiunea se activeaza cand semnalul $S$ depaseste $L_{up} + \frac{h}{2}$.`

## Sursa info pentru explicații

1. `descriere` — text PDF-derived (cel mai important input)
2. `pdf_extra` (JSON) — `values[]` (enum), `dependency`, `notice`, `note`, `refer_to`, `warnings`
3. `descriere_scurta` — numele scurt al param
4. Înțelegerea ta tehnică despre convertizoare frecvență (drives, motor control, comms)

**NU genera info care NU-i derivable** din descriere + pdf_extra + cunostințe tehnice generale.

## influenteaza CSV — cum populezi

- Coduri primare din `pdf_extra.refer_to` (lista deja extrasă)
- Coduri menționate în `descriere` (regex `\b[pr]\d{4,5}\b` pentru Siemens, `\b\d+\.\d+\b` pentru ABB, `\b\d+-\d+\b` pentru Danfoss, `\b0x[0-9A-F]{4,5}\b` pentru Lenze)
- Format final: `"30.12, 21.13"` (CSV, fără spații extra)

## Strategie batch pas-cu-pas

Ion vrea **cate un pic per turn** (asta-i decizia luată). Sugestie:

1. **Turn 1**: ACS580 batch 100 (10% din 1273). Generezi, applici, raportezi.
2. **Turn 2**: continuă ACS580 până termini, apoi ACS880.
3. **Turn 3-N**: pe rând familiile (Danfoss → Lenze → Siemens).
4. **După fiecare batch**: scurt raport — count keep/rewrite/new, observații quality, eventual issues.

**Sample mai bun decât mare**: 50 params per turn cu LaTeX corect > 500 generic.

## Categorii — ghid de mapping

| Categorie | Exemple params |
|---|---|
| **Motor** | nameplate (current, voltage, freq, speed, poles, cos φ, Ld, Lq, Rs), control mode, ID run |
| **Limite** | min/max speed, max torque, current limit, frequency limit |
| **Rampe** | acceleration time, deceleration time, S-curve, jerk |
| **I/O** | digital input/output, analog input/output, terminal config, scaling |
| **Comunicatii** | fieldbus (Profibus, Profinet, Modbus, CANopen, EtherCAT), PDO mapping, IP/MAC, baud rate |
| **Protectii** | overcurrent, overvoltage, undervoltage, motor temp, IGBT temp, supervision actions, SLS/STO |
| **Diagnostic** | actual values, status words, fault buffer, alarm time, energy counters |
| **Altul** | DCC blocks (LIM, MFP, MUL), favorites, expert/dev params |

## Cost estimat (Sonnet 4.7)

- ~14.000 params × 1500 tokens input (descriere + pdf_extra context cached) × 250 tokens output
- Sonnet $3/MT input, $15/MT output → ~$50-80 cu prompt caching agresiv
- Ion explicit: cost nu e blocker pentru accuracy

## Anti-coliziune

- Înainte de orice modificare: `git pull && git status` curat
- `git add scripts/apply_explicatii.py` + commit per batch ("LLM enrich: ACS580 +100 params, batch 1/13")
- Push imediat ca alte sesiuni (Claude pe alte fișiere, Hermes) să vadă
- Backup DB înainte de `apply` masiv: `Copy-Item pif_dashboard.db pif_dashboard.db.before-enrich-<ts>`

## Verificare quality

După fiecare batch:
1. Sample 3 params random din ultimul batch
2. Verifică:
   - Nu există diacritice
   - LaTeX pe formule e sintactic corect (`$...$` matched, `\dfrac` nu `\frac`)
   - Coduri în `influenteaza` sunt valide (există în DB-ul familiei)
   - Categorie e din lista fixă

## Done state

DB local va avea toate 14.745 params cu:
- `explicatie` non-empty cu LaTeX pe formule
- `influenteaza` CSV populat unde aplicabil
- `categorie` din lista fixă

Apoi: upload DB la server prin `https://pif.iupif.org/admin/db-upload`.

**Frontend deja randează KaTeX + chip-uri "Influențează" / "Influențat de"** — totul așteaptă DB-ul cu explicații.
