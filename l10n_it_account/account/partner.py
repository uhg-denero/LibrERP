# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2010-2013 Associazione OpenERP Italia
#    (<http://www.openerp-italia.org>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, orm
import datetime


class res_partner(orm.Model):
    _inherit = 'res.partner'

    def check_fiscalcode(self, cr, uid, ids, context={}):
        
        for partner in self.browse(cr, uid, ids):
            if not partner.fiscalcode:
                return True
            if len(partner.fiscalcode) != 16:
                return False

        return True

    def _set_fiscalcode(self, cr, uid, ids, field_name, field_value, arg, context):
        self.write(cr, uid, ids, {'fiscalcode': field_value})
        return True

    def _get_fiscalcode(self, cr, uid, ids, field_name, arg, context):
        if not ids:
            return False

        result = {}

        partners = self.browse(cr, uid, ids, context=context)
        for partner in partners:
            result[partner.id] = partner.fiscalcode

        return result
        
    _columns = {
        'pec': fields.related('address', 'pec', type='char', size=64, string='PEC'),
        'cf': fields.function(_get_fiscalcode, fnct_inv=_set_fiscalcode, string='Codice Fiscale', type='char', method=True),
        'individual': fields.boolean('Persona Fisica'),
        'fiscalcode': fields.char('Fiscal Code', size=16, help="Italian Fiscal Code"),
        'fiscalcode_surname': fields.char('Surname', size=64),
        'fiscalcode_firstname': fields.char('First name', size=64),
        'birth_date': fields.date('Date of birth'),
        'birth_city': fields.many2one('res.city', 'City of birth'),
        'sex': fields.selection([
            ('M', 'Male'),
            ('F', 'Female'),
        ], "Sex"),
        'property_payment_term_payable': fields.property(
            'account.payment.term',
            type='many2one',
            relation='account.payment.term',
            string ='Payment Term',
            view_load=True,
            help="This payment term will be used instead of the default one for the current partner for supplier moves."),
        'ref_companies': fields.one2many('res.company', 'partner_id',
            'Companies that refers to partner'),
        'last_reconciliation_date': fields.datetime(
            'Latest Reconciliation Date', help='Date on which the partner accounting entries were reconciled last time')
    }
    #_constraints = [(check_fiscalcode, "The fiscal code doesn't seem to be correct.", ["fiscalcode"])]

    _sql_constraints = [
        ('vat_uniq', 'unique (vat)', ('Error! Specified VAT Number already exists for any other registered partner.'))
    ]
     
    def _codicefiscale(self, cognome, nome, giornonascita, mesenascita, annonascita,
                       sesso, cittanascita):

        MESI = 'ABCDEHLMPRST'
        CONSONANTI = 'BCDFGHJKLMNPQRSTVWXYZ'
        VOCALI = 'AEIOU'
        LETTERE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        REGOLECONTROLLO = {
            'A': (0,   1), 'B': (1,   0), 'C': (2,   5), 'D': (3,   7), 'E': (4,   9),
            'F': (5,  13), 'G': (6,  15), 'H': (7,  17), 'I': (8,  19), 'J': (9,  21),
            'K': (10,  2), 'L': (11,  4), 'M': (12, 18), 'N': (13, 20), 'O': (14, 11),
            'P': (15,  3), 'Q': (16,  6), 'R': (17,  8), 'S': (18, 12), 'T': (19, 14),
            'U': (20, 16), 'V': (21, 10), 'W': (22, 22), 'X': (23, 25), 'Y': (24, 24),
            'Z': (25, 23),
            '0': (0,   1), '1': (1,   0), '2': (2,   5), '3': (3,   7), '4': (4,   9),
            '5': (5,  13), '6': (6,  15), '7': (7,  17), '8': (8,  19), '9': (9,  21)
        }
        
        ###
        # Funzioni
        ##
        def _surname(stringa):
            """Ricava, da stringa, 3 lettere in base alla convenzione dei CF."""
            cons = [c for c in stringa if c in CONSONANTI]
            voc = [c for c in stringa if c in VOCALI]
            chars = cons + voc
            if len(chars) < 3:
                chars += ['X', 'X']
            return chars[:3]
         
        def _name(stringa):
            """Ricava, da stringa, 3 lettere in base alla convenzione dei CF."""
            cons = [c for c in stringa if c in CONSONANTI]
            voc = [c for c in stringa if c in VOCALI]
            if len(cons) > 3:
                cons = [cons[0]] + [cons[2]] + [cons[3]]
            chars = cons + voc
            if len(chars) < 3:
                chars += ['X', 'X']
            return chars[:3]
         
        def _datan(giorno, mese, anno, sesso):
            """Restituisce il campo data del CF."""
            chars = (list(anno[-2:]) + [MESI[int(mese) - 1]])
            gn = int(giorno)
            if sesso == 'F':
                gn += 40
            chars += list("%02d" % gn)
            return chars
         
        def _codicecontrollo(c):
            """Restituisce il codice di controllo, l'ultimo carattere del CF."""
            sommone = 0
            for i, car in enumerate(c):
                j = 1 - i % 2
                sommone += REGOLECONTROLLO[car][j]
            resto = sommone % 26
            return [LETTERE[resto]]

        """Restituisce il CF costruito sulla base degli argomenti."""
        nome = nome.upper()
        cognome = cognome.upper()
        sesso = sesso.upper()
        cittanascita = cittanascita.upper()
        chars = (_surname(cognome) +
                 _name(nome) +
                 _datan(giornonascita, mesenascita, annonascita, sesso) +
                 list(cittanascita))
        chars += _codicecontrollo(chars)
        return ''.join(chars)
     
    def compute_fiscal_code(self, cr, uid, ids, context):
        partners = self.browse(cr, uid, ids, context)
        for partner in partners:
            if not partner.fiscalcode_surname or not partner.fiscalcode_firstname or not partner.birth_date or not partner.birth_city or not partner.sex:
                raise orm.except_orm('Error', 'One or more fields are missing')
            birth_date = datetime.datetime.strptime(partner.birth_date, "%Y-%m-%d")
            CF = self._codicefiscale(partner.fiscalcode_surname, partner.fiscalcode_firstname, str(birth_date.day),
                                     str(birth_date.month), str(birth_date.year), partner.sex,
                                     partner.birth_city.cadaster_code)
            self.write(cr, uid, partner.id, {'fiscalcode': CF})
        return True
    
    def action_select_fiscal_position(self, cr, uid, ids, context=None):
        if not ids:
            return
        position_id = self.pool.get("select.fiscal.position").create(cr, uid, {'partner_id': ids[0]}, context)
        return {
            'name': "Seleziona la Posizione Fiscale",
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': "select.fiscal.position",
            'res_id': position_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict({}),
        }


class res_partner_address(orm.Model):
    _inherit = 'res.partner.address'
    _columns = {
        'pec': fields.char('PEC', size=64),
    }

