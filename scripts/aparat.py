# -*- coding: utf-8 -*-
"""Puntea catre TELEFONUL REAL: adb + CDP peste WebView-ul aplicatiei Torqa.

DE CE EXISTA. Toate celelalte probe emuleaza tastatura — `audit_tastatura.py`
micsoreaza viewportul cu `set_viewport_size`, fiindca asta e ce PARE ca face
Capacitor. Dar e o reconstituire, nu o observatie: nimeni n-a vazut vreodata ce
face IME-ul adevarat pe aparatul adevarat. Trei runde de reglaje au trecut de
probe si n-au schimbat nimic pe telefon.

Aici nu se emuleaza nimic:
  * atingerea e `adb shell input tap` — un eveniment de sistem, deci Gboard
    chiar se ridica (Playwright n-ar putea: evenimentele lui stau in pagina si
    nu ajung niciodata la IME);
  * geometria se citeste din CHIAR WebView-ul aplicatiei, prin CDP;
  * ce se masoara e ce vede Ion.

CONDITII. WebView-ul trebuie sa fie inspectabil, adica APK-ul instalat sa aiba
`android.webContentsDebuggingEnabled: true` in `capacitor.config.json`
(`CapConfig.java:286` — implicit ia valoarea lui FLAG_DEBUGGABLE, care pe un
release e 0). Se verifica cu `socket_devtools()`: fara socket, nu e inspectabil.
"""
import os
import re
import subprocess
import time

ADB = os.environ.get('PIF_ADB', r'C:\Users\ion.ursu\Repos\Tools\android-sdk\platform-tools\adb.exe')
PACHET = 'org.iupif.pif'
PORT = 9222


def adb(*args, timeout=60):
    """Iesirea lui adb, ca text. Se decodeaza NOI, cu `replace`: `dumpsys` scoate
    octeti care nu sunt UTF-8 (nume de aplicatii, resurse), iar `text=True` ar
    incerca cp1252 si ar arunca UnicodeDecodeError la jumatatea unui raport de
    care ne trebuia o singura linie."""
    b = subprocess.run([ADB, *args], capture_output=True, timeout=timeout).stdout
    return (b or b'').decode('utf-8', 'replace')


def aparat():
    """Numele aparatului conectat, sau None."""
    for linie in adb('devices', '-l').splitlines()[1:]:
        if '\tdevice' in linie or ' device ' in linie:
            return linie.split()[0]
    return None


def pid_aplicatie():
    p = adb('shell', 'pidof', PACHET).strip()
    return p.split()[0] if p else None


def socket_devtools():
    """Numele socketului DevTools al WebView-ului, sau None daca nu e inspectabil.

    Forma: `@webview_devtools_remote_<pid>`. `@` inseamna socket abstract; `adb
    forward localabstract:` il vrea FARA `@`.
    """
    iesire = adb('shell', 'cat', '/proc/net/unix')
    for linie in iesire.splitlines():
        m = re.search(r'@?(webview_devtools_remote_\d+)', linie)
        if m:
            return m.group(1)
    return None


def porneste_aplicatia(asteapta=4.0):
    adb('shell', 'monkey', '-p', PACHET, '-c', 'android.intent.category.LAUNCHER', '1')
    time.sleep(asteapta)


def deschide_puntea(port=PORT):
    """Leaga `localhost:<port>` de socketul WebView-ului. Intoarce numele socketului."""
    s = socket_devtools()
    if not s:
        return None
    adb('forward', '--remove-all')
    adb('forward', 'tcp:%d' % port, 'localabstract:%s' % s)
    return s


def tinte(port=PORT):
    import requests
    return requests.get('http://localhost:%d/json/list' % port, timeout=10).json()


# ---------------------------------------------------------------- atingerea

def ecran():
    """Latimea si inaltimea FIZICA a ecranului, in pixeli de aparat."""
    m = re.search(r'(\d+)x(\d+)', adb('shell', 'wm', 'size'))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def atinge(x, y, pauza=0.0):
    """Atingere ADEVARATA, la nivel de sistem — singura care ridica IME-ul.

    Coordonatele sunt in pixeli de APARAT, nu CSS: vezi `catre_aparat`.
    """
    adb('shell', 'input', 'tap', str(int(x)), str(int(y)))
    if pauza:
        time.sleep(pauza)


def catre_aparat(page, x_css, y_css):
    """Pixeli CSS din WebView -> pixeli de aparat.

    Aplicatia e edge-to-edge (`setDecorFitsSystemWindows(false)` in
    MainActivity), deci originea WebView-ului coincide cu originea ecranului si
    e de ajuns scara `devicePixelRatio`.
    """
    dpr = page.evaluate('window.devicePixelRatio')
    return x_css * dpr, y_css * dpr


def tastatura_sus():
    """Cat ocupa IME-ul ACUM, in pixeli de aparat, dupa sistem (nu dupa pagina)."""
    d = adb('shell', 'dumpsys', 'input_method') or ''
    m = re.search(r'mVisibleInsets=Rect\((\d+), (\d+) - (\d+), (\d+)\)', d)
    if m:
        return int(m.group(4))
    return 1 if 'mInputShown=true' in d else 0


def ascunde_tastatura():
    """Coboara IME-ul si asteapta sa se aseze."""
    adb('shell', 'input', 'keyevent', '111')   # ESCAPE
    time.sleep(0.6)


# ------------------------------------------------------------------- ecranul

def trezeste():
    """Aprinde ecranul si scoate blocarea.

    OBLIGATORIU inainte de orice masuratoare: pe un ecran stins WebView-ul nu
    randeaza (deci `requestAnimationFrame` NU se declanseaza si urma iese goala),
    iar `input tap` nu trezeste aparatul — atingerea se pierde pur si simplu.
    Ambele esecuri arata identic: „foaia nu s-a deschis", fara nicio eroare.
    """
    adb('shell', 'input', 'keyevent', '224')      # KEYCODE_WAKEUP
    time.sleep(0.5)
    if 'mDreamingLockscreen=true' in adb('shell', 'dumpsys', 'window'):
        adb('shell', 'input', 'keyevent', '82')   # MENU — scoate ecranul de blocare
        time.sleep(0.5)


def tine_ecranul_aprins(da=True):
    """Cat timp e conectat pe USB, ecranul nu se mai stinge.

    Se PUNE LA LOC la sfarsit (`tine_ecranul_aprins(False)`) — e o setare pe
    telefonul lui Ion, nu a probei.
    """
    adb('shell', 'svc', 'power', 'stayon', 'usb' if da else 'false')


def randeaza():
    """Chiar deseneaza WebView-ul acum? Verificarea directa, nu prin `dumpsys`."""
    return 'mWakefulness=Awake' in adb('shell', 'dumpsys', 'power')
