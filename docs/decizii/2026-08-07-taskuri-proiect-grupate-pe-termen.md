# 2026-08-07 — Taskurile de proiect se grupeaza dupa termen, ca peste tot

- **2026-08-07 (4) — Taskurile de proiect se grupeaza dupa termen, ca peste tot.**
  Era singura lista de taskuri din aplicatie care nu grupa: venea
  `ORDER BY created_at DESC` si ramanea asa, iar in proiect nu exista nici
  reordonare manuala — deci un restant putea sta al patrulea. `grupeazaDupaTermen`
  era deja generica. Compozitorul a primit chipurile de zi (Azi / Mâine / Alege
  data): fara ele un task de proiect se nastea fara termen, adica INVIZIBIL in
  „Astăzi", in Planificator si in Google Calendar. „Finalizate" foloseste acum
  ACELASI rand, doar stins si taiat — inainte pierdea termenul si subtaskurile
  exact cand vrei sa verifici ce ai facut.
  **Capcana:** `animate:` cere ca elementul sa fie unicul copil al unui `{#each}`
  cheiat, deci snippetul `randTask` tine doar INTERIORUL randului; invelisul
  `.trow-wrap` (cu `--sev` si tranzitiile) sta in fiecare lista.
  **A doua:** `{@const}` trebuie sa fie copil IMEDIAT al blocului, nu ingropat in
  markup (`Projects.svelte`, `urmatoarea(p)`).
