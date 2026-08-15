# Contorul de pași se întoarce pe rând (2026-08-15)

## Din CLAUDE.md

Ion: *„la taskuri, când are subtaskuri ar fi bine să arate un counter subtil undeva,
câte din câte sunt îndeplinite."* Asta **ridică interdicția E1** („fracția de pași nu
stă pe rând, rândul poartă două lucruri — ce e de făcut și când"), pusă la redesignul
din 8 august. Se ridică în **toate cele patru liste deodată**: `/tasks`, „Astăzi",
tabul Taskuri al proiectului și rândul mobil din Planificator.

- **O rețetă, un loc: `components/ui/ContorPasi.svelte` + `.tpasi` în `global.css`.**
  Forma (SVG-ul) stă în componentă, culorile în `global.css`; apelanții dau doar
  `gata`/`total` și componenta se randează ca **nimic** dacă `total` e 0 — altfel
  același `{#if}` s-ar repeta în patru locuri. Înainte, același fapt avea o haină pe
  „Astăzi" (`.a-pasi`, pe linia a doua), niciuna în celelalte trei, și un
  `.tsub-chip` mort în `global.css` fără niciun consumator.
- **Inel + fracție — și inelul rămâne inel, cu gaură.** Direcția a ales-o Ion dintre
  șapte machete (`ContorPasi.dc.html`), și a fost nevoie de **două** corecturi ca să
  ajungă acolo:
  1. `r=5` cu `stroke-width: 2` **nu se citea**: la 12px o bandă de două puncte n-are
     suprafață din care să vezi cât e umplut — pe machetă, „0/3" și „5/5" arătau
     aproape la fel.
  2. `r=3` cu `stroke-width: 6` (contur întins de la centru până la margine) se citea,
     dar ieșea o **plăcintă**. Ion: *„acum e disc, nu inel."* Direcția aleasă se numea
     inel, iar un inel are gaură.
  Răspunsul e să **îngroși banda, nu s-o umpli**: `r=4.5` cu `stroke-width: 3`
  desenează între r=3 și r=6 — bandă de 3px (cu 50% mai groasă decât la prima
  încercare, deci vizibilă) și gaură de 6px care rămâne la orice umplere, inclusiv
  la 5/5. Pista și arcul iau **aceeași rază și aceeași grosime**: sunt fețele
  aceluiași inel, nu două cercuri concentrice.
  Nu se confundă cu bifa de la capătul rândului: aceea e un cerc de 18px, mereu gol,
  cu contur de 1.5.
  `rotate` se scrie ca **atribut SVG**, nu `transform-origin` în CSS: pe elementele
  SVG originea implicită e colțul viewport-ului, și ar cere și `transform-box`.
- **Lângă titlu, nu într-o coloană.** O coloană ar fi goală pe majoritatea rândurilor,
  iar o coloană cu goluri nu se mai citește pe verticală — adică pierde exact singurul
  motiv pentru care termenul e coloană. Contorul răspunde la „cât din lucrul ăsta",
  deci se leagă de titlu; termenul răspunde la „când" și rămâne pironit la dreapta.
- **Fără culoare, nici la 5/5.** Pe rândul de task culoarea e rezervată severității
  (inelul bifei + textul termenului, amândouă din `--ring`); o tentă verde ar fi al
  treilea canal cromatic, adică fix ce a demontat tura 9. Că e gata pe dinăuntru o
  spune cifra — și tot ea spune și cât mai e, ceea ce o tentă nu poate.
- **Și fără mono** — Gabarito 13/400, sub cele 15/500 ale titlului. Prima livrare l-a
  scris în DM Mono și Ion a cerut „mai subtil și mai estetic"; regula era deja scrisă
  mai sus: *mono = cifre care se compară pe verticală*. Termenul e mono fiindcă e o
  coloană pironită, citită de sus în jos; contorul plutește după un titlu de lungime
  variabilă, deci nu se aliniază cu nimic și n-are ce compara. Lângă literele rotunde
  ale lui Gabarito, cifrele late și bara oblică groasă a unui monospațiat se citeau ca
  un fragment de cod lipit pe rând. Măsurat: „1/4" trece de la 23px la 16, iar pe
  telefon nu se mai citește împreună cu termenul mono de alături.
  **`tabular-nums` a plecat atunci și s-a întors odată cu inelul**, din alt motiv:
  nu alinierea, ci stabilitatea. Cu cifre proporționale „1/4" și „2/4" n-au aceeași
  lățime, deci la fiecare bifă tot contorul — inclusiv felia — s-ar deplasa lateral.
  Singurul lucru care are voie să se miște când bifezi un pas e felia care crește.
