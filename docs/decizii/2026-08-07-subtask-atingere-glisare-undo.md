# 2026-08-07 — Subtaskul: atingerea bifeaza, glisarea sterge, undo peste tot

- **2026-08-07 (6) — Subtaskul: atingerea bifeaza, glisarea sterge, undo peste tot.**
  Cea mai mare tinta facea lucrul cel mai rar: titlul pornea REDENUMIREA, bifarea
  statea intr-un cerc de 26px. Acum atingi randul -> se bifeaza; redenumirea pe
  apasare lunga (actiune locala `apasareLunga` in `Tasks.svelte`, 300ms, anulata la
  8px de miscare). Pubela permanenta de 44px a plecat de pe rand — stergerea vine
  din glisare spre stanga, cu `.gl-sub` care recoloreaza pista in `--danger`.
  **Defect de paritate reparat:** `removeSubtask()` din `Tasks.svelte` stergea
  direct pe server, fara undo, in timp ce aceeasi functie din `ProjectDetail`
  avea `toastUndo` cu commit intarziat. Cea fara plasa era in lista folosita cel
  mai des — iar acum stergerea se poate porni si dintr-un gest.
