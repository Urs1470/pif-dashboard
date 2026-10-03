# Verificatoarele — ce pazeste fiecare si capcanele lor de masurare

> Mutat din `CLAUDE.md` la restructurarea din 2026-09-15; refacut dupa auditul testelor din
> 2026-09-28 (`docs/decizii/2026-09-28-verificatoarele-un-banc-si-trei-trepte.md`) si taiat pe
> 2026-10-03, odata cu interfata veche: au plecat build-ul, lintul SPA-ului, auditurile de
> design si de contrast, `smoke_ui`, toate auditurile cu browser si bancul lor de Chromium.
> Povestea fiecaruia, cu tot cu cod, sta in eticheta `inainte-de-retragere`
> (`git show inainte-de-retragere:docs/verificatoare.md`). Se citeste cand lucrezi LA un
> verificator sau cand unul raporteaza ceva ciudat.

## Harta

Un singur punct de intrare, `python scripts/verifica.py` (= `--rapid`); poarta
(`.claude/hooks/gate.py`) ruleaza, din aceeasi lista, doar ce cer fisierele atinse. Timpii sunt
masurati pe masina de dezvoltare, 2026-10-03.

| pas | ce pazeste | datele | timp |
|---|---|---|---|
| `lint` (`scripts/lint.py`) | ce e SCRIS si nu ajunge sa se intample: nume nedefinit, import ramas in urma, variabila moarta (pyflakes) | — | ~2 s |
| `unitare_js` (`teste/js/*.test.mjs`) | scriptul din `templates/login.html` (unde te duce dupa PIN; formularul si tema se leaga din script, fara handlere sau stiluri inline, ca sa treaca de CSP) si `static/service-worker.js` (se retrage singur, nu atinge `ngsw:`) | — | <1 s |
| `unitare_py` (`teste/`, `unittest`) | functiile pure, garzile, schema pe o baza goala, rutele prin clientul de test (APK, Torqa web, login, sync, notele din vault si tokenul de dispozitiv, IP-ul clientului, CSP), backup apoi restore pe toate coloanele, `requirements.txt` fata de importuri, `test_retragere` | baza noua | ~25-40 s |
| `test_suite` (`scripts/test_suite.py`) | invariantii vazuti prin HTTP: sfera, ce trimite un proiect inchis, backup-ul fara secrete | baza noua | ~4 s |

Probele de HTTP stau pe **`scripts/banc.py`**: serverul pe un port liber, baza de unica folosinta
(stearsa la iesire), raportul. **Coduri de iesire, aceleasi peste tot:** 0 curat, 1 abatere in
aplicatie, 2 instrumentul n-a ajuns la verdict (server mort, `requests` lipsa, proba a crapat pe
drum). **Vocabularul:** OK · PICA (se numara) · NOTA (informatie) · SARI (nu se aplica aici, cu
motiv) · ACCEPTAT (abatere tinuta cu buna stiinta, cu motiv).

Cerinte, doar pe masina de dezvoltare: `pip install pyflakes requests` si `node` in PATH (fara
npm). Un `node` care lipseste e un ESEC al pasului `unitare_js`, nu un pas sarit.

## Capcanele de masurare (fiecare a costat deja o data)

**O proba scrie doar in baza ei.** Probele de backup si de push din `test_suite` scriau direct in
`PIF_DB_PATH` sau, implicit, in `pif_dashboard.db` — iar curatenia lor stergea TOATE cheile
`push_*`. Rulate pe server, ar fi oprit notificarile fara niciun semn. Acum `test_suite` isi
porneste serverul pe o baza noua si scrie doar in `APP.db`. Partea de push a plecat pe
2026-10-03; proba de backup a ramas, fiindca randurile `push_*` (cheia VAPID privata) sunt tot in
baza, iar backup-ul nu are voie sa le scurga.

