# Planificator: înălțimea vine din împachetare (turele 4–6, 2026-08-08)

## Din CLAUDE.md

Ultima bucată a handoff-ului. Restul turei era deja construit din runde vechi (fereastra din
azi, cele cinci orizonturi, banda de perioadă, coloana de restanțe); ce lipsea era **regula
rândurilor**, **antetul de timp** și **orizontul lung**.

- **`packRows` măsoară ce se desenează, nu ziua.** Reperul e acum chiar coloana termenului
  (bară de o zi, 20px, contur = de făcut · plin = în lucru · tentă verde cu bifă = făcut), iar
  titlul **iese din ea**, la dreapta. Deci întinderea unui reper e *bara + titlul*, nu una din
  ele. ~~Rândul: `14 + n×20 + (n−1)×4 + 6`, minim 48~~ → **înlocuit 2026-08-15**, vezi
  „Perioada e o șină la baza rândului" mai jos: `6 + n×20 + (n−1)×4 + 20`, minim 44 →
  **1 reper 46 · 2 repere 70 · 3 repere 94**. Stiva nu se mai centrează, se **ancorează sus**.
  - ~~**Eticheta perioadei ține rândul întâi**~~ — **nu mai e adevărat.** Perioada nu mai scrie
    nimic în pistă, deci `packRows` se cheamă cu `blocate` GOL. Asta e chiar sursa scăderii de
    înălțime: rândul nu mai crește din coliziuni.
  - **Suprapunerea se testează cu TOT rândul, nu cu ultimul așezat.** Greedy-ul clasic „după
    ultimul" presupune că totul intră în ordine. Regula rămâne corectă și utilă (două repere
    apropiate), chiar dacă rândul întâi nu mai pornește ocupat.
  - **Numele de proiect a revenit pe UN rând.** Cu două rânduri, eticheta cerea 73px și
    `min-height: 48` nu mai însemna nimic: o bandă cu un reper și una cu trei arătau la fel —
    adică exact ce trebuia să spună înălțimea. Numele reale se despart de la primele caractere;
    ce se repetă e *sufixul* de client („— Continental"), adică fix ce pierde o trunchiere la
    dreapta.
  - **Întoarcerea titlului (`flip`) e geometrică, nu un prag.** Era `left > 62`, ales pentru
    altă geometrie: un reper la 64% cu titlu de 15% se măsura spre STÂNGA, peste bandă, și
    cobora trei rânduri degeaba. Acum se întoarce doar când n-ar încăpea la dreapta.
    (Se aplica ~~și etichetei unei perioade~~ — de la 2026-08-15 perioada n-are etichetă în
    pistă, deci `flip` a rămas doar al reperelor.)
- **Antetul are o singură structură: grosier peste fin.** Rând de săptămâni (S32 · S33)
  peste rândul de zile (inițială + cifră), 52px. Separator `--border` între coloane,
  `--border-strong` la granița grupei, **coborând continuu prin toate benzile**. Grupele nu-și
  recalculează muchiile: le adună din coloanele fine (`grupeazaColoane`), altfel două socoteli
  ale aceleiași margini se despart la a treia zecimală — și se vede, fiindcă linia groasă
  coboară prin bandă. **`.col-line` stă pe muchia din STÂNGA**, deci granița ei e `i-1`.
  - **Luna nu stă în antet** — o spune subtitlul paginii („de azi, 14 zile · 8–21 aug").
  - **„Azi" are aceeași formă ca orice coloană**, doar că scrie „azi" în loc de inițială, în
    accent, pe tentă. **Fără inel** (rezervat zilei de sub cursor la tragere) și **fără linia
    de 2px**: fereastra pornind mereu din azi, linia stătea la `left: 0`, lipită de cusătură,
    unde citea ca bordură de tabel. Rămâne coloana tentată, cu două muchii de accent.
- **La 3L/6L antetul urcă un nivel: luni peste SĂPTĂMÂNI.** De aceea `buildColumns` primește
  `unitCerut` și Planificatorul cere `week` și la 6L — implicitul dădea luni, iar peste luni
  n-are ce să mai urce. Ganttul de proiect nu cere nimic și rămâne pe scara veche: fereastra
  lui vine din date și poate ține un an, unde 52 de coloane de săptămână ar fi trei ecrane.
  - ~~Perioadele devin **bare pe rândul întâi** cu eticheta **lângă** ele~~ — **scos
    2026-08-15.** Exact mecanismul ăsta (`.ib-out`) avea un bug: eticheta ieșea din bandă fără
    să verifice dacă locul de afară e liber, deci două perioade pe același rând își tipăreau
    numele **una peste alta**, ilizibil (măsurat: 2 perechi, la 3L și la 6L). Acum perioada e
    aceeași șină la toate orizonturile; **lățimea minimă de 11px a rămas**, ca regulă CSS.
  - **Reperele se strâng într-un număr pe săptămână** (`.count accent`, aceeași pastilă ca
    peste tot). Nu deschide nimic și nici n-ar avea unde: fereastra pornește mereu din azi,
    deci nu există zi pe care să aterizezi. Spune în ce săptămână se îngrămădesc — adică unde
    cobori la 14z. Indicația de sub pistă se schimbă odată cu ele: una care promite un gest
    inexistent e mai rea decât niciuna.
  - Pe telefon scara arată **grupele** (lunile) la 3L/6L: 27 de coloane de săptămână pe 350px
    ar fi 13px fiecare, adică o dungă fără cifre.
  - **`iso` rămâne gol pe coloanele de săptămână.** Ganttul de proiect îl compară cu ziua de
    azi (`c.iso === today`); cu data de luni acolo, săptămâna s-ar aprinde o zi din șapte.
    Coloana care CONȚINE azi se află din procente (`contineAzi`), nu dintr-o egalitate.

## Din MEMORY.md

- **2026-08-08 (2) — Planificator, turele 4-6: inaltimea vine din impachetare.**
  `packRows` masoara bara PLUS titlul care iese din ea (reperul e acum coloana
  termenului, 20px, cu titlul la `left: 100%`), iar eticheta perioadei tine
  randul intai. Rand: `14 + n*20 + (n-1)*4 + 6`, minim 48 (1/2/3 repere =
  48/64/88). Suprapunerea se testeaza cu TOT randul, nu cu ultimul asezat —
  randul intai porneste ocupat pe mijloc. Numele de proiect a revenit pe UN rand:
  cu doua, eticheta cerea 73px si `min-height: 48` nu mai insemna nimic.
  Antetul: saptamani peste zile (52px), `--border-strong` la granita, coborand
  prin benzi; luna NU mai e in antet, o spune subtitlul. La 3L/6L urca un nivel
  (luni peste saptamani) — de aceea `buildColumns` primeste `unitCerut`, iar
  Planificatorul cere `week` si la 6L; Ganttul de proiect ramane pe scara veche.
  Perioadele devin bare de rand cu eticheta langa si `min-width: 11px`, reperele
  se strang intr-un numar pe saptamana. **Capcane:** `.col-line` sta pe muchia
  din STANGA, deci granita ei e `i-1`, nu `i`; `iso` trebuie sa ramana gol pe
  coloanele de saptamana (Ganttul il compara cu `today`); `flip` e geometric
  (`left + width + eticheta > 100`), nu un prag fix — cel vechi (62) intorcea
  repere care aveau loc si le cobora trei randuri degeaba.
