# 2026-07-03 — Verificare mobil + fixuri

- **2026-07-03 — Verificare mobil + fixuri** (SW v76): trecere Playwright la 390px pe toate paginile
  (Home/Tasks/Projects/ProjectDetail/Params/Calculator/Notes/Admin) — **0 overflow orizontal, 0 erori**,
  iconografia nouă (glife→Lucide) OK, dock jos corect. Fixat: (1) **salutul din header se suprapunea
  peste brand pe mobil** (`.header-context` centrat absolut nu încape la 390px) → ascuns pe ≤768px
  (`display:none`, nu doar `.hc-sub`). (2) Diacritice lipsă în `Notes.svelte`: Notițe, Configurează,
  către, în, „Caută în conținut", „Nicio notiță", „Selectează o notiță din listă".
