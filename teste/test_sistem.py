"""Pagina „System maintenance": snapshot-urile surselor, vederea combinata si deciziile.

Ce se pazeste, tacut daca se strica:
  - un corp care iese din contract (v1) da 400 cu calea campului si NU atinge snapshot-ul curent;
  - un snapshot cu `generat` mai vechi decat cel curent da 409; aceeasi cerere de doua ori lasa
    acelasi fisier; nu ramane niciun `.tmp`;
  - `GET /api/sistem`: itemii a doua surse, dedup pe id (ramane cel din snapshot-ul mai nou), ordinea
    (grup, restant descrescator, creat crescator), `vechime_ore` > 26 -> cel putin warn, `numar` fara
    deciziile in asteptare, fara surse -> liste goale;
  - o decizie se accepta doar pentru un item si o optiune pe care le-a pus sursa; ultima decizie pe
    acelasi id o inlocuieste pe cea neconsumata;
  - consumul: 404 la uid necunoscut, 409 la a doua oara, taierea la 500 de randuri (doar terminate:
    consumate sau anulate; cele in asteptare nu se taie);
  - contractul v1.1 (aditiv; rand vechi fara campurile noi ramane valid): `istoric` (ultimele 20
    terminate, cea mai recenta intai, `titlu`/`sursa` implicite pe randuri vechi), `preluat`
    (idempotent; 404/409 anulata/consumata), `anulare` (idempotenta; 409 preluata/consumata), o decizie
    noua peste una PRELUATA da 409 si nu scrie (peste una nepreluata o inlocuieste), `?sursa=` (lipsa
    = server, invalida 400), `stare` la consumat (ok|warn|fail, anulata 409), masinile asteptate
    (`never reported` / `report unreadable`), `amanare` (31 de zile, expirate taiate, maxim 200,
    item inexistent 409, `amanat_pana` in vedere);
  - tokenul de dispozitiv: citeste `GET /api/sistem`, trimite `POST /api/sistem/decizie`, anuleaza
    (`/api/sistem/decizie/<uid>/anulare`) si amana (`/api/sistem/amanare`), dar nu scrie surse, nu
    citeste coada de decizii, nu o preia si nu o consuma (prefixul `/api/sistem/decizii` nu prinde
    singularul `/api/sistem/decizie`).
Directorul datelor e unul temporar: un test nu scrie niciodata in `uploads/` din proiect.
"""

import json
import os
from datetime import datetime, timezone

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import sistem

ACUM = datetime(2026, 11, 17, 8, 12, 0, tzinfo=timezone.utc)

OPTIUNI = [{'id': 'aprob', 'label': 'Approve', 'stil': 'filled'},
           {'id': 'resping', 'label': 'Reject', 'stil': 'danger'}]


def item(id_='santinela:claims-audit', grup='review', **camp):
    base = {'id': id_, 'grup': grup, 'titlu': 'Titlu ' + id_, 'motiv': 'Motiv.', 'etichete': ['Vault'],
            'optiuni': []}
    base.update(camp)
    return base


def corp(sursa='pc-job', *itemi, generat='2026-11-17T08:00:03Z', **camp):
    c = {'v': 1, 'sursa': sursa, 'masina': 'ROPC427N', 'generat': generat,
         'sanatate': {'stare': 'ok', 'detaliu': 'ok · 08:00'},
         'itemi': list(itemi),
         'urmeaza': [{'titlu': 'Review de sistem', 'data': '2026-11-27'}],
         'automat': [{'ce': 'Nightly loop · server', 'stare': 'ok', 'detaliu': '02:30 · 2 închise'}]}
    c.update(camp)
    return c


