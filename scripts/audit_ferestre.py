# -*- coding: utf-8 -*-
"""Audit ferestre: fiecare popup, deschis pe rand si masurat.

DE CE EXISTA, LANGA `audit_foaie.py`
`audit_foaie` masoara MECANISMUL foii — treptele, viteza, voalul, gestul — pe una
sau doua foi. Intrebarea lui e „merge foaia?". Aici intrebarea e alta: „apar TOATE
ferestrele cum trebuie?". Aplicatia are peste douazeci de locuri care deschid un
`Modal`, iar pe telefon toate devin foi (`sheet = ecran.telefon`, `Modal.svelte`).
Pana la proba asta majoritatea nu erau atinse de nimic: confirmarile cu „Anuleaza",
formularul de proiect, cel de perioada, exportul, notificarile, sortarea, paleta.

PE DOUA LATIMI, SI ASTA E ESENTIAL. Unele ferestre exista DOAR pe desktop: pe
telefon randul isi ascunde actiunile sub 768px, iar stergerea se face reversibil,
fara intrebare (`Tasks.svelte:415-436`). O proba doar pe telefon ar fi raportat
„confirmarile nu se deschid" — adica un defect inexistent, pentru ferestre care nu
trebuie sa fie acolo.

CE MASOARA, pentru fiecare fereastra, pe fiecare latime si pe fiecare tema:
  sosire      cate animatii de intrare pornesc, si daca fereastra se monteaza o
              singura data (o a doua montare = pagina o randeaza de doua ori)
  pozitie     foaia sta lipita de marginea de jos; dialogul de desktop sta intreg
              in ecran
  actiuni     „Anuleaza" si perechea lui sunt INTREGI in ecran si sunt tinte de
              deget (>= `--tap-min`), nu taiate de marginea de jos
  renuntare   exista o cale vizibila de iesire: Anuleaza, X sau manerul foii
  voal        e cate unul per fereastra, si acopera tot ecranul
  iesire      nodul chiar dispare la Escape si nu ramane niciun voal in urma
  derulare    pagina de dedesubt se blocheaza la deschidere si se elibereaza la
              inchidere (altfel iesi din foaie si ai pierdut si locul din lista)

PATRU CAPCANE DE MASURARE, tratate aici — fara ele raportul minte:
  1. O animatie citita o singura data nimereste ori inainte sa existe, ori dupa ce
     s-a terminat. A doua greseala e cea rea: raporteaza „nicio animatie" pe o
     fereastra care se misca perfect. Se URMARESTE, din cadru in cadru, incepand
     DINAINTE de apasare.
  2. `getAnimations()` intoarce si animatiile parintilor. Se pastreaza doar cele al
     caror element e chiar fereastra sau voalul ei.
  3. Un buton poate fi in DOM, vizibil, si totusi sub bara de jos a telefonului. Se
     compara cu `visualViewport`, nu cu `innerHeight`.
  4. Apasarea lunga NU se poate face cu `page.mouse`: intr-un context `has_touch`
     el tot `pointerType: 'mouse'` produce, iar `apasareLunga.js:57` iese exact pe
     conditia asta. Se trimit atingeri adevarate (`Input.dispatchTouchEvent`).

RULARE
    python scripts/audit_ferestre.py                  # tot
    python scripts/audit_ferestre.py --doar sterge    # doar ce contine „sterge"
    python scripts/audit_ferestre.py --tema inchisa --latime telefon

Ca la `smoke_ui.py`: porneste singur aplicatia, pe un port liber si pe o COPIE a
bazei. Nicio scriere nu ajunge in baza adevarata. Iese cu 0 daca n-a gasit nimic.
"""

import argparse
import os
import shutil
import sys
import tempfile

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADACINA, 'scripts'))

import smoke_ui as S

TAP_MIN = 44
TELEFON = (390, 844)
DESKTOP = (1280, 860)

