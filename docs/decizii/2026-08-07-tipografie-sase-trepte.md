# 2026-08-07 — Tipografia: sase trepte si o regula de familii (tura 6)

- **2026-08-07 (9) — Tipografia: sase trepte si o regula de familii (tura 6).**
  Erau 8 trepte, 4 greutati, 7 valori de tracking si 9 inaltimi de rand, fara nicio
  regula scrisa. Acum: **26 / 20 / 17 / 15 / 13 / 11** (`--font-title`, `--font-h2`,
  `--font-h3`, `--font-body`, `--font-small`, `--font-label`), niciun salt sub 2px.
  **Corpul a urcat de la 14,4 la 15 si NU mai scade pe telefon** — doar
  `--font-title` (26 -> 22). Familii: Space Grotesk = numele unui lucru (nimic sub
  17px), Inter = tot ce citesti, mono = **cifre care se compara**; regula se
  verifica singura — *daca textul se poate traduce, nu e mono* (14 selectoare au
  pierdut monospace-ul). Tracking: `--tracking-tight/-normal/-label`. Line-height:
  1.15 / **1.35** / 1.55 / 1.7. `--fw-bold`, `--font-tiny/micro/h1/display`,
  `--tracking-wide/wider`, `--radius-xl/chip` **au fost sterse** (zero potriviri in
  `frontend/src`). O singura pastila `.count` in `global.css` (era in sase locuri):
  forma nu codifica nimic, culoarea da intelesul — neutru = cate sunt, `accent` =
  cate sunt de facut aici, `danger` = cate sunt restante; pastila poarta un NUMAR,
  cuvantul merge in `title`.
  **Capcana de migrare:** `--font-micro -> --font-label` NU e mecanica — tinta e
  `--font-label` doar unde selectorul are `text-transform: uppercase`; unde poarta
  cifre (`.zile`, `.ap`, `.lane-contor`, `.f-meta`, `.ag-cand`, `.nr-lucrari`) e
  `--font-small`. Scriptul de migrare a decis dupa exact conditia asta.
  **De verificat cu Ion (nedecis inca):** `.count` e la `--font-label` (11px), cum
  cere handoff-ul de implementare; prototipul 6c scrie in schimb „mono 13". Singurul
  loc unde cele doua documente nu spun acelasi lucru.
