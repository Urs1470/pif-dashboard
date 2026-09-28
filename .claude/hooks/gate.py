#!/usr/bin/env python3
"""Stop hook: poarta de verificare a pif-dashboard.

De ce exista. Verificatoarele sunt construite fiecare pe un mod de esec care trecea
de build: importul lipsa care lasa pagina pe schelet (27.07), butonul taiat de
marginea ecranului (30.07), a doua paleta rotita cu doua pozitii (30.07). Existau, dar
rularea lor era la discretia agentului — iar Ion nu revizuieste cod, deci
"criterii bifate" era o declaratie fara nimic care s-o contrazica. Poarta le
ruleaza automat, pe fisierele atinse de sesiune, si NU lasa tura sa se incheie
daca pica.

Ce ruleaza vine din `scripts/verifica.py` (`pasi_pentru`), aceeasi lista pe care o
rulezi si de mana (`python scripts/verifica.py --atinse <fisiere>`). Pana pe 2026-09-28
lista statea aici, iar documentatia si poarta ajunsesera sa spuna lucruri diferite.

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
import subprocess
import sys
import traceback
from pathlib import Path

RADACINA = Path(__file__).resolve().parents[2]
STARE = RADACINA / '.claude' / '.state'
SCRIPTURI = RADACINA / 'scripts'

MAX_BLOCARI = 2          # a (MAX_BLOCARI+1)-a oara raporteaza, nu blocheaza
MAX_IESIRE = 3000        # caractere pastrate din coada iesirii unei porti
# Buget TOTAL, sub timeout-ul hook-ului din settings.json (900 s). Fara el, cinci porti
# a cate 900 s puteau insuma 75 de minute, iar harness-ul ar fi omorat hook-ul la 900 —
# adica tura s-ar fi incheiat FARA VERDICT. O poarta care tace arata exact ca una care
# a trecut, si asta e singurul mod de esec pe care poarta n-are voie sa-l aiba.
TIMP_TOTAL = 780         # 13 min; restul pana la 900 ramane pentru raportare


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
# Pasii, selectia lor dupa fisiere si mediul in care ruleaza (npm pe Windows, venv,
# UTF-8) stau in `scripts/verifica.py` — un singur loc pentru lista verificatoarelor.
sys.path.insert(0, str(SCRIPTURI))
import verifica as V  # noqa: E402


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
                   'fost verificat, sau ruleaza manual `python scripts/verifica.py --poarta`.')

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
    for r in V.relevante(atinse):
        p = RADACINA / r
        semnatura.append('%s:%s' % (r, p.stat().st_mtime_ns if p.exists() else 0))
    semnatura = '|'.join(semnatura)
    if memo.get('semnatura_curata') == semnatura:
        iesi_curat()

    porti = V.pasi_pentru(atinse)
    if not porti:
        iesi_curat()

    blocari = int(memo.get('blocari', 0))

    import time
    pornit = time.monotonic()
    for i, pas in enumerate(porti):
        eticheta, manual = pas.eticheta, pas.manual
        ramas = TIMP_TOTAL - (time.monotonic() - pornit)
        if ramas < 30:
            memo['blocari'] = blocari
            f_memo.write_text(json.dumps(memo), encoding='utf-8')
            raporteaza(
                'Poarta a ramas fara buget inainte de %s: pasii ramasi (%s) NU au rulat. '
                'Nu inseamna ca au trecut — ruleaza-i manual (`python scripts/verifica.py '
                '--atinse ...`) si spune-i lui Ion ce a ramas neverificat.'
                % (eticheta, ', '.join(p.eticheta for p in porti[i:])))
        limita = int(ramas)
        try:
            cod, iesire = V.ruleaza_pas(pas, limita=limita)
        except subprocess.TimeoutExpired:
            cod, iesire = 1, 'Pasul a depasit bugetul ramas al portii (%d s) si a fost oprit.' % limita
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
               % (', '.join(p.eticheta for p in porti), ', '.join(atinse)))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Poarta stricata nu are voie sa treaca drept poarta trecuta.
        blocheaza('Poarta insasi a crapat, deci NIMIC nu e verificat. Nu declara '
                  'gata.\n\n%s' % traceback.format_exc())
