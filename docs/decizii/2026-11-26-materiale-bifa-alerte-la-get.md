# O alertă de livrare nu mai pomenește un material bifat: se aliniază la `GET /api/materiale` (2026-11-26)

> Ion, în Torqa, la Materials: „dacă bifez un material cu avertizare să dispară avertizarea”. Pe rând și în foaie
> avertizarea (întârziat, după start, aproape de start) dispărea deja la bifă; rămânea alerta din cardul de sus, cu
> numele materialului bifat, până la următoarea colectare (08:00 sau 13:00).

## Ce era

Decizia din 2026-11-25 lăsa alerta de livrare (`livrare_dupa_start`, `livrare_aproape_start`) din `alerte[]` pe
seama colectării următoare: serverul o calculează la `PUT /api/materiale`, cu bifele de atunci, iar snapshot-ul
rămâne neschimbat între colectări. Un material bifat după PUT rămânea deci în text („… vin după start: ETA 1180 …”) și
în numărul alertelor (meniul, rândul proiectului), cu marcajul de pe rând deja scos.

## Ce s-a decis

`GET /api/materiale` aliniază cele două alerte cu bifele de acum (`blueprints/materiale.realinia_alerte_start`, după
`aplica_bife`): le recalculează cu aceeași funcție ca PUT-ul (`materiale_alerte.alerte_start`), pe rândurile snapshot-ului
și pe perioada cu care a calculat colectarea alertele (`rezumat.perioada`). Un articol bifat iese din text și din `n`;
cu toate articolele bifate alerta dispare; cu bifa scoasă revine, și când PUT-ul o scrisese fără el.

- Doar când colectorul trimite `sursa.alerte = "server"` și snapshot-ul are `rezumat.perioada`. Alertele trimise de
  colector (fără flag) și celelalte tipuri (`comanda_fara_lm`, `ct_fara_lm`, `fara_linii_pontaj`) nu se ating.
- `schimbare` se păstrează de la alerta cu același `tip` și `ref`; una care revine din nimic o are `null`.
- GET-ul nu scrie nimic: snapshot-ul, bifele și taskurile rămân cum erau. Taskul unei alerte deja create (id stabil, pe
  `perioada|<id>|<start>`) nu se șterge niciodată, ca până acum; cel nou al unei alerte revenite îl face colectarea
  următoare.
- Perioada e cea din snapshot, nu cea de acum din `implementari`: o perioadă mutată între colectări o iau alertele la
  colectarea următoare, ca până acum.

Cod: `blueprints/materiale.py` (`realinia_alerte_start`, apelat din `vedere`). Teste: `teste/test_materiale_bifa.py`,
clasa `AlerteDeLivrare` (cinci teste care picau pe codul vechi, două de gardă).
