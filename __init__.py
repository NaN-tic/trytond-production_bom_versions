#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from . import bom
from . import product

def register():
    Pool.register(
        bom.BOM,
        bom.Production,
        bom.NewVersionStart,
        product.Product,
        module='production_bom_versions', type_='model')
    Pool.register(
        bom.OpenVersions,
        bom.NewVersion,
        module='production_bom_versions', type_='wizard')
