# 2026-07-03 — Excel Gantt real (nu tabel + grila coarse)

- **2026-07-03 — Excel Gantt real (nu tabel + grila coarse)** (cerut de Ion: „excelul trebuie tot sa fie
  Gantt altfel nu are sens"): rescris `export_gantt_xlsx` — coloane pe **ZI** (adaptiv la saptamana daca
  spanul >92z), **banda de luna** merged (RO: Ian..Dec) deasupra, header cu numar zi (weekend gri / azi
  cu fill amber), info stanga compact (#/Task/Start/Sfarsit/Zile/%), **bare = celule colorate** pe span
  cu **progres split** (partea facuta = nuanta inchisa `done_hex`, restul = nuanta deschisa `rem_hex`;
  done_cells = round(barlen*progres/100)), milestone = ◆ in celula de start, `freeze_panes` la prima
  coloana de grila (info + header raman fixe). SHADES per status. Verificat: done=toate inchise,
  in_progress 40%/4z = 2 inchise + 2 deschise, banda „Iun 2026/Iul 2026", freeze G6. (LibreOffice
  headless din sandbox nu incarca xlsx — validat programatic cu openpyxl.)
