#!/usr/bin/env python3
"""Traduce `frontend/src/styles/tokens.css` in date pentru Figma.

De ce exista. Un redesign estetic se face schimband ROLURI, nu ecrane: muti
`--bg-surface` si se re-vopseste tot. Ca sa se poata face asta in Figma, fisierul
de acolo trebuie sa fie construit pe VARIABILE legate, nu pe culori scrise de
mana in fiecare dreptunghi. Iar variabilele alea trebuie sa vina din tokens.css,
altfel a doua zi diverg — exact modul de esec pentru care exista `audit_design.py`.

Ce face, concret:
  - citeste cele doua teme (`:root`/`[data-theme="dark"]` si `[data-theme="light"]`);
  - pastreaza ALIASURILE ca aliasuri (`--text-faint: var(--text-dim)` devine in
    Figma o variabila care POINTEAZA la alta, nu o a doua copie a valorii) —
    proprietatea pe care comentariile din tokens.css o numesc „regula care se
    repara singura";
  - rezolva cele cinci `color-mix()`, in OKLab si in sRGB, ca in browser;
  - imparte restul pe colectii: culoare (doua moduri), scara (o singura valoare),
    tipografie (devine stiluri de text), umbre (stiluri de efect), miscare (nu are
    corespondent in Figma — se scrie ca fisa).

Iese `design/figma-plugin/tokens.generated.js`, pe care il inghite pluginul.

    python scripts/figma_tokens.py            # genereaza
    python scripts/figma_tokens.py --arata    # si tipareste ce a rezolvat
"""
import argparse
import json
import re
import sys
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
TOKENS = RADACINA / 'frontend' / 'src' / 'styles' / 'tokens.css'
IESIRE = RADACINA / 'design' / 'figma-plugin' / 'tokens.generated.js'

# Variabile scrise la RULARE din JS (stare de gest, insets, nivel de modal). Nu
# sunt tokenuri de design si n-au ce cauta intr-un fisier de Figma.
LA_RULARE = {
    '--nav-sens', '--nivel', '--tras', '--h-foaie', '--voal-p', '--dx', '--kb',
    '--dock-h', '--panou-w',
    '--safe-area-inset-top', '--safe-area-inset-bottom',
    '--safe-area-inset-left', '--safe-area-inset-right',
    '--safe-top', '--safe-bottom', '--safe-left', '--safe-right',
}

# Compozite CSS care nu au corespondent in Figma.
TRANZITII = {'--transition-colors', '--transition-pressable', '--focus-ring'}

MISCARE = re.compile(r'^--(dur-|ease|pas-scara|pauza-semn|press-scale)')
UMBRA = re.compile(r'^--shadow-')
VOAL = re.compile(r'^--scrim')
TIPO = re.compile(r'^--(font-|fw-|lh-|tracking-)')


# ------------------------------------------------------------------ culoare

def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def srgb_la_oklab(r, g, b):
    r, g, b = _lin(r), _lin(g), _lin(b)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_la_srgb(L, A, B):
    l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(min(1.0, max(0.0, _gam(x))) for x in (r, g, b))


def citeste_culoare(v):
    """'#rrggbb' | 'rgba(r, g, b, a)' -> (r, g, b, a) in 0..1, sau None."""
    v = v.strip()
    m = re.fullmatch(r'#([0-9a-fA-F]{6})', v)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 1.0)
    m = re.fullmatch(r'rgba?\(([^)]+)\)', v)
    if m:
        p = [x.strip() for x in m.group(1).replace('/', ',').split(',') if x.strip()]
        if len(p) >= 3:
            r, g, b = (float(x) / 255 for x in p[:3])
            a = float(p[3]) if len(p) > 3 else 1.0
            return (r, g, b, a)
    if v == 'transparent':
        return (0.0, 0.0, 0.0, 0.0)
    return None


def scrie_culoare(c):
    r, g, b, a = c
    h = '#%02x%02x%02x' % (round(r * 255), round(g * 255), round(b * 255))
    return h if abs(a - 1.0) < 1e-6 else '%s@%.4f' % (h, a)


def amesteca(spatiu, c1, proc, c2):
    """color-mix(in <spatiu>, c1 proc%, c2). Premultiplicat cu alfa, ca in CSS."""
    p = proc / 100.0
    a = c1[3] * p + c2[3] * (1 - p)
    if a <= 1e-9:
        return (0.0, 0.0, 0.0, 0.0)
    # ponderi premultiplicate, apoi impartite inapoi la alfa rezultata
    w1, w2 = c1[3] * p / a, c2[3] * (1 - p) / a
    if spatiu == 'oklab':
        L1, A1, B1 = srgb_la_oklab(*c1[:3])
        L2, A2, B2 = srgb_la_oklab(*c2[:3])
        r, g, b = oklab_la_srgb(L1 * w1 + L2 * w2, A1 * w1 + A2 * w2, B1 * w1 + B2 * w2)
    else:
        r, g, b = (c1[i] * w1 + c2[i] * w2 for i in range(3))
    return (r, g, b, a)


# ------------------------------------------------------------------- parsare

