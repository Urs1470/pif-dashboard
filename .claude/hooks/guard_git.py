#!/usr/bin/env python3
"""PreToolUse guard (Bash|PowerShell): blocheaza git add -A/. si force-push.

Regula globala nr. 3 ("stage explicit, niciodata force-push"), transformata in
verificare mecanica (memorie-standard R6): proza se respecta ~50-80% din timp,
hook-ul 100%. Exit 2 = blocat (stderr ajunge la Claude); exit 0 = trece.
Fail-open: orice eroare interna lasa comanda sa treaca (exit 0) - un guard care
crapa nu are voie sa blocheze tot Bash-ul.
"""
import json
import re
import sys

try:
    data = json.load(sys.stdin)
    if data.get('tool_name') not in ('Bash', 'PowerShell'):
        sys.exit(0)
    cmd = (data.get('tool_input') or {}).get('command', '') or ''
    # sterge stringurile citate ca un mesaj de commit cu "add ." sa nu dea fals pozitiv
    cmd = re.sub(r'"[^"]*"|\'[^\']*\'', '""', cmd)

    # git add -A / --all / . (punct ca argument intreg, nu prefix de cale)
    if re.search(r'\bgit\b[^\n;|&]{0,120}?\badd\b', cmd) and \
       re.search(r'\badd\b[^\n;|&]*?(?:\s-A\b|\s--all\b|\s\.(?=[\s;|&\'"]|$))', cmd):
        sys.stderr.write(
            'BLOCAT (guard_git): stage explicit - niciodata `git add -A` / `git add .`. '
            'A maturat o data munca necomisa a lui Ion intr-un commit strain. '
            'Numeste fisierele: `git add <cale> <cale>`.\n')
        sys.exit(2)

    # git push --force / -f / --force-with-lease
    if re.search(r'\bgit\b[^\n;|&]{0,120}?\bpush\b', cmd) and \
       re.search(r'\bpush\b[^\n;|&]*?(?:\s--force(?:-with-lease)?\b|\s-f\b)', cmd):
        sys.stderr.write(
            'BLOCAT (guard_git): niciodata force-push (regula globala). '
            'Push respins = altcineva a impins intre timp: refetch, rebase, reincearca.\n')
        sys.exit(2)
except SystemExit:
    raise
except Exception:
    sys.exit(0)
sys.exit(0)
