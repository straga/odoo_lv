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

from odoo import api, fields, models, _

class AccountJournal(models.Model):
    _inherit = "account.journal"

    def __get_bank_statements_available_sources(self):
        res = super(AccountJournal, self).__get_bank_statements_available_sources()
        add_manual = True
        add_import = True
        for r in res:
            if r[0] == 'manual':
                add_manual = False
            if r[0] == 'file_import':
                add_import = False
        if add_manual:
            res.append(('manual', _('Record Manually')))
        if add_import:
            res.append(('file_import', _('File Import')))
        return res


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: