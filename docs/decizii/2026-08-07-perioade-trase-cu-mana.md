# Perioadele se trag cu mâna (2026-08-07)

## Din CLAUDE.md

Ion: *„in calendar vreau sa iau perioadele si sa le pot muta cu drag drop, acuma scrie
trage ca sa muti dar nu functioneaza. Trebuie sa pot si schimba si perioada cu tragere."*

Gestul era pe **HTML5 drag-and-drop**, si era rupt tacut. Trei motive pentru care a
plecat, nu doua:

1. **Pe touch nu se declanseaza NICIODATA `dragstart`.** Pe telefon perioadele nu se
   puteau muta deloc — iar sub 620px benzile erau in plus `pointer-events: none`, deci
   nici nu existau ca obiect.
2. **Nu poate exprima „trage capatul ca sa lungesti".** API-ul are un singur inteles:
   ridici un obiect intreg si il lasi in alta parte.
3. **Benzile stau PESTE celule**, deci trebuia jonglat cu `pointer-events` ca dropul sa
   stie pe ce zi a cazut.

Acum totul trece prin `lib/tragere.js` (pointer events): **mouse** — gestul incepe dupa
4px de miscare, ca un click sa ramana click; **deget** — dupa 300ms de apasare fara
miscare, ca o atingere scurta sa ramana atingere. Derularea se blocheaza DOAR dupa ce
gestul a inceput, printr-un `touchmove` non-passive — de aceea NU punem `touch-action:
none` pe banda si o glisare pornita din greseala pe ea deruleaza pagina normal.

Trei manere, trei intelesuri: **mijlocul** mută lucrarea, **capetele** îi schimbă
perioada, **captura zilei** mută toată deplasarea.

Patru lucruri care nu sunt evidente:

- **Ziua APUCATA e cea care ajunge sub cursor**, nu inceputul lucrarii. Prinzi o perioada
  de patru zile de a treia zi, o lasi pe joi: a treia zi cade pe joi. Varianta veche
  punea inceputul pe ziua de drop, deci o ajustare de o zi arunca lucrarea cu trei.
- **Fantoma e un al doilea set de benzi**, nu o mutare a celor reale. Motivul e mecanic:
  banda apucata e chiar elementul care primeste evenimentele. Re-randata la fiecare pixel
  (cheia ei contine ziua de inceput), Svelte i-ar distruge nodul, iar pe touch captura
  implicita a pointerului moare odata cu el — gestul s-ar rupe fix cand incepe.
- **`benzi` si `peZi` raman pe datele SALVATE** cat timp tragi. Daca s-ar recalcula, bara
  ar sari de pe un rand pe altul sub deget.
- **Pe telefon banda a ramas „decor peste celula"** — dar prin COMPORTAMENT, nu prin
  `pointer-events: none`: o atingere scurta pe banda cheama `atingeZi` cu ziua de sub
  deget, adica exact ce ar fi facut celula. De aceea e in `ACCEPTATE` din `audit_mobil`:
  regula de 44px exista ca sa nu obtii ALTCEVA cand ratezi, iar aici nu poti obtine
  altceva. Manerele de capat se ascund pe benzile de o zi (`.banda:not(.lat)`): doua
  manere de 9px intr-o celula de 44px n-ar mai lasa de unde s-o apuci.

Regresia e prinsa de `audit_mobil.py`, sectiunea **„perioadele se trag"** — cu intrare
adevarata, nu evenimente fabricate: `page.mouse` pentru mouse si
`Input.dispatchTouchEvent` prin CDP pentru deget. **`page.mouse` produce `pointerType:
'mouse'` chiar si intr-un context `has_touch`** (verificat), deci ar fi ocolit exact
ramura de apasare lunga.

## Din MEMORY.md

- **2026-08-07 (3) — Perioadele din Calendar se trag pe pointer events, nu HTML5 DnD.**
  Ion: „scrie trage ca sa muti dar nu functioneaza". HTML5 drag-and-drop nu
  declanseaza `dragstart` la deget (deci pe telefon era imposibil), nu poate
  exprima redimensionarea, si cerea jonglat cu `pointer-events` fiindca benzile
  stau peste celule. `lib/tragere.js`: mouse dupa 4px de miscare, deget dupa
  300ms de apasare; derularea se blocheaza cu `touchmove` non-passive DOAR dupa
  ce gestul a inceput, ca sa nu punem `touch-action: none` pe banda.
  Trei capcane: (1) fantoma trebuie sa fie un AL DOILEA element — re-randarea
  benzii apucate ii distruge nodul si omoara captura implicita a pointerului pe
  touch; (2) `benzi`/`peZi` raman pe datele salvate cat timp tragi, altfel bara
  sare de pe un rand pe altul sub deget; (3) **`page.mouse` din Playwright
  produce `pointerType: 'mouse'` chiar si intr-un context `has_touch`** — testul
  de deget trebuie sa foloseasca `Input.dispatchTouchEvent` prin CDP, altfel
  ocoleste exact ramura pe care crede ca o verifica.
  Regresia e prinsa de `audit_mobil.py` -> „perioadele se trag" (verificat ca
  pica pe gestul rupt, pe ambele intrari).
