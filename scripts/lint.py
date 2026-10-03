#!/usr/bin/env python3
"""Lint pentru Python (pyflakes), pe tot proiectul, dintr-o singura comanda.

De ce exista. Proiectul n-avea niciun lint. Asta ruleaza in cateva secunde si prinde o clasa
de defect pe care testele n-o vad — nu „ce crapa" si nu „ce nu incape", ci „ce e scris si nu
ajunge niciodata sa se intample": un nume nedefinit pe o ramura rar, o variabila locala moarta,
un import care nu se mai rezolva dupa o stergere. Ultima clasa e cea care conteaza dupa
retragerea interfetei vechi (2026-10-03): modulele scoase lasa importuri in urma, iar pyflakes
le arata imediat.

Prima rulare (2026-08-23) a gasit, printre altele, o variabila locala moarta in
`blueprints/projects.py`. Jumatatea de frontend (compilatorul Svelte) a plecat odata cu SPA-ul.

Severitati. ERORI = se strica la rulare. AVERTISMENTE = curatenie. Implicit iese 1 la ORICE
abatere, fiindca linia de baza e curata si abia asa raportul ramane citibil; `--doar-erori`
slabeste poarta cand ai nevoie.

    python scripts/lint.py                # iese 1 la orice abatere
    python scripts/lint.py --doar-erori   # iese 1 doar la erori

Cerinte, doar pe masina de dezvoltare (NU in requirements.txt):
    pip install pyflakes
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent

# Directoare care nu sunt codul nostru sau sunt generate.
EXCLUSE = {'node_modules', '__pycache__', '.git', 'venv', '.venv', 'uploads'}

# Mesajele pyflakes care inseamna „se strica la rulare", nu „e dezordine".
# `% ... placeholder(s)` e aici fiindca un `%` cu numar gresit de argumente ridica
# TypeError. Atentie: pyflakes numara o LISTA ca mai multe substitutii, desi lista
# nu se despacheteaza; daca dai peste asa ceva, scrie f-string, e si mai clar.
ERORI_PY = (
    'undefined name',
    'syntax',
    'referenced before assignment',
    'placeholder(s)',
    'used prior to global declaration',
    'outside function',
    'outside loop',
    'duplicate argument',
    'two starred expressions',
)


def fisiere_python():
    out = []
    for p in RADACINA.rglob('*.py'):
        if any(parte in EXCLUSE for parte in p.relative_to(RADACINA).parts):
            continue
        out.append(p)
    return sorted(out)


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(RADACINA)).replace('\\', '/')
    except ValueError:
        return str(p).replace('\\', '/')


def ruleaza_pyflakes(fisiere):
    """(erori, avertismente, problema_de_unealta)."""
    try:
        subprocess.run([sys.executable, '-m', 'pyflakes', '--version'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception:
        return [], [], ('pyflakes nu e instalat pentru %s.\n'
                        '    Instaleaza-l o data: pip install pyflakes' % sys.executable)

    linii = []
    # In transe: linia de comanda din Windows are o limita, iar repo-ul creste.
    for i in range(0, len(fisiere), 40):
        transa = [str(f) for f in fisiere[i:i + 40]]
        p = subprocess.run([sys.executable, '-m', 'pyflakes'] + transa,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        linii += p.stdout.decode('utf-8', 'replace').splitlines()

    erori, avert = [], []
    tipar = re.compile(r'^(.*?):(\d+):(?:(\d+):)?\s*(.*)$')
    for l in linii:
        l = l.rstrip()
        if not l:
            continue
        m = tipar.match(l)
        if not m:
            # pyflakes scrie si linii de context la erori de sintaxa; le pastram
            # ca sa nu dispara informatie, dar fara pozitie.
            erori.append(('?', 0, 'pyflakes', l.strip()))
            continue
        fis, linie, _, mesaj = m.groups()
        tinta = erori if any(k in mesaj.lower() for k in ERORI_PY) else avert
        tinta.append((rel(fis), int(linie), 'pyflakes', mesaj))
    return erori, avert, None


def tipareste(titlu, randuri):
    if not randuri:
        return
    print('\n%s (%d)' % (titlu, len(randuri)))
    for fis, linie, cod, mesaj in randuri:
        loc = '%s:%d' % (fis, linie) if linie else fis
        print('   %-46s [%s] %s' % (loc, cod, mesaj))


def main():
    ap = argparse.ArgumentParser(description='Lint pentru Python (pyflakes).')
    ap.add_argument('--doar-erori', action='store_true', help='iesi 1 doar la erori')
    args = ap.parse_args()

    fis = fisiere_python()
    erori, avert, problema = ruleaza_pyflakes(fis)
    print('Python: %d fisiere' % len(fis))

    tipareste('ERORI', erori)
    tipareste('AVERTISMENTE', avert)

    if problema:
        print('\nNU AM PUTUT VERIFICA TOT:')
        print('   ' + problema)

    print('\n' + '=' * 60)
    if problema:
        # O jumatate nerulata NU e o trecere. Un lint care tace arata la fel cu unul
        # care a trecut, si asta e singurul mod de esec pe care n-are voie sa-l aiba.
        print('lint incomplet — vezi mai sus')
        return 2
    if not erori and not avert:
        print('curat — nicio abatere')
        return 0
    print('%d erori, %d avertismente' % (len(erori), len(avert)))
    if erori:
        return 1
    return 0 if args.doar_erori else 1


if __name__ == '__main__':
    sys.exit(main())
