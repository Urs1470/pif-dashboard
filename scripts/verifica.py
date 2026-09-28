#!/usr/bin/env python3
"""UN SINGUR PUNCT DE INTRARE PENTRU TOATE VERIFICATOARELE.

    python scripts/verifica.py              # = --rapid
    python scripts/verifica.py --rapid      # secunde: lint, design, contrast, teste unitare, API
    python scripts/verifica.py --poarta     # ce ruleaza poarta la o schimbare de interfata
    python scripts/verifica.py --complet    # tot, inclusiv auditurile care nu stau in poarta
    python scripts/verifica.py --atinse frontend/src/pages/Home.svelte blueprints/tasks.py
                                            # exact ce ar rula poarta pentru fisierele astea
    --continua                              # nu te opri la primul esec

DE CE EXISTA (auditul testelor, 2026-09-28). Lista verificatoarelor statea in trei
locuri — `CLAUDE.md`, antetul portii si `porti_pentru` din ea — si cele trei nu mai
spuneau acelasi lucru: documentatia omitea `audit_tastatura` din poarta si
`audit_ferestre` cu totul, iar cele mai ieftine teste (unitare JS, probele de API)
nu rulau automat nicaieri. Acum lista e AICI, o data: poarta (`.claude/hooks/gate.py`)
o importa (`pasi_pentru`), iar `CLAUDE.md` descrie treptele, nu scripturile.

ORDINEA E A COSTULUI: ce e ieftin si prinde mult merge primul, ca un esec sa se vada
in secunde, nu dupa trei minute de Chromium.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from collections import namedtuple

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTURI = os.path.join(RADACINA, 'scripts')
FRONTEND = os.path.join(RADACINA, 'frontend')

FISIERE_API = {'database.py', 'app.py', 'utils.py', 'labels.py', 'csrf.py', 'backup_db.py'}

Pas = namedtuple('Pas', 'eticheta argv cwd manual')


# ------------------------------------------------------------------- mediul

def cai_persistente():
    """Directoarele din PATH-ul PERSISTENT (registru), pe langa cel mostenit.

    Node-ul de pe masina lui Ion e portabil (`Tools\\node-v24...`) si sta DOAR in
    PATH-ul de utilizator din registru. Un proces pornit inainte ca intrarea sa fie
    adaugata nu-l vede — iar hookul mosteneste mediul aplicatiei, care poate fi
    deschisa de saptamani. Poarta spunea atunci „npm nu exista in PATH" si pica,
    desi `npm run build` merge perfect intr-un terminal nou.
    """
    if os.name != 'nt':
        return []
    try:
        import winreg
    except Exception:
        return []
    cai = []
    for radacina, cheie in (
        (winreg.HKEY_CURRENT_USER, r'Environment'),
        (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
    ):
        try:
            with winreg.OpenKey(radacina, cheie) as k:
                val, _ = winreg.QueryValueEx(k, 'Path')
        except OSError:
            continue
        cai += [os.path.expandvars(d).strip('"') for d in str(val).split(os.pathsep) if d.strip()]
    return cai


def gaseste_npm():
    gasit = shutil.which('npm.cmd') or shutil.which('npm')
    if gasit:
        return gasit
    supl = cai_persistente()
    if not supl:
        return None
    unde = os.pathsep.join(supl)
    return shutil.which('npm.cmd', path=unde) or shutil.which('npm', path=unde)


def python_probe():
    """Interpretorul verificatoarelor: `venv/` daca exista (acelasi pe care il activeaza
    deployul), altfel cel curent. NU orbeste `sys.executable` din hook: pe unele masini
    python-ul de sistem n-are nici flask, nici playwright, iar poarta ar pica cu
    ModuleNotFoundError — rosu care nu spune NIMIC despre cod."""
    for rel in ('venv/Scripts/python.exe', 'venv/bin/python'):
        p = os.path.join(RADACINA, rel)
        if os.path.exists(p):
            return p
    return sys.executable


PYTHON = python_probe()
NPM = gaseste_npm()
PY_MANUAL = 'venv\\Scripts\\python' if PYTHON != sys.executable else 'python'


def mediu():
    """Mediul proceselor copil: UTF-8 (consola Windows e cp1252 cand iesirea e
    redirectata) si directorul lui Node IN FATA PATH-ului — `npm.cmd` e un shim care
    cheama `node` din PATH, deci fara el build-ul murea cu `'"node"' is not recognized`."""
    m = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    if NPM:
        dir_node = os.path.dirname(NPM)
        cale = m.get('PATH') or ''
        if dir_node and dir_node not in cale.split(os.pathsep):
            m['PATH'] = dir_node + os.pathsep + cale
    return m


# -------------------------------------------------------------------- pasii

def _py(script, *arg, manual_arg=''):
    return Pas(script, [PYTHON, os.path.join(SCRIPTURI, script + '.py')] + list(arg), RADACINA,
               '%s scripts/%s.py%s' % (PY_MANUAL, script, (' ' + manual_arg) if manual_arg else
                                      (' ' + ' '.join(arg) if arg else '')))


def _npm(eticheta, *arg):
    manual = 'npm %s (in frontend/)' % ' '.join(arg)
    return Pas(eticheta, [NPM] + list(arg) if NPM else None, FRONTEND, manual)


PASI = {
    'lint': _py('lint'),
    'audit_design': _py('audit_design', manual_arg='--lista'),
    'audit_contrast': _py('audit_contrast'),
    'unitare_js': _npm('unitare_js', 'test'),
    'unitare_py': Pas('unitare_py', [PYTHON, '-m', 'unittest', 'discover', '-s', 'teste'], RADACINA,
                      '%s -m unittest discover -s teste' % PY_MANUAL),
    'test_suite': _py('test_suite'),
    'build': _npm('build', 'run', 'build'),
    # In poarta: un proiect din fiecare fel (37 s); turul complet (toate proiectele)
    # e al treptei `--complet` — vezi antetul lui smoke_ui.py.
    'smoke_ui': _py('smoke_ui', '--esantion'),
    'smoke_ui_complet': _py('smoke_ui'),
    'audit_mobil': _py('audit_mobil'),
    'audit_tastatura': _py('audit_tastatura'),
    'audit_navigare': _py('audit_navigare'),
    'audit_foaie': _py('audit_foaie'),
    'audit_reactivitate': _py('audit_reactivitate'),
    'audit_ferestre': _py('audit_ferestre'),
}
PASI['smoke_ui_complet'] = PASI['smoke_ui_complet']._replace(eticheta='smoke_ui_complet')

ORDINE = ['lint', 'audit_design', 'audit_contrast', 'unitare_js', 'unitare_py', 'test_suite',
          'build', 'smoke_ui', 'smoke_ui_complet', 'audit_mobil', 'audit_tastatura',
          'audit_foaie', 'audit_reactivitate', 'audit_navigare', 'audit_ferestre']

TREPTE = {
    'rapid': ['lint', 'audit_design', 'audit_contrast', 'unitare_js', 'unitare_py', 'test_suite'],
    'poarta': ['lint', 'audit_design', 'audit_contrast', 'unitare_js', 'unitare_py', 'test_suite',
               'build', 'smoke_ui', 'audit_mobil', 'audit_tastatura'],
    'complet': ['lint', 'audit_design', 'audit_contrast', 'unitare_js', 'unitare_py', 'test_suite',
                'build', 'smoke_ui_complet', 'audit_mobil', 'audit_tastatura', 'audit_foaie',
                'audit_reactivitate', 'audit_navigare', 'audit_ferestre'],
}

# Verificatoarele cu browser — toate stau pe `banc.py`, deci o schimbare acolo le
# poate strica pe toate, inclusiv pe cele care nu sunt in poarta.
CU_BROWSER = ('smoke_ui', 'audit_mobil', 'audit_tastatura', 'audit_foaie',
              'audit_reactivitate', 'audit_navigare', 'audit_ferestre')


def _backend(p):
    return (p.startswith('blueprints/') and p.endswith('.py')) or p in FISIERE_API


def relevante(atinse):
    """Fisierele care pot declansa un pas — doar ele intra in semnatura portii.

    Tine pasul cu `pasi_pentru`: un criteriu nou acolo apare si aici, altfel o
    modificare ar declansa un pas fara sa intre in semnatura, si poarta ar rula
    la nesfarsit. Documentatia nu intra: nu poate strica nici build-ul, nici
    geometria de pe telefon.
    """
    return [p for p in atinse
            if (p.startswith('frontend/src/') and p.endswith(('.svelte', '.css', '.js')))
            or p.endswith('.py')
            or p == 'scripts/lint_svelte.mjs']


def pasi_pentru(atinse):
    """Pasii pe care ii cer fisierele atinse, in ordinea costului."""
    fe = [p for p in atinse if p.startswith('frontend/src/')]
    # Ce ajunge in bundle. Testele nu ajung: o modificare DOAR intr-un `*.test.js`
    # ruleaza testele, nu build-ul si trei minute de Chromium.
    spa = any(p.endswith(('.svelte', '.js')) and not p.endswith('.test.js') for p in fe)
    stil = any(p.endswith(('.svelte', '.css')) for p in fe)
    lib = any(p.startswith('frontend/src/lib/') and p.endswith('.js') for p in fe)
    backend = any(_backend(p) for p in atinse)
    scripturi = {os.path.basename(p)[:-3] for p in atinse
                 if p.startswith('scripts/') and p.endswith('.py')}
    banc = 'banc' in scripturi

    alese = set()
    if fe or any(p.endswith('.py') for p in atinse) or 'scripts/lint_svelte.mjs' in atinse:
        alese.add('lint')
    # Doar CSS => doar audit_design si contrast, fara Chromium (criteriul aprobat de
    # Ion). Consecinta, scrisa ca s-o vada cineva: o modificare doar in tokens.css /
    # global.css nu trece prin audit_mobil.
    if stil:
        alese |= {'audit_design', 'audit_contrast'}
    if lib:
        alese.add('unitare_js')
    if backend or banc or any(p.startswith('teste/') for p in atinse):
        alese.add('unitare_py')
    if backend or banc or 'test_suite' in scripturi:
        alese.add('test_suite')
    if spa:
        alese.add('build')
    # smoke_ui si pe backend: el prinde ruta care da 500 dupa o curatenie in
    # blueprints (gantt.pdf a stat rupt din v32 fara ca nimic sa-l atinga).
    if spa or backend:
        alese.add('smoke_ui')
    if spa:
        alese |= {'audit_mobil', 'audit_tastatura'}
    # Un verificator atins se ruleaza: altfel poarta ar trece peste chiar proba pe
    # care ai schimbat-o. `banc.py` le atinge pe toate.
    for nume in CU_BROWSER:
        if banc or nume in scripturi:
            alese.add(nume)
    if 'audit_foaie' in scripturi:        # audit_tastatura ii importa bucati
        alese.add('audit_tastatura')
    return [PASI[k] for k in ORDINE if k in alese]


def pasi_treapta(treapta):
    return [PASI[k] for k in ORDINE if k in TREPTE[treapta]]


# --------------------------------------------------------------------- rulare

def ruleaza_pas(pas, limita=None):
    """(cod, iesire). `argv` None = unealta lipseste (npm), ceea ce e un esec: fara
    build, smoke_ui ar testa static/dist/ vechi si ar trece pe langa orice."""
    if pas.argv is None:
        return 2, ('npm nu s-a gasit nici in PATH-ul mostenit, nici in cel persistent din '
                   'registru, deci `%s` nu poate rula. Verifica unde e instalat Node si '
                   'adauga-l in PATH-ul de utilizator.' % pas.manual)
    p = subprocess.run(pas.argv, cwd=pas.cwd, env=mediu(), timeout=limita,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def _scrie(s=''):
    sys.stdout.buffer.write((str(s) + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description='Toate verificatoarele, dintr-un loc.')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--rapid', action='store_true', help='secunde (implicit)')
    g.add_argument('--poarta', action='store_true', help='ce ruleaza poarta la o schimbare de interfata')
    g.add_argument('--complet', action='store_true', help='tot')
    g.add_argument('--atinse', nargs='+', metavar='FISIER', help='ce ar rula poarta pentru fisierele astea')
    ap.add_argument('--continua', action='store_true', help='nu te opri la primul esec')
    arg = ap.parse_args()

    if arg.atinse:
        atinse = [os.path.relpath(os.path.abspath(p), RADACINA).replace('\\', '/') for p in arg.atinse]
        pasi = pasi_pentru(atinse)
        titlu = 'pentru %d fisier(e)' % len(atinse)
    else:
        treapta = 'poarta' if arg.poarta else 'complet' if arg.complet else 'rapid'
        pasi = pasi_treapta(treapta)
        titlu = 'treapta %s' % treapta
    if not pasi:
        _scrie('Nimic de rulat %s.' % titlu)
        return 0

    _scrie('VERIFICA — %s: %s\n' % (titlu, ', '.join(p.eticheta for p in pasi)))
    rezultate = []
    for pas in pasi:
        t0 = time.monotonic()
        try:
            cod, iesire = ruleaza_pas(pas)
        except Exception as e:
            cod, iesire = 2, 'nu s-a putut porni: %s' % e
        dt = time.monotonic() - t0
        rezultate.append((pas, cod, dt))
        _scrie('  %-5s %-18s %6.1f s%s' % ('OK' if cod == 0 else 'PICA', pas.eticheta, dt,
                                           '' if cod == 0 else '  (cod %d)' % cod))
        if cod != 0:
            coada = iesire.strip().splitlines()[-60:]
            _scrie('\n        --- %s, ultimele %d linii ---' % (pas.eticheta, len(coada)))
            for l in coada:
                _scrie('        ' + l)
            _scrie('        Reproduci cu: %s\n' % pas.manual)
            if not arg.continua:
                break

    picate = [p.eticheta for p, cod, _ in rezultate if cod != 0]
    ramase = [p.eticheta for p in pasi[len(rezultate):]]
    total = sum(dt for _, _, dt in rezultate)
    _scrie()
    if ramase:
        _scrie('Nerulate (oprit la primul esec; --continua le ruleaza): %s' % ', '.join(ramase))
    if picate:
        _scrie('PICA — %s, in %.0f s.' % (', '.join(picate), total))
        return 1
    _scrie('OK — %d pasi curati, in %.0f s.' % (len(rezultate), total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
