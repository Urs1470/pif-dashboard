#!/usr/bin/env python3
"""Stop hook: poarta de verificare a pif-dashboard.

De ce exista. Cele patru verificatoare (`audit_design`, `test_suite`, `smoke_ui`,
`audit_mobil`) sunt construite fiecare pe un mod de esec care trecea de build:
importul lipsa care lasa pagina pe schelet (27.07), butonul taiat de marginea
ecranului (30.07), a doua paleta rotita cu doua pozitii (30.07). Existau, dar
rularea lor era la discretia agentului — iar Ion nu revizuieste cod, deci
"criterii bifate" era o declaratie fara nimic care s-o contrazica. Poarta le
ruleaza automat, pe fisierele atinse de sesiune, si NU lasa tura sa se incheie
daca pica.

Ce ruleaza, dupa ce s-a atins:
    frontend/src/**.svelte|.css        -> audit_design
    blueprints/*.py, database.py, ...  -> test_suite
    frontend/src/**                    -> BUILD + smoke_ui + audit_mobil

Build-ul nu e optional. `smoke_ui` porneste Flask, care serveste `static/dist/`
— pe surse editate si neconstruite ar testa build-ul VECHI si ar da verde fals,
fix minciuna pe care poarta trebuie s-o prinda.

Doua plafoane, ca poarta sa nu se transforme in capcana:
  - dupa MAX_BLOCARI blocari intr-o sesiune nu mai blocheaza, doar raporteaza
    tare (contorul se reseteaza la prima trecere curata);
  - un Stop fara editari noi de la ultima trecere iese instant, fara sa rulele
    nimic.
"""
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

RADACINA = Path(__file__).resolve().parents[2]
STARE = RADACINA / '.claude' / '.state'
SCRIPTURI = RADACINA / 'scripts'

MAX_BLOCARI = 2          # a (MAX_BLOCARI+1)-a oara raporteaza, nu blocheaza
MAX_IESIRE = 3000        # caractere pastrate din coada iesirii unei porti
TIMP_MAX = 900           # secunde per poarta (audit_mobil e cel mai lung)

FISIERE_API = {'database.py', 'app.py', 'utils.py', 'labels.py', 'csrf.py'}


# ---------------------------------------------------------------- utilitare

def sid_curat(sid):
    curat = ''.join(c for c in str(sid) if c.isalnum() or c in '-_')
    return curat[:80] or 'fara-sesiune'


def iesi_curat():
    sys.exit(0)


def blocheaza(motiv):
    json.dump({'decision': 'block', 'reason': motiv}, sys.stdout)
    sys.exit(0)


def raporteaza(text):
    """Trece mai departe, dar imi baga textul in context."""
    json.dump({'hookSpecificOutput': {
        'hookEventName': 'Stop', 'additionalContext': text}}, sys.stdout)
    sys.exit(0)


def coada(text):
    text = (text or '').strip()
    return text if len(text) <= MAX_IESIRE else '…\n' + text[-MAX_IESIRE:]


# ------------------------------------------------------------------- porti

def npm():
    return shutil.which('npm.cmd') or shutil.which('npm')


def porti_pentru(atinse):
    """(eticheta, argv, cwd, cum-o-rulezi-manual) in ordine ieftin -> scump."""
    porti = []
    frontend = [p for p in atinse if p.startswith('frontend/src/')]

    if any(p.endswith(('.svelte', '.css')) for p in frontend):
        porti.append(('audit_design',
                      [sys.executable, str(SCRIPTURI / 'audit_design.py')],
                      RADACINA, 'python scripts/audit_design.py --lista'))

    if any(p.startswith('blueprints/') and p.endswith('.py') for p in atinse) \
            or any(p in FISIERE_API for p in atinse):
        porti.append(('test_suite',
                      [sys.executable, str(SCRIPTURI / 'test_suite.py')],
                      RADACINA, 'python scripts/test_suite.py'))

    # Lantul scump porneste pe .svelte/.js, NU pe .css singur — criteriul aprobat
    # de Ion e "doar CSS => doar audit_design, fara Chromium". Consecinta, scrisa
    # ca s-o vada cineva: o modificare doar in tokens.css/global.css nu trece pe
    # sub audit_mobil, adica exact clasa de defect a acelui script (bloc mobil
    # anulat de reguli scrise mai jos in fisier, 30.07). Ca sa se acopere si aia,
    # adauga '.css' in conditia de mai jos.
    if any(p.endswith(('.svelte', '.js')) for p in frontend):
        cmd = npm()
        if not cmd:
            porti.append(('build', None, None, 'npm run build (in frontend/)'))
        else:
            porti.append(('build', [cmd, 'run', 'build'],
                          RADACINA / 'frontend', 'npm run build (in frontend/)'))
        porti.append(('smoke_ui',
                      [sys.executable, str(SCRIPTURI / 'smoke_ui.py')],
                      RADACINA, 'python scripts/smoke_ui.py'))
        porti.append(('audit_mobil',
                      [sys.executable, str(SCRIPTURI / 'audit_mobil.py')],
                      RADACINA, 'python scripts/audit_mobil.py'))
    return porti


