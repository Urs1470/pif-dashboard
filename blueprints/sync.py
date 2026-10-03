"""Imaginea completa pentru Torqa: tot ce se sincronizeaza, intr-o singura cerere.

Torqa (build propriu din Super Productivity, pe telefon, pe desktop si pe web) tine o copie locala si o compara
la fiecare sincronizare cu imaginea de aici: ce lipseste din imagine s-a sters pe
server. Stergerile din baza sunt definitive (DELETE FROM), deci altfel n-ar avea de
unde afla de ele. Datele sunt putine (zeci de proiecte, sute de taskuri), asa ca
imaginea intreaga costa mai putin decat un jurnal de schimbari si nu cere schema noua.

Ruta doar citeste. Scrierile trec prin rutele obisnuite (/api/tasks/..., /api/global-tasks/...),
cu aceleasi reguli: bifarea unui task recurent naste urmatoarea aparitie AICI, pe server.
"""

from datetime import datetime

from flask import Blueprint, jsonify

from database import get_db, row_to_dict
from utils import login_required, TASK_PROIECT_VIU

sync_bp = Blueprint('sync', __name__)

PROIECT_COLOANE = ('id', 'nume', 'status', 'client', 'cod_proiect', 'data_finalizare', 'updated_at')
TASK_COLOANE = ('id', 'proiect_id', 'titlu', 'descriere', 'status', 'data_scadenta',
                'data_finalizare', 'recurenta', 'ordine', 'created_at', 'updated_at')
SUBTASK_COLOANE = ('id', 'task_id', 'titlu', 'done', 'ordine', 'created_at')
GLOBAL_COLOANE = ('id', 'titlu', 'descriere', 'status', 'categorie', 'sfera', 'data_scadenta', 'ora',
                  'data_finalizare', 'recurenta', 'created_at', 'updated_at')


@sync_bp.route('/api/sync/snapshot', methods=['GET'])
@login_required
def sync_snapshot():
    """{server_time, proiecte, tasks, subtasks, global_tasks}.

    `tasks[].viu` = 1 daca taskul inca se lucreaza: proiectul e deschis, sau taskul e
    nascut dupa inchiderea proiectului (aceeasi regula ca „Astazi", TASK_PROIECT_VIU).
    Taskurile unui proiect sters lipsesc, ca in pagina proiectului.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT {', '.join(PROIECT_COLOANE)} FROM proiecte ORDER BY nume")
        proiecte = [row_to_dict(r) for r in cursor.fetchall()]

        cursor.execute(f'''
            SELECT {', '.join('t.' + c for c in TASK_COLOANE)},
                   CASE WHEN {TASK_PROIECT_VIU} THEN 1 ELSE 0 END AS viu
            FROM tasks t JOIN proiecte p ON p.id = t.proiect_id
            ORDER BY t.proiect_id, t.ordine, t.created_at
        ''')
        tasks = [row_to_dict(r) for r in cursor.fetchall()]

        # Parintele e un task de proiect SAU unul global (task_subtasks n-are cheie straina,
        # tocmai ca sa le primeasca pe amandoua). Orfanii raman afara.
        cursor.execute(f'''
            SELECT {', '.join('s.' + c for c in SUBTASK_COLOANE)}
            FROM task_subtasks s
            WHERE s.task_id IN (SELECT id FROM tasks) OR s.task_id IN (SELECT id FROM global_tasks)
            ORDER BY s.task_id, s.ordine
        ''')
        subtasks = [row_to_dict(r) for r in cursor.fetchall()]

        cursor.execute(f"SELECT {', '.join(GLOBAL_COLOANE)} FROM global_tasks ORDER BY created_at")
        global_tasks = [row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

    return jsonify({
        'server_time': datetime.now().isoformat(timespec='seconds'),
        'proiecte': proiecte,
        'tasks': tasks,
        'subtasks': subtasks,
        'global_tasks': global_tasks,
    })
