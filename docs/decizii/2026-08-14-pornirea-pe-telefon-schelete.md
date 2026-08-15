# 2026-08-14 — Pornirea pe telefon si scheletele care mai ramasesera

- **2026-08-14 (4) — Pornirea pe telefon si scheletele care mai ramasesera.**
  Ion: „se vad rupturile la pornire" si „la schimbul pe un alt tab aproape tot
  timpul vad un schelet". Ambele confirmate — masurate, nu presupuse — dupa ce
  masuratoarea a fost reparata de doua ori:
  - **LOCALHOST MINTE.** Auditul rula pe `127.0.0.1`, unde o cerere se intoarce
    in 5ms, deci plafonul de 250ms al preincarcarii nu se atingea niciodata.
    Cu 150ms dus-intors (tunelul Cloudflare) au aparut cazuri reale.
  - **`MutationObserver` RATEAZA CLIPIRILE.** Pana ruleaza callbackul, scheletul
    poate fi deja scos — dar unul care prinde UN cadru tot se vede. Masuratoarea
    corecta e pe `requestAnimationFrame`. Asa au iesit Taskuri si Calendar cu
    exact un cadru de schelet la click rapid.
  - **KaTeX era pe drumul critic al listei de taskuri** — adica al ecranului cu
    care se deschide aplicatia pe telefon. `RichText`/`MarkdownView` -> `math.js`
    -> katex, 257 KB, terminand la 1623ms pe 4G. Acum `math.js` incarca KaTeX
    dinamic si **doar daca textul contine delimitatori**; `EditorLung` e import
    dinamic in Tasks, adus pe `requestIdleCallback`.
  - **Datele aterizarii pleaca din `main.js`, inainte de `mount`** — paralel cu
    chunkul rutei, nu dupa el. `/api/global-tasks` pornea la 1353ms si se
    intorcea la 1542; acum porneste la 826ms si e in mana INAINTE ca pagina sa se
    monteze. Merge doar fiindca `loadGlobalTasks` trece prin `preia`: cele doua
    apeluri se impart.
  - **`pregateste()` lipsea pe /tasks, /projects si /plan** — acolo hoverul
    aducea doar codul. Asta era cauza directa a reprosului „aproape tot timpul".
  - **Un schelet care clipeste e mai rau decat niciunul.** `Skeleton` are acum
    `intarziere = 110ms`: se arata doar daca asteptarea CHIAR exista. Regula e a
    scheletului, nu a paginii — altfel ar fi trebuit scrisa in douazeci de locuri.
  - **`uita()` sterge si cererile IN ZBOR**, iar `preia` nu mai scrie in memorie
    un raspuns dintr-o generatie trecuta: altfel „bific un task cat timp lista se
    reincarca" lasa in cache lista cu el nebifat.
  - Scheletul de ruta din App are acum forma paginii (randuri pe /tasks si
    /projects), nu blocul generic care statea 731ms si nu semana cu nimic.
  - Regresia: `audit_navigare.py`, sectiunea 8 — cu latenta si pe cadre.
