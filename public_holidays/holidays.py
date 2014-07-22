# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#
#    Copyright (C) 2014 Didotech srl (<http://www.didotech.com>).
#
#                       All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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

from openerp.osv import orm, fields
from tools.translate import _


class PublicHolidays(orm.Model):
    _name = 'public.holidays'
    _description = 'The list of public holidays'
    
    _columns = {
        'holiday_date': fields.date('Date', required=True),
        'description': fields.text('Description', required=True),
        'country': fields.many2one('res.country', 'Country', required=True)
    }

    _order = 'holiday_date ASC'
    
    _sql_constraints = [
        ('date_country_uniq', 'unique(holiday_date, country)', _('The date of the holiday must be unique (for the country)!'))
    ]