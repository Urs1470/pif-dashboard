# 2026-10-01 — Torqa: imaginea completă și tokenul de dispozitiv

**Context.** Ion a făcut din Tasks.org 15.12 un fork privat, Torqa (repo `Urs1470/torqa`), care
înlocuiește interfața dashboard-ului pe telefon și pe desktop: „platforma noastră este bună, însă aș
vrea ceva mai profi totuși, mai ales pe mobil". Serverul Flask rămâne sursa datelor, fiindcă de el
depind skill-ul `proiect`, vault-ul, backup-urile și `/calc`. Torqa ține o copie locală (merge și
fără rețea) și se sincronizează cu serverul.

**Ce s-a decis (faza 2a a fork-ului).**

1. **`GET /api/sync/snapshot`** dă tot ce se sincronizează într-o cerere: proiectele, taskurile
   (și cele făcute), subtaskurile și taskurile globale din ambele sfere. Torqa compară imaginea cu
   copia locală; ce lipsește din imagine s-a șters pe server. Motivul: ștergerile sunt definitive
   (`DELETE FROM`), deci un jurnal de schimbări ar fi cerut tombstone-uri, adică schemă nouă. Datele
   sunt puține (în copia locală din 2026-08-26: 21 de proiecte, 37 de taskuri, 9 globale), deci
   imaginea întreagă e mai ieftină decât jurnalul și nu atinge schema.
2. **`tasks[].viu`** poartă regula din Astăzi (`TASK_PROIECT_VIU`): taskul unui proiect închis
   contează doar dacă e născut după închidere. Torqa nu reface regula.
3. **Scrierile trec prin rutele obișnuite.** Bifarea unui task recurent naște apariția următoare pe
   server (cu săritul peste weekend). Torqa trimite doar „done” și nu mută singur data, altfel ar
   apărea dubluri: Tasks.org reprogramează același task, serverul creează unul nou.
4. **`PIF_DEVICE_TOKEN`**, un al doilea Bearer, pentru Torqa. Refuzat pe restore, backup, admin,
   deploy, upload de APK și cheia vault-ului (`DEVICE_TOKEN_DENIED` în `utils.py`). Motivul:
   `PIF_API_TOKEN` deschide și `/api/restore` și `/api/admin/db-dump`, iar un telefon pierdut cu el
   înseamnă baza în mâna altcuiva. Lista e de refuz, nu de permisiune: fazele următoare ale Torqa
   (proiecte, perioade, calendar, wiki) folosesc rutele existente fără să mai atingă garda.

**Verificat.** `teste/test_sync.py`, 8 teste: imaginea întreagă, câmpurile, `viu`, 401 fără token,
tokenul de dispozitiv refuzat pe toate cele 9 rute. Garda e probată pe funcția de verificare, nu pe
rute: o gardă stricată ar fi rulat `git reset --hard` prin `/api/deploy` chiar în clona testului.
Cu lista golită, 2 teste pică.

**Ce rămâne.** Tokenul se pune o dată în `/etc/pif-dashboard.env` pe server (Ion), apoi
`sudo systemctl restart pif-dashboard`. Valoarea stă în vault, lângă `PIF_API_TOKEN`
(`wiki/job/pif-dashboard.md`), nu în repo.
