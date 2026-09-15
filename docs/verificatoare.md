# Verificatoarele — de ce există fiecare și capcanele lor de măsurare

> Mutat din `CLAUDE.md` la restructurarea din 2026-09-15 — CLAUDE.md ține lista și poarta;
> aici stă povestea fiecărui verificator. Se citește când lucrezi LA verificatoare sau când
> unul raportează ceva ciudat.

**`lint.py` prinde ce e SCRIS si nu ajunge sa se intample.** Nu „ce crapa" (`smoke_ui`)
si nu „ce nu incape" (`audit_mobil`): o regula CSS pe care compilatorul o TAIE din build
fiindca nu poate verifica selectorul, un `let` citit in markup care in mod runes nu
redeseneaza, un import care nu se rezolva, un `svelte-ignore` cu coduri separate prin
spatiu (tace doar primul). Toate cinci existau in cod pe 2026-08-23, si niciun alt
verificator nu le vedea. Linia de baza e CURATA, deci orice abatere e noua.

Si **o verificare care verifica VERIFICAREA**: analiza de CSS nefolosit a Svelte se
dezarmeaza singura, tacut, la anumite constructii (un `{...rest}` pe un ELEMENT o
opreste pentru tot fisierul). Pe 2026-08-24 erau **12 din 48** de componente mute —
toate paginile mari si toate primitivele din `components/ui/` — iar linterul iesea
„curat" peste reguli moarte livrate in build. `lint.py` injecteaza acum un selector
imposibil in fiecare fisier: daca nu e raportat, fisierul e mut si cade pe o
verificare textuala conservatoare. Cand vezi `css_probabil_nefolosit`, aia e.

**`audit_contrast.py` masoara ce `audit_design.py` nu poate.** Acela verifica PARITATEA
tokenurilor intre teme — ca fiecare rol sa existe in amandoua — niciodata contrastul lor.
Comentariile din `tokens.css` isi scriu singure ratiile calibrate de mana, iar rolul care a
cazut ultima oara (accentul ca text pe o suprafata, pe tema deschisa) nu era numit de nicio
regula. Proba rezolva aliasurile si cele cinci `color-mix()` ca browserul (oklab si sRGB) si
socoteste doar perechile care chiar apar pe ecran, plus separarea celor trei trepte de text —
aceea nu e lizibilitate, e conditia ca ierarhia declarata sa se si vada.

**`audit_tastatura.py` emuleaza tastatura** printr-un `visualViewport` fals care urca la 250ms
dupa focus — singurul mod de a vedea pe masina de dezvoltare ce face foaia sub IME-ul Android.
Ce masoara nu se vede altfel: a doua sosire a foii, campul ramas sub tastatura, clicul de la
ridicarea degetului dupa apasarea lunga.

**`proba_mobil.py` nu e un verificator, e un banc**: nu are verdicte, are unelte —
raspunsul in ms separat pe apasare si actiune, geometria pe cadru, si baze de proba goale sau
cu 25 de proiecte si 133 de taskuri. Il folosesti cand nu stii inca ce cauti. **Citeste-i
antetul inainte:** trei capcane de masurare l-au facut sa mearga (`:active` nu se vede prin
atingere sintetica, `goto` la acelasi hash nu reincarca, elanul intentionat arata ca palpaire)
— vezi `docs/decizii/2026-08-21-verifica-instrumentul-inainte-de-subiect.md`.

**`audit_foaie.py` cere atingere ADEVARATA** (`Input.dispatchTouchEvent`, ca `audit_mobil`):
mouse-ul lui Playwright emite `pointerType: 'mouse'`, iar foaia iese exact pe conditia asta —
cu mouse-ul, gestul nu porneste deloc si proba ar raporta verde pe un gest inexistent.
