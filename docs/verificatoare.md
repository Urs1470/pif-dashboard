# Verificatoarele — ce pazeste fiecare si capcanele lor de masurare

> Mutat din `CLAUDE.md` la restructurarea din 2026-09-15 — CLAUDE.md tine punctul de intrare
> si poarta; aici sta povestea fiecarui verificator. Se citeste cand lucrezi LA un verificator
> sau cand unul raporteaza ceva ciudat. Refacut dupa auditul testelor din 2026-09-28
> (`docs/decizii/2026-09-28-verificatoarele-un-banc-si-trei-trepte.md`).

## Harta

Treptele sunt ale lui `scripts/verifica.py`; poarta ruleaza, din aceeasi lista, doar ce cer
fisierele atinse. Timpii sunt masurati pe masina de dezvoltare, 2026-09-28.

| verificator | ce pazeste | datele | treapta | timp |
|---|---|---|---|---|
| `lint.py` | ce e SCRIS si nu se intampla (vezi mai jos) | — | rapid | ~4 s |
| `audit_design.py` | coerenta sistemului de design (tokenuri, paritatea temelor) | — | rapid | ~2 s |
| `audit_contrast.py` | contrastul perechilor care chiar apar pe ecran, pe ambele teme | — | rapid | <1 s |
| `teste/` (`unittest`) | functiile pure si garzile de backend; schema pe o baza goala | baza noua | rapid | ~2 s |
| `frontend/src/lib/*.test.js` | parserul, gruparea, rendererul de markdown, driveCalc | — | rapid | ~1 s |
| `test_suite.py` | invariantii vazuti prin HTTP (sfera, proiect inchis, backup, push) | baza noua | rapid | ~4 s |
| `smoke_ui.py` | fiecare ruta si fiecare fel de proiect se randeaza, fara exceptii | copia locala | poarta: `--esantion` · complet: tot | ~37 s / ~2 min |
| `audit_mobil.py` | geometria pe trei telefoane, gesturile, perioadele, dockul | copia locala + ce pune el | poarta | ~85 s |
| `audit_tastatura.py` | foile CU tastatura: o sosire, nimic sub ea | baza noua | poarta | ~42 s |
| `audit_foaie.py` | foaia sub deget: trepte, viteza, voal | baza noua | complet | ~30 s |
| `audit_reactivitate.py` | raspunsul la apasare, profilul miscarii, cadrele pierdute | baza noua | complet | ~26 s |
| `audit_navigare.py` | ce se intampla cand schimbi tabul (animatii, schelet, preincarcare) | copia locala | complet | ~50 s |
| `audit_ferestre.py` | fiecare fereastra: sosire, voal, actiuni, renuntare, Escape | copia locala | complet | ~3 min |
| `proba_mobil.py` | banc de lucru, fara verdicte (vezi mai jos) | noua / goala / multa | — | — |

Toate auditurile cu browser stau pe **`scripts/banc.py`**: serverul pe un port liber, baza de
unica folosinta (sterse la iesire), contextul de telefon sau de desktop cu fusul orar al lui
Ion si service worker-ul blocat, loginul, degetul prin CDP, raportul. Pana pe 2026-09-28
fiecare le scria singur — ~600 de linii copiate in noua scripturi, cu copii care se
despartisera fara ca cineva sa fi hotarat asta.

**Coduri de iesire, aceleasi peste tot:** 0 curat, 1 abatere in aplicatie, 2 instrumentul n-a
ajuns la verdict (server mort, Playwright lipsa, auditul a crapat pe drum).

**Vocabularul:** OK · PICA (se numara) · NOTA (informatie) · SARI (nu se aplica aici, cu motiv)
· ACCEPTAT (abatere tinuta cu buna stiinta, cu motiv).

## Capcanele de masurare (fiecare a costat deja o data)

**O pauza fixa e o presupunere despre masina.** Pe o masina rapida pierde timp la fiecare
rulare, pe una lenta masoara o pagina neasezata. `banc.asteapta_linistea` asteapta pana cand
pagina a stat linistita — fara cereri in zbor, fara animatii finite, fara schelete, fara
arcuri JS — `LINISTE_UI` (120 ms) dupa o schimbare de interfata, `LINISTE_SERVER` (450 ms)
dupa o scriere pe server, fiindca aplicatia trimite unele cereri intarziat (bifarea asteapta
350 ms stampila, cautarea din foaie 200 ms). Pauzele care au RAMAS sunt stimuli sau
masuratori — cat tii degetul apasat, cat de repede derulezi, fereastra in care se inregistreaza
cadrele — si sunt marcate asa in cod. `PIF_BANC_JURNAL=1` scrie durata fiecarei asteptari si,
la plafon, ce anume nu s-a linistit.