SONDA = r"""
(() => {
  // Fereastra nu e mereu un `.modal`. Paleta de comenzi isi are propriul strat
  // (`.palette`), calendarul si ceasul la fel (`.dp-pop`, `.so-pop`) — iar pe
  // desktop ultimele doua sunt popovere agatate de declansator, FARA voal, si asta
  // e intentionat (`DatePicker.svelte:120-126`). O proba care cere voal peste tot
  // ar fi raportat un defect exact acolo unde exista o decizie scrisa.
  const SEL_F = '.modal,.palette,.dp-pop,.so-pop';
  const SEL_V = '.backdrop,.palette-backdrop,.dp-voal,.so-voal';
  const FARA_VOAL_PE_DESKTOP = '.dp-pop,.so-pop';

  window.__f = { montari: [], vazute: [] };
  const clase = (n) => (n && n.classList) ? n.classList : { contains: () => false };
  const eV = (n) => clase(n).contains('backdrop') || clase(n).contains('palette-backdrop');
  const eF = (n) => n && n.nodeType === 1 && (clase(n).contains('modal')
                    || clase(n).contains('palette') || eV(n));
  const nume = (n) => eV(n) ? 'voal' : 'fereastra';
  const noteaza = (semn, n) => {
    if (eF(n)) window.__f.montari.push([semn, nume(n), Math.round(performance.now())]);
    else if (n && n.nodeType === 1 && n.querySelectorAll)
      for (const d of n.querySelectorAll(SEL_F + ',' + SEL_V))
        window.__f.montari.push([semn, nume(d), Math.round(performance.now())]);
  };
  // Sonda se injecteaza INAINTE de `body`. `observe(null)` arunca, iar atunci
  // restul functiilor din blocul asta nu s-ar mai defini — si esecul ar arata ca
  // „window.__f.reset is not a function", adica departe de cauza.
  const obs = new MutationObserver((muts) => {
    for (const m of muts) {
      for (const n of m.addedNodes) noteaza('+', n);
      for (const n of m.removedNodes) noteaza('-', n);
    }
  });
  const leaga = () => obs.observe(document.body, { childList: true, subtree: true });
  if (document.body) leaga();
  else document.addEventListener('DOMContentLoaded', leaga, { once: true });

  window.__f.reset = () => { window.__f.montari = []; };

  // ANIMATIILE SE URMARESC, NU SE CITESC O DATA. Vezi capcana 1 din antet.
  window.__f.urmareste = (ms) => {
    window.__f.vazute = [];
    const stiute = new Set();
    const pana = performance.now() + ms;
    const pas = () => {
      for (const a of document.getAnimations()) {
        const t = a.effect && a.effect.target;
        if (!t || !t.closest) continue;
        const e = eF(t) ? t : t.closest(SEL_F + ',' + SEL_V);
        if (!e) continue;
        const ti = (a.effect.getTiming && a.effect.getTiming()) || {};
        const n = a.animationName || a.transitionProperty || 'tranzitie';
        const pe = eV(e) ? 'voal' : 'fereastra';
        const cheie = pe + '|' + n + '|' + Math.round(ti.duration || 0);
        if (stiute.has(cheie)) continue;
        stiute.add(cheie);
        window.__f.vazute.push({ pe: pe, nume: n, durata: Math.round(ti.duration || 0) });
      }
      if (performance.now() < pana) requestAnimationFrame(pas);
    };
    requestAnimationFrame(pas);
  };

  window.__f.masoara = () => {
    const toate = document.querySelectorAll(SEL_F);
    const m = toate[toate.length - 1];      // cea de deasupra
    if (!m) return null;
    const voaluri = document.querySelectorAll(SEL_V);
    const vv = window.visualViewport;
    const jos = vv ? vv.height + vv.offsetTop : window.innerHeight;
    const lat = vv ? vv.width : window.innerWidth;
    const b = m.getBoundingClientRect();

    // Butoanele de ACTIUNE. Nu doar `.modal-footer`: `ConfirmDialog` isi tine
    // perechea „Renunta / Sterge" in `.c-actiuni`, iar o proba care se uita numai
    // in subsol ar fi raportat „fara subsol" tocmai la ferestrele cu Anuleaza.
    const actiuni = [];
    for (const x of m.querySelectorAll('.modal-footer button, .modal-footer a, .c-actiuni button')) {
      const r = x.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      actiuni.push({
        text: (x.textContent || '').trim().slice(0, 22),
        sus: Math.round(r.top), jos: Math.round(r.bottom),
        lat: Math.round(r.width), inalt: Math.round(r.height),
        intreg: r.bottom <= jos + 0.5 && r.top >= -0.5 && r.left >= -0.5 && r.right <= lat + 0.5,
      });
    }
    let dreaptaMax = 0;
    for (const e of m.querySelectorAll('*')) {
      const r = e.getBoundingClientRect();
      if (r.width > 0 && r.right > dreaptaMax) dreaptaMax = r.right;
    }
    const vo = voaluri[voaluri.length - 1]
             ? voaluri[voaluri.length - 1].getBoundingClientRect() : null;
    const sonda = document.createElement('div');
    sonda.style.cssText = 'position:fixed;inset:0;pointer-events:none;visibility:hidden';
    document.body.appendChild(sonda);
    const icb = sonda.getBoundingClientRect();
    sonda.remove();
    const cap = m.querySelector('.modal-header');
    return {
      foaie: m.classList.contains('sheet'),
      paleta: m.classList.contains('palette'),
      popover: !m.classList.contains('sheet') && m.matches(FARA_VOAL_PE_DESKTOP),
      marime: [...m.classList].filter((c) => c.indexOf('modal-') === 0).join(' '),
      sus: Math.round(b.top), jos: Math.round(b.bottom),
      stanga: Math.round(b.left), dreapta: Math.round(b.right),
      ecranJos: Math.round(jos), ecranLat: Math.round(lat),
      actiuni: actiuni, voaluri: voaluri.length, ferestre: toate.length,
      // Se compara cu BLOCUL DE INCADRARE, masurat cu o sonda `position: fixed`,
      // nu cu `innerWidth`. `html { scrollbar-gutter: stable }` (global.css:104)
      // rezerva permanent 10px, iar un element fixat nu-i acopera — deci fata de
      // `innerWidth` orice voal corect ar fi parut cu 10px prea ingust.
      voalAcopera: vo ? (vo.width >= icb.width - 1 && vo.height >= icb.height - 1) : false,
      gutter: Math.round(window.innerWidth - icb.width),
      voalMasura: vo ? (Math.round(vo.width) + 'x' + Math.round(vo.height)) : '-',
      depasire: Math.round(dreaptaMax - lat),
      corpBlocat: document.body.style.position === 'fixed'
                  || getComputedStyle(document.body).overflow === 'hidden'
                  || getComputedStyle(document.documentElement).overflow === 'hidden',
      titlu: (cap ? cap.textContent : (m.getAttribute('aria-label') || '')).trim().slice(0, 32),
      inchidere: !!m.querySelector('.modal-close'),
      // Fiecare fereastra isi are manerul ei: `.sheet-grip` la `Modal`,
      // `.dp-grip` la calendar, `.so-grip` la ceas.
      manerFoaie: !!m.querySelector('.sheet-grip,.dp-grip,.so-grip'),
    };
  };
})();
"""

