# -*- encoding: utf-8 -*-
##############################################################################
#
#    Part of Odoo.
#    Copyright (C) 2019 Allegro IT (<http://www.allegro.lv/>)
#                       E-mail: <info@allegro.lv>
#                       Address: <Vienibas gatve 109 LV-1058 Riga Latvia>
#                       Phone: +371 67289467
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

{
    'name': 'Latvia - Account Bank Statement Import',
    'version': '1.1',
    'category': 'Accounting',
    'summary': 'Accounting configuration for Latvia',
    'description': """
Latvian Localization for Bank Statement data import
=====================================

Bank Statement data import in the following formats:
* ISO 20022;
* FiDAViSta
""",
    'author': 'Allegro IT',
    'website': 'http://www.allegro.lv',
    'images': [],
    'depends': [
        'account_bank_statement_import'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_bank_transaction_type_view.xml',
        'views/account_bank_statement_view.xml',
        'wizard/account_bank_statement_import_view.xml',
        'data/account_bank_transaction_type_data.xml'
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'qweb': [],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
