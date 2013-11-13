#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import datetime
from sql import Literal
from sql.conditionals import Coalesce

from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder
from trytond.pool import Pool, PoolMeta

__all__ = ['BOM', 'NewVersionStart', 'NewVersion', 'OpenVersions']
__metaclass__ = PoolMeta


class BOM:
    __name__ = 'production.bom'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    version = fields.Integer('Version', readonly=True)
    master_bom = fields.Many2One('production.bom', 'BOM')

    @classmethod
    def __setup__(cls):
        super(BOM, cls).__setup__()
        cls._sql_constraints += [
                ('report_code_uniq', 'unique (master_bom,version)',
                'Version Must be unique per BOM')
            ]
        cls._error_messages.update({
                'invalid_dates': 'Invalid dates for version "%(bom)s". They '
                    'overlap with version "%(version)s.',
            })

    @staticmethod
    def default_version():
        pool = Pool()
        Bom = pool.get('production.bom')
        master_bom = Transaction().context.get('master_bom')
        if master_bom:
            bom = Bom.get_last_version(master_bom)
            return bom.version + 1
        return 1

    @staticmethod
    def default_master_bom():
        return Transaction().context.get('master_bom')

    @staticmethod
    def default_start_date():
        return datetime.date.today()

    @staticmethod
    def excluded_version_fields():
        return ['id', 'create_uid', 'create_date', 'write_uid', 'write_date',
            'output_products', 'rec_name', 'master_bom', 'version',
            'start_date']

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        context = Transaction().context
        defaults = super(BOM, cls).default_get(fields_names, with_rec_name)
        for name in fields_names:
            if name not in cls.excluded_version_fields():
                context_name = 'master_bom_' + name
                value = context.get(context_name)
                if value:
                    defaults[name] = value
        return defaults

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

    def check_dates(self):
        if not self.master_bom:
            return
        with Transaction().set_context(show_versions=True):
            boms = self.search([
                    ('master_bom', '=', self.master_bom.id),
                    ('id', '!=', self.id),
                ])
            for bom in boms:
                if (bom.end_date and self.start_date < bom.end_date) or \
                        (self.end_date and self.end_date < bom.start_date):
                    self.raise_user_error('invalid_dates', {
                                'bom': self.rec_name,
                                'version': bom.version,
                            })

    @classmethod
    def validate(cls, boms):
        super(BOM, cls).validate(boms)
        for bom in boms:
            bom.check_dates()

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Inputs = pool.get('production.bom.input')
        Outputs = pool.get('production.bom.output')
        context = Transaction().context

        inputs_to_copy = {}
        outputs_to_copy = {}

        if not context.get('new_version', False):
            for value in vlist:
                master_bom = value.get('master_bom', context.get('master_bom'))
                if master_bom:
                    value['master_bom'] = master_bom
                    bom = cls.get_last_version(master_bom)
                    if bom:
                        value['version'] = bom.version + 1
                        date = value.get('start_date', datetime.date.today())
                        cls.write([bom], {'end_date': date})
                        for field in ('inputs', 'outputs'):
                            if field in value:
                                if field == 'inputs':
                                    save = inputs_to_copy
                                else:
                                    save = outputs_to_copy
                                for key in value[field]:
                                    if not key[0] == 'add':
                                        continue
                                save[bom.id] = key[1]
        boms = super(BOM, cls).create(vlist)
        for bom, ids in inputs_to_copy.iteritems():
            ins = Inputs.browse(ids)
            Inputs.copy(ins, {'bom': bom})
        for bom, ids in outputs_to_copy.iteritems():
            ins = Outputs.browse(ids)
            Outputs.copy(ins, {'bom': bom})
        for bom in boms:
            if not bom.master_bom:
                bom.master_bom = bom
                bom.save()
        return boms

    @classmethod
    def copy(cls, boms, default=None):
        if default is None:
            default = {}
        if not Transaction().context.get('new_version', False):
            default['master_bom'] = None
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
        transaction = Transaction()
        context = transaction.context
        cursor = transaction.cursor

        if not context.get('show_versions', False):
            table = cls.__table__()
            today = datetime.date.today()

            q = table.select(table.id, where=(table.start_date <= today) &
                (Literal(today) <= Coalesce(table.end_date, datetime.date.max)))
            cursor.execute(*q)
            ids = [r[0] for r in cursor.fetchall()]
            args.append(('id', 'in', ids))

        return super(BOM, cls).search(args, offset=offset, limit=limit,
            order=order, count=count, query=query)

    @classmethod
    def new_version(cls, boms, date):
        with Transaction().set_context(new_version=True):
            new_boms = cls.copy(boms, {
                    'end_date': None,
                    'start_date': date
                })
        cls.write(boms, {'end_date': date})
        return new_boms


class NewVersionStart(ModelView):
    'New Version Start'
    __name__ = 'production.bom.new.version.start'

    date = fields.Date('Date')

    @staticmethod
    def default_date():
        return datetime.date.today()


class NewVersion(Wizard):
    'New Version'
    __name__ = 'production.bom.new.version'

    start = StateView('production.bom.new.version.start',
        'production_bom_history.new_version_start_form', [
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

    @classmethod
    def __setup__(cls):
        super(OpenVersions, cls).__setup__()
        cls._error_messages.update({
                'versions': ('%s\'s versions'),
                })

    def do_open_(self, action):
        pool = Pool()
        Bom = pool.get('production.bom')

        transaction = Transaction()
        context = transaction.context

        bom = Bom(context.get('active_id'))

        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('master_bom', '=', bom.master_bom.id)])
        action['pyson_order'] = encoder.encode([('version', 'DESC')])
        context = {'show_versions': True, 'master_bom': bom.master_bom.id}
        bom = Bom.get_last_version(bom.master_bom.id)
        if bom:
            for name, field in Bom._fields.iteritems():
                if name not in Bom.excluded_version_fields():
                    value = getattr(bom, name)
                    if field._type in ('many2one',) and value:
                        value = value.id
                    if field._type in ('one2many', 'many2many') and value:
                        values = [r.id for r in value]
                        value = values

                    context['master_bom_' + name] = value

        action['pyson_context'] = encoder.encode(context)

        action['name'] += ' - %s' % (self.raise_user_error(error='versions',
                raise_exception=False, error_args=bom.rec_name))

        return action, {}

    def transition_open_(self):
        return 'end'
