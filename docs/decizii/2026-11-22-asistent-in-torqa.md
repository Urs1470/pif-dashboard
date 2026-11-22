# 2026-11-22 Asistentul în Torqa: registrul, firul de chat și push FCM, în `/api/asistent`

Pagina System din Torqa devine un hub: ce cere atenția lui Ion (registrul asistentului proactiv de pe
laptop-server), un fir de chat cu asistentul (mesajele lui Ion devin taskuri în coada Claude, răspunsurile
vin înapoi în fir) și notificări push native prin FCM. pif-dashboard e doar **depozitul și poșta**: stochează
registrul, acțiunile, firul și tokenurile și trimite push-ul. Nu rulează LLM și nu creează taskuri.
Codul: `blueprints/asistent.py` (rutele), `blueprints/fcm.py` (transportul FCM, doar bibliotecă standard).

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
`link`: cale relativă din vault (fără `/` la început, fără `..`, fără `:`) sau `https://`.
`stare = amanat` cere `amanat_pana` (altfel itemul ar fi ascuns pe veci).

## Asistent → backend (token de mașină sau sesiune; tokenul de dispozitiv primește 403)

1. `PUT /api/asistent/registru`
   ```json
   {"v": 1, "generat": "2026-11-22T07:35:00Z", "items": [/* ≤300 itemi */],
    "surse": {"torqa": {"ok": true}, "mail": {"ok": false, "eroare": "≤200"}},
    "veghe": {"generat": "ISO", "total": 46, "ok": 45, "picate": [{"nume": "≤120", "detaliu": "≤200"}]}}
   ```
   `veghe` e opțional. Validare strictă (câmp necunoscut sau tip greșit → 400 cu calea câmpului; registrul vechi
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
   altfel 400). `zile` doar la `amana` (implicit 1; altfel 400). `din` implicit `pagina`. O a doua acțiune pe același item cât
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
 "butoane": [], "raspuns_la": null, "stare": "nou|preluat|gata|eroare|null", "stare_detaliu": null}
```

`stare_detaliu` (aditiv): `mesaj`-ul de la `POST .../stare`.

## Push FCM (în backend)

- Cheia: `FCM_SERVICE_ACCOUNT_FILE` (JSON de service account, 600, în afara repo-ului). Fără ea sau cu un fișier ilizibil:
  `push.configurat = false`, `motiv: fcm_neconfigurat`, nicio eroare 5xx.
- FCM HTTP v1: OAuth2 cu JWT RS256 semnat de cheia contului (scope `https://www.googleapis.com/auth/firebase.messaging`), tokenul de
  acces ținut în memorie până expiră (reluat cu 60 s înainte; aruncat la 401); `POST https://fcm.googleapis.com/v1/projects/<project_id>/messages:send`.
- **Fără dependențe noi.** Semnătura RS256 e `pow(mesaj, d, n)` peste blocul PKCS#1 v1.5, în `blueprints/fcm.py`, cu biblioteca standard;
  se verifică imediat cu cheia publică și, în teste, e identică bit cu bit cu cea din `openssl dgst -sha256 -sign`. Nici `cryptography`
  (rămasă de la web push, interzisă de `teste/test_cerinte.py`), nici PyJWT n-au intrat în `requirements.txt`.
- Timp: tot apelul (token OAuth + toate trimiterile) are plafon de 10 s, fiecare cerere cel mult 8 s și cât a rămas din buget.
  O eroare (rețea, 4xx/5xx, timeout) nu ridică nimic: intră în `push.erori` (cel mult 10, fiecare ≤200 de caractere, cu doar ultimele 6
  caractere ale tokenului; textul erorilor `urllib` nu se copiază). Trimiterea rulează cu blocarea fișierelor eliberată.
- Mesaj DOAR de date (ca serviciul nativ să-l primească și cu aplicația închisă), toate valorile string:
  ```json
  {"message": {"token": "…", "android": {"priority": "HIGH pentru urgent, NORMAL altfel", "ttl": "86400s"},
   "data": {"v": "1", "tip": "alerta", "msg_id": "m_ab12cd", "titlu": "…", "text": "…", "item_id": "…",
            "butoane": "claude,amana,deschide", "prioritate": "urgent|normal|silent",
            "deschide": "/system?tab=asistent&msg=m_ab12cd"}}}
  ```
  `titlu` și `item_id` lipsă devin `""`. `text` se taie la 1000 de caractere în push (FCM are 4 KB pe tot mesajul); în fir rămâne întreg.
- Tokenul pe care FCM îl respinge cu `UNREGISTERED` / 404 se scoate din `push.json`.

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

## Ce nu intră

- Web push în browser (desktop): nu; pagina se reîmprospătează la deschidere și la 60 s cât e vizibilă. (Web push-ul vechi, cu `pywebpush`,
  a plecat odată cu interfața veche: eticheta `inainte-de-retragere`, `blueprints/push.py`. Din el nu s-a refolosit cod: era VAPID/aes128gcm,
  cu abonamente de browser; FCM HTTP v1 e alt protocol.)
- Telegram rămâne rezerva asistentului când `push.trimise == 0`.

## Rollback

Fără schemă și fără migrare: se scoate blueprint-ul din `app.py` (sau `git revert`) și se poate șterge `uploads/asistent/`. Torqa fără rutele
astea arată pagina System fără hub; asistentul cade pe Telegram.
