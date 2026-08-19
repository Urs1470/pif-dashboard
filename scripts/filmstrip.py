#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filmul interactiunilor: o plansa de cadre per gest, pe telefon.

De ce exista, langa celelalte audituri: ele masoara NUMERE — cate cadre s-au
pierdut, cati px/s are foaia, ce tinta e prea mica. Niciunul nu se uita. Iar
modul de esec care ramane dupa ele nu e „prea lent", ci „arata prost": lucrul
care porneste prea tarziu, cel care se opreste sec in loc sa aseze, cel care
apare din nimic in loc sa creasca din locul apasat, doua lucruri care se misca
in acelasi timp si se incurca.

Astea nu se prind masurand, se prind privind. Pana acum singurul care privea era
Ion, pe telefonul lui, gest cu gest — adica bucla de feedback trecea printr-un om
si costa un drum dus-intors pentru fiecare corectie.

Ce face: joaca fiecare interactiune cu ATINGERE ADEVARATA (`Input.dispatchTouchEvent`,
ca `audit_foaie` si `audit_mobil` — mouse-ul emite `pointerType:'mouse'` si o parte
din gesturi nici nu pornesc), inregistreaza ecranul prin `Page.startScreencast`
(~53 cadre/s, masurat), arunca cadrele identice si lipeste ce ramane intr-o
singura plansa PNG, cu momentul fiecarui cadru scris sub el.

Rezultatul: `docs/filmstrip/<scena>.png` + un `index.html` de rasfoit. O plansa se
citeste din ochi in cateva secunde si arata exact ce a facut miscarea, nu ce
credem noi ca face.

ATENTIE: joaca `static/dist/`, nu `frontend/src/`. Ruleaza `npx vite build` inainte,
altfel filmezi build-ul vechi (vezi capcana din `smoke_ui.py`).

    python scripts/filmstrip.py                # toate scenele
    python scripts/filmstrip.py foaie          # doar cele care contin „foaie"
