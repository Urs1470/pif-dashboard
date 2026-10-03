"""`requirements.txt` si importurile serverului spun acelasi lucru.

Doua feluri de abatere, amandoua tacute:
  - un pachet in `requirements.txt` pe care nu-l importa nimeni (`flask-compress`, `pyyaml`,
    `pymupdf`, `openpyxl` stateau acolo de la functii disparute; `pdfplumber` si `reportlab` au plecat
    odata cu parserele de parametri si cu exportul PDF). Fiecare e descarcat si instalat la fiecare
    deploy, pentru nimic;
  - un import de pachet strain in codul serverului care nu e in `requirements.txt`: merge pe masina
    de dezvoltare (unde pachetul e instalat) si pica la prima pornire pe un venv curat.

Scripturile (`scripts/`), testele si hook-urile ruleaza doar pe masina de dezvoltare, cu `requests`
si `pyflakes` instalate de mana (vezi CLAUDE.md): nu intra in `requirements.txt`.
"""

import ast
import os
import re
import sys

from _baza import RADACINA, Test

EXCLUSE = {'.git', 'venv', '.venv', 'uploads', '__pycache__', 'node_modules'}
# Ce porneste serverul fara sa fie importat de cod: gunicorn il lanseaza systemd-ul.
FARA_IMPORT = {'gunicorn': 'procesul care serveste aplicatia (unitatea systemd)'}
# Pachetele pe care le aduce flask odata cu el: se pot importa fara sa fie scrise in requirements.
DIN_FLASK = {'werkzeug', 'jinja2', 'markupsafe', 'itsdangerous', 'click', 'blinker'}
DEZVOLTARE = {'requests', 'pyflakes'}          # CLAUDE.md: `pip install pyflakes requests`


def importuri(cale):
    """Numele de top ale modulelor importate in fisierul `cale` (importurile relative nu conteaza)."""
    with open(cale, encoding='utf-8') as fh:
        arbore = ast.parse(fh.read(), filename=cale)
    nume = set()
    for n in ast.walk(arbore):
        if isinstance(n, ast.Import):
            nume.update(a.name.split('.')[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            nume.add(n.module.split('.')[0])
    return nume


def fisiere_py():
    """(cale relativa, cale absoluta) pentru fiecare .py din depozit."""
    for radacina, dosare, fisiere in os.walk(RADACINA):
        dosare[:] = [d for d in dosare if d not in EXCLUSE]
        for f in fisiere:
            if f.endswith('.py'):
                absoluta = os.path.join(radacina, f)
                yield os.path.relpath(absoluta, RADACINA).replace('\\', '/'), absoluta


def locale():
    """Modulele depozitului insusi: fisierele .py din radacina si pachetele/directoarele cu cod."""
    nume = {os.path.splitext(f)[0] for f in os.listdir(RADACINA) if f.endswith('.py')}
    for d in os.listdir(RADACINA):
        if os.path.isdir(os.path.join(RADACINA, d)) and d not in EXCLUSE:
            nume.add(d)
    for sub in ('scripts', 'teste', os.path.join('.claude', 'hooks')):
        cale = os.path.join(RADACINA, sub)
        if os.path.isdir(cale):
            nume.update(os.path.splitext(f)[0] for f in os.listdir(cale) if f.endswith('.py'))
    return nume


def cerinte():
    """{nume pachet normalizat: linia} din requirements.txt."""
    out = {}
    with open(os.path.join(RADACINA, 'requirements.txt'), encoding='utf-8') as fh:
        for linie in fh:
            linie = linie.split('#', 1)[0].strip()
            if linie:
                nume = re.split(r'[=<>!~\[; ]', linie, maxsplit=1)[0]
                out[re.sub(r'[-_.]+', '-', nume).lower()] = linie
    return out


def modul_pachet(nume):
    """Numele sub care se importa pachetul (aici coincid cu numele pachetului)."""
    return nume.replace('-', '_')


class CerinteSiImporturi(Test):

    def test_fiecare_pachet_din_requirements_este_importat_undeva(self):
        importate = set()
        for _, absoluta in fisiere_py():
            importate |= importuri(absoluta)
        necitite = [linie for nume, linie in cerinte().items()
                    if modul_pachet(nume) not in importate and nume not in FARA_IMPORT]
        self.assertEqual(necitite, [], 'pachete instalate la fiecare deploy si neimportate de nimeni')

    def test_requirements_nu_mai_are_pachetele_scoase(self):
        scoase = {'flask-compress', 'pyyaml', 'pymupdf', 'openpyxl', 'pdfplumber', 'reportlab',
                  'pywebpush', 'cryptography'}
        self.assertEqual(sorted(set(cerinte()) & scoase), [])

    def test_codul_serverului_importa_doar_ce_e_in_requirements(self):
        stdlib = set(sys.stdlib_module_names)
        proprii = locale()
        permise = {modul_pachet(n) for n in cerinte()} | DIN_FLASK
        abateri = []
        for rel, absoluta in fisiere_py():
            if rel.startswith(('scripts/', 'teste/', '.claude/')):
                continue                                   # doar pe masina de dezvoltare
            for m in importuri(absoluta):
                if m not in stdlib and m not in proprii and m not in permise:
                    abateri.append('%s importa `%s`' % (rel, m))
        self.assertEqual(abateri, [], 'import de pachet strain care nu e in requirements.txt')

    def test_ce_ruleaza_doar_pe_masina_de_dezvoltare_ramane_in_afara_requirements(self):
        self.assertEqual(sorted(set(cerinte()) & DEZVOLTARE), [])
        # Si e cu adevarat folosit doar de scripturi/teste/hook-uri, nu de server.
        for rel, absoluta in fisiere_py():
            if not rel.startswith(('scripts/', 'teste/', '.claude/')):
                self.assertFalse(importuri(absoluta) & DEZVOLTARE, rel)


if __name__ == '__main__':
    import unittest
    unittest.main()
