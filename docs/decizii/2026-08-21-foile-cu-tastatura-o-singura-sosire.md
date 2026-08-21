# 2026-08-21 — Foile cu tastatura: o singură sosire, nimic sub ea, nimic sub deget

Ion: „nu reușesc pe mobil să aliniez designul, tranzițiile, animațiile, închideri,
deschideri, atingeri, gesturi… când se deschide tastatura să fie frumos, dar nu rupt
ca acum. Vreau un audit complet, ultim, să nu mă mai chinui pe testing și reparații
punctuale." Și: „taskurile din proiecte trebuie să fie tot cu modale precum le avem
peste tot acum."

## Ce era de fapt „rupt"

Niciun audit nu simula tastatura, deci pe mașina de dezvoltare totul trecea verde.
Emulând IME-ul (un `visualViewport` fals care „urcă" la 250 ms după focus, exact
calea pe care o ascultă `Modal.svelte`) și măsurând cadru cu cadru:

1. **Două sosiri** la orice foaie cu câmp (Adaugă task, Proiect nou, subtask): foaia
   urca 280 ms (844 → 296), se așeza, apoi sosea `--kb` și o mai împingea o dată 224 px
   în 220 ms, în timp ce i se scurta înălțimea de jos.
2. **Editorul de notițe** cu tastatura: `.backdrop:has(.modal-doc) { padding: 0 }` bătea
   regula generală cu `--kb`, deci documentul (înalt `100dvh - kb`, ancorat jos) stătea cu
   312 px sub tastatură. Zona de scris rămânea de 55 px. Fără tastatură, bara de unelte
   fixată la `bottom: 0` **acoperea butonul „Salvează"**.
3. **Apăsarea lungă**: foaia de acțiuni sosește sub deget (420 ms), iar ridicarea produce
   un `click` care aterizează pe ce e acum sub deget — un rând al foii („Șterge" stă ultimul,
   exact unde se odihnește degetul pe un rând de jos) sau pe voal (închide). Pe Android
   clicul lipsește doar dacă ții până la pragul nativ de 500 ms; între puls și 500 e un clic.
4. **Foaia taskului** aștepta rețeaua înainte să se ridice — prin tunel, 300–800 ms fără
   niciun răspuns la atingere.
5. **Pagina proiectului** desfăcea rândul inline — singurul loc rămas pe modelul vechi.
6. **Foaia zilei** (`inalt`) își anima înălțimea 464 → 844 în timpul sosirii (clasa `intins`
   venea un tact după ce tranziția Svelte citise stilurile).
7. `.fa` (corpul foii de adăugare) avea înălțime fixă în `dvh` → sub tastatură ieșea din corp:
   dublu scroll, „Categorie și recurență" sub pliu.

## Ce s-a decis

- **Tastatura se prevede, nu doar se măsoară.** Înălțimea ei e aceeași pe același aparat,
  deci se ține minte (`localStorage['pif-kb']`) și se pune pe `<html>` ÎNAINTE ca foaia să
  se randeze (`Modal` prop `cuTastatura`; `prevedeTastatura()` în `<script module>`). Foaia
  se naște cu podeaua ridicată și urcă o singură dată, la înălțime constantă, în același timp
  cu tastatura care urcă nativ dedesubt. Măsurătoarea reală o bate (de obicei e identică);
  dacă tastatura nu vine (tastatură fizică, focus pierdut), prevederea expiră în 1,2 s.
  Prima deschidere pe un aparat rămâne cu două sosiri — de acolo se învață.
- **O singură sursă pentru tastatură.** `EditorLung` și `RichTextEditor` măsurau fiecare
  `visualViewport` și își fixau barele la `bottom: kb`. Au plecat: `Modal` ridică întreaga
  foaie „doc", bara de unelte stă **sub text, în flux**, iar „Salvează" sub ea. `<html>` poartă
  `are-tastatura` când e sus: insetul de jos dispare (e sub tastatură), toastul urcă peste ea.
- **Un clic e al foii doar dacă a început pe ea.** `Modal` înghite clicurile fără `pointerdown`
  în voal de la deschidere (Enter de la tastatură are `detail === 0` și trece).
- **Foaia taskului răspunde imediat**: un tact de 120 ms pentru cache/rețea locală, apoi se
  ridică oricum, cu schelet de exact atâtea rânduri cât spune `subtask_total` — aceeași
  înălțime ca rândurile reale, deci sosirea lor nu mișcă foaia.
- **Taskul din proiect se deschide în foaie (telefon) / panou (desktop)**, cu același cap ca
  în /tasks (bifa mare, titlu, rândul de termen cu `SelectorZi`). Corpul e același snippet
  (`detaliuTask`), nu se mai desface nimic în listă.
- **Starea de pornire a foii se pune în `$effect.pre`**, înainte de primul cadru: `intins`,
  `apasatInauntru`, prevederea tastaturii.
- **Tooltipul e interzis pe `(hover: none)`** — regula exista scrisă, acum e impusă.

## Cum se verifică

`scripts/audit_tastatura.py` — intră în poartă pe sursele SPA. Contractele: o singură
sosire (padding din primul cadru, înălțime constantă, 0 px mișcare după 330 ms), nimic
sub tastatură (câmp, subsol, corp fără dublu scroll), editorul întreg deasupra ei (zona de
scris ≥ 150 px), ridicarea degetului după apăsarea lungă nu apasă nimic, foaia taskului
în ≤ 260 ms, foaia zilei la înălțime constantă, prevederea expiră, pagina proiectului
deschide foaie / panou.

Ce NU acoperă: aparatul real. Emularea trece prin același cod ca telefonul, dar dacă pe
WebView-ul Capacitor `visualViewport` nu raportează tastatura (edge-to-edge fără tratarea
insetului IME), toată mașinăria primește 0 — atunci reparația e nativă (inset listener pe
WebView), nu în CSS.

## Runda a doua (aceeași zi), după proba pe telefon

Ion, cu prevederea în funcțiune: „modalul se ridică prea sus, apoi după câteva clipe
apare tastatura android." Corect — foaia ajungea la locul final în 280 ms și stătea în
aer până sosea IME-ul. **Și latența se învață** (`pif-kb-lat`, de la prevedere la primul
`resize` cu tastatura, netezită), iar urcarea e coregrafiată în doi timpi într-un singur
`css()`: 280 ms până pe marginea ecranului (locul ei fără tastatură), așezare acolo, apoi
cei `kb` px în ultimele 200 ms — exact cât urcă tastatura însăși. Nicio pauză în aer.

Tot atunci:
- **Prima apăsare lungă apărea instant** — `{#if task}<Modal>` creează componenta odată cu
  `open`, iar Svelte nu joacă tranzițiile locale la prima randare. `|global` pe toate patru
  tranzițiile din `Modal`: sosirea e a foii, oricine ar fi creat-o.
- **Foaia zilei se deschide pe treapta de mijloc** (`inalt` = două trepte), nu pe tot ecranul;
  sus e la un gest. Răstoarnă decizia din 2026-08-10, la cererea lui Ion.
- **Aterizarea din Acasă/Planificator**: pe atingere nu mai există morph (îngheța ecranul
  744 ms așteptând rândul-țintă); rândul e adus între antet și dock (nu doar „în fereastră"),
  iar hașura e reală — 22 % accent + inel 2 px, pe fața rândului (`.gl-fata` e opacă),
  2 s, pornită după ce derularea s-a așezat.
- **Din foaia zilei către proiect**: foaia coboară întâi (220 ms, ruta se încălzește între
  timp), pagina pleacă după ea — nu mai e dizolvată în instantaneul View Transition.
