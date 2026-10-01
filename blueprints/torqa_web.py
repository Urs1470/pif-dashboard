# Torqa web Blueprint
# Build-ul web al Torqa (Angular, PWA), gazduit pe acelasi server ca dashboardul,
# la `/torqa/`.
#
# DE CE EXISTA. Torqa e build-ul privat al lui Ion din Super Productivity. Pe telefon
# e aplicatie Android; pe web trebuie sa fie la un link, fara alt server de intretinut.
# Datele vin tot din `/api/*` (aceeasi sesiune, acelasi CSRF), deci pagina doar se
# gazduieste aici.
#
# UNDE STA BUILD-UL: in `uploads/torqa-web/<versiune>/`, adica in AFARA gitului — ca
# APK-ul (vezi `app_update.py`). Un build are 705 de fisiere si 21 MB (8 MB in zip), sau
# 1234 si 50 MB cu source map-uri, cu nume hash-uite la fiecare compilare (2026-10-01): in
# istoric ar ramane pentru totdeauna, iar serverul n-are npm ca sa-l refaca. Se urca ca zip,
# cu tokenul de masina: `POST /api/torqa/web/upload`.
#
# VERSIUNI SI SCHIMBARE ATOMICA. Fiecare urcare se extrage intr-un director nou
# (`<an><luna><zi>T<ora>-<microsecunde>`, UTC, deci ordinea lexicografica e cea
# cronologica), si abia apoi fisierul-pointer `current` e rescris cu `os.replace`: o
# cerere vede ori tot build-ul vechi, ori tot pe cel nou, niciodata jumatati. Raman live
# + 2 anterioare, pentru intoarcere (`printf '<versiune>' > uploads/torqa-web/current`);
# restul se sterg.
#
# CINE VEDE CE. Documentul HTML (`/torqa/`, `index.html`, orice cale fara extensie —
# rutele aplicatiei) cere sesiune de dashboard: fara ea, redirect la `/login?next=/torqa/`.
# Fisierele (JS, CSS, fonturi, imagini, `ngsw*`, manifest) se dau FARA login: nu contin
# date, iar service worker-ul Angular si browserul le descarca singure, in fundal, fara o
# pagina in fata care sa te trimita la PIN. Datele raman in `/api/*`, protejat. Fisierele
# nu ating nici sesiunea: fara Set-Cookie si fara `Vary: Cookie` (vezi SesiuneFaraStatice),
# ca sa se poata tine in cache.

import logging
import os
import re
import secrets
import shutil
import stat
import time
import zipfile
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, Response, abort, has_request_context, jsonify, redirect, request, send_file, session,
)
from flask.sessions import SecureCookieSessionInterface
from werkzeug.security import safe_join

from utils import _check_api_token, UPLOAD_FOLDER

# Logul aplicatiei (logs/app.log): urcarile de build trebuie sa lase urma acolo; un logger cu
# numele modulului n-are handler si INFO-ul lui se pierde (asa e azi la app_update.py).
logger = logging.getLogger('pif_dashboard')

torqa_web_bp = Blueprint('torqa_web', __name__)

DIR_WEB = os.path.join(UPLOAD_FOLDER, 'torqa-web')
NUME_POINTER = 'current'

PREFIX_URL = '/torqa/'
LOGIN_CU_INTOARCERE = '/login?next=/torqa/'

# Limite la urcare. Zip-ul comprimat: sub plafonul de 100 MB al Cloudflare (planul gratuit)
# si de 5 ori peste un build real cu source map-uri (16 MB, 2026-10-01). Descomprimat: de ~6
# ori un build real (50 MB); plafonul exista ca un zip-bomba sa nu umple discul.
MAX_ZIP = 80 * 1024 * 1024
MAX_DESCOMPRIMAT = 300 * 1024 * 1024
MAX_FISIERE = 5000
# Peste Content-Length-ul fisierului, formularul multipart mai adauga cateva sute de octeti.
MARGINA_FORMULAR = 1024 * 1024
MAGIC_ZIP = b'PK\x03\x04'

