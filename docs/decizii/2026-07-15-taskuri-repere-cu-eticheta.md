# 2026-07-15 — Taskuri = repere cu etichetă (Gantt + Planificator)

- **2026-07-15 — Taskuri = repere cu etichetă (Gantt + Planificator)** (SW v94): Taskurile lui
  Ion sunt aproape toate de o zi → pe un timeline de luni întregi barele deveneau dungi de ~3px
  invizibile (mai ales pe tema deschisă). Decizie (ales de Ion): „Timeline = perioade + repere".
  **ProjectGantt.svelte**: taskurile nu mai sunt bare, ci **puncte** (`.dot`, colorate pe status)
  la data scadentă, cu **linie subțire** start→scadență dacă au durată reală; milestone = romb.
  Fiecare marker are **etichetă cu titlul** lângă el (`.mk-label`, flip la stânga peste 58% ca
  să nu iasă din ecran). Adăugat marcaj **deadline** (linie punctată). **Plan.svelte**: taskurile
  de o zi arătau doar `◆` fără text (`.bar.single .bar-txt{display:none}` + `::after '◆'`) →
  acum romb (`.pin-dot`) + eticheta titlului lângă el (flip peste 62%). Motiv: Ion nu-și dădea
  seama ce task e fără hover. Tot needitabil în Gantt; export PDF/Excel **încă desenează bare**
  (follow-up: de trecut și exportul pe repere pt PDF-ul de client).
