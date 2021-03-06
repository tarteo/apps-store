# -*- coding: utf-8 -*-
# Copyright (C) 2017-Today: Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, api


class OdooModule(models.Model):
    _inherit = 'odoo.module'

    @api.depends(
        'product_template_id',
        'product_template_id.product_variant_ids'
    )
    def _compute_product_qty(self):
        for module in self:
            module.product_qty = len(
                module.product_template_id.product_variant_ids)

    product_template_id = fields.Many2one(
        'product.template',
        "Product Template",
    )
    product_qty = fields.Integer(
        '# of Products',
        compute='_compute_product_qty',
        store=True)

    @api.multi
    def action_view_products(self):
        action = self.env.ref('product.product_normal_action_sell')
        result = action.read()[0]
        product_ids = sum(
            [m.product_template_id.product_variant_ids.ids for m in self],
            []
        )
        # choose the view_mode accordingly
        if len(product_ids) > 1:
            result['domain'] = "[('id','in',[" + ','.join(
                map(str, product_ids)) + "])]"
        elif len(product_ids) == 1:
            res = self.env.ref('product.product_normal_form_view', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = product_ids and product_ids[0] or False
        return result

    @api.multi
    def action_create_product(self):
        self._create_product()

    @api.multi
    def _create_product(self):
        """
        Create the product template related to the module in current recordset.
        :return: product.template recordset
        """
        product_obj = self.env['product.template']
        products = self.env['product.template']
        modules = self.filtered(lambda m: not m.product_template_id)
        domain = [
            ('odoo_module_id', 'in', modules.ids),
        ]
        matching_products = product_obj.search(domain)
        for odoo_module in modules:
            product = matching_products.filtered(
                lambda p: p.odoo_module_id == odoo_module)
            if not product:
                product_values = odoo_module._prepare_template()
                new_product = product_obj.create(product_values)
                odoo_module.write({
                    'product_template_id': new_product.id,
                })
                products |= new_product
        return products

    @api.multi
    def _prepare_template(self):
        """
        Create the dict to create a product.template recordset based on the
        current recordset.
        The values dict contains info to link the future product with the
        current module. It also fill the name of the future product with the
        name of the current module.
        :return: dict
        """
        self.ensure_one()
        attribute_obj = self.env['product.attribute.value']
        series = self.module_version_ids.mapped(
            'repository_branch_id.organization_serie_id.name')
        attributes = attribute_obj.search([('name', 'in', series)])
        attribute = self.env.ref(
            'apps_product_creator.attribute_odoo_version')
        attribute_line_values = {
            'attribute_id': attribute.id,
            'value_ids': [(6, 0, attributes.ids)],
        }
        values = {
            'odoo_module_id': self.id,
            'type': 'service',
            'name': self.name,
            'purchase_ok': False,
            'list_price': 0,
            'standard_price': 0,
            'image': self.image,
            'attribute_line_ids': [
                (0, 0, attribute_line_values),
            ]
        }
        return values

    @api.multi
    def write(self, values):
        to_update = bool(values.get('image', False))
        result = super(OdooModule, self).write(values)
        if to_update:
            for odoo_module in self.filtered(lambda x: x.product_template_id):
                odoo_module.product_template_id.write({
                    'image': odoo_module.image,
                })
        return result

    @api.model
    def cron_create_product(self):
        modules = self.search([('product_template_id', '=', False),
                               ('module_version_qty', '!=', 0)])
        modules.action_create_product()
        return True