# Cate versiuni ANTERIOARE raman langa cea live.
PASTREAZA_ANTERIOARE = 2
ID_VERSIUNE = re.compile(r'^\d{8}T\d{6}-\d{6}$')
# Resturile unei urcari cazute la mijloc (`.up-*.zip`, `.tmp-*`) se sterg dupa o ora.
VARSTA_RESTURI = 3600

# Politica de continut pentru `/torqa/` (si doar pentru el; vezi after_request in app.py).
# Ce cere build-ul Angular, nimic mai larg. Gasita CU BROWSERUL (Chromium headless pe build-ul
# real, 2026-10-01: prima pagina, un task adaugat si bifat, 11 rute, panoul de detalii, 8
# rute de pluginuri, setarile): fiecare element de mai jos a fost scos pe rand, iar fara
# primele trei aplicatia da erori CSP; restul sunt cerute de cod, nu de acel parcurs.
#   - script-src 'unsafe-eval': runtime-ul pluginurilor ruleaza cod prin `new Function`
#     (src/app/plugins/plugin-runner.ts) si la pornire apar 9 violari fara el.
#   - script-src 'unsafe-inline': bootstrap-ul din index.html e un <script> inline, iar
#     CSS-ul se incarca cu `onload="this.media='all'"` (handler inline).
#   - style-src 'unsafe-inline': Angular Material pune stiluri inline (212 violari fara el).
#   - img-src data: blob: — NU apar in parcurs, dar le cere codul: imaginile lipite in
#     note devin `blob:` (core/clipboard-image/clipboard-image.service.ts), iar kit-ul de UI
#     al pluginurilor foloseste un `url(data:image/svg+xml...)`. Nu scot nimic din pagina.
#   - Restul (connect, font, media, worker, frame, manifest) cade pe `default-src 'self'`:
#     API-ul e pe acelasi domeniu, fonturile si sunetele vin din build. Integrarile externe
#     ale Super Productivity (Jira, CalDAV, Dropbox, SuperSync...) raman blocate, si e bine
#     asa. Un worker `blob:` (fflate, la instalarea unui plugin din zip) ramane blocat.
# Daca o functie a Torqa web nu mai merge, consola spune `Refused to ...`: se adauga exact
# acel element, nu un `https:` oarecare.
CSP_TORQA = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "object-src 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)

# Tipurile le dam NOI, nu din baza de date a sistemului: pe un Linux fara `mime.types`
# un `.mjs` sau `.webmanifest` ar iesi `application/octet-stream`, iar cu
# `X-Content-Type-Options: nosniff` (app.py) un modul JS cu tip gresit nu se executa.
TIPURI = {
    '.html': 'text/html', '.htm': 'text/html',
    '.js': 'text/javascript', '.mjs': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json', '.map': 'application/json',
    '.webmanifest': 'application/manifest+json',
    '.svg': 'image/svg+xml',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
    '.webp': 'image/webp', '.avif': 'image/avif', '.ico': 'image/x-icon',
    '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf',
    '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.wav': 'audio/wav',
    '.txt': 'text/plain', '.xml': 'application/xml', '.wasm': 'application/wasm',
    '.zip': 'application/zip',
}
TIP_IMPLICIT = 'application/octet-stream'

# Numele pe care browserul trebuie sa le reverifice MEREU: de ele depinde ce versiune
# vede utilizatorul. Orice alt fisier nehash-uit tot se reverifica (`no-cache` + ETag, deci
# 304 ieftin); doar bundle-urile cu hash in nume se tin un an.
FARA_CACHE = frozenset({
    'index.html', 'ngsw.json', 'ngsw-worker.js', 'safety-worker.js',
    'manifest.json', 'manifest.webmanifest',
})
CACHE_IMUABIL = 'public, max-age=31536000, immutable'
# Hash-ul esbuild din numele fisierelor Angular: 8 caractere [A-Z0-9], inainte de extensie
# (`main-D2W5MYI5.js`, `chunk-LDUBXBF5.js.map`, `media/open-sans-latin-400-normal-HCAVHEYW.woff2`).
HASH_IN_NUME = re.compile(r'-[A-Z0-9]{8}\.[A-Za-z0-9.]+$')


