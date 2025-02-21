# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.boms.order.insert(0, ('bom.version', 'DESC NULLS LAST'))
