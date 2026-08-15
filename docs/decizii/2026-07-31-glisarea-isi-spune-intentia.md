# 2026-07-31 — Glisarea spre dreapta isi spune intentia din primul milimetru

- **2026-07-31 — Glisarea spre dreapta isi spune intentia din primul milimetru.**
  Ion: „glisarea la dreapta pentru indeplinirea taskurilor pe mobil trebuie facuta mai
  frumoasa, o animatie si poate o bifa ce apare — acum doar se coloreaza si nu e
  intuitiv ce face."
  **Problema nu era culoarea, era MOMENTUL.** Singurul semnal (`.gl-bifa`, un fundal
  verde) aparea abia dupa **42%** din latimea randului; pana acolo trageai un rand
  peste nimic. Iar cand aparea, era o culoare — verdele spune „bine", nu spune „FACUT".
  In spatele randului, pe stanga, sta acum `.gl-pista`: bifa + eticheta „Făcut".
  `lib/glisare.js` publica **`--gl-p` (0..1)** = cat din drumul pana la prag s-a facut,
  iar CSS-ul creste fondul, opacitatea si scara bifei continuu — JS-ul nu scrie stiluri
  pe fiecare cadru, scrie o variabila. La prag: pista plina, bifa se umple si pocneste
  (`glPoc`), eticheta intra, plus `navigator.vibrate(12)` (Safari iOS n-o implementeaza,
  deci e optionala, nu o conditie).
  **CSS-ul sta in `global.css`, nu in cele patru componente** — nu doar ca era deja
  copiat de patru ori, dar Svelte TAIE selectorii pusi la rulare din JS (nu doar
  avertizeaza), capcana care odata a lasat o singura regula de gest vie in toata
  aplicatia. In foaia nescopata nu exista scaparea asta.
  **Prins pe parcurs:** panoul de actiuni al gestului OPUS (ancorat la dreapta) iesea
  de sub rand in timpul glisarii spre dreapta — se citea „Azi" in mijlocul confirmarii
  verzi, adica doua raspunsuri la „ce se intampla daca dau drumul". Clasa `gl-dreapta`
  il ascunde cat timp tragi in directia de bifare. Tot atunci: `.gl-pista` are `inset: 0`,
  nu latime dupa continut — altfel verdele se termina dupa eticheta si urma o bucata de
  fundal inchis, deci confirmarea parea o pastila lipita, nu suprafata de sub rand.
  Al treilea: `offsetWidth` se citea la FIECARE `pointermove` (masuratoare de layout in
  mijlocul gestului); acum se citeste o data, la apasare.
  **Regresie acoperita:** sectiunea de gesturi din `audit_mobil.py` esantiona doar
  capatul cursei. Acum esantioneaza tot parcursul si pica daca bifa nu se vede la
  MIJLOC — exact plangerea lui Ion. Verificat prin injectarea regresiei (`opacity: 0`):
  „PICA glisare dreapta: bifa nu se vede pe parcurs (opacitate 0.00 la mijloc)".
  `--gl-p` e declarat in `audit_design.py` la `DIN_JS` — nu e token de design, e stare
  de gest, si de aceea se foloseste mereu cu rezerva `var(--gl-p, 0)`.
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` complet OK,
  `test_suite` 12/12, plus masuratoare pe gest real (p 0,24 -> 0,60 -> 1,00; scara bifei
  0,66 -> 0,82 -> 1,00; pista `rgb(126,226,168)` la prag; randul chiar se bifeaza).
