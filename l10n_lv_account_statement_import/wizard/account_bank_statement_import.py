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
import base64
import ast
from xml.dom.minidom import getDOMImplementation, parseString
from datetime import datetime
from openerp.exceptions import UserError
from dateutil.parser import parse

class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'


    format = fields.Selection([('iso20022', 'ISO 20022'), ('fidavista','FiDAViSta')], string='Format', default='iso20022')
    flag = fields.Boolean('Continue Anyway', help='If checked, continues without comparing balances.', default=False)
    wrong_balance = fields.Boolean('Wrong Balance', default=False)
    statement_info = fields.Html(string='Statement Info', readonly=1)


    def find_bank_account(self, account_number):
        bank_acc = False
        if account_number:
            bank_obj = self.env['res.partner.bank']
            bank_acc = bank_obj.search([('acc_number','=',account_number)], limit=1)
            if not len(bank_acc):
                account_number_list = list(account_number)
                account_number_list.insert(4,' ')
                account_number_list.insert(9,' ')
                account_number_list.insert(14,' ')
                account_number_list.insert(19,' ')
                account_number_list.insert(24,' ')
                account_number_2 = "".join(account_number_list)
                bank_acc = bank_obj.search([('acc_number','=',account_number_2)], limit=1)
                if not len(bank_acc):
                    bank_acc = False
        return bank_acc


    @api.onchange('format', 'data_file')
    def _onchange_data_file(self):
        if self.data_file and self.format in ['iso20022', 'fidavista']:
            # decoding and encoding for string parsing; parseString() method:
            stringAsByte = "b'%s'" % self.data_file
            record = str(base64.decodestring(ast.literal_eval(stringAsByte)), 'iso8859-4', 'strict').encode('iso8859-4','strict')
            dom = parseString(record)

            account_number = ''
            statement_name = ''
            balance_start = 0.0
            currency_name = False

            bank_obj = self.env['res.partner.bank']
            statement_obj = self.env['account.bank.statement']
            journal_obj = self.env['account.journal']
            cur_obj = self.env['res.currency']
            if not self.format:
                if dom.documentElement.tagName == 'FIDAVISTA':
                    self.format = 'fidavista'
                if dom.documentElement.tagName == 'Document':
                    self.format = 'iso20022'
            if self.format == 'iso20022':
                statements = dom.getElementsByTagName('Stmt') or []
                if not statements:
                    statements = dom.getElementsByTagName('Rpt') or []
                account_tag = statements[0].getElementsByTagName('Acct')[0]
                account_number = account_tag.getElementsByTagName('IBAN')[0].toxml().replace('<IBAN>','').replace('</IBAN>','')
                statement_name = account_number
                ft_date_tag = statements[0].getElementsByTagName('FrToDt')
                if ft_date_tag:
                    start_datetime = ft_date_tag[0].getElementsByTagName('FrDtTm')[0].toxml().replace('<FrDtTm>','').replace('</FrDtTm>','')
                    end_datetime = ft_date_tag[0].getElementsByTagName('ToDtTm')[0].toxml().replace('<ToDtTm>','').replace('</ToDtTm>','')
                    start_date = datetime.strftime(parse(start_datetime).date(), '%Y-%m-%d')
                    end_date = datetime.strftime(parse(end_datetime).date(), '%Y-%m-%d')
                    statement_name += (' ' + start_date + ':' + end_date)
                balances = statements[0].getElementsByTagName('Bal')
                for b in balances:
                    balance_amount = 0.0
                    amount_tags = b.getElementsByTagName('Amt')
                    cl_amount_tag = False
                    credit_line = b.getElementsByTagName('CdtLine')
                    if credit_line:
                        cl_amount_tag = credit_line[0].getElementsByTagName('Amt')
                        cl_amount_tag = cl_amount_tag and cl_amount_tag[0] or False
                    for amt in amount_tags:
                        if amt != cl_amount_tag:
                            balance_amount = float(amt.firstChild.nodeValue)
                    cd_ind = b.getElementsByTagName('CdtDbtInd')[0].toxml().replace('<CdtDbtInd>','').replace('</CdtDbtInd>','')
                    if cd_ind == 'DBIT':
                        balance_amount *= (-1)
                    btype = b.getElementsByTagName('Tp')[0]
                    type_code = btype.getElementsByTagName('CdOrPrtry')[0].getElementsByTagName('Cd')[0].toxml().replace('<Cd>','').replace('</Cd>','')
                    found = False
                    if type_code == 'OPBD':
                        balance_start = balance_amount
                        found = True
                    if not found:
                        bsubtype = btype.getElementsByTagName('SubType')
                        if bsubtype:
                            subtype_code = bsubtype[0].getElementsByTagName('Cd')[0].toxml().replace('<Cd>','').replace('</Cd>','')
                            if subtype_code == 'OPBD':
                                balance_start = balance_amount
                cur_tag = account_tag.getElementsByTagName('Ccy')
                if cur_tag:
                    currency_name = cur_tag[0].toxml().replace('<Ccy>','').replace('</Ccy>','')

            if self.format == 'fidavista':
                start_date = dom.getElementsByTagName('StartDate')[0].toxml().replace('<StartDate>','').replace('</StartDate>','')
                end_date = dom.getElementsByTagName('EndDate')[0].toxml().replace('<EndDate>','').replace('</EndDate>','')
                accountset = dom.getElementsByTagName('AccountSet')[0]
                account_number = accountset.getElementsByTagName('AccNo')[0].toxml().replace('<AccNo>','').replace('</AccNo>','')
                statement_name = account_number + ' ' + start_date+ ':' + end_date
                balance_start = accountset.getElementsByTagName('OpenBal')[0].toxml().replace('<OpenBal>','').replace('</OpenBal>','')
                currency_name = accountset.getElementsByTagName('Ccy')[0].toxml().replace('<Ccy>','').replace('</Ccy>','')

            wrong_balance = False
            imported = {}
            bank_account = self.find_bank_account(account_number)
            if bank_account:
                journals = journal_obj.search([('bank_account_id','=',bank_account.id)])
                bank_statement = statement_obj.search([('journal_id', 'in', [j.id for j in journals])], order='date desc', limit=1)
                if bank_statement:
                    if bank_statement.balance_end_real != float(balance_start):
                        wrong_balance = True
                    imported.update({
                        'name': bank_statement.name,
                        'balance_end': bank_statement.balance_end_real,
                        'currency': bank_statement.currency_id
                    })

            currency = False
            if currency_name:
                currency = cur_obj.search([('name','=',currency_name)], limit=1)
                if not currency:
                    currency = cur_obj.search([('name','=',currency_name), ('active','=',False)], limit=1)
            importing = {
                'name': statement_name,
                'balance_start': float(balance_start),
                'currency': currency
            }

            info = """<table><tr>"""
            if imported:
                info += """<td style="padding:2px; border:1px solid black; font-weight:bold;">%s</td><td style="padding:2px; border:1px solid black; font-weight:bold;">%s</td>""" % (_('Last statement for selected account'), _('Ending Balance'))
            info += """<td style="padding:2px; border:1px solid black; font-weight:bold;">%s</td><td style="padding:2px; border:1px solid black; font-weight:bold;">%s</td>""" % (_('Statement to import'), _('Starting Balance'))
            info += "</tr><tr>"
            if imported:
                info += """<td style="padding:2px; border:1px solid black;">%s</td><td style="padding:2px; border:1px solid black; text-align:right; color:%s;">%.02f %s</td>""" % (imported['name'], wrong_balance and 'red' or 'black', imported['balance_end'], imported['currency'] and (imported['currency'].symbol or imported['currency'].name) or '')
            info += """<td style="padding:2px; border:1px solid black;">%s</td><td style="padding:2px; border:1px solid black; text-align:right; color:%s;">%.02f %s</td>""" % (importing['name'], wrong_balance and 'red' or 'black', importing['balance_start'], importing['currency'] and (importing['currency'].symbol or importing['currency'].name) or '')
            info += """</tr></table>"""
            if wrong_balance:
                info += """<p style="color:red; font-weight:bold;">%s</p><p style="color:red;">%s</p>""" % (_('Balances do not match!'), _('The Ending Balance of the last Bank Statement (by date) imported for the Bank Account is not equal to the Starting Balance of this document.'))

            self.statement_info = info
            self.wrong_balance = wrong_balance


    def check_balances(self, balance_start, account_number):
        journal_obj = self.env['account.journal']
        bs_obj = self.env['account.bank.statement']
        test_bnk_acc = self.find_bank_account(account_number)
        if test_bnk_acc:
            journals = journal_obj.search([('bank_account_id','=',test_bnk_acc.id)])
            test_bs = bs_obj.search([('journal_id','in',[j.id for j in journals])], order='date desc', limit=1)
            if test_bs and test_bs.balance_end_real != float(balance_start) and self.flag == False:
                raise UserError(_("The Ending Balance of the last Bank Statement (by date) imported for the Bank Account '%s' is not equal to the Starting Balance of this document. If this is OK with you, check the 'Continue Anyway' box and try to import again.") %(account_number))


    def iso20022_parsing(self, data_file):
        record = str(data_file, 'iso8859-4', 'strict').encode('iso8859-4','strict')
        dom = parseString(record)

        statements = dom.getElementsByTagName('Stmt') or []
        if not statements:
            statements = dom.getElementsByTagName('Rpt') or []

        cur_obj = self.env['res.currency']
        ba_obj = self.env['res.partner.bank']
        partner_obj = self.env['res.partner']
