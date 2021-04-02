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
import base64
from datetime import date, datetime, timedelta

class PayslipEDSExport(models.TransientModel):
    _name = 'payslip.eds.export'

    @api.model
    def get_year_month(self):
        payslip_obj = self.env['hr.payslip']
        year_list = []
        month_list = []
        for payslip in payslip_obj.browse(self.env.context.get('active_ids',[])):
            month_from = int(datetime.strftime(payslip.date_from, '%m'))
            month_to = int(datetime.strftime(payslip.date_to, '%m'))
            year_from = int(datetime.strftime(payslip.date_from, '%Y'))
            year_to = int(datetime.strftime(payslip.date_to, '%Y'))
            if month_from not in month_list:
                month_list.append(month_from)
            if month_to not in month_list:
                month_list.append(month_to)
            if year_from not in year_list:
                year_list.append(year_from)
            if year_to not in year_list:
                year_list.append(year_to)
        return year_list, month_list

    @api.model
    def prepare_data(self):
        payslip_obj = self.env['hr.payslip']
        result = {}
        for payslip in payslip_obj.browse(self.env.context.get('active_ids',[])):
            company = payslip.company_id and payslip.company_id or self.env.user.company_id
            if company.id in result:
                result[company.id]['payslips'].append(payslip)
            else:
                result.update({company.id: {
                    'company_reg': company.company_registry,
                    'company_name': company.name,
                    'payslips': [payslip]
                }})

        for c_id, c_vals in result.items():
            result1 = {}
            for payslip in c_vals['payslips']:
                tab = "1"
                emp_id = payslip.employee_id.id
                emp_name = payslip.employee_id.name
                emp_code = payslip.employee_id.identification_id
                emp_stat = "DN"
                hours = 0.0
                for wd in payslip.worked_days_line_ids:
                    if wd.code == 'WORK100':
                        hours += wd.number_of_hours
                if payslip.employee_id.relief_ids:
                    for relief in payslip.employee_id.relief_ids:
                        if relief.type in ['disability1', 'disability2', 'disability3'] and (((not relief.date_from) and (not relief.date_to)) or ((not relief.date_from) and relief.date_to and relief.date_to >= payslip.date_from) or ((not relief.date_to) and relief.date_from and relief.date_from <= payslip.date_to) or (relief.date_from and relief.date_to and relief.date_form <= payslip.date_to and relief.date_to >= payslip.date_from)):
                            tab = "2"
                            if relief.type in ['disability1', 'disability2']:
                                emp_stat = "DI"
