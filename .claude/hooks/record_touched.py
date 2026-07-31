#!/usr/bin/env python3
"""PostToolUse (Edit|Write): noteaza ce fisier a atins SESIUNEA curenta.

De ce nu `git status`: arborele poate fi murdar de la o sesiune anterioara
(pe 2026-07-31 avea 337 de linii necomise care nu erau ale sesiunii curente),
iar poarta ar fi rulat atunci pe munca altcuiva si ar fi blocat pe ea. Singurul
set corect e ce a atins sesiunea, si doar hook-ul asta il vede.

Nu blocheaza NICIODATA — o eroare aici n-are voie sa rupa o sesiune de lucru.
Dar nici n-o inghite: esecul se scrie in `<sid>.err`, iar `gate.py` blocheaza
daca il gaseste. Altfel un recorder mut ar da poarta verde pe zero fisiere
atinse, adica exact minciuna pentru care exista poarta.
"""
import json
import sys
import traceback
from pathlib import Path

RADACINA = Path(__file__).resolve().parents[2]
STARE = RADACINA / '.claude' / '.state'


def sid_curat(sid):
    """UUID in mod normal; taiem orice ar putea iesi din folderul de stare."""
    curat = ''.join(c for c in str(sid) if c.isalnum() or c in '-_')
    return curat[:80] or 'fara-sesiune'


def main():
    date = json.load(sys.stdin)
    sid = sid_curat(date.get('session_id', ''))
    STARE.mkdir(parents=True, exist_ok=True)

    cale = (date.get('tool_input') or {}).get('file_path')
    if not cale:
        return

    try:
        rel = Path(cale).resolve().relative_to(RADACINA).as_posix()
    except ValueError:
        return                                  # editare in afara repoului

    with open(STARE / ('%s.touched' % sid), 'a', encoding='utf-8') as f:
        f.write(rel + '\n')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        try:
            STARE.mkdir(parents=True, exist_ok=True)
            (STARE / 'recorder.err').write_text(
                traceback.format_exc(), encoding='utf-8')
        except Exception:
            pass
    sys.exit(0)
