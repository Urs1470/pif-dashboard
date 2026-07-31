# Briefing pentru sesiuni Claude spawned

Template scurt de copy-paste pentru orice sesiune Claude nouă care intră să lucreze la
PIF Dashboard. Ion alege scope-ul, copiază blocul de mai jos, înlocuiește `<SCOPE>` și
`<TASK>`, îl dă agentului ca prim mesaj.

> Context: aplicația e un **SPA Svelte 5** (build Vite în `static/dist/`) + backend Flask.
> Vechiul app vanilla-JS multi-fișier (desktop `app.js` + mobile `/m`) a fost eliminat
> 2026-06-17. Detaliile complete sunt în `CLAUDE.md`.

---

## Template (copy-paste, înlocuiește slot-urile)

```
Lucrezi la PIF Dashboard, repo C:\Users\ion.ursu\pif-dashboard pe Windows-ul lui Ion.
Tu esti sesiunea "<SCOPE>". Alte sesiuni Claude pot lucra in paralel pe ACELASI worktree
(deci acelasi .git si acelasi index git).

INAINTE de orice modificare:
1. Citeste CLAUDE.md (instructiuni de proiect, arhitectura SPA, design system,
   protocol anti-coliziune). Pentru locatii de cod foloseste docs/memory/CODE_MAP.md si
   docs/memory/API_MAP.md (nu cauta orbeste in fisiere mari).
2. Ruleaza:
     git fetch origin master
     git pull --rebase origin master
     git status        # trebuie clean
     git log --oneline -10
   Daca alta sesiune a comis foarte recent (<5 min), citeste-i commit-urile intai.

IN TIMPUL lucrului:
- Atinge DOAR fisierele din scope-ul tau.
- NU folosi `git commit -a` / `git add -A` (indexul e partajat cu alte sesiuni) — stage
  explicit doar fisierele tale.
- Daca vezi alta sesiune scriind activ (fisiere modificate la secunda), opreste-te,
  las-o sa commit-eze, apoi `git pull --rebase`.

INAINTE de fiecare push:
     git fetch origin master
     git pull --rebase origin master
     # rezolva orice conflict manual, NU forta push
     git push origin master
   (push-ul declanseaza webhook-ul de auto-deploy pe pif.iupif.org)

Commit messages:
- Scope clar: "<SCOPE>: ce ai facut".
- Identity: author Ion (Urs1470, default din git config), co-author Claude.

Frontend (daca atingi UI):
- SPA Svelte 5 in frontend/src/. Foloseste libraria de componente components/ui/
  (Button, Select, Modal, DatePicker, SolidIcon, Toast, ...) — NU stiluri ad-hoc.
- Culori/spacing DOAR din frontend/src/styles/tokens.css (paleta Bento: dark warm #12100d +
  amber #ffb454; text pe fill amber = ink --accent-text #1a1206). Iconite: <SolidIcon> pentru
  nav/feature, Lucide outline pentru afordante mici.
- Dupa modificari de cod previewabile, ruleaza dev server-ul si verifica in browser.

Comunicare cu Ion:
- Raspunsuri scurte, directe, in romana. Push imediat dupa fiecare felie functionala.

---

TASK-UL TAU:

<TASK>
```

---

## Domain map (cine atinge ce, ca să nu vă ciocniți)

| Zonă | Fișiere |
|---|---|
| **UI / pagini** | `frontend/src/pages/*`, `frontend/src/components/*` |
| **Stores / logică client** | `frontend/src/stores/*.svelte.js`, `frontend/src/lib/*` |
| **Design tokens / CSS global** | `frontend/src/styles/*` (hub — coordonează) |
| **API backend** | `blueprints/*.py` |
| **Schemă / migrații** | `database.py` (anunță prin commit message clar) |
| **Import parametri** | `scripts/parse_params/*.py` |
| **Memory Ion** (`~/.claude/.../memory/*`) | **NU atinge** — local Ion |

Hub-uri cu risc de coliziune (fii mic + rapid + `pull --rebase`): `App.svelte`,
`lib/router.svelte.js`, `stores/*`, `styles/tokens.css`/`global.css`, `app.py`, `database.py`.

## Exemple de scope

```
<SCOPE> = Import-Convertoare
<TASK> = Lucreaza la parserele de parametri din scripts/parse_params/ (abb, danfoss,
lenze, siemens). Endpoint relevant in blueprints/parametri.py. NU atinge frontend/.
```

```
<SCOPE> = UI-Proiecte
<TASK> = Imbunatateste pagina de proiecte. Domeniu: frontend/src/pages/Projects.svelte,
ProjectDetail.svelte + components/projects/*. Foloseste components/ui/ existente si
tokens.css. NU atinge blueprints/ sau database.py.
```

---

## De ce funcționează

- **CLAUDE.md** ține contextul stabil (arhitectură, design system, convenții) —
  agenții le citesc o dată per sesiune; `docs/memory/` dă locațiile exacte.
- **Domain map** previne două sesiuni să atingă același fișier concomitent.
- **Index git partajat**: pe același worktree, `git add -A` al unei sesiuni poate înghiți
  munca alteia → stage explicit + push des.
- **`pull --rebase` înainte de push** prinde modificările aterizate între read și write —
  fără el apar coliziunile „lost work”.

*Documentul ăsta e în repo. Update-l când stadiul se schimbă semnificativ.*
