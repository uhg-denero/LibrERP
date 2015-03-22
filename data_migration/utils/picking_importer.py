# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2013-2015 Andrei Levin (andrei.levin at didotech.com)
#
#                          All Rights Reserved.
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
###############################################################################

import pooler
import threading
from tools.translate import _
from openerp.osv import orm
import math
import data_migration.settings as settings
from collections import namedtuple
from pprint import pprint
from utils import Utils
import datetime
from openerp.addons.core_extended.file_manipulation import import_sheet
import xlrd

import logging
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)

DEBUG = settings.DEBUG

if DEBUG:
    import pdb


class ImportFile(threading.Thread, Utils):
    def __init__(self, cr, uid, ids, context):
        # Inizializzazione superclasse
        threading.Thread.__init__(self)
        
        # Inizializzazione classe ImportPricelist
        self.uid = uid
        
        self.dbname = cr.dbname
        self.pool = pooler.get_pool(cr.dbname)
        self.product_obj = self.pool['product.product']
        self.picking_obj = self.pool['stock.picking']
        self.move_obj = self.pool['stock.move']

        # Necessario creare un nuovo cursor per il thread,
        # quello fornito dal metodo chiamante viene chiuso
        # alla fine del metodo e diventa inutilizzabile
        # all'interno del thread.
        self.cr = pooler.get_db(self.dbname).cursor()
        
        self.pickingImportID = ids[0]
        
        self.context = context
        self.error = []
        self.warning = []
        self.first_row = True
        
        # Contatori dei nuovi prodotti inseriti e dei prodotti aggiornati,
        # vengono utilizzati per compilare il rapporto alla terminazione
        # del processo di import
        self.uo_new = 0
        self.updated = 0
        self.problems = 0
        self.cache = {}
        self.cache_product = {}
    
    def run(self):
        # Recupera il record dal database
        self.filedata_obj = self.pool['picking.import']
        self.pickingImportRecord = self.filedata_obj.browse(self.cr, self.uid, self.pickingImportID, context=self.context)
        self.file_name = self.pickingImportRecord.file_name.split('\\')[-1]
        self.address_id = self.pickingImportRecord.address_id
        self.stock_journal_id = self.pickingImportRecord.stock_journal_id
        self.location_id = self.pickingImportRecord.location_id
        self.location_dest_id = self.pickingImportRecord.location_dest_id

        # ===================================================
        Config = getattr(settings, self.pickingImportRecord.format)

        self.HEADER = Config.HEADER_PICKING
        self.REQUIRED = Config.REQUIRED_PICKING
        
        # Default values
        self.PRODUCT_DEFAULTS = Config.PRODUCT_DEFAULTS
        
        if not len(self.HEADER) == len(Config.COLUMNS_PICKING.split(',')):
            pprint(zip(self.HEADER, Config.COLUMNS_PICKING.split(',')))
            raise orm.except_orm('Error: wrong configuration!', 'The length of columns and headers must be the same')
        
        self.RecordPicking = namedtuple('RecordPicking', Config.COLUMNS_PICKING)

        # ===================================================

        table, self.numberOfLines = import_sheet(self.file_name, self.pickingImportRecord.content_text)

        if DEBUG:
            # Importa il file
            self.process(self.cr, self.uid, table)
            
            # Genera il report sull'importazione
            self.notify_import_result(self.cr, self.uid, self.message_title, 'Importazione completata')
        else:
            # Elaborazione del file
            try:
                # Importa il listino
                self.process(self.cr, self.uid, table)
                
                # Genera il report sull'importazione
                self.notify_import_result(self.cr, self.uid, self.message_title, 'Importazione completata')
            except Exception as e:
                # Annulla le modifiche fatte
                self.cr.rollback()
                self.cr.commit()
                
                title = "Import failed"
                message = "Errore alla linea %s" % self.processed_lines + "\nDettaglio:\n\n" + str(e)
                
                if DEBUG:
                    ### Debug
                    _logger.debug(message)
                    pdb.set_trace()
                
                self.notify_import_result(self.cr, self.uid, title, message, error=True)

    def process(self, cr, uid, table):
        self.message_title = _("Importazione Picking")
        self.progressIndicator = 0
        
        notifyProgressStep = (self.numberOfLines / 100) + 1     # NB: divisione tra interi da sempre un numero intero!
                                                                # NB: il + 1 alla fine serve ad evitare divisioni per zero
        
        # Use counter of processed lines
        # If this line generate an error we will know the right Line Number
        for self.processed_lines, row_list in enumerate(table, start=1):

            if not self.import_row(cr, uid, row_list):
                self.problems += 1
                
            if (self.processed_lines % notifyProgressStep) == 0:
                cr.commit()
                completedQuota = float(self.processed_lines) / float(self.numberOfLines)
                completedPercentage = math.trunc(completedQuota * 100)
                self.progressIndicator = completedPercentage
                self.updateProgressIndicator(cr, uid, self.pickingImportID)

        # here is import all now need to

        for pick in self.cache:

            self.picking_obj.draft_validate(cr, uid, [self.cache[pick]])
            picking_date = self.picking_obj.read(cr, uid, [self.cache[pick]])[0]['date']
            move_ids = self.move_obj.search(cr, uid, [('picking_id', 'in', [self.cache[pick]])])
            self.move_obj.write(cr, uid, move_ids, {'date': picking_date})

        self.progressIndicator = 100
        self.updateProgressIndicator(cr, uid, self.pickingImportID)
        
        return True
    
    def import_row(self, cr, uid, row_list):

        if self.first_row:
            row_str_list = [self.simple_string(value) for value in row_list]
            for column in row_str_list:
                #print column
                if column in self.HEADER:
                    _logger.info('Riga {0}: Trovato Header'.format(self.processed_lines))
                    return True
            self.first_row = False

        if not len(row_list) == len(self.HEADER):
            row_str_list = [self.simple_string(value) for value in row_list]
            if DEBUG:
                if len(row_list) > len(self.HEADER):
                    pprint(zip(self.HEADER, row_str_list[:len(self.HEADER)]))
                else:
                    pprint(zip(self.HEADER[:len(row_list)], row_str_list))
            
            error = u"""Row {row}: Row_list is {row_len} long. We expect it to be {expected} long, with this columns:
                {keys}
                Instead of this we got this:
                {header}
                """.format(row=self.processed_lines, row_len=len(row_list), expected=len(self.HEADER), keys=self.HEADER, header=', '.join(row_str_list))

            _logger.error(str(row_list))
            _logger.error(error)
            self.error.append(error)
            return False
        elif DEBUG:
            # pprint(row_list)
            row_str_list = [self.simple_string(value) for value in row_list]
            pprint(zip(self.HEADER, row_str_list))

        # Sometime value is only numeric and we don't want string to be treated as Float
        record = self.RecordPicking._make([self.simple_string(value) for value in row_list])
        for field in self.REQUIRED:
            if not getattr(record, field):
                error = "Riga {0}: Manca il valore della {1}. La riga viene ignorata.".format(self.processed_lines, field)
                _logger.debug(error)
                self.error.append(error)
                return False

        date = datetime.datetime(*xlrd.xldate_as_tuple(float(record.date), 0)).strftime("%d/%m/%Y %H:%M:%S")

        origin = record.origin.split('.')[0]
        if self.cache.get(origin):
            picking_id = self.cache[origin]
            _logger.info(u'Picking {0} already processed in cache'.format(origin))
            #    picking_id = picking_id[0]
        elif self.picking_obj.search(cr, uid, [('origin', '=', origin), ('state', '=', 'draft')]):
            picking_id = self.picking_obj.search(cr, uid, [('origin', '=', origin), ('state', '=', 'draft')])[0]
            self.cache[origin] = picking_id
            _logger.warning(u'Picking {0} already exist'.format(origin))
        else:
            # i need to create stock.picking
            # so need to create one
            vals_picking = {
                'address_id': self.address_id.id,
                'origin': origin,
                'type': 'internal',
                'move_type': 'one', # TODO must be parametric by location
                'invoice_state': 'none',
                'auto_picking': True,
                'stock_journal_id': self.stock_journal_id.id,
                'min_date': date,
                'date': date,
            }
            picking_id = self.picking_obj.create(cr, uid, vals_picking)
            self.cache[origin] = picking_id
            _logger.info(u'Create Picking {0} '.format(origin))
        
        vals_move = {}
        product_id = False
        if hasattr(record, 'product') and record.product:
            product = record.product
            if self.cache_product.get(product):
                product_id = self.cache_product[product]
                _logger.warning(u'Product {0} already processed in cache'.format(product))
            else:
                product_ids = self.product_obj.search(cr, uid, [('default_code', '=', product)])
                if not product_ids:
                    product_ids = self.product_obj.search(cr, uid, [('name', '=', product)])
                    if not product_ids:
                        product_ids = self.product_obj.search(cr, uid, [('ean13', '=', product)])
                if product_ids:
                    product_id = product_ids[0]
                    self.cache_product[product] = product_id

        if hasattr(record, 'qty') and record.qty:
            vals_move['product_qty'] = float(record.qty)

        if product_id:
            vals_move['name'] = origin
            vals_move['picking_id'] = picking_id
            vals_move['product_id'] = product_id
            vals_move['product_uom'] = self.product_obj.browse(cr, uid, product_id, context=None).uom_id.id
            vals_move['location_id'] = self.location_id.id
            vals_move['location_dest_id'] = self.location_dest_id.id
            vals_move['date'] = date
            vals_move['date_expected'] = date

            _logger.info(u'Row {row}: Adding product {product} to picking {picking}'.format(row=self.processed_lines, product=record.product, picking=origin))

            self.move_obj.create(cr, uid, vals_move)
            self.uo_new += 1
        else:
            _logger.warning(u'Row {row}: Not Find {product}'.format(row=self.processed_lines, product=record.product))

        return product_id
