# 2026-07-30 — Randul bifat pleaca vizibil; si doua capcane Svelte care suprimau animatia in tacere

- **2026-07-30 (10) — Randul bifat pleaca vizibil; si doua capcane Svelte care
  suprimau animatia in tacere.** Ion: „fă". Animatia in sine e cinci linii
  (`plecare` in `lib/motion.svelte.js`: se stinge SI se strange, cu o impingere mica
  spre dreapta — directia gestului de bifare de pe telefon). Drumul pana la ea a
  scos la iveala trei lucruri:
  **(1) Bifarea astepta serverul.** Randul pleca dupa `await update` + `await reload`,
  adica ~200ms de nimic dupa atingere. Acum lista se schimba OPTIMIST, iar `catch`
  reincarca daca cererea pica. Fara asta, animatia nu se citeste ca raspuns la gestul
  tau, ci ca ceva ce se intampla singur, mai tarziu.
  **(2) `{#if globalTasks.loading}` distrugea TOATA lista la fiecare actiune.**
  `loadGlobalTasks()` se cheama dupa orice modificare, deci fiecare bifare / mutare
  de termen / adaugare inlocuia lista cu cinci schelete si o reconstruia. O clipire
  pe fiecare gest, si — efect secundar — nicio animatie de iesire nu se putea vedea,
  fiindca subarborele ei era demolat in aceeasi clipa. Corect: `&& items.length === 0`
  (schelete doar la prima incarcare), regula pe care TodayBoard o avea deja.
  **(3) CAPCANA SVELTE, meritata scrisa:** un `{#each}` IMBRICAT peste obiecte NOI la
  fiecare recalcul face Svelte sa RE-CREEZE blocul interior in loc sa-l actualizeze —
  chiar si cu cheie stabila pe `g.id` — iar randurile dinauntru sunt distruse fara
  sa-si joace tranzitia de iesire. Zero erori, zero avertismente. Masurat: **0 cadre
  de animatie** cu each imbricat pe obiecte, **13 cadre** cu acelasi rand intr-un each
  de nivel superior. Solutia: `grupeazaDupaTermen` intoarce acum un OBIECT, iar
  sablonul itereaza `ORDINE_GRUPE` — un array constant de siruri — si citeste
  `grupe[id]`. Blocul exterior nu se mai schimba niciodata.
  **(3b) Al doilea strat al aceleiasi capcane:** grupele goale trebuie sa ramana in
  obiect. Daca `{#if grupe[gid]}` se stinge cand grupa ramane fara randuri, blocul in
  care tocmai pleaca ULTIMUL rand e distrus — deci exact cazul cel mai vizibil (bifezi
  ultimul restant) ramanea fara animatie. Sablonul ascunde capul gol; un cap n-are
  nevoie de tranzitie, un rand da.
  Verificat cu o sectiune noua in `audit_mobil.py` care esantioneaza OPACITATEA
  randului la fiecare cadru: cere >= 3 cadre intermediare (adica s-a stins, n-a sarit)
  si plecare sub 900ms (adica n-a asteptat serverul). Ambele liste, ambele conditii.
