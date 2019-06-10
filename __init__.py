#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from . import bom

def register():
    Pool.register(
        bom.BOM,
        bom.Production,
        bom.NewVersionStart,
        module='production_bom_versions', type_='model')
    Pool.register(
        bom.OpenVersions,
        bom.NewVersion,
        module='production_bom_versions', type_='wizard')
