
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

        today = dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        after_tomorrow = tomorrow + dt.timedelta(days=1)
        yesterday = today - dt.timedelta(days=1)

        bom = Bom()
        bom.name = 'Test'
        bom.start_date = today
        bom.save()

        self.assertEqual(bom.is_valid, True)

        with Transaction().set_context(production_date=today):
            self.assertEqual(bom.is_valid, True)

        with Transaction().set_context(production_date=yesterday):
            self.assertEqual(bom.is_valid, False)

        bom.start_date = yesterday
        bom.end_date = yesterday
        self.assertEqual(bom.is_valid, False)

        bom.end_date = tomorrow
        self.assertEqual(bom.is_valid, True)

        bom.start_date = after_tomorrow
        bom.end_date = None
        with Transaction().set_context(production_date=today):
            self.assertEqual(bom.is_valid, False)

del ModuleTestCase
