# Alertele centralizatorului de materiale, calculate pe server la `PUT /api/materiale`.
#
# Pana pe 2026-11-17 le calcula colectorul de pe PC-ul de job (Knowledge `tools/materiale-colector.ps1`),
# care crea si taskurile prin `POST /api/proiecte/<id>/tasks`. Acum PC-ul doar interogheaza E100, BC si
# Outlook, iar regulile stau aici, intr-un singur loc. Comutarea: colectorul trimite `sursa.alerte = "server"`;
# fara flag, serverul pastreaza alertele trimise (comportamentul de dinainte). Decizia:
# docs/decizii/2026-11-17-materiale-alerte-pe-server.md.
#
# Regulile (MdL rev2, Cazul B: materialul urgent se comanda pe mail, LM-ul vine in cel mult 2 zile lucratoare;
# Knowledge wiki/job/team/e100-definire-proiect.md, § Comanda de materiale dupa definire):
#   comanda_fara_lm        o comanda trimisa de Ion pe mail (`comanda_mea`), fara LM dupa 2 zile lucratoare.
#                          Acoperita daca un CT pomenit pe firul ei are LM in BC, sau daca exista un LM creat de
#                          Ion (`sursa.utilizator`) in E100 in ziua comenzii ori dupa.
#   ct_fara_lm             un CT al proiectului fara LM in BC, dupa 2 zile lucratoare de la crearea lui. Nu se
#                          dubleaza cu un comanda_fara_lm de pe acelasi fir.
#   fara_linii_pontaj      contract in E100 de cel putin 2 zile lucratoare (`contract_data`) si nicio linie de
#                          pontaj din contract (`linii_contract`).
#   livrare_dupa_start     termene (confirmate sau planificate) dupa startul urmatoarei perioade planificate;
#   livrare_aproape_start  termene cu cel mult o saptamana inainte de start (cererea lui Ion din 09.11).
# Zilele lucratoare sunt L-V, fara sarbatori. „Azi" e ziua din `generat` (ora PC-ului), nu ceasul serverului.
#
# Textele, titlurile si id-urile de task sunt cele ale colectorului, caracter cu caracter: un task deja creat de
# PC primeste acelasi id (SHA-1 pe `pif-materiale|<proiect>|<tip>|<ref>`), deci nu se dubleaza.

import hashlib
import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger('pif_dashboard')

LQ, RQ = '„', '”'
STARI_CU_TERMEN = ('confirmat', 'planificat')


# --------------------------------------------------------------------------- ajutoare

def _zi(s):
    """`YYYY-MM-DD` (sau un ISO mai lung) -> date; None la gol sau text stricat."""
    if not isinstance(s, str) or len(s) < 10:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def zile_lucratoare_dupa(d, azi):
    """Zilele L-V scurse dupa ziua `d`, pana la `azi` inclusiv (Get-WorkdaysSince din colector)."""
    n, x = 0, d + timedelta(days=1)
    while x <= azi:
        if x.weekday() < 5:
            n += 1
        x += timedelta(days=1)
    return n


def id_stabil(nume):
    """Id determinist in format UUID (versiunea 5 ca forma: SHA-1 pe nume), identic cu New-StableId din colector."""
    b = bytearray(hashlib.sha1(('pif-materiale|' + nume).encode('utf-8')).digest())
    b[6] = (b[6] & 0x0F) | 0x50
    b[8] = (b[8] & 0x3F) | 0x80
    h = bytes(b[:16]).hex()
    return '%s-%s-%s-%s-%s' % (h[:8], h[8:12], h[12:16], h[16:20], h[20:32])


def _dm(d):
    return d.strftime('%d.%m')


def _dmy(d):
    return d.strftime('%d.%m.%Y')


def _unice(xs):
    out = []
    for x in xs:
        if x and x not in out:
            out.append(x)
    return out


# --------------------------------------------------------------------------- regulile

