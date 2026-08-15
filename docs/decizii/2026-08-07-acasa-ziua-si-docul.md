# 2026-08-07 — Tura 7: Acasa isi spune ziua; docul nu mai pierde trei rute

- **2026-08-07 (10) — Tura 7: Acasa isi spune ziua; docul nu mai pierde trei rute.**
  Salutul statea in `ui.pageHeader` (bara de sus), care e `display: none` sub
  768px — iar Acasa e SINGURA pagina fara titlu propriu, tocmai ca sa nu existe o
  banda in plus. Cele doua reguli se anulau: pe telefon nu scria nicaieri ce zi e.
  Ziua a trecut pe capul boardului („Astăzi · Vineri, 7 august"), unde nu costa
  niciun rand nou, si se recalculeaza la `visibilitychange` + un tic de un minut
  (era scrisa o data, in `onMount`: deschis dimineata, scria „Bună dimineața" si
  seara). **Majuscula se pune in JS pe prima litera**, nu cu `text-transform:
  capitalize` — acela da „Vineri, 7 August", iar in romana luna e cu litera mica.
  `UrmatoareaIesire` foloseste acum `--loc-site` / `--loc-sediu` (purta `--accent`
  si `--purple`: un fapt binar imprumuta cerneala identitatii). „Fara perioada" se
  arata mereu, nu doar in ramura goala. „De clarificat" duce pe ziua celei mai
  vechi si scrie `1 / N`. Linia are o casuta care ii tine locul cat se incarca —
  altfel boardul sarea in jos cu ~46px cand sosea raspunsul.
  **Docul:** al cincilea slot e „Mai mult", o foaie cu Proiecte / Departament /
  Calculator la 44px, cu cautarea in cap. Cele cinci tinte raman decizia corecta;
  gresit era ca singurul drum spre celelalte trei trecea prin paleta de comanda —
  o unealta de TASTATURA, pe un ecran fara Ctrl. `CommandPalette` exporta
  `deschide()`; butonul nu mai trimite un `KeyboardEvent` sintetic.
  **Doua capcane la foaie:** ancorata cu o socoteala hardcodata iesea 2px peste doc
  (uitasem bordura) — acum e copil al docului cu `bottom: 100%`, deci se lipeste de
  marginea lui reala; si `fly` scrie `transform` inline, deci SUPRASCRIA
  `translateX(-50%)`-ul de centrare (invelisul centreaza, `fly` anima copilul).
  Cat timp foaia e deschisa, dockul nu se mai ascunde la derulare.
