"""Datele care intra in baza: `utils.norm_date` si `_norm_dates` (palnia tuturor scrierilor).

Regula lor: nu stocam niciodata o data pe care n-o putem citi. Asa a ajuns
`23.02.2026` pe un proiect si a stat nevazut in Calendar — nimic nu-l putea aseza
pe o zi. Testele de aici pazesc ambele jumatati ale regulii: ce se poate citi se
aduce la ISO, ce nu se poate citi se refuza (nu se ghiceste si nu se tace).
"""

import unittest

from _baza import Test
from utils import norm_date, _norm_dates


class NormDate(Test):

    def test_gol_ramane_gol_si_none_ramane_none(self):
        self.assertIsNone(norm_date(None))
        self.assertEqual(norm_date(''), '')
        self.assertEqual(norm_date('   '), '')

    def test_iso_ramane_neatins_inclusiv_timestampul(self):
        self.assertEqual(norm_date('2026-09-28'), '2026-09-28')
        # `data_finalizare` a unui task e un timestamp: nu se ciunteste.
        self.assertEqual(norm_date('2026-09-28T10:15:00.123456'), '2026-09-28T10:15:00.123456')

    def test_forma_romaneasca_se_aduce_la_iso(self):
        for scris, iso in [('28.09.2026', '2026-09-28'), ('28/09/2026', '2026-09-28'),
                           ('28-09-2026', '2026-09-28'), ('1.2.2026', '2026-02-01'),
                           ('28.09.26', '2026-09-28')]:
            self.assertEqual(norm_date(scris), iso, scris)

    def test_ce_nu_exista_in_calendar_se_refuza(self):
        for rau in ['2026-02-31', '31.02.2026', '2026-13-01', '00.01.2026']:
            with self.assertRaises(ValueError, msg=rau):
                norm_date(rau)

    def test_ce_nu_se_poate_citi_se_refuza(self):
        for rau in ['maine', '28 septembrie', '2026/09/28', '28.09']:
            with self.assertRaises(ValueError, msg=rau):
                norm_date(rau)
        with self.assertRaises(ValueError):
            norm_date(20260928)


class NormDates(Test):

    def test_doar_campurile_de_data_si_oricat_de_adanc(self):
        # Importul de debrief are proiect + taskuri[] + implementari[].
        corp = {
            'data_finalizare': '28.09.2026',
            'titlu': '28.09.2026',                    # NU e camp de data: ramane text
            'taskuri': [{'data_scadenta': '1.10.2026', 'titlu': 'x'}],
            'implementari': [{'data_start': '5.10.2026', 'data_sfarsit': ''}],
        }
        _norm_dates(corp)
        self.assertEqual(corp['data_finalizare'], '2026-09-28')
        self.assertEqual(corp['titlu'], '28.09.2026')
        self.assertEqual(corp['taskuri'][0]['data_scadenta'], '2026-10-01')
        self.assertEqual(corp['implementari'][0]['data_start'], '2026-10-05')
        self.assertEqual(corp['implementari'][0]['data_sfarsit'], '')

    def test_o_data_rea_oriunde_opreste_tot_corpul(self):
        with self.assertRaises(ValueError):
            _norm_dates({'taskuri': [{'data_scadenta': '31.02.2026'}]})


if __name__ == '__main__':
    unittest.main()