def alerte_start(materiale, perioada):
    """Marcheaza fiecare material cu `fata_de_start` (dupa | aproape | None) si intoarce alertele de livrare
    fata de startul perioadei (cel mult una pe tip). Fara perioada: marcajele raman neatinse, nicio alerta."""
    if not perioada or not _zi(perioada.get('data_start')):
        return []
    s = str(perioada['data_start'])[:10]
    start = _zi(s)
    limita = (start - timedelta(days=7)).isoformat()
    dupa, aproape = [], []
    for m in materiale:
        if not isinstance(m, dict):
            continue
        m['fata_de_start'] = None
        if m.get('termen_tip') not in STARI_CU_TERMEN or not m.get('termen'):
            continue
        t = str(m['termen'])
        if t > s:
            m['fata_de_start'] = 'dupa'
            dupa.append(m)
        elif t >= limita:
            m['fata_de_start'] = 'aproape'
            aproape.append(m)

    def lista(xs):
        ordonate = sorted(xs, key=lambda m: str(m.get('termen')))
        bucati = ['%s (%s %s)' % (m.get('descriere') or '', _dm(_zi(m['termen'])), m.get('termen_tip')) for m in ordonate[:5]]
        return '; '.join(bucati) + ('; încă %d' % (len(xs) - 5) if len(xs) > 5 else '')

    ref = 'perioada|%s|%s' % (perioada.get('id'), s)
    out = []
    if dupa:
        out.append({'tip': 'livrare_dupa_start', 'din': s, 'ref': ref, 'n': len(dupa),
                    'text': 'Perioada planificată începe pe %s, iar %d materiale vin după start: %s'
                            % (_dm(start), len(dupa), lista(dupa))})
    if aproape:
        out.append({'tip': 'livrare_aproape_start', 'din': s, 'ref': ref, 'n': len(aproape),
                    'text': 'Perioada planificată începe pe %s, iar %d materiale vin cu cel mult o săptămână înainte: %s'
                            % (_dm(start), len(aproape), lista(aproape))})
    return out


