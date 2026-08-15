# 2026-07-15 — Gantt per-proiect simplificat (calm by default)

- **2026-07-15 — Gantt per-proiect simplificat (calm by default)** (SW v92): Ion găsea ganttul din
  proiect prea complicat față de Planificator. `ProjectGantt.svelte`: toggle nou `Avansat` (persistat
  localStorage `pif-gantt-adv`, off implicit) ascunde uneltele PM avansate — dependențe+săgeți, `Auto`
  reschedule, `Drum critic`. Implicit vizibile doar `Task nou / Perioadă / PDF / Excel / Avansat`. Tabel
  redus la `Task | Fază | Start | Sfârșit | %` (scoase coloanele `#` și `Zile`; durata rămâne în tooltip-ul
  barei). Rânduri: 2 iconițe implicit (milestone + șterge), a 3-a (`Link2`) doar sub Avansat. Zero
  modificări backend — dependențele rămân în DB, doar săgețile se ascund. `.g-table` 560→440px.
