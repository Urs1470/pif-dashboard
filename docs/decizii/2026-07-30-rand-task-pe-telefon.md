# 2026-07-30 — Randul de task pe telefon: o linie + glisare; Planificatorul isi recapata timpul

- **2026-07-30 (5) — Randul de task pe telefon: o linie + glisare; Planificatorul isi
  recapata timpul; Calendarul se reaseaza.** Ion, dupa prima trecere: „acum sunt cam rupte,
  prea mari pe inaltime; sa fie aproape de cum sunt pe aplicatii de to do mobile".
  **(1) `lib/glisare.js`** — actiune Svelte refolosita de toate cele patru liste de taskuri
  (Acasa, Planificator, Taskuri, ProjectDetail). Glisare stanga = panou de actiuni; glisare
  dreapta = bifeaza; atingere pe titlu = deschide. Randurile: 172 -> 62px (Acasa), 110 -> 56
  (Taskuri), doua linii -> 56 (Planificator). **Trei lucruri obligatorii:** directia se decide
  O SINGURA data la primii 8px (altfel lista nu se mai poate derula vertical); `touch-action:
  pan-y` lasa derularea browserului nativa; un singur rand deschis global; `click`-ul de dupa
  gest se inghite in faza de capturare, altfel ajunge la ce era dedesubt.
  **Capcana:** `setPointerCapture`/`releasePointerCapture` arunca `NotFoundError` daca
  pointerul nu mai e activ si rupeau restul gestului — sunt intr-un try/catch, captura e o
  imbunatatire, nu o conditie.
  **(2) `.app-content` avea `overflow-y: auto`** — a doua oara aceeasi capcana ca la
  `.app-main`: face container de derulare, deci ORICE `position: sticky` dintr-o pagina se
  raporta la scrollportul lui, care nu deruleaza niciodata (documentat inca din 2026-07-03:
  fereastra deruleaza, nu `#main-content`). Mureau in tacere: antetul de zile din Planificator,
  bara laterala din pagina de proiect, capul de tabel, navigarea din Calculator. Scos.
  **(3) Planificatorul are timeline si pe telefon.** Sub 820px swimlane-ul era ascuns si ramanea
  o lista fara timp. Acum fiecare grup de proiect are BANDA lui — acelasi lane, intors la latime
  plina, cu numele deasupra in loc de la stanga — plus un antet de zile COMUN si lipicios sub
  bara aplicatiei. Geometria e cea existenta (`spanRect` da procente), zero calcule noi.
  Reperele de task sunt puncte care duc la randul lor din lista, cu `focus-flash` — nu deschid
  un al treilea meniu. **Aliniere:** `--m-pad` = rama grupului (1) + paddingul lui (8) +
  marginea benzii (3); daca cele trei nu sunt in acord, coloana „marti" cade langa marti.
  **(4) Calendar reasezat pe o coloana:** panoul zilei statea DEASUPRA grilei, deci atingeai o
  zi si raspunsul aparea in afara ecranului. Acum harta, apoi ziua atinsa sub ea, apoi
  contoarele (rezumat, nu intrebare de inceput).
  **(5) Legenda chiar era stricata:** „pe teren" si „implementare" aveau EXACT aceeasi umplere
  (45%) — doua patratele identice cu doua intelesuri. Nu e scapare de culoare: ambele axe
  folosesc „plin" pentru valoarea pozitiva. Se repara numind intrebarea („Unde" / „Fază"), nu
  schimband mostra; mostrele folosesc acum aceleasi retete ca benzile din grila.