"""

import base64
import io
import os
import sys
import tempfile
import time

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADACINA, 'scripts'))

from audit_foaie import (PIN_TEST, TELEFON, apuca, misca, porneste_serverul,
                         port_liber, ridica, seamana, trage)

from PIL import Image, ImageDraw, ImageFont

IESIRE = os.path.join(RADACINA, 'docs', 'filmstrip')

# Cat de mare iese o plansa. `LAT` e latimea unui cadru in plansa; restul se
# deduce din raportul telefonului.
LAT = 150
MAX_CADRE = 12          # cate cadre intra intr-o plansa, dupa curatare
ZGOMOT = 2.0            # cat din fiecare pas e compresie JPEG, nu miscare

FUNDAL = (26, 26, 28)
TEXT = (232, 232, 234)
TEXT_SLAB = (150, 150, 155)


def out(s=''):
    sys.stdout.buffer.write((str(s) + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


# ---------------------------------------------------------------- scene

SCENE = []


def scena(nume, ce_urmaresti):
    """Inregistreaza o scena. Functia primeste (page, cdp, baza) si intoarce
    ACTIUNEA de filmat — sau None daca scena nu se poate juca (selector lipsa),
    caz in care se sare, nu se crapa."""
    def dec(f):
        SCENE.append((nume, ce_urmaresti, f))
        return f
    return dec


def mergi(page, baza, ruta, pauza=1500):
    """Ruta + REINCARCARE. Router-ul e pe hash, deci `goto` intre doua rute nu
    reincarca documentul si starea scenei anterioare ar curge in asta."""
    page.goto(baza + '/#' + ruta, wait_until='load')
    page.reload(wait_until='load')
    page.wait_for_timeout(pauza)


def _centru(el):
    c = el.bounding_box()
    return c['x'] + c['width'] / 2, c['y'] + c['height'] / 2


@scena('foaie-deschide', 'Foaia taskului se deschide (tap pe rand, /tasks)')
def _(page, cdp, baza):
    mergi(page, baza, '/tasks')
    r = page.query_selector_all('.gl-fata')
    if not r:
        return None
    return lambda: (r[0].click(), page.wait_for_timeout(900))


@scena('foaie-inchide-tragere', 'Foaia se inchide trasa in jos cu degetul')
def _(page, cdp, baza):
    mergi(page, baza, '/tasks')
    r = page.query_selector_all('.gl-fata')
    if not r:
        return None
    r[0].click()
    page.wait_for_timeout(900)
    foaie = page.query_selector('.modal.sheet')
    if foaie is None:
        return None
    c = foaie.bounding_box()
    x, y = c['x'] + c['width'] / 2, c['y'] + 24
    return lambda: trage(page, cdp, x, y, [30] * 10)


@scena('foaie-zi', 'Foaia zilei din Calendar (are mereu doua trepte)')
def _(page, cdp, baza):
    mergi(page, baza, '/calendar')
    zi = page.query_selector('[data-zi]')
    if zi is None:
        return None
    return lambda: (zi.click(), page.wait_for_timeout(900))


@scena('dock-schimba-tab', 'Trecerea dintr-un tab in altul, din dock')
def _(page, cdp, baza):
    mergi(page, baza, '/tasks')
    # Calendar, nu Proiecte: pe telefon dock-ul arata cinci intrari, iar
    # „Proiecte" e sub „Mai mult" — deci un selector pe eticheta aia sare mereu.
    tinta = None
    for it in page.query_selector_all('.dock-item'):
        if 'alendar' in (it.get_attribute('aria-label') or ''):
            tinta = it
            break
    if tinta is None:
        return None
    return lambda: (tinta.click(), page.wait_for_timeout(900))


@scena('trage-reincarca', 'Trage-sa-reincarci: discul care se umple')
def _(page, cdp, baza):
    mergi(page, baza, '/tasks')
    # Fara verificare pe `.ptr`: discul se monteaza abia cand `tras > 0`, deci
    # in repaus nu exista si o conditie pe el ar sari scena de fiecare data.
    x = TELEFON['width'] / 2

    def act():
        apuca(cdp, x, 150)
        for k in range(12):
            misca(cdp, x, 150 + k * 12)
            page.wait_for_timeout(16)
        ridica(cdp, page, pauza=900)
    return act


@scena('glisare-facut', 'Glisarea randului spre dreapta (Facut), pe Acasa')
def _(page, cdp, baza):
    mergi(page, baza, '/')
    r = page.query_selector_all('.gl-fata')
    if not r:
        return None
    x, y = _centru(r[0])

    def act():
        apuca(cdp, x, y)
        for k in range(1, 13):
            misca(cdp, x + k * 11, y)
            page.wait_for_timeout(16)
        ridica(cdp, page, pauza=900)
    return act


@scena('apasare-lunga', 'Apasarea lunga pe un rand de task')
def _(page, cdp, baza):
    mergi(page, baza, '/tasks')
    r = page.query_selector_all('.gl-fata')
    if not r:
        return None
    x, y = _centru(r[0])

    def act():
        apuca(cdp, x, y)
        page.wait_for_timeout(750)
        ridica(cdp, page, pauza=700)
    return act


# ---------------------------------------------------------------- filmare

def inregistreaza(page, cdp, act, coada=350):
    """Porneste screencast-ul, joaca actiunea, intoarce [(ms, jpeg_b64)].

    Screencast-ul emite doar cand pagina se SCHIMBA, deci o pagina in repaus nu
    produce cadre — bun pentru noi, dar inseamna ca primul cadru poate veni
    tarziu. De-aia cadrul de referinta (0 ms) se ia separat, cu `captureScreenshot`."""
    cadre = []

    def pe_cadru(params):
        cadre.append((time.perf_counter(), params['data']))
        try:
            cdp.send('Page.screencastFrameAck', {'sessionId': params['sessionId']})
        except Exception:
            pass

    zero = cdp.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 80})['data']

    cdp.on('Page.screencastFrame', pe_cadru)
    cdp.send('Page.startScreencast', {'format': 'jpeg', 'quality': 80,
                                      'everyNthFrame': 1})
    page.wait_for_timeout(80)
    cadre.clear()
    t0 = time.perf_counter()
    act()
    page.wait_for_timeout(coada)
    try:
        cdp.send('Page.stopScreencast', {})
    except Exception:
        pass
    try:
        cdp.remove_listener('Page.screencastFrame', pe_cadru)
    except Exception:
        pass
    return [(0, zero)] + [(int(round((t - t0) * 1000)), d) for t, d in cadre]


VARF = 8  # cati pixeli intra in media care decide „s-a schimbat ceva"


def _amprenta(img):
    return img.convert('L').resize((48, 96), Image.BILINEAR).tobytes()


def _distanta(a, b):
    """Media celor mai schimbati OPT pixeli — NU media pe tot cadrul.

    Media globala e oarba la miscarea mica, si a ascuns deja doua lucruri aici:
      - glisarea randului (40px dintr-un ecran de 844): masuratoarea o arata
        urmarind degetul 1:1, plansa arata 445 ms de nimic;
      - discul de trage-sa-reincarci (~20px): 39 de cadre brute, un singur
        cadru „util", desi discul se umplea in toate.
    Un prag pe media generala nu se poate acorda ca sa le prinda pe amandoua si
    sa nu inghita zgomotul; un varf absolut, da. Opt pixeli din 4608 inseamna
    ~1,5% din latime — cat un disc mic pe o miniatura de 48x96. Zgomotul JPEG e
    imprastiat si mic, deci nu urca varful.

    Prea sensibil e ieftin (esantionul taie oricum la MAX_CADRE); prea surd
    costa o plansa care minte ca nu s-a intamplat nimic."""
    d = sorted((abs(x - y) for x, y in zip(a, b)), reverse=True)
    return sum(d[:VARF]) / float(VARF)


def alege_cadrele(cadre, n=MAX_CADRE):
    """Alege `n` cadre la intervale egale de MISCARE PARCURSA, nu de timp.

    Aici a fost greseala care a costat doua incercari: un PRAG fix, oricat de
    bine acordat, nu poate servi si o foaie care traverseaza ecranul (pasi de
    60+) si un disc de 20px (tot gestul incape in 23). Orice valoare alegi, una
    dintre scene iese drept „nu s-a intamplat nimic" — adica exact minciuna pe
    care plansa trebuia s-o faca imposibila.

    Fara prag: se aduna distantele dintre cadrele vecine intr-un drum cumulat,
    apoi se taie drumul in `n` felii egale. Repausul nu avanseaza drumul, deci
    nu primeste cadre; miscarea rapida il avanseaza mult, deci primeste multe.
    Se acordeaza singur pe fiecare scena, indiferent de cat de mare e gestul.

    `ZGOMOT` scade din fiecare pas: compresia JPEG pune cateva unitati in
    fiecare cadru, iar peste patruzeci de cadre s-ar aduna intr-un drum
    inexistent care ar imprastia esantionul peste o scena nemiscata."""
    depanare = os.environ.get('PIF_FILM_DEBUG')
    imagini = [Image.open(io.BytesIO(base64.b64decode(d))) for _, d in cadre]
    amprente = [_amprenta(i) for i in imagini]

    drum = [0.0]
    for k in range(1, len(amprente)):
        drum.append(drum[-1] + max(0.0, _distanta(amprente[k], amprente[k - 1]) - ZGOMOT))
    if depanare:
        out('         drum cumulat: %.1f (pasi: %s)'
            % (drum[-1], [round(drum[k] - drum[k - 1], 1) for k in range(1, len(drum))]))

    if drum[-1] <= 0 or len(cadre) <= n:
        return [(ms, img) for (ms, _), img in zip(cadre, imagini)]

    alese, k = [], 0
    for i in range(n):
        tinta = drum[-1] * i / float(n - 1)
        while k + 1 < len(drum) and drum[k + 1] <= tinta:
            k += 1
        if not alese or alese[-1] != k:
            alese.append(k)
    return [(cadre[i][0], imagini[i]) for i in alese]


def _font(marime):
    for cale in (r'C:\Windows\Fonts\segoeui.ttf', r'C:\Windows\Fonts\arial.ttf'):
        try:
            return ImageFont.truetype(cale, marime)
        except Exception:
            pass
    return ImageFont.load_default()


def plansa(cadre, nume, descriere):
    """Cadrele, unul langa altul, cu momentul scris sub fiecare."""
    if not cadre:
        return None
    w0, h0 = cadre[0][1].size
    inalt = int(LAT * h0 / float(w0))
    gol, sus, jos = 10, 58, 30

    W = gol + len(cadre) * (LAT + gol)
    H = sus + inalt + jos
    foaie = Image.new('RGB', (W, H), FUNDAL)
    d = ImageDraw.Draw(foaie)
    d.text((gol, 12), nume, font=_font(20), fill=TEXT)
    d.text((gol, 36), descriere, font=_font(13), fill=TEXT_SLAB)

    f_ms = _font(12)
    for i, (ms, img) in enumerate(cadre):
        x = gol + i * (LAT + gol)
        foaie.paste(img.resize((LAT, inalt), Image.LANCZOS), (x, sus))
        d.rectangle([x, sus, x + LAT - 1, sus + inalt - 1], outline=(70, 70, 74))
        d.text((x, sus + inalt + 8), '%d ms' % ms, font=f_ms, fill=TEXT_SLAB)
    return foaie


# ---------------------------------------------------------------- rulare

def scrie_index(facute):
    r = ['<!doctype html><meta charset="utf-8"><title>Filmul interactiunilor</title>',
         '<style>body{background:#1a1a1c;color:#e8e8ea;font:15px/1.5 system-ui;'
         'margin:0;padding:24px}h1{font-size:19px;margin:0 0 4px}'
         'p.s{color:#8a8a90;margin:0 0 28px}figure{margin:0 0 34px}'
         'img{max-width:100%;border-radius:8px;display:block}'
         'figcaption{color:#8a8a90;font-size:13px;margin-top:8px}</style>',
         '<h1>Filmul interactiunilor</h1>',
         '<p class="s">Fiecare rand e un gest, jucat cu atingere adevarata pe 390&times;844. '
         'Cadrele identice sunt scoase, deci ce vezi e chiar miscarea.</p>']
    for nume, descriere, durata in facute:
        r.append('<figure><img src="%s.png" alt="%s">'
                 '<figcaption><b>%s</b> — %s &middot; %d ms</figcaption></figure>'
                 % (nume, nume, nume, descriere, durata))
    with open(os.path.join(IESIRE, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(r))


def main():
    filtru = sys.argv[1] if len(sys.argv) > 1 else ''
    de_jucat = [s for s in SCENE if filtru in s[0]]
    if not de_jucat:
        raise SystemExit('Nicio scena nu se potriveste cu %r.' % filtru)

    os.makedirs(IESIRE, exist_ok=True)
    lucru = tempfile.mkdtemp(prefix='pif-film-')
    db = os.path.join(lucru, 'proba.db')
    seamana(db)
    port = port_liber()
    proc, baza = porneste_serverul(port, db, os.path.join(lucru, 'server.log'))
    facute = []

    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport=TELEFON, has_touch=True, is_mobile=True)
            page = ctx.new_page()
            cdp = ctx.new_cdp_session(page)
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', PIN_TEST)
            page.press('#pin', 'Enter')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)

            for nume, descriere, f in de_jucat:
                try:
                    act = f(page, cdp, baza)
                except Exception as e:
                    out('  SARIT  %-24s pregatirea a crapat: %s' % (nume, e))
                    continue
                if act is None:
                    out('  SARIT  %-24s selectorul nu exista in build-ul asta' % nume)
                    continue
                brute = inregistreaza(page, cdp, act)
                cadre = alege_cadrele(brute)
                img = plansa(cadre, nume, descriere)
                if img is None:
                    out('  GOL    %-24s niciun cadru' % nume)
                    continue
                img.save(os.path.join(IESIRE, nume + '.png'), optimize=True)
                out('  OK     %-24s %2d cadre brute -> %2d utile, %4d ms'
                    % (nume, len(brute), len(cadre), cadre[-1][0]))
                facute.append((nume, descriere, cadre[-1][0]))
            b.close()
    finally:
        proc.terminate()

    scrie_index(facute)
    out('\n%d planse in docs/filmstrip/ — deschide index.html' % len(facute))


if __name__ == '__main__':
    main()
