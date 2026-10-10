"""Limita de incercari de PIN, comuna tuturor worker-ilor Gunicorn si care supravietuieste unui
redeploy.

De ce nu in memorie. Pana acum, incercarile stateau intr-un dict din `app.py`: fiecare din cei
2 workeri avea al lui (5 incercari / 5 minute devenea in practica pana la 10), iar `git reset
--hard` + restart de la fiecare deploy il golea. Un PIN de 4-6 cifre, in spatele unei limite
care se reseteaza, se sparge din cateva adrese.

Unde stau incercarile. Intr-un fisier SQLite SEPARAT, langa baza aplicatiei
(`<PIF_DB_PATH>.ratelimit`, sau calea din `PIF_RATE_DB`). Nu in baza aplicatiei: asa nu exista
nicio schimba de schema sau migrare, restore-ul si `db-upload` (care inlocuiesc fisierul bazei)
nu sterg istoricul incercarilor, iar backup-ul nu-l poarta. Pe server, fisierul ramane intre
deploy-uri din acelasi motiv ca baza: `git reset --hard` nu atinge fisierele ignorate de git
(`*.db.*` in `.gitignore`).

Cum e atomic. Fiecare incercare e o tranzactie `BEGIN IMMEDIATE`: sterge intrarile expirate,
numara ale IP-ului, si abia apoi scrie. Doi workeri care primesc in acelasi timp incercari de la
acelasi IP se aseaza unul dupa altul (SQLite blocheaza scrierea), deci nu pot trece amandoi cu
a cincea incercare.

Cand fisierul nu merge (disc plin, drepturi, baza blocata peste 5 s): se logheaza eroarea si
limita cade pe memoria acestui worker, adica exact comportamentul de dinainte. Alternativa,
sa refuze orice login, ar incuia-o pe Ion afara din cauza unui fisier de ajutor.
"""

import logging
import os
import sqlite3
import threading
import time

logger = logging.getLogger('pif_dashboard')

_SCHEMA = (
    'CREATE TABLE IF NOT EXISTS incercari ('
    ' ip TEXT NOT NULL, ts REAL NOT NULL)',
    'CREATE INDEX IF NOT EXISTS idx_incercari_ip ON incercari(ip, ts)',
)
_TIMEOUT_S = 5.0


def cale_implicita():
    """`PIF_RATE_DB`, altfel `<baza aplicatiei>.ratelimit`. Se rezolva la fiecare apel, ca
    testele (si `PIF_DB_PATH`) sa poata muta baza fara sa repornesca modulul."""
    explicit = os.environ.get('PIF_RATE_DB', '').strip()
    if explicit:
        return os.path.abspath(explicit)
    import database
    return database.DATABASE_PATH + '.ratelimit'


class LimitaIncercari:
    """`permite(ip)`: True si inregistreaza incercarea, sau False daca IP-ul a atins `limita`
    incercari in ultimele `fereastra` secunde (si atunci nu mai inregistreaza nimic)."""

    def __init__(self, limita, fereastra, cale=None):
        self.limita = limita
        self.fereastra = fereastra
        self._cale = cale
        self._memorie = {}                     # plasa de siguranta, per worker
        self._lock = threading.Lock()

    @property
    def cale(self):
        return self._cale or cale_implicita()

    # ------------------------------------------------------------------ pe disc

    def _conexiune(self):
        # isolation_level=None: tranzactia o conducem noi (BEGIN IMMEDIATE).
        conn = sqlite3.connect(self.cale, timeout=_TIMEOUT_S, isolation_level=None)
        for ddl in _SCHEMA:
            conn.execute(ddl)
        return conn

    def _permite_pe_disc(self, ip, acum):
        conn = self._conexiune()
        try:
            conn.execute('BEGIN IMMEDIATE')
            try:
                conn.execute('DELETE FROM incercari WHERE ts <= ?', (acum - self.fereastra,))
                (n,) = conn.execute('SELECT COUNT(*) FROM incercari WHERE ip = ?', (ip,)).fetchone()
                permis = n < self.limita
                if permis:
                    conn.execute('INSERT INTO incercari (ip, ts) VALUES (?, ?)', (ip, acum))
                conn.execute('COMMIT')
            except BaseException:
                conn.execute('ROLLBACK')
                raise
            return permis
        finally:
            conn.close()

    # ---------------------------------------------------------------- in memorie

    def _permite_in_memorie(self, ip, acum):
        with self._lock:
            recente = [t for t in self._memorie.get(ip, []) if acum - t < self.fereastra]
            permis = len(recente) < self.limita
            if permis:
                recente.append(acum)
            self._memorie[ip] = recente
            if len(self._memorie) > 5000:
                for alt in [k for k, v in self._memorie.items()
                            if all(acum - t >= self.fereastra for t in v)]:
                    del self._memorie[alt]
            return permis

    # ------------------------------------------------------------------- public

    def permite(self, ip):
        acum = time.time()
        try:
            return self._permite_pe_disc(ip, acum)
        except (sqlite3.Error, OSError) as e:
            logger.error('Limita de login: fisierul %s nu merge (%s); se foloseste memoria acestui worker',
                         self.cale, e)
            return self._permite_in_memorie(ip, acum)

    def adrese(self):
        """IP-urile cu incercari in fereastra (pentru teste si diagnostic), pe disc."""
        acum = time.time()
        conn = self._conexiune()
        try:
            return sorted(r[0] for r in conn.execute(
                'SELECT DISTINCT ip FROM incercari WHERE ts > ?', (acum - self.fereastra,)))
        finally:
            conn.close()

    def goleste(self):
        """Sterge toate incercarile (pe disc si din memorie). Pentru teste si pentru o
        deblocare de mana."""
        with self._lock:
            self._memorie.clear()
        try:
            conn = self._conexiune()
            try:
                conn.execute('DELETE FROM incercari')
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            pass