**Un test de worker trebuie sa poata PICA.** `static/service-worker.js` nu e modul si nu exporta
nimic: testul il ruleaza intr-un context `vm`, cu un `self` de mana. Un test care trece pe un
worker stricat ar fi mai rau decat niciunul, deci la scrierea lui au fost provocate pe rand sapte
defecte — un handler de `fetch` ramas, `ngsw:` in lista de cache-uri sterse, o fereastra
`/torqa/` reincarcata, fragmentul pastrat la reincarcare, dezinregistrarea sarita,
`includeUncontrolled`, `skipWaiting` lipsa — si fiecare a picat cel putin un test. Testul cu `vm`
nu arata insa ce face un browser: pe 2026-10-03 worker-ul a fost incercat intr-un Chromium real,
cu worker-ul vechi inregistrat si cu doua servere pe aceeasi origine (vechi, apoi nou). Doua lucruri
iesite de acolo: `WindowClient.navigate()` reincarca si cu fragment in adresa, iar `client.url` are
fragment doar daca documentul a fost CREAT cu el (un `#` pus dupa incarcare nu apare); redirectul de la
`/` pastreaza fragmentul, deci fara scoaterea lui o fereastra creata cu `/#/tasks` ajunge la
`/torqa/#/tasks`.

**`lint.py` prinde ce e SCRIS si nu ajunge sa se intample.** Nu „ce crapa" si nu „ce nu
incape": o variabila locala moarta (prima rulare, 2026-08-23, in `blueprints/projects.py`), un
import care nu se mai rezolva. E si plasa dupa o stergere: un modul scos lasa importuri in urma
(la retragerea din 2026-10-03: `login_required`, `urlparse`, `send_from_directory`), iar pyflakes
le arata imediat. Linia de baza e CURATA, deci orice abatere e noua.

**`teste/` si `teste/js/` au inlocuit verificari care nu puteau pica.** Pana pe 2026-09-28 partea
„statica" din `test_suite` scana fisiere sterse din iunie si copia locala a bazei, deci iesea
verde oricum. Primele teste scrise in locul ei au gasit pe loc o migrare care pierdea un index la
prima pornire (schema difera intre prima si a doua pornire a serverului).

**`test_retragere` e o garda, nu o proba de comportament.** Tine la 404 rutele si fisierele plecate
(`/calc`, `/assets/`, `/api/push/*`, `/api/me`, `/api/clienti*`, `/api/agenda/*`, ...), ca un `git checkout`
din eticheta `inainte-de-retragere` sau un merge prost sa apara ca test picat, nu ca o suprafata veche care
renaste in tacere. Mai tine o garda de clasa: nicio ruta `/api` nu raspunde fara credentiale in afara de
`healthz` (doua previzualizari de import au ramas fara login dupa calculatorul public care le folosea). Daca restaurezi interfata veche cu buna
stiinta, sterge-i testele odata cu ea.

**Un test de dus-intors trebuie sa poata PIERDE coloana.** `test_backup_restore` umple fiecare coloana cu o
valoare DIFERITA de cea implicita a coloanei (si o verifica singur): daca ar scrie valoarea implicita, o coloana
pierduta la restaurare ar reveni oricum pe ea si testul ar trece. Coloanele si valorile vin din `PRAGMA
table_info`, nu dintr-o lista, deci o coloana viitoare intra singura. S-a provocat: restore-ul de dinainte (cu
coloanele enumerate de mana) pica testul, iar pe o copie a bazei locale (din august) pierdea `data_finalizare` pe 2
proiecte si `ora` pe 1 task global.

**O politica de continut stricta strica in tacere ce are inca ceva inline.** Un `onsubmit=` sau un
`style="..."` ramas intr-o pagina nu da nicio eroare in aplicatie: browserul doar nu-l executa. `test_csp`
scaneaza paginile randate (login, `/admin/db-upload`) dupa handlere, atribute `style` si `<script>`/`<style>` fara
nonce, iar `login.test.mjs` pazeste legarea formularului din script. Cum se vede cu adevarat: Chromium real pe un
server de unica folosinta, cu un ascultator `securitypolicyviolation` (nu cu `read_console_messages` pe un tab
folosit: buffer-ul arunca mesajele vechi).
