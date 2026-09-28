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

Porneste singur aplicatia (`banc.Aplicatia`), pe un port liber si pe o COPIE a bazei.
Iesire: 0 curat, 1 abatere, 2 instrumentul (vezi banc.py).

ASTEPTARILE SUNT PE CONDITIE (2026-09-28). Aici erau 57 de pauze fixe, ~66 s din cele
111 ale unei rulari. Fiecare a devenit una din trei: `aseaza(page)` dupa o schimbare
de interfata, `aseaza(page, server=True)` dupa o actiune care scrie pe server (vezi
`banc.LINISTE_SERVER`), sau a ramas pauza — acolo unde pauza E stimulul: cat tii
degetul apasat, cat de repede derulezi, cadrele dintre doua miscari.
"""

import argparse
import os
import sys
import time

# Numele lunilor din `DatePicker.svelte` — folosite ca sa stiu pe ce luna s-a
# deschis calendarul si cate apasari pe „luna urmatoare" mai trebuie.
LUNI_DP = ['Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie',
           'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie']

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADACINA, 'scripts'))

import banc  # noqa: E402
import smoke_ui as S  # noqa: E402
from banc import out  # noqa: E402

RUTE = [
    ('/', 'Acasa'),
    ('/projects', 'Proiecte'),
    ('/tasks', 'Taskuri'),
    ('/calendar', 'Calendar'),
    ('/departament', 'Departament'),
    ('/calculator', 'Calculator'),
]

ECRANE = [('iphone-se', 375, 667), ('android-mic', 360, 740), ('iphone-14', 390, 844)]


# `--tap-min` (44). Pana pe 2026-09-28 pragul de aici era 40, o toleranta scrisa
# doar in fisierul asta — `audit_ferestre` cerea 43, `audit_foaie` 44.
PRAG_TINTA = banc.TINTA_MIN

# Ce stim ca e sub prag CU BUNA STIINTA. Tine lista scurta si scrie MOTIVUL —
# altfel auditul devine o lista de exceptii si nu mai spune nimic.
ACCEPTATE = {
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


def rand(cond, mesaj, detaliu=''):
    """Un rand de raport; intoarce 1 daca e abatere, ca sa se poata aduna."""
    out('  %-8s %s%s' % ('OK' if cond else 'PICA', mesaj,
                         ('  — %s' % detaliu) if (detaliu and not cond) else ''))
    return 0 if cond else 1


def aseaza(page, server=False):
    """In locul unei pauze fixe: pana cand pagina a stat linistita (fara cereri in
    zbor, fara animatii finite, fara schelete) — mai mult dupa o scriere pe server,
    ca sa prinda si cererea trimisa intarziat."""
    banc.asteapta_linistea(page, liniste_ms=banc.LINISTE_SERVER if server else banc.LINISTE_UI)


def acceptat(s):
    return any(k in s for k in ACCEPTATE)


def geometrie(ctx, baza):
    """Depasiri / tinte / fonturi, pe fiecare ruta si fiecare latime."""
    probleme = 0
    for nume, w, h in ECRANE:
        out('--- %s (%dx%d) ---' % (nume, w, h))
        for ruta, eticheta in RUTE:
            page, col, blocata = S.deschide(ctx, baza + '/#' + ruta, w, h)
            # CONTINUTUL VENIT DIN RETEA TREBUIE SA FIE PE ECRAN INAINTE DE MASURA.
            # 600ms erau uneori de ajuns si uneori nu: benzile din Calendar vin din
            # `/api/calendar`, iar cand nu apucau sa se randeze pagina se masura
            # GOALA si trecea. `deschide` asteapta acum pana se intoarce ultima cerere
            # si se opreste ultima animatie — nici `networkidle` (500 ms de tacere
            # in plus la fiecare din cele 18 masuratori), nici o pauza ghicita.
            #
            # SI O PAGINA CARE NU S-A RANDAT NU TRECE. Pana pe 2026-09-28 colectorul
            # si semnalul „blocata" se aruncau, iar pe o pagina goala masuratoarea
            # gasea 0 depasiri, 0 tinte, 0 fonturi — adica OK.
            text = page.evaluate("() => (document.querySelector('#main-content') || document.body).innerText.trim().length")
            if blocata or text < 40 or col.curate():
                motiv = 'blocata pe schelet' if blocata else ('goala' if text < 40 else col.curate()[0][:120])
                out('  %-8s %-14s pagina nu s-a randat curat (%s) — nimic de masurat'
                    % ('PICA', eticheta, motiv))
                probleme += 1
                page.close()
                continue
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
    page = banc.pagina(ctx)
    erori = []
    page.on('pageerror', lambda e: erori.append(str(e).split('\n')[0]))
    page.goto(baza + '/#/', wait_until='load')
    try:
        page.wait_for_selector('.arow', timeout=15000)
    except Exception:
        out('  SARI  boardul „Astăzi" e gol — nimic de gesticulat')
        page.close()
        return 0
    aseaza(page)

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
        aseaza(page, server=True)
        dupa = titluri()
        if dupa[2] == inainte[0] and dupa[0] == inainte[1]:
            out('  OK    reordonare prin maner')
        else:
            out('  PICA  reordonare: %r -> %r' % (inainte[:3], dupa[:3])); probleme += 1
        page.reload(wait_until='load')
        page.wait_for_selector('.arow', timeout=15000)
        aseaza(page)
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

    # ALEGEREA ZILEI CHIAR S-A DESCHIS — si e ACELASI set ca in celelalte trei
    # liste.
    #
    # CE S-A SCHIMBAT (2026-08-17, handoff „Rafinare aplicație mobilă TORQA", P4):
    # gestul deschidea DIRECT calendarul (`.dp-pop.sheet`), printr-un `DatePicker`
    # ascuns intr-un invelis de 0×0 — deci pe „Astăzi" alegerea zilei era o grila de
    # luna, in /tasks era `SelectorZi` (Azi · Mâine · Alege · Scoate), iar in pagina
    # proiectului un formular de editare. Trei raspunsuri la aceeasi intrebare, pe
    # drumul aceluiasi gest. Acum toate patru deschid `components/FoaieTask.svelte`.
    # Verificarea NU s-a slabit: se cere in plus ca setul comun sa fie acolo, iar
    # calendarul rămâne verificat — doar c-a coborat o atingere mai jos, la „Alege".
    aseaza(page)
    optiuni = page.locator('.modal .sz-optiune')
    if optiuni.count() == 0:
        out('  PICA  glisare stanga: foaia cu zilele nu s-a deschis'); probleme += 1
    else:
        out('  OK    glisare stanga deschide alegerea zilei')
        # Setul comun, intreg: Azi · Mâine · Alege. Daca vreuna lipseste, foaia s-a
        # deschis dar nu e `SelectorZi` — adica exact divergenta pe care o reparam.
        etichete = [(optiuni.nth(i).text_content() or '').strip().lower()
                    for i in range(optiuni.count())]
        for cerut in ('azi', 'mâine', 'alege'):
            if not any(cerut in e for e in etichete):
                out('  PICA  foaia nu are „%s" (are: %s)' % (cerut, etichete)); probleme += 1
                break
        else:
            out('  OK    foaia poarta setul comun de zile (Azi · Mâine · Alege)')

        # CALENDARUL, ACOPERIT IN CONTINUARE: „Alege" trebuie sa-l deschida tot ca
        # SHEET, nu ca popup agatat de un declansator care pe telefon nu e randat.
        page.locator('.modal .sz-dp').first.click()
        aseaza(page)
        if page.locator('.dp-pop.sheet').count() == 0:
            out('  PICA  „Alege" nu deschide calendarul ca foaie'); probleme += 1
        else:
            out('  OK    „Alege" deschide calendarul ca foaie')
            page.keyboard.press('Escape')
            aseaza(page)

        # Si ziua aleasa chiar muta taskul: pica de pe boardul de azi. „Mâine" e o
        # zi din VIITOR prin definitie, deci nu mai e nevoie de plimbarea prin luni
        # de care avea nevoie grila (calendarul se deschidea pe luna TERMENULUI, iar
        # pe board taskurile sunt scadente azi sau restante — deci adesea o luna
        # trecuta, iar o zi din trecut lasa taskul pe board ca restant).
        maine = page.locator('.modal .sz-optiune', has_text='Mâine').first
        if maine.count():
            maine.click()
            aseaza(page, server=True)
            if titlu_inainte and titlu_inainte in (titluri() or []):
                out('  PICA  ziua aleasa n-a mutat taskul (%r)' % titlu_inainte); probleme += 1
            else:
                out('  OK    ziua aleasa muta taskul de pe board')

    # 3. glisare spre dreapta -> bifeaza, cu verdele de prag INAINTE de ridicare
    page.reload(wait_until='load')
    page.wait_for_selector('.arow', timeout=15000)
    aseaza(page)
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
    aseaza(page, server=True)

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
    page = banc.pagina(ctx)
    page.goto(baza + '/#/tasks', wait_until='load')
    try:
        page.wait_for_selector('.trow', timeout=15000)
    except Exception:
        out('  SARI  lista de taskuri e goala')
        page.close()
        return 0
    aseaza(page)

    capete = page.eval_on_selector_all('.grup-cap .grup-t', 'e => e.map(x => x.textContent.trim())')
    ORDINE = ['Restante', 'Azi', 'Mâine', 'Zilele astea', 'Mai târziu', 'Fără termen']
    idx = [ORDINE.index(x) for x in capete if x in ORDINE]
    probleme += rand(len(capete) >= 1, 'lista e grupata pe termen', capete)
    probleme += rand(idx == sorted(idx), 'grupele sunt in ordinea zilei', capete)
    probleme += rand('Fără termen' not in capete or capete[-1] == 'Fără termen',
       '„Fără termen" e ultima, nu prima', capete)

    # ADAUGAREA PE TELEFON TRECE PRIN BUTONUL MARE CU PLUS.
    #
    # Testul verifica alt contract decat pana acum, si nu fiindca s-a stricat
    # ceva: redesignul din 2026-08-08 cere O SINGURA cale de adaugare per ecran
    # — linia cu Enter pe desktop, butonul cu plus pe telefon. Compozitorul
    # inline de pe /tasks a plecat de pe latimea asta (pe „Astăzi" ramane, e al
    # boardului). Deci aici se verifica: butonul EXISTA, e o tinta adevarata, si
    # duce la locul din care poti pune si termenul din prima.
    #
    # CE S-A SCHIMBAT (2026-08-17, handoff „Rafinare aplicație mobilă TORQA"):
    # butonul deschidea un FORMULAR de patru campuri, cu bara de actiuni jos
    # („Anulează" / „Creează") — de aceea testul cauta `.modal-actions button`.
    # Acum deschide FOAIA DE ADAUGARE (`components/FoaieAdauga.svelte`): un singur
    # camp, iar crearea e PRIMUL RAND al listei („Creează «…»", `.fa-creeaza`),
    # fiindca acelasi camp e in acelasi timp si cautare — sub randul de creare stau
    # taskurile care exista deja, ca sa nu naști al doilea.
    # Verificarea nu s-a slabit, s-a mutat si a CRESCUT: pe langa „taskul s-a
    # creat" se verifica acum si ca foaia isi arata singura ce a inteles din text
    # (chipul de zi) — adica exact mecanismul nou care putea sa se strice tacut.
    MARCA = 'Audit — task de proba'
    n0 = page.eval_on_selector_all('.trow', 'e => e.length')
    probleme += rand(page.locator('.quick-add').count() == 0,
       'compozitorul inline nu se dubleaza cu butonul de adaugare')
    fab = page.locator('.dock-fab').first
    probleme += rand(fab.count() > 0 and fab.is_visible(), 'butonul mare cu plus e pe ecran')
    if fab.count() and fab.is_visible():
        c = fab.bounding_box()
        probleme += rand(c and c['width'] >= 44 and c['height'] >= 44,
           'butonul de adaugare e o tinta de deget', c)
        fab.click()
        aseaza(page)
        camp = page.locator('.fa-cauta input').first
        probleme += rand(camp.count() > 0, 'butonul deschide foaia de adaugare')
        if camp.count():
            # PARSERUL, INAINTE DE CREARE: ce se scrie in text trebuie sa apara pe
            # LINIA DE CONFIRMARE („Se planifică mâine · ● …", `.fa-linie`/`.fa-cheie`
            # — redesignul „1a" a inlocuit rândul de cipuri cu o propozitie), altfel
            # ziua ar fi extrasa in tacere si n-ai cum sa stii pe ce zi cade taskul.
            camp.fill('mâine ' + MARCA)
            aseaza(page)
            cheie = page.locator('.fa-linie .fa-cheie')
            probleme += rand(cheie.count() > 0, 'ziua scrisa in text apare pe linia de confirmare')
            if cheie.count():
                probleme += rand('mâine' in (page.locator('.fa-linie').first.text_content() or '').lower(),
                   'linia spune ziua inteleasa', page.locator('.fa-linie').first.text_content())
            # Titlul de pe randul de creare NU mai are ziua in el: ce a fost inteles
            # a plecat din titlu, altfel taskul s-ar numi „mâine revizie…".
            #
            # Se citeste `.fa-ct` — spanul TITLULUI —, nu textul intregului rand:
            # randul poarta si a doua linie „task nou · mâine · …" (`.fa-meta`), deci
            # textul lui CONTINE „mâine" cu bunastiinta. Prima versiune a testului se
            # uita la tot randul si picase pe exact asta.
            creeaza = page.locator('.fa-creeaza').first
            probleme += rand(creeaza.count() > 0, 'primul rand al listei e „Creează”')
            if creeaza.count():
                titlu_de_salvat = page.locator('.fa-creeaza .fa-ct').first.text_content() or ''
                probleme += rand('mâine' not in titlu_de_salvat.lower(),
                   'ziua a plecat din titlul care se va salva', titlu_de_salvat.strip())
                probleme += rand(MARCA.split('—')[-1].strip() in titlu_de_salvat,
                   'titlul pastreaza restul textului', titlu_de_salvat.strip())
                # Ziua rămâne vizibila pe rand, in a doua linie („task nou · mâine").
                probleme += rand('mâine' in (page.locator('.fa-creeaza .fa-meta').first.text_content() or '').lower(),
                   'randul de creare arata ziua in a doua linie')

            # Crearea propriu-zisa se face FARA zi, ca testul de glisare de mai jos
            # sa aiba ce muta: daca taskul s-ar naste deja pe mâine, verificarea
            # „ziua aleasa din foaie muta taskul" ar trece fara sa mute nimic.
            camp.fill(MARCA)
            aseaza(page)
            probleme += rand(page.locator('.fa-linie .fa-cheie').count() == 0,
               'fara zi in text nu apare cheie de zi pe linia de confirmare')
            # FOAIA NU-SI SCHIMBA INALTIMEA CAT TIMP SCRII.
            #
            # Ion: „cand tastez ceva in taskuri modalul isi schimba dimensiunea la
            # orice tastare (…) schimbarea se poate face exact in momentul cand vrei
            # sa adaugi ceva si ratezi." Asta e ce se masoara: inaltimea foii la trei
            # momente care schimbau CONTINUTUL — camp gol, text care filtreaza lista,
            # text care aduce si randul de chipuri. Toleranta 2px: sub-pixelii de
            # layout nu sunt o mutare pe care sa o simta degetul.
            def h_foaie():
                return page.evaluate("""() => {
                  const f = document.querySelector('.modal.sheet');
                  return f ? Math.round(f.getBoundingClientRect().height) : 0;
                }""")
            # `server=True`: continutul care o putea impinge vine din cautarea din
            # foaie (amanata 200 ms, apoi o cerere) — masuram dupa ce a sosit.
            camp.fill(''); aseaza(page, server=True); h0 = h_foaie()
            camp.fill(MARCA); aseaza(page, server=True); h1 = h_foaie()
            camp.fill('mâine ' + MARCA); aseaza(page, server=True); h2 = h_foaie()
            camp.fill('zzz' + MARCA); aseaza(page, server=True); h3 = h_foaie()
            stabila = max(h0, h1, h2, h3) - min(h0, h1, h2, h3) <= 2
            probleme += rand(stabila, 'foaia nu-si schimba inaltimea la tastare',
               f'inaltimi: {[h0, h1, h2, h3]}')

            camp.fill(MARCA)
            aseaza(page, server=True)
            page.locator('.fa-creeaza').first.click()
            aseaza(page, server=True)
            probleme += rand(page.eval_on_selector_all('.trow', 'e => e.length') == n0 + 1, 'taskul s-a creat')

    # ===== FOAIA DE LA APASARE LUNGA — CE CONTINE SI CE NU =====
    #
    # Lista e cea cerută de Ion pe 2026-08-17: „editeaza care redeschide modalul de
    # creare task cu textul introdus curent si selectat pentru editare, setare ora,
    # muta pe urmatoarea zi, alege ziua si sterg."
    # Se verifica si ABSENTELE, nu doar prezentele: „Bifează" si „Deschide" au fost
    # scoase pentru ca erau al doilea drum catre ceva care se face deja (glisarea la
    # dreapta, respectiv atingerea randului). Un meniu creste usor si tacit — daca
    # nimeni nu cere sa NU fie acolo, se intorc la prima ocazie.
    r = page.evaluate(CAUTA_RAND, MARCA)
    if r:
        cx, cy = r[0] + r[2] * 0.5, r[1] + r[3] / 2
        # Apasare lunga: peste `APASARE_MENIU` (420ms), fara sa miste degetul.
        page.evaluate("""([x, y]) => {
          const el = document.elementFromPoint(x, y);
          const ev = (t) => el.dispatchEvent(new PointerEvent(t, {
            pointerId: 9, pointerType: 'touch', isPrimary: true,
            clientX: x, clientY: y, bubbles: true, cancelable: true }));
          ev('pointerdown');
          window.__ridica = () => ev('pointerup');
        }""", [cx, cy])
        page.wait_for_timeout(700)          # degetul TINUT — stimulul, nu o asteptare
        page.evaluate('() => window.__ridica && window.__ridica()')
        aseaza(page)
        randuri_foaie = [t.strip() for t in page.eval_on_selector_all(
            '.modal .ft-rand', 'e => e.map(x => x.textContent)')]
        text_foaie = ' | '.join(randuri_foaie)
        probleme += rand(len(randuri_foaie) > 0, 'apasarea lunga deschide foaia de actiuni', text_foaie)
        if randuri_foaie:
            # Redesign „hold·1a": taskul e REPERUL sus, iar „Mută pe mâine" + „Alege
            # ziua" (doua randuri) s-au strans intr-un SINGUR rand de zile
            # (`SelectorZi`, „Replanifică") — un gest, nu doua ecrane.
            ref = page.query_selector('.modal .ft-referinta')
            probleme += rand(ref is not None, 'foaia are taskul ca reper sus',
               ref.text_content() if ref else 'lipseste .ft-referinta')
            pastile = [t.strip() for t in page.eval_on_selector_all(
                '.modal .ft-replan .sz-optiune', 'e => e.map(x => x.textContent)')]
            for cerut in ('Azi', 'Mâine', 'Alege'):
                probleme += rand(any(cerut in x for x in pastile),
                   'replanificarea (un rand) are „%s"' % cerut, ' | '.join(pastile))
            for cerut in ('Editează', 'Șterge'):
                probleme += rand(any(cerut in x for x in randuri_foaie), 'foaia are „%s"' % cerut, text_foaie)
            # ABSENTE: „Mută pe mâine"/„Alege ziua" ca RANDURI separate au disparut
            # (sunt pastile acum); „Bifează"/„Deschide" n-au fost niciodata aici.
            for interzis in ('Bifează', 'Redeschide', 'Deschide', 'Mută pe mâine', 'Alege ziua'):
                # „Deschide" apare ca subsir in „Redeschide", deci se compara pe
                # randul intreg, nu pe text lipit.
                probleme += rand(not any(x.strip().startswith(interzis) for x in randuri_foaie),
                   'foaia NU mai are randul „%s"' % interzis, text_foaie)

            # „Editează" duce in foaia de adaugare, cu titlul CURENT si SELECTAT.
            page.locator('.modal .ft-rand', has_text='Editează').first.click()
            aseaza(page)
            # Focusul vine DUPA ce s-a asezat foaia (un temporizator in FoaieAdauga,
            # nu o animatie) — deci se asteapta el anume.
            try:
                page.wait_for_function(
                    "() => document.activeElement === document.querySelector('.fa-cauta input')",
                    timeout=2000)
            except Exception:
                pass
            camp_ed = page.locator('.fa-cauta input').first
            probleme += rand(camp_ed.count() > 0, '„Editează" deschide foaia de adaugare')
            if camp_ed.count():
                stare = page.evaluate("""() => {
                  const i = document.querySelector('.fa-cauta input');
                  return { val: i ? i.value : null,
                           focus: document.activeElement === i,
                           sel: i ? (i.selectionEnd - i.selectionStart) : 0 };
                }""")
                probleme += rand(stare['val'] == MARCA, 'campul porneste cu titlul curent', stare)
                probleme += rand(stare['focus'], 'campul are focusul (la editare tastatura E scopul)', stare)
                probleme += rand(stare['sel'] == len(MARCA), 'textul e SELECTAT, ca sa se poata rescrie', stare)
                probleme += rand(page.locator('.fa-creeaza').first.text_content().strip().startswith('Salvează'),
                   'primul rand e „Salvează", nu „Creează"',
                   page.locator('.fa-creeaza').first.text_content())
                probleme += rand(page.locator('.fa-cap').count() == 0,
                   'la editare nu se mai arata „EXISTĂ DEJA" (ar planifica alt task)')
            page.keyboard.press('Escape')
            aseaza(page)

    # Glisarea spre stanga deschide FOAIA DE DETALII (pasi + nota).
    # Replanificarea se face din foaia de actiuni (long-press), nu de aici.
    r = page.evaluate(CAUTA_RAND, MARCA)
    if r:
        cx, cy = r[0] + r[2] * 0.5, r[1] + r[3] / 2
        page.evaluate(TRAGE, [cx, cy, [[cx - d, cy] for d in (30, 100, 180, 240)], 5])
        aseaza(page)
        probleme += rand(page.locator('.dt-referinta').count() > 0,
           'glisarea deschide foaia de detalii')
        page.keyboard.press('Escape')
        aseaza(page)
        page.evaluate(APASA_LUNG_RAND, MARCA)
        page.wait_for_timeout(700)          # degetul TINUT — stimulul
        page.evaluate('() => window.__ridica && window.__ridica()')
        aseaza(page)
        page.evaluate(ALEGE_ZI_IN_FOAIE, 'Mâine')
        aseaza(page, server=True)
        page.keyboard.press('Escape')
        aseaza(page)
        grup = page.evaluate(GRUPUL_LUI, MARCA)
        probleme += rand(grup == 'Mâine', 'ziua aleasa din foaia de actiuni muta taskul', grup)

    # bifare + anulare
    page.reload(wait_until='load')
    page.wait_for_selector('.trow', timeout=15000)
    aseaza(page)
    n1 = page.eval_on_selector_all('.trow', 'e => e.length')
    page.evaluate(BIFEAZA, MARCA)
    aseaza(page, server=True)
    probleme += rand(page.eval_on_selector_all('.trow', 'e => e.length') == n1 - 1, 'taskul bifat pleaca din lista')
    anuleaza = page.locator('.toast-action', has_text='Anulează')
    probleme += rand(anuleaza.count() > 0, 'bifarea ofera „Anulează"')
    if anuleaza.count():
        anuleaza.first.click()
        aseaza(page, server=True)
        probleme += rand(page.eval_on_selector_all('.trow', 'e => e.length') == n1, '„Anulează" aduce taskul inapoi')

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
  const b = [...document.querySelectorAll('.ft-replan .sz-optiune')].find(x => x.textContent.includes(eticheta));
  if (!b) return false;
  b.click();
  return true;
}"""

