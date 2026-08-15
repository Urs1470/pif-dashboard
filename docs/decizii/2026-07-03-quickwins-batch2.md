# 2026-07-03 — Faza 2 quick-wins (batch 2) — B3/B4/B5/B6

- **2026-07-03 — Faza 2 quick-wins (batch 2) — B3/B4/B5/B6** (SW v70): **B3** buton „Manual" +
  „Coduri erori" pe cardul echipamentului (ProjectDetail) → deschid PDF-ul drive-ului / fault-codes
  filtrate pe familie. Rezolver comun în `frontend/src/lib/manuals.js` (MANUAL_MAP mutat din Params +
  `familieForEquip` care replică `_familie_from_echipament` din backend + `manualUrlForEquip`). Params
  gestionează acum `/params?tab=faults&familie=<X>` (funcția `openFamilie` în `$effect`-ul de query).
  **B4** favorite + recente parametri (localStorage `pif-params-fav`/`pif-params-recent`, strip de
  chips deasupra tabelului + toggle stea în modalul de detaliu; `pushRecent` la deschidere). **B5**
  buton „Cameră" în AttachmentsTab (`<input accept="image/*" capture="environment">`). **B6** endpoint
  `GET /api/export/ics` (admin.py) — deadline-uri proiecte + scadențe taskuri/global_tasks ne-finalizate
  ca `.ics` (Response text/calendar), buton „Calendar (.ics)" în Admin > Export. Verificat: ICS 200 cu
  8 evenimente + diacritice; B3/B5 randează; B4 nu s-a putut testa UI local (parametri_master gol) dar
  compilează. **Gotcha:** kill TOATE procesele `app.py` înainte de restart în sandbox — un proces vechi
  pe portul 5000 servea cod vechi (ICS dădea 404).
