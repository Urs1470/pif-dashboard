# 2026-07-30 — Marginea din stanga a randului de task, si invariantul „azi"

- **2026-07-30 (8) — Marginea din stanga a randului de task, si invariantul „azi".**
  Ion: „parca ai lasat cam mult spatiu in stanga la taskuri". Avea dreptate, masurat:
  pe 375px titlul incepea la **x=96**, un sfert din latimea ecranului, pe fiecare rand.
  Trei cauze suprapuse: `.page` are 16px, cartonasul `.list-cell` inca 16 (se adunau),
  iar bifa era o caseta de 44px in care statea un cerc de 18 — 13px de aer de fiecare
  parte, plus 8 de spatiu dupa.
  **Bifa: 44px de ATINS, 30px de LATIME.** Caseta se ingusteaza, suprafata de atingere
  revine dintr-un `::after` cu `inset: -7px`, care se intinde in padding-ul randului si
  in spatiul dintre bifa si titlu — dar se opreste la 1px de `.tmain`, ca sa nu fure
  atingerile care trebuie sa DESCHIDA taskul. Aceeasi reteta in toate cele trei liste.
  **Cartonasul listei isi pierde rama si padding-ul lateral pe telefon.** Odata scos
  padding-ul, randurile ajungeau lipite de propria lui rama — o cutie desenata la 1px
  de continut se citeste ca o greseala. Iar gruparea face acum ce facea el: spune unde
  incepe si unde se termina o bucata de lista. Titlul: **96px → 66px**, randul 305 → 337.
  **Invariantul „azi", acum aparat de audit:** boardul „Astăzi" de pe Acasa si grupa
  „Azi" din `/tasks` sunt ACEEASI multime — `_AGENDA_WHERE` e `status != 'done' AND
  date(data_scadenta) <= today`, deci apartenenta e data de TERMEN, nu de vreun steag
  separat (v33). Verificat in ambele sensuri: pui pe „Azi" din /tasks si apare pe Acasa;
  muti pe „Mâine" si pleaca. Doua liste de azi care se contrazic ar fi mai rele decat
  una singura, fiindca n-ai sti care minte.
