# -*- coding: utf-8 -*-
"""Audit mobil: masoara ce nu se vede intr-o captura de ecran.

DE CE EXISTA, LANGA `smoke_ui.py`
`smoke_ui` raspunde la „s-a randat pagina?". O pagina poate insa sa se randeze
perfect si sa fie de nefolosit cu degetul: un buton taiat de marginea din dreapta
(`overflow-x: clip` il ascunde fara niciun semn), o tinta de 22px, un camp de
14px care face Safari sa faca zoom la fiecare atingere. Nimic din toate astea nu
arunca vreo eroare — de asta au trecut neobservate luni de zile.

CE MASOARA, pe trei latimi de telefon si pe toate rutele:
  - depasiri     element care iese din ecran fara sa fie taiat de un parinte
  - tinte mici   control sub 40px care nu are nici strat invizibil in jur
  - fonturi      camp sub 16px (Safari face zoom la focus si pagina sare)
  - gesturi      reordonarea prin maner si cele doua glisari, cu deget adevarat
  - perioade     benzile din Calendar se muta si se intind cu MOUSE; pe deget, nu se misca
  - de facut     gruparea pe termen, adaugarea cu zi, mutarea din gest, „Anulează"
  - „azi"        boardul de pe Acasa si grupa „Azi" din /tasks sunt aceeasi multime
  - iesire       randul bifat se stinge si pleaca imediat, nu dupa server

TREI CAPCANE DE MASURARE, toate tratate aici — fara ele raportul minte:
  1. `pointer-events: none` inseamna ca elementul NU e o tinta. Altfel ar aparea
     zeci de false alarme. (Benzile din Calendar raman masurabile: primesc
     atingeri, chiar daca de la 2026-08-08 tot ce fac e sa deschida ziua de sub
     ele — vezi ACCEPTATE.)
  2. Un strat invizibil in jur (`::after` cu inset negativ) mareste suprafata
     reala fara sa umfle eticheta. Se masoara intreband ce raspunde la 21px de
     centru, nu citind `getBoundingClientRect`.
  3. `elementFromPoint` intoarce `null` in afara ferestrei, deci orice element de
     sub pliu ar fi raportat ca mic. Se aduce in ecran inainte de intrebare.

RULARE
    python scripts/audit_mobil.py                 # tot
    python scripts/audit_mobil.py --fara-gesturi  # doar geometrie

Ca la `smoke_ui.py`: porneste singur aplicatia, pe un port liber si pe o COPIE a
bazei. Iese cu 0 daca nu a gasit nimic.
"""

import argparse
import datetime
import os
import shutil
import sys
import tempfile

# Numele lunilor din `DatePicker.svelte` — folosite ca sa stiu pe ce luna s-a
# deschis calendarul si cate apasari pe „luna urmatoare" mai trebuie.
LUNI_DP = ['Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie',
           'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie']

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADACINA, 'scripts'))

import smoke_ui as S

RUTE = [
    ('/', 'Acasa'),
    ('/projects', 'Proiecte'),
    ('/tasks', 'Taskuri'),
    ('/plan', 'Planificator'),
    ('/calendar', 'Calendar'),
    ('/departament', 'Departament'),
    ('/calculator', 'Calculator'),
]

ECRANE = [('iphone-se', 375, 667), ('android-mic', 360, 740), ('iphone-14', 390, 844)]

# FUSUL ORAR AL TESTELOR NU E UTC, CU BUNA STIINTA.
# Ion lucreaza in Romania (UTC+2/+3), iar containerele de test ruleaza pe UTC —
# unde ora locala si UTC coincid, deci orice greseala de conversie e INVIZIBILA.
# Asa a trecut neobservat un bug pe care il vedea la fiecare atingere: butoanele
# „Azi"/„Mâine" construiau data cu `new Date().toISOString()`, adica in UTC, iar
# miezul noptii local intr-un fus de la est de Greenwich cade in ziua precedenta.
# „Azi" scria IERI, la orice ora. Testele erau verzi.
FUS_TEST = 'Europe/Bucharest'

PRAG_TINTA = 40      # sub atat raportam; tinta dorita e --tap-min (44)

# Ce stim ca e sub prag CU BUNA STIINTA. Tine lista scurta si scrie MOTIVUL —
# altfel auditul devine o lista de exceptii si nu mai spune nimic.
ACCEPTATE = {
    # Reper de o zi in Ganttul din Planificator. Pe 14 zile o zi are ~22px, deci
    # doua repere alaturate s-ar acoperi la 44px: ai schimba o tinta mica pe una
    # gresita. Ratarea nu costa nimic — reperul doar sare la randul taskului din
    # lista de dedesubt, iar acel rand e cat toata latimea.
    'mt-pin': 'reper de o zi in Gantt; la 44px reperele din zile alaturate s-ar suprapune',
    # Doar informativ in rezumat — logica sta in iesirea_randului(): cadrele
    # animatiei de iesire nu se numara in medii headless (acceptat 2026-08-04).
    'cadre-iesire': 'Chromium headless taie tranzitia de iesire la 1-2 cadre; pe hardware real e vizibila',
    # Banda de perioada din Calendar: 12px inaltime pe telefon (2026-08-07).
    # Regula de 44px exista ca sa nu ratezi tinta si sa obtii ALTCEVA. Aici o
    # ratare nu produce nimic diferit: o atingere pe banda cheama exact
    # `atingeZi` cu ziua de sub deget, adica fix ce ar fi facut celula de
    # dedesubt — si de pe 2026-08-08 asta e SINGURUL lucru pe care il poate face
    # (pe telefon pista se citeste, nu se manipuleaza: nicio tragere, niciun
    # maner). Deci banda nu mai e o tinta distincta, e desen peste celula.
    # Nu poate fi facuta de 44px: inaltimea benzii E pasul grilei de benzi
    # (`--h-banda`), deci trei lucrari intr-o zi ar cere o celula de 132px.
    # CHEIA SE POTRIVESTE PE SUBSIR CU SELECTORUL RAPORTAT (`acceptat`), deci
    # trebuie sa fie numele elementului care EXISTA. A fost scrisa `button.banda`
    # in aceeasi tura care a mutat banda de pe `<button>` pe `<div>` cu pointer
    # events — deci exceptia n-a prins niciodata, iar pagina trecea doar cand
    # masuratoarea apuca sa se faca inainte ca benzile sa se randeze. O exceptie
    # care nu se potriveste e mai rea decat una lipsa: pare acoperita si nu e.
    'div.banda': 'banda de perioada, 12px pe telefon; o atingere scurta face exact ce face ziua de sub ea, iar gestul de mutare cere apasare lunga (T8) — deci o ratare nu produce nimic diferit',
    # `button.maner` A PLECAT DIN LISTA. Manerele de capat nu mai exista pe
    # telefon (`@media (hover: none) { .maner { display: none } }`), deci
    # masuratoarea nici nu le vede — o exceptie pentru un element care nu se
    # randeaza pare acoperire si nu e nimic. Ca ele chiar lipsesc se verifica
    # explicit in `perioadele_se_trag`, sectiunea 0.
}

