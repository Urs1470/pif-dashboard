# -*- coding: utf-8 -*-
"""Genereaza sursele de iconita pentru aplicatia Android, din logo-ul aplicatiei.
Apoi `npx capacitor-assets generate --android` le taie pe toate densitatile.

    python scripts/gen_icons.py

DE CE EXISTA. `cap add android` pune iconitele LUI de rezerva in
`res/mipmap-*/ic_launcher*`, iar Android citeste doar de acolo — `favicon.svg` si
`icon-512.png` sunt ale aplicatiei web si nu ajung niciodata pe ecranul
principal. Fara pasul asta, aplicatia sta pe telefon cu iconita altcuiva.

DE CE TREI FISIERE, nu unul. Android desenez iconitele „adaptive" pe doua
straturi si le taie in ce forma vrea producatorul (cerc, patrat rotunjit,
picatura). Daca dai o singura imagine gata taiata, colturile logo-ului se pierd
la taiere. Deci:
    icon-background.png  tila de accent, plina, pana in margini
    icon-foreground.png  rampa si punctul, DESENATE IN ZONA SIGURA (66% din
                         panza) — restul e transparent si poate fi taiat linistit
    icon.png             logo-ul intreg, pentru locurile care nu stiu de straturi

Randarea o face Chromium (cel al lui Playwright, deja instalat pentru smoke_ui):
SVG-ul e sursa de adevar a logo-ului si nu-l redesenam de mana in alt format.
"""
import os
import sys

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IESIRE = os.path.join(RADACINA, 'frontend', 'assets')

# ===== MARCA (AURORA, 2026-08-23) =====
#
# O sinusoida de o perioada inscrisa intr-un cerc — simbolul de sursa alternativa.
# Trecerile prin zero cad exact pe axa (x = 20, 32, 44), amplitudini egale sus si
# jos. Cerc: raza 18, grosime 5. Unda: grosime 4.2.
# Canonic: `design/handoff-aurora/assets/torqa-logomark.svg`.
#
# INAINTE DE AURORA, FISIERUL ASTA DESENA ALTCEVA DECAT APLICATIA, si nimeni n-a
# observat: aici era rampa cu cerc pe `#5980a6`, in `favicon.svg` semnalul
# dreptunghiular (PWM), iar in bara marca noua. Trei marci, in acelasi produs.
# Comentariul de aici chiar spunea „exact ca in favicon.svg" — si nu mai era
# adevarat de doua redesign-uri. De aceea TOATE artefactele se genereaza acum de
# aici, si cele web, nu doar cele de Android.

def marca(cerneala, umbra=''):
    return (f'<g fill="none" stroke="{cerneala}" stroke-linecap="round"'
            f' stroke-linejoin="round"{umbra}>'
            f'<path d="M14 32a18 18 0 1 0 36 0 18 18 0 1 0-36 0" stroke-width="5"/>'
            f'<path d="M20 32c4-11.33 8-11.33 12 0s8 11.33 12 0" stroke-width="4.2"/>'
            f'</g>')

# Tila simpla ia `--accent` de tema DESCHISA: iconita de launcher nu stie ce tema
# are aplicatia, iar valoarea mai inchisa tine cerneala alba lizibila pe ea.
ACCENT = '#63638f'
CERNEALA = '#ffffff'

# ECRANUL DE INCARCARE = FONDUL APLICATIEI, nu o imagine de marca.
# Splash-ul se vede o secunda, exact inainte ca pagina sa apara — daca e alta
# culoare decat fondul care ii urmeaza, pornirea clipeste. De aceea valorile sunt
# `--bg` din `tokens.css`, pe teme, nu ceva ales aici.
FOND_INCHIS  = '#15151a'    # --bg, [data-theme="dark"]
FOND_DESCHIS = '#f5f5f9'    # --bg, [data-theme="light"]