# Fiecare pas e (`ce`, `tinta`):
#   `sel`   apasa dupa selector
#   `text`  apasa dupa textul vizibil
#   `lung`  APASARE LUNGA, cu atingere adevarata (vezi `apasa_lung`)
# Pasii de dinainte de ultimul sunt drumul pana la fereastra; pe ULTIMUL se
# masoara sosirea. `unde` spune pe ce latimi are voie sa existe fereastra.
FERESTRE = [
    # Pe desktop adaugarea e IN LINIE (`quick-add`, `Tasks.svelte:1145`), fara
    # fereastra: butonul plutitor exista doar sub `ecran.telefon`.
    dict(nume='adauga-task', ruta='/tasks', unde='telefon', pasi=[('sel', '.fab')]),
    dict(nume='panou-task', ruta='/tasks', unde='telefon', pasi=[('sel', '.tmain')]),
    dict(nume='actiuni-task', ruta='/tasks', unde='telefon', pasi=[('lung', '.tmain')]),
    dict(nume='alege-data', ruta='/tasks', unde='ambele',
         pasi=[('sel', '.tmain'), ('sel', '.modal .dp-trigger')],
         pasi_desktop=[('hover', '.tmain'), ('sel', '.dp-trigger')]),
    dict(nume='editor-nota', ruta='/tasks', unde='telefon',
         pasi=[('sel', '.tmain'), ('sel', '.modal .td-link')]),
    dict(nume='editeaza-task', ruta='/tasks', unde='desktop',
         pasi=[('hover', '.tmain'), ('sel', '.ta-chip:not(.ta-sterge)')]),
    dict(nume='sterge-task', ruta='/tasks', unde='desktop',
         pasi=[('hover', '.tmain'), ('sel', '.ta-chip.ta-sterge')]),
    dict(nume='notificari', ruta='/tasks', unde='ambele',
         pasi=[('text', 'Personal'), ('sel', 'button[aria-label="Notificări"]')]),
    dict(nume='cauta', ruta='/tasks', unde='ambele',
         pasi=[('sel', 'button[aria-label="Caută"]')],
         # Pe desktop dockul e strans, iar paleta se cheama cu scurtatura.
         pasi_desktop=[('taste', 'Control+k')]),
    # Pe desktop butonul de tema comuta direct, fara fereastra — prin desen.
    dict(nume='tema', ruta='/tasks', unde='telefon',
         pasi=[('sel', 'button[aria-label="Temă"]')]),
    dict(nume='proiect-nou', ruta='/projects', unde='ambele', pasi=[('sel', '.fab')],
         pasi_desktop=[('text', 'Proiect nou')]),
    # Pe desktop sortarea e un meniu agatat de buton, nu o fereastra — prin desen.
    dict(nume='sorteaza', ruta='/projects', unde='telefon', pasi=[('sel', '.sort-trigger')]),
    dict(nume='proiect-editeaza', ruta='/projects', unde='ambele',
         pasi=[('sel', '.pcard'), ('text', 'Editează')]),
    dict(nume='proiect-sterge', ruta='/projects', unde='ambele',
         pasi=[('sel', '.pcard'), ('sel', 'button[aria-label="Șterge proiectul"]')]),
    # Idem in proiect (`ProjectDetail.svelte:1360`, gardat pe `ecran.telefon`).
    dict(nume='task-proiect', ruta='/projects', unde='telefon',
         pasi=[('sel', '.pcard'), ('sel', '.fab')]),
    dict(nume='zi-calendar', ruta='/calendar', unde='telefon', pasi=[('sel', '.zi')]),
    dict(nume='export-pdf', ruta='/plan', unde='ambele', pasi=[('text', 'ExportPDF')]),
]

