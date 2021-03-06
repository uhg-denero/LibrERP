# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 1.3 Thinkopen Solutions, Lda. All Rights Reserved
#    http://www.thinkopensolutions.com.
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version $revnoof the License, or
#    (at your option) any later version.51
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import fields, osv

class sale_validation_installer(osv.osv_memory):
    _name = 'sale.validation.installer'
    _inherit = 'res.config'
    _columns = {
        'limit_amount': fields.integer('Maximum Sale Amount', required=True, help="Maximum amount after which internal validation of sale is required."),
    }
    
    _defaults = {
        'limit_amount': 5000,
    }
    
    def execute(self, cr, uid, ids, context=None):
        data = self.read(cr, uid, ids, context=context)
        if not data:
            return {}
        amt = data[0]['limit_amount']
        data_pool = self.pool.get('ir.model.data')
        transition_obj = self.pool.get('workflow.transition')
        waiting = data_pool._get_id(cr, uid, 'tko_sale_validation', 'trans_draft_waiting_validation')
        waiting_id = data_pool.browse(cr, uid, waiting, context=context).res_id
        confirm = data_pool._get_id(cr, uid, 'tko_sale_validation', 'trans_draft_confirmed')
        confirm_id = data_pool.browse(cr, uid, confirm, context=context).res_id
        transition_obj.write(cr, uid, waiting_id, {'condition': 'amount_total>=%s' % (amt)})
        transition_obj.write(cr, uid, confirm_id, {'condition': 'amount_total<%s' % (amt)})
        return {}

sale_validation_installer()
