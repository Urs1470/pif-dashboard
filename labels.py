"""Centralised label dictionaries for project / task statuses.
Source of truth for backend rendering (Excel exports, PDF, etc.).
Mirror lives at static/core.js: getStatusLabel().
"""

# Doua statusuri, atat (v31, cerinta lui Ion). Un proiect ori e in lucru la el,
# ori s-a incheiat; „in asteptare" si „blocat" nu erau folosite de nimeni (0 din
# 18 randuri), iar „in lucru" nu spunea nimic peste „in pregatire".
# Cheile vechi raman mapate, ca un rand nemigrat sa nu se afiseze brut.
PROJECT_STATUS_LABELS = {
    'pregatire': 'În pregătire',
    'finalizat': 'Finalizat',
    # mostenite (migrate in v31, pastrate doar ca sa nu apara valori brute)
    'in_lucru': 'În pregătire',
    'in_asteptare': 'În pregătire',
    'in_așteptare': 'În pregătire',
    'blocat': 'În pregătire',
}

TASK_STATUS_LABELS = {
    'to_do': 'To Do',
    'in_lucru': 'În Lucru',
    'in_asteptare': 'În Așteptare',
    'in_așteptare': 'În Așteptare',
    'blocat': 'Blocat',
    'done': 'Finalizat',
    'finalizat': 'Finalizat',
}


def project_status_label(s):
    return PROJECT_STATUS_LABELS.get(s, s or '')


def task_status_label(s):
    return TASK_STATUS_LABELS.get(s, s or '')
