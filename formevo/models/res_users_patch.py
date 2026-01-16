from odoo import models, api, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    def assign_yonn_group(self, group_name):
        group = self.env.ref(f'formevo.group_yonn_elearning_{group_name}', raise_if_not_found=False)
        if group:
            self.sudo().with_context(bypass_user_type_check=True).write({
                'groups_id': [(4, group.id)]
            })
        return True