#        config_obj = self.env['account.bank.transaction.type']

        currency_code = False
        account_number = False
        stmts_vals = []
        for statement in statements:
            # getting start values:
            # Acct/Id/IBAN
            # Acct/Ccy
            # FrToDt/FrDtTm
            # FrToDt/ToDtTm
            account_tag = statement.getElementsByTagName('Acct')[0]
            account_number = account_tag.getElementsByTagName('IBAN')[0].toxml().replace('<IBAN>','').replace('</IBAN>','')
            name = account_number
            cur_tag = account_tag.getElementsByTagName('Ccy')
            if cur_tag:
                currency_code = cur_tag[0].toxml().replace('<Ccy>','').replace('</Ccy>','')
            start_date = False
            end_date = False
            ft_date_tag = statement.getElementsByTagName('FrToDt')
            if ft_date_tag:
                start_datetime = ft_date_tag[0].getElementsByTagName('FrDtTm')[0].toxml().replace('<FrDtTm>','').replace('</FrDtTm>','')
                end_datetime = ft_date_tag[0].getElementsByTagName('ToDtTm')[0].toxml().replace('<ToDtTm>','').replace('</ToDtTm>','')
                start_date = datetime.strftime(parse(start_datetime).date(), '%Y-%m-%d')
                end_date = datetime.strftime(parse(end_datetime).date(), '%Y-%m-%d')
                name += (' ' + start_date + ':' + end_date)

            # getting balances:
            # Bal/Amt
            # Bal/CdtDbtInd
            # Bal/Tp/CdOrPrtry/Cd or Bal/Tp/SubType/Cd
            balance_start = 0.0
            balance_end_real = 0.0
            balances = statement.getElementsByTagName('Bal')
            for b in balances:
                balance_amount = 0.0
                amount_tags = b.getElementsByTagName('Amt')
                cl_amount_tag = False
                credit_line = b.getElementsByTagName('CdtLine')
                if credit_line:
                    cl_amount_tag = credit_line[0].getElementsByTagName('Amt')
                    cl_amount_tag = cl_amount_tag and cl_amount_tag[0] or False
                for amt in amount_tags:
                    if amt != cl_amount_tag:
                        balance_amount = float(amt.firstChild.nodeValue)
                cd_ind = b.getElementsByTagName('CdtDbtInd')[0].toxml().replace('<CdtDbtInd>','').replace('</CdtDbtInd>','')
                if cd_ind == 'DBIT':
                    balance_amount *= (-1)
                btype = b.getElementsByTagName('Tp')[0]
                type_code = btype.getElementsByTagName('CdOrPrtry')[0].getElementsByTagName('Cd')[0].toxml().replace('<Cd>','').replace('</Cd>','')
                found = False
                if type_code == 'OPBD':
                    balance_start = balance_amount
                    found = True
                if type_code == 'CLBD':
                    balance_end_real = balance_amount
                    found = True
                if not found:
                    bsubtype = btype.getElementsByTagName('SubType')
                    if bsubtype:
                        subtype_code = bsubtype[0].getElementsByTagName('Cd')[0].toxml().replace('<Cd>','').replace('</Cd>','')
                        if subtype_code == 'OPBD':
                            balance_start = balance_amount
                        if subtype_code == 'CLBD':
                            balance_end_real = balance_amount

            # checking balances:
            self.check_balances(balance_start, account_number)

            svals = {
                'name': name,
                'date': end_date,
                'balance_start': balance_start,
                'balance_end_real': balance_end_real,
                'transactions': []
            }

            # getting line data:
            # Ntry
            entries = statement.getElementsByTagName('Ntry')
            for entry in entries:
                # getting date:
                # BookgDt or ValDt
                line_date = False
                date_tag = entry.getElementsByTagName('BookgDt')
                if not date_tag:
                    date_tag = entry.getElementsByTagName('ValDt')
                if date_tag:
                    line_date = date_tag[0].getElementsByTagName('Dt')[0].toxml().replace('<Dt>','').replace('</Dt>','')

                # getting reference and unique id:
                # NtryDtls/TxDtls/RmtInf/Strd/CdtrRefInf/Ref or NtryDtls/TxDtls/Refs/Reference or NtryRef or AcctSvcrRef
                # AcctSvcrRef
                line_ref = False
                unique_import_id = False
                ref_tag = entry.getElementsByTagName('NtryRef')
                if ref_tag:
                    line_ref = ref_tag[0].toxml().replace('<NtryRef>','').replace('</NtryRef>','')
                refs_uref_tag = False
                refs_tag = entry.getElementsByTagName('Refs')
                if refs_tag:
                    refs_uref_tag = refs_tag[0].getElementsByTagName('AcctSvcrRef')
                    refs_uref_tag = refs_uref_tag and refs_uref_tag[0] or False
                    refs_ref_tag = refs_tag[0].getElementsByTagName('Reference')
                    if refs_ref_tag and (not line_ref):
                        line_ref = refs_ref_tag[0].toxml().replace('<Reference>','').replace('</Reference>','')
                uref_tags = entry.getElementsByTagName('AcctSvcrRef')
                for urt in uref_tags:
                    if urt != refs_uref_tag:
                        unique_import_id = urt.toxml().replace('<AcctSvcrRef>','').replace('</AcctSvcrRef>','')
                if (not unique_import_id) and refs_uref_tag:
                    unique_import_id = refs_uref_tag.toxml().replace('<AcctSvcrRef>','').replace('</AcctSvcrRef>','')
                cdtr_refs_tag = entry.getElementsByTagName('CdtrRefInf')
                if cdtr_refs_tag:
                    cref_tag = cdtr_refs_tag[0].getElementsByTagName('Ref')
                    if cref_tag:
                        line_ref = cref_tag[0].toxml().replace('<Ref>','').replace('</Ref>','')
                if (not line_ref) and unique_import_id:
                    line_ref = unique_import_id

                # getting transaction type:
                # BkTxCd/Domn/Fmly/SubFmlyCd
                type_code = False
                tx_dtls_btc_tag = False
                tx_dtls_tag = entry.getElementsByTagName('TxDtls')
                if tx_dtls_tag:
                    tx_dtls_btc_tag = tx_dtls_tag[0].getElementsByTagName('BkTxCd')
                    tx_dtls_btc_tag = tx_dtls_btc_tag and tx_dtls_btc_tag[0] or False
                btc_tags = entry.getElementsByTagName('BkTxCd')
                for btc in btc_tags:
                    if btc != tx_dtls_btc_tag:
                        type_code_tag = btc.getElementsByTagName('SubFmlyCd')
                        if type_code_tag:
                            type_code = type_code_tag[0].toxml().replace('<SubFmlyCd>','').replace('</SubFmlyCd>','')

                # getting debit or credit info:
                # CdtDbtInd
                line_cd_ind = False
                entr_details_tag = entry.getElementsByTagName('NtryDtls')
                edt_cd_tgs = []
                if entr_details_tag:
                    edt_cd_tags = entr_details_tag[0].getElementsByTagName('CdtDbtInd')
                    edt_cd_tgs = [ecdt for ecdt in edt_cd_tags]
                entry_cd_tags = entry.getElementsByTagName('CdtDbtInd')
                for ecd in entry_cd_tags:
                    if ecd not in edt_cd_tgs:
                        line_cd_ind = ecd.toxml().replace('<CdtDbtInd>','').replace('</CdtDbtInd>','')

                # getting amount and currency:
                # NtryDtls/TxDtls/AmtDtls/TxAmt/Amt or Amt
                # NtryDtls/TxDtls/AmtDtls/InstdAmt/Amt
                line_amount = 0.0
                line_amount_cur = 0.0
                line_cur = False
                amt_tag = False
                amt_details_tag = entry.getElementsByTagName('AmtDtls')
                if amt_details_tag:
                    inst_amt_tag = amt_details_tag[0].getElementsByTagName('InstdAmt')
                    if inst_amt_tag:
                        amt_cur_tag = inst_amt_tag[0].getElementsByTagName('Amt')[0]
                        line_amount_cur = float(amt_cur_tag.firstChild.nodeValue)
                        if line_cd_ind == 'DBIT':
                            line_amount_cur *= (-1)
                        line_cur_code = amt_cur_tag.attributes['Ccy'].value
                        if line_cur_code != currency_code:
                            line_cur = cur_obj.search([('name','=',line_cur_code)], limit=1)
                    trans_amt_tag = amt_details_tag[0].getElementsByTagName('TxAmt')
                    if trans_amt_tag:
                        amt_tag = trans_amt_tag[0].getElementsByTagName('Amt')
                if (not amt_details_tag) or (amt_details_tag and (not amt_tag)):
                    amt_tag = entry.getElementsByTagName('Amt')
                if amt_tag:
                    line_amount = float(amt_tag[0].firstChild.nodeValue)
                    if line_cd_ind == 'DBIT':
                        line_amount *= (-1)

                # getting bank account and bank data:
                # NtryDtls/TxDtls/RltdPties/DbtrAcct/Id/IBAN incoming payment (+)
                # NtryDtls/TxDtls/RltdPties/CdtrAcct/Id/IBAN outgoing payment (-)
                partner_bank_account = False
                bank_account = False
                bank_name = False
                bank_bic = False
                entry_ba_tag = False
                entry_b_tag = False
                if line_cd_ind == 'CRDT':
                    entry_ba_tag = entry.getElementsByTagName('DbtrAcct')
                    entry_b_tag = entry.getElementsByTagName('DbtrAgt')
                if line_cd_ind == 'DBIT':
                    entry_ba_tag = entry.getElementsByTagName('CdtrAcct')
                    entry_b_tag = entry.getElementsByTagName('CdtrAgt')
                if entry_ba_tag:
                    partner_bank_account = entry_ba_tag[0].getElementsByTagName('IBAN')[0].toxml().replace('<IBAN>','').replace('</IBAN>','')
                    bank_account = ba_obj.search([('acc_number','=',partner_bank_account)], limit=1)
                    if (not bank_account) and partner_bank_account:
                        partner_bank_account_list = list(partner_bank_account)
                        partner_bank_account_list.insert(4,' ')
                        partner_bank_account_list.insert(9,' ')
                        partner_bank_account_list.insert(14,' ')
                        partner_bank_account_list.insert(19,' ')
                        partner_bank_account_list.insert(24,' ')
                        partner_bank_account_2 = "".join(partner_bank_account_list)
                        bank_account = ba_obj.search([('acc_number','=',partner_bank_account_2)], limit=1)
                if entry_b_tag:
                    entry_b_name_tag = entry_b_tag[0].getElementsByTagName('Name')
                    if entry_b_name_tag:
                        bank_name = entry_b_name_tag[0].toxml().replace('<Name>','').replace('</Name>','')
                    entry_b_bic_tag = entry_b_tag[0].getElementsByTagName('BIC')
                    if entry_b_bic_tag:
                        bank_bic = entry_b_bic_tag[0].toxml().replace('<BIC>','').replace('</BIC>','')

                # getting name:
                # NtryDtls/TxDtls/Purp/Prtry (+)
                # NtryDtls/TxDtls/RmtInf/Ustrd (+/-)
                line_name = False
                if line_cd_ind == 'CRDT':
                    purp_tag = entry.getElementsByTagName('Purp')
                    if purp_tag:
                        line_name = purp_tag[0].getElementsByTagName('Prtry')[0].toxml().replace('<Prtry>','').replace('</Prtry>','')
                if line_cd_ind == 'DBIT' or (line_cd_ind == 'CRDT' and (not line_name)):
                    rmt_inf_tag = entry.getElementsByTagName('RmtInf')
                    if rmt_inf_tag:
                        ustruct_tags = rmt_inf_tag[0].getElementsByTagName('Ustrd')
                        uc = 0
                        for ustruct_tag in ustruct_tags:
                            uc += 1
                            utxt = ustruct_tag.toxml().replace('<Ustrd>','').replace('</Ustrd>','')
                            if uc == 1:
                                line_name = utxt
                            else:
                                line_name += ('\n' + utxt)
                if not line_name:
                    line_name = type_code

                # getting partner data:
                # NtryDtls/TxDtls/RltdPties/Dbtr (+) Nm and Id/OrgId/Othr/Id or Id/PrvtId/Othr/Id
                # NtryDtls/TxDtls/RltdPties/Cdtr (-) Nm and Id/OrgId/Othr/Id or Id/PrvtId/Othr/Id
                partner = False
                if bank_account:
                    partner = bank_account.partner_id
                partner_name = False
                partner_reg_id = False
                partner_tag = False
                if line_cd_ind == 'CRDT':
                    partner_tag = entry.getElementsByTagName('Dbtr')
                if line_cd_ind == 'DBIT':
                    partner_tag = entry.getElementsByTagName('Cdtr')
                if partner_tag:
                    partner_name_tag = partner_tag[0].getElementsByTagName('Nm')
                    if partner_name_tag:
                        partner_name = partner_name_tag[0].toxml().replace('<Nm>','').replace('</Nm>','')
                    partner_reg_tag = partner_tag[0].getElementsByTagName('OrgId')
                    if not partner_reg_tag:
                        partner_reg_tag = partner_tag[0].getElementsByTagName('PrvtId')
                    if partner_reg_tag:
                        partner_reg_id_tag = partner_reg_tag[0].getElementsByTagName('Id')
                        if partner_reg_id_tag:
                            partner_reg_id = partner_reg_id_tag[0].toxml().replace('<Id>','').replace('</Id>','')
                    if (not partner_name) and partner_reg_id:
                        partner_name = partner_reg_id
                if (not bank_account) and (partner_reg_id):
                    partners = partner_obj.search([('vat','ilike',partner_reg_id)])
                    if len([p.id for p in partners]) == 1:
                        partner = partners

                # getting account:
