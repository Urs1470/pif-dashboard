#!/usr/bin/env python3
"""Audit al sistemului de design — culoare, miscare, stari.

De ce exista. `smoke_ui.py` prinde ce CRAPA, `audit_mobil.py` prinde ce nu incape.
Niciunul nu poate prinde ce e doar INCOERENT: o a doua paleta copiata in alta pagina
si rotita cu doua pozitii se randeaza perfect, trece testele si arata bine in
izolare — se vede doar cand pui doua ecrane alaturi. Exact asa a trait luni de zile
divergenta dintre Calendar si Planificator: 43% dintre proiecte aveau doua culori.

Regulile de mai jos sunt cele pe care le-am incalcat efectiv, nu o lista de bune
practici luata de undeva. Fiecare are un comentariu cu ce s-a stricat.

    python scripts/audit_design.py            # raporteaza, iese 1 daca sunt abateri
    python scripts/audit_design.py --lista    # si listeaza fiecare aparitie
"""
import argparse
import re
import sys
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
SRC = RADACINA / 'frontend' / 'src'
TOKENS = SRC / 'styles' / 'tokens.css'

# Tokenuri de culoare definite O SINGURA data, cu buna stiinta: rolul lor e FILL
# sub cerneala inchisa, iar un fill de mijloc merge la fel in ambele teme. Daca le
# redefinesti pe light le inchizi, si banda ajunge inchisa cu text inchis pe ea
# (s-a intamplat exact asa la prima incercare).
INDEPENDENTE_DE_TEMA = {'--loc-site', '--loc-sediu', '--on-color'}

# Fisiere in care valorile brute sunt legitime, cu motiv.
SCUTITE_HEX = {
    # Sursa unica a paletei de identitate — aici valorile TREBUIE sa fie brute.
    'lib/culori.js',
    # Pagina embed-uita a planului de departament: iframe strain, fara tokenurile noastre.
    'pages/Departament.svelte',
}


def fisiere():
    for p in sorted(SRC.rglob('*.svelte')):
        yield p
    for p in sorted(SRC.rglob('*.css')):
        yield p


def rel(p):
    return str(p.relative_to(SRC))


def fara_comentarii(text):
    """Neutralizeaza comentariile CSS/JS ca sa nu raportam exemple din explicatii.

    Le inlocuieste cu spatii de aceeasi lungime, PASTRAND liniile noi: altfel
    pozitiile se decaleaza si raportul arata numere de linie care nu exista in
    fisierul real (prima versiune a facut exact asta si a trimis la randuri
    nevinovate)."""
    def goleste(m):
        return re.sub(r'[^\n]', ' ', m.group(0))
    text = re.sub(r'/\*.*?\*/', goleste, text, flags=re.S)
    text = re.sub(r'(?m)//[^\n]*', goleste, text)
    return text


def blocuri_print(text):
    """Intervalele acoperite de @media print — acolo cerneala inchisa e corecta
    indiferent de tema, pentru ca hartia e alba."""
    spans = []
    for m in re.finditer(r'@media\s+print[^{]*\{', text):
        i, adanc = m.end(), 1
        while i < len(text) and adanc:
            if text[i] == '{':
                adanc += 1
            elif text[i] == '}':
                adanc -= 1
            i += 1
        spans.append((m.start(), i))
    return spans


def in_span(poz, spans):
    return any(a <= poz < b for a, b in spans)


class Audit:
    def __init__(self):
        self.abateri = []       # (regula, fisier, linie, fragment)

    def abatere(self, regula, p, text, poz, fragment):
        linie = text.count('\n', 0, poz) + 1
        self.abateri.append((regula, rel(p), linie, fragment.strip()[:100]))

    # -- R1 -----------------------------------------------------------------
    def r1_transition_all(self, p, text, curat):
        """`transition: all` urmareste si proprietatile care reaseaza pagina
        (width/height/padding), animate pe firul principal. Foloseste
        var(--transition-colors) sau var(--transition-pressable)."""
        for m in re.finditer(r'transition:\s*all\b', curat):
            self.abatere('R1 transition:all', p, curat, m.start(), m.group(0))

    # -- R2 -----------------------------------------------------------------
    def r2_hex_brut(self, p, text, curat):
        """Culoare scrisa de mana in loc de token. Asa au aparut TREI ambere
        diferite pentru acelasi „sediu" (#c99a3a, #b98a2e, #c9a13a)."""
        if rel(p) in SCUTITE_HEX or p.name == 'tokens.css':
            return
        printuri = blocuri_print(curat)
        for m in re.finditer(r'#[0-9a-fA-F]{3,8}\b', curat):
            val = m.group(0).lower()
            # #fff/#000 in color-mix sunt operatii de deschidere/inchidere, nu culori.
            inainte = curat[max(0, m.start() - 90):m.start()]
            # In `color-mix` alb/negru sunt operatii de deschidere/inchidere.
            # Intr-o MASCA (`mask-image`) negrul nu e culoare, e canalul alfa:
            # „aici se vede". Nu se schimba cu tema si n-are token.
            if val in ('#fff', '#000', '#ffffff', '#000000') and (
                    'color-mix' in inainte or 'mask-image' in inainte):
                continue
            if in_span(m.start(), printuri):
                continue
            self.abatere('R2 hex brut', p, curat, m.start(), m.group(0))

    # -- R3 -----------------------------------------------------------------
    def r3_durata_bruta(self, p, text, curat):
        """Durata scrisa in cifre intr-o tranzitie: scara de miscare se
        desincronizeaza pe tacute. Foloseste var(--dur-fast/base/slow/press)."""
        if p.name == 'tokens.css':
            return
        for m in re.finditer(r'transition:[^;{}]*', curat):
            frag = m.group(0)
            for d in re.finditer(r'(?<![\w-])\d*\.?\d+m?s\b', frag):
                self.abatere('R3 durata bruta', p, curat, m.start(), frag)
                break

    # -- R4 -----------------------------------------------------------------
    def r4_easing_brut(self, p, text, curat):
        """cubic-bezier scris de mana in loc de var(--ease)."""
        if p.name == 'tokens.css':
            return
        for m in re.finditer(r'cubic-bezier\(', curat):
            self.abatere('R4 easing brut', p, curat, m.start(), 'cubic-bezier(...)')

    # -- R5 -----------------------------------------------------------------
    def r5_paleta_duplicata(self, p, text, curat):
        """O a doua paleta de identitate in afara lib/culori.js. Regula asta
        exista din cauza divergentei Calendar <-> Planificator."""
        if rel(p) in SCUTITE_HEX:
            return
        for m in re.finditer(r'\[\s*(?:\'#[0-9a-fA-F]{3,8}\'\s*,\s*){2,}', curat):
            self.abatere('R5 paleta duplicata', p, curat, m.start(), m.group(0))


