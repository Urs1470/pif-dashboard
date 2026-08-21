# 2026-08-21 — Deschidere vâscoasă, butoane proeminente, aterizare cu inel, swipe curat

Un val de reglaje pe mobil, toate din observațiile lui Ion pe telefon.

## Modalul de creare — deschidere vâscoasă, închidere fără „două modale"

- „Un pic prea agresiv se deschide" → o **pagină plină** nu mai soseste pe DUR_SLOW (280),
  ci pe `DUR_PAGINA` 400 cu `EASE_PAGINA` (easeOutExpo `cubic-bezier(0.16,1,0.3,1)`): pornește
  prompt și se așază încet, ca prin fluid. Iese în continuare iute (DUR_BASE + ease-iesire).
- „La închidere parcă sunt două modale" → cauza: făcusem fundalul STATIC (turul trecut, ca
  să scap de fantoma), dar atunci pagina din spate se citea ca un al doilea modal la fel de
  aprins. Acum fundalul **se retrage ȘI se dimează** (`scale(.92)` + voal `--scrim-plin`, .58
  light / .78 dark) și **rămâne așa cât timp foaia e în DOM** — `:has(.modal.pagina)` fără
  `are-modal`, deci ține pe toată ieșirea și se așază la loc abia după ce foaia a plecat.
  Nici fantomă (nu crește în urma foii), nici două suprafețe aprinse.

## Butoanele de adăugare — reactive + proeminente

- „Reacționează prea greu, trebuie o presiune mai mare" → puls haptic pe `pointerdown` +
  apăsare mai adâncă și imediată (`scale(0.9)` pe `--dur-press`), la FAB-ul din /tasks.
- „Butonul de pe Acasă … mai proeminent pe mobil" → Acasă primește **același FAB plutitor**
  ca /tasks (58px, peste dock, accent); butonul mic „Adaugă task" din capul boardului rămâne
  doar pe desktop.

## Aterizarea de pe Acasă → task: inel care pulsează

Ion voia „la fel" ca Planificator→Calendar (inel care pulsează), nu tenta pusă turul trecut.
`.focus-flash` pe rând e acum un **inel de accent care pulsează în două bătăi** (`inelPuls`,
opacitate — nu scale, fiindcă rândul e lat și tăiat de pista de glisare), `inset: 2px` ca să
se vadă în rândul tăiat.

## Swipe: colțuri curate la trecerea pragului

„Colțurile parcă se taie și nu mai e umplerea cum trebuie" → pistele de gest aveau `radius-md`,
mai mare decât `radius-sm` al învelișului care le taie (`overflow: hidden`) → colț de fundal
descoperit. Acum pistele au `border-radius: 0` și umplu tot dreptunghiul; învelișul le
rotunjește colțul.

## Planificator — orizontul

- Desktop: implicit **14 zile** (Ion: „cum a fost"), nu 30.
- Mobil: bara de alegere a orizontului **dispare** („nu are sens pe mobil"), vizualizarea e
  fixă pe 30 de zile (de care grila de patru săptămâni are nevoie oricum). Implicitul se
  alege din lățimea ecranului la init, ca să nu existe dublu-load pe telefon.