class EroareBuild(Exception):
    """Un build respins la urcare; `status` e codul HTTP (400, 413)."""

    def __init__(self, mesaj, status=400):
        super().__init__(mesaj)
        self.status = status


# ---------------------------------------------------------------- ce e fisier

def arata_ca_fisier(rest):
    """True daca `rest` (calea de dupa `/torqa/`) cere un FISIER: ultimul segment are
    extensie. Aceeasi regula o aplica si service worker-ul Angular (`navigationUrls`
    exclude caile cu punct), deci `/torqa/tasks` e o ruta a aplicatiei, iar
    `/torqa/chunk-X.js` e un fisier — care, daca lipseste, da 404, nu HTML: un chunk
    lipsa raspuns cu pagina de start ar fi ajuns in browser ca JavaScript stricat.
    `index.html` e documentul, nu un fisier static."""
    if rest == 'index.html':
        return False
    return '.' in rest.rsplit('/', 1)[-1]


def cerere_statica(cale):
    """True pentru calea unei cereri de fisier static Torqa (nu pentru document)."""
    return cale.startswith(PREFIX_URL) and arata_ca_fisier(cale[len(PREFIX_URL):])


class SesiuneFaraStatice(SecureCookieSessionInterface):
    """Sesiunea obisnuita, mai putin pe fisierele statice Torqa.

    De ce. Sesiunea lui Flask e permanenta si se reinnoieste la fiecare raspuns, iar
    `csrf.py` scrie `csrf_token` pe fiecare raspuns autentificat. Rezultatul pe un fisier
    static ar fi un `Set-Cookie` nou si `Vary: Cookie` — iar un `Vary: Cookie` cu un cookie
    care se schimba la fiecare cerere face ca browserul sa nu refoloseasca NICIODATA fisierul
    din cache, oricat de lung ar fi `max-age`. Aici cererea de fisier primeste o sesiune goala
    si nu scrie nimic inapoi. Nu pierde nimic: fisierele se dau oricum fara login.

    Se aplica DOAR caii `/torqa/<fisier cu extensie>`; orice alta cerere merge ca inainte.
    """

    def open_session(self, app, request):
        if cerere_statica(request.path):
            return self.session_class()
        return super().open_session(app, request)

    def save_session(self, app, session, response):
        if has_request_context() and cerere_statica(request.path):
            return None
        return super().save_session(app, session, response)


# --------------------------------------------------------------- versiunea live

def _cale_pointer():
    return os.path.join(DIR_WEB, NUME_POINTER)


def versiune_live():
    """Id-ul versiunii live, sau None daca nu s-a urcat nimic (sau pointerul e stricat).

    Pointerul se valideaza, nu se crede: ajunge intr-o cale de pe disc, deci un continut
    care nu arata ca un id de versiune nu trebuie sa iasa din `DIR_WEB`."""
    try:
        with open(_cale_pointer(), encoding='utf-8') as fh:
            id_ = fh.read().strip()
    except OSError:
        return None
    if not ID_VERSIUNE.match(id_):
        return None
    if not os.path.isfile(os.path.join(DIR_WEB, id_, 'index.html')):
        return None
    return id_


def _cu_reincercari(functie, *args):
    """Apeleaza `functie`, reincercand de cateva ori la PermissionError.

    Pe Windows (masina de dezvoltare), un antivirus sau indexerul tine o clipa deschise
    fisierele abia scrise, iar `rename`/`replace` pe ele pica cu PermissionError; pe un test
    pornit in paralel cu altele s-a vazut. Pe Linux n-are cum sa apara, deci acolo bucla nu
    face nimic."""
    for incercare in range(5):
        try:
            return functie(*args)
        except PermissionError:
            if incercare == 4:
                raise
            time.sleep(0.1)