CUVINTE_RENUNTARE = ('nuleaz', 'enun', 'napoi')

# Ce cuvant foloseste aplicatia ca sa spuna „las-o balta". Daca iese mai mult
# de unul, doua ferestre cer acelasi lucru cu doua cuvinte.
ETICHETE_RENUNTARE = {}


def out(s=''):
    S.out(s)


def apasa_lung(page, cdp, tinta):
    """APASARE LUNGA, cu atingere adevarata. Vezi capcana 4 din antet."""
    e = page.locator(tinta).first
    e.scroll_into_view_if_needed(timeout=4000)
    b = e.bounding_box(timeout=4000)
    if not b:
        raise RuntimeError('elementul nu are geometrie')
    pct = {'touchPoints': [{'x': b['x'] + b['width'] / 2,
                            'y': b['y'] + b['height'] / 2, 'id': 1}]}
    cdp.send('Input.dispatchTouchEvent', dict(type='touchStart', **pct))
    page.wait_for_timeout(620)          # peste `APASARE_MENIU`
    cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))


def apasa(page, tip, tinta, jurnal, cdp=None):
    try:
        if tip == 'lung':
            apasa_lung(page, cdp, tinta)
        elif tip == 'hover':
            page.hover(tinta, timeout=4000)
        elif tip == 'taste':
            page.keyboard.press(tinta)
        elif tip == 'sel':
            page.locator(tinta).first.click(timeout=4000)
        else:
            page.get_by_text(tinta, exact=False).first.click(timeout=4000)
        page.wait_for_timeout(430)
        return True
    except Exception as exc:
        jurnal.append('nu s-a putut apasa %s "%s": %s'
                      % (tip, tinta, str(exc).split(chr(10))[0][:70]))
        return False