def ruleaza(argv, cwd):
    mediu = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    p = subprocess.run(argv, cwd=str(cwd), env=mediu, timeout=TIMP_MAX,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


# --------------------------------------------------------------------- main

def main():
    date = json.load(sys.stdin)

    # Subagentii au propriul Stop; poarta e a sesiunii principale.
    if date.get('agent_id'):
        iesi_curat()

    sid = sid_curat(date.get('session_id', ''))
    STARE.mkdir(parents=True, exist_ok=True)
    f_atinse = STARE / ('%s.touched' % sid)
    f_memo = STARE / ('%s.json' % sid)

    err = STARE / 'recorder.err'
    if err.exists():
        blocheaza(
            'Recorderul de fisiere atinse (PostToolUse) a crapat, deci poarta nu '
            'stie ce s-a modificat si NU are ce verifica. Nu declara nimic gata: '
            'arata-i lui Ion urma de mai jos si ruleaza manual verificatoarele '
            'potrivite.\n\n%s\n\n(sterge .claude/.state/recorder.err dupa ce e '
            'lamurit)' % coada(err.read_text(encoding='utf-8', errors='replace')))

    if not f_atinse.exists():
        iesi_curat()                              # sesiune fara editari

    atinse = sorted({r.strip() for r in
                     f_atinse.read_text(encoding='utf-8').splitlines() if r.strip()})
    if not atinse:
        iesi_curat()

    memo = {}
    if f_memo.exists():
        try:
            memo = json.loads(f_memo.read_text(encoding='utf-8'))
        except Exception:
            memo = {}

    # Semnatura = ce s-a atins + cand a fost scris ultima oara. Neschimbata de la
    # ultima trecere curata => nu mai are ce verifica, ies instant.
    semnatura = []
    for r in atinse:
        p = RADACINA / r
        semnatura.append('%s:%s' % (r, p.stat().st_mtime_ns if p.exists() else 0))
    semnatura = '|'.join(semnatura)
    if memo.get('semnatura_curata') == semnatura:
        iesi_curat()

    porti = porti_pentru(atinse)
    if not porti:
        iesi_curat()

    blocari = int(memo.get('blocari', 0))

    for eticheta, argv, cwd, manual in porti:
        if argv is None:                          # npm lipsa pe masina asta
            cod, iesire = 1, ('npm nu exista in PATH, deci build-ul Vite nu poate '
                              'rula. Fara build, smoke_ui ar testa static/dist/ '
                              'vechi si ar trece pe langa orice greseala din sursa.')
        else:
            try:
                cod, iesire = ruleaza(argv, cwd)
            except subprocess.TimeoutExpired:
                cod, iesire = 1, 'Poarta a depasit %d s si a fost oprita.' % TIMP_MAX
            except Exception:
                cod, iesire = 1, traceback.format_exc()

        if cod != 0:
            text = ('PORTA "%s" A PICAT (cod %d).\n\n'
                    'Fisiere atinse in sesiune:\n  %s\n\n'
                    'Reproduci cu:\n  %s\n\n--- iesire ---\n%s'
                    % (eticheta, cod, '\n  '.join(atinse), manual, coada(iesire)))

            if blocari >= MAX_BLOCARI:
                memo['blocari'] = blocari + 1
                f_memo.write_text(json.dumps(memo), encoding='utf-8')
                raporteaza(
                    'A %d-a picare in sesiunea asta — poarta NU mai blocheaza, ca '
                    'sa nu te inverti in gol. Nu inseamna ca a trecut: spune-i lui '
                    'Ion clar ce a ramas rosu.\n\n%s' % (blocari + 1, text))

            memo['blocari'] = blocari + 1
            f_memo.write_text(json.dumps(memo), encoding='utf-8')
            blocheaza(
                text + '\n\nNu incheia tura si nu raporta "gata": ori repari, ori '
                'ii spui lui Ion de ce pica si astepti. Daca esecul e din munca '
                'necomisa a altei sesiuni, spune asta explicit, nu-l repara tacut.')

    memo['blocari'] = 0                           # trecere curata => contor la zero
    memo['semnatura_curata'] = semnatura
    f_memo.write_text(json.dumps(memo), encoding='utf-8')
    raporteaza('Poarta a trecut: %s. Fisiere: %s.'
               % (', '.join(p[0] for p in porti), ', '.join(atinse)))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Poarta stricata nu are voie sa treaca drept poarta trecuta.
        blocheaza('Poarta insasi a crapat, deci NIMIC nu e verificat. Nu declara '
                  'gata.\n\n%s' % traceback.format_exc())
