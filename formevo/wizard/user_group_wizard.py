from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class UserGroupWizard(models.TransientModel):
    _name = 'yonn.user.group.wizard'
    _description = 'Assistant pour assigner les groupes Yonn'

    user_id = fields.Many2one('res.users', string='Utilisateur', required=True)
    user_type = fields.Selection([
        ('internal', 'Utilisateur Interne'),
        ('portal', 'Portail'),
    ], string='Type d\'utilisateur', required=True)
    yonn_role = fields.Selection([
        ('student', 'Apprenant'),
        ('teacher', 'Enseignant'),
        ('director', 'Directeur'),
    ], string='Rôle Yonn eLearning', required=True)

    @api.onchange('user_id')
    def _onchange_user_id(self):

        if self.user_id:
            self.user_type = 'internal' if not self.user_id.share else 'portal'


    @api.constrains('user_type', 'yonn_role')
    def _check_valid_combination(self):
        """Validation métier optionnelle"""
        for wizard in self:

            if wizard.yonn_role == 'director' and wizard.user_type != 'internal':
                raise ValidationError("Un directeur doit être un utilisateur interne")

    def action_assign_groups(self):
        self.ensure_one()
        user = self.user_id


        base_group = self.env.ref('base.group_user' if self.user_type == 'internal' else 'base.group_portal')
        yonn_group = self.env.ref(f'formevo.group_yonn_elearning_{self.yonn_role}', raise_if_not_found=False)

        if not yonn_group:
            raise UserError(f"Groupe Yonn '{self.yonn_role}' non trouvé !")


        try:
            user.sudo().with_context(tracking_disable=True).write({
                'share': self.user_type == 'portal',
                'groups_id': [
                    (6, 0, [base_group.id, yonn_group.id])
                ]
            })
        except Exception as e:

            self.env['ir.logging'].sudo().create({
                'name': 'Yonn Group Assignment Error',
                'type': 'server',
                'level': 'ERROR',
                'message': f'Failed to configure user {user.id}: {str(e)}',
                'path': 'yonn.user.group.wizard',
                'func': 'action_assign_groups',
                'line': '65'
            })
            raise UserError(f"Erreur lors de la configuration : {str(e)}")

        # 3. Journalisation pour audit
        self.env['ir.logging'].sudo().create({
            'name': 'Yonn Group Assignment',
            'type': 'server',
            'level': 'INFO',
            'message': f'User {user.id} ({user.login}) → Type: {self.user_type}, Role: {self.yonn_role}',
            'path': 'yonn.user.group.wizard',
            'func': 'action_assign_groups',
            'line': '75'
        })

        # 4. Notification de succès améliorée
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Configuration réussie',
                'message': f'{user.name} est maintenant {self.user_type} avec le rôle {self.yonn_role}',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'  # Ferme automatiquement le wizard
                }
            }
        }