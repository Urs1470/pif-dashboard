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

