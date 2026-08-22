# -*- coding: utf-8 -*-
"""FILMEAZA PORNIREA RECE, PE APARAT.

DE CE EXISTA. Pornirea rece e singura secventa din aplicatie care nu se poate
masura din afara: sonda injectata prin CDP moare odata cu WebView-ul vechi, iar
o captura prin USB soseste la ~1.8s — adica dupa ce s-a terminat tot ce voiam sa
vad. Trei runde de reparatii pe splash au mers pe deductie din cauza asta.

`screenrecord` ruleaza PE telefon si filmeaza la rata ecranului. Deci vede si
splashul de sistem (desenat inainte ca WebView-ul sa existe), si clipa in care
el se scoate — exact cusatura despre care intreaba Ion.

CUM SE CITESTE. Pentru fiecare cadru masor doua lucruri: culoarea medie (ca sa
prind un cadru de alb sau de negru strecurat intre splash si pagina) si cat
„continut" e pe ecran — pixeli departe de fondul paginii. Splashul are putin
continut (o placa mica), pagina are mult. Saltul dintre ele e tranzitia; orice
cadru intermediar cu alta culoare medie sau cu continut zero e clipirea.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ADB = r'C:\Users\ion.ursu\Repos\Tools\android-sdk\platform-tools\adb.exe'
PACHET = 'org.iupif.pif'
PE_TELEFON = '/sdcard/pornire.mp4'
SECUNDE = 7


def adb(*a, **kw):
    return subprocess.run([ADB] + list(a), capture_output=True, text=True, **kw)


def filmeaza(dosar):
    os.makedirs(dosar, exist_ok=True)
    local = os.path.join(dosar, 'pornire.mp4')

    adb('shell', 'input', 'keyevent', 'KEYCODE_WAKEUP')
    adb('shell', 'am', 'force-stop', PACHET)
    adb('shell', 'rm', '-f', PE_TELEFON)
    time.sleep(1.0)

    # Camera porneste INAINTE de aplicatie: screenrecord are el insusi o
    # intarziere de pornire, iar daca lansam simultan, primele cadre — chiar
    # splashul — s-ar pierde.
    cam = subprocess.Popen(
        [ADB, 'shell', 'screenrecord', '--time-limit', str(SECUNDE),
         '--bit-rate', '12000000', '--size', '540x1170', PE_TELEFON],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

    t0 = time.time()
    adb('shell', 'am', 'start', '-n', PACHET + '/.MainActivity')
    print('  aplicatia lansata la %.2fs in film' % (time.time() - t0 + 1.5))

    cam.wait(timeout=SECUNDE + 25)
    time.sleep(1.0)
    adb('pull', PE_TELEFON, local)
    return local


def taie_cadre(mp4, dosar):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cadre = os.path.join(dosar, 'cadre')
    os.makedirs(cadre, exist_ok=True)
    for f in os.listdir(cadre):
        os.remove(os.path.join(cadre, f))
    subprocess.run([ff, '-y', '-i', mp4, '-vf', 'fps=60',
                    os.path.join(cadre, 'c_%04d.png')],
                   capture_output=True)
    return cadre


def citeste(cadre):
    """Culoarea medie si cantitatea de continut, cadru cu cadru."""
    from PIL import Image
    nume = sorted(os.listdir(cadre))
    randuri = []
    for i, n in enumerate(nume):
        im = Image.open(os.path.join(cadre, n)).convert('RGB')
        mic = im.resize((54, 117))          # 10x mai mic: destul pentru statistici
        px = list(mic.getdata())
        med = tuple(sum(c[k] for c in px) // len(px) for k in range(3))
        # „Continut" = pixeli departe de culoarea medie a cadrului. Splashul e
        # aproape uniform; pagina are text, linii, carduri.
        dep = sum(1 for c in px
                  if abs(c[0] - med[0]) + abs(c[1] - med[1]) + abs(c[2] - med[2]) > 40)
        randuri.append((i / 60.0, med, dep * 100 // len(px)))
    return nume, randuri


if __name__ == '__main__':
    dosar = sys.argv[1] if len(sys.argv) > 1 else 'film_pornire'
    mp4 = filmeaza(dosar)
    cadre = taie_cadre(mp4, dosar)
    nume, randuri = citeste(cadre)
    print('\n  timp     culoare medie      continut   cadru')
    ant = None
    for (t, med, dep), n in zip(randuri, nume):
        cheie = (med[0] // 6, med[1] // 6, med[2] // 6, dep // 3)
        if cheie != ant:
            ant = cheie
            print('  %5.3fs  rgb(%3d,%3d,%3d)      %3d%%     %s' % (t, med[0], med[1], med[2], dep, n))
    print('\n  (se afiseaza doar cadrele care SCHIMBA ceva; restul sunt identice)')
