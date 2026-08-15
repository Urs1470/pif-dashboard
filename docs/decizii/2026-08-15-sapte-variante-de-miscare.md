# 2026-08-15 — Sapte variante de miscare, alese de Ion din simulari

- **2026-08-15 (4) — Sapte variante de miscare, alese de Ion din simulari.**
  Diagnosticul: sistemul nu era gresit, era **uniform amortizat** — o singura
  curba pentru si ce se misca in spatiu, si ce doar se stinge. Separarea e cea
  din Material 3: `spatial` (are voie sa depaseasca) vs `effects` (niciodata).
  - **Doua tokenuri noi de arc**, ca `linear()` — `--ease-arc` (bounce .18,
    depaseste ~1%) si `--ease-arc-elan` (.28, un singur consumator: tenta din
    dock). `linear()`, nu `cubic-bezier`: un arc oscileaza, o bezier are un
    singur maxim. Perechea lor JS (`ARC`, `ARC_ELAN` in `motion.svelte.js`) e
    FORMULA, nu esantioanele — si e verificata fata de `linear()` din token
    (abatere < 0,00005). Fara verificarea asta ar fi fost exact greseala pe care
    fisierul o are deja scrisa la `--ease-spring`: doua arcuri usor diferite dupa
    cine deseneaza miscarea.
  - `sosire`, `.cell-in`, `.ruta-in`, `.asteptare`, `aterizare` si pagina noua
    din View Transition trec pe arc. **`plecare` NU**: un obiect care iese n-are
    voie sa depaseasca — ar parea ca se razgandeste. Acelasi motiv la iesirea
    toastului si la revenirea paginii de sub foaie.
  - **Opacitatea ramane pe `--ease` chiar si acolo unde pozitia e pe arc.**
    `sosire` calculeaza cele doua separat, dintr-un progres liniar: o depasire pe
    opacitate se citeste ca palpait.
  - **Drum lat:** ±10px -> ±30px la schimbarea de pagina. La zece pixeli directia
    e sub pragul la care se citeste ca directie, deci plateai miscarea fara sa
    primesti informatia ei.
  - **Bifa se deseneaza** in inel: doua borduri pe o cutie rotita 45°, dezvelite
    din `clip-path` (care se aplica INAINTE de `transform`, deci taie de-a lungul
    semnului). Inelul nu se mai umple cu verde plin — ar acoperi exact locul in
    care trebuie sa incapa semnul. Sub `reduced-motion` semnul RAMANE, doar
    trasarea dispare: el e informatie, nu decor. Merge pe mecanismul `.bifare`
    care exista deja, deci sare peste gestul de glisare, unde pista verde e deja
    raspunsul.
  - **Modalul creste din declansator.** Originea vine din ultima APASARE
    (`pointerdown` global, fereastra 600ms, distanta plafonata), nu dintr-o
    proprietate pe fiecare apelant — sunt peste douazeci de locuri care deschid
    modale. Fara apasare recenta (tastatura, paleta, gest, notificare) creste din
    centru: o origine gresita e mai rea decat niciuna.
  - **Pagina se retrage sub foaie**, pe telefon (`html.are-modal .app-main`,
    scale .93). Ca sa fie posibil, **foaia a iesit in `body`** — `lib/portal.js`,
    modul nou, extras din copia locala din `DatePicker`. Fara asta foaia s-ar fi
    micsorat odata cu pagina pe care o acopera: un element transformat devine
    bloc de referinta pentru orice `position: fixed` dinauntru (aceeasi capcana
    ca la `.ruta-in`).
  - **Capcana de proces, nu de cod:** am dat `git stash` ca sa verific daca un
    avertisment de CSS neutilizat e preexistent, iar `stash pop` a esuat fiindca
    build-ul regenerase `static/dist`. Munca a stat in stash pana am aruncat
    dist-ul si am refacut pop. Avertismentul ERA preexistent. Nu se face `stash`
    cu build-ul murdar — sau se face dupa `git checkout -- static/dist`.