- **Cea mai proaspătă sursă câștigă.** `pasi()` (în `Tasks.svelte` și `ProjectDetail`)
  citește din `subtasksCache` când există, altfel din `subtask_total`/`_done` de la
  server. Fără asta, bifarea unui pas în rândul desfăcut nu mișca cifra de deasupra
  lui: `toggleSubtaskDone` scrie în cache și **nu** reîncarcă lista. Un `[]` în cache
  înseamnă „am întrebat, n-are niciunul", deci scoate contorul.
- **Scrierile de subtask invalidează acum listele** (`uitaSubtaskuri` în
  `stores/tasks.svelte.js` → `/api/global-tasks`, `/api/plan`, `/api/proiecte`).
  Fișierul își scria regula în cap — „orice scriere invalidează lista" — dar cele trei
  mutații de subtask erau singurele scutite. Era invizibil cât timp nicio listă nu
  arăta date de subtask; de acum, fără ele, bifai un pas, plecai de pe pagină și
  cifra veche revenea din cache. Toate trei prefixele, fiindcă `updateSubtask` are
  doar id-ul subtaskului: de acolo nu se poate ști dacă părintele e task de proiect
  sau global.
- **`.mrow-main` din Planificator și `.amain` de pe „Astăzi" sunt coloane**, deci
  titlul a primit un înveliș de rând (`.mrow-titlu` / `.atitlu`). Pe „Astăzi",
  `align-self: flex-start` a urcat pe înveliș: pe titlu ar fi însemnat aliniere pe
  verticală, iar el era acolo ca tăietura de „done" să se oprească la ultima literă.
- **`.tmain` din `ProjectDetail` era coloană degeaba** — rămăsese de pe vremea celei
  de-a doua linii (`.tinfo`), care n-avea niciun consumator în markup de la E1 încoace.
  Cu ea, contorul ar fi aterizat *sub* titlu aici și lângă el în celelalte trei.
- **Prins în aceeași trecere:** pe „Astăzi" contorul era gardat pe `contextRand(it)`
  împreună cu întreaga linie a doua, deci un task cu pași dar fără proiect și fără
  categorie nu-l arăta deloc.

## Din MEMORY.md

