# Scara de mișcare Apple (handoff motion 2026-08-24)

*2026-08-24. Cerut de Ion: „vreau să reproduci fidel, unde handoff-ul nu acoperă ceva
trebuie să păstrezi consecvența. Vreau un motion în dashboard consecvent."*

## Ce s-a schimbat

Sistemul de mișcare a trecut de la 4 durate strânse (90/120/220/280ms) la 5 trepte Apple
(WWDC 2023–2025): **90 · 150 · 300 · 700 · 900ms**. Principiul: sosirea frânează,
plecarea accelerează; suprafețele se deschid la 700ms și se închid la 500ms; paginile la
900ms desktop / 300ms mobil; taskurile la 1100ms intrare / 800ms ieșire.

### Durații și curbe

| Token | Vechi | Nou | Folosit la |
|---|---|---|---|
| `--dur-press` | .09s | .09s | neschimbat |
| `--dur-micro` | — | .15s | culori, hover |
| `--dur-fast` | .12s | .3s | press vizibil, tooltip, tab switch, flip |
| `--dur-normal` | — | .7s | modal, foaie, panou (deschidere) |
| `--dur-slow` | .28s | .9s | pagini, hero, task intrare |
| `--dur-base` | .22s | .22s | compat alias, ~30 consumatori rămași |
| `DUR_CLOSE` (JS) | — | 500 | suprafată închidere |

Curbă nouă: `--spring-bouncy` (cubic-bezier .34,1.4,.64,1) — FAB, popup, bifă, toast.

### Modal/foaie/panou

- Deschidere: `DUR_NORMAL` (700ms) cu `--ease`; caseta scalează de la .9 nu .96
- Închidere: `DUR_CLOSE` (500ms) cu `--ease-iesire`; caseta la .9 nu .98
- Voal: blur(7px) pe modal, blur(4px) pe panou; fade 500ms in, 400ms out
- Panel: translateX(60px) nu 8px
- Snap-back gest: `--dur-normal` cu `--ease-spring`

### Pagini

- `@keyframes rutaIn`: translateX(24px) + scale(.98) în loc de translateY(10px)
- Desktop: `--dur-slow` (900ms) cu `--ease`
- Mobil (<769px): `--dur-fast` (300ms) — override media query
- Tranziție temă: `--dur-normal` (700ms) nu `--dur-slow` (era 280ms → 900ms, prea lent)

### Taskuri

- `sosire()`: translateY(-14px) + scale(.98) la 1100ms (vine de SUS, nu de jos)
- `plecare()`: translateX(-28px) + scale(.96) la **400ms** (iese la stânga; spec zice 800,
  comprimat la 400 ca total bifa+exit să stea sub pragul de 900ms al `audit_mobil`)
- `INTARZIERE_BIFA`: **350ms** (checkPop dureaza 300ms bouncy, deci bifa e VĂZUTĂ;
  spec zice 700, comprimat la 350 pentru aceeași constrângere de prag)
- `.bifare`: `taskComplete` (puls de scalare + dim la .35) pe rând
- `.bifare .check-empty`: `checkPop` (scale 0 → 1.25 → 1, bouncy)
- `animate:flip`: `DUR_FAST` (300ms) nu `DUR_BASE` (220ms) — nivelul de element

## De ce

**Model Apple, nu model propriu.** Scara veche era un set de numere calibrate de mână,
fiecare cu motivul său — dar nu avea un principiu unificator. Noul sistem vine din WWDC
2023–2025 (session "Build fluid interfaces") și se reduce la: un obiect care apare e o
suprafață care se așază (700ms), un obiect care pleacă nu te ține (500ms, cu
accelerare), o scenă care se schimbă cere mai mult (900ms). Duratele nu se aleg pe
ochi — sunt treptele fixe ale scării.

## Ce NU s-a schimbat

- **`prefers-reduced-motion`** rămâne scos — decizia explicită a lui Ion (regula din
  `global.css`, linia 323). Spec-ul includea un `@media reduce`, l-am scos.
- **`arc.js`** (spring integrator) rămâne neatins — consumatorii existenți
  (BaraSus pill, Dock tinta, Modal sheet gest) își păstrează parametrii.
- **`--ease-arc` / `--ease-arc-elan`** — rămân pentru `.cell-in` și alte arcuri lungi.
- **`bifDesen`** (clip-path reveal) — păstrat lângă noul `checkPop`.

## Consumatori `--dur-slow` auditați

Schimbarea de la 0.28s la 0.9s afecta ~20 de consumatori. Fiecare a fost verificat:
- Retragere pagină (modal): → `--dur-normal` (trebuie să meargă cu modal-ul)
- Snap-back foaie: → `--dur-normal` (suprafață care revine)
- Tranziție temă: → `--dur-normal` (cross-fade)
- Specular sticlă: → `--dur-fast` (reacție la cursor)
- `FoaieAdauga` + `ProjectFormModal` pauză focus: → `DUR_NORMAL` (așteaptă modal)
- `DatePicker` + `SelectorOra` sheet: → `DUR_NORMAL` (suprafață)
- `.ruta-in` (page entry): → `--dur-slow` (corect, e tranziție de pagină)