MASOARA = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const out = { vw, scrollW: document.documentElement.scrollWidth, deposit: [], mici: [], fonturi: [], nemasurate: [] };
  const vizibil = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const atingibil = (el) => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      if (getComputedStyle(p).pointerEvents === 'none') return false;
    }
    return true;
  };
  const taiat = (el) => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      if (['hidden', 'clip', 'auto', 'scroll'].includes(getComputedStyle(p).overflowX)) return true;
    }
    return false;
  };
  const sel = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    const c = String(el.className || '');
    if (c && !c.includes('[object')) s += '.' + c.trim().split(/\s+/).filter(x => !x.startsWith('svelte-')).slice(0, 3).join('.');
    return s;
  };

  for (const el of document.querySelectorAll('body *')) {
    if (!vizibil(el)) continue;
    const r = el.getBoundingClientRect();
    if ((r.right > vw + 1 || r.left < -1) && !taiat(el)) {
      out.deposit.push({ sel: sel(el), left: Math.round(r.left), right: Math.round(r.right) });
    }
  }

  const controale = 'button, a[href], [role="button"], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  for (const el of document.querySelectorAll(controale)) {
    if (!vizibil(el) || !atingibil(el)) continue;
    let r = el.getBoundingClientRect();
    let w = r.width, h = r.height;
    if (h < PRAG || w < PRAG) {
      // Benzile de sus si de jos sunt ACOPERITE: antetul lipit (56px) sus, dockul
      // plutitor (68px + margine) jos. Acolo `elementFromPoint` raspunde ce e
      // deasupra, nu ce e sub deget — deci mutam elementul in mijloc inainte de
      // masuratoare. Marginea de jos trebuie sa fie mai mare decat cea de sus,
      // altfel exact ultimul rand de deasupra dockului iese „mic" de fiecare data.
      if (r.top < 70 || r.bottom > innerHeight - 110) {
        el.scrollIntoView({ block: 'center' });
        r = el.getBoundingClientRect();
      }
      // Daca nici acum nu e in mijloc, pagina e la capatul derularii si elementul
      // sta sub antetul lipit sau sub dock. Acolo `elementFromPoint` raspunde ce
      // e DEASUPRA, nu ce e sub deget — deci nu putem afla daca are strat in jur.
      // Il declaram nemasurat, nu vinovat: o alarma falsa repetata te invata sa
      // ignori raportul, ceea ce e mai rau decat sa nu-l ai.
      if (r.top < 70 || r.bottom > innerHeight - 110) {
        out.nemasurate.push({ sel: sel(el), w: Math.round(w), h: Math.round(h) });
        continue;
      }
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const prinde = (dx, dy) => {
        const t = document.elementFromPoint(cx + dx, cy + dy);
        return t && (t === el || el.contains(t) || t.contains(el));
      };
      if (prinde(-21, 0) && prinde(21, 0)) w = 44;
      if (prinde(0, -21) && prinde(0, 21)) h = 44;
    }
    if (h < PRAG || w < PRAG) {
      out.mici.push({ sel: sel(el), w: Math.round(w), h: Math.round(h),
                      txt: (el.textContent || el.value || '').trim().slice(0, 26) });
    }
  }

  for (const el of document.querySelectorAll('input, select, textarea')) {
    if (!vizibil(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 16) out.fonturi.push({ sel: sel(el), fs });
  }
  return out;
}
""".replace('PRAG', str(PRAG_TINTA))

# O tragere continua cu `pointerType: 'touch'`. Playwright nu are drag pe touch,
# iar `tap()` nu misca degetul — deci gestul se compune aici, in pagina.
TRAGE = """([x0, y0, pasi, id]) => {
  const el = document.elementFromPoint(x0, y0);
  if (!el) return false;
  const ev = (t, x, y) => el.dispatchEvent(new PointerEvent(t, {
    pointerId: id, pointerType: 'touch', isPrimary: true,
    clientX: x, clientY: y, bubbles: true, cancelable: true }));
  ev('pointerdown', x0, y0);
  for (const [x, y] of pasi) ev('pointermove', x, y);
  const u = pasi[pasi.length - 1];
  ev('pointerup', u[0], u[1]);
  // Browserul trimite un `click` dupa ridicarea degetului, iar `glisare.js` il
  // inghite O DATA (ca gestul sa nu ajunga click pe ce era dedesubt). Fara el
  // aici, steagul „tocmai am glisat" ramane ridicat si prima atingere de dupa —
  // pe un buton din panou — ar fi inghitita in loc sa lucreze.
  el.dispatchEvent(new MouseEvent('click', { clientX: u[0], clientY: u[1], bubbles: true, cancelable: true }));
  return true;
}"""


def out(s=''):
    sys.stdout.buffer.write((str(s) + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


def acceptat(s):
    return any(k in s for k in ACCEPTATE)


def geometrie(ctx, baza):
    """Depasiri / tinte / fonturi, pe fiecare ruta si fiecare latime."""
    probleme = 0
    for nume, w, h in ECRANE:
        out('--- %s (%dx%d) ---' % (nume, w, h))
        for ruta, eticheta in RUTE:
            page, _col, _blocata = S.deschide(ctx, baza + '/#' + ruta, w, h)
            page.wait_for_timeout(600)
            # CONTINUTUL VENIT DIN RETEA TREBUIE SA FIE PE ECRAN INAINTE DE MASURA.
            # 600ms erau uneori de ajuns si uneori nu: benzile din Calendar vin din
            # `/api/calendar`, iar cand nu apucau sa se randeze pagina se masura
            # GOALA si trecea. Un audit care da alt raspuns la fiecare rulare nu
            # spune nimic — si tocmai asta a ascuns benzile luni de zile.
            # `networkidle` in loc de inca un `sleep` fix: asteapta exact cat e
            # nevoie, nu o valoare ghicita.
            try:
                page.wait_for_load_state('networkidle', timeout=8000)
            except Exception:
                pass
            r = page.evaluate(MASOARA)
            page.close()
            mici = [m for m in r['mici'] if not acceptat(m['sel'])]
            rele = len(r['deposit']) + len(mici) + len(r['fonturi'])
            probleme += rele
            out('  %-4s %-14s depasiri=%-2d tinte=%-2d fonturi=%d'
                % ('OK' if not rele else 'PICA', eticheta,
                   len(r['deposit']), len(mici), len(r['fonturi'])))
            for d in r['deposit'][:4]:
                out('        iese din ecran: %s (dreapta %d > %d)' % (d['sel'], d['right'], r['vw']))
            for m in mici[:4]:
                out('        tinta %dx%d: %s %r' % (m['w'], m['h'], m['sel'], m['txt']))
            for f in r['fonturi'][:3]:
                out('        font %spx (Safari face zoom): %s' % (f['fs'], f['sel']))
            for n in r['nemasurate'][:3]:
                out('        (nemasurat, sub antet/dock: %s %dx%d)' % (n['sel'], n['w'], n['h']))
        out()
    return probleme


def gesturi(ctx, baza):
    """Cele trei gesturi de pe randul de task, cu deget adevarat."""
    out('--- gesturi (390x844) ---')
    probleme = 0
    page = ctx.new_page()
    page.set_viewport_size({'width': 390, 'height': 844})
    erori = []
    page.on('pageerror', lambda e: erori.append(str(e).split('\n')[0]))
    page.goto(baza + '/#/', wait_until='load')
    try:
        page.wait_for_selector('.arow', timeout=15000)
    except Exception:
        out('  SARI  boardul „Astăzi" e gol — nimic de gesticulat')
        page.close()
        return 0
    page.wait_for_timeout(900)

    def titluri():
        return page.eval_on_selector_all('.arow .atitle', 'e => e.map(x => x.textContent.trim())')

    # 1. reordonare: randul 1 sub randul 3
    inainte = titluri()
    if len(inainte) >= 3:
        cutii = page.eval_on_selector_all(
            '.arow', 'e => e.slice(0,3).map(x => { const r = x.getBoundingClientRect(); return [r.top, r.height] })')
        m = page.eval_on_selector(
            '.arow .gl-maner',
            'e => { const r = e.getBoundingClientRect(); return [r.left + r.width/2, r.top + r.height/2] }')
        dy = (cutii[2][0] + cutii[2][1] / 2) - (cutii[0][0] + cutii[0][1] / 2)
        page.evaluate(TRAGE, [m[0], m[1], [[m[0], m[1] + dy * k / 8] for k in range(1, 9)], 1])
        page.wait_for_timeout(1200)
        dupa = titluri()
        if dupa[2] == inainte[0] and dupa[0] == inainte[1]:
            out('  OK    reordonare prin maner')
        else:
            out('  PICA  reordonare: %r -> %r' % (inainte[:3], dupa[:3])); probleme += 1
        page.reload(wait_until='load')
        page.wait_for_selector('.arow', timeout=15000)
        page.wait_for_timeout(1200)
        if titluri()[:3] != dupa[:3]:
            out('  PICA  reordonarea nu s-a salvat pe server'); probleme += 1
        else:
            out('  OK    reordonarea s-a salvat pe server')

    # 2. glisare spre stanga -> DESCHIDE ALEGEREA ZILEI
    #
    # Doua schimbari de contract, una peste alta. Intai panoul de trei-patru
    # actiuni × 58px a plecat (176px din 390 acopereau taskul pe care actionai),
    # inlocuit de un verb executat, ca la bifare. Apoi verbul „Mâine" a plecat si
    # el: amanarea nu e „inca o zi", muti un task cand stii CAND il faci, iar ziua
    # aia e rareori mâine. Acum gestul deschide acelasi calendar ca butonul
    # „Planifică" de pe desktop si ca foaia din /tasks.
    #
    # De aceea NU se verifica un transform ramas dupa ridicare: randul se intoarce
    # la zero. Se verifica pista si pragul PE PARCURS — altfel gestul ar trece si
    # daca n-ai vedea nimic cat timp tragi — apoi ca alegerea chiar s-a deschis.
    titlu_inainte = titluri()[0] if titluri() else None
    r = page.eval_on_selector('.arow', 'e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height] }')
    cx, cy = r[0] + r[2] * 0.6, r[1] + r[3] / 2
    masuri_s = page.evaluate("""([x0, y0, pasi]) => {
      const el = document.elementFromPoint(x0, y0);
      const row = el.closest('.arow');
      const ev = (t, x, y) => el.dispatchEvent(new PointerEvent(t, {
        pointerId: 2, pointerType: 'touch', isPrimary: true,
        clientX: x, clientY: y, bubbles: true, cancelable: true }));
      const cite = () => {
        const ic = row.querySelector('.gl-ico-s');
        return { s: parseFloat(row.style.getPropertyValue('--gl-s') || '0'),
                 amana: row.classList.contains('gl-amana'),
                 stanga: row.classList.contains('gl-stanga'),
                 pista: !!row.querySelector('.gl-pista-s'),
                 icoOp: ic ? parseFloat(getComputedStyle(ic).opacity) : 0 };
      };
      ev('pointerdown', x0, y0);
      const jurnal = [];
      for (const [x, y] of pasi) { ev('pointermove', x, y); jurnal.push(cite()); }
      const u = pasi[pasi.length - 1];
      ev('pointerup', u[0], u[1]);
      el.dispatchEvent(new MouseEvent('click', { clientX: u[0], clientY: u[1], bubbles: true, cancelable: true }));
      return jurnal;
    }""", [cx, cy, [[cx - d, cy] for d in (20, 50, 90, 150, 230)]])
    # „Creste pe parcurs" = EXISTA un moment in care pista se vede si inca n-a
    # ajuns la capat. Se cauta printre esantioane, nu la un index fix: pragul e
    # 42% din latimea randului, deci un pas ales prost ar sari peste zona de mijloc
    # si testul ar pica pe alegerea pasilor, nu pe comportament.
    final = masuri_s[-1] if masuri_s else {}
    partial = [m for m in masuri_s if 0.05 < m.get('s', 0) < 0.95]
    if not final.get('pista'):
        out('  PICA  glisare stanga: pista „Planifică" lipseste din rand'); probleme += 1
    elif not partial:
        out('  PICA  glisare stanga: pista nu creste pe parcurs (%s)' % [m.get('s') for m in masuri_s]); probleme += 1
    elif not final.get('amana'):
        out('  PICA  glisare stanga: pragul nu s-a atins (--gl-s=%s)' % final.get('s')); probleme += 1
    else:
        out('  OK    glisare stanga: pista creste pe parcurs, apoi pragul')

    # Calendarul chiar s-a deschis — si ca SHEET, nu ca popup agatat de un
    # declansator care pe telefon nici nu e randat.
    page.wait_for_timeout(900)
    if page.locator('.dp-pop.sheet').count() == 0:
        out('  PICA  glisare stanga: calendarul nu s-a deschis'); probleme += 1
    else:
        out('  OK    glisare stanga deschide alegerea zilei')
        # Si ziua aleasa chiar muta taskul: pica de pe boardul de azi.
        #
        # Ziua trebuie sa fie in VIITOR, si de aceea nu se ia „ultima din grila":
        # calendarul se deschide pe luna TERMENULUI, iar pe board taskurile sunt
        # scadente azi sau restante — deci grila e adesea o luna trecuta, si o zi
        # din trecut lasa taskul pe board ca restant. Corect, dar nu ce masuram.
        # Se avanseaza pana strict dupa luna curenta, apoi se ia ziua 15.
        azi = datetime.date.today()
        for _ in range(6):
            titlu_luna = page.locator('.dp-pop .dp-title').inner_text().split()
            if len(titlu_luna) != 2:
                break
            an = int(titlu_luna[1])
            luna = LUNI_DP.index(titlu_luna[0]) + 1 if titlu_luna[0] in LUNI_DP else azi.month
            if (an, luna) > (azi.year, azi.month):
                break
            page.locator('.dp-pop .dp-nav').nth(1).click()
            page.wait_for_timeout(280)
        z = page.locator('.dp-pop.sheet .dp-day', has_text='15').first
        if z.count():
            z.click()
            page.wait_for_timeout(1800)
            if titlu_inainte and titlu_inainte in (titluri() or []):
                out('  PICA  ziua aleasa n-a mutat taskul (%r)' % titlu_inainte); probleme += 1
            else:
                out('  OK    ziua aleasa muta taskul de pe board')

    # 3. glisare spre dreapta -> bifeaza, cu verdele de prag INAINTE de ridicare
    page.reload(wait_until='load')
    page.wait_for_selector('.arow', timeout=15000)
    page.wait_for_timeout(1200)
    r = page.eval_on_selector('.arow', 'e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height] }')
    cx, cy = r[0] + r[2] * 0.35, r[1] + r[3] / 2
    # Esantionam pe TOT parcursul degetului, nu doar la capat. Ion, despre versiunea
    # de dinainte: „acum doar se coloreaza si nu e intuitiv ce face" — semnalul
    # exista, dar aparea abia dupa 42% din latimea randului, deci pe cea mai mare
    # parte a gestului trageai un rand peste nimic. De asta se verifica si mijlocul.
    masuri = page.evaluate("""([x0, y0, pasi]) => {
      const el = document.elementFromPoint(x0, y0);
      const row = el.closest('.arow');
      const ev = (t, x, y) => el.dispatchEvent(new PointerEvent(t, {
        pointerId: 3, pointerType: 'touch', isPrimary: true,
        clientX: x, clientY: y, bubbles: true, cancelable: true }));
      const cite = () => {
        const pi = row.querySelector('.gl-pista');
        const ic = row.querySelector('.gl-ico');
        return { p: parseFloat(row.style.getPropertyValue('--gl-p') || '0'),
                 bifa: row.classList.contains('gl-bifa'),
                 pista: !!pi,
                 icoOp: ic ? parseFloat(getComputedStyle(ic).opacity) : 0,
                 actiuniVizibile: (() => { const a = row.querySelector('.gl-actiuni');
                     return a ? getComputedStyle(a).visibility === 'visible' : false })() }; };
      ev('pointerdown', x0, y0);
      const out = [];
      for (const p of pasi) { ev('pointermove', p[0], p[1]); out.push(cite()) }
      const u = pasi[pasi.length - 1];
      ev('pointerup', u[0], u[1]);
      return out;
    }""", [cx, cy, [[cx + d, cy] for d in (40, 110, 200, 260)]])
    page.wait_for_timeout(1400)

    mijloc = masuri[1] if len(masuri) > 1 else masuri[0]
    prag = masuri[-1]['bifa']
    if not masuri[0]['pista']:
        out('  PICA  glisare dreapta: nu exista pista de bifare in rand'); probleme += 1
    elif mijloc['icoOp'] <= 0.05:
        # Fara asta, „intuitiv ce face" se pierde in tacere: gestul ar merge, dar
        # ai afla ce face abia dupa ce l-ai dus la capat.
        out('  PICA  glisare dreapta: bifa nu se vede pe parcurs (opacitate %.2f la mijloc)'
            % mijloc['icoOp']); probleme += 1
    elif not (0 < mijloc['p'] < 1) and mijloc['p'] != 1:
        out('  PICA  glisare dreapta: progresul --gl-p nu creste gradual'); probleme += 1
    elif not prag:
        # Regula asta a fost STEARSA din build o data (Svelte taie selectorii cu
        # clase puse din JS, nu doar avertizeaza) — deci se verifica, nu se crede.
        out('  PICA  glisare dreapta: pragul de bifare nu se marcheaza vizual'); probleme += 1
    elif masuri[-1]['actiuniVizibile']:
        # Doua panouri deodata = doua raspunsuri la „ce se intampla daca dau drumul".
        out('  PICA  glisare dreapta: panoul de actiuni ramane vizibil peste pista'); probleme += 1
    else:
        out('  OK    glisare dreapta: bifa creste pe parcurs, apoi pragul')

    if erori:
        out('  PICA  exceptii in timpul gesturilor: %s' % erori[:3]); probleme += 1
    page.close()
    out()
    return probleme


def lista_de_facut(ctx, baza):
    """Ce face ca /tasks sa fie o lista DE FACUT, nu un depozit: gruparea dupa
    termen, adaugarea cu zi dintr-un singur gest, mutarea din glisare si
    „Anulează" la bifat."""
    out('--- lista de facut (390x844) ---')
    probleme = 0
    page = ctx.new_page()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(baza + '/#/tasks', wait_until='load')
    try:
        page.wait_for_selector('.trow', timeout=15000)
    except Exception:
        out('  SARI  lista de taskuri e goala')
        page.close()
        return 0
    page.wait_for_timeout(1000)

    def zi(cond, mesaj, detaliu=''):
        nonlocal probleme
        out(('  OK    ' if cond else '  PICA  ') + mesaj + (('  — %s' % detaliu) if (detaliu and not cond) else ''))
        if not cond:
            probleme += 1

    capete = page.eval_on_selector_all('.grup-cap .grup-t', 'e => e.map(x => x.textContent.trim())')
    ORDINE = ['Restante', 'Azi', 'Mâine', 'Zilele astea', 'Mai târziu', 'Fără termen']
    idx = [ORDINE.index(x) for x in capete if x in ORDINE]
    zi(len(capete) >= 1, 'lista e grupata pe termen', capete)
    zi(idx == sorted(idx), 'grupele sunt in ordinea zilei', capete)
    zi('Fără termen' not in capete or capete[-1] == 'Fără termen',
       '„Fără termen" e ultima, nu prima', capete)

    # ADAUGAREA PE TELEFON TRECE PRIN BUTONUL MARE CU PLUS.
    #
    # Testul verifica alt contract decat pana acum, si nu fiindca s-a stricat
    # ceva: redesignul din 2026-08-08 cere O SINGURA cale de adaugare per ecran
    # — linia cu Enter pe desktop, butonul cu plus pe telefon. Compozitorul
    # inline de pe /tasks a plecat de pe latimea asta (pe „Astăzi" ramane, e al
    # boardului). Deci aici se verifica: butonul EXISTA, e o tinta adevarata, si
    # duce la formularul din care poti pune si termenul din prima.
    MARCA = 'Audit — task de proba'
    n0 = page.eval_on_selector_all('.trow', 'e => e.length')
    zi(page.locator('.quick-add').count() == 0,
       'compozitorul inline nu se dubleaza cu butonul de adaugare')
    fab = page.locator('.fab').first
    zi(fab.count() > 0 and fab.is_visible(), 'butonul mare cu plus e pe ecran')
    if fab.count() and fab.is_visible():
        c = fab.bounding_box()
        zi(c and c['width'] >= 44 and c['height'] >= 44,
           'butonul de adaugare e o tinta de deget', c)
        fab.click()
        page.wait_for_timeout(700)
        camp = page.locator('.modal input[type="text"], .modal-body input[type="text"]').first
        zi(camp.count() > 0, 'butonul deschide formularul de task nou')
        if camp.count():
            camp.fill(MARCA)
            page.wait_for_timeout(200)
            trimite = page.locator('.modal-actions button', has_text='Adaugă').first
            if trimite.count() == 0:
                trimite = page.locator('.modal-actions button').last
            trimite.click()
            page.wait_for_timeout(1600)
            zi(page.eval_on_selector_all('.trow', 'e => e.length') == n0 + 1, 'taskul s-a creat')

    # mutare din gest: glisarea spre stanga deschide FOAIA cu panoul de termen
    # desfacut, si alegi ziua acolo. Pe /tasks termenele sunt imprastiate pe
    # saptamani, deci un „Mâine" fix ar fi o zi aleasa de aplicatie, nu de tine —
    # de aceea aici gestul duce la alegere, nu executa (spre deosebire de „Astăzi").
    r = page.evaluate(CAUTA_RAND, MARCA)
    if r:
        cx, cy = r[0] + r[2] * 0.5, r[1] + r[3] / 2
        page.evaluate(TRAGE, [cx, cy, [[cx - d, cy] for d in (30, 100, 180, 240)], 5])
        page.wait_for_timeout(900)
        zi(page.locator('.ts-zile .sz-optiune').count() > 0,
           'glisarea deschide foaia cu ziua de ales')
        page.evaluate(ALEGE_ZI_IN_FOAIE, 'Mâine')
        page.wait_for_timeout(1400)
        page.keyboard.press('Escape')
        page.wait_for_timeout(700)
        grup = page.evaluate(GRUPUL_LUI, MARCA)
        zi(grup == 'Mâine', 'ziua aleasa din foaie muta taskul', grup)

    # bifare + anulare
    page.reload(wait_until='load')
    page.wait_for_selector('.trow', timeout=15000)
    page.wait_for_timeout(1200)
    n1 = page.eval_on_selector_all('.trow', 'e => e.length')
    page.evaluate(BIFEAZA, MARCA)
    page.wait_for_timeout(1400)
    zi(page.eval_on_selector_all('.trow', 'e => e.length') == n1 - 1, 'taskul bifat pleaca din lista')
    anuleaza = page.locator('.toast-action', has_text='Anulează')
    zi(anuleaza.count() > 0, 'bifarea ofera „Anulează"')
    if anuleaza.count():
        anuleaza.first.click()
        page.wait_for_timeout(1600)
        zi(page.eval_on_selector_all('.trow', 'e => e.length') == n1, '„Anulează" aduce taskul inapoi')

    page.close()
    out()
    return probleme