#                account_id = False
#                if partner:
#                    if line_cd_ind == 'CRDT':
#                        account_id = partner.property_account_receivable_id.id
#                    if line_cd_ind == 'DBIT':
#                       account_id = partner.property_account_payable_id.id
#                if (not partner) and type_code:
#                    config = config_obj.search([('name','=',type_code)], limit=1)
#                    if config:
#                        account_id = config.account_id.id

                svals['transactions'].append({
                    'unique_import_id': unique_import_id,
                    'date': line_date,
                    'name': line_name,
                    'ref': line_ref,
                    'amount': line_amount,
                    'amount_currency': line_amount_cur,
                    'currency_id': line_cur and line_cur.id or False,
                    'partner_name': partner_name,
                    'account_number': partner_bank_account,
                    'partner_bank_account': partner_bank_account,
                    'partner_reg_id': partner_reg_id,
                    'partner_id': partner and partner.id or False,
                    'transaction_type': type_code,
                    'bank_account_id': bank_account and bank_account.id or False,
#                    'account_id': account_id,
                    'bank_name': bank_name,
                    'bank_bic': bank_bic
                })

            stmts_vals.append(svals)

        return currency_code, account_number, stmts_vals


    def fidavista_parsing(self, data_file):
        # decoding and encoding for string parsing; parseString() method:
        record = str(data_file, 'iso8859-4', 'strict').encode('iso8859-4','strict')
        dom = parseString(record)

        cur_obj = self.env['res.currency']
        bank_obj = self.env['res.partner.bank']

        # getting start values:
        currency_code = False
        account_number = False
        stmts_vals = []
        start_date = dom.getElementsByTagName('StartDate')[0].toxml().replace('<StartDate>','').replace('</StartDate>','')
        end_date = dom.getElementsByTagName('EndDate')[0].toxml().replace('<EndDate>','').replace('</EndDate>','')

        accountsets = dom.getElementsByTagName('AccountSet')
        for accountset in accountsets:
            account_number = accountset.getElementsByTagName('AccNo')[0].toxml().replace('<AccNo>','').replace('</AccNo>','')
            currency_code = accountset.getElementsByTagName('Ccy')[0].toxml().replace('<Ccy>','').replace('</Ccy>','')
            balance_start = accountset.getElementsByTagName('OpenBal')[0].toxml().replace('<OpenBal>','').replace('</OpenBal>','')
            balance_end_real = accountset.getElementsByTagName('CloseBal')[0].toxml().replace('<CloseBal>','').replace('</CloseBal>','')

            # checking balances:
            self.check_balances(balance_start, account_number)

            svals = {
                'name': account_number + ' ' + start_date + ':' + end_date,
                'date': end_date,
                'balance_start': float(balance_start),
                'balance_end_real': float(balance_end_real),
                'transactions': []
            }

            # getting elements for account.bank.statement.line:
            statement_lines = accountset.getElementsByTagName('TrxSet')
            for line in statement_lines:
                # checking transaction types:
                type_name_tag = line.getElementsByTagName('TypeName')

                # getting date, name, ref and amount
                line_date = line.getElementsByTagName('BookDate')[0].toxml().replace('<BookDate>','').replace('</BookDate>','')
                pmt_info = line.getElementsByTagName('PmtInfo')
                if pmt_info:
                    line_name = pmt_info[0].toxml().replace('<PmtInfo>','').replace('</PmtInfo>','')
                if (not pmt_info) and type_name_tag:
                    line_name = type_name_tag[0].toxml().replace('<TypeName>','').replace('</TypeName>','')
                line_ref = line.getElementsByTagName('BankRef')[0].toxml().replace('<BankRef>','').replace('</BankRef>','')
                line_amount = float(line.getElementsByTagName('AccAmt')[0].toxml().replace('<AccAmt>','').replace('</AccAmt>',''))
                cord = line.getElementsByTagName('CorD')[0].toxml().replace('<CorD>','').replace('</CorD>','')
                if cord == 'D':
                    line_amount *= (-1)

                # getting Partner and Currency data
                line_cur = False
                line_amount_cur = 0.0
                partner = False
                partner_name = False
                partner_reg_id = False
                partner_bank_account = False
                bank_account = False
