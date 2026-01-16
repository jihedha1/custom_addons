# custom_addons/lms_public_info/models/trainer_competency.py
from odoo import models, fields, api


class TrainerCompetency(models.Model):
    _name = 'lms_public_info.trainer_competency'
    _inherit = ['mail.thread']  # AJOUTEZ CETTE LIGNE
    _description = 'Compétence Formateur'
    _order = 'sequence, name'
    _rec_name = 'name'

    # Champs de base
    name = fields.Char(string='Nom', required=True, translate=True, tracking=True)
    code = fields.Char(string='Code', size=10, help='Code unique d\'identification', tracking=True)
    description = fields.Html(string='Description', sanitize=True)

    category = fields.Selection([
        ('technical', 'Technique'),
        ('pedagogical', 'Pédagogique'),
        ('managerial', 'Managerial'),
        ('language', 'Langue'),
        ('certification', 'Certification'),
        ('other', 'Autre')
    ], string='Catégorie', default='technical', required=True, tracking=True)

    level_required = fields.Selection([
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
        ('expert', 'Expert')
    ], string='Niveau requis', default='intermediate', required=True, tracking=True)

    sequence = fields.Integer(string='Séquence', default=10)
    active = fields.Boolean(string='Actif', default=True)

    # Relations
    trainer_ids = fields.Many2many(
        'res.partner',
        relation='trainer_competency_partner_rel',
        column1='competency_id',
        column2='partner_id',
        string='Formateurs',
        domain="[('is_trainer', '=', True)]" # Seulement les individus
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        relation='competency_attachment_rel',
        column1='competency_id',
        column2='attachment_id',
        string='Documents joints'
    )

    # Pour affichage public
    is_public = fields.Boolean(
        string='Visible publiquement',
        default=True,
        help='Cette compétence peut être affichée sur le site web',
        tracking=True
    )

    is_certified = fields.Boolean(
        string='Certifiée',
        default=False,
        help='Cette compétence est certifiée par un organisme',
        tracking=True
    )

    certification_date = fields.Date(string='Date de certification', tracking=True)
    certification_body = fields.Char(string='Organisme certificateur', tracking=True)

    # Champs calculés
    trainer_count = fields.Integer(
        string='Nombre de formateurs',
        compute='_compute_trainer_count',
        store=True
    )

    attachment_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_attachment_count',
        store=True
    )

    # Contraintes
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code doit être unique !'),
        ('name_unique', 'UNIQUE(name)', 'Le nom doit être unique !'),
    ]

    @api.depends('trainer_ids')
    def _compute_trainer_count(self):
        for competency in self:
            competency.trainer_count = len(competency.trainer_ids)

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for competency in self:
            competency.attachment_count = len(competency.attachment_ids)

    # Méthodes d'action
    def action_view_trainers(self):
        """Voir les formateurs ayant cette compétence"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Formateurs - {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'tree,form,kanban',
            'domain': [('id', 'in', self.trainer_ids.ids), ('is_company', '=', False)],
            'context': {
                'default_is_trainer': True,
                'create': False,
                'search_default_filter_trainers': 1
            }
        }

    def action_view_attachments(self):
        """Voir tous les documents joints"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Documents - {self.name}',
            'res_model': 'ir.attachment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {'default_res_model': self._name, 'default_res_id': self.id}
        }

    def toggle_public(self):
        """Basculer la visibilité publique"""
        for competency in self:
            competency.is_public = not competency.is_public
        return True

    @api.model
    def create(self, vals):
        """Surcharge de la création pour générer un code automatique"""
        if not vals.get('code'):
            # Générer un code automatique : COMP-001, etc.
            last_record = self.search([], order='id desc', limit=1)
            if last_record and last_record.code and last_record.code.startswith('COMP-'):
                try:
                    last_num = int(last_record.code.split('-')[1])
                    new_num = last_num + 1
                except:
                    new_num = 1
            else:
                new_num = 1
            vals['code'] = f"COMP-{new_num:03d}"
        return super().create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la création pour le batch processing et génération de code"""
        for vals in vals_list:
            # Générer un code automatique si non fourni
            if not vals.get('code'):
                last_record = self.search([], order='id desc', limit=1)
                if last_record and last_record.code and last_record.code.startswith('COMP-'):
                    try:
                        last_num = int(last_record.code.split('-')[1])
                        new_num = last_num + 1
                    except:
                        new_num = 1
                else:
                    new_num = 1
                vals['code'] = f"COMP-{new_num:03d}"

            # Assurer des valeurs par défaut cohérentes
            if 'active' not in vals:
                vals['active'] = True
            if 'is_public' not in vals:
                vals['is_public'] = True

        return super().create(vals_list)

    def write(self, vals):
        """Surcharge de l'écriture si nécessaire"""
        # Ajoutez votre logique ici
        return super().write(vals)

    # Méthodes pour les boutons
    def action_make_public(self):
        """Rendre la compétence publique"""
        if not self:
            return
        self.ensure_one()
        self.is_public = True
        message = _("La compétence '%s' a été rendue publique.") % self.name
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': message,
                'sticky': False,
                'type': 'success',
            }
        }

    def action_make_private(self):
        """Rendre la compétence privée"""
        if not self:
            return
        self.ensure_one()
        self.is_public = False
        message = _("La compétence '%s' a été rendue privée.") % self.name
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': message,
                'sticky': False,
                'type': 'success',
            }
        }

    @api.depends('trainer_ids')
    def _compute_trainer_count(self):
        for competency in self:
            competency.trainer_count = len(competency.trainer_ids)

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for competency in self:
            competency.attachment_count = len(competency.attachment_ids)