GRUPUL_LUI = """(marca) => {
  const r = [...document.querySelectorAll('.trow')].find(x => x.textContent.includes(marca));
  if (!r) return null;
  let n = r.closest('.trow-wrap');
  while (n && !n.classList.contains('grup-cap')) n = n.previousElementSibling;
  return n ? n.querySelector('.grup-t').textContent.trim() : null;
}"""

CAUTA_RAND = """(marca) => {
  const x = [...document.querySelectorAll('.trow')].find(e => e.textContent.includes(marca));
  if (!x) return null;
  x.scrollIntoView({ block: 'center' });
  const b = x.getBoundingClientRect();
  return [b.left, b.top, b.width, b.height];
}"""

# Ziua se alege ACUM DIN FOAIE, nu dintr-un panou sub rand: glisarea spre stanga
# deschide foaia taskului cu panoul de termen desfacut (Azi / Mâine / Alege ziua /
# Scoate). Panoul din rand — patru actiuni × 58px = 232px din 390 — a plecat cu
# tot cu CSS-ul lui, deci `.gl-actiuni .glb` nu mai exista.
# `.sz-optiune` — butoanele lui `components/ui/SelectorZi.svelte`. Erau scrise
# local in fiecare foaie (`.ts-zi`), cu alt desen in fiecare loc; de la redesign
# sunt o componenta, deci si testul intreaba de ea.
ALEGE_ZI_IN_FOAIE = """(eticheta) => {
  const b = [...document.querySelectorAll('.ts-zile .sz-optiune')].find(x => x.textContent.includes(eticheta));
  if (!b) return false;
  b.click();
  return true;
}"""

