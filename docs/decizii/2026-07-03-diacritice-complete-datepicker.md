# 2026-07-03 — Diacritice complete + DatePicker portal + Faza 1 audit

- **2026-07-03 — Diacritice complete + DatePicker portal + Faza 1 audit** (backend): (1)
  diacritice comma-below (ș U+0219 / ț U+021B) pe TOT textul afișat din dashboard — reguli:
  NU se ating valorile `value:`, cheile de status/prioritate ('in_lucru', 'normal'…),
  `familie`/`producator` folosite ca chei, cheile localStorage, comentariile de cod;
  CommandPalette păstrează `keywords` ASCII + variante fără diacritice ca să nu strice
  filtrarea. (2) **Bug fix DatePicker**: `.dp-pop` (position:fixed) era prins în
  stacking-context-ul unui strămoș cu transform (tranziție pagină / `.arow:hover`) → cardul
  „URGENTE" îl acoperea. Fix: acțiune Svelte `use:portal` care ridică pop-up-ul la
  `document.body` (`DatePicker.svelte`); z-tooltip=3000 > z-modal=1000 → merge și în modale.
  (3) **Faza 1 backend** din audit: `parametri.py` guard `sqlite3.OperationalError` pe
  get_parametri / get_parametri_familii / parametri_audit (200 gol în loc de 500 pe DB fără
  seed); reorder_agenda (`tasks.py`) folosește `logger.exception` în loc de linia moartă;
  șterse rute moarte `/api/parametri/{search,bulk,by-producator}`, `/api/fault-codes/lookup`,
  `/api/import-params/preview` + importurile/constantele orfane (math, PRODUCATOR_FAMILII,
  parse_for_producator). (Deja livrate în fazele anterioare: backup/restore complet,
  rate-limit login 5/5min, href-whitelist XSS, guard atomic recurență, indexuri atașamente.)