# Declanseaza apasarea lunga pe un rand de task (deschide FoaieTask).
# Dupa apel, asteapta 700ms si cheama window.__ridica() ca sa ridici degetul.
APASA_LUNG_RAND = """(marca) => {
  const r = [...document.querySelectorAll('.trow')].find(x => x.textContent.includes(marca));
  if (!r) return false;
  r.scrollIntoView({ block: 'center' });
  const box = r.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const tinta = document.elementFromPoint(x, y);
  const ev = (type) => tinta.dispatchEvent(
    new PointerEvent(type, { pointerId: 1, pointerType: 'touch',
      clientX: x, clientY: y, bubbles: true, cancelable: true }));
  ev('pointerdown');
  window.__ridica = () => ev('pointerup');
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
    """Dock-ul pe telefon: patru tinte, mai mari, si ascundere la derulare.

    De ce e verificat. Ascunderea la derulare s-a rupt O DATA fara nicio eroare:
    efectul care readuce dock-ul la schimbarea rutei chema o functie care CITEA
    starea de ascundere, deci efectul devenea dependent de ea si o stingea imediat
    ce se aprindea. Build verde, zero exceptii, dock care pur si simplu nu se
    ascundea. Asta se prinde doar deruland si masurand.

    Si numarul de tinte conteaza: daca cineva readauga rute in `PE_TELEFON` fara sa
    scada marimea, dock-ul iese din ecran. PATRU: Acasa, Taskuri, Calendar + „Mai
    mult". La 56px de tinta incapeau cinci; patru incap cu si mai mult aer.
    (Al patrulea slot a fost al Planificatorului pana pe 2026-08-24, cand a coborat
    in foaie; pe 2026-08-26 pagina a plecat cu totul.)"""
    out('--- dock pe telefon ---')
    probleme = 0
    page = banc.pagina(ctx)

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
    aseaza(page)

    s0 = page.evaluate(STARE)
    if not s0:
        probleme += rand(False, 'dock-ul exista pe telefon')
        page.close()
        return probleme

    probleme += rand(s0['n'] == 4, 'patru tinte pe telefon', 'sunt %d' % s0['n'])
    probleme += rand(s0['tinta'] >= 52, 'tintele folosesc spatiul castigat (>=52px)', '%dpx' % s0['tinta'])
    probleme += rand(not s0['depaseste'], 'dock-ul nu iese din ecran')

    inaltime = page.evaluate('document.documentElement.scrollHeight')
    if inaltime <= 844 + 40:
        probleme += rand(False, 'pagina de test poate fi derulata', 'scrollHeight=%d' % inaltime)
        page.close()
        return probleme

    def deruleaza(pana, pas=60):
        cur = page.evaluate('window.scrollY')
        d = 1 if pana > cur else -1
        while (d > 0 and cur < pana) or (d < 0 and cur > pana):
            cur = min(pana, cur + pas) if d > 0 else max(pana, cur - pas)
            page.evaluate('window.scrollTo(0, %d)' % cur)
            page.wait_for_timeout(55)       # viteza derularii — stimulul
        aseaza(page)

    # CONTRACT INTORS PE 2026-08-10 (Ion): dock-ul pe telefon e FIX si mereu la
    # vedere — a rasturnat propria cerinta din 2026-07-31 („urmareste derularea ca
    # bara de adresa"). Cu etichetele sub iconite dockul e harta aplicatiei, iar o
    # harta care fuge de sub deget e mai scumpa decat ecranul castigat.
    #
    # AURORA (2026-08-23) a schimbat UN singur lucru din contractul asta: dockul
    # nu mai e LIPIT de fundul ecranului, ci PLUTESTE la 6px + safe-area. Restul e
    # neatins, si tocmai de aceea se verifica in continuare: patru tinte, peste
    # 52px, nu iese din ecran, si derularea NU-l misca — nici in jos, nici in varf.
    # Ce era „lipit la 0" a devenit „desprins, dar putin": intre 4 si 20px de gol,
    # cu safe-area inclusa. Plafonul e acolo ca sa prinda regresia inversa — un
    # dock care incepe iar sa fuga in sus de sub deget.
    deruleaza(500)
    jos = page.evaluate(STARE)
    probleme += rand(not jos['ascuns'], 'coborand prin pagina, dock-ul RAMANE (contract 2026-08-10)')
    probleme += rand(not jos['subEcran'], 'sta pe ecran, nu sub el')
    gol = page.evaluate("""() => {
      const r = document.querySelector('.dock').getBoundingClientRect();
      return Math.round(window.innerHeight - r.bottom); }""")
    probleme += rand(4 <= gol <= 20, 'pluteste deasupra marginii de jos (AURORA)', 'gol de %dpx' % gol)

    deruleaza(0)
    varf = page.evaluate(STARE)
    probleme += rand(not varf['ascuns'], 'si in varful paginii sta afara')

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
        page.wait_for_timeout(120)          # zabovirea inainte de ridicare — stimulul
        page.mouse.up()
        aseaza(page, server=True)

    for eticheta, tactil, pauza in (('mouse', False, 0), ('deget', True, 420)):
        ctx = banc.context(browser, 'telefon' if tactil else 'desktop')
        page = banc.autentifica(ctx, baza)
        cdp = banc.cdp(page) if tactil else None
        erori = []
        page.on('pageerror', lambda e: erori.append(str(e).split('\n')[0]))
        try:
            page.goto(baza + '/#/calendar', wait_until='load')
            # PERIOADA DE TRAS O PUNE AUDITUL (`seamana`), deci o grila fara benzi
            # nu mai e „nimic de tras" — e un calendar care nu randeaza ce are.
            # Pana pe 2026-09-28 aici era SARI: proba se sprijinea pe copia locala a
            # bazei, iar cand ultima ei perioada (18.08) a iesit din fereastra,
            # sectiunea a sarit o luna intreaga, in tacere, dupa 2 x 15 s de asteptare.
            try:
                page.wait_for_selector('.banda[data-perioada]', timeout=15000)
            except Exception:
                out('  PICA  %s: nicio banda in calendar, desi auditul a pus una' % eticheta)
                probleme += 1
                ctx.close()
                continue
            aseaza(page)

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
                    out('  PICA  deget: nicio banda pe un proiect deschis, desi auditul a pus una')
                    probleme += 1
                    ctx.close()
                    continue
                ord0 = [z[0] for z in zile]
                in0 = stare(page, b0[0])

                # CENTRUL BENZII SE CITESTE INAINTE DE FIECARE ATINGERE.
                #
                # Pe telefon banda are 4px inaltime (`min-height: 4px`, pasul
                # `--h-banda: 6px`), deci o deplasare de layout de un rand o scoate
                # complet de sub deget. Si grila se aseaza inca dupa cele 700ms de
                # asteptare: masurat pe 2026-08-26, intr-o rulare din patru, centrul
                # citit la masurare era y=278,6, iar cel citit inainte de gest —
                # y=269. Doua atingeri trimise la 278,6 cadeau amandoua pe `.zi` de
                # dedesubt, nu pe banda.
                # Se vedea doar la a doua: (c) pica fiindca gestul chiar n-avea ce
                # apuca, dar (b) — „o glisare simpla nu muta nimic" — TRECEA, fiindca
                # o glisare pe o zi goala intr-adevar nu muta nimic. O proba care
                # se confirma din cauza ca a ratat tinta e mai rea decat una care
                # pica: nu se vede ca n-a verificat.
                # `harta` zilelor se reciteste din acelasi motiv, si in acelasi loc.
                def centru_benzii():
                    r = page.evaluate(
                        """(id) => { const el = document.querySelector('.banda[data-perioada="' + id + '"]');
                             if (!el) return null; const q = el.getBoundingClientRect();
                             return [q.left + q.width / 2, q.top + q.height / 2,
                                     Math.round(q.left), Math.round(q.top),
                                     Math.round(q.width), Math.round(q.height)]; }""", b0[0])
                    return r

                # (b) O GLISARE SCURTA, FARA APASARE, RAMANE DERULARE. Proba
                #     asta e cea care face gestul acceptabil: daca ea pica,
                #     lista nu se mai poate derula cu degetul peste benzi.
                pb = centru_benzii()
                if not pb:
                    out('  SARI  deget: banda a disparut din grila inainte de gest')
                    ctx.close()
                    continue
                cdp.send('Input.dispatchTouchEvent', dict(
                    type='touchStart',
                    touchPoints=[dict(x=pb[0], y=pb[1], radiusX=6, radiusY=6, force=1)]))
                for k in range(1, 5):
                    cdp.send('Input.dispatchTouchEvent', dict(
                        type='touchMove',
                        touchPoints=[dict(x=pb[0], y=pb[1] + k * 12, radiusX=6, radiusY=6, force=1)]))
                cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                # `server=True`: daca glisarea ar muta (gresit) perioada, scrierea
                # trebuie sa apuce sa ajunga pe server inainte sa intrebam.
                aseaza(page, server=True)
                if stare(page, b0[0]) == in0:
                    out('  OK    deget: glisarea fara apasare lunga nu muta nimic')
                else:
                    out('  PICA  deget: o glisare simpla a mutat perioada')
                    probleme += 1

                # (c) APASAREA LUNGA + TRAGEREA MUTA. Si banda se ridica, si
                #     manerele devin tinte de deget — semnalul care spune ca
                #     gestul a prins, pe un ecran care n-are cursor.
                t0 = ord0[min((ord0.index(in0[0]) if in0[0] in ord0 else 0) + 9, len(ord0) - 1)]
                harta = {z[0]: (z[1], z[2]) for z in page.eval_on_selector_all(
                    '.zi[data-zi]',
                    'e => e.map(z => { const r = z.getBoundingClientRect();'
                    ' return [z.dataset.zi, r.left + r.width / 2, r.top + r.height / 2] })')}
                pc = centru_benzii()
                if not pc or t0 not in harta:
                    out('  SARI  deget: banda sau ziua-tinta au disparut inainte de gest')
                    ctx.close()
                    continue
                cdp.send('Input.dispatchTouchEvent', dict(
                    type='touchStart',
                    touchPoints=[dict(x=pc[0], y=pc[1], radiusX=6, radiusY=6, force=1)]))
                # APASAREA LUNGA SE ASTEAPTA PE CONDITIE, NU PE CEAS.
                #
                # Aici a fost un `wait_for_timeout` fix: intai 450ms, urcat la 700
                # (25cab389) fiindca „nu ajungea sub sarcina". Numarul nu era
                # problema — masurat, cand gestul PORNESTE el porneste in ~337ms,
                # iar cand nu porneste nu-l scot nici 3000. Cauza era geometria
                # veche (vezi `centru_benzii` mai sus), reparata acum.
                # Asteptarea ramane totusi pe CONDITIE, nu pe ceas: `APASARE_LUNGA`
                # e 300ms masurate de ceasul PAGINII, iar cand firul ei principal e
                # blocat, ceasul probei si al paginii nu mai sunt acelasi lucru.
                # `polling=100`, nu implicitul `raf`: sub sarcina, cadrele sunt exact
                # ce intarzie. Bugetul de 3s ramane o afirmatie — daca gestul nu
                # porneste pana atunci, chiar nu porneste.
                _t = time.time()
                try:
                    page.wait_for_function(
                        "() => !!document.querySelector('.banda.se-trage')",
                        timeout=3000, polling=100)
                except Exception:
                    pass
                asteptat = int((time.time() - _t) * 1000)
                ridicata = page.evaluate(
                    '''() => { const b = document.querySelector('.banda.se-trage');
                         if (!b) return null;
                         const m = b.querySelector('.maner');
                         return { umbra: getComputedStyle(b).boxShadow !== 'none',
                                  maner: m ? Math.round(parseFloat(getComputedStyle(m).width)) : 0 }; }''')
                if not ridicata:
                    # Cine a primit atingerea, si unde e banda ACUM. Fara asta,
                    # „nu a pornit gestul" nu deosebeste „codul e stricat" de
                    # „proba a atins alaturi" — si prima oara chiar a fost a doua.
                    unde = page.evaluate(
                        """(pt) => { const sub = document.elementFromPoint(pt[0], pt[1]);
                             return sub ? (sub.className || sub.tagName) : null; }""",
                        [pc[0], pc[1]])
                    out('  PICA  deget: apasarea lunga nu a pornit gestul (%dms) — '
                        'atins (%d,%d), banda la [%d,%d %dx%d], sub deget: %s'
                        % (asteptat, pc[0], pc[1], pc[2], pc[3], pc[4], pc[5], unde))
                    probleme += 1
                else:
                    if ridicata['umbra']:
                        # Numarul e in raport cu intentie: el arata cat de departe
                        # sta gestul de pragul fix care era aici (700ms).
                        out('  OK    deget: banda se ridica la apucare (%dms)' % asteptat)
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
                        touchPoints=[dict(x=pc[0] + (harta[t0][0] - pc[0]) * k / 8,
                                          y=pc[1] + (harta[t0][1] - pc[1]) * k / 8,
                                          radiusX=6, radiusY=6, force=1)]))
                    page.wait_for_timeout(16)       # un cadru intre miscari — stimulul
                cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                aseaza(page, server=True)
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
                out('  PICA  %s: nicio banda pe un proiect deschis, desi auditul a pus una' % eticheta)
                probleme += 1
                ctx.close()
                continue
            pid, bx, by = b[0], b[1], b[2]
            inainte = stare(page, pid)
            # O zi din aceeasi fereastra, indeajuns de departe cat sa nu fie ea
            # insasi; +9 sare peste o saptamana, deci si peste alt rand din grila.
            ordonate = [z[0] for z in zile]
            i = ordonate.index(inainte[0]) if inainte[0] in ordonate else 0
            tinta = ordonate[min(i + 9, len(ordonate) - 1)]
            trage_mouse(page, cdp, bx, by, harta[tinta][0], harta[tinta][1], pauza)
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
            # ASTEPTAREA ISI SPUNE MOTIVUL. Timeoutul gol arunca un traceback de
            # Playwright in raportul portii — adica un verdict fara nicio informatie
            # despre ce s-a intamplat. S-a si intamplat, pe 2026-08-24, cand masina
            # rula in paralel serverul de previzualizare, mai multe Chromium si sapte
            # agenti: banda n-a reaparut in 15s, si tot ce s-a vazut a fost stiva.
            # Acum spune CE lipseste si CU CE date, si trece mai departe ca abatere,
            # nu ca prabusire — restul probelor tot merita rulate.
            try:
                page.wait_for_selector('.banda[data-perioada]', timeout=15000)
            except Exception:
                cate = page.eval_on_selector_all('.banda', 'e => e.length')
                out('  PICA  %s: banda n-a reaparut dupa reload — %d benzi in grila, '
                    'perioada mutata e %s' % (eticheta, cate, dupa))
                probleme += 1
                continue
            aseaza(page)
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
                trage_mouse(page, cdp, mx, my, h2[capat][0], h2[capat][1], pauza)
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
    page = banc.pagina(ctx)

    for ruta, sel, eticheta in [('/tasks', '.trow', 'Taskuri'), ('/', '.arow', 'Astăzi')]:
        page.goto(baza + '/#' + ruta, wait_until='load')
        try:
            page.wait_for_selector(sel, timeout=15000)
        except Exception:
            out('  SARI  %s: lista e goala' % eticheta)
            continue
        aseaza(page)
        r = page.evaluate(PROBA_IESIRE, sel)
        if r.get('eroare'):
            probleme += rand(False, '%s: %s' % (eticheta, r['eroare'])); continue
        interm = [o for o in r['op'] if 0.02 < o < 0.98]
        probleme += rand(r['plecatLa'] is not None, '%s: randul chiar pleaca din DOM' % eticheta)
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
        probleme += rand(r['plecatLa'] is None or r['plecatLa'] < 900,
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
    page = banc.pagina(ctx)

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
    aseaza(page)
    page.fill('.quick-add input', MARCA)
    page.keyboard.press('Enter')
    aseaza(page, server=True)
    probleme += rand(pe_acasa(), 'taskul scris pe board apare in boardul de azi')

    page.goto(baza + '/#/tasks', wait_until='load')
    page.wait_for_selector('.trow', timeout=15000)
    aseaza(page)
    # Foaia de actiuni (long-press), apoi „Mâine" din SelectorZi.
    page.evaluate(APASA_LUNG_RAND, MARCA)
    page.wait_for_timeout(700)              # degetul TINUT — stimulul
    page.evaluate('() => window.__ridica && window.__ridica()')
    aseaza(page)
    page.evaluate(ALEGE_ZI_IN_FOAIE, 'Mâine')
    aseaza(page, server=True)
    page.keyboard.press('Escape')
    aseaza(page)
    page.goto(baza + '/#/', wait_until='load')
    page.wait_for_selector('.arow', timeout=15000)
    aseaza(page)
    probleme += rand(not pe_acasa(), 'mutat pe mâine, pleaca din boardul de azi')

    page.close()
    out()
    return probleme


def seamana(db):
    """Datele de care depind probele, puse de audit — nu imprumutate din copia locala.

    O perioada de trei zile pe un proiect DESCHIS, in lunea din AL DOILEA rand al
    grilei. Grila arata saptamanile lunii curente (4–6 randuri, de la lunea saptamanii
    in care incepe luna) — nu cele 49 de zile pe care le cere API-ul —, deci „lunea
    viitoare" iesea din ea in ultima saptamana a lunii. Din al doilea rand raman mereu
    peste 9 zile vizibile dupa perioada, cat cere mutarea de mai jos (+9).
    Si trei taskuri de munca scadente azi, ca boardul „Astăzi" sa aiba ce reordona si
    pe ce gesticula.

    DE CE: pana pe 2026-09-28 probele citeau ce gaseau in `pif_dashboard.db`. Copia
    locala a imbatranit (ultima perioada: 18.08), calendarul de azi n-a mai avut nicio
    banda, si proba perioadelor — cea care prinsese tragerea rupta — a SARIT o luna,
    in tacere. SARI nu se numara, deci raportul era verde."""
    import sqlite3
    import uuid
    from datetime import date, datetime, timedelta
    acum = datetime.now().isoformat()
    azi = date.today()
    luna = azi.replace(day=1)
    luni = luna - timedelta(days=luna.weekday()) + timedelta(days=7)
    c = sqlite3.connect(db)
    try:
        pid = str(uuid.uuid4())
        c.execute("INSERT INTO proiecte (id, tip, nume, client, status, created_at, updated_at) "
                  "VALUES (?, 'PIF', 'Audit — perioade', 'Audit', 'pregatire', ?, ?)", (pid, acum, acum))
        c.execute("INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit, locatie, faza, "
                  "eticheta, ordine, created_at) VALUES (?, ?, ?, ?, 'site', 'implementare', '', 0, ?)",
                  (str(uuid.uuid4()), pid, luni.isoformat(), (luni + timedelta(days=2)).isoformat(), acum))
        for i in range(1, 4):
            c.execute("INSERT INTO global_tasks (id, titlu, status, categorie, sfera, data_scadenta, "
                      "created_at, updated_at) VALUES (?, ?, 'to_do', 'General', 'munca', ?, ?, ?)",
                      (str(uuid.uuid4()), 'Audit — rand %d' % i, azi.isoformat(), acum, acum))
        c.commit()
    finally:
        c.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fara-gesturi', action='store_true', help='doar geometrie')
    banc.argumente(ap, vizibil=False)
    arg = ap.parse_args()
    sync_playwright = banc.playwright()

    probleme = 0
    with banc.Aplicatia(sursa=arg.baza, seamana=seamana, prefix='pif-audit-') as app:
        out('Server pe %s (baza: copie de unica folosinta)\n' % app.baza)
        with sync_playwright() as pw:
            browser = banc.browserul(pw)
            ctx = banc.context(browser, 'telefon')
            banc.autentifica(ctx, app.baza, inchide=True)

            probleme += geometrie(ctx, app.baza)
            if not arg.fara_gesturi:
                probleme += perioadele_se_trag(browser, app.baza)
                probleme += gesturi(ctx, app.baza)
                probleme += lista_de_facut(ctx, app.baza)
                probleme += azi_peste_tot(ctx, app.baza)
                probleme += iesirea_randului(ctx, app.baza)
                probleme += dockul_pe_telefon(ctx, app.baza)
            browser.close()
    return banc.incheie(probleme, acceptate=ACCEPTATE)


if __name__ == '__main__':
    sys.exit(banc.ruleaza(main))