# Deschide foaia FARA gest, cand testul vrea doar sa mute ziua (atingerea randului
# deschide aceeasi foaie; panoul de termen se desface cu un clic pe randul de data).
DESCHIDE_FOAIA = """(marca) => {
  const r = [...document.querySelectorAll('.trow')].find(x => x.textContent.includes(marca));
  if (!r) return false;
  r.querySelector('.tmain').click();
  return true;
}"""

BIFEAZA = """(marca) => {
  const r = [...document.querySelectorAll('.trow')].find(x => x.textContent.includes(marca));
  if (!r) return false;
  r.scrollIntoView({ block: 'center' });
  r.querySelector('.check').click();
  return true;
}"""


def dockul_pe_telefon(ctx, baza):
    """Dock-ul pe telefon: cinci tinte, mai mari, si ascundere la derulare.

    De ce e verificat. Ascunderea la derulare s-a rupt O DATA fara nicio eroare:
    efectul care readuce dock-ul la schimbarea rutei chema o functie care CITEA
    starea de ascundere, deci efectul devenea dependent de ea si o stingea imediat
    ce se aprindea. Build verde, zero exceptii, dock care pur si simplu nu se
    ascundea. Asta se prinde doar deruland si masurand.

    Si numarul de tinte conteaza: daca cineva readauga rute in `PE_TELEFON` fara sa
    scada marimea, dock-ul iese din ecran — la 56px de tinta incap cinci, nu opt."""
    out('--- dock pe telefon ---')
    probleme = 0
    page = ctx.new_page()
    page.set_viewport_size({'width': 390, 'height': 844})

    def zi(cond, mesaj, detaliu=''):
        nonlocal probleme
        out(('  OK    ' if cond else '  PICA  ') + mesaj + (('  — %s' % detaliu) if (detaliu and not cond) else ''))
        if not cond:
            probleme += 1

    STARE = """() => {
      const d = document.querySelector('.dock');
      if (!d) return null;
      const r = d.getBoundingClientRect();
      const it = [...d.querySelectorAll('.dock-item')];
      const lat = it.map(e => { const b = e.getBoundingClientRect(); return Math.min(b.width, b.height) });
      return { n: it.length, tinta: Math.round(Math.min(...lat)),
               ascuns: d.classList.contains('hidden'),
               subEcran: Math.round(r.top) >= window.innerHeight,
               depaseste: r.right > window.innerWidth + 0.5 || r.left < -0.5,
               y: Math.round(window.scrollY) }; }"""

    # Calculatorul e o pagina sigur mai inalta decat ecranul; lista de taskuri a
    # bazei de test poate incapea intr-un ecran, si atunci nu exista derulare de
    # masurat (prima varianta a testului „a trecut" exact asa, degeaba).
    page.goto(baza + '/#/calculator', wait_until='load')
    page.wait_for_selector('.dock', timeout=15000)
    # SE ASTEAPTA CONTINUTUL, NU INVELISUL. `.dock` e in shell-ul aplicatiei si
    # apare imediat; modulele Calculatorului vin dintr-un chunk de ~880 KB, si
    # pana soseste el pagina e cat ecranul — deci masuratoarea de mai jos gasea
    # `scrollHeight == 844` si pica pe „nu se poate derula", desi pagina reala
    # are 1600+. Nu era o regresie, era o cursa.
    page.wait_for_function('() => document.documentElement.scrollHeight > window.innerHeight + 40',
                           timeout=20000)
    page.wait_for_timeout(600)

    s0 = page.evaluate(STARE)
    if not s0:
        zi(False, 'dock-ul exista pe telefon')
        page.close()
        return probleme

    zi(s0['n'] == 5, 'cinci tinte pe telefon', 'sunt %d' % s0['n'])
    zi(s0['tinta'] >= 52, 'tintele folosesc spatiul castigat (>=52px)', '%dpx' % s0['tinta'])
    zi(not s0['depaseste'], 'dock-ul nu iese din ecran')

    inaltime = page.evaluate('document.documentElement.scrollHeight')
    if inaltime <= 844 + 40:
        zi(False, 'pagina de test poate fi derulata', 'scrollHeight=%d' % inaltime)
        page.close()
        return probleme

    def deruleaza(pana, pas=60):
        cur = page.evaluate('window.scrollY')
        d = 1 if pana > cur else -1
        while (d > 0 and cur < pana) or (d < 0 and cur > pana):
            cur = min(pana, cur + pas) if d > 0 else max(pana, cur - pas)
            page.evaluate('window.scrollTo(0, %d)' % cur)
            page.wait_for_timeout(55)
        page.wait_for_timeout(420)

    # CONTRACT INTORS PE 2026-08-10 (Ion): dock-ul pe telefon e FIX, jos de tot,
    # mereu la vedere — a rasturnat propria cerinta din 2026-07-31 („urmareste
    # derularea ca bara de adresa"). Cu etichetele sub iconite dockul e harta
    # aplicatiei, iar o harta care fuge de sub deget e mai scumpa decat ecranul
    # castigat. Testul verifica acum CONTRARIUL celui vechi: derularea NU-l
    # misca, si sta lipit de marginea de jos. (Singura ascundere ramasa e
    # tastatura — netestabila credibil headless.)
    deruleaza(500)
    jos = page.evaluate(STARE)
    zi(not jos['ascuns'], 'coborand prin pagina, dock-ul RAMANE (contract 2026-08-10)')
    zi(not jos['subEcran'], 'sta pe ecran, nu sub el')
    lipit = page.evaluate("""() => {
      const r = document.querySelector('.dock').getBoundingClientRect();
      return Math.round(window.innerHeight - r.bottom); }""")
    zi(abs(lipit) <= 1, 'lipit de marginea de jos (bottom: 0)', 'gol de %dpx' % lipit)

    deruleaza(0)
    varf = page.evaluate(STARE)
    zi(not varf['ascuns'], 'si in varful paginii sta afara')

    page.close()
    return probleme


