# Pentru Hermes — context, reguli, anti-coliziune

## Cine face ce

- **Ion** — single user al PIF Dashboard, owner repo, owner laptop-server care expune `https://pif.iupif.org` prin Cloudflare Tunnel.
- **Claude (în Claude Code, sesiunile lui Ion)** — face majoritatea modificărilor UI/UX, commit + push direct în repo. Auto-deploy aduce schimbările pe Pi/laptop-server în ~5–10s.
- **Hermes (tu)** — vii la nevoie pentru task-uri grele cu costuri mari de tokeni: audit DB față de PDF, batch LLM pe explicații parametri, sarcini care necesită rulare locală cu API key separat.

Cei doi agenți trebuie să **NU se suprascrie** și să **NU lase fișiere orfane** pe vreuna din mașini.

---

## Stack și topologie

- **Repo**: `https://github.com/Urs1470/pif-dashboard` (private)
- **Worktree local Ion**: `D:\Projects\pif-dashboard`
- **Laptop-server**: rulează `pif-dashboard.service` (systemd), expus prin `cloudflared` la `https://pif.iupif.org/`
- **Backend**: Flask + SQLite single-process, auth PIN (`pif2024` default, `PIF_DASHBOARD_PIN` env var override)
- **Frontend**:
  - Desktop: `templates/index.html` + `static/app.js`
  - Mobile (PWA, ruta `/m`): `templates/mobile.html` + `static/mobile.js`
  - Manifest separat: `static/manifest.json` (desktop, scope `/`) și `static/manifest-mobile.json` (`/m`)
- **Login**: `templates/login.html` (același pentru ambele)
- **Service worker**: `static/service-worker.js` — bump `CACHE_NAME`/`STATIC_CACHE`/`API_CACHE` versions când livrezi static assets noi
- **Auto-deploy**: webhook GitHub → `git pull && systemctl restart pif-dashboard`. Există un `.deploy_secret` pe server, **NU îl pune în repo**.

---

## Reguli stricte (NU le rupe)

### A. Workflow Git

1. **Înainte de orice modificare** rulează `git pull` și `git log --oneline -5` ca să vezi ultimul commit. Verifică dacă cineva (Claude) a făcut modificări recente la fișierele pe care vrei să le atingi. Dacă da, **integrează modificările lui** și nu refă din ce era înainte.
2. **Push imediat după modificare** — nu lăsa modificări locale ne-pushe-uite. Cu cât stai mai mult, cu atât crește riscul ca Claude să facă altă modificare suprapusă.
3. **NU edita direct pe Pi/laptop-server fără să commit-i în repo** — auto-deploy următor va suprascrie. Asta s-a întâmplat deja: `mobile.html` și `mobile.js` au trăit doar pe server săptămâni la rând și au fost recuperate dintr-un backup Telegram când Claude a vrut să le aducă în repo.
4. **Toate fișierele live trebuie să existe în repo**. Nu lăsa nimic orfan.
5. **Commit messages fără diacritice** (PowerShell se incurcă la `-m` cu `@'...'@`). Co-author obligatoriu:
   ```
   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   ```
   Sau dacă ești Hermes:
   ```
   Co-Authored-By: Hermes <noreply@anthropic.com>
   ```
   Așa Ion vede în istoric cine a făcut ce.

### B. Domeniu — cine atinge ce

| Zonă | Owner principal |
|---|---|
| `templates/`, `static/app.js`, `static/mobile.js`, `static/service-worker.js`, `static/budget/*` | **Claude** (UI/UX, design system) |
| `app.py` (rute API), `database.py` (migrații), `blueprints/*` | **Claude** dacă e UI-driven, **Hermes** dacă e infra/data |
| `scripts/audit_pdf.py`, `scripts/audit_reports/*` | **Hermes** |
| Improvements LLM pe `parametri_master` (descrieri, explicații, interconexiuni) | **Hermes** (folosește API key-ul tău) |
| Manuale PDF în `manuals/` | **Hermes** (descarcă, validează) |
| Memory files Ion (`~/.claude/projects/.../memory/*.md`) | **NU atinge** — sunt locale lui Ion |

Dacă găsești un bug în zona "Claude" și e mic (typo, bug de o linie), corectează-l cu commit message care explică clar `Hermes fix: ...`. Dacă e mai mare, lasă-l într-un fișier `HERMES_FOUND_BUGS.md` la root și anunță Ion să-l direcționeze.

