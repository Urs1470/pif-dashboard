#!/usr/bin/env python3
"""UN SINGUR PUNCT DE INTRARE PENTRU VERIFICATOARE.

    python scripts/verifica.py              # = --rapid
    python scripts/verifica.py --rapid      # lint, teste JS, teste Python, probele de API (~35 s)
    python scripts/verifica.py --atinse app.py blueprints/tasks.py
                                            # exact ce ar rula poarta pentru fisierele astea
    --continua                              # nu te opri la primul esec

DE CE EXISTA. Lista verificatoarelor statea in trei locuri (`CLAUDE.md`, antetul portii si
`porti_pentru` din ea) si cele trei nu mai spuneau acelasi lucru (auditul testelor,
2026-09-28). Acum lista e AICI, o data: poarta (`.claude/hooks/gate.py`) o importa
(`pasi_pentru`), iar `CLAUDE.md` descrie pasii, nu scripturile.

CE A PLECAT PE 2026-10-03, odata cu interfata veche: build-ul si lintul SPA-ului, testele JS
ale codului lui, auditurile de design si de contrast, `smoke_ui` si toate auditurile cu
browser (si bancul lor de Chromium din `banc.py`). Au ramas patru pasi, toti fara browser.
Cum se aduc inapoi: `docs/decizii/2026-10-03-retragerea-interfetei-vechi.md`.

ORDINEA E A COSTULUI: ce e ieftin si prinde mult merge primul, ca un esec sa se vada in
secunde.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from collections import namedtuple

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTURI = os.path.join(RADACINA, 'scripts')

FISIERE_API = {'database.py', 'app.py', 'utils.py', 'labels.py', 'csrf.py', 'backup_db.py'}

# `lipsa` = ce se spune cand pasul nu poate porni (argv None): unealta lui nu s-a gasit.
Pas = namedtuple('Pas', 'eticheta argv cwd manual lipsa')


# ------------------------------------------------------------------- mediul

def cai_persistente():
    """Directoarele din PATH-ul PERSISTENT (registru), pe langa cel mostenit.

    Pe unele masini Node-ul e portabil si sta DOAR in PATH-ul de utilizator din registru. Un
    proces pornit inainte ca intrarea sa fie adaugata nu-l vede — iar hookul mosteneste mediul
    aplicatiei, care poate fi deschisa de saptamani. Poarta ar spune atunci „node nu exista in
    PATH" si ar pica, desi comanda merge perfect intr-un terminal nou.
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


def gaseste_node():
    gasit = shutil.which('node.exe') or shutil.which('node')
    if gasit:
        return gasit
    supl = cai_persistente()
    if not supl:
        return None
    unde = os.pathsep.join(supl)
    return shutil.which('node.exe', path=unde) or shutil.which('node', path=unde)


def python_probe():
    """Interpretorul verificatoarelor: `venv/` daca exista (acelasi pe care il activeaza
    deployul), altfel cel curent. NU orbeste `sys.executable` din hook: pe unele masini
    python-ul de sistem n-are flask, iar poarta ar pica cu ModuleNotFoundError — rosu care
    nu spune NIMIC despre cod."""
    for rel in ('venv/Scripts/python.exe', 'venv/bin/python'):
        p = os.path.join(RADACINA, rel)
        if os.path.exists(p):
            return p
    return sys.executable


PYTHON = python_probe()
NODE = gaseste_node()
PY_MANUAL = 'venv\\Scripts\\python' if PYTHON != sys.executable else 'python'


def mediu():
    """Mediul proceselor copil: UTF-8 (consola Windows e cp1252 cand iesirea e redirectata)
    si directorul lui Node IN FATA PATH-ului, ca un `node` cerut de un test (test_login_next
    ruleaza `destinatie()` din pagina de login) sa fie gasit si el."""
    m = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    if NODE:
        dir_node = os.path.dirname(NODE)
        cale = m.get('PATH') or ''
        if dir_node and dir_node not in cale.split(os.pathsep):
            m['PATH'] = dir_node + os.pathsep + cale
    return m


# -------------------------------------------------------------------- pasii

def _py(script, *arg):
    return Pas(script, [PYTHON, os.path.join(SCRIPTURI, script + '.py')] + list(arg), RADACINA,
               '%s scripts/%s.py%s' % (PY_MANUAL, script, (' ' + ' '.join(arg)) if arg else ''), '')