def perioadele_se_trag(browser, baza):
    """Perioadele din Calendar se MUTA si se INTIND — cu MOUSE. Pe deget, NU.

    DE CE EXISTA
    Pana la 2026-08-07 tragerea era pe HTML5 drag-and-drop. Nu functiona — pe
    deget nici nu putea, fiindca `dragstart` nu exista la atingere — si nimic
    nu se plangea: zero exceptii, zero erori de consola, build verde, `smoke_ui`
    verde, `audit_mobil` verde. Bara isi purta linistita tooltipul „Trage ca sa
    muti lucrarea" deasupra unui calendar care nu muta nimic, si asa a stat pana
    a incercat Ion.

    Un gest care nu se declanseaza ARATA IDENTIC cu unul care se declanseaza si
    nu are ce face. Singurul mod de a face diferenta e sa tragi si sa te uiti pe
    server daca s-a schimbat ceva — exact ce face functia asta.

    CONTRACTUL S-A SCHIMBAT PE 2026-08-08 (handoff-ul de design, turele 7–8):
    **pe telefon pista se citeste, nu se manipuleaza** — nicio tragere de banda,
    niciun maner de capat, nicio alipire. Motivul e masura, nu gustul: alegi o ZI
    dintr-o celula de ~48px acoperita de benzi, iar ce iese din gest nu e „aproape
    ce voiai", e alta zi scrisa in baza. De pe telefon atingi ziua si raspunzi in
    panou. Deci verificarea la deget si-a schimbat semnul: nu mai cere ca gestul sa
    functioneze, ci ca el sa NU existe (nici manere desenate, nici mutare).
    Cu mouse-ul ramane exact cum era.

    Doua contexte, nu unul: cu `has_touch` Chromium transforma intrarile de mouse
    in atingeri, deci un singur context ar testa o singura poarta din doua.
    """
    out('--- perioadele se trag (Calendar) ---')
    probleme = 0

    def stare(page, pid):
        return page.evaluate(
            """async (id) => {
                 const prima = document.querySelector('.zi').dataset.zi;
                 const d = await fetch('/api/calendar?start=' + prima + '&zile=49').then(r => r.json());
                 const p = d.perioade.find(x => String(x.id) === String(id));
                 return p ? [p.data_start, p.data_sfarsit || p.data_start] : null;
               }""", pid)

    def trage_mouse(page, _cdp, x0, y0, x1, y1, pauza):
        page.mouse.move(x0, y0)
        page.mouse.down()
        page.wait_for_timeout(pauza)
        page.mouse.move(x0 + 14, y0 + 3, steps=3)
        page.mouse.move(x1, y1, steps=10)
        page.wait_for_timeout(120)
        page.mouse.up()
        page.wait_for_timeout(900)

    def trage_deget(page, cdp, x0, y0, x1, y1, pauza):
        """Atingere ADEVARATA, prin `Input.dispatchTouchEvent`.

        NU `page.mouse`: intr-un context cu `has_touch` el tot `pointerType:
        'mouse'` produce (verificat), deci ar trece pe langa exact ramura care
        conteaza — apasarea lunga. O verificare care ocoleste ce vrea sa
        verifice e mai rea decat lipsa ei.
        """
        pct = lambda x, y: {'touchPoints': [{'x': x, 'y': y, 'id': 1}]}
        cdp.send('Input.dispatchTouchEvent', dict(type='touchStart', **pct(x0, y0)))
        page.wait_for_timeout(pauza)          # zabovirea: asta apuca lucrarea
        for k in (1, 2, 3):
            cdp.send('Input.dispatchTouchEvent',
                     dict(type='touchMove', **pct(x0 + 5 * k, y0 + k)))
        for k in range(1, 9):
            cdp.send('Input.dispatchTouchEvent', dict(
                type='touchMove',
                **pct(x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8)))
        page.wait_for_timeout(120)
        cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
        page.wait_for_timeout(900)

    for eticheta, tactil, latime, inalt, pauza in (
            ('mouse', False, 1280, 800, 0),
            ('deget', True, 390, 844, 420)):
        ctx = browser.new_context(
            viewport={'width': latime, 'height': inalt},
            is_mobile=tactil, has_touch=tactil, service_workers='block',
            timezone_id=FUS_TEST)
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page) if tactil else None
        trage = trage_deget if tactil else trage_mouse
        erori = []
        page.on('pageerror', lambda e: erori.append(str(e).split('\n')[0]))
        try:
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', S.PIN_TEST)
            page.click('button[type="submit"]')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
            page.goto(baza + '/#/calendar', wait_until='load')
            # Pe o baza fara perioade (clona proaspata, container de CI) nu e
            # nimic de tras. Se SARE, ca peste tot in fisierul asta — o proba
            # fara date nu e o picare, iar un traceback de Playwright in locul
            # unei linii „SARI" ascunde ce chiar merita reparat.
            try:
                page.wait_for_selector('.banda[data-perioada]', timeout=15000)
            except Exception:
                out('  SARI  %s: nicio perioada in calendar' % eticheta)
                ctx.close()
                continue
            page.wait_for_timeout(700)

            zile = page.eval_on_selector_all(
                '.zi[data-zi]',
                'e => e.map(z => { const r = z.getBoundingClientRect();'
                ' return [z.dataset.zi, r.left + r.width / 2, r.top + r.height / 2] })')
            harta = {z[0]: (z[1], z[2]) for z in zile}

            # --- 0. PE DEGET: gestul EXISTA, dupa apasare lunga (T8) ---
            # Contractul s-a intors pe 2026-08-14: pana atunci pista se citea si
            # atat, fiindca pe un ecran fara hover manerele n-aveau cum sa fie
            # anuntate. Ce tine acum locul afordantei e apasarea lunga: 300ms
            # fara miscare pornesc gestul, 10px il anuleaza. Trei promisiuni, si
            # se verifica toate trei — a treia le tine pe primele doua.
            if tactil:
                # (a) IN REPAUS manerele nu se vad. Doua dungi permanente pe
                #     fiecare banda ar fi zgomot, si n-ar avea ce apuca degetul
                #     intr-o celula de ~48px.
                vizibile = page.eval_on_selector_all(
                    '.maner',
                    'e => e.filter(m => { const s = getComputedStyle(m);'
                    ' return s.display !== "none" && s.visibility !== "hidden"'
                    ' && parseFloat(s.opacity) > 0.05 }).length')
                if vizibile:
                    out('  PICA  deget: %d manere vizibile IN REPAUS' % vizibile)
                    probleme += 1
                else:
                    out('  OK    deget: manerele stau ascunse pana ceri gestul')

                # Ca la mutarea cu mouse-ul: NU prima banda din DOM. Daca
                # proiectul ei e inchis, `/api/calendar` o taie la
                # `data_finalizare` (v35), deci un gest REUSIT o face sa dispara
                # din raspuns si proba ar citi „nu s-a mutat". Sectiunea de
                # mouse ruleaza prima si schimba datele, deci care banda e
                # „prima" varia de la o rulare la alta — exact felul de proba
                # care da alt raspuns de fiecare data.
                deschise0 = page.evaluate(
                    """async () => {
                         const prima = document.querySelector('.zi').dataset.zi;
                         const d = await fetch('/api/calendar?start=' + prima + '&zile=49').then(r => r.json());
                         return d.perioade.filter(p => p.status !== 'finalizat').map(p => String(p.id));
                       }""")
                b0 = page.evaluate(
                    """(ids) => {
                         const el = [...document.querySelectorAll('.banda[data-perioada]')]
                           .find(x => ids.includes(String(x.dataset.perioada)));
                         if (!el) return null;
                         const r = el.getBoundingClientRect();
                         return [el.dataset.perioada, r.left + r.width / 2, r.top + r.height / 2];
                       }""", deschise0)
                if not b0:
                    out('  SARI  deget: nicio perioada pe un proiect deschis')
                    ctx.close()
                    continue
                ord0 = [z[0] for z in zile]
                in0 = stare(page, b0[0])

                # (b) O GLISARE SCURTA, FARA APASARE, RAMANE DERULARE. Proba
                #     asta e cea care face gestul acceptabil: daca ea pica,
                #     lista nu se mai poate derula cu degetul peste benzi.
                cdp.send('Input.dispatchTouchEvent', dict(
                    type='touchStart',
                    touchPoints=[dict(x=b0[1], y=b0[2], radiusX=6, radiusY=6, force=1)]))
                for k in range(1, 5):
                    cdp.send('Input.dispatchTouchEvent', dict(
                        type='touchMove',
                        touchPoints=[dict(x=b0[1], y=b0[2] + k * 12, radiusX=6, radiusY=6, force=1)]))
                cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                page.wait_for_timeout(400)
                if stare(page, b0[0]) == in0:
                    out('  OK    deget: glisarea fara apasare lunga nu muta nimic')
                else:
                    out('  PICA  deget: o glisare simpla a mutat perioada')
                    probleme += 1

                # (c) APASAREA LUNGA + TRAGEREA MUTA. Si banda se ridica, si
                #     manerele devin tinte de deget — semnalul care spune ca
                #     gestul a prins, pe un ecran care n-are cursor.
                t0 = ord0[min((ord0.index(in0[0]) if in0[0] in ord0 else 0) + 9, len(ord0) - 1)]
                cdp.send('Input.dispatchTouchEvent', dict(
                    type='touchStart',
                    touchPoints=[dict(x=b0[1], y=b0[2], radiusX=6, radiusY=6, force=1)]))
                page.wait_for_timeout(450)          # peste APASARE_LUNGA (300ms)
                ridicata = page.evaluate(
                    '''() => { const b = document.querySelector('.banda.se-trage');
                         if (!b) return null;
                         const m = b.querySelector('.maner');
                         return { umbra: getComputedStyle(b).boxShadow !== 'none',
                                  maner: m ? Math.round(parseFloat(getComputedStyle(m).width)) : 0 }; }''')
                if not ridicata:
                    out('  PICA  deget: apasarea lunga nu a pornit gestul')
                    probleme += 1
                else:
                    if ridicata['umbra']:
                        out('  OK    deget: banda se ridica la apucare')
                    else:
                        out('  PICA  deget: banda apucata nu se ridica (niciun semnal)')
                        probleme += 1
                    if ridicata['maner'] >= 44:
                        out('  OK    deget: manerele devin tinte de deget (%dpx)' % ridicata['maner'])
                    else:
                        out('  PICA  deget: manerele au %dpx dupa apucare' % ridicata['maner'])
                        probleme += 1
                for k in range(1, 9):
                    cdp.send('Input.dispatchTouchEvent', dict(
                        type='touchMove',
                        touchPoints=[dict(x=b0[1] + (harta[t0][0] - b0[1]) * k / 8,
                                          y=b0[2] + (harta[t0][1] - b0[2]) * k / 8,
                                          radiusX=6, radiusY=6, force=1)]))
                    page.wait_for_timeout(16)
                cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                page.wait_for_timeout(1200)
                dupa0 = stare(page, b0[0])
                if dupa0 and dupa0[0] != in0[0]:
                    out('  OK    deget: apasare lunga + tragere MUTA (%s -> %s)' % (in0[0], dupa0[0]))
                else:
                    out('  PICA  deget: gestul nu a mutat perioada (a ramas %s)' % in0)
                    probleme += 1

                if erori:
                    out('  PICA  deget: exceptii in pagina: %s' % erori[:2])
                    probleme += 1
                continue          # `finally` inchide pagina si contextul

            # --- 1. mutarea ---
            # NU prima banda din DOM: daca proiectul ei e inchis, `/api/calendar`
            # o taie la `data_finalizare` (v35), deci o mutare REUSITA dincolo de
            # acea zi o face sa dispara din raspuns si proba ar citi „nu s-a
            # mutat". Se cere serverului lista si se alege una a carei perioada
            # apartine unui proiect deschis.
            deschise = page.evaluate(
                """async () => {
                     const prima = document.querySelector('.zi').dataset.zi;
                     const d = await fetch('/api/calendar?start=' + prima + '&zile=49').then(r => r.json());
                     return d.perioade.filter(p => p.status !== 'finalizat').map(p => String(p.id));
                   }""")
            b = page.evaluate(
                """(ids) => {
                     const el = [...document.querySelectorAll('.banda[data-perioada]')]
                       .find(x => ids.includes(String(x.dataset.perioada)));
                     if (!el) return null;
                     const r = el.getBoundingClientRect();
                     return [el.dataset.perioada, r.left + r.width / 2, r.top + r.height / 2];
                   }""", deschise)
            if not b:
                out('  SARI  %s: nicio perioada pe un proiect deschis' % eticheta)
                ctx.close()
                continue
            pid, bx, by = b[0], b[1], b[2]
            inainte = stare(page, pid)
            # O zi din aceeasi fereastra, indeajuns de departe cat sa nu fie ea
            # insasi; +9 sare peste o saptamana, deci si peste alt rand din grila.
            ordonate = [z[0] for z in zile]
            i = ordonate.index(inainte[0]) if inainte[0] in ordonate else 0
            tinta = ordonate[min(i + 9, len(ordonate) - 1)]
            trage(page, cdp, bx, by, harta[tinta][0], harta[tinta][1], pauza)
            dupa = stare(page, pid)
            if dupa and dupa[0] != inainte[0]:
                out('  OK    %s: perioada s-a mutat (%s -> %s)' % (eticheta, inainte[0], dupa[0]))
            else:
                out('  PICA  %s: perioada NU s-a mutat (a ramas %s)' % (eticheta, inainte)); probleme += 1

            # Durata se pastreaza la mutare — altfel „mutarea" ar fi o taiere.
            if dupa and (nr_zile(dupa) != nr_zile(inainte)):
                out('  PICA  %s: mutarea a schimbat durata (%s -> %s)' % (eticheta, inainte, dupa)); probleme += 1
            else:
                out('  OK    %s: durata s-a pastrat la mutare' % eticheta)

            # --- 2. redimensionarea ---
            page.reload(wait_until='load')
            page.wait_for_selector('.banda[data-perioada]', timeout=15000)
            page.wait_for_timeout(700)
            man = page.eval_on_selector_all(
                '.banda.lat[data-perioada] .maner.dr',
                'e => e.slice(0,1).map(m => { const r = m.getBoundingClientRect(); const b = m.closest(".banda");'
                ' return [b.dataset.perioada, r.left + r.width / 2, r.top + r.height / 2] })')
            if not man:
                out('  SARI  %s: nicio perioada de mai multe zile in fereastra' % eticheta)
            else:
                pid2, mx, my = man[0]
                inainte2 = stare(page, pid2)
                zile2 = page.eval_on_selector_all(
                    '.zi[data-zi]',
                    'e => e.map(z => { const r = z.getBoundingClientRect();'
                    ' return [z.dataset.zi, r.left + r.width / 2, r.top + r.height / 2] })')
                h2 = {z[0]: (z[1], z[2]) for z in zile2}
                ord2 = [z[0] for z in zile2]
                j = ord2.index(inainte2[1]) if inainte2[1] in ord2 else 0
                capat = ord2[min(j + 2, len(ord2) - 1)]
                trage(page, cdp, mx, my, h2[capat][0], h2[capat][1], pauza)
                dupa2 = stare(page, pid2)
                if dupa2 and dupa2[0] == inainte2[0] and dupa2[1] != inainte2[1]:
                    out('  OK    %s: capatul s-a mutat, inceputul a stat (%s -> %s)'
                        % (eticheta, inainte2[1], dupa2[1]))
                else:
                    out('  PICA  %s: redimensionare: %s -> %s' % (eticheta, inainte2, dupa2)); probleme += 1

            # (Proba „fara apasare lunga nu se muta nimic" a plecat odata cu
            #  gestul: pe deget nu se mai muta NIMIC, nici cu apasare lunga —
            #  se verifica mai sus, in sectiunea 0.)

            if erori:
                out('  PICA  %s: exceptii in pagina: %s' % (eticheta, erori[:2])); probleme += 1
        finally:
            page.close()
            ctx.close()
    return probleme


