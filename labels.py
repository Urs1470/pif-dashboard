"""Centralised label dictionaries for project / task statuses.
Source of truth for backend rendering (Excel exports, PDF, etc.).
Mirror lives at static/core.js: getStatusLabel().
"""

PROJECT_STATUS_LABELS = {
    'in_lucru': 'În Lucru',
    'in_asteptare': 'În Așteptare',
    'in_așteptare': 'În Așteptare',  # tolerate both diacritic forms
    'blocat': 'Blocat',
    'finalizat': 'Finalizat',
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
