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

class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    @api.model
    def _get_statement_line(self, st_line):
        res = super(AccountReconciliation, self)._get_statement_line(st_line)
        if (not st_line.partner_id) and st_line.transaction_type:
            config = self.env['account.bank.transaction.type'].search([
                ('name','=',st_line.transaction_type)
            ], limit=1)
            if config:
                res['open_balance_account_id'] = config.account_id.id
        return res


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: