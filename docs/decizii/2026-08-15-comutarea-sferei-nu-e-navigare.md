# 2026-08-15 — Comutarea sferei nu e o schimbare de pagina

- **2026-08-15 (5) — Comutarea sferei nu e o schimbare de pagina.** Ion: „la
  comutatia dintre taskuri personale si lucru parca se reincarca pagina si se
  vede asta", plus „pe Android vreau prin swipe sa pot face comutatia".
  - **Se vedea fiindca ASA ERA.** Sfera traieste in interogare
    (`#/tasks?sfera=personal`), comutatorul cheama `navigate`, iar `navigate`
    pornea o View Transition pe RADACINA — tot ecranul, antet inclusiv, pentru o
    filtrare care nu cere nicio cerere. De la „drumul lat" (±30px, tot 15 august)
    a devenit imposibil de ignorat.
    **Regula noua in `navigate`:** cand CALEA nu se schimba, tranzitia de
    radacina nu se joaca. Ce s-a schimbat e o stare din pagina, iar pagina isi
    are deja miscarea ei (`{#key listaCheie}` cu `alunecare` directionala).
  - **Garda pe `loading` la comutarea sferei a plecat.** Fusese scrisa cand sfera
    CEREA date; de cand lista vine „toate" dintr-un foc, comutarea e o filtrare
    in memorie, iar garda doar intarzia raspunsul cat tinea o improspatare in
    fundal. Arhiva chiar cere o cerere, deci ea asteapta mai departe.
  - **Glisarea comuta sfera, dar pe BARA DE UNELTE, nu pe lista.** Pe lista,
    orizontala e deja luata: fiecare rand are gestul lui (dreapta = bifat,
    stanga = planifica). Doua intelesuri pe aceeasi directie si aceeasi
    suprafata inseamna ca uneori obtii altceva decat ai vrut — iar regula
    aplicatiei de la gesturile de rand incoace e ca o ratare n-are voie sa
    produca ALTCEVA. Verticala castiga la egalitate (`touch-action: pan-y`).
  - Cursorul de sfera a trecut de pe `--ease-spring` pe `--ease-arc-elan`:
    acelasi fel de obiect ca pastila din dock.
  - Regresia: `audit_navigare.py` sectiunea 9.
  - **A patra oara aceeasi capcana de masurare:** proba parea sa arate liste
    goale, dar seed-ul intra DUPA ce aplicatia se incarcase, iar `goto` pe alt
    hash nu creeaza document nou. Dupa `reload()`: 4 randuri, tot verde.
