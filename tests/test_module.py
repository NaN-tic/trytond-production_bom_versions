
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool
from trytond.transaction import Transaction


class ProductionBomVersionsTestCase(CompanyTestMixin, ModuleTestCase):
    'Test ProductionBomVersions module'
    module = 'production_bom_versions'

    @with_transaction()
    def test_bom_is_valid(self):
        "Test bom is_valid"
        pool = Pool()
        Bom = pool.get('production.bom')
        Production = pool.get('production')

        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        after_tomorrow = tomorrow + dt.timedelta(days=1)
        yesterday = today - dt.timedelta(days=1)
        before_yesterday = today - dt.timedelta(days=2)

        bom1 = Bom()
        bom1.name = 'Test1'
        bom1.start_date = today
        bom1.save()

        bom2 = Bom()
        bom2.name = 'Test2'
        bom2.start_date = before_yesterday
        bom2.end_date = yesterday
        bom2.save()

        production = Production()

        self.assertEqual(production.bom_valid, True)

        production.bom = bom1
        self.assertEqual(production.bom_valid, True)

        production.bom = bom2
        self.assertEqual(production.bom_valid, False)

        production.planned_date = yesterday
        self.assertEqual(production.bom_valid, True)

del ModuleTestCase