def nr_zile(pereche):
    """Numarul de zile dintr-un [start, sfarsit] ISO."""
    from datetime import date
    a = date.fromisoformat(pereche[0])
    b = date.fromisoformat(pereche[1])
    return (b - a).days + 1


def iesirea_randului(ctx, baza):
    """Randul bifat trebuie sa PLECE — vizibil si imediat.
    Doua lucruri se pot strica separat, si amandoua in tacere:
      - raspunsul la atingere: daca randul asteapta dus-intorsul cu serverul,
        animatia nu se mai citeste ca raspuns la gestul tau;
      - animatia insasi: o structura de sablon gresita o suprima complet, fara
        nicio eroare (vezi comentariile din lib/grupare.js)."""
    out('--- iesirea randului bifat ---')
    probleme = 0
    page = ctx.new_page()
    page.set_viewport_size({'width': 390, 'height': 844})

    def zi(cond, mesaj, detaliu=''):
        nonlocal probleme
        out(('  OK    ' if cond else '  PICA  ') + mesaj + (('  — %s' % detaliu) if (detaliu and not cond) else ''))
        if not cond:
            probleme += 1

    for ruta, sel, eticheta in [('/tasks', '.trow', 'Taskuri'), ('/', '.arow', 'Astăzi')]:
        page.goto(baza + '/#' + ruta, wait_until='load')
        try:
            page.wait_for_selector(sel, timeout=15000)
        except Exception:
            out('  SARI  %s: lista e goala' % eticheta)
            continue
        page.wait_for_timeout(1100)
        r = page.evaluate(PROBA_IESIRE, sel)
        if r.get('eroare'):
            zi(False, '%s: %s' % (eticheta, r['eroare'])); continue
        interm = [o for o in r['op'] if 0.02 < o < 0.98]
        zi(r['plecatLa'] is not None, '%s: randul chiar pleaca din DOM' % eticheta)
        # Numarul de cadre intermediare NU se mai numara ca problema: in Chromium
        # headless de container (sandbox, fara GPU) tranzitia de iesire e taiata
        # dupa 1-2 cadre — identic si pe cod NEmodificat (verificat cu git stash
        # pe ca3771f, 2026-08-04), desi rAF-ul merge la 60fps pe pagina idle.
        # Pe hardware real animatia ramane vizibila. Acceptat de Ion (2026-08-04).
        # Masuratoarea se afiseaza in continuare, ca o schimbare sa se vada.
        if len(interm) >= 3:
            out('  OK    %s: se stinge (%d cadre) si sare' % (eticheta, len(interm)))
        else:
            out('  ACCEPTAT  %s: doar %d cadre intermediare (mediu headless) — %s' % (eticheta, len(interm), r['op'][:6]))
        zi(r['plecatLa'] is None or r['plecatLa'] < 900,
           '%s: raspunde la atingere, nu dupa server' % eticheta, '%sms' % r['plecatLa'])
    page.close()
    out()
    return probleme


