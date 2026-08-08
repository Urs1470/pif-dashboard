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

# Tila ia --accent (tema deschisa: fillul e acelasi in ambele teme, fiindca
# iconita de launcher nu stie ce tema are aplicatia), cerneala ia --accent-text.
ACCENT = '#5980a6'
CERNEALA = '#ffffff'

# Logo-ul, exact ca in frontend/public/favicon.svg — aceleasi coordonate.
RAMPA = (
    '<path d="M14 48 C27 48 30 40 33 30 S42 16 50 16 L50 48 Z" fill="{i}" opacity="0.3"/>'
    '<path d="M14 48 C27 48 30 40 33 30 S42 16 50 16" fill="none" stroke="{i}"'
    ' stroke-width="5.5" stroke-linecap="round"/>'
    '<circle cx="50" cy="16" r="5" fill="{i}"/>'
).format(i=CERNEALA)

# ZONA SIGURA O PUNE GENERATORUL, NU NOI.
# `capacitor-assets` scrie XML-ul adaptive cu `inset 16.7%` pe stratul de
# prim-plan — exact cat trebuie ca desenul sa incapa in cercul de 66% pe care
# orice producator il pastreaza. Daca ii dam un logo caruia i-am pus DEJA marja,
# insetul se aplica a doua oara si rampa iese de doua ori mai mica decat trebuie.
# Deci desenam pe toata panza si il lasam pe el sa strange.
SVG_FUNDAL = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
              f'<rect width="64" height="64" fill="{ACCENT}"/></svg>')

SVG_PRIMPLAN = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
                f'{RAMPA}</svg>')

# Acelasi XML pentru ambele forme. Diferenta fata de ce scrie generatorul: FARA
# inset pe fundal. Fundalul unei iconite adaptive trebuie sa umple panza pana in
# margini — el e cel pe care sistemul il taie in cerc, patrat sau picatura. Cu
# inset, tila se opreste inainte de margine si iconita apare ca un patrat mic
# care pluteste intr-un colt transparent.
XML_ADAPTIVE = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background" />
    <foreground>
        <inset android:drawable="@mipmap/ic_launcher_foreground" android:inset="16.7%" />
    </foreground>
</adaptive-icon>
'''

SVG_INTREG = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
              f'<rect width="64" height="64" rx="14" fill="{ACCENT}"/>{RAMPA}</svg>')


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
