# 2026-11-22 Asistentul în Torqa: registrul, firul de chat și push FCM, în `/api/asistent`

Pagina System din Torqa devine un hub: ce cere atenția lui Ion (registrul asistentului proactiv de pe
laptop-server), un fir de chat cu asistentul (mesajele lui Ion devin taskuri în coada Claude, răspunsurile
vin înapoi în fir) și notificări push native prin FCM. pif-dashboard e doar **depozitul și poșta**: stochează
registrul, acțiunile, firul și tokenurile și trimite push-ul. Nu rulează LLM și nu creează taskuri.
Codul: `blueprints/asistent.py` (rutele), `blueprints/fcm.py` (transportul FCM, doar bibliotecă standard). v1.1 (aditiv: `ref`, `tinta`,
`alegere`, întrebări cu opțiuni, prezența mașinilor): secțiunea „v1.1” mai jos.

Trei părți vorbesc prin pif-dashboard (fișiere ca `blueprints/sistem.py`, fără tabele, fără migrare):
- **asistentul** de pe laptop-server (`tools/asistent/atentie.py` în Knowledge), cu tokenul de MAȘINĂ;
- **Torqa** (web și Android), cu sesiunea sau tokenul de DISPOZITIV (`g.api_token_scope == 'device'`);
- **serviciul nativ Android** (butoanele din notificare), cu același token de dispozitiv.

pif-dashboard rulează pe același laptop-server ca asistentul (gunicorn, 127.0.0.1:5000).

## Pe disc: `<UPLOAD_FOLDER>/asistent/`

| fișier | ce ține | scriere |
|---|---|---|
| `registru.json` | ultimul registru urcat de asistent (itemii, sursele, rezumatul veghei) | atomic (tmp + rename) |
| `actiuni.jsonl` | acțiunile lui Ion pe itemi, cu starea (`asteapta` → `consumat`) | atomic, max 500 de rânduri (cad cele consumate) |
| `fir.jsonl` | mesajele firului (Ion și asistentul) | atomic, max 500 (cad întâi cele terminate) |
| `push.json` | tokenurile FCM ale dispozitivelor, drepturi 600 | atomic, max 20 |
| `prezenta.json` | ultima raportare a fiecărei mașini (v1.1) | atomic |
| `asistent.lock` | doar blocarea (fcntl): doi workeri nu rescriu deodată | — |

Ca la `/api/sistem`: fișierele nu intră în backup, nu au schemă; registrul se reface la fiecare rulare a
asistentului, iar firul și tokenurile se pierd doar dacă dispare directorul `uploads/`.

## Itemul din registru

```json
{"id": "<sursa>:<cheie> (≤120)", "sursa": "torqa|mail|sistem|server|netdata|vault|backlog|finante|ci|claude|pagina",
 "titlu": "≤140", "de_ce": "≤200", "gravitate": "critic|urgent|azi|info", "termen": "AAAA-LL-ZZ|null",
 "prima_data": "ISO|null", "stare": "nou|vazut|amanat|gata|ignorat|la_claude", "amanat_pana": "ISO|null",
 "incredere": "proprie|straina", "actiuni": ["gata","amana","ignora","claude"], "link": "opțional"}
```