def _teste_js():
    """Testele JS ale fisierelor pe care le serveste serverul (login.html, service-worker.js),
    cu runner-ul built-in al lui Node: fara npm, fara pachete. Fisierele se dau pe nume, nu ca
    sablon: un sablon intre ghilimele e expandat de Node abia din v21."""
    fisiere = sorted(glob.glob(os.path.join(RADACINA, 'teste', 'js', '*.test.mjs')))
    manual = 'node --test teste/js/*.test.mjs'
    if not fisiere:
        return Pas('unitare_js', None, RADACINA, manual,
                   'nu exista niciun teste/js/*.test.mjs: fara fisiere, `node --test` ar cauta '
                   'teste prin tot proiectul. Daca testele JS au plecat, scoate pasul din verifica.py.')
    if not NODE:
        return Pas('unitare_js', None, RADACINA, manual,
                   'node nu s-a gasit nici in PATH-ul mostenit, nici in cel persistent din '
                   'registru, deci `%s` nu poate rula. Verifica unde e instalat Node si '
                   'adauga-l in PATH-ul de utilizator.' % manual)
    return Pas('unitare_js', [NODE, '--test'] + fisiere, RADACINA, manual, '')


PASI = {
    'lint': _py('lint'),
    'unitare_js': _teste_js(),
    'unitare_py': Pas('unitare_py', [PYTHON, '-m', 'unittest', 'discover', '-s', 'teste'], RADACINA,
                      '%s -m unittest discover -s teste' % PY_MANUAL, ''),
    'test_suite': _py('test_suite'),
}

ORDINE = ['lint', 'unitare_js', 'unitare_py', 'test_suite']


def _backend(p):
    return (p.startswith('blueprints/') and p.endswith('.py')) or p in FISIERE_API


def _servit(p):
    """Fisierele pe care le serveste serverul si pe care le citesc teste: pagina de login si
    service worker-ul care se retrage."""
    return p in ('templates/login.html', 'static/service-worker.js')


def _test_js(p):
    return p.startswith('teste/js/') and p.endswith('.mjs')


def relevante(atinse):
    """Fisierele care pot declansa un pas — doar ele intra in semnatura portii.

    Tine pasul cu `pasi_pentru`: un criteriu nou acolo apare si aici, altfel o modificare ar
    declansa un pas fara sa intre in semnatura, si poarta ar rula la nesfarsit. Documentatia
    nu intra: nu poate strica nici un test, nici o proba.
    """
    return [p for p in atinse if p.endswith('.py') or _servit(p) or _test_js(p)]


def pasi_pentru(atinse):
    """Pasii pe care ii cer fisierele atinse, in ordinea costului."""
    backend = any(_backend(p) for p in atinse)
    servit = any(_servit(p) for p in atinse)
    scripturi = {os.path.basename(p)[:-3] for p in atinse
                 if p.startswith('scripts/') and p.endswith('.py')}
    banc = 'banc' in scripturi

    alese = set()
    if any(p.endswith('.py') for p in atinse):
        alese.add('lint')
    if servit or any(_test_js(p) for p in atinse):
        alese.add('unitare_js')
    if backend or banc or servit or any(p.startswith('teste/') and p.endswith('.py') for p in atinse):
        alese.add('unitare_py')
    # `test_suite` porneste serverul real pe `banc.py`: o schimbare in banc le poate strica pe amandoua.
    if backend or banc or 'test_suite' in scripturi:
        alese.add('test_suite')
    return [PASI[k] for k in ORDINE if k in alese]


def pasi_rapid():
    return [PASI[k] for k in ORDINE]


# --------------------------------------------------------------------- rulare

def ruleaza_pas(pas, limita=None):
    """(cod, iesire). `argv` None = unealta lipseste (node), ceea ce e un esec: un pas
    sarit tacut arata exact ca unul trecut, si asta e singurul mod de esec interzis."""
    if pas.argv is None:
        return 2, pas.lipsa
    p = subprocess.run(pas.argv, cwd=pas.cwd, env=mediu(), timeout=limita,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def _scrie(s=''):
    sys.stdout.buffer.write((str(s) + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description='Toate verificatoarele, dintr-un loc.')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--rapid', action='store_true', help='toti pasii (implicit)')
    g.add_argument('--atinse', nargs='+', metavar='FISIER', help='ce ar rula poarta pentru fisierele astea')
    ap.add_argument('--continua', action='store_true', help='nu te opri la primul esec')
    arg = ap.parse_args()

    if arg.atinse:
        atinse = [os.path.relpath(os.path.abspath(p), RADACINA).replace('\\', '/') for p in arg.atinse]
        pasi = pasi_pentru(atinse)
        titlu = 'pentru %d fisier(e)' % len(atinse)
    else:
        pasi = pasi_rapid()
        titlu = 'treapta rapid'
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
