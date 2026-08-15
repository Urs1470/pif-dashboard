# O perioada de mai multe zile e UN element (2026-07-30)

## Din CLAUDE.md

Ion: *„regandeste cum arata in calendar perioadele de implementare pe mai multe zile."*

Prima versiune desena o bara **in fiecare celula** a perioadei, fiecare cu numele scris din
nou si trunchiat la latimea UNEI zile. Pentru o lucrare de opt zile, „Pregatire documentatie
…" aparea de **noua** ori — si fiecare copie era ciuntita, desi lucrarea avea sase celule de
spatiu. Doua trunchieri diferite ale aceluiasi text, una langa alta, se citesc ca doua lucruri
diferite, nu ca unul care continua.

Acum benzile sunt **elemente ale grilei, peste celule**, cu `grid-column: <col> / span <n>` —
`bare` in `Calendar.svelte` taie fiecare perioada in felii de saptamana. Numele se scrie o
data per felie si foloseste toata latimea. Capetele rotunjite arata inceputul si sfarsitul
REAL; la granita de saptamana capatul rămâne drept si felia urmatoare poarta „…".

Trei capcane, toate lovite:

- **`minmax(0, 1fr)`, nu `1fr`** pentru coloane. `1fr` inseamna `minmax(auto, 1fr)`, deci o
  banda care se intinde peste coloane si are `nowrap` isi impune latimea minima si largeste
  coloanele pe care le acopera. Zilele nu mai erau egale si se desincronizau de antetul
  zilelor saptamanii.
- **Celulele trebuie asezate EXPLICIT** (`grid-row`/`grid-column` calculate din index). Altfel
  auto-plasarea sare peste pozitiile ocupate de benzi si celulele se muta din loc.
- **Benzile devin transparente la cursor cat timp tragi** (`.grid.trag .banda`). Ele stau
  PESTE celule, deci altfel un drop peste o banda de patru zile n-ar sti pe care zi a cazut.

Decalajul de sus al benzii trebuie sa fie exact zona de bare din celula
(`--h-antet: 24px` = bordura 1 + padding 5 + antet 15 + gap 3) cu pasul `--h-banda: 20px`
(bara 17 + gap 3). Numerele sunt aceleasi cu cele din `min-height` al celulei — **se schimba
impreuna**, altfel benzile plutesc pe langa celule.

Bonus prins in aceeasi trecere: clasa `azi` era pe **doua** lucruri diferite — butonul „Azi"
din bara de sus si celula zilei de azi (`.zi.azi`). Selectorul neprefixat `.azi` prindea si
celula, care primea `display: inline-flex` cu centrare si `padding: 0 10px` — de aceea
numarul zilei de azi stătea centrat in mijlocul celulei. Butonul e acum `.b-azi`.

## Din MEMORY.md

- **2026-07-30 (2) — O perioada de mai multe zile e UN element, nu N bucati.** Ion: „regandeste
  cum arata in calendar perioadele de implementare pe mai multe zile". Desenam o bara in fiecare
  celula, fiecare cu numele scris din nou si tăiat la latimea unei zile — o lucrare de 8 zile
  aparea ca 9 obiecte ciuntite, desi avea 6 celule de spatiu. Acum benzile sunt elemente ale
  grilei, cu `grid-column: <col> / span <n>`, taiate doar la granita de saptamana.
  **Trei capcane:** `1fr` e `minmax(auto, 1fr)`, deci o banda cu `nowrap` largea coloanele si
  strica alinierea — trebuie `minmax(0, 1fr)`; celulele trebuie asezate explicit in grila,
  altfel auto-plasarea sare peste pozitiile benzilor; benzile trebuie sa devina transparente la
  cursor cat timp tragi, altfel dropul nu ajunge la celula.
  **Bug vechi prins:** clasa `azi` era pe butonul „Azi" SI pe celula zilei de azi, iar `.azi`
  neprefixat centra numarul in mijlocul celulei. Butonul e acum `.b-azi`.
