# Briefing pentru agenții Claude spawned

Template scurt de copy-paste pentru orice sesiune Claude nouă care intră să lucreze
la PIF Dashboard. Ion alege scope-ul, copiază blocul de mai jos, înlocuiește
`<SCOPE>` și `<TASK>`, îl dă agentului ca prim mesaj.

---

## Template (copy-paste, înlocuiește slot-urile)

```
Lucrezi la PIF Dashboard, repo D:/Projects/pif-dashboard pe Windows-ul lui Ion.
Tu ești sesiunea "<SCOPE>" (ex: PV, Import-Convertoare, Equipment-Card, Budget,
Audit, etc.). Alte sesiuni Claude lucrează în paralel pe același worktree.

ÎNAINTE de orice modificare:
1. Citește integral HERMES.md din root-ul repo-ului. Conține contextul,
   design system-ul, conventiile Ion, domain map per sesiune și protocolul
   anti-coliziune. NU sări peste el.
2. Rulează:
     cd D:/Projects/pif-dashboard
     git fetch origin master
     git pull --rebase origin master
     git status        # trebuie clean
     git log --oneline -10
   Dacă ultimul push e foarte recent (<5 minute) de la altă sesiune, așteaptă 30s.

ÎN TIMPUL lucrului:
- Atinge DOAR fișierele din domain-ul tău (vezi HERMES.md → "Cine atinge ce").
- Pe shared files (templates/index.html, templates/mobile.html, static/app.js,
  static/mobile.js) wrappează integrarea ta cu marker BEGIN/END:
     <!-- BEGIN: <SCOPE> (owned by spawned-<scope> session) -->
     ... codul tău ...
     <!-- END: <SCOPE> -->
  Asta semnalează Claude main + altor sesiuni să NU șteargă blocul.

ÎNAINTE de fiecare push:
     git fetch origin master
     git pull --rebase origin master
     # rezolvă orice conflict manual, NU forța push
     git push origin master

Commit messages:
- Fără diacritice (PowerShell incurcă heredoc).
- Scope clar: "<SCOPE>: ce ai facut".
- Identity Urs1470 (default), co-author: Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

Comunicare cu Ion:
- Răspunsuri scurte, directe, în română.
- Push imediat după fiecare felie funcțională → testează pe live (https://pif.iupif.org/).
- Înainte de feature UI complexă: propune mockup HTML standalone întâi.

---

TASK-UL TĂU:

<TASK>
```

---

## Exemple gata-de-trimis pentru sesiunile curente

### ~~PV generation~~ (ELIMINAT 2026-06-05)

> Generarea de procese verbale (PIF + Service) a fost ștearsă complet din dashboard:
> `services/pv_generator.py`, `static/pv-modal.js`, `templates/pv/*.docx`, rutele
> `/api/proiecte/<id>/pv/*` și butoanele din UI nu mai există. Fluxul actual de
> raportare e prin Cowork debrief → import (`/api/import/debrief`).

### Import parametri convertoare

```
<SCOPE> = Import-Convertoare
<TASK> = Implementează tool-ul de import parametri modificați per echipament,
cu parser separat pentru Danfoss (text), Lenze (PDF), Siemens (PDF). ABB rămâne
TBD. Domain: scripts/parse_params/*.py, endpoint /api/echipamente/<id>/import-params
în app.py. Sample-urile Ion: D:/Downloads/Changed parameters danfoss.txt,
exemplu lenze.pdf, exemplu starter.pdf. Pe shared files, wrappează butonul
"Import params" din modal echipament cu BEGIN/END Import.
```

### Sprint UI (Claude main)

```
<SCOPE> = Sprint-UI
<TASK> = Continuă pachetul de fix-uri UI/UX semnalat de Ion (vezi conversația
principală). Domeniul tău e maximal pe shared files: templates/index.html,
templates/mobile.html, static/app.js, static/mobile.js, static/service-worker.js,
templates/login.html. NU atinge fișiere wrappuite cu BEGIN/END de altă sesiune
fără să discuți cu Ion.
```

### Audit DB (Hermes-class agent)

```
<SCOPE> = Audit
<TASK> = Continuă auditul parametrilor DB față de PDF-urile manualelor. Rulează
--all pentru toate familiile, validează parser-ele per producător, raportează
mismatch-urile. Domain: scripts/audit_pdf.py, scripts/audit_reports/*. NU atinge
templates/ sau static/. Pe laptop-server păstrează git worktree clean între
sesiuni — webhook-ul de deploy crapă 500 când pull-ul nu poate avansa.
```

---

## De ce funcționează

- **HERMES.md** ține contextul stabil (design system, paletă, convenții) —
  agenții îl citesc o singură dată per sesiune.
- **Domain map** previne două sesiuni să atingă același fișier concomitent.
- **Marker BEGIN/END** semnalează ownership inline, vizibil în diff.
- **pull --rebase înainte de push** prinde modificările care au aterizat între
  read și write — fără asta apar coliziunile tip "lost work" (a se vedea
  commit `245cf33` din istoric).

Documentul ăsta și HERMES.md sunt în repo. Update-le când stadiul se schimbă
semnificativ.