class Sistem(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'sistem')
        self.patch(sistem, 'DIR_SISTEM', self.dir)
        self.patch(sistem, '_acum', lambda: ACUM)       # marti 17 nov. 2026, 08:12 UTC

    def pune(self, sursa, cuprins, token=FULL):
        return self.client.put('/api/sistem/sursa/' + sursa, json=cuprins,
                               headers=self.bearer(token) if token else {})

    def pune_ok(self, sursa, cuprins):
        r = self.pune(sursa, cuprins)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def citeste(self, token=FULL):
        r = self.client.get('/api/sistem', headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def decide(self, id_, optiune, token=FULL, **camp):
        return self.client.post('/api/sistem/decizie', json={'id': id_, 'optiune': optiune, **camp},
                                headers=self.bearer(token) if token else {})

    def masina(self, sursa):
        """Intrarea din `masini` a unei surse (celelalte doua asteptate apar si ele, ca `fail`)."""
        return next(m for m in self.citeste()['masini'] if m['sursa'] == sursa)

    def decizii(self, token=FULL, sursa=None):
        return self.client.get('/api/sistem/decizii', headers=self.bearer(token),
                               query_string={'sursa': sursa} if sursa is not None else None)

    def consuma(self, uid, rezultat='aprobat in ledger', token=FULL):
        return self.client.post('/api/sistem/decizii/%s/consumat' % uid, json={'rezultat': rezultat},
                                headers=self.bearer(token) if token else {})

    def preia(self, uid, token=FULL, corp=None):
        return self.client.post('/api/sistem/decizii/%s/preluat' % uid, headers=self.bearer(token),
                                **({'json': corp} if corp is not None else {}))

    def anuleaza(self, uid, token=FULL, corp=None):
        return self.client.post('/api/sistem/decizie/%s/anulare' % uid, headers=self.bearer(token),
                                **({'json': corp} if corp is not None else {}))

    def amana(self, id_, pana, token=FULL, **camp):
        return self.client.post('/api/sistem/amanare', json={'id': id_, 'pana': pana, **camp},
                                headers=self.bearer(token))

    def randuri(self):
        return [json.loads(l) for l in self.fisier('decizii.jsonl').decode('utf-8').splitlines()]

    def fisier(self, nume):
        with open(os.path.join(self.dir, nume), 'rb') as fh:
            return fh.read()

    def cu_cerere(self, id_='A-009'):
        """Un snapshot cu o cerere deschisa (cu optiuni), pus de `server`."""
        self.pune_ok('server', corp('server', item(id_, 'decide', optiuni=OPTIUNI)))

    # ----------------------------------------------------------------------- PUT valid

    def test_put_valid_scrie_si_raspunde(self):
        r = self.pune('pc-job', corp('pc-job', item(restant_zile=7, comanda='python x.py', creat='2026-11-13')))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json(), {'ok': True, 'itemi': 1})
        self.assertEqual(os.listdir(self.dir), ['pc-job.json'], 'niciun .tmp ramas')

    def test_diacriticele_se_pastreaza(self):
        self.pune_ok('pc-job', corp('pc-job', item(motiv='Ultimul audit acum 37 de zile (prag 30). Ștergere în așteptare.')))
        self.assertIn('Ștergere în așteptare', self.citeste()['itemi'][0]['motiv'])

    def test_repetarea_aceleiasi_cereri_lasa_acelasi_fisier(self):
        c = corp('pc-job', item())
        self.pune_ok('pc-job', c)
        prima = self.fisier('pc-job.json')
        self.pune_ok('pc-job', c)
        self.assertEqual(self.fisier('pc-job.json'), prima)
        self.assertEqual(os.listdir(self.dir), ['pc-job.json'])

    def test_snapshot_gol_de_itemi_e_valid(self):
        self.assertEqual(self.pune_ok('ionpc', corp('ionpc'))['itemi'], 0)

    # ----------------------------------------------------------------------- PUT respins

    def test_corp_gresit_da_400_cu_calea_si_nu_atinge_snapshotul(self):
        self.pune_ok('pc-job', corp('pc-job', item()))
        inainte = self.fisier('pc-job.json')

        def cu_item(**camp):
            return corp('pc-job', item(**camp))

        def fara(camp):
            c = corp('pc-job', item())
            del c[camp]
            return c

        def fara_item(camp):
            it = item()
            del it[camp]
            return corp('pc-job', it)

        cazuri = [
            (dict(corp('pc-job'), v=2), 'v'),
            (dict(corp('pc-job'), v=True), 'v'),
            (corp('alta-sursa'), 'sursa'),                                              # sursa din corp != cea din cale
            (dict(corp('pc-job'), extra=1), 'corpul.extra'),                            # camp necunoscut
            (fara('masina'), 'corpul.masina'),
            (dict(corp('pc-job'), masina=''), 'corpul.masina'),
            (dict(corp('pc-job'), masina='M' * 81), 'corpul.masina'),
            (dict(corp('pc-job'), generat='2026-11-17T08:00:03'), 'generat'),            # fara Z
            (dict(corp('pc-job'), generat='2026-11-17T08:00:03+00:00'), 'generat'),      # offset, nu Z
            (dict(corp('pc-job'), generat='2026-11-17T08:00:03.5Z'), 'generat'),         # fractiune
            (dict(corp('pc-job'), generat='2026-13-17T08:00:03Z'), 'generat'),           # luna 13
            (dict(corp('pc-job'), generat=None), 'generat'),
            (dict(corp('pc-job'), sanatate={'stare': 'bine', 'detaliu': ''}), 'sanatate.stare'),
            (dict(corp('pc-job'), sanatate={'stare': 'ok'}), 'sanatate.detaliu'),
            (dict(corp('pc-job'), sanatate={'stare': 'ok', 'detaliu': 'x' * 201}), 'sanatate.detaliu'),
            (dict(corp('pc-job'), sanatate='ok'), 'sanatate'),
            (dict(corp('pc-job'), itemi={}), 'corpul.itemi'),
            (fara('itemi'), 'corpul.itemi'),
            (cu_item(grup='urgent'), 'itemi[0].grup'),
            (cu_item(id=''), 'itemi[0].id'),
            (cu_item(id='x' * 81), 'itemi[0].id'),
            (cu_item(id=5), 'itemi[0].id'),
            (corp('pc-job', item('a'), item('a')), 'itemi[1].id: duplicat'),
            (cu_item(titlu=''), 'itemi[0].titlu'),
            (cu_item(titlu='t' * 201), 'itemi[0].titlu'),
            (cu_item(motiv='m' * 601), 'itemi[0].motiv'),
            (fara_item('motiv'), 'itemi[0].motiv'),
            (cu_item(etichete='Vault'), 'itemi[0].etichete'),
            (cu_item(etichete=['a'] * 6), 'itemi[0].etichete'),
            (cu_item(etichete=['a' * 41]), 'itemi[0].etichete[0]'),
            (cu_item(etichete=[3]), 'itemi[0].etichete[0]'),
            (cu_item(restant_zile=-1), 'itemi[0].restant_zile'),
            (cu_item(restant_zile=1.5), 'itemi[0].restant_zile'),
            (cu_item(restant_zile='7'), 'itemi[0].restant_zile'),
            (cu_item(restant_zile=True), 'itemi[0].restant_zile'),
            (cu_item(comanda='c' * 401), 'itemi[0].comanda'),
            (cu_item(creat='13.11.2026'), 'itemi[0].creat'),
            (cu_item(creat='2026-02-30'), 'itemi[0].creat'),
            (cu_item(nou='x'), 'itemi[0].nou'),                                          # camp necunoscut in item
            (fara_item('optiuni'), 'itemi[0].optiuni'),
            (cu_item(optiuni={}), 'itemi[0].optiuni'),
            (cu_item(optiuni=[{'id': 'Aprob', 'label': 'A', 'stil': 'filled'}]), 'itemi[0].optiuni[0].id'),
            (cu_item(optiuni=[{'id': 'a' * 21, 'label': 'A', 'stil': 'filled'}]), 'itemi[0].optiuni[0].id'),
            (cu_item(optiuni=[{'id': 'a', 'label': 'L' * 41, 'stil': 'filled'}]), 'itemi[0].optiuni[0].label'),
            (cu_item(optiuni=[{'id': 'a', 'label': '', 'stil': 'filled'}]), 'itemi[0].optiuni[0].label'),
            (cu_item(optiuni=[{'id': 'a', 'label': 'A', 'stil': 'rosu'}]), 'itemi[0].optiuni[0].stil'),
            (cu_item(optiuni=[{'id': 'a', 'label': 'A', 'stil': 'filled', 'cmd': 'rm'}]), 'itemi[0].optiuni[0].cmd'),
            (cu_item(optiuni=[{'id': 'a', 'label': 'A', 'stil': 'filled'},
                              {'id': 'a', 'label': 'B', 'stil': 'tinted'}]), 'optiuni[1].id: duplicat'),
            (dict(corp('pc-job'), urmeaza=[{'titlu': '', 'data': '2026-11-27'}]), 'urmeaza[0].titlu'),
            (dict(corp('pc-job'), urmeaza=[{'titlu': 'x', 'data': '27.11.2026'}]), 'urmeaza[0].data'),
            (dict(corp('pc-job'), urmeaza=[{'titlu': 'x'}]), 'urmeaza[0].data'),
            (dict(corp('pc-job'), automat=[{'ce': '', 'stare': 'ok', 'detaliu': ''}]), 'automat[0].ce'),
            (dict(corp('pc-job'), automat=[{'ce': 'x', 'stare': 'rau', 'detaliu': ''}]), 'automat[0].stare'),
            (dict(corp('pc-job'), automat=[{'ce': 'x', 'stare': 'ok', 'detaliu': 'd' * 201}]), 'automat[0].detaliu'),
            (dict(corp('pc-job'), itemi=[item('i%d' % n) for n in range(201)]), 'itemi: maximum 200'.replace('itemi', 'corpul.itemi')),
            (dict(corp('pc-job'), urmeaza=[{'titlu': 'x', 'data': '2026-11-27'}] * 51), 'corpul.urmeaza'),
            (dict(corp('pc-job'), automat=[{'ce': 'x', 'stare': 'ok', 'detaliu': ''}] * 51), 'corpul.automat'),
            ([], 'corpul'),
        ]
        for corpul, in_mesaj in cazuri:
            with self.subTest(in_mesaj=in_mesaj):
                r = self.pune('pc-job', corpul)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(in_mesaj, r.get_json()['error'])
        self.assertEqual(self.fisier('pc-job.json'), inainte, 'niciun corp respins nu atinge snapshot-ul')
        self.assertEqual(os.listdir(self.dir), ['pc-job.json'])

    def test_200_de_itemi_trec(self):
        self.pune_ok('pc-job', corp('pc-job', *[item('i%d' % n) for n in range(200)]))

    def test_json_invalid_sau_gol_da_400(self):
        h = self.bearer(FULL)
        for brut in (b'', b'{nu e json', b'\xff\xfe'):
            r = self.client.put('/api/sistem/sursa/pc-job', data=brut, headers=dict(h, **{'Content-Type': 'application/json'}))
            self.assertEqual(r.status_code, 400, brut)

    def test_corp_peste_1_mb_da_413(self):
        mare = corp('pc-job', item(), masina='x') | {'umplutura': 'x' * (sistem.MAX_CORP + 1)}
        r = self.pune('pc-job', mare)
        self.assertEqual(r.status_code, 413)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'pc-job.json')))

    def test_numele_sursei_gresit_da_400(self):
        for nume in ('A', 'x', '-job', 'Pc-Job', 'a' * 21, 'pc_job', 'pc.job', 'pc%20job'):
            with self.subTest(nume=nume):
                r = self.pune(nume, corp(nume))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))

    def test_traversare_de_cale_nu_scrie_nimic(self):
        r = self.client.put('/api/sistem/sursa/..%2Fx', json=corp('..%2Fx'), headers=self.bearer(FULL))
        self.assertIn(r.status_code, (400, 404))
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))

    # ----------------------------------------------------------------------- 409 la snapshot vechi

    def test_snapshot_mai_vechi_da_409_si_nu_se_scrie(self):
        self.pune_ok('pc-job', corp('pc-job', item('nou'), generat='2026-11-17T08:00:03Z'))
        inainte = self.fisier('pc-job.json')
        r = self.pune('pc-job', corp('pc-job', item('vechi'), generat='2026-11-17T08:00:02Z'))
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertIn('2026-11-17T08:00:03Z', r.get_json()['error'])
        self.assertEqual(self.fisier('pc-job.json'), inainte)

    def test_snapshot_mai_nou_il_inlocuieste(self):
        self.pune_ok('pc-job', corp('pc-job', item('vechi'), generat='2026-11-17T08:00:03Z'))
        self.pune_ok('pc-job', corp('pc-job', item('nou'), generat='2026-11-17T08:05:00Z'))
        self.assertEqual([i['id'] for i in self.citeste()['itemi']], ['nou'])

    def test_aceeasi_data_generat_se_accepta(self):
        self.pune_ok('pc-job', corp('pc-job', item('a')))
        self.pune_ok('pc-job', corp('pc-job', item('b')))
        self.assertEqual([i['id'] for i in self.citeste()['itemi']], ['b'])

    def test_snapshot_stricat_pe_disc_nu_blocheaza_un_PUT_nou(self):
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, 'pc-job.json'), 'w') as fh:
            fh.write('{nu e json')
        self.pune_ok('pc-job', corp('pc-job', item()))

    # ----------------------------------------------------------------------- GET combinat

    def test_fara_surse_vederea_e_goala(self):
        j = self.citeste()
        # nicio sursa n-a raportat: cele trei masini asteptate apar in `fail`, restul listelor e gol
        self.assertEqual(j, {'generat': '2026-11-17T08:12:00Z', 'numar': 0, 'itemi': [], 'urmeaza': [],
                             'automat': [], 'istoric': [], 'backlog': None,
                             'masini': [{'sursa': s, 'masina': '', 'ultima': None, 'vechime_ore': None,
                                         'stare': 'fail', 'detaliu': 'never reported', 'joburi': []}
                                        for s in ('ionpc', 'pc-job', 'server')]})

    def test_fisier_stricat_sau_in_plus_nu_strica_GET(self):
        self.pune_ok('pc-job', corp('pc-job', item()))
        with open(os.path.join(self.dir, 'server.json'), 'w') as fh:
            fh.write('{nu e json')
        with open(os.path.join(self.dir, 'ionpc.json'), 'w') as fh:
            fh.write('{"v": 1}')                                  # JSON valid, dar nu respecta contractul
        with open(os.path.join(self.dir, 'Gresit.json'), 'w') as fh:
            fh.write('{}')
        j = self.citeste()
        # pc-job e valid; server (JSON stricat) si ionpc (nu respecta contractul) sunt asteptate dar ilizibile;
        # Gresit.json nu e nume de sursa si se ignora
        self.assertEqual([(m['sursa'], m['stare'], m['detaliu']) for m in j['masini']],
                         [('ionpc', 'fail', 'report unreadable'), ('pc-job', 'ok', 'ok · 08:00'),
                          ('server', 'fail', 'report unreadable')])

    def test_doua_surse_masini_itemi_urmeaza_si_automat(self):
        self.pune_ok('server', corp('server', item('S1', 'do'), masina='ion-ursu-thinkpad-t450',
                                    generat='2026-11-17T08:00:00Z',
                                    urmeaza=[{'titlu': 'Backup test', 'data': '2026-11-20'},
                                             {'titlu': 'Review de sistem', 'data': '2026-11-27'}],
                                    automat=[{'ce': 'Nightly loop', 'stare': 'ok', 'detaliu': '02:30'}]))
        self.pune_ok('pc-job', corp('pc-job', item('P1', 'review'), generat='2026-11-17T08:05:00Z',
                                    urmeaza=[{'titlu': 'Review de sistem', 'data': '2026-11-27'},
                                             {'titlu': 'Audit', 'data': '2026-11-18'}],
                                    automat=[{'ce': 'Sweep mail', 'stare': 'warn', 'detaliu': 'intarziat'}]))
        j = self.citeste()
        self.assertEqual([(m['sursa'], m['masina']) for m in j['masini']],
                         [('ionpc', ''), ('pc-job', 'ROPC427N'), ('server', 'ion-ursu-thinkpad-t450')])
        _, pc, srv = j['masini']
        self.assertEqual((pc['ultima'], pc['vechime_ore'], pc['stare'], pc['detaliu']),
                         ('2026-11-17T08:05:00Z', 0.1, 'ok', 'ok · 08:00'))
        self.assertEqual(srv['vechime_ore'], 0.2)
        self.assertEqual([(i['id'], i['sursa'], i['decizie']) for i in j['itemi']],
                         [('P1', 'pc-job', None), ('S1', 'server', None)])
        # urmeaza: sortat dupa data, deduplicat dupa titlu
        self.assertEqual([(u['data'], u['titlu']) for u in j['urmeaza']],
                         [('2026-11-18', 'Audit'), ('2026-11-20', 'Backup test'), ('2026-11-27', 'Review de sistem')])
        self.assertEqual([(a['ce'], a['sursa']) for a in j['automat']],
                         [('Sweep mail', 'pc-job'), ('Nightly loop', 'server')])
        self.assertEqual(j['numar'], 2)

    def test_acelasi_id_in_doua_surse_ramane_cel_din_snapshotul_mai_nou(self):
        self.pune_ok('server', corp('server', item('X', 'review', titlu='din server'), generat='2026-11-17T07:00:00Z'))
        self.pune_ok('pc-job', corp('pc-job', item('X', 'review', titlu='din pc-job'), generat='2026-11-17T08:00:00Z'))
        itemi = self.citeste()['itemi']
        self.assertEqual([(i['titlu'], i['sursa']) for i in itemi], [('din pc-job', 'pc-job')])
        # invers: pe disc, serverul e acum cel mai nou
        self.pune_ok('server', corp('server', item('X', 'review', titlu='din server, nou'), generat='2026-11-17T08:10:00Z'))
        itemi = self.citeste()['itemi']
        self.assertEqual([(i['titlu'], i['sursa']) for i in itemi], [('din server, nou', 'server')])

    def test_ordinea_itemilor(self):
        self.pune_ok('server', corp('server',
                                    item('do-1', 'do', restant_zile=99),
                                    item('rev-creat-nou', 'review', restant_zile=3, creat='2026-11-10'),
                                    item('rev-creat-vechi', 'review', restant_zile=3, creat='2026-11-01'),
                                    item('rev-fara-restant', 'review'),
                                    item('rev-restant-mare', 'review', restant_zile=40),
                                    item('rev-restant-zero', 'review', restant_zile=0),
                                    item('dec-1', 'decide', restant_zile=1, optiuni=OPTIUNI)))
        self.assertEqual([i['id'] for i in self.citeste()['itemi']],
                         ['dec-1', 'rev-restant-mare', 'rev-creat-vechi', 'rev-creat-nou',
                          'rev-restant-zero', 'rev-fara-restant', 'do-1'])

    def test_itemul_pastreaza_campurile_si_primeste_sursa_si_decizie(self):
        self.pune_ok('pc-job', corp('pc-job', item(restant_zile=7, comanda='python x.py', creat='2026-11-13',
                                                   etichete=['A-003', 'Vault'])))
        it = self.citeste()['itemi'][0]
        self.assertEqual((it['restant_zile'], it['comanda'], it['creat'], it['etichete'], it['optiuni']),
                         (7, 'python x.py', '2026-11-13', ['A-003', 'Vault'], []))
        self.assertEqual((it['sursa'], it['decizie']), ('pc-job', None))

    def test_vechime_peste_26_ore_da_cel_putin_warn(self):
        # ACUM = 2026-11-17 08:12. 26 h exact nu depaseste pragul.
        self.pune_ok('ionpc', corp('ionpc', generat='2026-11-16T06:12:00Z'))
        self.pune_ok('pc-job', corp('pc-job', generat='2026-11-16T05:12:00Z'))        # 27 h
        self.pune_ok('server', corp('server', generat='2026-11-14T08:12:00Z',          # 72 h = 3 zile
                                    sanatate={'stare': 'fail', 'detaliu': 'picat'}))
        m = {x['sursa']: x for x in self.citeste()['masini']}
        self.assertEqual((m['ionpc']['vechime_ore'], m['ionpc']['stare'], m['ionpc']['detaliu']),
                         (26.0, 'ok', 'ok · 08:00'))
        self.assertEqual((m['pc-job']['vechime_ore'], m['pc-job']['stare'], m['pc-job']['detaliu']),
                         (27.0, 'warn', 'last seen 27 h'))
        self.assertEqual((m['server']['vechime_ore'], m['server']['stare'], m['server']['detaliu']),
                         (72.0, 'fail', 'last seen 3 d'), 'fail nu coboara la warn')

    def test_vechime_exact_48_ore_ramane_in_ore(self):
        self.pune_ok('pc-job', corp('pc-job', generat='2026-11-15T08:12:00Z'))
        self.assertEqual(self.masina('pc-job')['detaliu'], 'last seen 48 h')

    def test_warn_din_sanatate_ramane_warn_cand_snapshotul_e_proaspat(self):
        self.pune_ok('pc-job', corp('pc-job', sanatate={'stare': 'warn', 'detaliu': 'disc plin'}))
        m = self.masina('pc-job')
        self.assertEqual((m['stare'], m['detaliu']), ('warn', 'disc plin'))

    def test_generat_din_viitor_nu_da_vechime_negativa(self):
        self.pune_ok('pc-job', corp('pc-job', generat='2026-11-17T09:00:00Z'))
        self.assertEqual(self.masina('pc-job')['vechime_ore'], 0.0)

    def test_numar_nu_include_itemii_cu_decizie_in_asteptare(self):
        self.pune_ok('server', corp('server', item('A-009', 'decide', optiuni=OPTIUNI),
                                    item('A-010', 'decide', optiuni=OPTIUNI), item('s:x', 'do')))
        self.assertEqual(self.citeste()['numar'], 3)
        uid = self.decide('A-009', 'aprob', text='ok').get_json()['uid']
        j = self.citeste()
        self.assertEqual(j['numar'], 2)
        self.assertEqual(len(j['itemi']), 3, 'itemul ramane in lista pana il scoate snapshot-ul')
        a009 = next(i for i in j['itemi'] if i['id'] == 'A-009')
        self.assertEqual(a009['decizie'], {'uid': uid, 'optiune': 'aprob', 'label': 'Approve',
                                           'ts': '2026-11-17T08:12:00Z', 'preluat': None})
        # dupa consum, decizia nu mai e „in asteptare": itemul se numara din nou
        self.assertEqual(self.consuma(uid).status_code, 200)
        j = self.citeste()
        self.assertEqual(j['numar'], 3)
        self.assertIsNone(next(i for i in j['itemi'] if i['id'] == 'A-009')['decizie'])

    # ----------------------------------------------------------------------- decizia

    def test_decizie_valida(self):
        self.cu_cerere()
        r = self.decide('A-009', 'aprob', text='de acord')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        uid = r.get_json()['uid']
        self.assertRegex(uid, r'^[0-9a-f]{12}$')
        self.assertEqual(r.get_json(), {'ok': True, 'uid': uid})
        rand = json.loads(self.fisier('decizii.jsonl').decode('utf-8'))
        self.assertEqual(rand, {'uid': uid, 'ts': '2026-11-17T08:12:00Z', 'id': 'A-009', 'optiune': 'aprob',
                                'label': 'Approve', 'text': 'de acord', 'de_la': 'masina',
                                'consumat': None, 'rezultat': None,
                                'titlu': 'Titlu A-009', 'sursa': 'server', 'preluat': None, 'anulat': None,
                                'stare': None})

    def test_decizie_fara_text_pastreaza_text_gol(self):
        self.cu_cerere()
        self.assertEqual(self.decide('A-009', 'resping').status_code, 201)
        rand = json.loads(self.fisier('decizii.jsonl').decode('utf-8'))
        self.assertEqual((rand['text'], rand['label']), ('', 'Reject'))

    def test_decizie_cu_optiune_inexistenta_409(self):
        self.cu_cerere()
        r = self.decide('A-009', 'sterge-tot')
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertIn('nu mai există', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'decizii.jsonl')))

    def test_decizie_pentru_item_inexistent_409(self):
        self.cu_cerere()
        self.assertEqual(self.decide('A-999', 'aprob').status_code, 409)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'decizii.jsonl')))

    def test_decizie_pentru_item_fara_optiuni_409(self):
        self.pune_ok('server', corp('server', item('santinela:ci', 'review')))
        self.assertEqual(self.decide('santinela:ci', 'aprob').status_code, 409)

    def test_decizie_fara_nicio_sursa_409(self):
        self.assertEqual(self.decide('A-009', 'aprob').status_code, 409)

    def test_optiunea_se_ia_din_snapshotul_mai_nou(self):
        self.pune_ok('server', corp('server', item('A-009', 'decide', optiuni=OPTIUNI), generat='2026-11-17T07:00:00Z'))
        self.pune_ok('pc-job', corp('pc-job', item('A-009', 'decide', optiuni=[OPTIUNI[1]]), generat='2026-11-17T08:00:00Z'))
        self.assertEqual(self.decide('A-009', 'aprob').status_code, 409, 'optiunea a disparut din snapshot-ul mai nou')
        self.assertEqual(self.decide('A-009', 'resping').status_code, 201)

    def test_decizie_cu_corp_gresit_400(self):
        self.cu_cerere()
        cazuri = [
            ({}, 'corpul.id'),
            ({'id': 'A-009'}, 'corpul.optiune'),
            ({'id': '', 'optiune': 'aprob'}, 'corpul.id'),
            ({'id': 'x' * 81, 'optiune': 'aprob'}, 'corpul.id'),
            ({'id': 5, 'optiune': 'aprob'}, 'corpul.id'),
            ({'id': 'A-009', 'optiune': ''}, 'corpul.optiune'),
            ({'id': 'A-009', 'optiune': 'APROB'}, 'corpul.optiune'),
            ({'id': 'A-009', 'optiune': 'a' * 21}, 'corpul.optiune'),
            ({'id': 'A-009', 'optiune': 'aprob', 'text': 't' * 501}, 'corpul.text'),
            ({'id': 'A-009', 'optiune': 'aprob', 'text': 5}, 'corpul.text'),
            ({'id': 'A-009', 'optiune': 'aprob', 'comanda': 'rm -rf /'}, 'corpul.comanda'),    # clientul nu trimite comenzi
            ([], 'corpul'),
        ]
        for corpul, in_mesaj in cazuri:
            with self.subTest(corpul=corpul):
                r = self.client.post('/api/sistem/decizie', json=corpul, headers=self.bearer(FULL))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(in_mesaj, r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'decizii.jsonl')))

    def test_decizie_text_de_500_de_caractere_trece(self):
        self.cu_cerere()
        self.assertEqual(self.decide('A-009', 'aprob', text='t' * 500).status_code, 201)

    def test_decizie_pe_acelasi_id_o_inlocuieste_pe_cea_neconsumata(self):
        self.cu_cerere()
        u1 = self.decide('A-009', 'aprob').get_json()['uid']
        u2 = self.decide('A-009', 'resping', text='m-am razgandit').get_json()['uid']
        self.assertNotEqual(u1, u2)
        randuri = [json.loads(l) for l in self.fisier('decizii.jsonl').decode('utf-8').splitlines()]
        self.assertEqual([(r['uid'], r['optiune']) for r in randuri], [(u2, 'resping')])
        self.assertEqual([d['uid'] for d in self.decizii().get_json()['decizii']], [u2])
        self.assertEqual(self.citeste()['itemi'][0]['decizie']['optiune'], 'resping')

    def test_decizia_consumata_nu_se_inlocuieste_ci_se_adauga_alta(self):
        self.cu_cerere()
        u1 = self.decide('A-009', 'aprob').get_json()['uid']
        self.consuma(u1)
        u2 = self.decide('A-009', 'resping').get_json()['uid']
        randuri = [json.loads(l) for l in self.fisier('decizii.jsonl').decode('utf-8').splitlines()]
        self.assertEqual([(r['uid'], r['consumat'] is not None) for r in randuri], [(u1, True), (u2, False)])

    def test_decizii_pe_id_diferite_coexista(self):
        self.pune_ok('server', corp('server', item('A-009', 'decide', optiuni=OPTIUNI),
                                    item('A-010', 'decide', optiuni=OPTIUNI)))
        self.decide('A-009', 'aprob')
        self.decide('A-010', 'resping')
        self.assertEqual([d['id'] for d in self.decizii().get_json()['decizii']], ['A-009', 'A-010'])

    def test_de_la_dupa_cine_a_trimis(self):
        self.cu_cerere()
        self.decide('A-009', 'aprob', token=DEVICE)
        self.assertEqual(json.loads(self.fisier('decizii.jsonl').decode('utf-8'))['de_la'], 'dispozitiv')
        self.client.post('/login', json={'pin': '135790'})
        r = self.client.post('/api/sistem/decizie', json={'id': 'A-009', 'optiune': 'aprob'},
                             headers={'X-CSRF-Token': self.client.get_cookie('csrf_token').value})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(json.loads(self.fisier('decizii.jsonl').decode('utf-8'))['de_la'], 'sesiune')

    # ----------------------------------------------------------------------- GET decizii si consumat

    def test_get_decizii_doar_neconsumate_cele_mai_vechi_intai(self):
        self.pune_ok('server', corp('server', *[item('A-0%d' % n, 'decide', optiuni=OPTIUNI) for n in range(3)]))
        u = []
        for n, ts in enumerate(('2026-11-17T08:12:05Z', '2026-11-17T08:12:01Z', '2026-11-17T08:12:03Z')):
            self.patch(sistem, '_acum', lambda ts=ts: datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc))
            u.append(self.decide('A-0%d' % n, 'aprob').get_json()['uid'])
        self.consuma(u[2])
        r = self.decizii()
        self.assertEqual(r.status_code, 200)
        self.assertEqual([d['uid'] for d in r.get_json()['decizii']], [u[1], u[0]])

    def test_get_decizii_fara_fisier_da_lista_goala(self):
        r = self.decizii()
        self.assertEqual((r.status_code, r.get_json()), (200, {'decizii': []}))

    def test_consumat_pune_momentul_si_rezultatul(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        r = self.consuma(uid, 'aprobat în ledger')
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'uid': uid}))
        rand = json.loads(self.fisier('decizii.jsonl').decode('utf-8'))
        self.assertEqual((rand['consumat'], rand['rezultat']), ('2026-11-17T08:12:00Z', 'aprobat în ledger'))
        self.assertEqual(self.decizii().get_json(), {'decizii': []})
        self.assertEqual(os.listdir(self.dir).count('decizii.jsonl'), 1)
        self.assertFalse([n for n in os.listdir(self.dir) if n.endswith('.tmp')])

    def test_consumat_uid_necunoscut_404(self):
        self.cu_cerere()
        self.decide('A-009', 'aprob')
        for uid in ('000000000000', 'nu-e-uid', 'A' * 12, '..%2F..'):
            with self.subTest(uid=uid):
                self.assertEqual(self.consuma(uid).status_code, 404)

    def test_consumat_a_doua_oara_409_si_nu_rescrie_rezultatul(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.consuma(uid, 'primul')
        r = self.consuma(uid, 'al doilea')
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertEqual(json.loads(self.fisier('decizii.jsonl').decode('utf-8'))['rezultat'], 'primul')

    def test_consumat_cu_corp_gresit_400(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        for corpul, in_mesaj in (({}, 'corpul.rezultat'), ({'rezultat': ''}, 'corpul.rezultat'),
                                 ({'rezultat': 'r' * 301}, 'corpul.rezultat'), ({'rezultat': 3}, 'corpul.rezultat'),
                                 ({'rezultat': 'ok', 'altceva': 1}, 'corpul.altceva')):
            with self.subTest(corpul=corpul):
                r = self.client.post('/api/sistem/decizii/%s/consumat' % uid, json=corpul, headers=self.bearer(FULL))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(in_mesaj, r.get_json()['error'])
        self.assertEqual(len(self.decizii().get_json()['decizii']), 1, 'decizia a ramas neconsumata')
        self.assertEqual(self.consuma(uid, 'r' * 300).status_code, 200)

    def test_fisierul_pastreaza_cel_mult_500_de_randuri_taind_consumatele_vechi(self):
        self.cu_cerere()
        os.makedirs(self.dir, exist_ok=True)
        # 500 de randuri deja consumate, apoi o decizie noua: cea mai veche consumata iese.
        with open(os.path.join(self.dir, 'decizii.jsonl'), 'w', encoding='utf-8') as fh:
            for n in range(500):
                fh.write(json.dumps({'uid': '%012x' % n, 'ts': '2026-11-01T00:00:00Z', 'id': 'vechi-%d' % n,
                                     'optiune': 'aprob', 'label': 'Approve', 'text': '', 'de_la': 'masina',
                                     'consumat': '2026-11-01T00:00:01Z', 'rezultat': 'ok'}) + '\n')
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        randuri = [json.loads(l) for l in self.fisier('decizii.jsonl').decode('utf-8').splitlines()]
        self.assertEqual(len(randuri), 500)
        self.assertEqual(randuri[0]['uid'], '%012x' % 1, 'cea mai veche consumata a iesit')
        self.assertEqual(randuri[-1]['uid'], uid)
        # un rand in asteptare nu se taie niciodata, nici cand fisierul e plin de ele
        self.assertEqual([d['uid'] for d in self.decizii().get_json()['decizii']], [uid])

    def test_randuri_in_asteptare_nu_se_taie(self):
        self.cu_cerere()
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'decizii.jsonl'), 'w', encoding='utf-8') as fh:
            for n in range(500):
                fh.write(json.dumps({'uid': '%012x' % n, 'ts': '2026-11-01T00:00:00Z', 'id': 'alt-%d' % n,
                                     'optiune': 'aprob', 'label': 'Approve', 'text': '', 'de_la': 'masina',
                                     'consumat': None, 'rezultat': None}) + '\n')
        self.decide('A-009', 'aprob')
        self.assertEqual(len(self.decizii().get_json()['decizii']), 501)

    def test_rand_stricat_in_decizii_se_sare(self):
        self.cu_cerere()
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'decizii.jsonl'), 'w', encoding='utf-8') as fh:
            fh.write('{nu e json\n[1,2]\n')
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.assertEqual([d['uid'] for d in self.decizii().get_json()['decizii']], [uid])

    # ----------------------------------------------------------------------- v1.1: ciclul de viata al deciziei

    def la(self, ts):
        """Ceasul serverului la `ts` (ISO Z)."""
        moment = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        self.patch(sistem, '_acum', lambda: moment)

    def scrie_randuri(self, randuri):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'decizii.jsonl'), 'w', encoding='utf-8') as fh:
            for r in randuri:
                fh.write(json.dumps(r) + '\n')

    @staticmethod
    def rand_vechi(n, **camp):
        """Un rand ca cele scrise inainte de v1.1: fara titlu, sursa, preluat, anulat, stare."""
        r = {'uid': '%012x' % n, 'ts': '2026-11-01T00:00:00Z', 'id': 'vechi-%d' % n, 'optiune': 'aprob',
             'label': 'Approve', 'text': '', 'de_la': 'masina', 'consumat': None, 'rezultat': None}
        r.update(camp)
        return r

    def test_randul_nou_tine_titlul_si_sursa_din_vedere(self):
        self.pune_ok('pc-job', corp('pc-job', item('P-1', 'decide', titlu='Aproba P-1', optiuni=OPTIUNI)))
        self.decide('P-1', 'aprob')
        rand = self.randuri()[0]
        self.assertEqual((rand['titlu'], rand['sursa'], rand['preluat'], rand['anulat'], rand['stare']),
                         ('Aproba P-1', 'pc-job', None, None, None))

    # --- istoric

    def test_istoric_gol_fara_decizii_terminate_si_fara_cele_in_asteptare(self):
        self.cu_cerere()
        self.assertEqual(self.citeste()['istoric'], [])
        self.decide('A-009', 'aprob')
        self.assertEqual(self.citeste()['istoric'], [], 'o decizie in asteptare nu e in istoric')

    def test_istoric_ultimele_20_cea_mai_recenta_intai_dupa_consumat_sau_anulat(self):
        # 24 consumate la minutele 1..24, una anulata la minutul 30 (cea mai recenta), una in asteptare
        randuri = [self.rand_vechi(n, consumat='2026-11-10T00:%02d:00Z' % n, rezultat='r%d' % n)
                   for n in range(1, 25)]
        randuri.append(self.rand_vechi(90, ts='2026-11-02T00:00:00Z', anulat='2026-11-10T00:30:00Z'))
        randuri.append(self.rand_vechi(91))
        self.scrie_randuri(randuri)
        istoric = self.citeste()['istoric']
        self.assertEqual(len(istoric), 20)
        self.assertEqual(istoric[0]['uid'], '%012x' % 90)
        self.assertEqual([r['uid'] for r in istoric[1:]], ['%012x' % n for n in range(24, 5, -1)])
        self.assertNotIn('%012x' % 91, [r['uid'] for r in istoric])

    def test_istoric_are_campurile_din_contract(self):
        self.pune_ok('pc-job', corp('pc-job', item('P-1', 'decide', titlu='Aproba P-1', optiuni=OPTIUNI)))
        uid = self.decide('P-1', 'aprob', text='de acord').get_json()['uid']
        self.la('2026-11-17T08:20:00Z')
        self.preia(uid)
        r = self.client.post('/api/sistem/decizii/%s/consumat' % uid, json={'rezultat': 'aplicat', 'stare': 'warn'},
                             headers=self.bearer(FULL))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.citeste()['istoric'], [{
            'uid': uid, 'id': 'P-1', 'titlu': 'Aproba P-1', 'optiune': 'aprob', 'label': 'Approve',
            'text': 'de acord', 'ts': '2026-11-17T08:12:00Z', 'sursa': 'pc-job', 'de_la': 'masina',
            'rezultat': 'aplicat', 'stare': 'warn', 'consumat': '2026-11-17T08:20:00Z', 'anulat': None}])

    def test_istoric_o_decizie_anulata_are_rezultat_null(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.la('2026-11-17T08:30:00Z')
        self.anuleaza(uid)
        (r,) = self.citeste()['istoric']
        self.assertEqual((r['uid'], r['rezultat'], r['consumat'], r['anulat'], r['stare']),
                         (uid, None, None, '2026-11-17T08:30:00Z', None))

    def test_istoric_randuri_vechi_fara_campurile_noi(self):
        self.scrie_randuri([self.rand_vechi(1, consumat='2026-11-10T00:00:01Z', rezultat='ok')])
        (r,) = self.citeste()['istoric']
        self.assertEqual((r['titlu'], r['sursa'], r['stare'], r['anulat']), ('vechi-1', 'server', None, None))
        self.assertEqual((r['rezultat'], r['consumat']), ('ok', '2026-11-10T00:00:01Z'))

    # --- preluat

    def test_preluat_pune_momentul_si_se_vede_in_vedere_si_in_coada(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.la('2026-11-17T08:15:00Z')
        r = self.preia(uid)
        self.assertEqual((r.status_code, r.get_json()),
                         (200, {'ok': True, 'uid': uid, 'preluat': '2026-11-17T08:15:00Z'}))
        self.assertEqual(self.randuri()[0]['preluat'], '2026-11-17T08:15:00Z')
        self.assertEqual(self.citeste()['itemi'][0]['decizie']['preluat'], '2026-11-17T08:15:00Z')
        (d,) = self.decizii().get_json()['decizii']
        self.assertEqual((d['uid'], d['preluat']), (uid, '2026-11-17T08:15:00Z'))

    def test_preluat_e_idempotent_si_pastreaza_momentul_vechi(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.la('2026-11-17T08:15:00Z')
        self.preia(uid)
        inainte = self.fisier('decizii.jsonl')
        self.la('2026-11-17T09:00:00Z')
        r = self.preia(uid, corp={})
        self.assertEqual((r.status_code, r.get_json()['preluat']), (200, '2026-11-17T08:15:00Z'))
        self.assertEqual(self.fisier('decizii.jsonl'), inainte, 'o reincercare nu rescrie nimic')

    def test_preluat_uid_necunoscut_404(self):
        self.cu_cerere()
        self.decide('A-009', 'aprob')
        for uid in ('000000000000', 'nu-e-uid', 'A' * 12, '..%2F..'):
            with self.subTest(uid=uid):
                self.assertEqual(self.preia(uid).status_code, 404)

    def test_preluat_pe_anulata_sau_consumata_409(self):
        self.pune_ok('server', corp('server', item('A-009', 'decide', optiuni=OPTIUNI),
                                    item('A-010', 'decide', optiuni=OPTIUNI)))
        anulata = self.decide('A-009', 'aprob').get_json()['uid']
        consumata = self.decide('A-010', 'aprob').get_json()['uid']
        self.anuleaza(anulata)
        self.consuma(consumata)
        r = self.preia(anulata)
        self.assertEqual((r.status_code, r.get_json()), (409, {'error': 'decizia a fost anulata'}))
        r = self.preia(consumata)
        self.assertEqual((r.status_code, r.get_json()), (409, {'error': 'decizia e deja consumata'}))
        self.assertTrue(all(r['preluat'] is None for r in self.randuri()), 'niciuna nu a fost preluata')

    def test_preluat_corp_cu_camp_in_plus_400(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        r = self.preia(uid, corp={'altceva': 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.altceva', r.get_json()['error'])
        self.assertEqual(self.preia(uid, corp=[]).status_code, 400)
        self.assertIsNone(self.randuri()[0]['preluat'])

    def test_consumat_fara_preluat_merge_ca_inainte(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.assertEqual(self.consuma(uid).status_code, 200)
        self.assertIsNone(self.randuri()[0]['preluat'])

    # --- decizie peste una preluata

    def test_decizie_peste_una_preluata_409_si_nu_scrie(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.preia(uid)
        inainte = self.fisier('decizii.jsonl')
        r = self.decide('A-009', 'resping')
        self.assertEqual((r.status_code, r.get_json()), (409, {'error': 'decizia anterioara se aplica deja'}))
        self.assertEqual(self.fisier('decizii.jsonl'), inainte)
        self.assertFalse([n for n in os.listdir(self.dir) if n.endswith('.tmp')])

    def test_decizie_peste_una_nepreluata_o_inlocuieste_ca_inainte(self):
        self.cu_cerere()
        u1 = self.decide('A-009', 'aprob').get_json()['uid']
        r = self.decide('A-009', 'resping')
        self.assertEqual(r.status_code, 201)
        self.assertEqual([(x['uid'], x['optiune']) for x in self.randuri()], [(r.get_json()['uid'], 'resping')])
        self.assertNotEqual(u1, r.get_json()['uid'])

    def test_decizie_noua_dupa_una_anulata_sau_consumata_se_adauga(self):
        self.cu_cerere()
        u1 = self.decide('A-009', 'aprob').get_json()['uid']
        self.anuleaza(u1)
        u2 = self.decide('A-009', 'resping').get_json()['uid']
        self.preia(u2)
        self.consuma(u2)
        u3 = self.decide('A-009', 'aprob').get_json()['uid']
        self.assertEqual([(r['uid'], r['anulat'] is not None, r['consumat'] is not None) for r in self.randuri()],
                         [(u1, True, False), (u2, False, True), (u3, False, False)])

    # --- anulare

    def test_anulare_pune_momentul_si_decizia_iese_din_asteptare(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.assertEqual(self.citeste()['numar'], 0)
        self.la('2026-11-17T08:40:00Z')
        r = self.anuleaza(uid)
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'uid': uid}))
        self.assertEqual(self.randuri()[0]['anulat'], '2026-11-17T08:40:00Z')
        j = self.citeste()
        self.assertIsNone(j['itemi'][0]['decizie'])
        self.assertEqual(j['numar'], 1, 'itemul se numara din nou')
        self.assertEqual(self.decizii().get_json(), {'decizii': []})

    def test_anulare_e_idempotenta_si_nu_muta_momentul(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.la('2026-11-17T08:40:00Z')
        self.anuleaza(uid)
        inainte = self.fisier('decizii.jsonl')
        self.la('2026-11-17T09:00:00Z')
        r = self.anuleaza(uid, corp={})
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'uid': uid}))
        self.assertEqual(self.fisier('decizii.jsonl'), inainte)

    def test_anulare_pe_preluata_409_si_nu_scrie(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.preia(uid)
        inainte = self.fisier('decizii.jsonl')
        r = self.anuleaza(uid)
        self.assertEqual((r.status_code, r.get_json()), (409, {'error': 'se aplica deja'}))
        self.assertEqual(self.fisier('decizii.jsonl'), inainte)

    def test_anulare_pe_consumata_409(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.consuma(uid)
        r = self.anuleaza(uid)
        self.assertEqual((r.status_code, r.get_json()), (409, {'error': 'decizia e deja consumata'}))
        self.assertIsNone(self.randuri()[0]['anulat'])

    def test_anulare_uid_necunoscut_404(self):
        self.cu_cerere()
        self.decide('A-009', 'aprob')
        for uid in ('000000000000', 'nu-e-uid', 'A' * 12, '..%2F..'):
            with self.subTest(uid=uid):
                self.assertEqual(self.anuleaza(uid).status_code, 404)

    def test_anulare_corp_cu_camp_in_plus_400(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        r = self.anuleaza(uid, corp={'motiv': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.motiv', r.get_json()['error'])
        self.assertIsNone(self.randuri()[0]['anulat'])

    def test_consumat_pe_anulata_409(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.anuleaza(uid)
        r = self.consuma(uid)
        self.assertEqual((r.status_code, r.get_json()), (409, {'error': 'decizia a fost anulata'}))
        self.assertIsNone(self.randuri()[0]['consumat'])

    # --- ?sursa

    def test_decizii_filtrate_dupa_sursa_lipsa_inseamna_server(self):
        self.pune_ok('server', corp('server', item('A-009', 'decide', optiuni=OPTIUNI)))
        self.pune_ok('pc-job', corp('pc-job', item('P-1', 'decide', optiuni=OPTIUNI)))
        u_srv = self.decide('A-009', 'aprob').get_json()['uid']
        u_pc = self.decide('P-1', 'aprob').get_json()['uid']
        self.scrie_randuri(self.randuri() + [self.rand_vechi(7)])     # un rand vechi, fara `sursa`

        def uids(sursa):
            return sorted(d['uid'] for d in self.decizii(sursa=sursa).get_json()['decizii'])

        self.assertEqual(uids('pc-job'), [u_pc])
        self.assertEqual(uids('server'), sorted([u_srv, '%012x' % 7]))
        self.assertEqual(uids('ionpc'), [])
        self.assertEqual(len(self.decizii().get_json()['decizii']), 3, 'fara filtru: toate')

    def test_decizii_sursa_invalida_400(self):
        for sursa in ('', 'A', 'x', '-job', 'Pc-Job', 'pc_job', 'a' * 21):
            with self.subTest(sursa=sursa):
                r = self.decizii(sursa=sursa)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('sursa', r.get_json()['error'])

    def test_decizii_filtrul_nu_arata_anulatele(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.anuleaza(uid)
        self.assertEqual(self.decizii(sursa='server').get_json(), {'decizii': []})

    # --- consumat cu stare

    def test_consumat_cu_stare_valida_se_pastreaza(self):
        self.pune_ok('server', corp('server', *[item('A-0%d' % n, 'decide', optiuni=OPTIUNI) for n in range(3)]))
        for n, stare in enumerate(('ok', 'warn', 'fail')):
            uid = self.decide('A-0%d' % n, 'aprob').get_json()['uid']
            r = self.client.post('/api/sistem/decizii/%s/consumat' % uid, json={'rezultat': 'r', 'stare': stare},
                                 headers=self.bearer(FULL))
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual([r['stare'] for r in self.randuri()], ['ok', 'warn', 'fail'])

    def test_consumat_fara_stare_o_lasa_null(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        self.consuma(uid)
        self.assertIsNone(self.randuri()[0]['stare'])

    def test_consumat_cu_stare_invalida_400_si_decizia_ramane_in_asteptare(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        for stare in ('bine', 'OK', '', None, 5, ['ok']):
            with self.subTest(stare=stare):
                r = self.client.post('/api/sistem/decizii/%s/consumat' % uid, json={'rezultat': 'r', 'stare': stare},
                                     headers=self.bearer(FULL))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('corpul.stare', r.get_json()['error'])
        self.assertEqual(len(self.decizii().get_json()['decizii']), 1)

    # --- masini asteptate

    def test_joburile_masinii_trec_in_vedere(self):
        joburi = [{'id': 'mail-tasks', 'nume': 'Mail Tasks', 'stare': 'fail', 'ultima': '2026-11-17T06:00:40Z',
                   'urmatoarea': '2026-11-17T12:00:00Z', 'detaliu': 'cod 1'},
                  {'id': 'knowledge-sync', 'nume': 'Knowledge Sync', 'stare': 'ok', 'detaliu': 'n-a rulat încă'}]
        self.pune_ok('pc-job', corp('pc-job', joburi=joburi))
        m = {x['sursa']: x for x in self.citeste()['masini']}
        self.assertEqual(m['pc-job']['joburi'], joburi)
        self.assertEqual(m['server']['joburi'], [], 'masina fara snapshot: lista goala')

    def test_snapshot_fara_joburi_ramane_valid(self):
        self.pune_ok('pc-job', corp('pc-job'))
        m = {x['sursa']: x for x in self.citeste()['masini']}
        self.assertEqual(m['pc-job']['joburi'], [])

    def test_joburi_in_afara_contractului_400(self):
        bun = {'id': 'a', 'nume': 'A', 'stare': 'ok', 'detaliu': ''}
        for rau in ([dict(bun, x=1)], [dict(bun, stare='rau')], [dict(bun, ultima=None)], [dict(bun, ultima='azi')],
                    [bun, dict(bun)], [dict(bun, nume='')], 'nu-i lista'):
            r = self.client.put('/api/sistem/sursa/pc-job', json=corp('pc-job', joburi=rau), headers=self.bearer(FULL))
            self.assertEqual(r.status_code, 400, (rau, r.get_data(as_text=True)))

    def test_masinile_asteptate_fara_snapshot_apar_ca_fail(self):
        self.pune_ok('server', corp('server', masina='ion-ursu-thinkpad-t450'))
        masini = self.citeste()['masini']
        self.assertEqual([m['sursa'] for m in masini], ['ionpc', 'pc-job', 'server'])
        self.assertEqual(masini[0], {'sursa': 'ionpc', 'masina': '', 'ultima': None, 'vechime_ore': None,
                                     'stare': 'fail', 'detaliu': 'never reported', 'joburi': []})
        self.assertEqual(masini[1]['detaliu'], 'never reported')
        self.assertEqual((masini[2]['stare'], masini[2]['masina']), ('ok', 'ion-ursu-thinkpad-t450'))

    def test_masina_asteptata_cu_fisier_stricat_e_report_unreadable(self):
        self.pune_ok('server', corp('server'))
        with open(os.path.join(self.dir, 'pc-job.json'), 'w') as fh:
            fh.write('{nu e json')
        self.assertEqual(self.masina('pc-job')['detaliu'], 'report unreadable')
        self.assertEqual(self.masina('ionpc')['detaliu'], 'never reported')
        self.pune_ok('pc-job', corp('pc-job'))                              # un PUT valid o repara
        self.assertEqual(self.masina('pc-job')['stare'], 'ok')

    def test_sursa_in_plus_ramane_in_masini_in_ordinea_numelui(self):
        self.pune_ok('banc', corp('banc'))
        self.assertEqual([m['sursa'] for m in self.citeste()['masini']], ['banc', 'ionpc', 'pc-job', 'server'])

    # --- amanare

    def cu_doi_itemi(self):
        self.pune_ok('server', corp('server', item('A-009', 'decide', optiuni=OPTIUNI), item('s:x', 'do')))

    def test_amanare_pune_data_si_o_arata_pe_item(self):
        self.cu_doi_itemi()
        r = self.amana('A-009', '2026-11-20T08:00:00Z')
        self.assertEqual((r.status_code, r.get_json()),
                         (200, {'ok': True, 'id': 'A-009', 'pana': '2026-11-20T08:00:00Z'}))
        self.assertEqual(json.loads(self.fisier('amanari.json')), {'A-009': '2026-11-20T08:00:00Z'})
        itemi = {i['id']: i for i in self.citeste()['itemi']}
        self.assertEqual((itemi['A-009']['amanat_pana'], itemi['s:x']['amanat_pana']),
                         ('2026-11-20T08:00:00Z', None))
        self.assertEqual(self.citeste()['numar'], 2, '`numar` nu se schimba')

    def test_amanare_null_o_scoate_si_merge_si_pentru_id_necunoscut(self):
        self.cu_doi_itemi()
        self.amana('A-009', '2026-11-20T08:00:00Z')
        r = self.amana('A-009', None)
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'id': 'A-009', 'pana': None}))
        self.assertEqual(json.loads(self.fisier('amanari.json')), {})
        self.assertIsNone(self.citeste()['itemi'][0]['amanat_pana'])
        self.assertEqual(self.amana('nu-mai-exista', None).status_code, 200)

    def test_amanare_null_fara_fisier_nu_creeaza_nimic(self):
        self.assertEqual(self.amana('A-009', None).status_code, 200)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'amanari.json')))

    def test_amanare_e_idempotenta(self):
        self.cu_doi_itemi()
        self.amana('A-009', '2026-11-20T08:00:00Z')
        prima = self.fisier('amanari.json')
        self.assertEqual(self.amana('A-009', '2026-11-20T08:00:00Z').status_code, 200)
        self.assertEqual(self.fisier('amanari.json'), prima)
        self.assertFalse([n for n in os.listdir(self.dir) if n.endswith('.tmp')])

    def test_amanare_o_data_noua_o_inlocuieste(self):
        self.cu_doi_itemi()
        self.amana('A-009', '2026-11-20T08:00:00Z')
        self.amana('A-009', '2026-11-25T08:00:00Z')
        self.assertEqual(json.loads(self.fisier('amanari.json')), {'A-009': '2026-11-25T08:00:00Z'})

    def test_amanare_cu_data_gresita_400(self):
        self.cu_doi_itemi()
        cazuri = [
            '2026-11-17T08:12:00Z',                # exact acum: nu e in viitor
            '2026-11-17T08:11:59Z',                # trecut
            '2026-12-18T08:12:01Z',                # cu o secunda peste 31 de zile
            '2026-11-20T08:00:00',                 # fara Z
            '2026-11-20T08:00:00+00:00',
            '2026-11-20',
            'maine',
            5,
            '',
        ]
        for pana in cazuri:
            with self.subTest(pana=pana):
                r = self.amana('A-009', pana)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('corpul.pana', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'amanari.json')))

    def test_amanare_exact_31_de_zile_trece(self):
        self.cu_doi_itemi()
        self.assertEqual(self.amana('A-009', '2026-12-18T08:12:00Z').status_code, 200)

    def test_amanare_cu_corp_gresit_400(self):
        self.cu_doi_itemi()
        h = self.bearer(FULL)
        cazuri = [
            ({}, 'corpul.id'),
            ({'id': 'A-009'}, 'corpul.pana'),                                          # pana lipseste (null e explicit)
            ({'pana': '2026-11-20T08:00:00Z'}, 'corpul.id'),
            ({'id': '', 'pana': '2026-11-20T08:00:00Z'}, 'corpul.id'),
            ({'id': 'x' * 81, 'pana': '2026-11-20T08:00:00Z'}, 'corpul.id'),
            ({'id': 5, 'pana': '2026-11-20T08:00:00Z'}, 'corpul.id'),
            ({'id': 'A-009', 'pana': '2026-11-20T08:00:00Z', 'altceva': 1}, 'corpul.altceva'),
            ([], 'corpul'),
        ]
        for corpul, in_mesaj in cazuri:
            with self.subTest(corpul=corpul):
                r = self.client.post('/api/sistem/amanare', json=corpul, headers=h)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(in_mesaj, r.get_json()['error'])
        r = self.client.post('/api/sistem/amanare', data=b'{nu e json',
                             headers=dict(h, **{'Content-Type': 'application/json'}))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'amanari.json')))

    def test_amanare_pentru_item_care_nu_mai_exista_409(self):
        self.cu_doi_itemi()
        r = self.amana('A-999', '2026-11-20T08:00:00Z')
        self.assertEqual((r.status_code, r.get_json()), (409, {'error': 'itemul nu mai exista'}))
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'amanari.json')))

    def test_amanarile_expirate_se_taie_la_scriere_si_nu_se_arata(self):
        self.cu_doi_itemi()
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'amanari.json'), 'w') as fh:
            json.dump({'s:x': '2026-11-17T08:11:59Z', 'vechi': '2026-11-01T00:00:00Z',
                       'viitor': '2026-11-19T00:00:00Z'}, fh)
        self.assertIsNone(next(i for i in self.citeste()['itemi'] if i['id'] == 's:x')['amanat_pana'],
                          'o amanare expirata nu se arata')
        self.assertEqual(self.amana('A-009', '2026-11-20T08:00:00Z').status_code, 200)
        self.assertEqual(json.loads(self.fisier('amanari.json')),
                         {'viitor': '2026-11-19T00:00:00Z', 'A-009': '2026-11-20T08:00:00Z'})

    def test_amanari_maxim_200_peste_da_409_dar_o_amanare_existenta_se_poate_schimba(self):
        self.cu_doi_itemi()
        os.makedirs(self.dir, exist_ok=True)
        plin = {'x%d' % n: '2026-11-19T00:00:00Z' for n in range(200)}
        with open(os.path.join(self.dir, 'amanari.json'), 'w') as fh:
            json.dump(plin, fh)
        inainte = self.fisier('amanari.json')
        r = self.amana('A-009', '2026-11-20T08:00:00Z')
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertEqual(self.fisier('amanari.json'), inainte)
        # cu 199 de intrari si A-009 printre ele (200 in total), schimbarea trece
        plin.popitem()
        plin['A-009'] = '2026-11-19T00:00:00Z'
        with open(os.path.join(self.dir, 'amanari.json'), 'w') as fh:
            json.dump(plin, fh)
        self.assertEqual(self.amana('A-009', '2026-11-25T08:00:00Z').status_code, 200)
        self.assertEqual(len(json.loads(self.fisier('amanari.json'))), 200)
        # scoaterea merge oricand
        self.assertEqual(self.amana('x0', None).status_code, 200)
        self.assertEqual(len(json.loads(self.fisier('amanari.json'))), 199)

    def test_amanari_stricat_nu_strica_GET_si_nu_e_snapshot_de_sursa(self):
        self.cu_doi_itemi()
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'amanari.json'), 'w') as fh:
            fh.write('{nu e json')
        j = self.citeste()
        self.assertEqual([i['amanat_pana'] for i in j['itemi']], [None, None])
        self.assertNotIn('amanari', [m['sursa'] for m in j['masini']])
        self.assertEqual(self.amana('A-009', '2026-11-20T08:00:00Z').status_code, 200, 'un fisier stricat se rescrie')

    def test_amanari_nu_se_poate_scrie_ca_sursa(self):
        self.cu_doi_itemi()
        self.amana('A-009', '2026-11-20T08:00:00Z')
        inainte = self.fisier('amanari.json')
        r = self.pune('amanari', corp('amanari', item('x')))
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertEqual(self.fisier('amanari.json'), inainte)

    # --- taierea la 500 cu anulate

    def test_taierea_la_500_trateaza_anulatele_ca_terminate(self):
        self.cu_cerere()
        # un rand in asteptare, cel mai vechi, si 499 anulate; cu cel nou sunt 501: iese prima anulata
        randuri = [self.rand_vechi(0)] + [self.rand_vechi(n, anulat='2026-11-01T00:00:01Z') for n in range(1, 500)]
        self.scrie_randuri(randuri)
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        dupa = self.randuri()
        self.assertEqual(len(dupa), 500)
        self.assertEqual(dupa[0]['uid'], '%012x' % 0, 'cel in asteptare nu se taie, oricat de vechi')
        self.assertEqual(dupa[1]['uid'], '%012x' % 2, 'prima anulata a iesit')
        self.assertEqual(dupa[-1]['uid'], uid)

    # ----------------------------------------------------------------------- autentificare

    def test_fara_token_sau_cu_token_gresit_401(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob').get_json()['uid']
        for token in (None, 'gresit'):
            with self.subTest(token=token):
                h = self.bearer(token) if token else {}
                self.assertEqual(self.pune('pc-job', corp('pc-job'), token=token).status_code, 401)
                self.assertEqual(self.client.get('/api/sistem', headers=h).status_code, 401)
                self.assertEqual(self.client.post('/api/sistem/decizie', json={'id': 'A-009', 'optiune': 'aprob'},
                                                  headers=h).status_code, 401)
                self.assertEqual(self.client.get('/api/sistem/decizii', headers=h).status_code, 401)
                self.assertEqual(self.client.post('/api/sistem/decizii/%s/consumat' % uid, json={'rezultat': 'x'},
                                                  headers=h).status_code, 401)
        self.assertEqual(len(self.decizii().get_json()['decizii']), 1, 'nimic nu s-a consumat fara token')

    def test_dispozitivul_citeste_vederea_si_trimite_decizii(self):
        self.cu_cerere()
        j = self.citeste(token=DEVICE)
        self.assertEqual([i['id'] for i in j['itemi']], ['A-009'])
        r = self.decide('A-009', 'aprob', token=DEVICE)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))

    def test_dispozitivul_nu_scrie_surse(self):
        r = self.pune('pc-job', corp('pc-job', item()), token=DEVICE)
        self.assertEqual(r.status_code, 401)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'pc-job.json')))

    def test_dispozitivul_nu_citeste_si_nu_consuma_coada_de_decizii(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob', token=DEVICE).get_json()['uid']
        self.assertEqual(self.decizii(token=DEVICE).status_code, 401)
        self.assertEqual(self.consuma(uid, token=DEVICE).status_code, 401)
        self.assertEqual(len(self.decizii().get_json()['decizii']), 1, 'decizia a ramas neconsumata')

    def test_dispozitivul_nu_preia_decizii(self):
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob', token=DEVICE).get_json()['uid']
        self.assertEqual(self.preia(uid, token=DEVICE).status_code, 401)
        self.assertIsNone(self.randuri()[0]['preluat'], 'decizia a ramas nepreluata')
        self.assertEqual(self.preia(uid).status_code, 200, 'masina o poate prelua')

    def test_dispozitivul_anuleaza_si_amana(self):
        """Ion anuleaza si amana din Torqa pe telefon: ambele raman deschise tokenului de dispozitiv."""
        self.cu_cerere()
        uid = self.decide('A-009', 'aprob', token=DEVICE).get_json()['uid']
        r = self.anuleaza(uid, token=DEVICE)
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'uid': uid}), r.get_data(as_text=True))
        self.assertIsNotNone(self.randuri()[0]['anulat'])
        r = self.amana('A-009', '2026-11-20T08:00:00Z', token=DEVICE)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.citeste(token=DEVICE)['itemi'][0]['amanat_pana'], '2026-11-20T08:00:00Z')

    def test_sesiunea_cu_pin_are_acces_la_tot(self):
        self.cu_cerere()
        self.client.post('/login', json={'pin': '135790'})
        csrf = {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}
        self.assertEqual(self.client.get('/api/sistem').status_code, 200)
        r = self.client.put('/api/sistem/sursa/pc-job', json=corp('pc-job', item()), headers=csrf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/sistem/decizii').status_code, 200)

    def test_prefixele_din_lista_de_refuz_nu_se_calca(self):
        from utils import device_token_denied
        # refuzat dispozitivului
        for metoda, cale in (('PUT', '/api/sistem/sursa/pc-job'), ('GET', '/api/sistem/decizii'),
                             ('POST', '/api/sistem/decizii/0123456789ab/consumat')):
            self.assertTrue(device_token_denied(metoda, cale), (metoda, cale))
        for metoda, cale in (('POST', '/api/sistem/decizii/0123456789ab/preluat'),):
            self.assertTrue(device_token_denied(metoda, cale), (metoda, cale))
        # permis dispozitivului
        for metoda, cale in (('GET', '/api/sistem'), ('POST', '/api/sistem/decizie'),
                             ('POST', '/api/sistem/decizie/0123456789ab/anulare'),
                             ('POST', '/api/sistem/amanare')):
            self.assertFalse(device_token_denied(metoda, cale), (metoda, cale))

    def test_fiecare_ruta_sistem_are_login(self):
        """Nicio ruta noua fara autentificare: toate cele opt dau 401 fara sesiune si fara token."""
        reguli = [r for r in self.app_module.app.url_map.iter_rules() if r.rule.startswith('/api/sistem')]
        self.assertEqual(len(reguli), 8)
        for r in reguli:
            cale = r.rule.replace('<sursa>', 'pc-job').replace('<uid>', '0123456789ab')
            for metoda in r.methods - {'HEAD', 'OPTIONS'}:
                with self.subTest(cale=cale, metoda=metoda):
                    self.assertEqual(self.client.open(cale, method=metoda, json={}).status_code, 401)
