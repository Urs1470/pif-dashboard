# -*- coding: utf-8 -*-
"""Contrastul perechilor din sistemul de design, masurat, pe amandoua temele.

DE CE EXISTA
`tokens.css` isi scrie singur, in comentarii, ratiile pe care le-a calibrat:
„--text-dim e MINIMUL pentru text mic, ~5,6:1 aici, ~4,7:1 pe tema deschisa",
„accentul de tema deschisa era #5980a6 si cadea sub AA in AMBELE roluri ale lui".
Numerele alea au fost socotite O DATA, de mana, si nu le verifica nimic: comentariul
din dreptul accentului spune exact asta — „`audit_design.py` verifica paritatea
tokenurilor intre teme, NICIODATA contrastul".

Deci orice atingere a paletei e, azi, o schimbare pe incredere. Iar rolul care a
cazut ultima oara — accentul ca text pe o suprafata — nu era numit de nicio regula
scrisa, si a cazut numai pe tema pe care Ion o foloseste in hala.

CE VERIFICA
Perechile care chiar apar pe ecran, nu produsul cartezian: cerneala pe fiecare
dintre cele trei suprafete, accentul in cele trei roluri ale lui (text pe fond,
text pe suprafata, cerneala pe fillul lui), cerneala adanca pe fiecare tenta de
stare, si SEPARAREA dintre cele trei trepte de text — aceea nu e o cerinta de
lizibilitate, e cerinta ca ierarhia declarata sa se si vada (sub 1,3:1 doua trepte
se citesc ca una singura, si chiar asta s-a intamplat pana pe 2026-08-08).

Pragurile sunt cele din WCAG AA, cu treapta corecta pentru fiecare rol:
text mic 4,5 · text mare / element de interfata 3,0 · separare de trepte 1,4.

RULARE
    python scripts/audit_contrast.py
    python scripts/audit_contrast.py --tot     # si perechile care trec
    python scripts/audit_contrast.py --paleta fisier.css   # incearca alta paleta

Nu porneste nimic si nu atinge reteaua: citeste `frontend/src/styles/tokens.css`,
rezolva aliasurile si cele cinci `color-mix()` exact ca browserul (oklab si sRGB),
si socoteste. Iese cu 0 daca totul trece, 1 daca ceva cade.
"""

import argparse
import re
import sys
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
TOKENS = RADACINA / 'frontend' / 'src' / 'styles' / 'tokens.css'


