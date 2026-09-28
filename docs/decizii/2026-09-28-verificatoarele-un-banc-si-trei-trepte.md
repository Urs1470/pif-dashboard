# Verificatoarele: un banc comun, trei trepte, teste unitare (2026-09-28)

Ion, dupa auditul testelor: „toate 5" — adica toate cele cinci recomandari:
1. poarta ruleaza ce e ieftin si precis; 2. poarta mai rapida; 3. un banc comun;
4. un singur punct de intrare; 5. teste unitare cu biblioteca standard.

## Ce a gasit auditul (masurat, nu estimat, unde scrie „masurat")

- Poarta, la o schimbare de interfata: ~5 min (masurat pe pasi: build 5,6 s, smoke_ui 127 s,
  audit_mobil 111 s, audit_tastatura 50 s, restul secunde).
- Pasul `test_suite --static` din poarta nu verifica nimic real: doua probe scanau fisiere
  sterse din iunie (`static/app.js`, `core.js`, `mobile.js`), una dubla `lint`, restul citeau
  copia locala a bazei.
- Cele mai ieftine teste nu rulau automat nicaieri: 74 de teste unitare JS (0,8 s) si probele
  de API (2,6 s cu serverul pornit).
- Probele de backup si push scriau direct in baza gasita si stergeau TOATE cheile `push_*`.
- ~600 de linii copiate in noua scripturi, cu copii divergente (fus orar, service worker,
  `PIF_CHROMIUM`, „telefon" cu sau fara atingere, pragul de tinta 40/43/44/52).
- Verificari care nu puteau pica: `audit_ferestre` rosu permanent pe o decizie de produs,
  foi care lipseau trecute ca „nota", geometrie masurata pe o pagina goala, cod mort.

## Ce s-a facut

**`scripts/banc.py`** — serverul si baza de unica folosinta (sterse la iesire), contextul de
telefon/desktop cu fusul orar si SW blocat, loginul, degetul, raportul unic si codurile de
iesire 0/1/2, asteptarea pe conditie. Toate auditurile cu browser stau acum pe el.

**`scripts/verifica.py`** — un singur punct de intrare, trepte `--rapid` / `--poarta` /
`--complet` / `--atinse`. Poarta (`gate.py`) isi ia pasii de aici (`pasi_pentru`), deci lista
nu mai sta in trei locuri care spun lucruri diferite. Poarta ruleaza acum si `npm test`,
testele Python, `audit_contrast` si probele de API (pe server propriu, nu `--static`).

**`test_suite.py`** isi porneste singur serverul pe o baza noua, cu un singur login; probele
moarte au plecat; partea care nu trece prin HTTP e in `teste/test_push.py`.

**Teste unitare**: `teste/` (Python, `unittest`: date, recurenta, ora, sfera, garzile de vault,
tokenul push, notificarile, schema pe o baza goala) si doua fisiere JS noi (markdown, grupare).
Au gasit pe loc doua defecte, reparate: migrarea v18->v19 pierdea un index pus de `init_db()`
(schema difera intre prima si a doua pornire), si garda de URL din `markdown.js` era o lista de
interdictii pe care o ocolea un caracter de control (`\u0001javascript:`) — acum e o lista de
scheme permise.

**Asteptari pe conditie** in locul pauzelor fixe de asezare (`banc.asteapta_linistea`);
pauzele ramase sunt stimuli sau masuratori. `smoke_ui --esantion` in poarta: un proiect din
fiecare tip x status x „are perioada viitoare", in loc de toate de doua ori.

**Probe care puteau pica doar in teorie, reparate**: perioadele din `audit_mobil` isi pun
singure datele (sareau de o luna, in tacere); elementele lipsa sunt PICA, nu note; geometria
pica pe o pagina neranduita; „Editează" chiar trebuie sa deschida foaia; „Calendarul s-a
randat" nu mai inseamna „exista `.page`".

## Ce NU s-a facut, si de ce

- **Un singur server si un singur Chromium pentru toata poarta.** Masurat: pornirea serverului
  1,6 s, a lui Chromium 0,2 s, loginul 0,65 s — adica ~5 s din ~3 min. In schimb un server comun
  ar fi facut auditurile dependente unul de altul (unele scriu in baza). Nu merita.
- **Auditurile nu scad cat ar fi sperat pauzele**: mare parte din timp e miscarea aplicatiei
  insasi (scara de miscare: foaie 0,7 s, pagina 0,9 s). Asteptarea pe conditie le-a facut
  CORECTE pe orice masina; viteza vine mai ales din esantionul `smoke_ui`.
- **`audit_navigare` isi pastreaza pauzele**: aproape toate sunt ferestre de masura sau asteapta
  temporizatoare ale aplicatiei (scrierea amanata pe disc, incalzirea pe timp liber).
- **Cele trei note „momentul declansarii n-a fost prins curat"** din `audit_reactivitate`:
  limita a instrumentului, deschisa.

## Decizie de produs ramasa la Ion

„Anulează" (editarea taskului) vs „Renunță" (patru ferestre de proiect/stergere) — acelasi gest,
doua cuvinte. `audit_ferestre` il raporteaza acum ca NOTA, nu ca abatere.

**Hotarat in aceeasi zi — Ion: „anuleaza ramane".** Formularul de proiect, `ConfirmDialog`
(stergerile) si editarea planului din Departament spun acum „Anulează". Cu decizia luata,
`audit_ferestre` nu mai tine o nota: orice alt cuvant pe un buton de renuntare e PICA.