# ===== ICONITA DE APLICATIE — „planseta de schite" =====
# Corp cu gradient, caroiaj de 4 unitati, axe punctate si repere de colt; marca
# deasupra, intr-un gradient metalic cu umbra proprie. Constructia asta ramane
# DOAR iconita: in interfata s-ar citi ca un corp strain (handoff, README).
DEFS = (
    '<defs>'
    '<linearGradient id="corp" x1="0" y1="1" x2="0" y2="0">'
    '<stop offset="0" stop-color="#1b1b30"/><stop offset=".55" stop-color="#3f3f66"/>'
    '<stop offset="1" stop-color="#7878a6"/></linearGradient>'
    '<pattern id="caroiaj" width="4" height="4" patternUnits="userSpaceOnUse">'
    '<path d="M4 0H0v4" fill="none" stroke="#dfdff2" stroke-opacity=".30" stroke-width=".35"/>'
    '</pattern>'
    '<linearGradient id="metal" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#e6e6f2"/>'
    '<stop offset="1" stop-color="#b6b6d0"/></linearGradient>'
    '<filter id="umbra" x="-40%" y="-40%" width="180%" height="180%">'
    '<feDropShadow dx="0" dy="1.8" stdDeviation="1.6" flood-color="#0d0d20" flood-opacity=".55"/>'
    '</filter>'
    '</defs>'
)
PLANSETA = (
    '<rect width="64" height="64" fill="url(#corp)"/>'
    '<rect width="64" height="64" fill="url(#caroiaj)" opacity=".55"/>'
    '<g fill="none" stroke="#dfdff2" stroke-opacity=".42" stroke-width=".45">'
    '<path d="M0 32h64M32 0v64" stroke-dasharray="2 2.4"/>'
    '<path d="M6 6h6M6 6v6M58 6h-6M58 6v6M6 58h6M6 58v-6M58 58h-6M58 58v-6" stroke-opacity=".55"/>'
    '</g>'
)
MARCA_METAL = marca('url(#metal)', ' filter="url(#umbra)"')

# ===== FORMA: SQUIRCLE, NU DREPTUNGHI ROTUNJIT (Apple, 2026-08-23) =====
#
# Iconitele Apple nu au colturi de ARC DE CERC, ci curbura CONTINUA: raza nu sare
# de la infinit la o valoare fixa in punctul de tangenta, ci creste lin. De aceea
# un `rx` obisnuit se citeste ca „aproape" langa o iconita de sistem.
# Ion, 2026-08-23: redesignul e inspirat de la ei, deci si forma.
#
# Se genereaza NUMERIC din superelipsa |x/a|^n + |y/a|^n = 1, nu din coeficienti
# copiati de undeva: asa se poate verifica, si se poate regla dintr-un singur
# numar. n = 5 e aproximarea uzuala a formei lor (n = 2 ar da un cerc, n -> inf un
# patrat). 128 de puncte pe contur — la 1024px randati inseamna sub un pixel intre
# ele, deci conturul e neted si la marimea cea mai mare pe care o scoatem.
import math

def squircle(centru, a, n=5.0, puncte=128):
    """Traseu inchis de superelipsa, in coordonatele grilei de 64."""
    pas = []
    for i in range(puncte):
        t = 2 * math.pi * i / puncte
        ct, st = math.cos(t), math.sin(t)
        x = centru + a * math.copysign(abs(ct) ** (2.0 / n), ct)
        y = centru + a * math.copysign(abs(st) ** (2.0 / n), st)
        pas.append('%s%.3f %.3f' % ('M' if i == 0 else 'L', x, y))
    return ''.join(pas) + 'Z'


FORMA = squircle(32, 32)          # conturul iconitei
FORMA_RAMA = squircle(32, 31.4)   # aceeasi forma, trasa 0.6 inauntru, pentru rama


def svg(continut, taiat=False):
    clip = (f'<defs><clipPath id="taie"><path d="{FORMA}"/></clipPath></defs>'
            f'<g clip-path="url(#taie)">{continut}</g>'
            f'<path d="{FORMA_RAMA}" fill="none" stroke="#fff" stroke-opacity=".22"'
            f' stroke-width="1.2"/>') if taiat else continut
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'{DEFS}{clip}</svg>')

# ZONA SIGURA O PUNE GENERATORUL, NU NOI.
# `capacitor-assets` scrie XML-ul adaptive cu `inset 16.7%` pe stratul de
# prim-plan — exact cat trebuie ca desenul sa incapa in cercul de 66% pe care
# orice producator il pastreaza. Daca ii dam un logo caruia i-am pus DEJA marja,
# insetul se aplica a doua oara si marca iese de doua ori mai mica decat trebuie.
# Deci desenam pe toata panza si il lasam pe el sa strange.
SVG_FUNDAL = svg(PLANSETA)
SVG_PRIMPLAN = svg(MARCA_METAL)
SVG_INTREG = svg(PLANSETA + MARCA_METAL, taiat=True)

# Tila simpla, pentru favicon si pentru locurile mici: fara caroiaj (handoff:
# „la sub ~32px se recomanda o varianta fara caroiaj").
SVG_TILA = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<path d="{FORMA}" fill="{ACCENT}"/>{marca(CERNEALA)}</svg>')