### C. Design system — neapărat respectă

Aplicația are deja paletă, fonturi și pattern-uri stabilite. **NU introduce stiluri ad-hoc.**

**Palete** (vezi `templates/index.html` și `templates/mobile.html`):
- Background: `--bg #0a0d12`, `--bg-elev1 #11161e`, `--bg-elev2 #161c26`, `--bg-elev3 #1d2530`
- Accent turcoaz: `--accent #58d1c9`, cu `--accent-soft` și `--accent-ring`
- Semantic: `--danger #f97066`, `--warning #f5b14d`, `--success #66d19e`, `--violet #8b87ff`
- Light theme are propriile valori — păstrează ambele dacă atingi CSS

**Fonturi**:
- `Plus Jakarta Sans` pentru body
- `JetBrains Mono` pentru orice cifră, cod, valoare numerică, parametru

**Iconițe**:
- **Lucide line-icons EXCLUSIV** (CDN `https://unpkg.com/lucide@latest/dist/umd/lucide.min.js`). Zero emoji în UI. Excepție: emoji-urile DIN DATA (în explicații parametri, observații Ion etc.) — alea sunt conținut, nu UI.
- Iconițe inserate dinamic prin `<i data-lucide="nume-iconita">` + apel `lucide.createIcons()`. Mobile.html are deja un MutationObserver care le rerandează automat, **NU spargi pattern-ul ăsta**.
- Re-entry guard `_iconsRendering` (vezi `static/app.js` `refreshIcons()`) e critic — fără el observer-ul intră în buclă infinită.

**Componente reutilizabile** pe desktop (`app.js`):
- `enhanceSelect()` / `cs-enhance` — transformă `<select>` native în dropdown custom dark. Pe orice `<select>` nou pus în UI, **pune clasa `cs-enhance`** și `enhanceAllSelects()` se ocupă.
- `flatpickr` pentru date — **NU folosi `<input type="date">` native** (Chrome îl afișează alb urât).
- Cache API: `apiGet`, `apiPost`, `apiPut`, `apiDelete`, `apiPrefetch` din `app.js`. `_invalidateCache(url)` face match pe root URL și suprafețe.

**Pe mobile** (`mobile.js`):
- Cache params în IndexedDB cu version bump
- Toate listele de parametri sortate **ASC by cod natural** (folosește `localeCompare` cu `{ numeric: true }`)

### D. Sortare parametri

**Default ASC by cod** pe ambele platforme. Backend (`/api/parametri`, `/api/parametri/bulk`) sortează deja `ORDER BY familie, parametru`. Pe client, dacă filtrezi sau resortezi, păstrează regula. **Nu introduce DESC by ID sau sort by created_at**.

### E. Cache-busting

- Versionează static assets prin query string: `?v=YYYYMMDD` sau `?v={{ js_version }}`
- La modificare în `static/service-worker.js`, bump `CACHE_NAME`/`STATIC_CACHE`/`API_CACHE` (`v1` → `v2` → ...). Activate-event-ul șterge cache-urile vechi automat.

---

## Stadiu curent (snapshot)

### UI
- Login pagină coerentă, fără dependență externă (Lucide ca SVG inline)
- Desktop: 5 taburi (Acasă, Taskuri Zilnice, Proiecte, Parametri, Administrativ), greeting + 4 stats color-coded, drill-down parametri (producător picker → familie mini-tabs → listă)
- Mobile (`/m`): paritate cu desktop ca features. Bottom-nav cu Lucide icons. Drill-down parametri. Buton "+ Proiect nou" și "+ Notiță nouă" inline (NU FAB), Lucide peste tot.
- Budget tracker (`/budget/`): redesign-uit aliniat cu PIF design system (alte sesiuni Claude)

### Data
- DB SQLite (`pif_dashboard.db` pe server, **NU în repo** — e în `.gitignore`)
- ~15.274 parametri în `parametri_master`. Calitatea descrierilor inconsistentă — asta e job-ul tău LLM.
- 7 familii: ABB (ACS580, ACS880), Siemens (G120, G130_G150, S120_S150), Danfoss (FC302), Lenze (i550, i950)