Momentele ISO au secunde și fus (`Z` sau `+HH:MM`). `de_ce`, `incredere`, `actiuni`, `sursa`, `gravitate`, `stare`
sunt obligatorii; `termen`, `prima_data`, `amanat_pana`, `link` pot lipsi sau fi `null` (se stochează cu `null`).
`link`: cale relativă din vault (fără `/` sau `\` la început, fără `..`, fără `:`, fără `%2e` / `%2f` / `%5c` / `%00`) sau `https://host/...` (cu host, fără `user:parola@`, fără spații). În ambele, fără caractere de control (C0, DEL, C1), separatoare U+2028/2029 și marcaje de direcție (U+061C, U+200E/F, U+202A–202E, U+2066–2069).
`stare = amanat` cere `amanat_pana` (altfel itemul ar fi ascuns pe veci).

## Asistent → backend (token de mașină sau sesiune; tokenul de dispozitiv primește 403)

1. `PUT /api/asistent/registru`
   ```json
   {"v": 1, "generat": "2026-11-22T07:35:00Z", "items": [/* ≤300 itemi */],
    "surse": {"torqa": {"ok": true}, "mail": {"ok": false, "eroare": "≤200"}},
    "veghe": {"generat": "ISO", "total": 46, "ok": 45, "picate": [{"nume": "≤120", "detaliu": "≤200"}]}}
   ```
   `veghe` e opțional. Tot opțional, `veghe.categorii` = `{http|timer|docker|putere|disc|netdata: {"total", "ok"}}`
   (adăugat 2026-11-22, pentru rândurile pe categorie din tabul Server; `ok` ≤ `total`). Validare strictă (câmp necunoscut sau tip greșit → 400 cu calea câmpului; registrul vechi
   rămâne). `generat` mai vechi decât cel stocat → 409 (egal trece: cererea retrimisă e idempotentă). 200 `{"ok": true, "items": N}`.
2. `GET /api/asistent/actiuni?stare=asteapta` (implicit; `consumat` pentru istoric; altceva 400) →
   `[{"uid","ts","item_id","actiune","zile","din"}]` (`din`: `pagina|notificare`), cele mai vechi întâi.
3. `POST /api/asistent/actiuni/<uid>/consumat` `{"rezultat": "ok|fail", "mesaj": "≤300 opțional"}` → 200 `{"ok", "uid"}`;
   uid necunoscut 404; deja consumat 409 (o retrimitere nu rescrie rezultatul).
4. `POST /api/asistent/fir` (mesaj al asistentului; `cine` obligatoriu, cu tokenul de mașină)
   ```json
   {"cine": "asistent", "tip": "brief|alerta|raspuns|lucreaza|rezultat|info", "text": "≤2000", "titlu": "≤140 opțional",
    "item_id": "opțional", "task_id": "opțional", "link": "opțional: cale relativă din vault sau https://",
    "butoane": ["claude","gata","amana","ignora","deschide"], "raspuns_la": "id mesaj opțional",
    "push": {"prioritate": "urgent|normal|silent"}}
   ```
   → 201 `{"id": "m_<hex>", "push": {"incercat": true, "trimise": 1, "erori": [], "motiv": null}}`. Fără `push` în cerere nu se
   trimite nimic (`incercat: false`, `motiv: null`). `push: {}` înseamnă prioritate `normal`. `motiv`: `fcm_neconfigurat`
   (lipsește cheia de service account) sau `fara_tokenuri`. Când `trimise == 0`, asistentul cade pe Telegram (rezerva rămâne).
5. `GET /api/asistent/fir/noi` → lista mesajelor lui Ion cu `stare: "nou"`, cele mai vechi întâi.
6. `POST /api/asistent/fir/<id>/stare` `{"stare": "preluat|gata|eroare", "task_id": "≤80 opțional", "mesaj": "≤300 opțional"}` →
   200 `{"ok", "id", "stare"}`; 404 necunoscut; tranziții permise: nou→preluat, preluat→gata|eroare, nou→gata|eroare; aceeași stare
   a doua oară: 200 fără rescriere; orice altceva (și un mesaj al asistentului, care n-are stare): 409. `task_id` și `mesaj`
   se păstrează pe mesaj (`task_id`, `stare_detaliu`).

## Torqa → backend (sesiune sau token de dispozitiv)

7. `GET /api/asistent` →
   ```json
   {"v": 1, "acum": "ISO",
    "registru": {"generat": "ISO|null", "vechime_min": 3, "items": [/* doar activi */], "surse": {}},
    "veghe": {"generat": "ISO", "total": 46, "ok": 45, "picate": []},
    "fir": [/* ultimele 100 de mesaje, cele mai vechi întâi */],
    "actiuni_in_asteptare": [{"uid", "item_id", "actiune"}],
    "push": {"configurat": true}}
   ```
   Itemi activi: stare `nou` sau `vazut`, sau `amanat` cu `amanat_pana` trecut; `gata`, `ignorat`, `la_claude` și amânatul
   din viitor sunt ascunși. Fără registru urcat: `registru.generat = null`, `vechime_min = null`, `items = []`, `veghe = null`
   (pagina arată „Assistant hasn't reported yet”). Tokenurile FCM nu ies niciodată prin GET.
8. `POST /api/asistent/actiune` `{"item_id": "…", "actiune": "gata|amana|ignora|claude|nu_util", "zile": 1-31 opțional, "din": "pagina|notificare"}`
   → 201 `{"uid"}`. Itemul trebuie să existe în registru (404), iar `actiune` să fie în `item.actiuni` (`nu_util` e mereu permis;
   altfel 400). Itemul trebuie să fie **activ** (aceleași reguli ca în `GET`: `nou`, `vazut` sau `amanat` expirat), altfel 409: a doua apăsare
   pe butonul din notificare, după ce asistentul a trecut itemul la `la_claude`, nu face al doilea task. `zile` doar la `amana` (implicit 1; altfel 400). `din` implicit `pagina`. O a doua acțiune pe același item cât
   prima așteaptă → 409 (deci o cerere retrimisă nu dublează nimic).
9. `POST /api/asistent/fir` (mesaj al lui Ion; cu sesiune sau token de dispozitiv, `cine` e forțat `ion`)
   `{"text": "≤2000, nevid", "sursa": "scris|dictat (implicit scris)", "raspuns_la": "opțional"}` → 201 `{"id"}`. Mesajul primește
   `stare: "nou"`. Limită: 30 de mesaje pe oră → 429 cu `Retry-After`. Cu `cine: "asistent"` sesiunea și dispozitivul primesc 403;
   `cine` altceva decât `ion` → 400. **Retrimiterea aceluiași mesaj îl dublează** (contractul n-are cheie de idempotență).
10. `POST /api/asistent/push/token` `{"token": "≤4096, ASCII fără spații", "platforma": "android", "aplicatie": "org.iupif.torqa", "versiune": "≤40 opțional"}`
    → 200 `{"ok": true}` (upsert pe token, cu `ultima_vedere`; idempotent; rămân cele mai recent văzute 20).
    `DELETE /api/asistent/push/token` `{"token"}` → 200 `{"ok", "scos"}` (un token necunoscut dă tot 200).

## Mesajul din fir (cum îl întoarce GET)

```json
{"id": "m_ab12cd", "ts": "ISO", "cine": "ion|asistent", "tip": "mesaj|brief|alerta|raspuns|lucreaza|rezultat|info",
 "titlu": null, "text": "…", "sursa": "scris|dictat|null", "item_id": null, "task_id": null, "link": null,
 "butoane": [], "raspuns_la": null, "stare": "nou|preluat|gata|eroare|null", "stare_detaliu": null,
 "via": "sesiune|dispozitiv|masina|null"}
```

`stare_detaliu` (aditiv): `mesaj`-ul de la `POST .../stare`. `via` (aditiv): de unde vine mesajul lui Ion, pus de server după felul
autentificării (sesiune cu PIN, token de dispozitiv, token de mașină); `null` la mesajele asistentului. Clientul nu-l poate trimite (400).

## Push FCM (în backend)

- Cheia: `FCM_SERVICE_ACCOUNT_FILE` (JSON de service account, 600, în afara repo-ului). Fără ea sau cu un fișier ilizibil:
  `push.configurat = false`, `motiv: fcm_neconfigurat`, nicio eroare 5xx.
- FCM HTTP v1: OAuth2 cu JWT RS256 semnat de cheia contului (scope `https://www.googleapis.com/auth/firebase.messaging`), tokenul de
  acces ținut în memorie până expiră (reluat cu 60 s înainte; aruncat la 401); `POST https://fcm.googleapis.com/v1/projects/<project_id>/messages:send`.
- **Fără dependențe noi.** Semnătura RS256 e `pow(mesaj, d, n)` peste blocul PKCS#1 v1.5, în `blueprints/fcm.py`, cu biblioteca standard;
  se verifică imediat cu cheia publică și, în teste, e identică bit cu bit cu cea din `openssl dgst -sha256 -sign`. Nici `cryptography`
  (rămasă de la web push, interzisă de `teste/test_cerinte.py`), nici PyJWT n-au intrat în `requirements.txt`.
- Timp: tot apelul (token OAuth + toate trimiterile) are plafon de 10 s, fiecare cerere cel mult 8 s și cât a rămas din buget. Plafonul e pe TOATĂ cererea
  (conectare, antete, corp), nu pe operația de socket: `http.client` cu un cronometru care taie socketul (cu `urlopen(timeout=)`, un răspuns trimis
  un octet la 3 s ținea 117 s).
  O eroare (rețea, 4xx/5xx, timeout) nu ridică nimic: intră în `push.erori` (cel mult 10, fiecare ≤200 de caractere, cu doar ultimele 6
  caractere ale tokenului; textul erorilor `urllib` nu se copiază). Trimiterea rulează cu blocarea fișierelor eliberată.
- Mesaj DOAR de date (ca serviciul nativ să-l primească și cu aplicația închisă), toate valorile string:
  ```json
  {"message": {"token": "…", "android": {"priority": "HIGH pentru urgent, NORMAL altfel", "ttl": "86400s"},
   "data": {"v": "1", "tip": "alerta", "msg_id": "m_ab12cd", "titlu": "…", "text": "…", "item_id": "…",
            "butoane": "claude,amana,deschide", "prioritate": "urgent|normal|silent",
            "deschide": "/system?tab=asistent&msg=m_ab12cd"}}}
  ```
  `titlu` și `item_id` lipsă devin `""`. `data` are 4096 de octeți pe tot (chei și valori): `text` se taie la cel mai lung prefix (pe caractere, fără să rupă
  un caracter UTF-8, cu `…` la capăt) cu care `data` serializat rămâne sub 4000 de octeți; în fir rămâne întreg.
- Tokenul pe care FCM îl respinge cu `UNREGISTERED` / 404, sau cu 400 `INVALID_ARGUMENT` pe câmpul `message.token` (`fieldViolations`), se scoate din
  `push.json`; un `INVALID_ARGUMENT` pe alt câmp nu (mesajul e prost, nu tokenul). Răspunsurile de eroare cu altă formă decât cea așteptată se citesc defensiv.

## Date și erori de disc

- Un corp cu surogat Unicode izolat (`\ud83d`) dă 400 cu calea câmpului (altfel scrierea UTF-8 ar fi dat 500).
- Rândurile din `.jsonl` se despart doar la `\n` (`splitlines` rupea un mesaj care conține U+2028 / U+0085).
- Citirea dinaintea unei scrieri se face sub blocare și e **strictă**: o eroare de citire a fișierului (permisiuni, disc) dă 500 fără nicio scriere,
  ca firul sau tokenurile să nu fie rescrise de la zero. Ce nu se poate citi (rânduri JSON stricate, `push.json` ilizibil ca JSON, intrări de token cu
  altă formă) se păstrează, o singură dată fiecare, în `<fișier>.corupt` (drepturi 600, cu rând în log), apoi se rescrie fișierul cu ce a rămas valid.
  Citirile simple (`GET`) cu un fișier ilizibil dau listă goală, nu 500. Un `registru.json` stricat se înlocuiește la următorul `PUT`.

## Acces

Rutele 1–6 refuză tokenul de dispozitiv cu **403** (verificare în rută, nu în `DEVICE_TOKEN_DENIED`, care dă 401: contractul cere 403).
Sesiunea și tokenul de mașină trec. `POST /api/asistent/fir` e deschis dispozitivului doar pentru mesajul lui Ion. Fără autentificare, 401 peste tot.
Erorile au forma depozitului, `{"error": "<text>"}`, iar fiecare cerere eșuată lasă un rând în log (metodă, cale, status, motiv; nu corpul).

## Android (torqa-sp)

- Canale: `asistent-urgent` (sunet, importanță HIGH), `asistent-rezultat` (DEFAULT), `asistent-brief` (LOW, fără sunet).
- Butoane: `claude` → „Give to Claude”, `amana` → „Tomorrow” (zile=1), `gata` → „Done”, `ignora` → „Ignore”,
  `deschide` → „Open” (deschide `deschide` în aplicație). Butonul face `POST /api/asistent/actiune` cu `din: notificare`
  din receiver-ul nativ, cu tokenul de dispozitiv, apoi schimbă notificarea în „Sent to Claude ✓” / „Tomorrow ✓” sau o
  închide; la eroare de rețea: „Couldn't send, open Torqa”.

## v1.1 (2026-11-22, aditiv): ce a cerut hub-ul System

Cerințele lui Ion și designul: Knowledge, `references/decizii/2026-11-22-system-hub.md`. Nicio rută din v1 nu se schimbă; un Torqa
vechi ignoră câmpurile noi. O rută nouă (`PUT /api/asistent/prezenta/<masina>`, a unsprezecea), fără schemă și fără migrare.
Mașinile au id-uri fixe: `server` (Server), `pc-job` (PC job), `ionpc` (IONPC).

**Mesajul lui Ion** (`POST /api/asistent/fir`), câmpuri noi opționale:
- `ref`: `{"tip": "item|decizie|verificare|job|istoric", "id": "≤160", "titlu": "≤140", "sursa": "≤40", "masina": "server|pc-job|ionpc",
  "mod": "discuta|raspuns"}`. `tip`, `id`, `titlu` obligatorii; `sursa`, `masina` și `mod` pot lipsi **sau fi `null`** (`mod` lipsă/`null` = `discuta`): serverul
  întoarce ref-ul cu `sursa: null`, `masina: null` și `mod` pus, iar asistentul (pe răspuns, din `fir/noi`) și Torqa (din `GET`) îl retrimit
  neschimbat.
  `mod: raspuns` doar la `tip: decizie` (400 `corpul.ref.mod`). Se stochează cu toate cheile și se întoarce în `GET` și în `fir/noi`.
- `tinta`: `auto|server|pc-job|ionpc` (implicit `auto`; mesajele de dinainte de v1.1 se întorc tot cu `auto`).
- `alegere` (≤40): doar cu `raspuns_la` (400 `corpul.alegere`); răspunsul lui Ion la o întrebare, vezi mai jos.
- `ref`, `tinta` și `alegere` pot fi `null` = lipsă (`raspuns_la: null` rămâne 400, ca în v1).

**Mesajul asistentului**, câmpuri și tipuri noi:
- `tip` primește `intrebare` (unde să ruleze) și `asteapta` (taskul așteaptă o mașină oprită). Acestea două **cer** `optiuni`: 1–4 de
  `{"id": "≤40", "eticheta": "≤60"}`, id-uri unice; alte tipuri nu primesc `optiuni` (400 `corpul.optiuni`). Serverul nu fixează
  vocabularul id-urilor (mașini la `intrebare`; `server` și `anuleaza` la `asteapta`): îl fixează asistentul.
- `masina` (`server|pc-job|ionpc`, pe orice tip; contractul o folosește la `lucreaza`, `rezultat`, `asteapta`) și `ref` (aceeași schemă),
  opționale; `null` = lipsă, ca la celelalte câmpuri ale asistentului.
- Mesajul din `GET`/`fir/noi` are mereu cheile `ref`, `tinta`, `alegere`, `optiuni` (`[]` când nu sunt), `masina`, `raspuns`.

**Răspunsul lui Ion la o întrebare:** un mesaj obișnuit cu `raspuns_la: <id întrebare>` și `alegere: <id opțiune>` (`text` = eticheta).
Verificări, sub blocarea firului: întrebarea nu există → **404**; nu e un mesaj al asistentului de tip `intrebare`/`asteapta` → **409**;
a primit deja răspuns → **409**; `alegere` nu e între `optiuni` → **400** (`corpul.alegere`, întrebarea rămâne deschisă); 30 pe oră → 429.
Plafonul de 500 de mesaje: o `intrebare`/`asteapta` fără răspuns se tratează ca muncă deschisă (ca mesajele lui Ion `nou`/`preluat`) și
nu cade înaintea mesajelor terminate; întrebarea la care se răspunde în scrierea curentă nu cade în ea, ca răspunsul să nu dea 404 și ca Torqa să-i
vadă butonul ales. Cu 500 de mesaje toate deschise cade cel mai vechi, ca în v1. Dacă trece: întrebarea primește `raspuns: {"optiune", "ts"}` și mesajul lui Ion (`stare: "nou"`, același `ts`) se adaugă în
**aceeași** scriere atomică a `fir.jsonl` (un singur `_scrie_fir`, sub aceeași blocare): nu există o stare cu răspunsul fără mesaj sau
mesajul fără răspuns, iar două cereri simultane (două workere, dublu-tap) dau exact un 201 și un 409. Un `raspuns_la` fără `alegere` rămâne
un reply obișnuit, ca în v1. **Retrimitere:** a doua cerere pentru aceeași întrebare dă 409 (clientul îl tratează ca „deja trimis”).

**Prezența:** `PUT /api/asistent/prezenta/<masina>` `{"activ": bool, "idle_s": număr finit 0..10^9, "versiune": "≤40 opțional, null = lipsă"}` → 200 `{"ok", "masina"}`.
`idle_s` poate fi float (scripturile îl citesc din `gdbus` / `xprintidle` așa) și se rotunjește **în jos** la întreg înainte de comparații și
de stocare (900,9 → 900, încă activ); negativ, `NaN`, `Infinity`, bool, text sau peste 10^9 dau 400. Token de mașină sau sesiune; tokenul de dispozitiv 403; mașină necunoscută 404; câmp necunoscut sau tip greșit 400. Starea stă în
`prezenta.json` (`{"masini": {id: {ultima, activ, idle_s, versiune}}}`), scris atomic sub aceeași blocare; `ultima` o pune serverul. Idempotent:
cererea repetată lasă aceeași stare, doar `ultima` avansează. Un fișier ilizibil ca JSON se tratează ca „nicio mașină n-a raportat” și se
rescrie la următoarea raportare (se reface în cel mult un minut); o eroare de citire a discului dă 500 la scriere, fără rescriere.
`GET /api/asistent` primește `masini`, mereu trei, în ordinea `server`, `pc-job`, `ionpc`:
`{"id", "nume", "stare": "activ|online|offline", "ultima": "ISO|null", "idle_min": int|null}`. `online` = ultima raportare în ultimele
**180 s** (inclusiv 180); `activ` = online, `activ: true` și `idle_s` ≤ **900** (inclusiv 900); altfel `offline` (și `ultima` rămâne ultima
raportare). Mașina care n-a raportat niciodată: `offline`, `ultima: null`. `idle_min` = `idle_s // 60` cât e online, `null` când e offline
(valoarea veche ar induce în eroare). Ceasul serverului dat înapoi (`ultima` în viitor) nu scoate mașina din `online`.

Ce nu face serverul (neschimbat): nu execută text liber și nu primește opțiuni inventate la `/api/sistem/decizie`; rutarea pe mașini,
coada și închiderea deciziei în ledger sunt ale asistentului. Push-ul FCM al unui mesaj `intrebare`/`asteapta` poartă `tip` nou în `data`;
serviciul nativ Android trebuie să-l cunoască înainte ca asistentul să ceară `push` pe ele.

Rollback: `git revert` al commitului v1.1; `prezenta.json` se poate șterge. Câmpurile deja scrise în `fir.jsonl` rămân inofensive (v1 le ignoră).

## Ce nu intră

- Web push în browser (desktop): nu; pagina se reîmprospătează la deschidere și la 60 s cât e vizibilă. (Web push-ul vechi, cu `pywebpush`,
  a plecat odată cu interfața veche: eticheta `inainte-de-retragere`, `blueprints/push.py`. Din el nu s-a refolosit cod: era VAPID/aes128gcm,
  cu abonamente de browser; FCM HTTP v1 e alt protocol.)
- Telegram rămâne rezerva asistentului când `push.trimise == 0`.

## Rollback

Fără schemă și fără migrare: se scoate blueprint-ul din `app.py` (sau `git revert`) și se poate șterge `uploads/asistent/`. Torqa fără rutele
astea arată pagina System fără hub; asistentul cade pe Telegram.