def blocuri(css):
    """{eticheta_tema: {token: valoare_bruta}} pentru cele doua teme + telefon."""
    out = {'dark': {}, 'light': {}, 'telefon': {}}

    def culege(text):
        d = {}
        for m in re.finditer(r'(--[\w-]+)\s*:\s*([^;]+);', text):
            d[m.group(1)] = ' '.join(m.group(2).split())
        return d

    m = re.search(r':root,\s*\[data-theme="dark"\]\s*\{(.*?)\n\}', css, re.S)
    if not m:
        sys.exit('nu gasesc blocul temei intunecate')
    out['dark'] = culege(m.group(1))

    m = re.search(r'\[data-theme="light"\]\s*\{(.*?)\n\}', css, re.S)
    if not m:
        sys.exit('nu gasesc blocul temei deschise')
    out['light'] = culege(m.group(1))

    m = re.search(r'@media \(max-width: 768px\)\s*\{\s*:root\s*\{(.*?)\}', css, re.S)
    if m:
        out['telefon'] = culege(m.group(1))
    return out


def rezolva(token, tema, brut, adancime=0):
    """Valoarea FINALA a unui token intr-o tema (urmareste var() si color-mix())."""
    if adancime > 12:
        return None
    v = brut[tema].get(token)
    if v is None and tema == 'light':
        v = brut['dark'].get(token)      # tema deschisa suprascrie doar primitivele
    if v is None:
        return None
    return rezolva_valoare(v, tema, brut, adancime)


def rezolva_valoare(v, tema, brut, adancime=0):
    if adancime > 12:
        return None
    v = v.strip()
    m = re.fullmatch(r'var\((--[\w-]+)\)', v)
    if m:
        return rezolva(m.group(1), tema, brut, adancime + 1)
    m = re.fullmatch(r'color-mix\(in (\w+),\s*(.+?)\s+([\d.]+)%,\s*(.+?)\)', v)
    if m:
        spatiu, a_txt, proc, b_txt = m.group(1), m.group(2), float(m.group(3)), m.group(4)
        ca = citeste_culoare(a_txt) or citeste_culoare(rezolva_valoare(a_txt, tema, brut, adancime + 1) or '')
        cb = citeste_culoare(b_txt) or citeste_culoare(rezolva_valoare(b_txt, tema, brut, adancime + 1) or '')
        if ca and cb:
            return scrie_culoare(amesteca(spatiu, ca, proc, cb))
        return None
    return v


def px(v):
    """'1.5625rem' | '16px' | '400' -> numar in px, sau None."""
    v = v.strip()
    m = re.fullmatch(r'(-?[\d.]+)rem', v)
    if m:
        return float(m.group(1)) * 16
    m = re.fullmatch(r'(-?[\d.]+)px', v)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r'-?[\d.]+', v)
    if m:
        return float(v)
    return None


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description='tokens.css -> date pentru pluginul de Figma')
    ap.add_argument('--arata', action='store_true', help='tipareste ce a rezolvat')
    args = ap.parse_args()

    css = TOKENS.read_text(encoding='utf-8')
    brut = blocuri(css)
    ordine = list(brut['dark'].keys())

    culori, scara, tipografie, umbre, miscare = {}, {}, {}, {}, {}
    nerezolvate = []

    for t in ordine:
        if t in LA_RULARE or t in TRANZITII:
            continue
        v_dark = rezolva(t, 'dark', brut)
        v_light = rezolva(t, 'light', brut)
        if v_dark is None:
            nerezolvate.append(t)
            continue

        brut_dark = brut['dark'][t]
        alias = None
        m = re.fullmatch(r'var\((--[\w-]+)\)', brut_dark)
        if m and m.group(1) not in LA_RULARE:
            alias = m.group(1)

        if MISCARE.match(t):
            miscare[t] = brut_dark
            continue
        if UMBRA.match(t):
            umbre[t] = {'dark': v_dark, 'light': v_light}
            continue
        if VOAL.match(t):
            culori[t] = {'dark': v_dark, 'light': v_light, 'alias': alias}
            continue

        if citeste_culoare(v_dark):
            culori[t] = {'dark': v_dark, 'light': v_light, 'alias': alias}
        elif TIPO.match(t):
            n = px(v_dark)
            tipografie[t] = {'px': n, 'brut': v_dark, 'alias': alias,
                             'telefon': px(brut['telefon'][t]) if t in brut['telefon'] else None}
        else:
            n = px(v_dark)
            if n is None:
                nerezolvate.append(t)
            else:
                scara[t] = {'px': n, 'alias': alias}

    date = {
        'sursa': 'frontend/src/styles/tokens.css',
        'culori': culori,
        'scara': scara,
        'tipografie': tipografie,
        'umbre': umbre,
        'miscare': miscare,
    }

    IESIRE.parent.mkdir(parents=True, exist_ok=True)
    IESIRE.write_text(
        '// GENERAT de scripts/figma_tokens.py — nu edita cu mana.\n'
        '// Sursa: frontend/src/styles/tokens.css\n'
        'const TOKENS = ' + json.dumps(date, indent=2, ensure_ascii=False) + ';\n',
        encoding='utf-8')

    print('culori %d · scara %d · tipografie %d · umbre %d · miscare %d'
          % (len(culori), len(scara), len(tipografie), len(umbre), len(miscare)))
    aliasuri = [t for t, d in culori.items() if d.get('alias')]
    print('aliasuri de culoare pastrate ca aliasuri: %d' % len(aliasuri))
    print('scris: ' + str(IESIRE.relative_to(RADACINA)).replace('\\', '/'))

    if nerezolvate:
        print('\nNEREZOLVATE (%d) — nu intra in Figma:' % len(nerezolvate))
        for t in nerezolvate:
            print('   %-28s %s' % (t, brut['dark'].get(t, '')[:60]))

    if args.arata:
        print('\ncolor-mix rezolvat:')
        for t, d in culori.items():
            if 'color-mix' in brut['dark'].get(t, ''):
                print('   %-20s dark %-16s light %s' % (t, d['dark'], d['light']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
