#!/usr/bin/env python3
"""Rezolva paleta de identitate a proiectelor (frontend/src/lib/culori.js).

De ce un script si nu sase valori scrise de mana: alegerea din ochi a esuat masurabil.
„Sase nuante egal distantate pe roata de culori" a iesit la o separare de 0,055 — MAI
PROST decat paleta din productie (0,064) — pentru ca sub deficienta rosu-verde axa
rosu-verde se prabuseste si nuantele „bine distantate" se suprapun. Ce supravietuieste
e luminozitatea si axa albastru-galben.

Ruleaza-l daca schimbi accentul sau tokenurile semantice — paleta depinde de ele si
trebuie RE-rezolvata, nu ajustata pe bucati. (Locatia nu mai e codata cromatic din
redesignul 2026-08-08: forma spune faza, locul e scris — deci nu mai e rezervata.)

    python scripts/solve_paleta.py

Simularea CVD e Vienot-Brettel pe LMS (aceeasi familie folosita de Color Oracle si de
tabelele Okabe-Ito). Metrica de separare e o distanta LMS normalizata: relativa, deci
comparabila intre palete, fara unitate fizica.
"""
import colorsys
import random

# ---- culori rezervate: paleta trebuie sa stea DEPARTE de ele -------------------
# Tinute sincronizate manual cu frontend/src/styles/tokens.css (tema dark).
REZERVATE = {
    '--accent': '#8ab2d9',
    '--danger': '#e0917f',
    '--success': '#82c2a2',
}
FUNDAL = '#121417'      # --bg
CERNEALA = '#0e1114'    # --accent-text / --on-color: textul peste un fill saturat

# O nuanta per familie => paleta ramane echilibrata, nu aduna trei verzi.
SECTOARE = [(70, 110), (112, 165), (167, 205), (207, 248), (262, 302), (304, 354)]

PRAG_REZERVAT = 0.20    # cat de departe de o culoare cu SENS
AA_PE_CERNEALA = 4.5    # text inchis peste fill
MIN_PE_FUNDAL = 3.0     # fill-ul insusi trebuie sa se vada pe pagina


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(t):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(x)))) for x in t)


def _lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lrgb(h):
    r, g, b = rgb(h)
    return (_lin(r), _lin(g), _lin(b))


def luminanta(h):
    r, g, b = lrgb(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    l1, l2 = sorted([luminanta(a), luminanta(b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _lms(h):
    r, g, b = lrgb(h)
    return (17.8824 * r + 43.5161 * g + 4.11935 * b,
            3.45565 * r + 27.1554 * g + 3.86714 * b,
            0.0299566 * r + 0.184309 * g + 1.46709 * b)


def simuleaza(h, fel):
    L, M, S = _lms(h)
    if fel == 'deuter':
        return (L, 0.494207 * L + 1.24827 * S, S)
    if fel == 'prot':
        return (2.02344 * M - 2.52581 * S, M, S)
    if fel == 'trit':
        return (L, M, -0.395913 * L + 0.801109 * M)
    return (L, M, S)


FELURI = ['normal', 'deuter', 'prot', 'trit']


def departare(a, b, fel):
    x, y = simuleaza(a, fel), simuleaza(b, fel)
    return sum(((x[i] - y[i]) / (abs(x[i]) + abs(y[i]) + 1e-6)) ** 2 for i in range(3)) ** 0.5


def separare(paleta, rezervate):
    """Cea mai mica departare din paleta — intre membri SI fata de rezervate."""
    minim = 9.0
    for a in paleta:
        for b in list(paleta) + list(rezervate):
            if a == b:
                continue
            for fel in FELURI:
                minim = min(minim, departare(a, b, fel))
    return minim


def candidati(lo, hi, rezervate):
    out = []
    for hd in range(lo, hi + 1, 2):
        for s in (0.36, 0.44, 0.52, 0.60, 0.68, 0.76):
            for v in (0.64, 0.72, 0.80, 0.88):
                r, g, b = colorsys.hsv_to_rgb(hd / 360, s, v)
                c = _hex((r * 255, g * 255, b * 255))
                if contrast(c, CERNEALA) < AA_PE_CERNEALA:
                    continue
                if contrast(c, FUNDAL) < MIN_PE_FUNDAL:
                    continue
                if min(departare(c, r_, f) for r_ in rezervate for f in FELURI) <= PRAG_REZERVAT:
                    continue
                out.append(c)
    return list(dict.fromkeys(out))


def main():
    rezervate = list(REZERVATE.values())
    galeti = [candidati(lo, hi, rezervate) for lo, hi in SECTOARE]
    print('candidati per familie:', [len(g) for g in galeti])
    if not all(galeti):
        raise SystemExit('o familie a ramas fara candidati — relaxeaza pragurile')

    random.seed(5)
    best = None
    for _ in range(40000):
        pal = [random.choice(g) for g in galeti]
        s = separare(pal, rezervate)
        if best is None or s > best[0]:
            best = (s, pal)

    s, pal = best
    imbunatatit = True
    while imbunatatit:                      # slefuire lacoma pana la stabilizare
        imbunatatit = False
        for i in range(len(pal)):
            for c in galeti[i]:
                if c == pal[i]:
                    continue
                incercare = pal[:i] + [c] + pal[i + 1:]
                t = separare(incercare, rezervate)
                if t > s:
                    s, pal, imbunatatit = t, incercare, True

    print(f'\nseparare in cel mai rau caz = {s:.3f}')
    print('paleta:', pal)
    for c in pal:
        h = colorsys.rgb_to_hsv(*[x / 255 for x in rgb(c)])[0] * 360
        print(f'  {c}  nuanta={h:5.0f}  pe cerneala={contrast(c, CERNEALA):5.2f}:1'
              f'  pe fundal={contrast(c, FUNDAL):5.2f}:1')

    vechi = ['#3f9dc4', '#3fae74', '#8b6fe0', '#d1697f', '#5f8fd0', '#c9a13a', '#b9a5ff']
    print(f'\nreper — paleta dinainte de 2026-07-30: {separare(vechi, rezervate):.3f}')


if __name__ == '__main__':
    main()
