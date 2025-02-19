# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from trytond.model import ModelView, Unique, Check, fields
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder, Bool, Date, Eval, If
from trytond.pool import Pool, PoolMeta
from trytond.i18n import gettext
from trytond.exceptions import UserError, UserWarning


class BOM(metaclass=PoolMeta):
    __name__ = 'production.bom'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    version = fields.Integer('Version', readonly=True)
    master_bom = fields.Many2One('production.bom', 'BOM', readonly=True)
    reason_change = fields.Text('Reason for Change')
    modification_made = fields.Text('Modification Made')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('report_code_uniq', Unique(t, t.master_bom, t.version),
                'production_bom_versions.msg_bom_report_code_uniq'),
            ('end_date_check',
                Check(t, ((t.end_date == None) | (t.end_date > t.start_date))),
                'production_bom_versions.msg_bom_end_date_check'),
            ]
        cls._order.insert(0, ('version', 'DESC NULLS LAST'))

    @staticmethod
    def default_version():
        return 1

    @staticmethod
    def default_start_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    def get_rec_name(self, name):
        rec_name = super().get_rec_name(name)
        if self.version:
            rec_name += " (%s)" % self.version
        return rec_name

    @classmethod
    def get_last_version(cls, master_bom):
        '''
        Get latest version for master_bom
        '''
        with Transaction().set_context(show_versions=True):
            boms = cls.search([
                    ('master_bom', '=', master_bom),
                ], order=[
                    ('version', 'DESC')
                ], limit=1)
        if boms:
            return boms[0]

    @classmethod
    def validate(cls, boms):
        super(BOM, cls).validate(boms)
        for bom in boms:
            bom.check_dates()

    def check_dates(self):
        if not self.master_bom:
            return
        with Transaction().set_context(show_versions=True):
            domain = [
                ('master_bom', '=', self.master_bom.id),
                ('id', '!=', self.id),
            ]
            if not self.end_date:
                domain.append(['OR', [
                                ('end_date', '=', None),
                            ], [
                                ('end_date', '>', self.start_date),
                            ]
                        ])
            else:
                domain.append(('start_date', '<', self.end_date))
                domain.append(['OR', [
                                    ('end_date', '=', None),
                                ], [
                                    ('end_date', '>', self.start_date),
                                ]
                            ])
            with Transaction().set_context(show_versions=True):
                boms = self.search(domain, limit=1)
                if boms:
                    raise UserError(gettext('production_bom_versions.'
                            'msg_invalid_dates',
                            bom=self.rec_name,
                            version=boms[0].version))
    @classmethod
    def create(cls, vlist):
        boms = super(BOM, cls).create(vlist)
        for bom in boms:
            if not bom.master_bom:
                bom.master_bom = bom
                bom.save()
        return boms

    @classmethod
    def copy(cls, boms, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        if not Transaction().context.get('new_version', False):
            default['master_bom'] = None
            default['version'] = cls.default_version()
            return super(BOM, cls).copy(boms, default=default)

        new_boms = []
        for bom in boms:
            last_bom = cls.get_last_version(bom.master_bom)
            default['version'] = last_bom.version + 1
            new_boms.extend(super(BOM, cls).copy([bom], default=default))
        return new_boms

    def _product_new_version_boms(self):
        pool = Pool()
        ProductBOM = pool.get('product.product-production.bom')

        res = []
        for output in self.outputs:
            res.append(ProductBOM(
                    product=output.product,
                    bom=self,
                    ))
        return res

    @classmethod
    def new_version(cls, boms, date, reason_change, modification_made):
        pool = Pool()
        ProductBOM = pool.get('product.product-production.bom')

        cls.write(boms, {
            'end_date': date - datetime.timedelta(days=1),
            })

        with Transaction().set_context(new_version=True):
            new_boms = cls.copy(boms, {
                    'end_date': None,
                    'start_date': date,
                    'reason_change': reason_change,
                    'modification_made': modification_made,
                    })

        # relate new version BOMs to the product in case source bom is related to the product
        existing_keys = set((pb.product.id, pb.bom.master_bom)
            for pb in ProductBOM.search([('bom', 'in', boms)]))

        to_save = []
        for new_bom in new_boms:
            for output in new_bom.outputs:
                key = (output.product.id, new_bom.master_bom)
                if key in existing_keys:
                    to_save += [ProductBOM(
                            product=output.product,
                            bom=new_bom,
                            )]


        ProductBOM.save(to_save)
        return new_boms


class Production(metaclass=PoolMeta):
    __name__ = 'production'
    bom_valid = fields.Function(fields.Boolean('Bom Valid'), 'on_change_with_bom_valid')

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        cls.bom.domain += [If((Eval('state').in_(['request', 'draft'])) & ~Bool(Eval('bom', False)),
            [
                ('start_date', '<=', If(Bool(Eval('effective_date')), Eval('effective_date'), Eval('planned_date', Date()))),
                ['OR',
                    ('end_date', '>=', If(Bool(Eval('effective_date')), Eval('effective_date'), Eval('planned_date', Date()))),
                    ('end_date', '=', None),
                ]
            ],
            ())]

    @fields.depends('effective_date', 'planned_date', 'bom')
    def on_change_with_bom_valid(self, name=None):
        pool = Pool()
        Date = pool.get('ir.date')

        today = Date.today()
        production_date = self.effective_date or self.planned_date or today
        bom = self.bom
        if not bom:
            return True

        if (bom.end_date and (bom.start_date <= production_date
                and bom.end_date < production_date)):
            return False
        elif production_date < bom.start_date:
            return False
        return True

    @classmethod
    def run(cls, productions):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        for production in productions:
            if production.bom_valid:
                continue

            key = 'bom_expired_date_%s_%s' % (production.id, production.bom.id)
            if Warning.check(key):
                raise UserWarning(key,
                    gettext('production_bom_versions.msg_bom_expired_date',
                        production=production.rec_name,
                        bom=production.bom.rec_name,
                        ))
        return super().run(productions)


class NewVersionStart(ModelView):
    'New Version Start'
    __name__ = 'production.bom.new.version.start'

    date = fields.Date('Date')
    reason_change = fields.Text('Reason for Change')
    modification_made = fields.Text('Modification Made')

    @staticmethod
    def default_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()


class NewVersion(Wizard):
    'New Version'
    __name__ = 'production.bom.new.version'

    start = StateView('production.bom.new.version.start',
        'production_bom_versions.new_version_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-forward', default=True),
            ])
    create_ = StateAction('production.act_bom_list')

    def do_create_(self, action):
        pool = Pool()
        BOM = pool.get('production.bom')

        boms = self.records
        new_versions = BOM.new_version(boms, self.start.date,
            self.start.reason_change, self.start.modification_made)

        data = {'res_id': [i.id for i in new_versions]}
        if len(new_versions) == 1:
            action['views'].reverse()
        return action, data

    def transition_create_(self):
        return 'end'


class OpenVersions(Wizard):
    'Open Versions'
    __name__ = 'production.bom.open_versions'
    start_state = 'open_'
    open_ = StateAction('production.act_bom_list')


    def do_open_(self, action):
        pool = Pool()
        Bom = pool.get('production.bom')

        bom = self.record

        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('master_bom', '=', bom and bom.master_bom and bom.master_bom.id)])
        action['pyson_order'] = encoder.encode([('version', 'DESC')])
        context = {'show_versions': True}
        bom = Bom.get_last_version(bom.master_bom and bom.master_bom.id)
        action['pyson_context'] = encoder.encode(context)

        action['name'] += ' - %s' % (gettext('production_bom_versions.'
                'msg_versions', version=bom.rec_name))

        return action, {}

    def transition_open_(self):
        return 'end'