**`document.getAnimations()` nu vede arcurile.** Foile, pastila din dock si bara de sus se
misca din `lib/arc.js`, cadru cu cadru din JS — pentru browser nu e nicio animatie. Prima
varianta a asteptarii s-a oprit in mijlocul unui arc si a raportat foaia zilei „neasezata pe
treapta de mijloc". De aceea `arc.js` numara arcurile in miscare in `window.__arcuri`, iar
bancul il citeste.

**SARI nu se numara — deci o sectiune intreaga poate muri in tacere.** Proba perioadelor din
`audit_mobil` (cea care prinsese tragerea rupta) a sarit o luna: se sprijinea pe perioadele din
copia locala a bazei, iar cand ultima (18.08) a iesit din fereastra calendarului, raportul era
verde si nu mai verifica nimic. Acum auditul isi pune singur perioada si randurile de care
depinde (`audit_mobil.seamana`), iar o grila fara benzi e PICA. Regula: o proba care isi poate
face singura datele si le face; SARI ramane doar pentru ce chiar nu exista pe un ecran, prin
desen.

**Copia locala a bazei imbatraneste.** `smoke_ui`, `audit_navigare` si `audit_ferestre` merg pe
ea (volum real de date), deci ce vad depinde de cand a fost adusa
(`scripts/sync_db_from_server.sh`). Auditurile care nu au nevoie de volum pornesc pe o baza
NOUA, umpluta de ele.

**O proba scrie doar in baza ei.** Probele de backup si push din `test_suite` scriau direct in
`PIF_DB_PATH` sau, implicit, in `pif_dashboard.db` — iar curatenia lor stergea TOATE cheile
`push_*`. Rulate pe server, ar fi oprit notificarile fara niciun semn. Acum `test_suite` isi
porneste serverul pe o baza noua si scrie doar in `APP.db`; partea care nu trece prin HTTP e in
`teste/test_push.py`, tot pe o baza noua.

## Povestile

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

**`teste/` si `*.test.js` au inlocuit verificari care nu puteau pica.** Pana pe 2026-09-28
partea „statica" din `test_suite` scana fisiere sterse din iunie si copia locala a bazei, deci
iesea verde oricum. Primele teste scrise in locul ei au gasit doua lucruri pe loc: o migrare
care pierdea un index la prima pornire (schema difera intre prima si a doua pornire a
serverului) si garda de URL din `markdown.js`, care lasa sa treaca `\u0001javascript:`.

**`audit_tastatura.py` micsoreaza CHIAR viewportul**, ca `setPadding`-ul lui Capacitor pe
aparat — nu mai falsifica `visualViewport` (varianta aia testa un aparat care nu exista, iar
trei runde de reglaje au trecut de ea fara sa schimbe ceva pe telefon). Ce masoara nu se vede
altfel: a doua sosire a foii, campul ramas sub tastatura, clicul de la ridicarea degetului dupa
apasarea lunga. Sectiunea 1b pazeste celalalt regim (browser/PWA), unde `--kb` chiar ridica foaia.

**`proba_mobil.py` nu e un verificator, e un banc**: nu are verdicte, are unelte —
raspunsul in ms separat pe apasare si actiune, geometria pe cadru, si baze de proba goale sau
cu 25 de proiecte si 133 de taskuri. Il folosesti cand nu stii inca ce cauti. **Citeste-i
antetul inainte:** trei capcane de masurare l-au facut sa mearga (`:active` nu se vede prin
atingere sintetica, `goto` la acelasi hash nu reincarca, elanul intentionat arata ca palpaire)
— vezi `docs/decizii/2026-08-21-verifica-instrumentul-inainte-de-subiect.md`.

**`audit_foaie.py` cere atingere ADEVARATA** (`Input.dispatchTouchEvent`, prin `banc.apuca`):
mouse-ul lui Playwright emite `pointerType: 'mouse'`, iar foaia iese exact pe conditia asta —
cu mouse-ul, gestul nu porneste deloc si proba ar raporta verde pe un gest inexistent.

**`audit_reactivitate.py` are trei masuratori care nu judeca inca nimic.** Pornirea foii
(deschidere, inchidere, foaia de adaugare) iese ca NOTA „momentul declansarii n-a fost prins
curat" la fiecare rulare: marcajul apasarii vine dupa primul cadru miscat, deci proba nu poate
separa latenta aplicatiei de a ei. E o limita a instrumentului, nu un verdict — si e deschisa.

**`audit_ferestre.py` e lent prin natura lui, nu prin pauze**: 44 de ferestre, fiecare pe o
pagina noua, fiecare cu intrarea rutei, sosirea si plecarea ferestrei — adica animatiile
aplicatiei, 3–4 s pe fereastra. Mai repede s-ar putea doar cu pagini in paralel.