def alerte_proiect(p, azi, utilizator, perioada):
    """Alertele unui proiect din snapshot, in ordinea colectorului: comenzi pe mail, CT-uri, liniile de pontaj,
    apoi livrarile fata de start. Scrie si marcajele `fata_de_start` si campurile `perioada`, `dupa_start`,
    `aproape_start` din `rezumat` (pe obiectul primit)."""
    cod = p.get('cod_proiect') or ''
    mailuri = [m for m in (p.get('mailuri') or []) if isinstance(m, dict)]
    lm = [x for x in (p.get('lm') or []) if isinstance(x, dict)]
    termene = [x for x in (p.get('termene') or []) if isinstance(x, dict)]
    necomandate = [x for x in (p.get('necomandate') or []) if isinstance(x, dict)]
    materiale = [x for x in (p.get('materiale') or []) if isinstance(x, dict)]

    ct_lm = {}                                       # CT -> are LM in BC
    for r in termene + necomandate:
        if r.get('lm') is not None:
            ct_lm[r.get('ct')] = True
        elif r.get('ct') not in ct_lm:
            ct_lm[r.get('ct')] = False

    alerte, acoperite = [], set()
    for c in mailuri:
        if not c.get('comanda_mea'):
            continue
        d = _zi(c.get('data'))
        if d is None:
            continue
        fir_ct = _unice(x for m in mailuri if m.get('fir') == c.get('fir') for x in (m.get('ct') or []))
        acoperite.update(fir_ct)
        if fir_ct and not any(x in ct_lm for x in fir_ct):
            continue                                 # CT-urile firului au iesit din BC: comanda e incheiata
        are_lm_pe_ct = any(ct_lm.get(x) for x in fir_ct)
        are_lm_al_meu = bool(utilizator) and any(
            _zi(x.get('creat')) is not None and _zi(x.get('creat')) >= d
            and str(x.get('creat_de') or '').lower() == utilizator.lower() for x in lm)
        if are_lm_pe_ct or are_lm_al_meu:
            continue
        zile = zile_lucratoare_dupa(d, azi)
        if zile < 2:
            continue
        text = 'Comanda pe mail din %s (%s%s%s) nu are LM în E100 după %d zile lucrătoare' % (
            _dmy(d), LQ, c.get('subiect') or '', RQ, zile)
        if fir_ct:
            text += ' (pe fir: %s)' % ', '.join(fir_ct)
        alerte.append({'tip': 'comanda_fara_lm', 'din': d.isoformat(),
                       'ref': c.get('entry_id') or 'mail|%s|%s' % (c.get('data'), c.get('fir')),
                       'text': text, 'entry_id': c.get('entry_id'), 'subiect': c.get('subiect')})

    cu_data = {}
    for r in necomandate:
        if r.get('data_creare_ct'):
            cu_data[r.get('ct')] = r['data_creare_ct']
    for ct in sorted(k for k, v in ct_lm.items() if not v and k and k != '(fara CT)'):
        if ct in acoperite:
            continue
        din = cu_data.get(ct)
        if din and _zi(din) and zile_lucratoare_dupa(_zi(din), azi) < 2:
            continue
        cine = ', '.join(_unice(r.get('achizitor') for r in necomandate if r.get('ct') == ct))
        text = '%s nu e alocat pe niciun LM în BC' % ct
        if din and _zi(din):
            text += ' (creat %s' % _dmy(_zi(din)) + (', achizitor %s' % cine if cine else '') + ')'
        alerte.append({'tip': 'ct_fara_lm', 'din': din, 'ref': ct, 'text': text})

    dc = _zi(p.get('contract_data'))
    if dc and p.get('linii_contract') == 0 and zile_lucratoare_dupa(dc, azi) >= 2:
        alerte.append({'tip': 'fara_linii_pontaj', 'din': dc.isoformat(), 'ref': cod,
                       'text': 'Proiectul %s are contract în E100 din %s, dar nicio linie de pontaj deschisă' % (cod, _dmy(dc))})

    start = alerte_start(materiale, perioada)
    rez = p.get('rezumat')
    if isinstance(rez, dict):
        rez['perioada'] = ({'id': perioada.get('id'), 'data_start': perioada.get('data_start'),
                            'data_sfarsit': perioada.get('data_sfarsit'), 'faza': perioada.get('faza')}
                           if perioada else None)
        rez['dupa_start'] = sum(1 for m in materiale if m.get('fata_de_start') == 'dupa')
        rez['aproape_start'] = sum(1 for m in materiale if m.get('fata_de_start') == 'aproape')
    alerte.extend(start)
    return alerte


# --------------------------------------------------------------------------- taskurile

def task_pentru(p, a, azi):
    """{id, titlu, descriere, data_scadenta} pentru o alerta: textele colectorului (pasul 6 din materiale-colector.ps1)."""
    cod = p.get('cod_proiect') or ''
    tip = a['tip']
    din = _zi(a.get('din'))
    if tip == 'comanda_fara_lm':
        titlu = 'Fă LM-ul în E100 pentru comanda din %s (%s)' % (_dm(din), cod)
    elif tip == 'livrare_dupa_start':
        titlu = 'Materiale care vin după startul din %s (%s)' % (_dm(din), cod)
    elif tip == 'livrare_aproape_start':
        titlu = 'Materiale cu cel mult o săptămână înainte de startul din %s (%s)' % (_dm(din), cod)
    elif tip == 'fara_linii_pontaj':
        titlu = 'Cere deschiderea liniilor de pontaj pe %s' % cod
    else:
        titlu = 'Fă LM-ul în E100 pentru %s (%s)' % (a.get('ref'), cod)
    desc = a['text'] + '.'
    if a.get('entry_id'):
        desc += '\n\nDin mail: [%s%s%s](outlook:%s)' % (LQ, a.get('subiect') or '', RQ, a['entry_id'])
    scad = None
    if tip == 'fara_linii_pontaj':
        desc += ('\n\nLiniile se deschid din Comercial (DL_ELECTROGLOBAL_COMERCIAL_PROIECTE); fără ele nu poți ponta pe '
                 'proiect. Verificare: .\\tools\\egb.ps1 linii %s. Alerta vine din colectorul de materiale; taskul îl '
                 'bifezi tu.' % cod)
    elif tip.startswith('livrare_'):
        scad = max(din - timedelta(days=7), azi).isoformat()
        desc += ('\n\nTermenele se compară cu începutul perioadei planificate (cererea ta din 09.11). Lista la zi e pe '
                 'pagina Materials; taskul îl bifezi tu.')
    else:
        desc += ('\n\nRegula: MdL rev2, Cazul B (LM-ul în cel mult 2 zile lucrătoare de la comanda pe mail). Alerta vine '
                 'din colectorul de materiale; taskul îl bifezi tu.')
    return {'id': id_stabil('%s|%s|%s' % (p['proiect_id'], tip, a.get('ref'))), 'titlu': titlu, 'descriere': desc,
            'data_scadenta': scad}


