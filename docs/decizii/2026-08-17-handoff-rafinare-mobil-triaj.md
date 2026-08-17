# 2026-08-17 — Handoff „Rafinare mobil TORQA": ce s-a luat, ce s-a respins

Handoff-ul de design (`design_handoff_mobil_torqa`, prototip HTML + README) a venit cu șase
propuneri (P1–P6) și un audit de mișcare pe **31 de interacțiuni**: 17 marcate rupte,
7 lipsă, 7 bune.

Textul de mai jos e triajul, cu verificarea făcută pe cod. Motivul pentru care există:
**auditul descrie prototipul, nu repo-ul.** O bună parte din „rupturi" erau deja rezolvate
aici, iar implementarea lor pe încredere ar fi însemnat să stric lucruri care mergeau.

## Verificat că exista DEJA, deși auditul îl dădea rupt

Fiecare a fost citit în cod sau măsurat în browser, nu presupus:

| Ce zicea auditul | Ce era de fapt |
|---|---|
| „Apăsarea pe orice buton — niciun răspuns, pe 60+ butoane" | `global.css` are podeaua `:where(button, [role=button], a.btn, .tab, .row, .zi):active` sub `@media (hover:none) and (pointer:coarse)`, cu specificitate ZERO ca să nu bată componentele |
| „Bifare — 400 ms în care nu se întâmpla nimic" | cei patru timpi există: `@keyframes bifStamp`, `bifDesen`, `bifTaie` |
| „Toast — ieșire: dispărea instant" | `out:fly` 180 ms |
| „Închiderea modalului: se demonta pe loc" | `out:intra` + `out:fade`; Svelte amână demontarea |
| „Schimbare de tab: ecranul se substituia brusc" | view-transitions + `.ruta-in`; `audit_navigare.py` testează exact asta |
| „Muncă ⇄ Personal: lista pocnea" | `{#key listaCheie}` + `in:alunecare` cu sens |
| „Mutare pe altă zi: rândul teleporta" | `in:sosire` / `out:plecare` / `animate:flip` |
| „Câmp nou în foaie: apărea tăiat" | acordeonul de termen are `transition:slide` |
| „Butonul plutitor rămânea blocat sub voal" | **măsurat:** ajunge la y=917 pe un ecran de 844 — se retrage odată cu pagina (`html.are-modal .app-main`), deci e deja coerent |
| „Trepte bază ⇄ ecran plin — era bună" | corect, dar de azi (commit `d81d4bd`); handoff-ul s-a sincronizat înainte |

## Luat

**Curba de ieșire (`--ease-iesire`).** Singura observație de fond din audit care era reală
și pentru repo: sistemul avea **o singură curbă pentru amândouă sensurile**. `--ease` e o
curbă de sosire (87% din drum în prima jumătate) — pusă și pe ieșire, obiectul zăbovește
exact când ar trebui să fie deja plecat.

Prima variantă a fost oglinda derivată a lui `--ease` — elegantă, fără un al doilea set de
numere de ținut sincronizat: oglinda unei `cubic-bezier(x1,y1,x2,y2)` e
`(1-x2, 1-y2, 1-x1, 1-y1)`, deci `(.72, 0, .68, .28)`. **Măsurată, a picat** pe o regulă pe
care repo-ul o are deja scrisă la `--dur-press` („sub ~100 ms legătura cauză-efect se
citește ca instantanee"): dintr-o ieșire de 220 ms, la 100 ms mutase foaia 6,9% din drum.

Interesant: valoarea din handoff (`.4, .02, .72, .06`, dată ca tunată pe telefon) dă 9,3% —
adică e practic tot oglinda, scrisă altfel. Două surse independente au nimerit aceeași
curbă, și amândouă sunt prea agresive ca să fie folosibile.

Luată: accelerarea standard `cubic-bezier(.4, 0, 1, 1)` — 11% la 60 ms, 27% la 100 ms,
viteză maximă fix când obiectul iese din cadru. Aplicată pe foaie, voal, panou, casetă, toast.

**Trecerea de temă.** Măsurat: `transition: all / 0s` pe body și pe carduri — ecranul chiar
pocnea dintr-o temă în alta. Cadrul primește 320 ms clasa `tema-trece`, care pune o tranziție
de CULOARE pe tot subarborele, apoi și-o scoate. Nu e permanentă: altfel fiecare hover ar
trage după el 280 ms și răspunsul la atingere s-ar simți moale peste tot.

Doar proprietăți de culoare, cu bunăștiință — o tranziție de `transform` forțată pe tot
arborele ar prinde, în cele 320 ms, obiecte care se mișcă din alt motiv (pastila din dock,
foaia trasă de deget) și le-ar da altă durată decât au. Tranzițiile Svelte nu sunt atinse:
ele merg pe `animation`, nu pe `transition`.

## Respins

**Pragul de gest 118px fix (P1).** Contrazice o decizie scrisă în `lib/gesturi.js`, cu
motivul măsurat: pragurile care se raportează la un obiect sunt **procente**, fiindcă un prag
fix nu înseamnă același lucru pe două obiecte de mărimi diferite. Rămâne `PRAG_ACTIUNE` 42%.

**Apăsare lungă 420 ms → foaie de acțiuni (P1).** Apăsarea lungă e deja ocupată:
`lib/reordonare.js` o folosește pentru apucarea rândului, la 300 ms (`APASARE_LUNGA`). Două
gesturi pe aceeași apăsare înseamnă că niciunul nu e sigur.

> **Corecție, câteva ore mai târziu.** Obiecția era bună, concluzia („se respinge") nu.
> O altă sesiune a livrat gestul între timp (`lib/apasareLunga.js`), rezolvând exact conflictul
> pe care îl semnalam: cele două nu sunt același gest, deci nu împart pragul. `APASARE_LUNGA`
> (300 ms) rămâne pentru **apucare** — degetul rămâne jos și continuă să lucreze, deci pragul
> trebuie să fie scurt. `APASARE_MENIU` (420 ms) e pentru **deschidere** — degetul trebuie să
> se ridice, și are nevoie de timp ca să afle că a reușit; la 300 ms foaia sosea sub deget
> înainte să-l ridici și WebView-ul pornea selecția de text.
> Am tras concluzia greșită fiindcă am citit conflictul ca pe o coliziune de resursă („o
> singură apăsare lungă"), când era o distincție de intenție. Handoff-ul avea dreptate, și
> chiar cu cifra lui.

**Cele trei curbe suplimentare** („pocnet" `.34,1.5,.42,1`, „ieșire rapidă pe gest"
`.36,0,.86,.28`, plus cea de ieșire). Sistemul are un set închis de curbe, fiecare cu motivul
lângă ea. S-a luat UNA, cea care acoperea un sens întreg care lipsea. Celelalte două nu
descriau un sens, ci un accent — și pentru asta există deja `--ease-arc` / `--ease-spring`.

## Amânat, nu respins

- ~~**P3 — o singură foaie de adăugare**~~ — **livrat** între timp de altă sesiune
  (`components/FoaieAdauga.svelte`, `lib/parserTask.js` + teste). Cele trei drumuri de
  adăugare au devenit unul singur. Era, cum scriam, cea mai valoroasă propunere din handoff.
- **P5 — Planificator ca lună + densitate.** Redesign de pagină.
- **P6 — splash varianta B.** Contained, dar atinge `index.html` + `lib/splash.js` + regulile
  de sosire din `global.css`, adică fix zona unde `audit_navigare` are cele mai multe
  contracte.
- **Pull-to-refresh.** Util pe teren; e o funcție nouă peste paginile de listă.
- **Vocabular de vibrații** (un puls pentru „s-a făcut", altul pentru „nu se poate"). Mic,
  dar de decis împreună, ca să nu ajungă trei feluri de vibrat inventate separat.

## Lecția

Un audit de design făcut pe un prototip descrie **prototipul**. Aici 10 din cele 17 „rupturi"
erau deja reparate în cod, unele de ani de commituri, una chiar de dimineață. Verificarea
fiecărei afirmații înainte de a scrie o linie a costat mai puțin decât ar fi costat o singură
„reparație" care strica ceva ce mergea.

Și invers: singura observație care ERA reală — o singură curbă pentru amândouă sensurile —
n-ar fi fost găsită uitându-te la cod, fiindcă acolo totul e coerent. Se vedea doar
întrebând „de ce iese la fel cum intră".


## Post-scriptum: două sesiuni pe același master

Commitul ăsta a plecat după un rebase peste șase commituri venite din altă sesiune, care
lucra în paralel pe același handoff. Merită notat ce s-a întâmplat la întâlnire, fiindcă e
argumentul pentru regula din `CLAUDE.md` („pull FIRST"):

- **Nu s-a pierdut nimic și nu s-a suprapus nimic.** Ei au luat funcțiile (P3, apăsarea lungă,
  ceasul, Planificatorul), eu am luat sistemul de mișcare (curba de ieșire, trecerea de temă).
  Conflictele au fost exclusiv în fișiere generate — `static/dist`, `service-worker.js`.
- **Munca lor s-a așezat peste a mea fără să știe:** `urmaritor()` din `gesturi.js`, scris
  dimineață pentru viteza foii, e folosit acum și de gesturile lor.
- **O reparație de-a mea a fost înlocuită cu una mai bună.** Diagnosticasem „foaia de adăugare
  pare că reîncarcă pagina" ca două sosiri suprapuse (foaia urcă, apoi tastatura o smulge) și
  o rezolvasem scoțând focusul automat pe telefon. Ei au rezolvat cauza, nu simptomul:
  tastatura urcă ACUM ODATĂ cu foaia, deci sunt tot două mișcări dar o singură sosire — și
  câmpul își păstrează focusul. Contractul din `audit_foaie.py` a fost rescris în consecință
  („câmpul are focusul, deci tastatura urcă odată cu foaia"), și e mai bun decât al meu.
  Diagnosticul a ținut; leacul a fost depășit.