#                account_id = False
                bank_name = False
                bank_bic = False
                cPartySet = line.getElementsByTagName('CPartySet')
                if cPartySet:
                    # currency data:
                    line_cur_tag = cPartySet[0].getElementsByTagName('Ccy')
                    if line_cur_tag:
                        line_cur_txt = line_cur_tag[0].toxml().replace('<Ccy>','').replace('</Ccy>','').replace('<Ccy/>','')
                        if line_cur_txt and line_cur_txt != currency_code:
                            line_cur = cur_obj.search([('name','=',line_cur_txt)], limit=1)
                    line_amount_cur_tag = cPartySet[0].getElementsByTagName('Amt')
                    if line_amount_cur_tag:
                        line_amount_cur = line_amount_cur_tag[0].toxml().replace('<Amt>','').replace('</Amt>','').replace('<Amt/>','')
                        line_amount_cur = float(line_amount_cur)

                    # partner data:
                    partner_name_tag = cPartySet[0].getElementsByTagName('Name')
                    if partner_name_tag:
                        partner_name = partner_name_tag[0].toxml().replace('<Name>','').replace('</Name>','').replace('<Name/>','').replace("&quot;","'")
                    partner_reg_id_tag = cPartySet[0].getElementsByTagName('LegalId')
                    if partner_reg_id_tag:
                        partner_reg_id = partner_reg_id_tag[0].toxml().replace('<LegalId>','').replace('</LegalId>','').replace('<LegalId/>','')
                    partner_bank_account_tag = cPartySet[0].getElementsByTagName('AccNo')
                    if partner_bank_account_tag:
                        partner_bank_account = partner_bank_account_tag[0].toxml().replace('<AccNo>','').replace('</AccNo>','').replace('<AccNo/>','')

                    # testing, whether it's possible to get partner (also type and account) from the system:
                    bank_account = bank_obj.search([('acc_number','=',partner_bank_account)], limit=1)
                    if (not bank_account) and partner_bank_account:
                        partner_bank_account_list = list(partner_bank_account)
                        partner_bank_account_list.insert(4,' ')
                        partner_bank_account_list.insert(9,' ')
                        partner_bank_account_list.insert(14,' ')
                        partner_bank_account_list.insert(19,' ')
                        partner_bank_account_list.insert(24,' ')
                        partner_bank_account_2 = "".join(partner_bank_account_list)
                        bank_account = bank_obj.search([('acc_number','=',partner_bank_account_2)], limit=1)
                    if bank_account:
                        partner = bank_account.partner_id
                    if (not bank_account) and (partner_reg_id):
                        partners = self.env['res.partner'].search([('vat','ilike',partner_reg_id)])
                        if len([p.id for p in partners]) == 1:
                            partner = partners
                    # setting account if partner found:
