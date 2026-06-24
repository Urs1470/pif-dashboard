export const meta = {
  name: 'drivecalc-ux-redesign',
  description: 'Panel de design: propune si noteaza moduri de a reorganiza calculatorul de actionari (95 module) ca sa fie mai comod',
  phases: [
    { title: 'Propuneri', detail: '6 paradigme UX distincte, fundamentate pe cod' },
    { title: 'Juriu', detail: 'notare adversariala pe criterii ponderate' },
  ],
}

const FILE = 'C:/Users/ion.ursu/pif-dashboard/frontend/src/pages/Calculator.svelte'
const DATA = 'C:/Users/ion.ursu/pif-dashboard/frontend/src/lib/driveCalc.js'

const DIGEST = `
APLICATIE: "Calculator actionari electrice" — pagina Svelte 5 SPA (Calculator.svelte), data-driven din driveCalc.js (array MODULES). Exista si varianta publica standalone la /calc. Tema Everforest (dark+light), container 1400px centrat, responsive (grid -> 1 coloana pe mobil).
SCARA: 95 module ("carduri"), 7 categorii: Aplicatii (6 sub-procese: pompe&vent/compresoare/ridicare/transportoare/winder/mecanica-gen), Motoare (4 sub-familii: asincron/cc/servo/sincron), VFD, Armonici, Instalatie, Termic, Utilitare. ~487 marimi distincte.
NAVIGARE ACTUALA: o caseta de cautare (filtreaza toate modulele) + un rand de 7 tab-uri de categorie + un al doilea rand de sub-tab-uri (pt Motoare = familii, pt Aplicatii = procese). Selectarea unei categorii/sub-tab afiseaza TOATE modulele ei deodata.
LAYOUT: grid CSS de carduri, repeat(auto-fill, minmax(420px,1fr)) -> ~3 coloane la 1400px.
ANATOMIE CARD (fiecare modul = un card mare, TOTUL desfasurat simultan): titlu + subtitlu; un grid de campuri numerice de INTRARE (eticheta = simbol KaTeX + [u.m.] + text, clickabila -> modal glosar); o lista de REZULTATE calculate (eticheta KaTeX, valoare, formula KaTeX); 0-2 GRAFICE (SVG, click -> zoom modal); o nota; linie params; linie sursa; chip-uri linkuri documentatie. Orice marime (intrare sau rezultat) e clickabila -> modal cu definitie/teorie/sursa/documentatie.
TOATE cardurile dintr-un tab calculeaza rezultate + randeaza graficele simultan.
PROBLEMA (spusa de utilizator): cu pana la ~18 carduri grele per sub-tab e un "zid" lung de derulat, dens vizual, greu de gasit/focalizat un calcul anume. "Foarte greoi".
CONSTRANGERI: ramane data-driven (modulele raman declarative in driveCalc.js); pastreaza glosar/grafice/teorie; pastreaza /calc public; pastreaza estetica Everforest; rulează bine pe laptop (primar) + rezonabil pe mobil; utilizator = inginer PIF care trebuie sa GASEASCA repede un calcul, introduca cateva numere, citeasca rezultate/curba. Fara stare pe backend implicit (se poate localStorage pt favorite/recente).
`

const CRITERIA = `
CRITERII DE EVALUARE (pondere):
1. Gasire & start rapid al unui calcul (x3) — cat de repede ajungi de la "vreau NPSH" la calculul deschis.
2. Scanabilitate / incarcare cognitiva redusa (x3) — fara "zid", usor de parcurs.
3. Pastreaza functiile puternice (x2) — grafice, teorie, posibilitatea de a compara 2-3 calcule cand e nevoie.
4. Efort & risc de implementare pe stack-ul actual (x2) — Svelte 5, data-driven; churn minim e de preferat.
5. Mobil + standalone /calc viabil (x1).
6. Potrivire estetica (Everforest, curat, profesional) (x1).
`

const PARADIGMS = [
  { key: 'workbench', seed: 'Master/detail "workbench": rail stanga ingust cu LISTA tuturor modulelor (doar titluri, grupate pe categorie, grupuri pliabile, cautare in rail, favorite+recente sus); zona principala = UN singur modul focalizat pe toata latimea, cu grafice mari si teorie. Un calcul deschis o data.' },
  { key: 'accordion', seed: 'Carduri compacte pliabile (acordeon): grid de antete pliate (titlu + subtitlu + 1 rezultat-cheie inline); click -> expandeaza intrari/rezultate/grafice in loc; graficele se randeaza lazy doar la expandare; buton densitate.' },
  { key: 'launcher', seed: 'Ecran "launcher"/paleta de comenzi: cautare proeminenta + tile-uri de categorie + recente/favorite pe un home; selectarea deschide un calcul focalizat (full-width); buton inapoi la home. Inspiratie: command palette + spotlight.' },
  { key: 'drilldown', seed: 'Drill-down pe 2 niveluri: categorie -> lista compacta de RANDURI cu numele modulelor din categorie (fara carduri grele) -> click pe rand deschide/expandeaza calculul. Elimina "toate cardurile deodata".' },
  { key: 'pinboard', seed: 'Pinboard/comparatie: implicit = lista compacta cautabila; utilizatorul "fixeaza" (pin) module intr-un set de lucru afisat ca carduri; doar cele fixate calculeaza/randeaza (suporta comparatie 2-3); restul = quick-pick. Persistat in localStorage.' },
  { key: 'progressive', seed: 'Imbunatatire in loc a grid-ului ACTUAL (churn minim): grafice ascunse implicit in spatele unui toggle, sub-anteturi de grup + sub-nav lipicioasa, mod densitate compacta, index "sari la", randare lazy a graficelor. Pastreaza grid-ul dar il face usor.' },
]

const DSCHEMA = { type: 'object', properties: {
  key: { type: 'string' }, name: { type: 'string' },
  summary: { type: 'string', description: '2-3 fraze: ideea centrala' },
  layout: { type: 'string', description: 'descriere concreta a layout-ului (zone, navigare)' },
  mockup: { type: 'string', description: 'mockup ASCII al ecranului principal' },
  interactions: { type: 'array', items: { type: 'string' }, description: 'fluxuri cheie de interactiune' },
  whatChanges: { type: 'array', items: { type: 'string' }, description: 'ce se schimba concret in Calculator.svelte / driveCalc.js' },
  pros: { type: 'array', items: { type: 'string' } },
  cons: { type: 'array', items: { type: 'string' } },
  effort: { type: 'string', enum: ['S', 'M', 'L'] },
  mobileNote: { type: 'string' },
}, required: ['key', 'name', 'summary', 'layout', 'pros', 'cons', 'effort'] }

const JSCHEMA = { type: 'object', properties: {
  ranking: { type: 'array', items: { type: 'object', properties: {
    key: { type: 'string' }, scores: { type: 'object', properties: {
      gasire: { type: 'number' }, scanabilitate: { type: 'number' }, functii: { type: 'number' },
      efort: { type: 'number' }, mobil: { type: 'number' }, estetica: { type: 'number' },
    } }, weighted: { type: 'number' }, verdict: { type: 'string' },
  }, required: ['key', 'weighted', 'verdict'] } },
  recommended: { type: 'string', description: 'key-ul paradigmei recomandate ca primara' },
  graft: { type: 'array', items: { type: 'string' }, description: 'idei din alte paradigme de altoit pe cea recomandata' },
  rationale: { type: 'string' },
}, required: ['ranking', 'recommended', 'rationale'] }

log(`Panel de design: ${PARADIGMS.length} paradigme UX -> juriu adversarial`)

const designs = (await parallel(PARADIGMS.map((p) => () =>
  agent(
    `Esti designer UX/produs senior pentru unelte tehnice (ingineri). Proiectezi o REORGANIZARE a unui calculator de actionari electrice care a devenit greoi.

STAREA ACTUALA:${DIGEST}

Citeste fisierul real ca sa te fundamentezi: ${FILE} (si la nevoie taxonomia din ${DATA}).

SARCINA: dezvolta concret paradigma urmatoare (poti rafina/imbunatati, dar pastreaza esenta):
"${p.seed}"

Livreaza un design CONCRET, implementabil pe Svelte 5 + data-driven, care REZOLVA "zidul de carduri" si face gasirea/folosirea unui calcul rapida. Include un mockup ASCII al ecranului principal, fluxurile de interactiune, ce se schimba exact in cod, pro/contra oneste, efort (S/M/L) si nota mobil. Fii specific, nu generic.`,
    { label: `design:${p.key}`, phase: 'Propuneri', schema: { ...DSCHEMA }, model: 'sonnet', effort: 'medium' }
  ).then((d) => (d ? { ...d, key: d.key || p.key } : null))
))).filter(Boolean)

const judge = await agent(
  `Esti un juriu sever de design (lead UX + inginer frontend). Evaluezi ${designs.length} propuneri de reorganizare a unui calculator tehnic care a devenit greoi.

STAREA ACTUALA:${DIGEST}
${CRITERIA}

PROPUNERILE (JSON):
${JSON.stringify(designs, null, 1)}

Noteaza FIECARE propunere pe cele 6 criterii (1-5), calculeaza scorul ponderat, da un verdict scurt. Apoi recomanda paradigma PRIMARA (key) si ce idei din celelalte merita altoite pe ea. Fii critic si concret, gandeste ca un utilizator inginer care lucreaza la PIF pe laptop. Justifica.`,
  { label: 'juriu', phase: 'Juriu', schema: JSCHEMA, model: 'sonnet', effort: 'high' }
)

return { designs, judge }
