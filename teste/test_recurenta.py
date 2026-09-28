"""Recurenta, ora si sfera unui task — regulile scrise in `blueprints/tasks.py`.

Recurenta e locul in care o greseala nu se vede azi, ci la urmatoarea aparitie:
un task lunar pus pe 31 trebuie sa cada pe ultima zi a lunii scurte, iar nimic nu
cade in weekend (Ion nu lucreaza sambata si duminica — `_skip_weekend`).
Datele de mai jos sunt fixe si verificate in calendar: 2026-09-28 e luni.
"""

import unittest
from datetime import date, timedelta

from _baza import Test
from blueprints.tasks import _skip_weekend, _next_recurrence_date, norm_ora, _sfera_or_none


class Weekend(Test):

    def test_sambata_si_duminica_merg_luni(self):
        self.assertEqual(_skip_weekend(date(2026, 10, 3)), date(2026, 10, 5))   # sambata
        self.assertEqual(_skip_weekend(date(2026, 10, 4)), date(2026, 10, 5))   # duminica

    def test_zilele_lucratoare_raman(self):
        for zi in range(28, 31):                                               # luni..miercuri
            self.assertEqual(_skip_weekend(date(2026, 9, zi)), date(2026, 9, zi))


class UrmatoareaAparitie(Test):

    def test_zilnic_de_vineri_revine_luni(self):
        self.assertEqual(_next_recurrence_date('2026-10-02', 'zilnic'), '2026-10-05')

    def test_saptamanal(self):
        self.assertEqual(_next_recurrence_date('2026-09-28', 'saptamanal'), '2026-10-05')

    def test_lunar_pe_31_cade_pe_ultima_zi_a_lunii_scurte(self):
        self.assertEqual(_next_recurrence_date('2026-03-31', 'lunar'), '2026-04-30')

    def test_lunar_care_cade_sambata_merge_luni(self):
        # 31 ian -> 28 feb 2026, care e sambata -> luni, 2 martie.
        self.assertEqual(_next_recurrence_date('2026-01-31', 'lunar'), '2026-03-02')

    def test_lunar_trece_anul(self):
        self.assertEqual(_next_recurrence_date('2026-12-15', 'lunar'), '2027-01-15')

    def test_fara_baza_pleaca_de_azi_si_nu_cade_in_weekend(self):
        d = date.fromisoformat(_next_recurrence_date('', 'zilnic'))
        azi = date.today()
        self.assertTrue(azi < d <= azi + timedelta(days=3), d)
        self.assertLess(d.weekday(), 5)

    def test_recurenta_necunoscuta_nu_inventeaza_o_data(self):
        self.assertEqual(_next_recurrence_date('2026-09-28', 'anual'), '2026-09-28')
        self.assertEqual(_next_recurrence_date('', 'anual'), '')


class Ora(Test):

    def test_trei_rezultate_neatins_sters_pus(self):
        self.assertIsNone(norm_ora(None))
        self.assertEqual(norm_ora(''), '')
        self.assertEqual(norm_ora('9:00'), '09:00')

    def test_formele_scrise_de_mana(self):
        for scris, ora in [('9.05', '09:05'), ('23:59', '23:59'), ('0:00', '00:00'), (' 7:30 ', '07:30')]:
            self.assertEqual(norm_ora(scris), ora, scris)

    def test_ce_nu_e_ora_se_refuza(self):
        for rau in ['24:00', '12:60', '9', '9:5', 'noua', '9:00:00']:
            with self.assertRaises(ValueError, msg=rau):
                norm_ora(rau)


class Sfera(Test):

    def test_doar_cele_doua_sfere(self):
        self.assertEqual(_sfera_or_none('munca'), 'munca')
        self.assertEqual(_sfera_or_none('personal'), 'personal')
        # Invariantul 7: o valoare necunoscuta NU se corecteaza tacit.
        for rau in ['Munca', 'xyz', '', None]:
            self.assertIsNone(_sfera_or_none(rau), rau)


if __name__ == '__main__':
    unittest.main()