#                if tab == "1":
#                    for pl in payslip.line_ids:
#                        if pl.code in ['PABAN','PABBN'] and pl.amount != 0.0:
#                            tab == "2"
                if (emp_id, tab) in result1:
                    result1[(emp_id, tab)]['lines'] += [l for l in payslip.line_ids]
                    result1[(emp_id, tab)]['hours'] += hours
                else:
                    result1.update({(emp_id, tab): {
                        'tab': tab,
                        'emp_name': emp_name,
                        'emp_code': emp_code and emp_code.replace('-','') or False,
                        'emp_stat': emp_stat,
                        'lines': [l for l in payslip.line_ids],
                        'hours': hours
                    }})

            result[c_id].update({'results': result1.values()})
        return result.values()

    @api.model
    def _get_default_name(self):
        company_list = self.prepare_data()
        name = "_".join([c['company_name'] for c in company_list]).replace(' ','_').replace('"','').replace("'","")
        year, month = self.get_year_month()
        if len(year) == 1 and len(month) == 1:
            name += ('_' + str(year[0]) + '-' + "%02d" % (month[0]))
        if len(name) > 28:
            name = name[:28]
        name += '.xml'
        return name

    @api.model
    def _get_default_responsible(self):
        def_resp_id = self.env['ir.config_parameter'].sudo().get_param('payslip_eds_export.responsible_id')
        resp_id = False
        if def_resp_id:
            resp_id = int(def_resp_id)
        return resp_id

    @api.model
    def _get_default_date_pay(self):
        date_pay = date.today().strftime('%Y-%m-%d')
        year, month = self.get_year_month()
        if len(year) == 1 and len(month) == 1:
            day_def = self.env['ir.config_parameter'].sudo().get_param('payslip_eds_export.date_pay_day', default=31)
            if day_def:
                day = int(day_def)
                if month[0] in [4, 6, 9, 11] and day > 30:
                    day = 30
                if month[0] == 2:
                    if int(str(year[0])[-2:]) % 4 != 0 and day > 28:
                        day = 28
                    if int(str(year[0])[-2:]) % 4 == 0 and day > 29:
                        day = 29
                date_pay = datetime.strftime(date(year[0], month[0], day), '%Y-%m-%d')
        return date_pay

    name = fields.Char(string='File Name', required=True, default=_get_default_name)
    file_save = fields.Binary(string='Save File', filters='*.xml', readonly=True)
    responsible_id = fields.Many2one('hr.employee', string='Responsible', required=True, default=_get_default_responsible)
    date_pay = fields.Date(string='Payment Date', required=True, default=_get_default_date_pay)
    pit_src = fields.Selection([
        ('sel_month', 'Selected Month'),
        ('prev_month', 'Previous Month')
    ], string='Personal Income Tax From', required=True, default='prev_month')

    @api.model
    def get_prev_pit(self, lines):
        payslips = []
        for l in lines:
            if l.slip_id and l.slip_id not in payslips:
                payslips.append(l.slip_id)
        date_from = False
        date_to = False
        employee_id = False
        for p in payslips:
            employee_id = p.employee_id.id
            if date_from == False or date_from != False and p.date_from < date_from:
                date_from = p.date_from
            if date_to == False or date_to != False and p.date_to < date_to:
                date_to = p.date_to
        pit = 0.0
        if payslips:
            days_diff = date_to - date_from
            dys = days_diff.days
            ps_obj = self.env['hr.payslip']
            prev_pss = ps_obj.search([('employee_id','=',employee_id), ('date_from','<',date_from)], order='date_from desc')
            dys2 = 0
            c = 0
            for pps in prev_pss:
                c += 1
                d_diff = pps.date_to - pps.date_from
                dys2 += d_diff.days
                if c > 1 and dys2 > dys:
                    break
                for pl in pps.line_ids:
                    if pl.code == 'IIN':
                        pit += pl.total
        return pit

    @api.multi
    def create_xml(self):
        self.ensure_one()

        def make_table_dict(t_data):
            t_dict = {}
            for r in t_data['results']:
                if r['tab'] in t_dict:
                    t_dict[r['tab']].append(r)
                if r['tab'] not in t_dict:
                    t_dict.update({r['tab']: [r]})
            return t_dict

        data_prep = self.prepare_data()
        year, month = self.get_year_month()
        data_of_file = """<?xml version="1.0" encoding="utf-8"?>"""
        for d in data_prep:
            data_of_file += """\n<DokDDZv2 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">"""

            # top section:
            if len(year) == 1:
                data_of_file += ("\n  <ParskGads>" + str(year[0]) + "</ParskGads>")
            if len(year) != 1:
                data_of_file += "\n  <ParskGads/>"
            if len(month) == 1:
                data_of_file += ("\n  <ParskMen>" + str(month[0]) + "</ParskMen>")
            if len(month) != 1:
                data_of_file += "\n  <ParskMen/>"
            if d['company_reg']:
                data_of_file += ("\n  <NmrKods>" + d['company_reg'] + "</NmrKods>")
            if not d['company_reg']:
                data_of_file += ("\n  <NmrKods/>")
            date_pay = str(int(datetime.strftime(self.date_pay, '%d')))
            data_of_file += ("\n  <IzmaksasDatums>" + date_pay + "</IzmaksasDatums>")
            data_of_file += ("\n  <Sagatavotajs>" + self.responsible_id.name + "</Sagatavotajs>")
            if self.responsible_id.work_phone:
                data_of_file += ("\n  <Talrunis>" + self.responsible_id.work_phone + "</Talrunis>")
            if not self.responsible_id.work_phone:
                data_of_file += ("\n  <Talrunis/>")

            # tab section:
            table_dict = make_table_dict(d)
            tot_income = 0.0
            tot_contributions = 0.0
            tot_pit = 0.0
            tot_rf = 0.0
            for key, value in table_dict.items():
                data_of_file += ("\n  <Tab%s>" % key)
                for v in value:
                    data_of_file += "\n    <R>"
                    if v['emp_code']:
                        data_of_file += ("\n      <PersonasKods>" + v['emp_code'] + "</PersonasKods>")
                    if not v['emp_code']:
                        data_of_file += "\n      <PersonasKods/>"
                    data_of_file += ("\n      <VardsUzvards>" + v['emp_name'] + "</VardsUzvards>")
                    data_of_file += ("\n      <Statuss>" + v['emp_stat'] + "</Statuss>")
                    income = 0.0
                    contributions = 0.0
                    pit = 0.0
                    if self.pit_src == 'prev_month':
                        pit = self.get_prev_pit(v['lines'])
                    rf = 0.0
                    for l in v['lines']:
                        if l.salary_rule_id.category_id.code == 'BRUTOnLV':
                            income += l.total
                        if l.salary_rule_id.category_id.code == 'VSAOILV':
                            contributions += l.total
                        if self.pit_src == 'sel_month' and l.code == 'IIN':
                            pit += l.total
                        if l.code == 'RN':
                            rf += l.total
                    data_of_file += ("\n      <Ienakumi>" + str(income) + "</Ienakumi>")
                    data_of_file += ("\n      <Iemaksas>" + str(contributions) + "</Iemaksas>")
                    data_of_file += ("\n      <PrecizetieIenakumi>" + str(0.0) + "</PrecizetieIenakumi>")
                    data_of_file += ("\n      <PrecizetasIemaksas>" + str(0.0) + "</PrecizetasIemaksas>")
                    data_of_file += ("\n      <IeturetaisNodoklis>" + str(pit) + "</IeturetaisNodoklis>")
                    wt = "1"
                    data_of_file += ("\n      <DarbaVeids>" + wt + "</DarbaVeids>")
                    data_of_file += ("\n      <RiskaNodevasPazime>" + (rf > 0.0 and "true" or "false") + "</RiskaNodevasPazime>")
                    data_of_file += ("\n      <RiskaNodeva>" + str(rf) + "</RiskaNodeva>")
