# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from sql import Literal
from sql.conditionals import Coalesce

from trytond.model import ModelView, Unique, Check, fields
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder, Bool, Eval, If
from trytond.pool import Pool, PoolMeta
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['BOM', 'Production', 'NewVersionStart', 'NewVersion',
    'OpenVersions']


class BOM(metaclass=PoolMeta):
    __name__ = 'production.bom'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    version = fields.Integer('Version', readonly=True)
    master_bom = fields.Many2One('production.bom', 'BOM', readonly=True)

    @classmethod
    def __setup__(cls):
        super(BOM, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('report_code_uniq', Unique(t, t.master_bom, t.version),
                'production_bom_versions.msg_bom_report_code_uniq'),
            ('end_date_check',
                Check(t, ((t.end_date == None) | (t.end_date > t.start_date))),
                'production_bom_Versions.msg_end_date_check'),
            ]

    @staticmethod
    def default_version():
        return 1

    @staticmethod
    def default_start_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

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

    @classmethod
    def search(cls, args, offset=0, limit=None, order=None, count=False,
            query=False):
        pool = Pool()
        Date = pool.get('ir.date')
        transaction = Transaction()
        context = transaction.context
        cursor = transaction.connection.cursor()

        if not context.get('show_versions', False):
            table = cls.__table__()
            today = (context['production_date']
                if context.get('production_date') else Date.today())

            q = table.select(table.id, where=(table.start_date <= today) &
                (Literal(today) <= Coalesce(table.end_date, datetime.date.max))
                )
            cursor.execute(*q)
            ids = [r[0] for r in cursor.fetchall()]
            args.append(('id', 'in', ids))

        return super(BOM, cls).search(args, offset=offset, limit=limit,
            order=order, count=count, query=query)

    @classmethod
    def new_version(cls, boms, date):
        cls.write(boms, {'end_date': date - datetime.timedelta(days=1)})
        with Transaction().set_context(new_version=True):
            new_boms = cls.copy(boms, {
                    'end_date': None,
                    'start_date': date
                    })
        return new_boms


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        if 'production_date' not in cls.bom.context:
            cls.bom.context['production_date'] = If(
                Bool(Eval('effective_date')),
                Eval('effective_date'),
                Eval('planned_date'))
        for fname in ('effective_date', 'planned_date'):
            if fname not in cls.bom.depends:
                cls.bom.depends.append(fname)


class NewVersionStart(ModelView):
    'New Version Start'
    __name__ = 'production.bom.new.version.start'

    date = fields.Date('Date')

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
            Button('Create', 'create_', 'tryton-go-next', default=True),
            ])
    create_ = StateAction('production.act_bom_list')

    def do_create_(self, action):
        pool = Pool()
        BOM = pool.get('production.bom')

        boms = BOM.browse(Transaction().context['active_ids'])
        new_versions = BOM.new_version(boms, self.start.date)

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

        transaction = Transaction()
        context = transaction.context

        bom = Bom(context.get('active_id'))

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
