# Un gest = un verb, în ambele sensuri (2026-08-07)

## Din CLAUDE.md

Glisarea spre stânga **descoperea un panou** de 3–4 acțiuni × 58px: 176px (Astăzi)
sau 232px (`/tasks`, proiect) din 390, deci taskul pe care acționai dispărea aproape
complet de sub deget. Iar „Șterge", ultimul din panou, cădea exact unde ajunge o
glisare rapidă. În plus cele două direcții aveau două modele mentale („deschide un
meniu" vs „execută"), deci se învățau separat.

`lib/glisare.js` primește `onAmana`: când e dată **și nu există `latime`**, stânga
execută un verb, simetric cu `onBifa`. Clase la rulare `gl-stanga` / `gl-amana`,
variabilă `--gl-s` (oglinda lui `--gl-p`), același prag de 42%.

**Verbul diferă după ce e pe ecran, deliberat:**

| suprafață | stânga | de ce |
|---|---|---|
| „Astăzi" | deschide **calendarul** (`.dp-gest`) | vezi mai jos |
| `/tasks` | deschide foaia cu **panoul de termen desfăcut** | termenele sunt împrăștiate pe săptămâni; „mâine" ar fi o zi aleasă de aplicație |
| pagina de proiect | deschide **modalul de editare** (are câmpul Termen) | acolo nu există foaie |
| rândul de **subtask** | execută **„Șterge"**, pistă `--danger` (`.gl-sub`) | pubela permanentă de 44px a plecat de pe rând |

Pe „Astăzi" gestul a executat o vreme **„Mâine"** — părea verbul potrivit, fiindcă
tot ce vezi acolo e scadent azi. Ion: *„trebuie data picker"*. Amânarea nu e „încă
o zi": muți un task când știi CÂND îl faci, iar ziua aia e rareori mâine. Deci
toate cele trei liste duc acum la aceeași întrebare — **ce zi?**

Calendarul de pe „Astăzi" e **unul pe board**, nu unul pe rând: pe telefon
`.arow-actions` nu se randează, deci nu există declanșator de apăsat. Instanța stă
într-un înveliș de 0×0 (`.dp-gest`), iar sheet-ul ei se mută oricum în `body`
(`use:portal`), deci învelișul strâns nu-l taie. `DatePicker` a primit
`export function deschideCalendarul()` — aceeași funcție ca la clic, ca luna
afișată să fie așezată la fel.

**Calendarul se deschide pe luna TERMENULUI**, nu pe luna curentă. Pe board
taskurile sunt scadente azi sau restante, deci grila e adesea o lună **trecută** —
iar o zi din trecut lasă taskul pe board, ca restant. E corect; contează doar când
scrii un test (vezi `audit_mobil`, care avansează până strict după luna curentă).

Pe subtask ștergerea din gest e acceptabilă **doar** fiindcă are `toastUndo` cu
commit întârziat — vezi paritatea reparată în `Tasks.svelte`.

`.gl-pista-s` trăiește în `global.css` (neschopat): `gl-amana` e pusă la rulare din
JS, iar Svelte **taie** regulile pe care le crede moarte în componente scopate.

Regresia e prinsă de `audit_mobil.py`, secțiunea **„gesturi"** — care a fost
rescrisă odată cu contractul: nu mai verifică un `transform` rămas după ridicare
(rândul se întoarce la zero, ca la bifare), ci că pista **crește pe parcurs** și
atinge pragul, apoi că verbul chiar s-a executat.

## Din MEMORY.md

- **2026-08-07 (7) — Gestul duce la ALEGEREA zilei, pe toate suprafetele; agenda de 7 zile a plecat.**
  Ion, la cele doua intrebari ramase deschise: „1. trebuie data picker  2. rezolv".
  Pe „Astăzi" glisarea spre stanga executa „Mâine" — parea verbul potrivit, fiindca
  tot ce vezi acolo e scadent azi. Dar amanarea nu e „inca o zi": muti un task cand
  stii CAND il faci. Acum deschide acelasi calendar ca butonul „Planifică" de pe
  desktop si ca foaia din /tasks. Calendarul e UNUL pe board, intr-un invelis de
  0×0 (`.dp-gest`): pe telefon `.arow-actions` nu se randeaza, deci nu exista
  declansator de apasat, iar sheet-ul iese oricum in `body` prin `use:portal`.
  `DatePicker` a primit `export function deschideCalendarul()` — deschidere din
  afara cu aceeasi asezare a lunii ca la clic.
  **Agenda de 7 zile** (`components/tasks/AgendaColumn.svelte`) a fost STEARSA: o a
  doua coloana de 300px care asezea aceleasi taskuri dupa aceeasi cheie — termenul
  — langa lista tocmai grupata dupa termen. Era deja `display: none` pe telefon; o
  coloana care nu-si plateste locul pe 390px nu si-l plateste nici pe 1440.
  **Capcana la verificare:** calendarul se deschide pe luna TERMENULUI, iar pe board
  taskurile sunt scadente azi sau restante — deci grila e adesea o luna TRECUTA, si
  o zi din trecut lasa taskul pe board ca restant. Corect, dar `audit_mobil` alegea
  „ultima zi din grila" si pica pe asta; acum avanseaza pana strict dupa luna
  curenta.