def _scrie_pointer(id_):
    """Pointerul se rescrie ATOMIC: se scrie intr-un fisier alaturat si se muta peste el."""
    cale = _cale_pointer()
    tmp = '%s.%s.tmp' % (cale, secrets.token_hex(3))
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(id_ + '\n')
            fh.flush()
            os.fsync(fh.fileno())
        _cu_reincercari(os.replace, tmp, cale)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def versiuni():
    """Toate versiunile de pe disc, cea mai noua prima."""
    try:
        nume = os.listdir(DIR_WEB)
    except OSError:
        return []
    return sorted((n for n in nume
                   if ID_VERSIUNE.match(n)
                   and os.path.isdir(os.path.join(DIR_WEB, n))
                   and not os.path.islink(os.path.join(DIR_WEB, n))), reverse=True)


def _taie_vechi(live):
    """Pastreaza versiunea live + PASTREAZA_ANTERIOARE cele mai noi; sterge restul.
    Intoarce lista celor ramase, cea mai noua prima."""
    toate = versiuni()
    pastrate = set(toate[:1 + PASTREAZA_ANTERIOARE]) | {live}
    for id_ in toate:
        if id_ not in pastrate:
            shutil.rmtree(os.path.join(DIR_WEB, id_), ignore_errors=True)
    return sorted(pastrate, reverse=True)


FORMAT_ID = '%Y%m%dT%H%M%S-%f'


def _id_nou():
    """Id de versiune: ora UTC pana la microsecunda, dar STRICT mai mare decat orice versiune
    de pe disc. Ceasul singur nu garanteaza asta: unul cu rezolutie grosiera da acelasi id la
    doua urcari apropiate, iar unul dat inapoi (NTP, reglare de mana) da unei versiuni noi un id
    mai mic decat al uneia vechi — adica o aseaza gresit in ordinea de care depinde taierea."""
    acum = datetime.now(timezone.utc)
    for existent in versiuni():
        try:
            ultima = datetime.strptime(existent, FORMAT_ID).replace(tzinfo=timezone.utc)
        except ValueError:                    # arata a id, dar nu e o data (director pus de mana)
            continue
        if acum <= ultima:
            acum = ultima + timedelta(microseconds=1)
        break
    return acum.strftime(FORMAT_ID)


def _curata_resturi():
    """Sterge directoarele/zip-urile temporare ramase de la o urcare cazuta la mijloc."""
    try:
        nume = os.listdir(DIR_WEB)
    except OSError:
        return
    limita = time.time() - VARSTA_RESTURI
    for n in nume:
        if not (n.startswith('.up-') or n.startswith('.tmp-')):
            continue
        cale = os.path.join(DIR_WEB, n)
        try:
            if os.path.getmtime(cale) >= limita:
                continue
            if os.path.isdir(cale) and not os.path.islink(cale):
                shutil.rmtree(cale, ignore_errors=True)
            else:
                os.remove(cale)
        except OSError:
            pass


# ------------------------------------------------------------ validare + extragere

def _segmente(nume):
    """Segmentele curate ale unei cai din arhiva, sau ValueError daca ar putea iesi din
    directorul tinta (zip-slip) ori nu e o cale pe care s-o scriem."""
    if '\x00' in nume:
        raise ValueError('nume cu octet NUL')
    n = nume.replace('\\', '/')       # unele unelte Windows scriu `\` in arhiva
    if n.startswith('/') or re.match(r'^[A-Za-z]:', n):
        raise ValueError('cale absoluta: %r' % nume)
    segmente = []
    for s in n.split('/'):
        if s in ('', '.'):
            continue
        if s == '..':
            raise ValueError('cale cu `..`: %r' % nume)
        if ':' in s:
            raise ValueError('cale cu `:` (litera de unitate / flux alternativ): %r' % nume)
        segmente.append(s)
    return segmente


