# 2026-11-25 Bifa manuală pe materiale: `PUT /api/materiale/bifa`, stocată în `app_settings`

Ion vrea, în pagina Materials din Torqa, să bifeze că un articol „a ajuns la destinație” sau e „livrat”, peste ce
spune colectorul (BC): marfa poate fi pe șantier înainte ca recepția să apară în BC. Până acum stările veneau doar
din snapshot-ul colectorului (decizia 2026-11-06), iar `/api/materiale` era read-only pentru tokenul de dispozitiv.

- **Contractul (fix, Torqa se scrie în paralel pe el).** `PUT /api/materiale/bifa`, corp
  `{"proiect_id", "cod_bc", "stare": "la_destinatie" | "livrat" | null}`; `null` scoate bifa. Răspuns 200
  `{"ok": true, "bifa": {"stare", "la": "<ISO UTC cu Z>"} | null}`. 400 cu mesaj pe câmp (`stare: una din
  la_destinatie|livrat sau null`; lipsa câmpului `stare` e 400, nu „scoate bifa”), 413 peste 16 KB, 409 fără
  snapshot curent sau când proiectul / `cod_bc` nu sunt în `proiecte[].materiale` din snapshot-ul curent (și la
  `null`). `cod_bc` se potrivește exact, ca în snapshot. Câmpurile în plus din corp se ignoră.
- **Cine scrie.** `login_required`: sesiune (cu CSRF), `PIF_API_TOKEN` și tokenul de dispozitiv. Ruta nu e în
  `DEVICE_TOKEN_READ_ONLY` (`utils.device_token_denied` e exact-match pe `/api/materiale`), deci Torqa scrie
  bifa, iar `PUT /api/materiale` rămâne al colectorului (dispozitivul primește 401, ca înainte).
- **De ce `app_settings` și nu snapshot-ul.** Snapshot-ul se înlocuiește la fiecare colectare și stă în afara
  backup-ului; o bifă pusă în el ar dispărea la următoarea rulare (08:00 / 13:00). Cheia `materiale_bife`
  (JSON `{proiect_id: {cod_bc: {stare, la}}}`) intră în backup și restore o aduce înapoi (nu e în `CHEI_PROTEJATE`,
  care ține doar `push_*`; verificat cu un test de dus-întors). Fără schemă nouă, fără migrare. Citirea și scrierea
  sunt într-o tranzactie (`BEGIN IMMEDIATE`), ca două bife simultane (2 workeri) să nu se strice între ele; baza
  ocupată dă 503.
- **Idempotent.** Aceeași stare de două ori lasă bifa neatinsă, inclusiv `la` (o reîncercare după un răspuns
  pierdut nu mută ora); altă stare înlocuiește bifa cu ora nouă; `null` pe un articol fără bifă e tot 200.
- **Cum o aplică `GET /api/materiale`.** Pe fiecare rând din `proiecte[].materiale` cu bifă: `bifa: {stare, la}`
  (rândurile fără bifă n-au cheia). Dacă nivelul bifei e peste starea colectorului (livrat > la_destinatie > orice
  altceva, inclusiv `null`), rândul primește `stare` = bifa, `stare_colector` = starea colectorului și `intarziat`
  = false; atunci `rezumat` se ajustează: `pe_stare` (scade vechea stare, un contor ajuns la 0 dispare, ca la
  colector; crește cea nouă), `intarziate` (scade dacă rândul era întârziat), `dupa_start` / `aproape_start`
  (scad dacă rândul era marcat), iar `urmatoarea` trece la următorul rând în așteptare dacă ea era rândul bifat.
  Colectorul ajuns deja la nivelul bifei sau peste: `stare` rămâne a lui, `bifa` apare tot. Scoaterea bifei
  readuce starea colectorului fără altă acțiune: snapshot-ul de pe disc nu e atins niciodată. Bifele pentru
  rânduri ieșite din snapshot rămân stocate și reapar dacă rândul revine.
- **„Următorul rând în așteptare” = definiția colectorului** (`$viitoare` din `tools/materiale-colector.ps1`):
  stare în `in_tranzit|confirmat|comandat|din_stoc|necomandat`, cu `termen`, neîntârziat, cel mai mic `termen`.
  Un rând întârziat nu devine „următoarea”, ca nici la colector. Aceeași listă dă și `ultima_asteptata`, pe care o
  recalculez când o bifă schimbă un rând (în plus față de contract; fără `ultima_asteptata` în rezumat nu se
  atinge).
- **Alertele de livrare.** Cu `sursa.alerte = "server"`, `calculeaza` primește bifele: un articol bifat primește
  `fata_de_start` null și nu intră în `livrare_dupa_start` / `livrare_aproape_start`; `rezumat.dupa_start` /
  `aproape_start` îl exclud. Snapshot-ul se scrie tot cu starea colectorului. Alerta din `alerte[]` și taskul ei
  se refac la colectarea următoare, nu pe loc (un task deja creat nu se șterge niciodată, ca până acum); pe rând,
  `fata_de_start` și contoarele din `rezumat` se ajustează imediat, la GET.
- **Ce nu face.** Nu atinge `lm[].pozitii[].stare` (copia stării din material, cheiată prin alias și nu mereu prin
  același `cod_bc`) și nu schimbă `termen` / `termen_tip` ale rândului bifat.
- **Cod:** `blueprints/materiale.py` (`put_bifa`, `aplica_bife`, `citeste_bife`), `blueprints/materiale_alerte.py`
  (`_bifat`, `NIVEL_BIFA`), teste în `teste/test_materiale_bifa.py` (37: PUT ok / null / 400 / 409 / 413 / token,
  GET peste colector, colectorul deja la nivel, persistența peste un PUT nou, backup și restore, alertele).
