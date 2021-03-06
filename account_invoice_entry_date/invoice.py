# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 ISA srl (<http://www.isa.it>).
#    Copyright (C) 2013 Sergio Corato (<http://www.icstools.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time
from openerp.osv import fields, orm
from openerp.tools.translate import _
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT


class account_invoice(orm.Model):

    _inherit = 'account.invoice'

    def _maturity(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for o in self.browse(cr, uid, ids, context):
            if not o.id in res:
                res[o.id] = []
            if o.move_id and o.move_id.line_id:
                for line in o.move_id.line_id:
                    if line.date_maturity:
                        res[o.id].append(line.id)
        return res

    def _format_time(self, date):
        return datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT).strftime('%d/%m/%Y')

    def _get_preview_line(self, invoice, line):
        currency_name = invoice.currency_id.name
        amount_total_line = line[1]
        t_pterm = {
                   'date':self._format_time(line[0]),
                   'amount':amount_total_line,
                   'currency_name':currency_name}
        return t_pterm

    def _get_preview_lines(self, cr, uid, ids, field_name, arg, context=None):
        context = context or {}
        result = {}
        if not len(ids):
            return []
        ait_obj = self.pool.get('account.invoice.tax')
        amount_tax = 0.0
        for invoice in self.browse(cr, uid, ids, context):
            if not invoice.id in result:
                result[invoice.id] = []
            if invoice.state == 'draft':
                compute_taxes = ait_obj.compute(cr, uid, invoice.id, context=context)
                for tax in compute_taxes:
                    amount_tax += compute_taxes[tax]['amount']
                t_amount_total = invoice.amount_total
                context.update({'amount_tax': amount_tax})
                if invoice.payment_term:
                    for line in self.pool['account.payment.term'].compute(cr, uid, invoice.payment_term.id, t_amount_total, date_ref=invoice.date_invoice, context=context):
                        result[invoice.id].append(self._get_preview_line(invoice, line))
        return result

    _columns = {
        'registration_date': fields.date('Registration Date', states={'paid': [('readonly', True)], 'open': [('readonly', True)], 'close': [('readonly', True)]}, select=True, help="Keep empty to use the current date"),
        'maturity_ids': fields.function(
            _maturity, type="one2many", store=False,
            relation="account.move.line", method=True),
        'payments_preview':   fields.function(_get_preview_lines,
                                    type="one2many",
                                    relation='account.invoice.maturity.preview.lines',
                                    string="Maturities preview (calculated at invoice validation time)",
                                    readonly=True),
#        'payments_overview':  fields.function(_get_payments_overview,
#                                    type="one2many",
#                                    relation='account.invoice.maturity.preview.lines',
#                                    string="Payments overview", readonly=True),
    }
    
    def action_move_create(self, cr, uid, ids, context=None):
        super(account_invoice, self).action_move_create(cr, uid, ids, context=context)
        for inv in self.browse(cr, uid, ids):
            date_invoice = inv.date_invoice
            reg_date = inv.registration_date
            if not inv.registration_date:
                if date_invoice:
                    reg_date = date_invoice
                else:
                    reg_date = time.strftime('%Y-%m-%d')
            if date_invoice and reg_date:
                if (date_invoice > reg_date):
                    raise orm.except_orm(_('Error date !'), _('The invoice date cannot be later than the date of registration!'))
            #periodo
            if inv.type in ['in_invoice', 'in_refund']:
                date_start = inv.registration_date or inv.date_invoice or time.strftime('%Y-%m-%d')
                date_stop = inv.registration_date or inv.date_invoice or time.strftime('%Y-%m-%d')
            elif inv.type in ['out_invoice', 'out_refund']:
                date_start = inv.date_invoice or inv.registration_date or time.strftime('%Y-%m-%d')
                date_stop = inv.date_invoice or inv.registration_date or time.strftime('%Y-%m-%d')
            period_ids = self.pool['account.period'].search(
                cr, uid, [('date_start', '<=', date_start), ('date_stop', '>=', date_stop), ('company_id', '=', inv.company_id.id)])
            if period_ids:
                period_id = period_ids[0]
                self.write(cr, uid, [inv.id], {'registration_date': reg_date, 'period_id': period_id})
                mov_date = reg_date or inv.date_invoice or time.strftime('%Y-%m-%d')
                self.pool['account.move'].write(cr, uid, [inv.move_id.id], {'state': 'draft'})
                if inv.supplier_invoice_number:
                    sql = "update account_move_line set period_id = " + \
                        str(period_id) + ", date = '" + mov_date + "' , ref = '" + \
                        inv.supplier_invoice_number + "' where move_id = " + str(inv.move_id.id)
                else:
                    sql = "update account_move_line set period_id = " + \
                        str(period_id) + ", date = '" + mov_date + "' where move_id = " + str(inv.move_id.id)
                cr.execute(sql)
                if inv.supplier_invoice_number:
                    self.pool['account.move'].write(
                    cr, uid, [inv.move_id.id], {
                        'period_id': period_id,
                        'date': mov_date,
                        'ref': inv.supplier_invoice_number})
                else:
                    self.pool['account.move'].write(
                        cr, uid, [inv.move_id.id], {'period_id': period_id, 'date': mov_date})
                self.pool['account.move'].write(cr, uid, [inv.move_id.id], {'state': 'posted'})

        self._log_event(cr, uid, ids)
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        if 'registration_date' not in default:
            default.update({
                'registration_date': False,
            })
        return super(account_invoice, self).copy(cr, uid, id, default, context)