def masoara_fereastra(ctx, baza, f, tema, telefon):
    """Deschide o fereastra, o masoara, o inchide. Intoarce (probleme, note)."""
    note, probleme = [], []
    page = ctx.new_page()
    page.add_init_script(SONDA)
    cdp = ctx.new_cdp_session(page)
    try:
        page.goto(baza + '/#' + f['ruta'], wait_until='load')
        page.wait_for_timeout(1500)
        page.evaluate("(t) => { document.documentElement.setAttribute('data-theme', t);"
                      " try { localStorage.setItem('pif-tema', t) } catch (e) {} }", tema)
        page.wait_for_timeout(220)

        derulare_inainte = page.evaluate(
            "() => document.body.style.position + '|' + document.documentElement.style.overflow")

        pasi = f.get('pasi_desktop') if (not telefon and f.get('pasi_desktop')) else f['pasi']
        for tip, tinta in pasi[:-1]:
            if not apasa(page, tip, tinta, note, cdp):
                return ['nu s-a ajuns la fereastra'], note
        page.evaluate("() => window.__f.reset()")
        page.evaluate("() => window.__f.urmareste(900)")
        tip, tinta = pasi[-1]
        if not apasa(page, tip, tinta, note, cdp):
            return ['nu s-a deschis'], note
        page.wait_for_timeout(650)
        animatii = page.evaluate("() => window.__f.vazute")
        m = page.evaluate("() => window.__f.masoara()")
        montari = page.evaluate("() => window.__f.montari")

        if m is None:
            return ['fereastra nu exista in pagina dupa apasare'], note

        note.append('%s | %s | sus=%d jos=%d (ecran %d) | ferestre=%d voaluri=%d'
                    % (m['titlu'] or '(fara titlu)',
                       m['marime'] or ('paleta' if m['paleta'] else '(fara marime)'),
                       m['sus'], m['jos'], m['ecranJos'], m['ferestre'], m['voaluri']))

        intrari = [a for a in animatii if a['durata'] > 0]
        if not intrari:
            probleme.append('nicio animatie de intrare (fereastra apare dintr-o data)')
        note.append('sosire: %d animatii (%s)'
                    % (len(intrari), ', '.join('%s %dms' % (a['pe'], a['durata'])
                                               for a in intrari[:4]) or '-'))
        montari_f = [x for x in montari if x[0] == '+' and x[1] == 'fereastra']
        if len(montari_f) > 1:
            probleme.append('fereastra se monteaza de %d ori' % len(montari_f))

        if m['voaluri'] == 0:
            if not m['popover']:
                probleme.append('fara voal')
            else:
                note.append('voal: niciunul — popover agatat de declansator, prin desen')
        elif m['voaluri'] > m['ferestre']:
            probleme.append('%d voaluri pentru %d ferestre (fond dublu)'
                            % (m['voaluri'], m['ferestre']))
        elif not m['voalAcopera']:
            probleme.append('voalul nu acopera tot ecranul (voal %s, ecran %dx%d)'
                            % (m['voalMasura'], m['ecranLat'], m['ecranJos']))

        if m['foaie']:
            if abs(m['jos'] - m['ecranJos']) > 2:
                probleme.append('foaia nu e lipita de jos (jos=%d, ecran=%d)'
                                % (m['jos'], m['ecranJos']))
            if m['sus'] < -1:
                probleme.append('foaia iese pe sus (%d)' % m['sus'])
        else:
            if m['sus'] < -1 or m['jos'] > m['ecranJos'] + 1:
                probleme.append('fereastra nu incape pe verticala (%d..%d, ecran %d)'
                                % (m['sus'], m['jos'], m['ecranJos']))
        if m['depasire'] > 1:
            probleme.append('continut care iese in dreapta cu %dpx' % m['depasire'])

        if m['actiuni']:
            note.append('actiuni: ' + ' | '.join(
                '%s %dx%d%s' % (b['text'], b['lat'], b['inalt'],
                                '' if b['intreg'] else ' TAIAT')
                for b in m['actiuni']))
            inaltimi = set(b['inalt'] for b in m['actiuni'])
            if len(inaltimi) > 1:
                probleme.append('butoanele din acelasi rand au inaltimi diferite: %s'
                                % ', '.join('%s %dpx' % (b['text'], b['inalt'])
                                            for b in m['actiuni']))
            for b in m['actiuni']:
                if not b['intreg']:
                    probleme.append('butonul "%s" nu incape in ecran (jos=%d, ecran=%d)'
                                    % (b['text'], b['jos'], m['ecranJos']))
                if b['inalt'] < TAP_MIN - 1 and telefon:
                    probleme.append('butonul "%s" are %dpx inaltime (sub --tap-min %d)'
                                    % (b['text'], b['inalt'], TAP_MIN))
        else:
            note.append('actiuni: fara rand de actiuni')

        cale = []
        if any(any(c in b['text'] for c in CUVINTE_RENUNTARE) for b in m['actiuni']):
            cale.append('Anuleaza')
        if m['inchidere']:
            cale.append('X')
        if m['manerFoaie']:
            cale.append('maner')
        # Paleta si popoverele de desktop se inchid la clic in afara sau Escape, si
        # n-au nevoie de buton: sunt agatate de declansator, nu blocheaza ecranul.
        # Cerinta de „Anuleaza vizibil" e pentru ferestrele care iau ecranul.
        if not cale and not m['paleta'] and not m['popover']:
            probleme.append('nicio cale vizibila de renuntare (nici Anuleaza, nici X, nici maner)')
        note.append('renuntare: ' + (', '.join(cale) or 'clic in afara / Escape'))

        if m.get('gutter'):
            note.append('gutter de scrollbar: %dpx la dreapta, nevopsiti de voal '
                        '(`html { scrollbar-gutter: stable }`)' % m['gutter'])

        if m['foaie'] and not m['corpBlocat']:
            probleme.append('pagina de dedesubt nu e blocata cat e foaia deschisa')

        # --- iesire
        #
        # Se cere sa plece fereastra de DEASUPRA, nu toate: calendarul deschis peste
        # panoul taskului lasa in urma panoul, si asta e corect. O proba care numara
        # „au ramas ferestre" ar fi raportat un defect exact acolo unde teancul
        # functioneaza cum trebuie.
        inainte = page.evaluate(
            "() => ({ f: document.querySelectorAll('.modal,.palette,.dp-pop,.so-pop').length,"
            " v: document.querySelectorAll('.backdrop,.palette-backdrop,.dp-voal,.so-voal').length })")
        page.evaluate("() => window.__f.reset()")
        try:
            page.keyboard.press('Escape')
        except Exception:
            pass
        page.wait_for_timeout(800)
        ramas = page.evaluate(
            "() => ({ f: document.querySelectorAll('.modal,.palette,.dp-pop,.so-pop').length,"
            " v: document.querySelectorAll('.backdrop,.palette-backdrop,.dp-voal,.so-voal').length })")
        if ramas['f'] >= inainte['f']:
            probleme.append('fereastra de deasupra nu a plecat la Escape (%d -> %d)'
                            % (inainte['f'], ramas['f']))
        if ramas['v'] > ramas['f']:
            probleme.append('a ramas un voal fara fereastra (%d voaluri, %d ferestre)'
                            % (ramas['v'], ramas['f']))
        derulare_dupa = page.evaluate(
            "() => document.body.style.position + '|' + document.documentElement.style.overflow")
        if derulare_dupa != derulare_inainte and ramas['f'] == 0:
            probleme.append('derularea paginii nu s-a eliberat (era "%s", a ramas "%s")'
                            % (derulare_inainte, derulare_dupa))
        for b in m['actiuni']:
            if any(c in b['text'] for c in CUVINTE_RENUNTARE):
                ETICHETE_RENUNTARE.setdefault(b['text'], []).append(f['nume'])
        return probleme, note
    finally:
        page.close()


