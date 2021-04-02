# -*- encoding: utf-8 -*-
##############################################################################
#
#    Part of Odoo.
#    Copyright (C) 2020 Allegro IT (<http://www.allegro.lv/>)
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
import datetime
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from odoo.tools import float_round


class HolidaysType(models.Model):
    _inherit = "hr.leave.type"

    code = fields.Char(string='Code')
    reduces_tax_relief = fields.Boolean(string='Reduces Tax Relief')


class Employee(models.Model):
    _inherit = "hr.employee"

    holiday_ids = fields.One2many('hr.leave', 'employee_id', string='Leaves')
    relief_ids = fields.One2many('hr.employee.relief', 'employee_id', string='Tax Relief')


class EmployeeRelief(models.Model):
    _name = "hr.employee.relief"
    _description = "Employee Tax Relief"
    _order = "date_from desc"

    @api.model
    def _get_default_currency(self):
        return self.env.user.company_id.currency_id.id

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    type = fields.Selection([
        ('untaxed_month', 'Untaxed Minimum for Month'),
        ('dependent', 'Dependent Person'),
        ('disability1', 'Group 1 Disability'),
        ('disability2', 'Group 2 Disability'),
        ('disability3', 'Group 3 Disability')
    ], string='Type', required=True)
    name = fields.Char(string='Name', required=True)
    date_from = fields.Date(string='Valid From')
    date_to = fields.Date(string='Valid Until')
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', default=_get_default_currency)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        res = super(HrPayslip, self).get_worked_day_lines(contracts, date_from, date_to)
        hd_type_obj = self.env['hr.leave.type']
        for r in res:
            hd_type = hd_type_obj.search([('name','=',r['name'])], limit=1)
            if hd_type and hd_type.code and hd_type.code != r['code']:
                ind = res.index(r)
                res[ind]['code'] = hd_type.code
        return res

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        res = super(HrPayslip, self).get_inputs(contracts, date_from, date_to)
        for contract in contracts:
            employee = contract.employee_id
            avg_salary = 0.0
            if date_from and date_to and employee:
                # get date 6 months earlier:
                date_to_6 = datetime.datetime.strftime((isinstance(date_to, str) and datetime.datetime.strptime(date_to, '%Y-%m-%d') or date_to + relativedelta(months=-7)), '%Y-%m-%d')
                # find all payslips within these 6 months:
                curr_pss = self.search([('date_from','=',date_from), ('date_to','=',date_to), ('employee_id','=',employee.id), ('contract_id','=',contract.id)])
                cur_ps_ids = [cps.id for cps in curr_pss]
                prev_pss = self.search([('date_from','<=',date_to), ('date_to','>',date_to_6), ('employee_id','=',employee.id), ('contract_id','=',contract.id), ('id','not in',cur_ps_ids)])
                # set start values:
                worked_days = 0.0
                total_salary = 0.0
                # compute worked days and total salary + premiums from previous payslips:
                if prev_pss:
                    for prev_ps in prev_pss:
                        prev_wd = 0.0
                        prev_ts = 0.0
                        # try to get worked days from lines:
                        for wdl in prev_ps.worked_days_line_ids:
                            if wdl.code == 'WORK100':
                                prev_wd += wdl.number_of_days
                        # if there are no worked day lines, compute workdays from dates:
                        if not prev_ps.worked_days_line_ids:
                            oneday = datetime.timedelta(days=1)
                            test_date = isinstance(prev_ps.date_from, str) and datetime.datetime.strptime(prev_ps.date_from, '%Y-%m-%d') or prev_ps.date_from
                            test_date_to = isinstance(prev_ps.date_from, str) and datetime.datetime.strptime(prev_ps.date_to, '%Y-%m-%d') or prev_ps.date_to
                            while test_date != test_date_to:
                                if test_date.weekday() in [0, 1, 2, 3, 4]:
                                    prev_wd += 1.0
                                test_date += oneday
                        # try to get salary and premiums from computed payslip lines:
                        for l in prev_ps.line_ids:
                            if l.code in ['LD', 'PIEM', 'PIEMV']:
                                prev_ts += l.total
                        # if there are no computed lines, compute them to get data:
                        if not prev_ps.line_ids:
                            prev_lines = self._get_payslip_lines([contract.id], prev_ps.id)
                            for pl in prev_lines:
                                if pl['code'] in ['LD', 'PIEM', 'PIEMV']:
                                    prev_ts += (float(pl['quantity']) * pl['amount'] * pl['rate'] / 100)
                        # sum this to start values:
                        worked_days += prev_wd
                        total_salary += prev_ts
                # if there are no previous payslips, compute from current:
                if not prev_pss:
                    # get current worked days:
                    wd_lines = self.get_worked_day_lines(contract, date_from, date_to)
                    curr_wd = 0.0
                    total_days = 0.0
                    for wd in wd_lines:
                        if wd['code'] == 'WORK100':
                            curr_wd += wd['number_of_days']
                        total_days += wd['number_of_days']
                    # if worked days are not provided, get workdays from dates:
                    if not wd_lines:
                        oneday = datetime.timedelta(days=1)
                        test_date = datetime.datetime.strptime(date_from, '%Y-%m-%d')
                        while test_date != datetime.datetime.strptime(date_to, '%Y-%m-%d'):
                            if test_date.weekday() in [0, 1, 2, 3, 4]:
                                curr_wd += 1.0
                            test_date += oneday
                        total_days = curr_wd
                    # define start total:
                    curr_ts = 0.0
                    # if current payslip ids, get payslip line computed values:
                    if cur_ps_ids:
                        for c in cur_ps_ids:
                            ps_lines = self._get_payslip_lines([contract.id], c)
                            for p in ps_lines:
                                if p['code'] in ['LD', 'PIEM', 'PIEMV']:
                                    curr_ts += (float(p['quantity']) * p['amount'] * p['rate'] / 100)
                    # if no current payslip ids, compute the value:
                    if (not cur_ps_ids) and total_days != 0.0:
                        curr_ts += contract.wage * curr_wd / total_days
                        ip_lines = res
                        if ip_lines:
                            for cil in ip_lines:
                                if cil['code'] == 'PIEMV':
                                    curr_ts += cil.get('amount',0.0)
                    total_salary += curr_ts
                    worked_days += curr_wd
                if worked_days != 0.0:
                    avg_salary = total_salary / worked_days
            if avg_salary != 0.0:
                found = False
                for r in res:
                    if r['code'] == 'VDA6M' and r['contract_id'] == contract.id:
                        found = True
                        if r.get('amount',0.0) != avg_salary:
                            ind = res.index(r)
                            res[ind].update({'amount': float(avg_salary)})
                if not found:
                    res.append({
                        'name': _("Average day salary for last 6 months"),
                        'code': 'VDA6M',
                        'amount': avg_salary,
                        'contract_id': contract.id
                    })
        return res

    @api.model
    def reload_inputs(self):
        self.ensure_one()
        wd_line_vals = self.get_worked_day_lines(self.contract_id, self.date_from, self.date_to)
        if wd_line_vals:
            wd_obj = self.env['hr.payslip.worked_days']
            for wd in wd_line_vals:
                wd_lines = wd_obj.search([('payslip_id','=',self.id), ('code','=',wd['code']), ('contract_id','=',wd['contract_id'])])
                if wd_lines:
                    wd_lines.write(wd)
                else:
                    wd_vals = wd.copy()
                    wd_vals.update({'payslip_id': self.id})
                    wd_vals.create(wd_vals)
        input_line_vals = self.get_inputs(self.contract_id, self.date_from, self.date_to)
        if input_line_vals:
            input_obj = self.env['hr.payslip.input']
            for inp in input_line_vals:
                inp_lines = input_obj.search([('payslip_id','=',self.id), ('code','=',inp['code']), ('contract_id','=',inp['contract_id'])])
                if inp_lines:
                    if 'amount' in inp:
                        inp_lines.write({'amount': inp['amount']})
                else:
                    inp_vals = inp.copy()
                    inp_vals.update({'payslip_id': self.id})
                    input_obj.create(inp_vals)
        return True

    @api.model
    def round_float(self, value, precision_digits=None, precision_rounding=None, rounding_method='HALF-UP'):
        return float_round(value, precision_digits=precision_digits, precision_rounding=precision_rounding, rounding_method=rounding_method)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