#                    if partner:
#                        if cord == 'C':
#                            account_id = partner.property_account_receivable_id.id
#                        if cord == 'D':
#                            account_id = partner.property_account_payable_id.id
                    # getting bank data:
                    bank_name_tag = cPartySet[0].getElementsByTagName('BankName')
                    if bank_name_tag:
                        bank_name = bank_name_tag[0].toxml().replace('<BankName>','').replace('</BankName>','').replace('<BankName/>','')
                    bank_bic_tag = cPartySet[0].getElementsByTagName('BankCode')
                    if bank_bic_tag:
                        bank_bic = bank_bic_tag[0].toxml().replace('<BankCode>','').replace('</BankCode>','').replace('<BankCode/>','')

                # getting Transaction Types
                type_code = False
                type_code_tag = line.getElementsByTagName('TypeCode')
                if type_code_tag:
                    type_code = type_code_tag[0].toxml().replace('<TypeCode>','').replace('</TypeCode>','')
                if (not type_code_tag) and type_name_tag:
                    type_code = type_name_tag[0].toxml().replace('<TypeName>','').replace('</TypeName>','')
#                if not partner:
#                    config_obj = self.env['account.bank.transaction.type']
#                    config = config_obj.search([('name','=',type_code)], limit=1)
#                    if config:
#                        account_id = config.account_id.id

                svals['transactions'].append({
                    'date': line_date,
                    'name': line_name,
                    'ref': line_ref,
                    'amount': line_amount,
                    'amount_currency': line_amount_cur,
                    'currency_id': line_cur and line_cur.id or False,
                    'partner_name': partner_name,
                    'account_number': partner_bank_account,
                    'partner_bank_account': partner_bank_account,
                    'partner_reg_id': partner_reg_id,
                    'partner_id': partner and partner.id or False,
                    'transaction_type': type_code,
                    'bank_account_id': bank_account and bank_account.id or False,
#                    'account_id': account_id,
                    'bank_name': bank_name,
                    'bank_bic': bank_bic
                })

            stmts_vals.append(svals)

        return currency_code, account_number, stmts_vals


    def _complete_stmts_vals(self, stmts_vals, journal, account_number):
        res = super(AccountBankStatementImport, self)._complete_stmts_vals(stmts_vals, journal, account_number)
        ba_obj = self.env['res.partner.bank']
        bank_obj = self.env['res.bank']
        for st_vals in res:
            for line_vals in st_vals['transactions']:
                # update bank account and save partner if possible:
                if (not line_vals.get('partner_id', False)) and line_vals.get('partner_reg_id'):
                    partners = self.env['res.partner'].search([('vat','ilike',line_vals['partner_reg_id'])])
                    if len([p.id for p in partners]) == 1:
                        line_vals['partner_id'] = partners.id
                if line_vals.get('bank_account_id', False):
                    bank_account = ba_obj.browse(line_vals['bank_account_id'])
                    if (not bank_account.partner_id) and line_vals.get('partner_id', False):
                        bank_account.write({'partner_id': line_vals['partner_id']})
                    if (not bank_account.bank_id) and (line_vals.get('bank_name', False) or line_vals.get('bank_bic', False)):
                        bank_name = line_vals.get('bank_name', False) or line_vals.get('bank_bic', False)
                        bank_bic = line_vals.get('bank_bic', False)
                        bank = bank_obj.search([('bic','=',bank_bic)], limit=1)
                        if not bank:
                            bank = bank_obj.search([('name','=',bank_name)], limit=1)
                        if not bank:
                            bank = bank_obj.create({
                                'name': bank_name,
                                'bic': bank_bic
                            })
                        bank_account.write({'bank_id': bank.id})
                line_vals.pop('bank_name')
                line_vals.pop('bank_bic')
        return res


    def _parse_file(self, data_file):
        if self.format == 'iso20022':
            return self.iso20022_parsing(data_file)
        elif self.format == 'fidavista':
            return self.fidavista_parsing(data_file)
        else:
            return super(AccountBankStatementImport, self)._parse_file()


#    @api.model
#    def create(self, values):
#        res = super(AccountBankStatementImport, self).create(values)
#        res._onchange_data_file()
#        return res


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: