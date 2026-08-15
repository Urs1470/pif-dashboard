# 2026-07-15 — Gantt per-proiect refăcut ca listă read-only + timeline

- **2026-07-15 — Gantt per-proiect refăcut ca listă read-only + timeline** (SW v93):
  Ion voia taskuri **needitabile** aici (se gestionează în tabul Taskuri), fără procentaje
  (taskurile lui sunt discrete făcut/nefăcut), arătate ca o listă simplă (stil widget-ul
  „Task-uri urgente" de pe Home). `ProjectGantt.svelte` rescris: stânga = listă read-only
  (`.tk-row`: index/bifă + titlu + sub-linie faza/interval + due-chip azi/mâine/depășit),
  dreapta = timeline read-only (bare solide pe status, fără %/fill; milestone ◆; benzi
  Site/Sediu). Finalizate = `CheckCircle2` + titlu tăiat. Click pe task → sare la tabul
  Taskuri cu focus (`ProjectDetail.openTaskFromGantt` setează `router.query.focus` +
  `activeTab='tasks'`; prinde `focusOnLand`). Scos tot ce era editare: tabelul editabil,
  drag/resize, dependențe+săgeți on-screen, Auto/Reprogramează/Drum critic, „Avansat",
  „Task nou". Singura editare rămasă = **perioada de implementare** (`ImplPeriodModal`).
  Export PDF/Excel neschimbat (backend intact; dependențele rămân în DB + în export).
  Tradeoff: `is_milestone`/`faza`/`data_start` nu se mai setează din Gantt (rar folosite).
