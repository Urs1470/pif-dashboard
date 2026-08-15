# 2026-08-14 — Ce se anima pe telefon, inventariat din `document.getAnimations()`

- **2026-08-14 (6) — Ce se anima pe telefon, inventariat din
  `document.getAnimations()`.** Nu numarand cadre (in headless e zgomotos), ci
  citind CE PROPRIETATI se anima la fiecare gest. Trei lucruri:
  - **`transition: background` e o capcana, in 21 de locuri.** Prescurtarea
    animeaza si `background-image`, si `background-position`, si
    `background-size`. Masurat: celulele Calendarului (42 deodata, cu liniile de
    grila desenate dintr-un `linear-gradient`) animau `background-position-x` si
    `-y` la fiecare hover si la fiecare schimbare de tab. Sistemul avea deja
    raspunsul scris — `--transition-colors` enumera `background-color` — dar 21
    de declaratii il ocoleau. **Regula R10 din `audit_design.py`** il prinde
    acum, si pentru `border`/`font`/`flex`/`mask`.
  - **`::view-transition-group(cadru-antet|cadru-doc)` primeau implicitul
    browserului**, care interpoleaza `width`, `height`, `transform` SI
    `backdrop-filter` intre geometria veche si cea noua. Aici geometria nu se
    schimba, deci erau trei interpolari de la o valoare la ea insasi, cu layout
    pe fiecare cadru. `animation: none` le scoate; grupul ia direct starea noua.
  - Net: o schimbare de tab pe telefon a scazut de la **13 animatii la 8**, si
    cele doua care interpolau asezare au disparut.
  - Ramas cu buna stiinta: haloul de `box-shadow` al bifei (`.check-empty`) se
    aprinde si la atingere, fiindca touchul produce un hover sintetic. E paint
    pe un element de 18px; scoaterea lui ar costa afordanta de hover pe desktop.