# ----------------------------------------------------------------- culoare
def _liniar(c):
    """sRGB 0..1 -> liniar. Pragul si exponentul sunt cei din specificatie."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gama(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def hex_rgb(h):
    h = h.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_hex(t):
    return '#' + ''.join('%02x' % max(0, min(255, round(c * 255))) for c in t)


def luminanta(rgb):
    r, g, b = (_liniar(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminanta(a), luminanta(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def rgb_oklab(rgb):
    r, g, b = (_liniar(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (v ** (1 / 3) if v >= 0 else -((-v) ** (1 / 3)) for v in (l, m, s))
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_rgb(lab):
    L, A, B = lab
    l_ = L + 0.3963377774 * A + 0.2158037573 * B
    m_ = L - 0.1055613458 * A - 0.0638541728 * B
    s_ = L - 0.0894841775 * A - 1.2914855480 * B
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(min(1.0, max(0.0, _gama(v))) for v in (r, g, b))


def amesteca(spatiu, a, pa, b):
    """`color-mix(in <spatiu>, a pa%, b)` — a cu pondere pa, restul b."""
    w = pa / 100.0
    if spatiu == 'oklab':
        la, lb = rgb_oklab(a), rgb_oklab(b)
        return oklab_rgb(tuple(la[i] * w + lb[i] * (1 - w) for i in range(3)))
    # srgb: amestecul se face pe canalele GAMA, ca in browser
    return tuple(a[i] * w + b[i] * (1 - w) for i in range(3))


# ------------------------------------------------------------------ parser
BLOC = re.compile(r'(?P<sel>[^{}]+)\{(?P<corp>[^{}]*)\}', re.S)
DECL = re.compile(r'(--[\w-]+)\s*:\s*([^;]+);')
MIX = re.compile(r'color-mix\(\s*in\s+(\w+)\s*,\s*(.+?)\s+([\d.]+)%\s*,\s*(.+?)\s*\)$', re.S)
VAR = re.compile(r'^var\(\s*(--[\w-]+)\s*\)$')


def fara_comentarii(s):
    return re.sub(r'/\*.*?\*/', '', s, flags=re.S)


def citeste(cale):
    """Doua dictionare brute, {token: expresie}, pentru cele doua teme.

    Tema deschisa MOSTENESTE de la blocul de baza: `[data-theme="light"]`
    redefineste doar culorile, iar aliasurile („`--info: var(--accent)`") sunt
    scrise o singura data, sus. Fara mostenire, jumatate din roluri ar lipsi din
    tema pe care o foloseste Ion cel mai des.
    """
    text = fara_comentarii(Path(cale).read_text(encoding='utf-8'))
    baza, light = {}, {}
    for m in BLOC.finditer(text):
        sel = m.group('sel').strip()
        # Blocurile din `@media` au selectorul lipit de linia lui; ne intereseaza
        # doar cele doua teme de baza. Restul (praguri de telefon/desktop) nu tin
        # de culoare.
        if 'data-theme="light"' in sel:
            tinta = light
        elif sel.startswith(':root') or 'data-theme="dark"' in sel:
            if '@media' in sel:
                continue
            tinta = baza
        else:
            continue
        for k, v in DECL.findall(m.group('corp')):
            tinta[k] = v.strip()
    return baza, dict(baza, **light)


def rezolva(nume, brut, adanc=0):
    """Expresia unui token -> RGB. Aliasuri si `color-mix` incluse."""
    if adanc > 12 or nume not in brut:
        return None
    v = brut[nume].strip()
    return _val(v, brut, adanc)


def _val(v, brut, adanc=0):
    v = v.strip()
    if adanc > 12:
        return None
    m = VAR.match(v)
    if m:
        return rezolva(m.group(1), brut, adanc + 1)
    m = MIX.match(v)
    if m:
        spatiu, a, pa, b = m.group(1), m.group(2), float(m.group(3)), m.group(4)
        # `transparent` nu se poate masura pe un fond necunoscut; rolurile care il
        # folosesc (`--accent-ring`) sunt inel de focus, nu text — si nu intra in
        # niciuna dintre perechi.
        if 'transparent' in (a, b):
            return None
        ca, cb = _val(a, brut, adanc + 1), _val(b, brut, adanc + 1)
        if ca is None or cb is None:
            return None
        return amesteca(spatiu, ca, pa, cb)
    if v.startswith('#'):
        return hex_rgb(v)
    m = re.match(r'rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)', v)
    if m:
        return tuple(float(m.group(i)) / 255 for i in (1, 2, 3))
    return None


# ------------------------------------------------------------- ce se verifica
# (cerneala, fond, prag, eticheta). Pragul e treapta WCAG a ROLULUI, nu una
# singura pentru tot: text mic 4,5; obiect de interfata sau text mare 3,0.
PERECHI = [
    # --- cerneala pe cele trei suprafete ---
    ('--text', '--bg', 4.5, 'text pe fond'),
    ('--text', '--bg-surface', 4.5, 'text pe suprafata'),
    ('--text', '--bg-elevated', 4.5, 'text pe camp'),
    ('--text-secondary', '--bg', 4.5, 'text secundar pe fond'),
    ('--text-secondary', '--bg-surface', 4.5, 'text secundar pe suprafata'),
    ('--text-dim', '--bg', 4.5, 'text estompat pe fond'),
    ('--text-dim', '--bg-surface', 4.5, 'text estompat pe suprafata'),
    ('--text-dim', '--bg-elevated', 4.5, 'text estompat pe camp'),

    # --- accentul, in cele TREI roluri ale lui ---
    # Exact cele care au cazut pe 2026-08-08 si pe care nicio regula scrisa nu le
    # numea: doua din trei nu erau acoperite de „text pe tenta ia varianta -deep".
    ('--accent', '--bg', 4.5, 'accent ca text pe fond'),
    ('--accent', '--bg-surface', 4.5, 'accent ca text pe suprafata'),
    ('--accent-text', '--accent', 4.5, 'cerneala pe fillul de accent'),
    ('--accent-deep', '--accent-subtle', 4.5, 'accent adanc pe tenta lui'),

    # --- stare: cerneala adanca pe tenta ei ---
    ('--danger-deep', '--danger-subtle', 4.5, 'restant pe tenta lui'),
    ('--success-deep', '--success-subtle', 4.5, 'facut pe tenta lui'),
    ('--danger', '--bg-surface', 4.5, 'restant ca text pe suprafata'),
    ('--success', '--bg-surface', 4.5, 'facut ca text pe suprafata'),

    # --- linii si obiecte de interfata (treapta de 3,0) ---
    ('--border-strong', '--bg-surface', 1.4, 'linia tare se vede pe suprafata'),
]

# Cele trei trepte de text trebuie sa se DEOSEBEASCA intre ele, altfel ierarhia
# declarata e o fictiune. Pragul de 1,4 e cel sub care perechea a fost declarata
# rupta in tokens.css (masurat atunci: 1,29 si 1,16).
TREPTE = [
    ('--text', '--text-secondary', 1.4, 'treapta 1 -> 2 se vede'),
    ('--text-secondary', '--text-dim', 1.4, 'treapta 2 -> 3 se vede'),
]


def verifica(brut, eticheta, tot=False):
    probleme = []
    linii = []
    for a, b, prag, nume in PERECHI + TREPTE:
        ca, cb = rezolva(a, brut), rezolva(b, brut)
        if ca is None or cb is None:
            linii.append(('SARI', nume, '%s / %s — nerezolvabil' % (a, b)))
            continue
        r = contrast(ca, cb)
        ok = r >= prag
        if not ok:
            probleme.append('%s: %s — %.2f, cere %.1f (%s pe %s)'
                            % (eticheta, nume, r, prag, rgb_hex(ca), rgb_hex(cb)))
        if tot or not ok:
            linii.append(('OK' if ok else 'PICA', nume,
                          '%.2f  (cere %.1f)  %s pe %s' % (r, prag, rgb_hex(ca), rgb_hex(cb))))
    return probleme, linii


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tot', action='store_true', help='si perechile care trec')
    ap.add_argument('--paleta', help='alt fisier de tokenuri (pentru a incerca o paleta)')
    a = ap.parse_args()

    cale = a.paleta or TOKENS
    dark, light = citeste(cale)

    print('CONTRAST — %s' % Path(cale).name)
    print('=' * 60)
    total = []
    for brut, eticheta in ((dark, 'intunecat'), (light, 'deschis')):
        probleme, linii = verifica(brut, eticheta, a.tot)
        print('\n--- tema %s ---' % eticheta)
        if not linii:
            print('  curat')
        for stare, nume, det in linii:
            print('  %-5s %-38s %s' % (stare, nume, det))
        total += probleme

    print('\n' + '=' * 60)
    if total:
        print('%d perechi sub prag' % len(total))
        return 1
    print('curat — toate perechile trec')
    return 0


if __name__ == '__main__':
    sys.exit(main())
