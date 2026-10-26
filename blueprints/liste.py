# Liste Blueprint (v46)
# Listele de taskuri globale ale lui Ion: Munca si Personal (fixe) si cele create din Torqa
# (ex. „Casa"). Un task global apartine unei liste prin `global_tasks.sfera` = `liste.id`.
# Decizia: docs/decizii/2026-10-26-liste.md. Rutele sunt deschise si tokenului de dispozitiv
# (Torqa): nu apar in DEVICE_TOKEN_DENIED din utils.py.

import re
import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify

from database import get_db, row_to_dict, LISTE_FIXE
from utils import generate_uuid, login_required, get_json_or_400, id_ocupat

liste_bp = Blueprint('liste', __name__)

# Id-ul dat de client (Torqa creeaza offline si retrimite cu acelasi id). `ordine` este rezervat:
# `PUT /api/liste/ordine` ar prinde o lista cu acest id inaintea rutei `<lista_id>`.
RE_ID = re.compile(r'[a-z0-9_-]{1,40}')
ID_REZERVATE = frozenset(f[0] for f in LISTE_FIXE) | {'ordine'}
RE_CULOARE = re.compile(r'#[0-9a-fA-F]{6}')
NUME_MAX = 60
ICONITA_MAX = 40

_SELECT = '''
    SELECT l.id, l.nume, l.iconita, l.culoare, l.ordine, l.fixa, l.created_at, l.updated_at,
           (SELECT COUNT(*) FROM global_tasks g WHERE g.sfera = l.id AND g.status != 'done') AS deschise
    FROM liste l
'''
_ORDINE = ' ORDER BY l.ordine, l.created_at'


def citeste_liste(cursor, lista_id=None):
    """Listele, ordonate, fiecare cu `deschise` (taskurile globale nefacute din ea). Una singura
    daca `lista_id` e dat (intoarce un dict sau None). Le foloseste si /api/sync/snapshot."""
    if lista_id is not None:
        cursor.execute(_SELECT + ' WHERE l.id = ?', (lista_id,))
        return row_to_dict(cursor.fetchone())
    cursor.execute(_SELECT + _ORDINE)
    return [row_to_dict(r) for r in cursor.fetchall()]


def _eroare(mesaj, cod, **extra):
    return jsonify({'error': mesaj, **extra}), cod


def _nume(valoare):
    """(nume curatat, None) sau (None, mesaj)."""
    if not isinstance(valoare, str) or not valoare.strip():
        return None, 'nume trebuie sa fie un text nevid'
    if len(valoare.strip()) > NUME_MAX:
        return None, 'nume: cel mult %d caractere' % NUME_MAX
    return valoare.strip(), None


def _iconita(valoare):
    if not isinstance(valoare, str) or not valoare.strip():
        return None, 'iconita trebuie sa fie un text nevid'
    if len(valoare.strip()) > ICONITA_MAX:
        return None, 'iconita: cel mult %d caractere' % ICONITA_MAX
    return valoare.strip(), None


def _culoare(valoare):
    """None = culoarea implicita a temei. Altfel '#rrggbb', salvat cu litere mici."""
    if valoare is None:
        return None, None
    if not isinstance(valoare, str) or not RE_CULOARE.fullmatch(valoare):
        return None, "culoare trebuie sa fie '#rrggbb' sau null"
    return valoare.lower(), None


@liste_bp.route('/api/liste', methods=['GET'])
@login_required
def get_liste():
    conn = get_db()
    try:
        return jsonify(citeste_liste(conn.cursor()))
    finally:
        conn.close()


@liste_bp.route('/api/liste', methods=['POST'])
@login_required
def create_lista():
    data = get_json_or_400()
    nume, eroare = _nume(data.get('nume'))
    if eroare:
        return _eroare(eroare, 400)
    iconita, eroare = _iconita(data.get('iconita'))
    if eroare:
        return _eroare(eroare, 400)
    culoare, eroare = _culoare(data.get('culoare'))
    if eroare:
        return _eroare(eroare, 400)
    lista_id = data.get('id')
    if lista_id is None:
        lista_id = generate_uuid()
    elif (not isinstance(lista_id, str) or not RE_ID.fullmatch(lista_id) or lista_id in ID_REZERVATE):
        return _eroare("id trebuie sa aiba 1-40 de caractere din [a-z0-9_-] si sa nu fie unul rezervat "
                       "(munca, personal, ordine)", 400)

    conn = get_db()
    try:
        cursor = conn.cursor()
        ocupat = id_ocupat(cursor, 'liste', lista_id)
        if ocupat:
            return ocupat
        acum = datetime.now().isoformat()
        try:
            # O singura instructiune: `ordine` = max + 1 se calculeaza in aceeasi scriere cu inserarea,
            # deci doua cereri simultane (2 workeri) nu primesc aceeasi pozitie.
            cursor.execute(
                'INSERT INTO liste (id, nume, iconita, culoare, ordine, fixa, created_at, updated_at) '
                'SELECT ?, ?, ?, ?, COALESCE(MAX(ordine), -1) + 1, 0, ?, ? FROM liste',
                (lista_id, nume, iconita, culoare, acum, acum))
            conn.commit()
        except sqlite3.IntegrityError:
            # Aceeasi cerere sosita a doua oara, in paralel cu prima: pierde cursa, primeste 409.
            conn.rollback()
            return jsonify({'error': 'Exista deja', 'id': lista_id}), 409
        return jsonify(citeste_liste(cursor, lista_id)), 201
    finally:
        conn.close()


