# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class ResPartnerTrainerExtended(models.Model):
    """Extension res.partner pour ajouter les fonctionnalités Ressources (US-D1)"""
    _inherit = 'res.partner'

    # =====================
    # TARIFICATION (nouveau - pas dans lms_public_info)
    # =====================
    hourly_rate = fields.Float(
        string='Tarif horaire (€)',
        tracking=True,
        help="Tarif horaire du formateur"
    )

    daily_rate = fields.Float(
        string='Tarif journalier (€)',
        compute='_compute_daily_rate',
        store=True,
        compute_sudo=True,
        help="Calculé automatiquement : tarif horaire × 7"
    )

    @api.depends('hourly_rate')
    def _compute_daily_rate(self):
        for partner in self:
            partner.daily_rate = partner.hourly_rate * 7 if partner.hourly_rate else 0.0

    # =====================
    # DOCUMENTS ET HABILITATIONS (US-D1)
    # =====================
    trainer_document_ids = fields.One2many(
        'lms_resources_trainers.trainer_document',
        'trainer_id',
        string='Documents administratifs'
    )

    document_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_document_count',
        compute_sudo=True
    )

    mandatory_documents_complete = fields.Boolean(
        string='Documents obligatoires complets',
        compute='_compute_mandatory_documents_complete',
        store=True,
        compute_sudo=True
    )

    expiring_documents_count = fields.Integer(
        string='Documents expirant bientôt',
        compute='_compute_expiring_documents_count',
        compute_sudo=True
    )

    # Méthodes de calcul séparées pour éviter l'incohérence
    @api.depends('trainer_document_ids')
    def _compute_document_count(self):
        """Calcule le nombre de documents"""
        for partner in self:
            if not partner.is_trainer:
                partner.document_count = 0
            else:
                partner.document_count = len(partner.trainer_document_ids)

    @api.depends('trainer_document_ids', 'trainer_document_ids.state',
                 'trainer_document_ids.document_type_id')
    def _compute_mandatory_documents_complete(self):
        """Vérifie si tous les documents obligatoires sont valides"""
        for partner in self:
            if not partner.is_trainer:
                partner.mandatory_documents_complete = False
                continue

            mandatory_types = self.env['lms_resources_trainers.trainer_document_type'].search([
                ('is_mandatory', '=', True)
            ])

            if not mandatory_types:
                partner.mandatory_documents_complete = True
                continue

            valid_mandatory = partner.trainer_document_ids.filtered(
                lambda d: d.state == 'valid' and d.document_type_id.is_mandatory
            )
            partner.mandatory_documents_complete = len(valid_mandatory) >= len(mandatory_types)

    @api.depends('trainer_document_ids', 'trainer_document_ids.expiry_date',
                 'trainer_document_ids.state')
    def _compute_expiring_documents_count(self):
        """Compte les documents expirant dans 30 jours"""
        for partner in self:
            if not partner.is_trainer:
                partner.expiring_documents_count = 0
                continue

            today = fields.Date.today()
            threshold = today + timedelta(days=30)
            expiring = partner.trainer_document_ids.filtered(
                lambda d: d.expiry_date and
                          today <= d.expiry_date <= threshold and
                          d.state == 'valid'
            )
            partner.expiring_documents_count = len(expiring)

    # =====================
    # DISPONIBILITÉS (nouveau)
    # =====================
    availability_ids = fields.One2many(
        'lms_resources_trainers.trainer_availability',
        'trainer_id',
        string='Disponibilités hebdomadaires'
    )

    availability_status = fields.Selection([
        ('available', 'Disponible'),
        ('busy', 'Occupé'),
        ('on_leave', 'En congé'),
        ('unavailable', 'Indisponible')
    ], string='Statut disponibilité', default='available', tracking=True)

    # =====================
    # STATISTIQUES FORMATIONS (nouveau)
    # =====================
    training_session_count = fields.Integer(
        string='Sessions animées',
        compute='_compute_training_stats',
        compute_sudo=True
    )

    average_training_rating = fields.Float(
        string='Note moyenne',
        digits=(3, 2),
        compute='_compute_training_stats',
        compute_sudo=True
    )

    @api.depends('is_trainer')
    def _compute_training_stats(self):
        """Calcule statistiques formations"""
        for partner in self:
            if not partner.is_trainer:
                partner.training_session_count = 0
                partner.average_training_rating = 0.0
                continue

            # Compter sessions via slide.channel
            channels = self.env['slide.channel'].search([
                ('trainer_partner_id', '=', partner.id)
            ])
            partner.training_session_count = len(channels)

            # Note moyenne (placeholder - à implémenter avec les évaluations)
            partner.average_training_rating = 0.0

    # =====================
    # ARCHIVAGE ET RGPD (nouveau)
    # =====================
    trainer_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('archived', 'Archivé')
    ], string='Statut formateur', default='draft', tracking=True)

    activation_date = fields.Date(string="Date d'activation", tracking=True)

    # =====================
    # CONTRAINTES
    # =====================
    @api.constrains('is_trainer', 'trainer_document_ids')
    def _check_trainer_mandatory_documents(self):
        """Vérifie documents obligatoires pour activation"""
        for partner in self:
            if partner.trainer_state == 'active' and not partner.mandatory_documents_complete:
                raise ValidationError(_(
                    'Le formateur "%s" ne peut pas être activé. '
                    'Tous les documents obligatoires doivent être valides.'
                ) % partner.name)

    # =====================
    # ACTIONS
    # =====================
    def action_activate_trainer(self):
        """Active le formateur après validation documents"""
        for partner in self:
            if not partner.is_trainer:
                raise ValidationError(_('Ce contact n\'est pas un formateur.'))

            if not partner.mandatory_documents_complete:
                raise ValidationError(_(
                    'Documents obligatoires incomplets.'
                ))

            partner.write({
                'trainer_state': 'active',
                'activation_date': fields.Date.today(),
            })

    def action_view_documents(self):
        """Ouvre documents du formateur"""
        self.ensure_one()
        return {
            'name': _('Documents - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'lms_resources_trainers.trainer_document',
            'view_mode': 'tree,form',
            'domain': [('trainer_id', '=', self.id)],
            'context': {'default_trainer_id': self.id}
        }

    def action_view_availability(self):
        """Ouvre disponibilités"""
        self.ensure_one()
        return {
            'name': _('Disponibilités - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'lms_resources_trainers.trainer_availability',
            'view_mode': 'tree,form',
            'domain': [('trainer_id', '=', self.id)],
            'context': {'default_trainer_id': self.id}
        }

    # =====================
    # CRON JOBS
    # =====================
    @api.model
    def _cron_clean_inactive_trainers(self):
        """Archive formateurs inactifs > 90 jours"""
        three_months_ago = fields.Date.today() - timedelta(days=90)

        inactive = self.search([
            ('is_trainer', '=', True),
            ('trainer_state', '=', 'inactive'),
            ('last_activity_date', '<=', three_months_ago)
        ])

        for trainer in inactive:
            trainer.write({'trainer_state': 'archived'})
            trainer.trainer_document_ids.write({'state': 'archived'})

        return len(inactive)


# =====================
# MODÈLES LIÉS (US-D1)
# =====================

class TrainerDocument(models.Model):
    """Documents formateur (CV, diplômes, certifications)"""
    _name = 'lms_resources_trainers.trainer_document'
    _description = 'Document formateur'
    _inherit = ['mail.thread']
    _order = 'expiry_date, document_type_id'

    trainer_id = fields.Many2one(
        'res.partner',
        string='Formateur',
        required=True,
        ondelete='cascade',
        domain=[('is_trainer', '=', True)]
    )

    document_type_id = fields.Many2one(
        'lms_resources_trainers.trainer_document_type',
        string='Type de document',
        required=True
    )

    name = fields.Char(string='Nom du document', required=True, tracking=True)

    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Fichier',
        required=True,
        ondelete='cascade'
    )

    issue_date = fields.Date(string="Date d'émission", tracking=True)
    expiry_date = fields.Date(string="Date d'expiration", tracking=True)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('valid', 'Valide'),
        ('expired', 'Expiré'),
        ('archived', 'Archivé')
    ], string='Statut', default='draft', tracking=True)

    days_to_expiry = fields.Integer(
        string='Jours avant expiration',
        compute='_compute_days_to_expiry'
    )

    is_expiring_soon = fields.Boolean(
        string='Expire bientôt',
        compute='_compute_days_to_expiry'
    )

    notes = fields.Text(string='Notes')

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        """Calcule jours avant expiration"""
        today = fields.Date.today()
        for doc in self:
            if doc.expiry_date:
                delta = doc.expiry_date - today
                doc.days_to_expiry = delta.days
                doc.is_expiring_soon = 0 < delta.days <= 30
            else:
                doc.days_to_expiry = 0
                doc.is_expiring_soon = False

    def action_validate(self):
        """Valide le document"""
        self.write({'state': 'valid'})

    @api.model
    def _cron_check_document_expiry(self):
        """Marque documents expirés"""
        today = fields.Date.today()

        expired = self.search([
            ('expiry_date', '<', today),
            ('state', '=', 'valid')
        ])
        expired.write({'state': 'expired'})

        return len(expired)


