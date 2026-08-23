#!/usr/bin/env python3
"""Lint — ambele jumatati ale aplicatiei, dintr-o singura comanda.

De ce exista. Proiectul n-avea niciun lint: nici ESLint in `frontend/`, nici
ruff/flake8 pentru Python. Celelalte verificatoare pornesc Chromium si dureaza
minute; asta ruleaza in cateva secunde si prinde alta clasa de defect — nu „ce
crapa" si nu „ce nu incape", ci „ce e scris si nu ajunge niciodata sa se
intample".

Ce a gasit la prima rulare (2026-08-23), ca sa se vada ce fel de lucruri prinde:
  - doua variabile citite in markup dar declarate cu `let` simplu in mod runes
    (`editingChip` din RichTextEditor, `dragTask` din Plan): reasignarea NU
    redeseneaza, deci butonul ramanea pe eticheta veche si zona de drop nu se
    aprindea;
  - doua reguli CSS pe care compilatorul le TAIA din build fiindca nu putea
    verifica selectorul (`.trow-wrap.deschis .gl-fata`, `:global(.modal-body) >
    .td-jos`) — scrise, comentate, si absente din CSS-ul livrat;
  - un `svelte-ignore` cu doua coduri separate prin spatiu, care tace doar primul;
  - 31 de importuri neutilizate, dintre care iconite si componente intregi care
    intrau degeaba in bundle;
  - o variabila locala moarta in `blueprints/projects.py`.

Severitati. ERORI = are efect vizibil sau opreste build-ul. AVERTISMENTE =
curatenie. Implicit iese 1 la ORICE abatere, fiindca linia de baza e curata si
abia asa raportul ramane citibil; `--doar-erori` slabeste poarta cand ai nevoie.

    python scripts/lint.py                # tot, iese 1 la orice abatere
    python scripts/lint.py --doar-erori   # iese 1 doar la erori
    python scripts/lint.py --backend      # doar Python
    python scripts/lint.py --frontend     # doar SPA

Cerinte, doar pe masina de dezvoltare (NU in requirements.txt, ca playwright):
    pip install pyflakes
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
MOTOR_SPA = Path(__file__).resolve().parent / 'lint_svelte.mjs'

# Directoare care nu sunt codul nostru sau sunt generate.
EXCLUSE = {'node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'uploads'}

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


# ------------------------------------------------------------------ backend

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


# ----------------------------------------------------------------- frontend

def ruleaza_spa():
    """(erori, avertismente, scanate, problema_de_unealta)."""
    node = shutil.which('node') or shutil.which('node.exe')
    if not node:
        return [], [], None, 'node nu e in PATH — nu pot rula lintul de SPA'
    if not MOTOR_SPA.exists():
        return [], [], None, 'lipseste %s' % rel(MOTOR_SPA)

    mediu = dict(os.environ, PYTHONIOENCODING='utf-8')
    p = subprocess.run([node, str(MOTOR_SPA), '--json'], cwd=str(RADACINA),
                       env=mediu, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    brut = p.stdout.decode('utf-8', 'replace').strip()
    if not brut:
        return [], [], None, ('motorul de SPA n-a scos nimic (cod %d)\n    %s'
                              % (p.returncode, p.stderr.decode('utf-8', 'replace').strip()[:400]))
    try:
        d = json.loads(brut)
    except ValueError:
        return [], [], None, 'raspuns necitibil de la motorul de SPA:\n    ' + brut[:400]

    def ca_tupluri(lista):
        return [(x['file'], x['line'], x['code'], x['msg']) for x in lista]

    return ca_tupluri(d['erori']), ca_tupluri(d['avertismente']), d['scanate'], None


# --------------------------------------------------------------------- main

def tipareste(titlu, randuri):
    if not randuri:
        return
    print('\n%s (%d)' % (titlu, len(randuri)))
    for fis, linie, cod, mesaj in randuri:
        loc = '%s:%d' % (fis, linie) if linie else fis
        print('   %-46s [%s] %s' % (loc, cod, mesaj))


def main():
    ap = argparse.ArgumentParser(description='Lint pentru backend (pyflakes) si SPA (compilatorul Svelte).')
    ap.add_argument('--backend', action='store_true', help='doar Python')
    ap.add_argument('--frontend', action='store_true', help='doar SPA')
    ap.add_argument('--doar-erori', action='store_true', help='iesi 1 doar la erori')
    args = ap.parse_args()

    fa_backend = args.backend or not args.frontend
    fa_frontend = args.frontend or not args.backend

    erori, avert, unelte = [], [], []

    if fa_backend:
        fis = fisiere_python()
        e, a, problema = ruleaza_pyflakes(fis)
        print('Python: %d fisiere' % len(fis))
        if problema:
            unelte.append(problema)
        erori += e
        avert += a

    if fa_frontend:
        e, a, scanate, problema = ruleaza_spa()
        if scanate:
            print('SPA:    %d .svelte, %d .js' % (scanate['svelte'], scanate['js']))
        if problema:
            unelte.append(problema)
        erori += e
        avert += a

    tipareste('ERORI', erori)
    tipareste('AVERTISMENTE', avert)

    if unelte:
        print('\nNU AM PUTUT VERIFICA TOT:')
        for u in unelte:
            print('   ' + u)

    print('\n' + '=' * 60)
    if unelte:
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
