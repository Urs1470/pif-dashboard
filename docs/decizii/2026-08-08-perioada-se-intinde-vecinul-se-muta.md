# Perioada se întinde, iar vecinul se dă la o parte (Calendar, turele 7–8, 2026-08-08)

`redimensioneaza()` scria capetele și lăsa coliziunea să se întâmple, deși „perioadele nu se
suprapun" era deja regula. Înlocuit cu `intinde()`, care decide după CINE e vecinul:

- **același `loc\|client` = continuare, nu coliziune.** Nu se scrie nimic în plus: `deplasari`
  grupează deja zilele consecutive pe cheia asta, deci în clipa atingerii datele spun „o
  singură ieșire". Toastul o spune („o deplasare, 8 zile") și se poate anula. Se anunță
  **doar când chiar s-a alipit ceva nou** — doi vecini care se atingeau și înainte erau deja
  o deplasare.
- **alt loc sau alt client = vecinul e împins**, cu o zi **lucrătoare** (`nextWorkday` în
  `calendarDates.js`), păstrându-și durata. **Împingerea se propagă**: un singur pas ar putea
  așeza vecinul fix peste următorul, adică aceeași suprapunere mutată cu o căsuță. Bucla e
  mărginită (fiecare mutare împinge strict la dreapta) și toastul spune câte s-au mutat.
- **Anulează readuce TOT** — perioada trasă și fiecare vecin împins. O propagare tăcută ar fi
  fost singurul lucru inacceptabil.
- **Fantoma e CONTUR peste banda reală, nu o mută.** Banda apucată nu se mai stinge la 32%:
  la întindere cele două se suprapun aproape complet, deci vedeai un dreptunghi cu două
  opacități și nu mai știai care e starea de acum. Fără fundal și fără text — al doilea
  exemplar al aceluiași nume, decalat cu o zi, se citește ca două lucrări.
- **Mânerele sunt două bare subțiri de accent**, la hover, pe toată înălțimea benzii (era o
  pastilă albă de 2×9px în mijloc).
- **`chenar` — ieșirea ca un singur obiect.** Fără el alipirea n-avea ce să arate: două
  perioade care se ating devin o deplasare, dar pe ecran rămâneau două bare la fel ca înainte.
  Chenarul acoperă zilele consecutive la același `loc\|client` și exact benzile lucrărilor lui;
  raza stă **doar pe capetele adevărate**, deci la alipire cele două muchii rotunjite din
  mijloc dispar — asta e „peretele se stinge". Lucrările rămân bare separate înăuntru: s-au
  unit ieșirile, nu lucrările.
- **Pe telefon pista se citește, nu se manipulează.** Gestul e oprit în `seManipuleaza()`
  (`ecran.telefon || ecran.grosier` — perechea în JS a lui `@media (hover: none)`, ca desenul
  și comportamentul să nu se desincronizeze), iar mânerele sunt `display: none`. Asta
  **răstoarnă** decizia din 7 august („Perioadele se trag cu mâna" acoperă acum doar mouse-ul):
  alegi o ZI dintr-o celulă de ~48px acoperită de benzi, iar ce iese din gest nu e „aproape ce
  voiai", e altă zi scrisă în bază. `audit_mobil.py`, secțiunea „perioadele se trag", a fost
  întoarsă odată cu contractul: la deget verifică acum că **nu** există mânere și că apăsarea
  lungă + tragerea **nu** mută nimic.