class TrainerDocumentType(models.Model):
    """Types de documents formateur"""
    _name = 'lms_resources_trainers.trainer_document_type'
    _description = 'Type de document formateur'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Séquence', default=10)

    is_mandatory = fields.Boolean(
        string='Obligatoire',
        default=False,
        help="Document obligatoire pour activer un formateur"
    )

    has_expiry_date = fields.Boolean(
        string="A une date d'expiration",
        default=False
    )

    validity_duration = fields.Integer(
        string='Durée de validité (mois)',
        default=12
    )

    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code doit être unique !'),
    ]


class TrainerAvailability(models.Model):
    """Disponibilités hebdomadaires formateur"""
    _name = 'lms_resources_trainers.trainer_availability'
    _description = 'Disponibilité formateur'
    _order = 'day_of_week, start_time'

    trainer_id = fields.Many2one(
        'res.partner',
        string='Formateur',
        required=True,
        ondelete='cascade',
        domain=[('is_trainer', '=', True)]
    )

    day_of_week = fields.Selection([
        ('0', 'Lundi'),
        ('1', 'Mardi'),
        ('2', 'Mercredi'),
        ('3', 'Jeudi'),
        ('4', 'Vendredi'),
        ('5', 'Samedi'),
        ('6', 'Dimanche')
    ], string='Jour', required=True)

    start_time = fields.Float(
        string='Heure début',
        required=True,
        help="Heure décimale (ex: 9.5 = 9h30)"
    )

    end_time = fields.Float(
        string='Heure fin',
        required=True,
        help="Heure décimale (ex: 17.5 = 17h30)"
    )

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for availability in self:
            if availability.start_time >= availability.end_time:
                raise ValidationError(_("L'heure de début doit être avant l'heure de fin."))

            if availability.start_time < 0 or availability.end_time > 24:
                raise ValidationError(_("Les heures doivent être entre 0 et 24."))