#                    data_of_file += ("\n      <IemaksuDatums/>")
                    data_of_file += ("\n      <Stundas>" + str(int(v['hours'])) + "</Stundas>")
                    data_of_file += "\n    </R>"
                    tot_income += income
                    tot_contributions += contributions
                    tot_pit += pit
                    tot_rf += rf
                data_of_file += ("\n  </Tab%s>" % key)

            data_of_file += ("\n  <Ienakumi>" + str(tot_income) + "</Ienakumi>")
            data_of_file += ("\n  <Iemaksas>" + str(tot_contributions) + "</Iemaksas>")
            data_of_file += ("\n  <PrecizetieIenakumi>" + str(0) + "</PrecizetieIenakumi>")
            data_of_file += ("\n  <PrecizetasIemaksas>" + str(0) + "</PrecizetasIemaksas>")
            data_of_file += ("\n  <IeturetaisNodoklis>" + str(tot_pit) + "</IeturetaisNodoklis>")
            data_of_file += ("\n  <RiskaNodeva>" + str(tot_rf) + "</RiskaNodeva>")
            data_of_file += "\n</DokDDZv2>"

        data_of_file_real = base64.encodestring(data_of_file.encode('utf8'))
        self.write({'file_save': data_of_file_real, 'name': self.name})

        cp_obj = self.env['ir.config_parameter'].sudo()
        def_resp_id = cp_obj.get_param('payslip_eds_export.responsible_id')
        if (not def_resp_id) or def_resp_id != self.responsible_id.id:
            cp_obj.set_param('payslip_eds_export.responsible_id', str(self.responsible_id.id))
        def_date_pay_day = cp_obj.get_param('payslip_eds_export.date_pay_day')
        exp_date_pay_day = datetime.strftime(self.date_pay, '%d')
        if (not def_date_pay_day) or def_date_pay_day != exp_date_pay_day:
            cp_obj.set_param('payslip_eds_export.date_pay_day', str(exp_date_pay_day))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payslip.eds.export',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False,'form')],
            'target': 'new',
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: