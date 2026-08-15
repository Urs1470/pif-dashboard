# 2026-08-15 — Taburile din pagina de proiect

- **2026-08-15 (6) — Taburile din pagina de proiect.** Ion: „cum se deschid
  taburile de proiecte, acum e cu ramasite si schelet, nu se deschide fluent."
  - **A CINCEA OARA aceeasi familie de eroare de masurare.** Prima sonda asculta
    `animationstart` si a raportat „nicio animatie" — fals: Svelte 5 ruleaza
    tranzitiile prin **Web Animations**, care nu emit evenimentul ala. Se numara
    cu `document.getAnimations()`, la mijlocul miscarii. Continutul CHIAR se
    estompa; i-am spus lui Ion ca nu, si a trebuit sa ma corectez.
  - Ce era adevarat, masurat cu 150ms dus-intors: prima vizita pe „Perioade" si
    pe „Wiki" trecea printr-un cadru de schelet si **trei** stari vizuale.
    A doua era curata — deci nu lipsea cache-ul, lipsea momentul umplerii lui.
  - **Incalzirea la hover NU ajunge.** Intre `pointerenter` si click trec ~150ms
    pe desktop si ~100 pe telefon, adica exact cat un dus-intors prin tunel.
    Datele taburilor se incalzesc acum la deschiderea PAGINII, pe rand liber
    (`requestIdleCallback`), ca sa nu concureze cu cele doua cereri proprii ale
    paginii. Hoverul ramane ca a doua sansa.
  - **`in:fade` -> `in:alunecare` cu sens din ordinea taburilor.** Era singurul
    loc ramas fara directie, dupa ce ruta, luna din Calendar si sfera din
    Taskuri au primit-o pe toate.
  - **Sublinierea taburilor aluneca**, ca pastila din doc si cursorul de sfera —
    al treilea indicator de acelasi fel. Latimile difera, deci se scaleaza pe X
    (`scaleX`, compozabil) in loc sa se anime `width` (layout). `.tabs` a primit
    `position: relative`: are `overflow-x: auto` dar nu era pozitionat, deci un
    copil absolut s-ar fi raportat la pagina.
  - `urlPerioade` s-a mutat in `<script module>` din `ImplPeriods` si e
    exportat: incalzirea si montarea trebuie sa ceara ACELASI URL, altfel
    memoria se umple pe alta cheie si scheletul revine fara nicio eroare.
  - Regresia: `audit_navigare.py` sectiunea 11. Proba sare peste tabul DEJA
    activ — un click pe el nu schimba nimic, deci n-are ce anima, iar
    contractul ar fi picat pe un comportament corect.