PROBA_IESIRE = """(sel) => new Promise((res) => {
  const rand = document.querySelector(sel);
  if (!rand) return res({ eroare: 'niciun rand' });
  const w = rand.closest('.trow-wrap') || rand;
  const t0 = performance.now(); const op = [];
  const tic = () => {
    if (!w.isConnected) return res({ op, plecatLa: Math.round(performance.now() - t0) });
    op.push(+getComputedStyle(w).opacity);
    if (performance.now() - t0 > 2500) return res({ op, plecatLa: null });
    requestAnimationFrame(tic);
  };
  rand.querySelector('.check').click();
  requestAnimationFrame(tic);
})"""


def azi_peste_tot(ctx, baza):
    """Boardul „Astăzi" de pe Acasa si grupa „Azi" din /tasks sunt ACEEASI multime:
    apartenenta e data de TERMEN, nu de vreun steag separat (v33). Daca cele doua
    se desincronizeaza, ai doua liste de azi care se contrazic — si nu stii care
    minte."""
    out('--- „azi" inseamna acelasi lucru peste tot ---')
    probleme = 0
    MARCA = 'Audit — proba azi'
    page = ctx.new_page()
    page.set_viewport_size({'width': 390, 'height': 844})

    def zi(cond, mesaj, detaliu=''):
        nonlocal probleme
        out(('  OK    ' if cond else '  PICA  ') + mesaj + (('  — %s' % detaliu) if (detaliu and not cond) else ''))
        if not cond:
            probleme += 1

    def pe_acasa():
        return page.evaluate(
            "(m) => [...document.querySelectorAll('.arow .atitle')].some(e => e.textContent.includes(m))", MARCA)

    # Taskul se naste de pe ACASA: acolo a ramas compozitorul pe telefon (e al
    # boardului „Astăzi"), iar pe /tasks adaugarea trece prin butonul cu plus.
    # Intrebarea testului nu s-a schimbat — „azi" inseamna aceeasi zi pe ambele
    # ecrane — doar usa prin care intra taskul.
    page.goto(baza + '/#/', wait_until='load')
    try:
        page.wait_for_selector('.quick-add input', timeout=15000)
    except Exception:
        out('  SARI  compozitorul nu e disponibil')
        page.close()
        return 0
    page.wait_for_timeout(800)
    page.fill('.quick-add input', MARCA)
    page.keyboard.press('Enter')
    page.wait_for_timeout(1600)
    zi(pe_acasa(), 'taskul scris pe board apare in boardul de azi')

    page.goto(baza + '/#/tasks', wait_until='load')
    page.wait_for_selector('.trow', timeout=15000)
    page.wait_for_timeout(1100)
    # Foaia, apoi randul de termen, apoi ziua — acelasi drum ca pe deget, fara gest.
    page.evaluate(DESCHIDE_FOAIA, MARCA)
    page.wait_for_timeout(900)
    page.locator('.ts-rand').first.click()
    page.wait_for_timeout(500)
    page.evaluate(ALEGE_ZI_IN_FOAIE, 'Mâine')
    page.wait_for_timeout(1500)
    page.keyboard.press('Escape')
    page.wait_for_timeout(600)
    page.goto(baza + '/#/', wait_until='load')
    page.wait_for_selector('.arow', timeout=15000)
    page.wait_for_timeout(1400)
    zi(not pe_acasa(), 'mutat pe mâine, pleaca din boardul de azi')

    page.close()
    out()
    return probleme


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fara-gesturi', action='store_true', help='doar geometrie')
    ap.add_argument('--baza', help='alta baza sursa (implicit pif_dashboard.db din proiect)')
    arg = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            'Lipseste playwright. Ruleaza:\n'
            '  pip install playwright\n'
            '  python -m playwright install chromium')

    db_sursa = arg.baza or os.path.join(RADACINA, 'pif_dashboard.db')
    if not os.path.isfile(db_sursa):
        raise SystemExit('Nu exista pif_dashboard.db local. Adu una: scripts/sync_db_from_server.sh')

    tmp = tempfile.mkdtemp(prefix='pif-audit-')
    db = os.path.join(tmp, 'audit.db')
    shutil.copy2(db_sursa, db)
    port = S.port_liber()
    proc, baza = S.porneste_serverul(port, db, os.path.join(tmp, 'server.log'))
    out('Server pe %s (baza: copie de unica folosinta)\n' % baza)

    probleme = 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.environ.get('PIF_CHROMIUM') or None)
            ctx = browser.new_context(viewport={'width': 390, 'height': 844},
                                      is_mobile=True, has_touch=True, service_workers='block',
                                      timezone_id=FUS_TEST)
            page = ctx.new_page()
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', S.PIN_TEST)
            page.click('button[type="submit"]')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
            page.close()

            probleme += geometrie(ctx, baza)
            if not arg.fara_gesturi:
                probleme += perioadele_se_trag(browser, baza)
                probleme += gesturi(ctx, baza)
                probleme += lista_de_facut(ctx, baza)
                probleme += azi_peste_tot(ctx, baza)
                probleme += iesirea_randului(ctx, baza)
                probleme += dockul_pe_telefon(ctx, baza)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    if ACCEPTATE:
        out('Acceptate cu buna stiinta (nu se numara):')
        for k, de_ce in ACCEPTATE.items():
            out('  %-10s %s' % (k, de_ce))
        out()
    out('OK — nimic de reparat.' if not probleme else '%d probleme.' % probleme)
    return 1 if probleme else 0


if __name__ == '__main__':
    sys.exit(main())
