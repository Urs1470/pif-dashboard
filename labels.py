"""Vocabularul de status al proiectelor si taskurilor: ce valori scrie aplicatia si ce chei
vechi mai pot sta in baza.

Serverul nu mai randeaza nicio eticheta: exportul PDF care le folosea a plecat pe 2026-10-03, iar
Torqa isi scrie etichetele singur. Dictionarele raman pentru `scripts/gen_memory.py`, care le
citeste (din text) ca sa puna in `docs/memory/DB_MAP.md` valorile de status.
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

# Doua stari, atat (v34): facut sau nu. Celelalte erau in selector, dar pe zero
# randuri. Cheile vechi raman mapate ca un rand nemigrat sa nu apara brut.
TASK_STATUS_LABELS = {
    'to_do': 'De făcut',
    'done': 'Făcut',
    'finalizat': 'Făcut',
    'in_lucru': 'De făcut',
    'in_asteptare': 'De făcut',
    'in_așteptare': 'De făcut',
    'blocat': 'De făcut',
}



# Ce are voie sa stea in baza (v48, E-015). Pana in v48 vocabularul era doar o conventie a
# aplicatiei: un `UPDATE` direct, un client cu un status vechi sau un restore dintr-un backup
# vechi puteau scrie orice. Acum triggerele din `database.py` (SQL_TRIGGERE_STATUS) refuza
# la INSERT si UPDATE orice valoare din afara tuplurilor de mai jos, iar rutele si restore-ul
# trec intai prin `status_*_canonic`, ca o cheie veche sa se stranga, nu sa pice.
PROJECT_STATUSES = ('pregatire', 'finalizat')
TASK_STATUSES = ('to_do', 'done')


def status_proiect_canonic(valoare):
    """'pregatire' | 'finalizat' pentru o cheie cunoscuta (si veche), altfel None."""
    if not isinstance(valoare, str) or valoare.strip() not in PROJECT_STATUS_LABELS:
        return None
    return 'finalizat' if valoare.strip() == 'finalizat' else 'pregatire'


def status_task_canonic(valoare):
    """'to_do' | 'done' pentru o cheie cunoscuta (si veche), altfel None. `finalizat` e cheia
    veche pentru facut."""
    if not isinstance(valoare, str) or valoare.strip() not in TASK_STATUS_LABELS:
        return None
    return 'done' if valoare.strip() in ('done', 'finalizat') else 'to_do'