### Audit parametri (status la 2026-05-18)
- `scripts/audit_pdf.py` — script de validare DB vs PDF
- ABB ACS580: pilot rulat cu success. Parser-ul a fost îmbunătățit (split la double-space, BAD_NAME_PATTERNS, look-ahead pe definiție). Mismatch 554 → 455.
- **Pending de la tine**: rulează `--all` pentru toate familiile (Danfoss/Lenze/Siemens), validează parserele pentru fiecare format (Danfoss `NN-NN`, Lenze `0xXXXXX`, Siemens `pNNNNN`), apoi `--apply-pagini` ca să fixezi paginile PDF în DB.
- **După audit**: batch LLM Haiku pe descrieri lipsă/proaste. Folosește API key-ul tău, raportează costul.

---

## Anti-coliziune — checklist la fiecare sesiune

Înainte să faci orice modificare:

```bash
cd D:/Projects/pif-dashboard
git pull
git log --oneline -10
git status
```

Dacă vezi commit-uri Claude foarte recente (ultimele ore), citește-le rapid ca să știi ce a atins. Dacă fișierul pe care vrei să-l modifici a fost atins de Claude azi, **citește-l înainte de a-l rescrie** — Claude probabil a introdus o convenție nouă pe care trebuie să o respecți.

După modificare:

```bash
git add <file>
git commit -m "Hermes: <ce ai făcut, fără diacritice>

Co-Authored-By: Hermes <noreply@anthropic.com>"
git push
```

Verifică pe live că nu ai spart nimic:

```bash
curl -s -o /dev/null -w "HTTP: %{http_code}\n" --max-time 10 https://pif.iupif.org/login
curl -s -o /dev/null -w "HTTP: %{http_code}\n" --max-time 10 https://pif.iupif.org/m
```

Dacă vezi 500/502/503 după push-ul tău, **rollback imediat**:

```bash
git revert HEAD --no-edit
git push
```

Apoi diagnostichează în pace.

---

## Erori / gotcha cunoscute (pentru tine, ca să nu te lovesti de ele iar)

- **`render_template('mobile.html')` are nevoie de `js_version`** — context processor în `app.py` îl injectează. Dacă faci o rută nouă care randează mobile.html, lasă `{{ js_version }}` referit; nu îl elimina.
- **SQLite nu are REGEXP built-in** — nu folosi `REGEXP` în query-uri. Folosește `LIKE` sau Python regex post-fetch.
- **Service Worker cache-uiește agresiv** — la deploy nou pe static assets, bump versiunile din `service-worker.js` ca activate-event să șteargă cache-ul vechi. Userii vor primi versiunea nouă la următoarea încărcare.
- **`new project form crash` pe desktop** — `#jurnal-data` a fost șters dintr-o iterație anterioară. Codul care îl mai referă trebuie `if (jd) jd.value = ...`. Pattern: guard pe `getElementById` în tot codul care toucheză DOM-ul Acasă.
- **Cloudflare Tunnel poate cădea independent** — 1033 error apare când `cloudflared` e jos pe server. NU e cod-related. Ion îl restart-ează: `sudo systemctl restart cloudflared`.
- **PIN-ul** default e `pif2024`. NU păstra PIN-ul în niciun fișier committed.
- **Webhook auto-deploy crapă tăcut dacă ai modificări locale ne-comitate pe server** — pe laptop-server, dacă tu (Hermes) ai un fișier modificat dar ne-commit-uit (ex: `scripts/audit_pdf.py` în lucru), `git pull` refuză să suprascrie și webhook-ul returnează 500. Toate push-urile ulterioare ale lui Claude se acumulează pe GitHub fără să ajungă pe server. **Regulă**: păstrează worktree-ul de pe server CURAT. Înainte de orice sesiune de lucru pe scripts/audit, fie commit + push WIP, fie `git stash`. Verifică:
  ```bash
  cd ~/Projects/pif-dashboard && git status
  ```
  Trebuie să fie `nothing to commit, working tree clean` între sesiuni.

---

## Comunicare cu Ion

- Mesaje **scurte, directe, în română**.
- Fără introduceri lungi de tipul "Bună ziua, sper că ești bine". Direct la subiect.
- Când termini o sarcină, raportează concret: ce ai schimbat (fișiere), ce ai testat, ce mai e de făcut.
- Dacă ai întrebări, pune-le clar și ofera opțiuni (A / B / C) — Ion alege.
- Dacă nu ești sigur de scope, **întreabă înainte** — task-urile mari care se dovedesc greșite te costă tokeni.

---

*Document menținut de Claude în repo. Update-uri când stadiul aplicației se schimbă semnificativ.*
