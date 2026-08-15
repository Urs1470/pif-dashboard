# 2026-08-14 — Schimbarea de tab: trei animatii au devenit una

- **2026-08-14 (3) — Schimbarea de tab: trei animatii au devenit una, si datele
  nu mai mor cu componenta.** Ion: „nu sunt omogene, nu sunt peste tot, cel mai
  mult ma deranjeaza la schimbul dintre taburi cand se incarca pagina."
  Masurat, nu presupus: la fiecare apasare de tab se jucau `::view-transition-*(root)`
  (240ms, ±10px pe X), `.ruta-in` (220ms, 10px pe Y) si `.cell-in` (220ms +
  decalaj pana la 240) — **peste aceiasi pixeli, pe doua axe, cu opacitatile
  INMULTITE** (o celula ajungea pe la 0,13 la mijlocul drumului). Ce s-a facut:
  - `.ruta-in`/`.cell-in` sunt gardate pe `html.prima-incarcare`, clasa scrisa in
    `index.html`/`calc.html` si stearsa de `router.svelte.js` la prima navigare.
    **Se STINGE, nu se aprinde:** `animation-name` care revine de la `none` la un
    nume REPORNESTE animatia, deci o clasa pusa doar in timpul tranzitiei ar fi
    jucat exact miscarea suprimata, la scoatere. Pusa in HTML si nu in router
    fiindca `/calc` randeaza `Calculator.svelte` FARA router.
  - `lib/cache.js` — `dinCache()` sincron + `preia()` cu dedup pe cereri in zbor
    si fereastra de prospetime. **Seedul e doar la MONTARE** (`primaCitire`):
    dupa o scriere, `load()` s-ar redeschide cu starea de dinainte. Invalidarea
    sta in mutatiile store-ului (`updateProject`/`deleteProject` -> `uita`), nu
    la apelanti — pagina de proiect isi salveaza campurile lungi fara reload.
  - Fiecare pagina cu date isi exporta `pregateste()` din `<script module>`
    (Calendar, ProjectDetail, Departament). O harta ruta->URL tinuta in App s-ar
    fi despartit tacut de pagini. `setPreincarcaRuta` pastreaza acum MODULUL
    intreg, nu doar `default`. Plafon 250ms (era 180 — acum incape si un fetch).
  - Preincarcarea la `pointerenter`/`pointerdown` sta in actiunea `link`, deci o
    primeste orice navigare. Cardul de proiect NU e `use:link` (cheama `navigate`
    de mana) — are `preincarca()` scris pe el.
  - `view-transition-name: cadru-antet` / `cadru-doc`: antetul si docul ies din
    instantaneul `root`, deci nu mai clipesc si nu mai iau alunecarea. **NU se
    pune un al doilea nume pe `.dock-item.active`:** „Mai mult" poate fi activ
    simultan cu un tab de ruta, iar doua elemente cu acelasi nume fac browserul
    sa RENUNTE la toata tranzitia.
  - **Tenta slotului activ ALUNECA** (`.dock-pilula`), cerut de Ion dupa prima
    livrare. NU prin `view-transition-name` pe slotul activ, din doua motive
    independente: „Mai mult" poate fi activ simultan cu un tab de ruta, iar doua
    nume identice fac browserul sa RENUNTE la toata tranzitia; si ar fi mers doar
    cand tranzitia o detine browserul — sub `reduced-motion` VT sunt oprite, deci
    exact acolo tenta ar fi sarit. Slotul purtator e MARCAT (`data-pilula`), nu
    cautat dupa `.active`: cu doua sloturi active `querySelector` l-ar lua tacut
    pe primul. Consecinta obligatorie: `::view-transition-old/new(cadru-doc)` nu
    mai fac cross-fade (ca antetul) — `-new` e o reprezentare VIE, deci
    alunecarea se joaca inauntru, si amestecata cu instantaneul vechi s-ar vedea
    prin ea tenta veche in vechiul loc.
  - **Derularea nu se reseta la navigare.** `main.scrollTop = 0` din `hashchange`
    era no-op de la bun inceput (`.app-content` nu e scroller — fereastra e).
    Acum `window.scrollTo` in `inregistreaza`, doar la schimbarea CAII.
  - `aterizare()` avea bezierul scris de mana — a treia copie a acelorasi patru
    numere. Acum `easeCss()` il citeste din `--ease`, lazy (foaia de stil e un
    `<link>` in productie, deci nu e rezolvabil la evaluarea modulului).
  - Cardul de proiect a primit `in:sosire|local` — `.cell-in` nu mai poate anima
    un card NOU, iar decalajul lui venea oricum din indexul in lista.
  - Regresia e prinsa de **`scripts/audit_navigare.py`** (16 probe). Doua capcane
    de scris teste: pe desktop docul e ascuns pana muti cursorul in banda de jos
    (`hover` expira altfel), iar „hoverul cere date" trebuie testat pe o ruta
    NEVIZITATA — pe una proaspata zero cereri e raspunsul corect.
  - Corectie la o afirmatie din raportul initial: **Planificatorul NU clipea** —
    `plan` e store la nivel de modul, gardat pe `lanes.length === 0`. Paginile
    care chiar clipeau: Calendar, pagina de proiect, Departament.
