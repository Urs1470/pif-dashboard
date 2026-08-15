# 2026-08-07 — O exceptie care nu se potriveste e mai rea decat una lipsa

- **2026-08-07 (8) — O exceptie care nu se potriveste e mai rea decat una lipsa.**
  `ACCEPTATE` din `audit_mobil.py` se potriveste pe SUBSIR cu selectorul raportat
  (`acceptat()`), iar cheia scrisa era `button.banda` — in aceeasi tura in care
  banda trecuse de pe `<button>` pe `<div>` cu pointer events (v. 5c0789aa). Deci
  exceptia n-a prins niciodata: pagina Calendar trecea doar cand masuratoarea se
  facea INAINTE ca benzile sa se randeze, si pica altfel. Un audit care da alt
  raspuns la fiecare rulare nu spune nimic — si tocmai asta a ascuns constatarea.
  Reparat: cheia e `div.banda`, iar geometria asteapta `networkidle` inainte de
  masura (nu inca un `sleep` ghicit).
  **Ce a scos la iveala:** `button.maner.st` / `.dr` (redimensionarea perioadei) au
  9×12 pe telefon, pe benzile de mai multe zile. Am crezut intai ca nu se califica
  pentru exceptie — regula de 44px exista ca sa nu obtii ALTCEVA cand ratezi, iar
  aici ratarea cade pe banda, deci MUTI in loc sa redimensionezi. Argumentul care
  raspunde (scris in `ACCEPTATE`): manerele erau `<span>`-uri cu `onpointerdown`,
  deci masura de 9×12 nu s-a inrautatit, doar a devenit VIZIBILA cand au ajuns
  butoane reale; nu pot fi de 44px fiindca pasul grilei de benzi e 15px, deci ar
  acoperi trei randuri si ar fura atingeri de la alte lucrari; iar „altceva"-ul pe
  care il obtii cand ratezi e REVERSIBIL — mutarea se vede cat tii degetul si se
  anuleaza ridicandu-l inainte de drop. Exceptata pe motivul asta.
