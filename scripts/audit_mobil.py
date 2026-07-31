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
  - de facut     gruparea pe termen, adaugarea cu zi, mutarea din gest, „Anulează"
  - „azi"        boardul de pe Acasa si grupa „Azi" din /tasks sunt aceeasi multime
  - iesire       randul bifat se stinge si pleaca imediat, nu dupa server

TREI CAPCANE DE MASURARE, toate tratate aici — fara ele raportul minte:
  1. `pointer-events: none` inseamna ca elementul NU e o tinta (benzile din
     Calendar sunt decor; celula e tinta). Altfel ar aparea zeci de false alarme.
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
import os
import shutil
import sys
import tempfile

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

    # 2. glisare spre stanga -> panoul de actiuni
    r = page.eval_on_selector('.arow', 'e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height] }')
    cx, cy = r[0] + r[2] * 0.6, r[1] + r[3] / 2
    page.evaluate(TRAGE, [cx, cy, [[cx - d, cy] for d in (30, 80, 130, 150)], 2])
    page.wait_for_timeout(600)
    tx = page.eval_on_selector('.arow .gl-fata', 'e => getComputedStyle(e).transform')
    if tx == 'none' or '-1' not in tx.replace(' ', ''):
        out('  PICA  glisare stanga: randul nu s-a deplasat (%s)' % tx); probleme += 1
    else:
        out('  OK    glisare stanga deschide panoul')

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

    # adaugare cu zi
    MARCA = 'Audit — task de proba'
    n0 = page.eval_on_selector_all('.trow', 'e => e.length')
    page.fill('.quick-add input', MARCA)
    page.wait_for_timeout(400)
    chip = page.locator('.qa-chip', has_text='Azi').first
    zi(chip.is_visible(), 'chipurile de zi apar cat timp scrii')
    if chip.is_visible():
        chip.click()
        page.wait_for_timeout(1400)
        grup = page.evaluate(GRUPUL_LUI, MARCA)
        zi(page.eval_on_selector_all('.trow', 'e => e.length') == n0 + 1, 'taskul s-a creat')
        zi(grup == 'Azi', 'taskul nou aterizeaza direct in ziua aleasa', grup)
        zi(page.input_value('.quick-add input') == '', 'campul ramane gol si focusat pentru urmatorul')

    # mutare din gest
    r = page.evaluate(CAUTA_RAND, MARCA)
    if r:
        cx, cy = r[0] + r[2] * 0.5, r[1] + r[3] / 2
        page.evaluate(TRAGE, [cx, cy, [[cx - d, cy] for d in (30, 100, 180, 240)], 5])
        page.wait_for_timeout(600)
        page.evaluate(APASA_IN_RAND, [MARCA, 'Mâine'])
        page.wait_for_timeout(1400)
        grup = page.evaluate(GRUPUL_LUI, MARCA)
        zi(grup == 'Mâine', 'glisarea muta taskul in alta zi', grup)
        zi(page.locator('.toast-action', has_text='Anulează').count() > 0,
           'mutarea se poate anula')

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

APASA_IN_RAND = """([marca, eticheta]) => {
  const row = [...document.querySelectorAll('.trow')].find(x => x.textContent.includes(marca));
  if (!row) return false;
  const b = [...row.querySelectorAll('.gl-actiuni .glb')].find(x => x.textContent.includes(eticheta));
  if (!b) return false;
  b.click();
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
    page.wait_for_timeout(1500)

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

    deruleaza(500)
    jos = page.evaluate(STARE)
    zi(jos['ascuns'], 'coborand prin pagina, dock-ul pleaca')
    # Nu e de ajuns sa primeasca clasa: pe telefon manerul e ascuns, deci daca
    # deplasarea e cea de desktop ramane o dunga de dock peste continut.
    zi(jos['subEcran'], 'plecat inseamna COMPLET sub ecran, nu o dunga')

    deruleaza(340)
    sus = page.evaluate(STARE)
    zi(not sus['ascuns'], 'urcand, revine imediat')

    deruleaza(0)
    varf = page.evaluate(STARE)
    zi(not varf['ascuns'], 'in varful paginii sta afara')

    page.close()
    return probleme


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
        zi(len(interm) >= 3, '%s: se stinge (%d cadre), nu sare' % (eticheta, len(interm)), r['op'][:6])
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

    page.goto(baza + '/#/tasks', wait_until='load')
    try:
        page.wait_for_selector('.quick-add input', timeout=15000)
    except Exception:
        out('  SARI  compozitorul nu e disponibil')
        page.close()
        return 0
    page.wait_for_timeout(800)
    page.fill('.quick-add input', MARCA)
    page.wait_for_timeout(400)
    page.locator('.qa-chip', has_text='Azi').first.click()
    page.wait_for_timeout(1400)

    page.goto(baza + '/#/', wait_until='load')
    page.wait_for_selector('.arow', timeout=15000)
    page.wait_for_timeout(1400)
    zi(pe_acasa(), 'taskul pus pe „Azi" apare si in boardul de pe Acasa')

    page.goto(baza + '/#/tasks', wait_until='load')
    page.wait_for_selector('.trow', timeout=15000)
    page.wait_for_timeout(1100)
    page.evaluate(APASA_IN_RAND, [MARCA, 'Mâine'])
    page.wait_for_timeout(1500)
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
