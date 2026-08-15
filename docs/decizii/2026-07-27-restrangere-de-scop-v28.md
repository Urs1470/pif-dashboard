# Restrangere de scop (v28, 2026-07-27)

## Din CLAUDE.md

Dashboard-ul nu mai dubleaza wiki-ul si manualele. Ce a plecat si de ce:

- **parametri_master** (14.813 randuri) si **fault_codes** (3.851) — catalog de referinta fara nicio
  legatura cu proiectele. Parametrii si codurile de eroare se iau din manual sau prin Cowork, unde
  ai sursa citabila.
- **echipamente** (26 randuri, in 4 din 20 de proiecte) — reintroducere manuala a ceva ce skill-ul
  `drive-backup` extrage determinist din `.dcparamsbak` / STARTER, direct in wiki.
- **atasamente** (30 fisiere) — backup-urile brute stau in vault, la `raw/projects/<slug>/`.
  Fisierele urcate NU au fost sterse de pe disc; doar tabela.

Ce **nu** s-a atins: Calculatorul, inclusiv `/api/import-abb-multi/preview` si
`/api/import-archive/preview` — ele parseaza un backup de drive fara sa atinga DB-ul si alimenteaza
placuta motorului. Blueprint-ul `obsidian.py` ramane: el tine sincronizarea wiki <-> dashboard.

Arhiva completa a datelor sterse: `raw/pif-dashboard/2026-07-27-inainte-de-v28/` in vault
(JSON + CSV per tabela, snapshot integral, seed-uri, README cu procedura de recuperare).

## Din MEMORY.md

- **2026-07-27 — v28: restrangere de scop.** Dashboard-ul nu mai dubleaza wiki-ul si manualele.
  Sterse: `parametri_master` (14.813 randuri), `fault_codes` (3.851), `echipamente` (26, in 4 din 20
  de proiecte), `atasamente` (30 fisiere). Sterse si: `blueprints/parametri.py`, paginile
  `Params.svelte` / `Notes.svelte`, `AttachmentsTab`, `EquipmentFormModal`, `AttachmentPreview`,
  `data/fault_codes/` (3,84 MB seed), `scripts/enrich_params_from_backup.py`, endpoint-urile
  `/api/admin/enrich-params` + `/api/admin/bulk-add-params`, sectiunea „Audit DB Parametri" din
  Admin, sectiunea de echipamente din exportul PDF si Markdown.
  **Motiv:** catalogul de 18k randuri nu avea nicio legatura cu proiectele — parametrii si codurile
  de eroare se iau din manual (sursa citabila), backup-urile de drive stau brute in vault unde le
  citeste `drive-backup`.
  **NU s-a atins Calculatorul.** Atentie: el depinde de `/api/import-abb-multi/preview` si
  `/api/import-archive/preview` — le-am sters din greseala si le-am repus; `scripts/parse_params/`
  trebuie sa ramana. Tabul „Din proiect" din modalul de import a disparut (depindea de tabela
  `echipamente`); tabul de incarcat fisier ramane si merge fara login.
  **Verificat:** migratia ruleaza curat pe DB local (v27 -> v28, 4 tabele + 6 indexuri sterse),
  `/api/import-abb-multi/preview` parseaza un `.dcparamsbak` real (70 parametri, placuta motor
  80 A / 686 V / 75 kW / 2960 rpm), build trece, fara erori in consola.
  **Arhiva:** `raw/pif-dashboard/2026-07-27-inainte-de-v28/` in vault (JSON + CSV per tabela,
  snapshot integral, seed-uri fault codes, parsere, README cu procedura de recuperare). `raw/` e
  gitignored — arhiva e propagata prin Google Drive, nu prin git.
  **Migrare echipamente:** cele 13 de la Retrofit FML3 -> `wiki/job/projects/continental-fml3/`
  (`backup-<drive>.md` + `backups-index.md`). Restul erau deja acoperite in wiki, cu mai multi
  parametri decat in DB. Bonus: recuperat `FAA.dcparamsbak` (backup final) din atasamentul
  `Backupuri Multidrive.zip` — nu exista in vault; nota `backup-FAA.md` ramane de generat.
