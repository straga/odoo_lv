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
from xml.dom.minidom import getDOMImplementation, parseString
from datetime import datetime

class ReliefEDSImport(models.TransientModel):
    _name = 'relief.eds.import'
    _rec_name = 'eds_fname'

    @api.model
    def _get_default_employees(self):
        return self.env.context.get('active_ids', [])

    eds_file = fields.Binary(string='XML File from EDS', required=True)
    eds_fname = fields.Char(string='EDS File Name')
    employee_ids = fields.Many2many('hr.employee', string='Employees', default=_get_default_employees)

    @api.multi
    def eds_file_parsing(self):
        self.ensure_one()
        record = str(base64.b64decode(self.eds_file), 'iso8859-4', 'strict').encode('iso8859-4','strict')
        dom = parseString(record)
        file_employees = dom.getElementsByTagName('gigv')
        if file_employees is None:
            return False
        emp_obj = self.env['hr.employee']
        rel_obj = self.env['hr.employee.relief']
        e_ids = [e.id for e in self.employee_ids]
        for fe in file_employees:
            emp_ids = []
            fe_pc = fe.getElementsByTagName('pers_kods')[0].toxml().replace('<pers_kods>', '').replace('</pers_kods>', '')
            fe_name = fe.getElementsByTagName('vards_uzvards')[0].toxml().replace('<vards_uzvards>', '').replace('</vards_uzvards>', '')
            if fe_pc:
                emp_query_str = """SELECT id FROM hr_employee 
                    WHERE COALESCE(identification_id, '') != '' 
                    AND REPLACE(identification_id, '-', '') = '%s' 
                    AND id %s %s""" % (fe_pc, len(e_ids) == 1 and '=' or 'in', len(e_ids) == 1 and e_ids[0] or tuple(e_ids),)
                self._cr.execute(emp_query_str)
                emp_ids = [r['id'] for r in self._cr.dictfetchall()]
            if (not e_ids) and fe_name:
                emp_query_str = """SELECT emp.id FROM hr_employee AS emp 
                    LEFT JOIN resource_resource AS res ON emp.resource_id = res.id 
                    WHERE UPPER(res.name) = %s 
                    AND emp.id %s %s""" % (fe_name, len(e_ids) == 1 and '=' or 'in', len(e_ids) == 1 and e_ids[0] or tuple(e_ids),)
                self._cr.execute(emp_query_str)
                emp_ids = [r['id'] for r in self._cr.dictfetchall()]
            if emp_ids:
                dep_list = []
                dep_main = fe.getElementsByTagName('apgadajamie')
                if dep_main:
                    deps = dep_main[0].getElementsByTagName('apgadajamais')
                    for dep in deps:
                        dep_name = dep.getElementsByTagName('vards_uzvards')[0].toxml().replace('<vards_uzvards>', '').replace('</vards_uzvards>', '')
                        dep_df = dep.getElementsByTagName('datums_no')[0].toxml().replace('<datums_no>', '').replace('</datums_no>', '')
                        dep_date_from = datetime.strftime(datetime.strptime(dep_df, '%Y-%m-%dT%H:%M:%S').date(), '%Y-%m-%d')
                        dep_dt = dep.getElementsByTagName('datums_lidz')[0].toxml().replace('<datums_lidz>', '').replace('</datums_lidz>', '')
                        dep_date_to = datetime.strftime(datetime.strptime(dep_dt, '%Y-%m-%dT%H:%M:%S').date(), '%Y-%m-%d')
                        dep_list.append({
                            'type': 'dependent',
                            'name': dep_name,
                            'date_from': dep_date_from,
                            'date_to': dep_date_to
                        })
                dis_list = []
                add_main = fe.getElementsByTagName('papildu_atvieglojumi')
                if add_main:
                    adds = add_main[0].getElementsByTagName('papildu_atvieglojums')
                    for add in adds:
                        add_type = add.getElementsByTagName('veids')[0].toxml().replace('<veids>', '').replace('</veids>', '')
                        dis_type = False
                        if add_type == u'1. grupas invalīds':
                            dis_type = 'disability1'
                        if add_type == u'2. grupas invalīds':
                            dis_type = 'disability2'
                        if add_type == u'3. grupas invalīds':
                            dis_type = 'disability3'
                        if dis_type:
                            dis_df = add.getElementsByTagName('datums_no')[0].toxml().replace('<datums_no>', '').replace('</datums_no>', '')
                            dis_date_from = datetime.strftime(datetime.strptime(dis_df, '%Y-%m-%dT%H:%M:%S').date(), '%Y-%m-%d')
                            dis_dt = add.getElementsByTagName('datums_lidz')[0].toxml().replace('<datums_lidz>', '').replace('</datums_lidz>', '')
                            dis_date_to = datetime.strftime(datetime.strptime(dis_dt, '%Y-%m-%dT%H:%M:%S').date(), '%Y-%m-%d')
                            dis_list.append({
                                'type': dis_type,
                                'name': add_type,
                                'date_from': dis_date_from,
                                'date_to': dis_date_to
                            })
                umm_list = []
                umm_main = fe.getElementsByTagName('prognozetie_mnm')
                if umm_main:
                    umms = umm_main[0].getElementsByTagName('prognozetais_mnm')
                    for umm in umms:
                        umm_name = umm.getElementsByTagName('veids')[0].toxml().replace('<veids>', '').replace('</veids>', '')
                        umm_df = umm.getElementsByTagName('datums_no')[0].toxml().replace('<datums_no>', '').replace('</datums_no>', '')
                        umm_date_from = datetime.strftime(datetime.strptime(umm_df, '%Y-%m-%dT%H:%M:%S').date(), '%Y-%m-%d')
                        umm_dt = umm.getElementsByTagName('datums_lidz')[0].toxml().replace('<datums_lidz>', '').replace('</datums_lidz>', '')
                        umm_date_to = datetime.strftime(datetime.strptime(umm_dt, '%Y-%m-%dT%H:%M:%S').date(), '%Y-%m-%d')
                        umm_amount = umm.getElementsByTagName('summa')[0].toxml().replace('<summa>', '').replace('</summa>', '')
                        umm_list.append({
                            'type': 'untaxed_month',
                            'name': umm_name,
                            'date_from': umm_date_from,
                            'date_to': umm_date_to,
                            'amount': float(umm_amount)
                        })
                for emp_id in emp_ids:
                    for dpl in dep_list:
                        self._cr.execute("""SELECT id FROM hr_employee_relief 
                            WHERE type = 'dependent' 
                            AND employee_id = %s 
                            AND UPPER(name) = %s 
                            AND (date_from is Null OR date_from <= %s) 
                            AND (date_to is Null OR date_to >= %s)""", (emp_id, dpl['name'], dpl['date_to'], dpl['date_from'],))
                        dep_ids = [r['id'] for r in self._cr.dictfetchall()]
                        if dep_ids:
                            if len(dep_ids) > 1:
                                e_dep_ids = []
                                for dep in rel_obj.browse(dep_ids):
                                    if dep.date_from == dpl['date_from'] or dep.date_to == dpl['date_to']:
                                        e_dep_ids.append(dep.id)
                                if e_dep_ids:
                                    dep_ids = e_dep_ids
                            rel_obj.browse([dep_ids[0]]).write({
                                'date_from': dpl['date_from'],
                                'date_to': dpl['date_to']
                            })
                        if not dep_ids:
                            dep_data = dpl.copy()
                            dep_data.update({'employee_id': emp_id})
                            rel_obj.create(dep_data)
                    for dsl in dis_list:
                        diss = rel_obj.search([
                            ('employee_id','=',emp_id),
                            ('type','=',dsl['type']),
                            ('date_from','=',dsl['date_from']),
                            ('date_to','=',dsl['date_to'])
                        ])
                        if not diss:
                            dis_data = dsl.copy()
                            dis_data.update({'employee_id': emp_id})
                            rel_obj.create(dis_data)
                    for uml in umm_list:
                        umms = rel_obj.search([
                            ('employee_id','=',emp_id),
                            ('type','=','untaxed_month'),
                            ('date_from','=',uml['date_from']),
                            ('date_to','=',uml['date_to'])
                        ])
                        if umms:
                            umms.write({
                                'name': uml['name'],
                                'amount': uml['amount']
                            })
                        else:
                            umm_data = uml.copy()
                            umm_data.update({'employee_id': emp_id})
                            rel_obj.create(umm_data)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: