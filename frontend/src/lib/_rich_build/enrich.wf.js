export const meta = {
  name: 'drivecalc-glossary-enrich',
  description: 'Imbogateste definitiile si teoria pentru cele 484 marimi ale calculatorului de actionari (notatie RO/IEC, KaTeX)',
  phases: [
    { title: 'Imbogatire', detail: 'un agent per lot rescrie def+teorie mai bogat' },
    { title: 'Verificare', detail: 'critic adversarial: notatie RO/IEC, KaTeX, acuratete' },
  ],
}

const A = (typeof args === 'string' ? JSON.parse(args) : (args || {}))
const BASE = A.base
const BATCHES = A.batches || []

const NOTATION = `
REGULI DE NOTATIE (OBLIGATORII):
- Limba romana, FARA diacritice (doar ASCII: scrie "frecventa", "putere", nu "frecvență").
- Notatie ROMANEASCA / IEC, NU americana:
  cuplu = M (NICIODATA T), tensiune = U (NICIODATA V), curent = I, putere = P,
  turatie = n, viteza unghiulara = \\omega, randament = \\eta, flux = \\Phi,
  alunecare = s, factor de putere = \\cos\\varphi, rezistenta = R, reactanta = X, impedanta = Z.
- ORICE formula, ecuatie sau simbol se scrie in KaTeX intre $...$. Exemple corecte:
  "$M = 9550 \\cdot P/n$", "$\\omega = 2\\pi n/60$", "$U_d = U_{d0}\\cos\\alpha$",
  "$\\cos\\varphi$", "$\\eta$", "$\\Phi$", "$M \\propto U^2$", "$\\sqrt{3}\\,U\\,I$".
  Foloseste \\cdot pentru inmultire, \\frac sau a/b pentru impartire, indici cu _{...}.
  NU lasa simboluri "desfasurate" ca "omega egal 2 pi n" — foloseste $...$.
- Standarde EUROPENE (IEC/EN), NU NEMA/IEEE/ANSI. Exemple relevante:
  IEC 60034 (masini electrice rotative), IEC 61800-x (sisteme de actionare PDS; -2 nominale, -3 EMC, -5-2 SIL/STO),
  IEC 60364 (instalatii JT), IEC/EN 61000 (CEM / armonici, ex. 61000-3-2/-3-12), IEC 60909 (curenti de scurtcircuit),
  IEC 60072 (dimensiuni motoare), IEC 60269 (sigurante gG/aR).
`

const ENRICH_PROMPT = (b) => `Esti inginer electroenergetician, expert in actionari electrice si punere in functiune (PIF).
Imbogatesti definitiile si teoria unor marimi dintr-un calculator profesional de actionari.

Citeste fisierul de intrare: ${BASE}/in/${b.name}
Este un array JSON. Fiecare element are: mk (cheie unica), key, family, labels[], units[], modules[] (contextul in care apare marimea in calculator), def, ia, practic, teorie (valorile ACTUALE, de imbunatatit).

Pentru FIECARE element produ doua campuri imbogatite:
- "def" (Definitie): ce ESTE fizic marimea si ce reprezinta, precis si complet. 1-2 propozitii. Mai bogat si mai exact decat def actual, dar concis. Foloseste contextul din labels/units/modules ca sa intelegi exact ce simbolizeaza marimea aici.
- "teorie" (Principiu / teorie): principiul fizic + relatia de baza (ecuatia, in $...$) + valori/intervale tipice cand au sens + de ce conteaza la PIF (punere in functiune). 2-4 propozitii. Substantial mai bogat decat teorie actuala. Aplicabil, fara umplutura, fara marketing.

${NOTATION}

CONTINUT corect din punct de vedere ingineresc. Daca o marime e specifica unei familii (asincron, cc, servo, sincron, pompe etc.), tine cont de family. Pastreaza coerenta cu valorile actuale (nu inventa contradictii).

IESIRE: scrie un fisier JSON STRICT VALID (fara comentarii, fara virgule in plus) la calea:
${BASE}/out/${b.name}
Continut: un array cu ACELASI numar de elemente si ACEEASI ordine ca intrarea, fiecare element STRICT de forma:
{ "mk": "<mk-ul exact din intrare>", "def": "<definitie imbogatita>", "teorie": "<teorie imbogatita>" }
NIMIC altceva (fara ia/practic). Pastreaza "mk" identic. Toate valorile string, ASCII fara diacritice.

Dupa scriere, intoarce DOAR un JSON: {"name":"${b.name}","count":<nr elemente scrise>,"notes":"<eventuale incertitudini sau marimi unde nu ai fost sigur>"}.`

const VERIFY_PROMPT = (b) => `Esti recenzor tehnic sever (inginer actionari electrice). Verifici si CORECTEZI un fisier de glosar imbogatit.

Intrare originala (context + valori vechi): ${BASE}/in/${b.name}
Fisier de verificat/corectat (rescris de un alt agent): ${BASE}/out/${b.name}

Verifica FIECARE element din fisierul de iesire si CORECTEAZA pe loc (rescrie fisierul) orice incalcare:
1. NOTATIE: cuplu trebuie sa fie M (nu T), tensiune U (nu V). Orice formula/simbol TREBUIE sa fie in KaTeX $...$ valid. Fara simboluri "desfasurate" in cuvinte (ex. "omega egal..."). Indici cu _{...}.
2. KaTeX VALID: comenzi corecte (\\omega, \\eta, \\Phi, \\cos\\varphi, \\sqrt{}, \\frac{}{}, \\cdot, \\propto, \\approx). Fara $ neimperecheat.
3. STANDARDE: doar IEC/EN (NU NEMA/IEEE/ANSI). Daca apare un standard american, inlocuieste cu echivalentul IEC/EN corect.
4. FARA DIACRITICE (doar ASCII). Limba romana.
5. ACURATETE INGINEREASCA: def si teorie corecte fizic; teorie chiar mai bogata decat originalul (principiu + ecuatie + valori tipice + relevanta PIF). Daca o intrare e superficiala sau gresita, rescrie-o corect si mai bogat.
6. STRUCTURA: array JSON STRICT valid, fiecare element {mk, def, teorie}, mk neschimbat fata de intrare, acelasi numar/ordine de elemente.

${NOTATION}

Rescrie fisierul ${BASE}/out/${b.name} cu versiunea corectata (chiar daca doar cateva elemente s-au schimbat, scrie tot array-ul).
Intoarce DOAR un JSON: {"name":"${b.name}","checked":<nr>,"fixed":<nr corectate>,"issues":["<scurt: ce ai corectat>"]}.`

const SUMMARY = { type: 'object', properties: {
  name: { type: 'string' }, count: { type: 'number' }, notes: { type: 'string' },
}, required: ['name'] }
const VSUMMARY = { type: 'object', properties: {
  name: { type: 'string' }, checked: { type: 'number' }, fixed: { type: 'number' },
  issues: { type: 'array', items: { type: 'string' } },
}, required: ['name'] }

log(`Imbogatesc ${BATCHES.length} loturi (484 marimi) -> def + teorie, notatie RO/IEC + KaTeX`)

const results = await pipeline(
  BATCHES,
  (b) => agent(ENRICH_PROMPT(b), { label: `enrich:${b.name}`, phase: 'Imbogatire', schema: SUMMARY, model: 'sonnet', effort: 'medium' }),
  (enr, b) => agent(VERIFY_PROMPT(b), { label: `verify:${b.name}`, phase: 'Verificare', schema: VSUMMARY, model: 'sonnet', effort: 'medium' })
    .then(v => ({ batch: b.name, enrich: enr, verify: v })),
)

const ok = results.filter(Boolean)
return {
  batches: BATCHES.length,
  done: ok.length,
  totalChecked: ok.reduce((s, r) => s + (r.verify?.checked || 0), 0),
  totalFixed: ok.reduce((s, r) => s + (r.verify?.fixed || 0), 0),
  perBatch: ok.map(r => ({ b: r.batch, fixed: r.verify?.fixed, notes: r.enrich?.notes, issues: r.verify?.issues })),
}
