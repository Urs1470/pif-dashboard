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
    orice .py, orice frontend/src/**   -> lint (secunde; pyflakes + Svelte)
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
# Buget TOTAL, sub timeout-ul hook-ului din settings.json (900 s). Fara el, cinci porti
# a cate 900 s puteau insuma 75 de minute, iar harness-ul ar fi omorat hook-ul la 900 —
# adica tura s-ar fi incheiat FARA VERDICT. O poarta care tace arata exact ca una care
# a trecut, si asta e singurul mod de esec pe care poarta n-are voie sa-l aiba.
TIMP_TOTAL = 780         # 13 min; restul pana la 900 ramane pentru raportare

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

def cai_persistente():
    """Directoarele din PATH-ul PERSISTENT (registru), pe langa cel mostenit.

    Node-ul de pe masina lui Ion e portabil (`Tools\\node-v24...`) si sta DOAR in
    PATH-ul de utilizator din registru. Un proces pornit inainte ca intrarea sa
    fie adaugata nu-l vede — iar hookul mosteneste mediul aplicatiei, care poate
    fi deschisa de saptamani. Poarta spunea atunci „npm nu exista in PATH" si
    pica, desi `npm run build` merge perfect intr-un terminal nou.

    O poarta care da un verdict FALS e mai rea decat lipsa portii: te invata s-o
    ignori, si atunci nu mai prinde nici esecurile adevarate.
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
        (winreg.HKEY_LOCAL_MACHINE,
         r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
    ):
        try:
            with winreg.OpenKey(radacina, cheie) as k:
                val, _ = winreg.QueryValueEx(k, 'Path')
        except OSError:
            continue
        cai += [os.path.expandvars(d).strip('"')
                for d in str(val).split(os.pathsep) if d.strip()]
    return cai


def npm():
    gasit = shutil.which('npm.cmd') or shutil.which('npm')
    if gasit:
        return gasit
    supl = cai_persistente()
    if not supl:
        return None
    unde = os.pathsep.join(supl)
    return shutil.which('npm.cmd', path=unde) or shutil.which('npm', path=unde)


def python_probe():
    """Interpretorul cu care se ruleaza verificatoarele.

    NU `sys.executable`: hookul porneste cu `python`-ul de sistem, care pe masina
    asta n-are nici flask, nici playwright. `smoke_ui` n-ar putea nici macar sa
    porneasca aplicatia si ar pica cu ModuleNotFoundError — o poarta rosie care
    nu spune NIMIC despre cod, exact felul de esec care face poarta de necrezut.
    Mediul proiectului e `venv/`, acelasi pe care il activeaza si deployul.
    Cadem inapoi pe `sys.executable` doar daca venv-ul nu exista.
    """
    for rel in ('venv/Scripts/python.exe', 'venv/bin/python'):
        p = RADACINA / rel
        if p.exists():
            return str(p)
    return sys.executable


PYTHON = python_probe()
NPM = npm()
# Cum o rulezi cu mana, ca linia din raport sa fie chiar cea care merge.
PY_MANUAL = 'venv\\Scripts\\python' if PYTHON != sys.executable else 'python'


def mediu_probe():
    """Mediul proceselor copil: PATH-ul mostenit + directorul in care sta Node.

    `npm.cmd` NU e autonom — e un shim care cheama `node` din PATH. Gasirea lui
    npm in registru rezolva doar jumatatea de sus: procesul copil mostenea tot
    PATH-ul vechi si pica cu `'"node"' is not recognized`, adica poarta ajungea
    sa ruleze build-ul doar ca sa-l vada murind dintr-un motiv care n-are nicio
    legatura cu codul. Directorul lui npm se pune IN FATA, ca `node`-ul de langa
    el sa fie cel folosit.
    """
    mediu = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    if NPM:
        dir_node = os.path.dirname(NPM)
        cale = mediu.get('PATH') or ''
        if dir_node and dir_node not in cale.split(os.pathsep):
            mediu['PATH'] = dir_node + os.pathsep + cale
    return mediu


def relevante(atinse):
    """Subsetul care poate declansa o poarta — restul nu conteaza pentru semnatura.

    Tine pasul cu `porti_pentru`: daca acolo apare un criteriu nou de fisier,
    apare si aici, altfel o modificare ar declansa o poarta fara sa intre in
    semnatura si poarta ar rula la nesfarsit.
    """
    return [p for p in atinse
            if (p.startswith('frontend/src/') and p.endswith(('.svelte', '.css', '.js')))
            or p.endswith('.py')
            or p in FISIERE_API]


def porti_pentru(atinse):
    """(eticheta, argv, cwd, cum-o-rulezi-manual) in ordine ieftin -> scump."""
    porti = []
    frontend = [p for p in atinse if p.startswith('frontend/src/')]
    backend = [p for p in atinse
               if (p.startswith('blueprints/') and p.endswith('.py'))
               or p in FISIERE_API]

    # Sursele care ajung in bundle. NU si .css singur: criteriul aprobat de Ion e
    # "doar CSS => doar audit_design, fara Chromium". Consecinta, scrisa ca s-o
    # vada cineva: o modificare doar in tokens.css/global.css nu trece pe sub
    # audit_mobil, adica exact clasa lui de defect (bloc mobil anulat de reguli
    # scrise mai jos in acelasi fisier, 30.07). Ca sa se acopere si aia, adauga
    # '.css' in `surse_spa`.
    surse_spa = any(p.endswith(('.svelte', '.js')) for p in frontend)

    # PRIMA, fiindca e cea mai ieftina (secunde, fara Chromium) si fiindca
    # prinde alta clasa de defect decat toate celelalte: nu ce crapa si nu ce
    # nu incape, ci ce e SCRIS si nu ajunge sa se intample — regula CSS taiata
    # din build, `let` citit in markup care nu redeseneaza, import care nu se
    # rezolva. Vezi antetul lui scripts/lint.py pentru ce a gasit la prima
    # rulare. Se declanseaza si de un .py din scripts/, care nu trece pe sub
    # nicio alta poarta.
    if frontend or any(p.endswith('.py') for p in atinse):
        porti.append(('lint', [PYTHON, str(SCRIPTURI / 'lint.py')],
                      RADACINA, '%s scripts/lint.py' % PY_MANUAL))

    if any(p.endswith(('.svelte', '.css')) for p in frontend):
        porti.append(('audit_design',
                      [PYTHON, str(SCRIPTURI / 'audit_design.py')],
                      RADACINA, '%s scripts/audit_design.py --lista' % PY_MANUAL))

    if backend:
        # `--static`: proba pe API cere server pe :5000 + PIN-ul real din mediu,
        # iar PIN-ul n-are unde sa stea fara sa intre intr-un fisier versionat.
        # Rularea reala o face smoke_ui mai jos, cu serverul lui.
        porti.append(('test_suite',
                      [PYTHON, str(SCRIPTURI / 'test_suite.py'), '--static'],
                      RADACINA, '%s scripts/test_suite.py --static' % PY_MANUAL))

    if surse_spa:
        cmd = NPM
        if not cmd:
            porti.append(('build', None, None, 'npm run build (in frontend/)'))
        else:
            porti.append(('build', [cmd, 'run', 'build'],
                          RADACINA / 'frontend', 'npm run build (in frontend/)'))

    # smoke_ui si pe backend: el prinde ruta care da 500 dupa o curatenie in
    # blueprints (gantt.pdf a stat rupt din v32 fara ca nimic sa-l atinga).
    # Build-ul nu e nevoie cand s-a atins doar Python — dist-ul e neschimbat.
    if surse_spa or backend:
        porti.append(('smoke_ui',
                      [PYTHON, str(SCRIPTURI / 'smoke_ui.py')],
                      RADACINA, '%s scripts/smoke_ui.py' % PY_MANUAL))

    if surse_spa:
        porti.append(('audit_mobil',
                      [PYTHON, str(SCRIPTURI / 'audit_mobil.py')],
                      RADACINA, '%s scripts/audit_mobil.py' % PY_MANUAL))
        # Foile cu tastatura: `audit_tastatura` emuleaza IME-ul (fals
        # `visualViewport`) si masoara ce niciun alt audit nu vede — a doua sosire
        # a foii, ce ramane sub tastatura, clicul de la ridicarea degetului.
        porti.append(('audit_tastatura',
                      [PYTHON, str(SCRIPTURI / 'audit_tastatura.py')],
                      RADACINA, '%s scripts/audit_tastatura.py' % PY_MANUAL))
    return porti


def ruleaza(argv, cwd, limita=None):
    p = subprocess.run(argv, cwd=str(cwd), env=mediu_probe(), timeout=min(TIMP_MAX, limita) if limita else TIMP_MAX,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


# --------------------------------------------------------------------- main

def main():
    date = json.load(sys.stdin)

    # Subagentii au propriul Stop; poarta e a sesiunii principale.
    if date.get('agent_id'):
        iesi_curat()

    # Supapa. Nu e o portita de comoditate: exista fiindca o poarta care nu poate
    # fi oprita se ocoleste prin a nu edita fisierul, ceea ce e mai rau. Cand e
    # folosita, o SPUNE in context — nu tace.
    if os.environ.get('PIF_GATE', '').lower() == 'skip':
        raporteaza('PIF_GATE=skip: poarta a fost sarita in mod deliberat. '
                   'Verificatoarele NU au rulat — spune-i lui Ion explicit ce n-a '
                   'fost verificat, sau ruleaza manual `python scripts/audit_design.py` '
                   'si `python scripts/smoke_ui.py`.')

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
    #
    # Se calculeaza DOAR peste fisierele care declanseaza o poarta. Inainte se
    # calcula peste tot ce s-a atins, iar fiecare sesiune se incheie cu o retusare
    # in CLAUDE.md / docs/memory/ — deci semnatura se schimba dupa ce verificarea
    # trecuse deja, si urmatorul Stop relua build + smoke_ui + audit_mobil (3-6
    # minute) pentru un text care nu intra in bundle. Un fisier de documentatie nu
    # poate strica nici build-ul, nici geometria de pe telefon.
    semnatura = []
    for r in relevante(atinse):
        p = RADACINA / r
        semnatura.append('%s:%s' % (r, p.stat().st_mtime_ns if p.exists() else 0))
    semnatura = '|'.join(semnatura)
    if memo.get('semnatura_curata') == semnatura:
        iesi_curat()

    porti = porti_pentru(atinse)
    if not porti:
        iesi_curat()

    blocari = int(memo.get('blocari', 0))

    import time
    pornit = time.monotonic()
    for eticheta, argv, cwd, manual in porti:
        ramas = TIMP_TOTAL - (time.monotonic() - pornit)
        if ramas < 30:
            memo['blocari'] = blocari
            f_memo.write_text(json.dumps(memo), encoding='utf-8')
            raporteaza(
                'Poarta a ramas fara buget dupa %s: portile ramase (%s) NU au rulat. '
                'Nu inseamna ca au trecut — ruleaza-le manual si spune-i lui Ion ce a ramas '
                'neverificat.' % (eticheta, ', '.join(
                    p[0] for p in porti[porti.index((eticheta, argv, cwd, manual)):])))
        if argv is None:                          # npm lipsa pe masina asta
            cod, iesire = 1, ('npm nu s-a gasit nici in PATH-ul mostenit, nici in '
                              'cel persistent din registru (`cai_persistente`), '
                              'deci build-ul Vite nu poate rula. Fara build, '
                              'smoke_ui ar testa static/dist/ vechi si ar trece pe '
                              'langa orice greseala din sursa. Verifica unde e '
                              'instalat Node si adauga-l in PATH-ul de utilizator.')
        else:
            try:
                cod, iesire = ruleaza(argv, cwd, limita=int(ramas))
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
