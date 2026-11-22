# 2026-11-22 Backlog-ul evolve în System: blocul `backlog` și închiderea prin deciziile existente

Ion a aprobat un al patrulea tab în pagina System din Torqa, „Backlog”: itemii E-NNN deschiși din ledger-ul evolve, fiecare cu „Give to
Claude”, „Discuss” și „Close”. Partea de server: contractul `/api/sistem` v1.3, aditiv (Torqa 1171 și APK-ul instalat citesc fără erori).
Codul: `blueprints/sistem.py`; testele: `teste/test_sistem_backlog.py`. Partea din Knowledge: `tools/sistem-snapshot.py`
(`references/decizii/2026-11-22-backlog-in-system.md`).

## De ce așa

- **Prin snapshot, nu printr-un cititor nou.** Ledger-ul stă pe laptop-server; `evolve-fold.service` trimite deja snapshot-ul serverului
  după fold. Blocul `backlog` din el e singura cale nouă de date: fără rută nouă, fără tabelă, fără migrare (fișierul `server.json`
  se rescrie întreg, ca până acum).
- **Închiderea prin deciziile existente.** `POST /api/sistem/decizie` primește id `backlog:E-NNN`; consumatorul din Knowledge
  (`--consuma-decizii`, rulat înaintea fold-ului) face `evolve.py close`. Backlog-ul nu are opțiuni puse de sursă: cele trei sunt fixe
  aici (`OPTIUNI_BACKLOG`), iar clientul tot nu poate trimite o comandă, ci doar alege dintre ele.
- **Corpul PUT urcă de la 1 la 2 MiB.** 300 de itemi cu cele mai lungi texte, în caractere de 3 octeți, fac 894 KiB doar pentru bloc
  (măsurat în `test_300_de_itemi_cu_texte_maxime_incap_in_limita_corpului`); cu cei 200 de itemi obișnuiți ai snapshot-ului, 1 MiB nu mai
  ajungea în cazul cel mai rău. Datele reale (54 de itemi) sunt cu un ordin de mărime sub.

## Contractul v1.3

**Snapshot** (`PUT /api/sistem/sursa/server`, câmp opțional `backlog`; la oricare altă sursă: 400, `backlog: doar in snapshot-ul sursei server`):

```
backlog: {generat: "AAAA-LL-ZZTHH:MM:SSZ", total: int, asteapta_ion: int, cel_mai_vechi_zile: int, itemi: [{
  id: "E-264"            # ^E-\d{1,5}$, unic în listă
  zona: "dashboard"      # 1-40
  titlu: "…"             # 1-200, fără markdown
  descriere: "…" | ""    # ≤400, fără markdown
  creat: "AAAA-LL-ZZ" | null,  varsta_zile: int ≥0 | null
  etichete: [..]         # ≤8, fiecare 1-40
  asteapta_ion: bool
  masina: "server" | "ionpc" | "pc-job" | null
  repo: "torqa-sp" | null }]}      # ≤300 de itemi
```

Toate câmpurile sunt obligatorii (cele cu `| null` pot fi null, dar nu lipsi); un câmp în plus sau un tip greșit dă 400 cu calea câmpului și
snapshot-ul curent rămâne. `total` ≥ lungimea listei (lista se taie la 300, totalul rămâne cel real) și `asteapta_ion` ≤ `total`.
Corpul PUT: până la 2 MiB (413 peste).

**Citire** (`GET /api/sistem`): cheia `backlog` la nivelul de sus, blocul sursei `server` sau `null` când serverul n-a trimis niciunul.
Un item cu decizie de închidere în așteptare (neconsumată, neanulată; preluată de consumator inclusă) nu se mai arată, iar `total` și
`asteapta_ion` scad cu el (`cel_mai_vechi_zile` se reface din ce rămâne când lista e completă): fără asta itemul ar reapărea până la
următorul PUT al serverului. Anulată sau consumată cu `stare: fail`, reapare.

**Închidere** (`POST /api/sistem/decizie`, corpul existent `{id, optiune, text}`; `text` e câmpul liber de până acum, aici ≤400):

| optiune | label în istoric | verdictul din ledger |
|---|---|---|
| `inchide-implementat` | Close as done | `implementat`, nota = `--dovada` |
| `inchide-respins` | Close as not needed | `respins`, nota = `--motiv` |
| `inchide-duplicat` | Close as duplicate | `fara-obiect`, `--motiv "duplicat: <nota>"` |

- 201 `{ok, uid}`; rândul are `titlu` = `E-264 · <titlul>`, `sursa` = `server`.
- 400: id care nu e `backlog:E-NNN`, optiune în afara celor trei, `text` peste 400 de caractere, câmp necunoscut. 409: itemul nu e (sau nu mai
  e) în backlog-ul stocat; același 409 ca la un item obișnuit dispărut. 401 fără token.
- Retrimiterea: decizia în așteptare pe același id se înlocuiește (ultima câștigă), deci o cerere repetată nu dublează; una deja preluată dă 409.
- Consumatorul rulează `evolve.py close`; un item deja închis (ledger sau inbox) se consumă `ok`, fără efect. Itemul iese din backlog la
  fold-ul și PUT-ul din aceeași trecere (15 min).

## „Give to Claude” și „Discuss”

Fără schimbare de server: sunt mesaje obișnuite la `POST /api/asistent/fir` cu `ref: {tip: "item", id: "backlog:E-264", titlu, sursa, masina}`
și, la „Give to Claude”, `tinta`. Limitele din `_ref` (`blueprints/asistent.py`): `id` 1-160 de caractere, fără caractere de control;
`titlu` 1-**140** (peste: 400); `sursa` 1-**40** (peste: 400); `masina` `server|pc-job|ionpc` sau lipsă; `tinta` `auto|server|pc-job|ionpc`;
`text` ≤2000. Titlul din backlog are până la 200 de caractere, deci Torqa îl taie la 140 înainte să-l pună în `ref`. Verificat în
`RefulBacklogInFirul`.

Rollback: întâi se scoate blocul din Knowledge (`construieste_backlog` în `tools/sistem-snapshot.py`), apoi `git revert` aici. În ordinea
inversă, validatorul vechi (strict) respinge cheia `backlog`: PUT-ul serverului dă 400, iar `server.json` rămas cu bloc nu mai trece
validarea, deci sursa `server` apare „report unreadable” până la primul PUT fără bloc.