# `ordine` e rutat inaintea lui `<lista_id>` de Werkzeug (partea statica castiga), iar id-ul
# „ordine" e oricum rezervat la creare.
@liste_bp.route('/api/liste/ordine', methods=['PUT'])
@login_required
def reordoneaza_liste():
    data = get_json_or_400()
    ids = data.get('ids')
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        return _eroare('ids trebuie sa fie o lista de id-uri de liste', 400)
    if len(set(ids)) != len(ids):
        return _eroare('ids contine un id de doua ori', 400)

    conn = get_db()
    try:
        cursor = conn.cursor()
        # Verificarea si scrierea in aceeasi tranzactie: o lista creata intre ele nu ramane cu pozitia
        # nepusa.
        cursor.execute('BEGIN IMMEDIATE')
        existente = {r['id']: r['ordine'] for r in cursor.execute('SELECT id, ordine FROM liste')}
        if set(ids) != set(existente):
            conn.rollback()
            return _eroare('ids trebuie sa fie exact listele existente (lipsesc: %s; necunoscute: %s)' % (
                ', '.join(sorted(set(existente) - set(ids))) or '-',
                ', '.join(sorted(set(ids) - set(existente))) or '-'), 400)
        acum = datetime.now().isoformat()
        for pozitie, lista_id in enumerate(ids):
            if existente[lista_id] != pozitie:
                cursor.execute('UPDATE liste SET ordine = ?, updated_at = ? WHERE id = ?',
                               (pozitie, acum, lista_id))
        conn.commit()
        return jsonify(citeste_liste(cursor))
    finally:
        conn.close()


@liste_bp.route('/api/liste/<lista_id>', methods=['PUT'])
@login_required
def update_lista(lista_id):
    data = get_json_or_400()
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT nume, fixa FROM liste WHERE id = ?', (lista_id,))
        existenta = cursor.fetchone()
        if existenta is None:
            return _eroare('Lista inexistenta', 404)

        schimbari = {}
        if 'nume' in data:
            nume, eroare = _nume(data['nume'])
            if eroare:
                return _eroare(eroare, 400)
            # Pe o lista fixa, acelasi nume trimis iar nu e o schimbare: Torqa poate trimite obiectul intreg.
            if existenta['fixa'] and nume != existenta['nume']:
                return _eroare('Numele unei liste fixe nu se schimba', 400)
            schimbari['nume'] = nume
        if 'iconita' in data:
            iconita, eroare = _iconita(data['iconita'])
            if eroare:
                return _eroare(eroare, 400)
            schimbari['iconita'] = iconita
        if 'culoare' in data:
            culoare, eroare = _culoare(data['culoare'])
            if eroare:
                return _eroare(eroare, 400)
            schimbari['culoare'] = culoare

        if schimbari:
            schimbari['updated_at'] = datetime.now().isoformat()
            # Numele coloanelor vin din cheile de mai sus, scrise aici, nu din cerere.
            cursor.execute('UPDATE liste SET %s WHERE id = ?' % ', '.join('%s = ?' % c for c in schimbari),
                           [*schimbari.values(), lista_id])
            conn.commit()
        return jsonify(citeste_liste(cursor, lista_id))
    finally:
        conn.close()


@liste_bp.route('/api/liste/<lista_id>', methods=['DELETE'])
@login_required
def delete_lista(lista_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        # Stergerea si conditiile ei intr-o singura instructiune: un task creat intre o verificare si
        # stergere ar ramane pe o lista care nu mai exista.
        cursor.execute(
            'DELETE FROM liste WHERE id = ? AND fixa = 0 '
            'AND NOT EXISTS (SELECT 1 FROM global_tasks g WHERE g.sfera = liste.id)', (lista_id,))
        sters = cursor.rowcount
        conn.commit()
        if sters:
            return jsonify({'message': 'ok'})
        cursor.execute('SELECT fixa FROM liste WHERE id = ?', (lista_id,))
        ramas = cursor.fetchone()
        if ramas is None:
            return _eroare('Lista inexistenta', 404)
        if ramas['fixa']:
            return _eroare('O lista fixa nu se sterge', 403)
        taskuri = cursor.execute('SELECT COUNT(*) FROM global_tasks WHERE sfera = ?', (lista_id,)).fetchone()[0]
        return _eroare('Lista are taskuri; muta-le sau sterge-le intai', 409, taskuri=taskuri)
    finally:
        conn.close()
