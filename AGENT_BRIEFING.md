# Briefing pentru sesiuni Claude spawned

Template scurt de copy-paste pentru orice sesiune Claude nouă care intră să lucreze la
PIF Dashboard. Ion alege scope-ul, copiază blocul de mai jos, înlocuiește `<SCOPE>` și
`<TASK>`, îl dă agentului ca prim mesaj.

> Context: aplicația e **backend-ul Torqa** — Flask + SQLite, API-ul `/api/*`, loginul cu PIN
> și Torqa web la `/torqa/` (build Angular urcat pe server). Interfața veche (SPA Svelte 5,
> calculatorul, planul de departament, notificările push) a fost retrasă pe 2026-10-03 și nu
> mai există în arbore; ultima stare cu ea e eticheta git `inainte-de-retragere`. Detaliile
> complete sunt în `CLAUDE.md`.

---

## Template (copy-paste, înlocuiește slot-urile)

```
Lucrezi la PIF Dashboard, in repo-ul din directorul curent (pe PC-ul de acasa
`C:\Users\Ion Ursu\Repos\pif-dashboard`, pe cel de job alta cale — nu presupune,
verifica cu `git rev-parse --show-toplevel`).
Tu esti sesiunea "<SCOPE>". Alte sesiuni Claude pot lucra in paralel pe ACELASI worktree
(deci acelasi .git si acelasi index git).

INAINTE de orice modificare:
1. Citeste CLAUDE.md (instructiuni de proiect, arhitectura, invarianti, verificatoare,
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

Verificare (daca atingi cod):
- `python scripts/verifica.py --atinse <fisierele tale>` ruleaza exact ce cer ele (lint,
  teste JS si Python, probele de API); `python scripts/verifica.py` le ruleaza pe toate.
- Serverul n-are interfata proprie: nu exista frontend de construit si de verificat in browser.
  Torqa (telefon, desktop, web) sta in repo-ul lui; aici se schimba doar API-ul pe care il citeste.

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
| **API backend** | `blueprints/*.py` |
| **Schemă / migrații** | `database.py` (anunță prin commit message clar) |
| **Torqa web / APK (urcare, versiuni)** | `blueprints/torqa_web.py`, `blueprints/app_update.py` |
| **Login, sesiune, CSRF, tokenuri** | `app.py`, `utils.py`, `csrf.py`, `templates/login.html` |
| **Teste și verificatoare** | `teste/`, `scripts/verifica.py`, `scripts/test_suite.py`, `.claude/hooks/gate.py` |
| **Memory Ion** (`~/.claude/.../memory/*`) | **NU atinge** — local Ion |

Hub-uri cu risc de coliziune (fii mic + rapid + `pull --rebase`): `app.py`, `database.py`,
`utils.py`, `scripts/verifica.py`.

## Exemple de scope

```
<SCOPE> = Backup-Restore
<TASK> = Lucreaza la backup/restore din blueprints/admin.py. Adauga teste in teste/ pentru
ce schimbi. NU atinge database.py (schema) si NU rula restore pe baza de lucru.
```

```
<SCOPE> = API-Taskuri
<TASK> = Imbunatateste rutele de taskuri din blueprints/tasks.py (agenda, recurenta). Adauga
teste in teste/ pentru ce schimbi. NU atinge database.py (schema) fara sa anunti in commit.
```

---

## De ce funcționează

- **CLAUDE.md** ține contextul stabil (arhitectură, invarianți, convenții) —
  agenții le citesc o dată per sesiune; `docs/memory/` dă locațiile exacte.
- **Domain map** previne două sesiuni să atingă același fișier concomitent.
- **Index git partajat**: pe același worktree, `git add -A` al unei sesiuni poate înghiți
  munca alteia → stage explicit + push des.
- **`pull --rebase` înainte de push** prinde modificările aterizate între read și write —
  fără el apar coliziunile „lost work”.

*Documentul ăsta e în repo. Update-l când stadiul se schimbă semnificativ.*