XML_ADAPTIVE = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background" />
    <foreground>
        <inset android:drawable="@mipmap/ic_launcher_foreground" android:inset="16.7%" />
    </foreground>
</adaptive-icon>
'''

def svg_splash(fond):
    """Panza patrata (`capacitor-assets` o taie pentru fiecare densitate si
    orientare), cu logo-ul mic in mijloc.

    Logo-ul ocupa 22% din latura: splash-ul se decupeaza diferit pe fiecare
    ecran, iar ce e in afara centrului se poate pierde. La 22% incape intreg
    chiar si pe cea mai ingusta taietura de peisaj."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            f'<rect width="100" height="100" fill="{fond}"/>'
            f'<g transform="translate(39 39) scale(0.34375)">'
            f'<path d="{FORMA}" fill="{ACCENT}"/>{marca(CERNEALA)}</g>'
            f'</svg>')


def randeaza(pagina, svg, cale, latura):
    pagina.set_viewport_size({'width': latura, 'height': latura})
    pagina.set_content(
        '<style>html,body{margin:0;padding:0;background:transparent}'
        f'svg{{display:block;width:{latura}px;height:{latura}px}}</style>' + svg)
    pagina.wait_for_timeout(60)
    pagina.screenshot(path=cale, omit_background=True)
    print(f'  {os.path.basename(cale)}  {latura}x{latura}  '
          f'{os.path.getsize(cale) // 1024} KB')


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit('Lipseste playwright (vezi scripts/smoke_ui.py pentru instalare).')
    os.makedirs(IESIRE, exist_ok=True)
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        p = br.new_page()
        print(f'Scriu in {IESIRE}:')
        randeaza(p, SVG_INTREG, os.path.join(IESIRE, 'icon.png'), 1024)
        randeaza(p, SVG_FUNDAL, os.path.join(IESIRE, 'icon-background.png'), 1024)
        randeaza(p, SVG_PRIMPLAN, os.path.join(IESIRE, 'icon-foreground.png'), 1024)
        # 2732 e latura pe care o cere `capacitor-assets`: din ea taie fiecare
        # densitate SI ambele orientari, deci trebuie sa fie cea mai mare
        # diagonala de care are nevoie.
        randeaza(p, svg_splash(FOND_DESCHIS),
                 os.path.join(IESIRE, 'splash.png'), 2732)
        randeaza(p, svg_splash(FOND_INCHIS),
                 os.path.join(IESIRE, 'splash-dark.png'), 2732)

        # SI ARTEFACTELE WEB, DIN ACEEASI SURSA. Cat timp erau scrise separat,
        # marca a apucat sa se bifurce in TREI fara ca nimeni sa observe: rampa
        # aici, semnalul dreptunghiular in favicon, si a treia in bara.
        pub = os.path.join(RADACINA, 'frontend', 'public')
        print('Scriu in %s:' % pub)
        randeaza(p, SVG_INTREG, os.path.join(pub, 'icon-192.png'), 192)
        randeaza(p, SVG_INTREG, os.path.join(pub, 'icon-512.png'), 512)
        with open(os.path.join(pub, 'favicon.svg'), 'w',
                  encoding='utf-8', newline='\n') as fh:
            fh.write(SVG_TILA + '\n')
        print('  favicon.svg  (tila fara caroiaj — se citeste si la 16px)')
        br.close()
    print('\nAcum: cd frontend && npx capacitor-assets generate --android')
    print('apoi:  python scripts/gen_icons.py --repara-xml   (scoate insetul de pe fundal)')


def repara_xml():
    """Rescrie XML-urile adaptive dupa `capacitor-assets generate`.

    Generatorul pune inset si pe fundal; vezi comentariul de la XML_ADAPTIVE.
    Se ruleaza DUPA el, de fiecare data — regenerarea iconitelor il pune la loc.
    """
    baza = os.path.join(RADACINA, 'frontend', 'android', 'app', 'src', 'main',
                        'res', 'mipmap-anydpi-v26')
    if not os.path.isdir(baza):
        raise SystemExit(f'Nu exista {baza} — ruleaza intai capacitor-assets generate --android')
    for nume in ('ic_launcher.xml', 'ic_launcher_round.xml'):
        cale = os.path.join(baza, nume)
        with open(cale, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(XML_ADAPTIVE)
        print(f'  reparat: {nume} (fundal fara inset)')


if __name__ == '__main__':
    sys.exit(repara_xml() if '--repara-xml' in sys.argv else main())
