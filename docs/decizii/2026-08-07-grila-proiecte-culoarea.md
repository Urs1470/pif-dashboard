# 2026-08-07 — Grila de proiecte: culoarea ramane doar pe ce variaza

- **2026-08-07 (5) — Grila de proiecte: culoarea ramane doar pe ce variaza.**
  `.tip-chip.service` citea `--success` (verde), `.ptip.service` citea
  `--service-accent` (amber) — un fapt, doua culori, in aceeasi pagina. Tipul nu
  mai are fill deloc: linie subtire `--text-faint` lipita de cuvant, aceeasi
  definitie pe card si in arhiva. Sus ramane colorat doar STATUSUL, care se
  schimba. Pastila lui arata acum ca un control (fill discret + chevron) si are
  `toastUndo` — o atingere gresita trimitea un proiect viu in arhiva pliata, fara
  drum inapoi. **Pe touch e `<span>`, nu `<button>`:** avea 22px in interiorul
  zonei de atingere a cardului, deci o atingere deviata ori deschidea proiectul,
  ori ii schimba statusul, si nu se putea sti dinainte care. Chipurile de filtru
  au plecat (dublau arhiva, ca „Active" din /tasks); sortarea si arhiva sunt
  butoane-fantoma. Pe telefon bara intra pe UN rand: primul card urca de la
  y≈314 la y≈178.
