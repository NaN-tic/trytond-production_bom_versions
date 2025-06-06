import datetime as dt
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.exceptions import UserWarning
from trytond.modules.company.tests.tools import create_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        today = dt.date.today()
        yesterday = today - dt.timedelta(days=1)
        yesterday2 = today - dt.timedelta(days=2)
        yesterday3 = today - dt.timedelta(days=3)
        yesterday4 = today - dt.timedelta(days=4)

        # Activate modules
        config = activate_modules('production_bom_versions')
        Warning = Model.get('res.user.warning')

        # Create company
        _ = create_company()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.producible = True
        template.list_price = Decimal(30)
        product, = template.products
        product.cost_price = Decimal(20)
        template.save()
        product, = template.products

        # Create Components
        template1 = ProductTemplate()
        template1.name = 'component 1'
        template1.default_uom = unit
        template1.type = 'goods'
        template1.list_price = Decimal(5)
        component1, = template1.products
        component1.cost_price = Decimal(1)
        template1.save()
        component1, = template1.products
        meter, = ProductUom.find([('name', '=', 'Meter')])
        centimeter, = ProductUom.find([('name', '=', 'Centimeter')])
        template2 = ProductTemplate()
        template2.name = 'component 2'
        template2.default_uom = meter
        template2.type = 'goods'
        template2.list_price = Decimal(7)
        component2, = template2.products
        component2.cost_price = Decimal(5)
        template2.save()
        component2, = template2.products

        # Create Bill of Material
        BOM = Model.get('production.bom')
        BOMInput = Model.get('production.bom.input')
        BOMOutput = Model.get('production.bom.output')
        bom = BOM(name='product')
        bom.start_date = today
        input1 = BOMInput()
        bom.inputs.append(input1)
        input1.product = component1
        input1.quantity = 5
        input2 = BOMInput()
        bom.inputs.append(input2)
        input2.product = component2
        input2.quantity = 150
        input2.unit = centimeter
        output = BOMOutput()
        bom.outputs.append(output)
        output.product = product
        output.quantity = 1
        bom.save()

        # Create an Inventory
        Inventory = Model.get('stock.inventory')
        InventoryLine = Model.get('stock.inventory.line')
        Location = Model.get('stock.location')
        storage, = Location.find([
            ('code', '=', 'STO'),
        ])
        inventory = Inventory()
        inventory.location = storage
        inventory_line1 = InventoryLine()
        inventory.lines.append(inventory_line1)
        inventory_line1.product = component1
        inventory_line1.quantity = 20
        inventory_line2 = InventoryLine()
        inventory.lines.append(inventory_line2)
        inventory_line2.product = component2
        inventory_line2.quantity = 6
        inventory.click('confirm')
        self.assertEqual(inventory.state, 'done')

        # Make a production
        Production = Model.get('production')
        production = Production()
        production.planned_date = today
        production.product = product
        production.bom = bom
        production.quantity = 2
        self.assertEqual(
            sorted([i.quantity for i in production.inputs]) == [10, 300], True)
        output, = production.outputs
        self.assertEqual(output.quantity, 2)
        production.save()
        self.assertEqual(production.state, 'draft')
        production.click('wait')
        self.assertEqual(production.state, 'waiting')
        production.click('assign_try')
        self.assertEqual(production.state, 'assigned')
        production.click('run')
        self.assertEqual(production.state, 'running')

        # Make a production, expired bom date and try to run the production
        production_id, = Production.copy([production], config.context)
        production = Production(production_id)
        self.assertEqual(production.state, 'draft')
        production.click('wait')
        self.assertEqual(production.state, 'waiting')
        bom.start_date = yesterday4
        bom.end_date = yesterday3
        bom.save()
        production.click('assign_try')
        self.assertEqual(production.state, 'assigned')

        with self.assertRaises(UserWarning):
            try:
                production.click('run')
            except UserWarning as warning:
                _, (key, *_) = warning.args
                raise

        Warning(user=config.user, name=key).save()
        production.click('run')
        self.assertEqual(production.state, 'running')

        # Relate BOM to product
        self.assertEqual(len(product.boms), 0)

        ProductBom = Model.get('product.product-production.bom')
        product_bom = ProductBom(
            product=product,
            bom=bom,
            )
        product_bom.save()
        product.reload()
        self.assertEqual(len(product.boms), 1)

        # Create two new bom versions from the wizard, and check that boom is related to product
        bom_new_version = Wizard('production.bom.new.version', [bom])
        bom_new_version.form.date = yesterday2
        bom_new_version.form.reason_change = 'Test New Version'
        bom_new_version.execute('create_')

        product.reload()
        self.assertEqual(len(product.boms), 2)
        new_bom = product.boms[0].bom
        self.assertEqual((new_bom.start_date, new_bom.end_date),
            (yesterday2, None))

        bom_new_version2 = Wizard('production.bom.new.version', [new_bom])
        bom_new_version2.form.date = today
        bom_new_version2.form.reason_change = 'Test New Version'
        bom_new_version2.execute('create_')

        product.reload()
        self.assertEqual(len(product.boms), 3)

        # product.boms return boms ordered by version
        bom1, bom2, bom3 = product.boms[0].bom, product.boms[1].bom, product.boms[2].bom

        # version, start_date, end_date
        values = [
            ('product (3)', 3, today, None),
            ('product (2)', 2, yesterday2, yesterday),
            ('product (1)', 1, yesterday4, yesterday3),
            ]
        for i, bom in enumerate([bom1, bom2, bom3]):
            self.assertEqual(
                (bom.rec_name, bom.version, bom.start_date, bom.end_date), values[i])