def perioada_urmatoare(cursor, proiect_id, azi):
    """Urmatoarea perioada care n-a trecut (inclusiv una in curs), ca in colector: din `/api/calendar` (200 de zile),
    cea cu sfarsitul (sau startul) >= azi, cea mai devreme. Doar citeste `implementari`."""
    cursor.execute("""
        SELECT id, data_start, data_sfarsit, faza FROM implementari
        WHERE proiect_id = ? AND data_start IS NOT NULL AND data_start != ''
          AND date(data_start) < date(?, '+200 days')
          AND COALESCE(NULLIF(data_sfarsit, ''), data_start) >= ?
        ORDER BY data_start LIMIT 1
    """, (proiect_id, azi.isoformat(), azi.isoformat()))
    r = cursor.fetchone()
    return dict(r) if r else None


def creeaza_taskuri(conn, taskuri):
    """[(proiect_id, task)] -> (noi, existente, sarite). Acelasi INSERT ca `create_task` din blueprints/tasks.py (status
    to_do, ordinea la coada proiectului); un id care exista deja se sare (colectorul primea 409), la fel un proiect sters.
    Nu bifeaza si nu sterge nimic."""
    noi = existente = sarite = 0
    cur = conn.cursor()
    for pid, t in taskuri:
        cur.execute('SELECT 1 FROM tasks WHERE id = ?', (t['id'],))
        if cur.fetchone() is not None:
            existente += 1
            continue
        cur.execute('SELECT 1 FROM proiecte WHERE id = ?', (pid,))
        if cur.fetchone() is None:
            sarite += 1
            continue
        cur.execute('SELECT MAX(ordine) AS m FROM tasks WHERE proiect_id = ?', (pid,))
        r = cur.fetchone()
        ordine = (r['m'] if r and r['m'] is not None else 0) + 1
        acum = datetime.now().isoformat()
        cur.execute('''
            INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta, data_finalizare, ordine, created_at,
                               descriere, recurenta, updated_at, implementare_id, decalaj_zile, recurenta_baza)
            VALUES (?, ?, ?, 'to_do', ?, '', ?, ?, ?, '', ?, NULL, NULL, 'scadenta')
        ''', (t['id'], pid, t['titlu'], t['data_scadenta'], ordine, acum, t['descriere'], acum))
        noi += 1
    conn.commit()
    return noi, existente, sarite


def calculeaza(snapshot, perioada_pentru):
    """Pe un snapshot validat, cu `sursa.alerte == "server"`: alertele fiecarui proiect, marcajele si rezumatul (pe
    loc), plus lista taskurilor de creat. `perioada_pentru(proiect_id, azi)` da perioada (sau None).
    Intoarce [(proiect_id, task)]."""
    azi = _zi(snapshot['generat'])
    utilizator = (snapshot.get('sursa') or {}).get('utilizator') or ''
    taskuri = []
    for p in snapshot['proiecte']:
        alerte = alerte_proiect(p, azi, utilizator, perioada_pentru(p['proiect_id'], azi))
        p['alerte'] = alerte
        taskuri += [(p['proiect_id'], task_pentru(p, a, azi)) for a in alerte]
    return taskuri