def tokenuri_definite(text):
    """Tokenurile declarate, pe bloc de tema."""
    blocuri = {}
    for m in re.finditer(r'(:root[^{]*|\[data-theme="[^"]+"\][^{]*)\{(.*?)\n\}', text, re.S):
        nume = m.group(1).strip()
        blocuri[nume] = set(re.findall(r'(--[\w-]+)\s*:', m.group(2)))
    return blocuri


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lista', action='store_true', help='listeaza fiecare aparitie')
    args = ap.parse_args()

    if not SRC.exists():
        print(f'nu gasesc {SRC}', file=sys.stderr)
        return 2

    a = Audit()
    texte = {}
    for p in fisiere():
        text = p.read_text(encoding='utf-8')
        texte[p] = text
        curat = fara_comentarii(text)
        a.r1_transition_all(p, text, curat)
        a.r2_hex_brut(p, text, curat)
        a.r3_durata_bruta(p, text, curat)
        a.r4_easing_brut(p, text, curat)
        a.r5_paleta_duplicata(p, text, curat)

    # -- R6: tokenuri folosite dar nedefinite -------------------------------
    tk = TOKENS.read_text(encoding='utf-8')
    blocuri = tokenuri_definite(tk)
    definite = set().union(*blocuri.values()) if blocuri else set()
    # tokenurile derivate din env()/definite local in componente sunt permise
    locale = set()
    for p, text in texte.items():
        locale |= set(re.findall(r'(--[\w-]+)\s*:', text))
    folosite = {}
    for p, text in texte.items():
        for m in re.finditer(r'var\(\s*(--[\w-]+)', text):
            folosite.setdefault(m.group(1), []).append(p)
    nedefinite = sorted(t for t in folosite if t not in definite and t not in locale)

    # -- R7: paritate intre teme -------------------------------------------
    dark = blocuri.get(':root,\n[data-theme="dark"]') or next(
        (v for k, v in blocuri.items() if 'dark' in k or k.startswith(':root')), set())
    light = next((v for k, v in blocuri.items() if 'light' in k), set())
    # Tokenurile de culoare trebuie sa existe in ambele teme; scarile structurale
    # (spacing/typography/z-index) se definesc o singura data, in :root.
    culoare = re.compile(r'--(accent|bg|text|border|success|warning|danger|info|purple|service|chart|loc|on-color|shadow)')
    doar_dark = sorted(t for t in dark - light
                       if culoare.match(t) and t not in INDEPENDENTE_DE_TEMA)

    # -- raport -------------------------------------------------------------
    print('AUDIT SISTEM DE DESIGN\n' + '=' * 60)
    reguli = {}
    for regula, f, l, frag in a.abateri:
        reguli.setdefault(regula, []).append((f, l, frag))

    total = 0
    for regula in sorted(reguli):
        ap_ = reguli[regula]
        total += len(ap_)
        print(f'\n{regula}: {len(ap_)}')
        aratate = ap_ if args.lista else ap_[:5]
        for f, l, frag in aratate:
            print(f'   {f}:{l}  {frag}')
        if not args.lista and len(ap_) > 5:
            print(f'   … si inca {len(ap_) - 5} (--lista pentru toate)')

    if nedefinite:
        total += len(nedefinite)
        print(f'\nR6 token folosit dar nedefinit: {len(nedefinite)}')
        for t in nedefinite:
            print(f'   {t}  (in {rel(folosite[t][0])})')

    if doar_dark:
        total += len(doar_dark)
        print(f'\nR7 token de culoare doar in tema dark: {len(doar_dark)}')
        for t in doar_dark:
            print(f'   {t}')

    print('\n' + '=' * 60)
    if total == 0:
        print('curat — nicio abatere')
        return 0
    print(f'{total} abateri')
    return 1


if __name__ == '__main__':
    sys.exit(main())
