#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from trytond.pool import Pool
from bom import *


def register():
    Pool.register(
        BOM,
        NewVersionStart,
        module='production_bom_versions', type_='model')
    Pool.register(
        OpenVersions,
        NewVersion,
        module='production_bom_versions', type_='wizard')