- **2026-08-15 (4) — CONTORUL DE PASI SE INTOARCE PE RAND.** Ion: „la taskuri, cand
  are subtaskuri ar fi bine sa arate un counter subtil undeva, cate din cate sunt
  indeplinite." Ridica interdictia E1 din redesignul de pe 8 august („fractia de
  pasi nu sta pe rand"), in TOATE cele patru liste deodata: `/tasks`, „Astăzi",
  tabul Taskuri al proiectului, randul mobil din Planificator.
  - **Forma finala: INEL + FRACTIE**, aleasa de Ion dintre sapte machete
    (`ContorPasi.dc.html`, pastrata in repo ca urma a deciziei). Componenta
    `components/ui/ContorPasi.svelte` tine forma, `.tpasi` din `global.css` tine
    culorile; apelantii dau doar `gata`/`total`, iar componenta se randeaza ca
    NIMIC cand `total` e 0 — altfel acelasi `{#if}` s-ar repeta in patru locuri.
  - **Inelul: se INGROASA banda, nu se umple discul.** Doua corecturi pana acolo:
    (1) `r=5` + `stroke-width: 2` NU SE CITEA — la 12px o banda de doua puncte
    n-are suprafata din care sa vezi cat e umplut, si „0/3" si „5/5" aratau
    aproape la fel (am spus-o inainte ca Ion sa aleaga); (2) `r=3` +
    `stroke-width: 6` se citea, dar intinde conturul de la centru la margine,
    deci iese o PLACINTA — Ion: „acum e disc, nu inel". Directia se numea inel.
    Final: `r=4.5` + `stroke-width: 3`, adica banda intre r=3 si r=6 — cu 50% mai
    groasa decat prima incercare, si gaura de 6px ramane la ORICE umplere.
    Pista si arcul au aceeasi raza si aceeasi grosime: sunt fetele aceluiasi
    inel, nu doua cercuri concentrice.
    `rotate` se scrie ca ATRIBUT SVG, nu `transform-origin` in CSS — pe elemente
    SVG originea implicita e coltul viewport-ului si ar cere si `transform-box`.
    **Morala, pentru orice indicator mic:** cand un semn de 12px nu se citeste,
    intrebarea e „cat de groasa e banda", nu „cat de plina e forma" — umplerea
    schimba OBIECTUL, grosimea doar il face vizibil.
  - Cifrele: Gabarito 13/400, `--text-dim`, LANGA TITLU. Nu coloana: ar fi goala pe majoritatea randurilor,
    iar o coloana cu goluri nu se citeste pe verticala — adica pierde exact motivul
    pentru care termenul e coloana. A inlocuit `.tsub-chip`, mort in `global.css`
    de la redesign, si `.a-pasi`, care traia doar pe „Astăzi".
  - **Fara culoare, nici la „5/5".** Pe randul de task culoarea e rezervata
    severitatii; o tenta verde ar fi al treilea canal cromatic (tura 9).
  - **NU E MONO, si asta e regula sistemului, nu gust.** Prima livrare l-a scris
    in DM Mono si Ion a cerut „mai subtil si mai estetic" — avea dreptate, si
    motivul era scris deja in `CLAUDE.md`: mono e pentru cifre care SE COMPARA PE
    VERTICALA. Termenul e mono fiindca e coloana pironita; contorul pluteste dupa
    un titlu de lungime variabila, deci nu se aliniaza cu nimic. Langa literele
    rotunde ale lui Gabarito, cifrele late si bara oblica groasa a unui
    monospatiat se citeau ca un fragment de cod lipit pe rand. In Gabarito 400
    (titlul e 500) „1/4" masoara 16px, nu 23 — si pe telefon nu se mai citeste
    impreuna cu termenul mono de langa el.
    `tabular-nums` a plecat atunci si S-A INTORS odata cu inelul, din alt motiv:
    nu alinierea, ci stabilitatea — cu cifre proportionale „1/4" si „2/4" n-au
    aceeasi latime, deci la fiecare bifa tot contorul (si felia) s-ar deplasa
    lateral. Singurul lucru care are voie sa se miste la bifare e felia.
  - **Bugul de fond, si singura parte care nu era cosmetica:** `createSubtask` /
    `updateSubtask` / `deleteSubtask` erau SINGURELE mutatii din
    `stores/tasks.svelte.js` care nu invalidau nimic, desi fisierul isi scrie
    regula in cap. Invizibil cat timp nicio lista nu arata date de subtask; de
    acum, fara `uitaSubtaskuri()` (global-tasks + plan + proiecte), bifai un pas,
    plecai de pe pagina si cifra veche revenea din cache. Toate trei prefixele,
    fiindca `updateSubtask` are doar id-ul subtaskului, deci de acolo nu se poate
    sti daca parintele e task de proiect sau global.
  - `pasi()` citeste din `subtasksCache` cand exista, altfel de la server:
    `toggleSubtaskDone` scrie in cache si NU reincarca lista, deci altfel cifra nu
    s-ar misca exact cand o privesti. `[]` in cache = „am intrebat, n-are niciunul".
  - Prins pe drum: pe „Astăzi" contorul era gardat pe `contextRand(it)` odata cu
    toata linia a doua — un task cu pasi dar fara proiect si fara categorie nu-l
    arata deloc. Iar `.tmain` din `ProjectDetail` era coloana degeaba, de pe vremea
    lui `.tinfo` (fara consumator in markup de la E1 incoace).
  - **Capcana de test:** proba de reordonare din `audit_mobil` PICA pe o baza
    insamantata cu un task RESTANT — sortarea serverului pune restantele primele
    (`0 if is_restant else 1`), deci ordinea trasa cu degetul nu poate supravietui
    unui reload, oricat de corect ar fi salvata. Insamanteaza fara restante.
  - Verificat: build curat, `audit_design` curat, `smoke_ui` 20/20, `audit_mobil`
    curat (pe baza insamantata: si gesturile, si lista de facut), `audit_navigare`
    toate contractele, plus o proba AD-HOC de 22 de verificari, NECOMISA (contorul
    in cele patru liste, absent fara pasi, geometrie pe 360/390px, bifare
    1/4 -> 2/4 sub 250ms, cifra pastrata dupa navigare si dupa F5, si — important
    pentru inel — ca `stroke-dasharray` chiar corespunde fractiei: 2/5 = 40%,
    3/3 = 100%, 1/4 = 25%. Fara masuratoarea aia, un inel desenat mereu la fel ar
    trece toate probele de text.)
    Daca invarianta „o scriere de subtask invalideaza cele trei liste" se mai
    rupe o data, merita mutata intr-un script din `scripts/` — niciunul dintre
    cele cinci audituri existente nu o atinge.