def main():
    ap = argparse.ArgumentParser(description='Fiecare fereastra, deschisa si masurata.')
    ap.add_argument('--doar', help='doar ferestrele al caror nume contine textul asta')
    ap.add_argument('--tema', choices=['deschisa', 'inchisa', 'ambele'], default='ambele')
    ap.add_argument('--latime', choices=['telefon', 'desktop', 'ambele'], default='ambele')
    ap.add_argument('--baza', help='alta baza sursa')
    arg = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit('Lipseste playwright. Ruleaza:\n'
                         '  pip install playwright\n'
                         '  python -m playwright install chromium')

    db_sursa = arg.baza or os.path.join(RADACINA, 'pif_dashboard.db')
    if not os.path.isfile(db_sursa):
        raise SystemExit('Nu exista pif_dashboard.db local.')

    lista = [f for f in FERESTRE if not arg.doar or arg.doar in f['nume']]
    teme = ['light', 'dark'] if arg.tema == 'ambele' else \
           (['light'] if arg.tema == 'deschisa' else ['dark'])
    latimi = []
    if arg.latime in ('telefon', 'ambele'):
        latimi.append(('telefon', TELEFON, True))
    if arg.latime in ('desktop', 'ambele'):
        latimi.append(('desktop', DESKTOP, False))

    tmp = tempfile.mkdtemp(prefix='pif-ferestre-')
    db = os.path.join(tmp, 'audit.db')
    shutil.copy2(db_sursa, db)
    port = S.port_liber()
    proc, baza = S.porneste_serverul(port, db, os.path.join(tmp, 'server.log'))
    out('Server pe %s (baza: copie de unica folosinta)\n' % baza)

    total = 0
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(executable_path=os.environ.get('PIF_CHROMIUM') or None)
            for eticheta, (w, h), telefon in latimi:
                ctx = br.new_context(viewport={'width': w, 'height': h},
                                     is_mobile=telefon, has_touch=telefon,
                                     service_workers='block')
                p = ctx.new_page()
                p.goto(baza + '/login', wait_until='load')
                p.fill('#pin', S.PIN_TEST)
                p.click('button[type="submit"]')
                p.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
                p.close()
                for tema in teme:
                    out('=== %s, tema %s ==='
                        % (eticheta, 'deschisa' if tema == 'light' else 'inchisa'))
                    for f in lista:
                        if f['unde'] != 'ambele' and f['unde'] != eticheta:
                            out('  --    %-17s (nu exista pe %s, prin desen)'
                                % (f['nume'], eticheta))
                            continue
                        probleme, note = masoara_fereastra(ctx, baza, f, tema, telefon)
                        out('  %s  %-17s %s' % ('OK  ' if not probleme else 'PICA',
                                                f['nume'], note[0] if note else ''))
                        for n in note[1:]:
                            out('           %s' % n)
                        for pr in probleme:
                            out('        -> %s' % pr)
                        total += len(probleme)
                    out()
                ctx.close()
            br.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    if len(ETICHETE_RENUNTARE) > 1:
        out('NECONCORDANTA: aplicatia numeste renuntarea in %d feluri:'
            % len(ETICHETE_RENUNTARE))
        for eticheta, unde in sorted(ETICHETE_RENUNTARE.items()):
            out('    „%s" — %s' % (eticheta, ', '.join(sorted(set(unde)))))
        out('  Acelasi gest, doua cuvinte. E o decizie de produs, nu un defect de cod:')
        out('  proba o raporteaza, alegerea o face omul.')
        out()
        total += 1

    out('OK — nimic de reparat.' if not total else '%d probleme.' % total)
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