def valideaza_zip(zf):
    """[(ZipInfo, [segmente])] pentru fisierele din arhiva, sau ValueError cu motivul.

    Respinge: cai absolute / cu `..` (zip-slip), legaturi simbolice si alte fisiere
    speciale, intrari criptate, nume duplicate sau in conflict (fisier si director cu
    acelasi nume), prea multe fisiere, descomprimat prea mare, lipsa `index.html` in
    radacina."""
    infos = zf.infolist()
    if len(infos) > MAX_FISIERE:
        raise ValueError('prea multe intrari (%d, maxim %d)' % (len(infos), MAX_FISIERE))

    intrari = []
    vazute = set()
    total = 0
    for info in infos:
        segmente = _segmente(info.filename)       # valideaza si numele directoarelor
        mod = info.external_attr >> 16
        if stat.S_ISLNK(mod):
            raise ValueError('legatura simbolica in arhiva: %r' % info.filename)
        tip = stat.S_IFMT(mod)
        if tip not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError('fisier special in arhiva: %r' % info.filename)
        if info.is_dir() or info.filename.endswith(('/', '\\')):
            continue
        if info.flag_bits & 0x1:
            raise ValueError('intrare criptata: %r' % info.filename)
        if not segmente:
            raise ValueError('nume gol: %r' % info.filename)
        cheie = '/'.join(segmente)
        if cheie in vazute:
            raise ValueError('nume duplicat in arhiva: %r' % cheie)
        vazute.add(cheie)
        total += info.file_size
        intrari.append((info, segmente))

    if total > MAX_DESCOMPRIMAT:
        raise ValueError('descomprimat prea mare (%d MB, maxim %d MB)'
                         % (total // 1024 // 1024, MAX_DESCOMPRIMAT // 1024 // 1024))
    directoare = set()
    for _, segmente in intrari:
        for i in range(1, len(segmente)):
            directoare.add('/'.join(segmente[:i]))
    conflict = vazute & directoare
    if conflict:
        raise ValueError('nume si de fisier, si de director: %r' % sorted(conflict)[0])
    if 'index.html' not in vazute:
        raise ValueError('lipseste index.html din radacina arhivei (zip-ul trebuie sa contina '
                         'CONTINUTUL folderului `browser`, nu folderul insusi)')
    return intrari


def _extrage(zf, intrari, tinta):
    """Scrie fisierele in `tinta`. Intoarce (numar de fisiere, octeti scrisi).

    Dimensiunile din antet pot minti, asa ca octetii se numara pe masura ce se scriu."""
    os.makedirs(tinta)
    baza = os.path.realpath(tinta)
    scrisi = 0
    for info, segmente in intrari:
        cale = os.path.join(tinta, *segmente)
        if os.path.commonpath([baza, os.path.realpath(cale)]) != baza:
            raise ValueError('cale in afara directorului tinta: %r' % info.filename)
        os.makedirs(os.path.dirname(cale), exist_ok=True)
        with zf.open(info) as sursa, open(cale, 'wb') as dest:
            for bloc in iter(lambda: sursa.read(1 << 20), b''):
                scrisi += len(bloc)
                if scrisi > MAX_DESCOMPRIMAT:
                    raise ValueError('descomprimat prea mare (peste %d MB)'
                                     % (MAX_DESCOMPRIMAT // 1024 // 1024))
                dest.write(bloc)
    return len(intrari), scrisi


def _verifica_baza(director):
    """Lista de avertismente despre `<base href>` din index.html; ValueError daca e gresit.

    Build-ul trebuie facut cu `--base-href /torqa/`: tot ce are Angular relativ (fisiere,
    rute, service worker) se rezolva fata de el. Gresit = o pagina alba, pe care nu o vezi
    la urcare. Se intampla chiar la prima incercare: in Git Bash, `--base-href /torqa/`
    devine o cale de Windows (`C:/Users/.../Git/torqa/`) daca nu setezi MSYS_NO_PATHCONV=1.
    Un `<base>` lipsa nu respinge (un build real il are mereu), dar se spune."""
    with open(os.path.join(director, 'index.html'), 'rb') as fh:
        inceput = fh.read(512 * 1024).decode('utf-8', 'replace')
    gasit = re.search(r'<base\b[^>]*?\bhref\s*=\s*(["\'])(.*?)\1', inceput, re.I | re.S)
    if gasit is None:
        return ['index.html nu are <base href="%s">' % PREFIX_URL]
    if gasit.group(2) != PREFIX_URL:
        raise ValueError(
            'index.html are <base href="%s"> in loc de "%s": build-ul se face cu '
            '`--base-href %s` (in Git Bash, cu MSYS_NO_PATHCONV=1 in fata, altfel calea '
            'devine una de Windows)' % (gasit.group(2), PREFIX_URL, PREFIX_URL))
    return []


def instaleaza(fisier):
    """Salveaza, valideaza, extrage si activeaza un build. `fisier` are `.save(cale)`.

    Ordinea conteaza: tot ce poate pica (zip-ul, validarea, extragerea) se intampla INAINTE
    de rescrierea pointerului, deci un build stricat nu atinge versiunea live."""
    os.makedirs(DIR_WEB, exist_ok=True)
    _curata_resturi()
    sufix = secrets.token_hex(4)
    zip_tmp = os.path.join(DIR_WEB, '.up-%s.zip' % sufix)
    dir_tmp = os.path.join(DIR_WEB, '.tmp-%s' % sufix)
    try:
        fisier.save(zip_tmp)
        marime_zip = os.path.getsize(zip_tmp)
        if marime_zip > MAX_ZIP:
            raise EroareBuild('zip prea mare (%d MB, maxim %d MB)'
                              % (marime_zip // 1024 // 1024, MAX_ZIP // 1024 // 1024), 413)
        with open(zip_tmp, 'rb') as fh:
            if fh.read(4) != MAGIC_ZIP:
                raise EroareBuild('nu e un zip (lipseste semnatura PK)')
        try:
            with zipfile.ZipFile(zip_tmp) as zf:
                intrari = valideaza_zip(zf)
                fisiere, octeti = _extrage(zf, intrari, dir_tmp)
            avertismente = _verifica_baza(dir_tmp)
        except (zipfile.BadZipFile, NotImplementedError, EOFError) as e:
            raise EroareBuild('zip corupt sau cu o compresie nesuportata: %s' % e)
        except ValueError as e:
            raise EroareBuild(str(e))

        # Doua urcari simultane pot alege acelasi id: cine pierde (directorul exista deja)
        # isi ia alt id si incearca din nou.
        for incercare in range(5):
            id_ = _id_nou()
            final = os.path.join(DIR_WEB, id_)
            try:
                _cu_reincercari(os.rename, dir_tmp, final)
                break
            except OSError:
                if incercare == 4 or not os.path.exists(final):
                    raise
        try:
            _scrie_pointer(id_)             # AICI se schimba versiunea live
        except BaseException:
            # Un director care n-a ajuns live ar ramane pe disc ca „versiune noua" si ar
            # impinge afara, la taiere, o versiune buna de intoarcere.
            shutil.rmtree(final, ignore_errors=True)
            raise
        ramase = _taie_vechi(id_)
        logger.info('Torqa web: versiunea %s live (%d fisiere, %d KB); raman %s',
                    id_, fisiere, octeti // 1024, ', '.join(ramase))
        for a in avertismente:
            logger.warning('Torqa web: versiunea %s: %s', id_, a)
        return {
            'version': id_,
            'files': fisiere,
            'size': octeti,
            'zip_size': marime_zip,
            'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'kept': ramase,
            'warnings': avertismente,
        }
    finally:
        if os.path.exists(zip_tmp):
            os.remove(zip_tmp)
        if os.path.isdir(dir_tmp):
            shutil.rmtree(dir_tmp, ignore_errors=True)


@torqa_web_bp.route('/api/torqa/web/upload', methods=['POST'])
def torqa_web_upload():
    """Urca un build web Torqa (zip cu CONTINUTUL folderului `browser`). Doar
    masina-la-masina (Bearer PIF_API_TOKEN), ca `/api/app/upload`.

    Deliberat FARA sesiune, iar tokenul de dispozitiv e refuzat (`DEVICE_TOKEN_DENIED`):
    ruta inlocuieste cod care ruleaza in browserul lui Ion, pe domeniul dashboardului.
    Camp: `zip`. Raspuns: {ok, version, files, size, zip_size, at, kept, warnings}.
    """
    if not _check_api_token():
        return jsonify({'error': 'Unauthorized'}), 401
    if request.content_length is not None and request.content_length > MAX_ZIP + MARGINA_FORMULAR:
        return jsonify({'error': 'zip prea mare (maxim %d MB)' % (MAX_ZIP // 1024 // 1024)}), 413
    f = request.files.get('zip')
    if f is None:
        return jsonify({'error': 'Lipseste fisierul (camp `zip`).'}), 400
    try:
        rezultat = instaleaza(f)
    except EroareBuild as e:
        logger.warning('Torqa web: build respins: %s', e)
        return jsonify({'error': str(e)}), e.status
    except OSError:
        logger.exception('Torqa web: urcarea a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la instalarea build-ului.'}), 500
    return jsonify({'ok': True, **rezultat})


# ------------------------------------------------------------------- servirea

def _cale_in(baza, rest):
    """Calea unui fisier din `baza`, sau None: iese din director, nu exista sau nu e fisier.

    `safe_join` respinge `..` si caile absolute; `realpath` prinde in plus o legatura
    simbolica sau o jonctiune (arhiva nu poate crea una, dar pointerul poate arata spre un
    director modificat de mana)."""
    cale = safe_join(baza, rest)
    if cale is None:
        return None
    real_baza = os.path.realpath(baza)
    real = os.path.realpath(cale)
    try:
        if os.path.commonpath([real_baza, real]) != real_baza:
            return None
    except ValueError:                       # unitati diferite pe Windows
        return None
    return cale if os.path.isfile(real) else None


def _tip(nume):
    return TIPURI.get(os.path.splitext(nume)[1].lower(), TIP_IMPLICIT)


def _cache_control(rest):
    baza = rest.rsplit('/', 1)[-1]
    if baza in FARA_CACHE:
        return 'no-cache'
    # `assets/` e copiat de Angular fara hash, chiar daca un nume arata a hash.
    if not rest.startswith('assets/') and HASH_IN_NUME.search(baza):
        return CACHE_IMUABIL
    return 'no-cache'


def _trimite(cale, rest):
    r = send_file(cale, mimetype=_tip(rest), conditional=True)
    r.headers['Cache-Control'] = _cache_control(rest)
    return r


def _neinstalat():
    r = Response(
        '<!doctype html><meta charset="utf-8"><title>Torqa web</title>'
        '<h1>503</h1><p>Torqa web nu este instalat inca (nu s-a urcat niciun build). '
        'Torqa web is not installed yet.</p>',
        status=503, mimetype='text/html')
    r.headers['Cache-Control'] = 'no-store'
    r.headers['Retry-After'] = '300'
    return r


@torqa_web_bp.route('/torqa', methods=['GET'])
def torqa_fara_slash():
    return redirect(PREFIX_URL, code=301)


@torqa_web_bp.route('/torqa/', methods=['GET'])
def torqa_start():
    return _serveste('')


@torqa_web_bp.route('/torqa/<path:rest>', methods=['GET'])
def torqa_cale(rest):
    return _serveste(rest)


def _serveste(rest):
    """Documentul cere sesiune; fisierele nu. Vezi antetul modulului."""
    fisier = arata_ca_fisier(rest)
    if not fisier:
        if 'authenticated' not in session:
            return redirect(LOGIN_CU_INTOARCERE)
        rest = 'index.html'
    id_ = versiune_live()
    if id_ is None:
        return _neinstalat()
    cale = _cale_in(os.path.join(DIR_WEB, id_), rest)
    if cale is None:
        abort(404)
    return _trimite(cale, rest)
