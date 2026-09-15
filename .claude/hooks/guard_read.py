#!/usr/bin/env python3
"""PreToolUse guard (Read): blocheaza citirea INTEGRALA a fisierelor > 200 KB.

Inlocuieste tabelul "fisiere care NU se citesc integral" din nucleu (un Read pe
fault-codes de 881 KB costa ~225k tokeni - mai mult decat o fereastra de context).
Citirea partiala (offset/limit/pages) si fisierele mici trec. Fail-open la erori.
"""
import json
import os
import sys

MAX = 200 * 1024

try:
    data = json.load(sys.stdin)
    if data.get('tool_name') != 'Read':
        sys.exit(0)
    ti = data.get('tool_input') or {}
    fp = ti.get('file_path')
    if not fp or ti.get('limit') or ti.get('offset') or ti.get('pages'):
        sys.exit(0)
    if os.path.isfile(fp) and os.path.getsize(fp) > MAX:
        kb = os.path.getsize(fp) / 1024.0
        sys.stderr.write(
            'BLOCAT (guard_read): %s are %.0f KB (> 200 KB) - nu se citeste integral. '
            'Cauta cu `grep -n "termen"` / `python tools/vaultq.py "termen"` (da si '
            'cale:linie in tabelele generate), sau citeste partial cu offset/limit.\n'
            % (fp, kb))
        sys.exit(2)
except SystemExit:
    raise
except Exception:
    sys.exit(0)
sys.exit(0)
