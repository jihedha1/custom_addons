# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class TrainerProfile(models.Model):
    _name = 'lms_resources_trainers.trainer_profile'
    _description = 'Profil formateur'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # =====================
    # CHAMPS DE BASE
    # =====================
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        ondelete='cascade',
        domain=[('is_trainer', '=', True)],
        tracking=True
    )

    name = fields.Char(
        string='Nom',
        related='partner_id.name',
        store=True,
        readonly=True
    )

    email = fields.Char(
        string='Email',
        related='partner_id.email',
        store=True,
        readonly=True
    )

    phone = fields.Char(
        string='Téléphone',
        related='partner_id.phone',
        store=True,
        readonly=True
    )

    # =====================
    # INFORMATIONS PROFESSIONNELLES
    # =====================
    specialization = fields.Char(
        string='Spécialisation',
        required=True,
        tracking=True
    )

    years_experience = fields.Integer(
        string='Années d\'expérience',
        tracking=True
    )

    biography = fields.Html(
        string='Biographie',
        tracking=True
    )

    # CORRECTION CRITIQUE : Utiliser le modèle de lms_public_info
    competency_ids = fields.Many2many(
        'lms_public_info.trainer_competency',
        'trainer_profile_competency_rel',
        'profile_id',
        'competency_id',
        string='Compétences',
        tracking=True,
        help='Compétences du formateur (depuis lms_public_info)'
    )

    # =====================
    # TARIFICATION
    # =====================
    hourly_rate = fields.Float(
        string='Tarif horaire (€)',
        tracking=True
    )

    daily_rate = fields.Float(
        string='Tarif journalier (€)',
        compute='_compute_daily_rate',
        store=True
    )

    @api.depends('hourly_rate')
    def _compute_daily_rate(self):
        for trainer in self:
            trainer.daily_rate = trainer.hourly_rate * 7

    # =====================
    # DISPONIBILITÉS
    # =====================
    availability_ids = fields.One2many(
        'lms_resources_trainers.trainer_availability',
        'trainer_id',
        string='Disponibilités'
    )

    # =====================
    # DOCUMENTS ET HABILITATIONS
    # =====================
    document_ids = fields.One2many(
        'lms_resources_trainers.trainer_document',
        'trainer_id',
        string='Documents'
    )

    mandatory_documents_complete = fields.Boolean(
        string='Documents obligatoires complets',
        compute='_compute_documents_status',
        store=True
    )

    expiring_documents_count = fields.Integer(
        string='Documents expirant bientôt',
        compute='_compute_expiring_documents'
    )

    @api.depends('document_ids', 'document_ids.state', 'document_ids.document_type_id')
    def _compute_documents_status(self):
        """Vérifie si tous les documents obligatoires sont présents"""
        for trainer in self:
            # Récupérer les types obligatoires
            mandatory_types = self.env['lms_resources_trainers.trainer_document_type'].search([
                ('is_mandatory', '=', True)
            ])

            # Vérifier documents valides
            valid_docs = trainer.document_ids.filtered(
                lambda d: d.state == 'valid' and d.document_type_id.is_mandatory
            )

            trainer.mandatory_documents_complete = len(valid_docs) >= len(mandatory_types)

    @api.depends('document_ids', 'document_ids.expiry_date')
    def _compute_expiring_documents(self):
        """Compte les documents expirant dans les 30 prochains jours"""
        for trainer in self:
            today = fields.Date.today()
            threshold = today + timedelta(days=30)

            expiring = trainer.document_ids.filtered(
                lambda d: d.expiry_date and today <= d.expiry_date <= threshold
            )

            trainer.expiring_documents_count = len(expiring)

    # =====================
    # STATISTIQUES
    # =====================
    training_count = fields.Integer(
        string='Nombre de formations',
        compute='_compute_training_stats'
    )

    last_training_date = fields.Date(
        string='Dernière formation',
        compute='_compute_training_stats',
        store=True
    )

    average_rating = fields.Float(
        string='Note moyenne',
        digits=(3, 2),
        compute='_compute_training_stats'
    )

    @api.depends('partner_id')
    def _compute_training_stats(self):
        for trainer in self:
            # Chercher les formations liées via slide.channel.trainer_id
            channels = self.env['slide.channel'].search([
                ('trainer_partner_id', '=', trainer.partner_id.id)
            ])

            trainer.training_count = len(channels)

            # Dernière session via calendar.event
            events = self.env['calendar.event'].search([
                ('partner_ids', 'in', [trainer.partner_id.id])
            ], order='start desc', limit=1)

            trainer.last_training_date = events[0].start.date() if events else False

            # Note moyenne depuis survey.user_input
            # Note: Vous devrez ajouter un champ trainer_id dans survey.user_input
            trainer.average_rating = 0.0

    # =====================
    # STATUT
    # =====================
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('archived', 'Archivé')
    ], string='Statut', default='draft', tracking=True)

    activation_date = fields.Date(
        string='Date d\'activation',
        tracking=True
    )

    last_activity_date = fields.Date(
        string='Dernière activité',
        compute='_compute_last_activity',
        store=True
    )

    inactivity_days = fields.Integer(
        string='Jours d\'inactivité',
        compute='_compute_inactivity_days'
    )

    @api.depends('last_training_date', 'write_date')
    def _compute_last_activity(self):
        for trainer in self:
            dates = [
                trainer.write_date.date() if trainer.write_date else False,
                trainer.last_training_date
            ]
            valid_dates = [d for d in dates if d]
            trainer.last_activity_date = max(valid_dates) if valid_dates else False

    @api.depends('last_activity_date')
    def _compute_inactivity_days(self):
        for trainer in self:
            if trainer.last_activity_date:
                delta = fields.Date.today() - trainer.last_activity_date
                trainer.inactivity_days = delta.days
            else:
                trainer.inactivity_days = 0

    # =====================
    # COMPTEURS POUR STAT BUTTONS
    # =====================
    document_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_document_count'
    )

    @api.depends('document_ids')
    def _compute_document_count(self):
        for trainer in self:
            trainer.document_count = len(trainer.document_ids)

    # =====================
    # COMPANY
    # =====================
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    # =====================
    # CONTRAINTES
    # =====================
    @api.constrains('hourly_rate')
    def _check_hourly_rate(self):
        for trainer in self:
            if trainer.hourly_rate < 0:
                raise ValidationError(_('Le tarif horaire doit être positif.'))

    # =====================
    # ACTIONS
    # =====================
    def action_activate(self):
        """Activer le formateur"""
        for trainer in self:
            if not trainer.mandatory_documents_complete:
                raise UserError(_(
                    'Tous les documents obligatoires doivent être valides avant activation.'
                ))

            trainer.write({
                'state': 'active',
                'activation_date': fields.Date.today(),
            })

    def action_deactivate(self):
        """Désactiver le formateur"""
        self.write({'state': 'inactive'})

    def action_archive(self):
        """Archiver après 3 mois d'inactivité"""
        for trainer in self:
            if trainer.inactivity_days >= 90:
                trainer.write({'state': 'archived'})
                trainer._anonymize_personal_data()

    def _anonymize_personal_data(self):
        """Anonymise les données pour RGPD"""
        for trainer in self:
            trainer.document_ids.write({'state': 'archived'})
            _logger.info(f'Formateur {trainer.name} archivé et anonymisé')

    def action_view_trainings(self):
        """Voir les formations"""
        self.ensure_one()
        return {
            'name': _('Formations de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel',
            'view_mode': 'tree,form',
            'domain': [('trainer_partner_id', '=', self.partner_id.id)],
        }

    # =====================
    # CRON
    # =====================
    @api.model
    def _cron_clean_inactive_trainers(self):
        """Archiver les formateurs inactifs > 90 jours"""
        three_months_ago = fields.Date.today() - timedelta(days=90)

        inactive_trainers = self.search([
            ('state', '=', 'inactive'),
            ('last_activity_date', '<=', three_months_ago)
        ])

        for trainer in inactive_trainers:
            trainer.action_archive()

        _logger.info(f'{len(inactive_trainers)} formateurs archivés')


# =====================
# MODÈLES LIÉS
# =====================

class TrainerDocument(models.Model):
    _name = 'lms_resources_trainers.trainer_document'
    _description = 'Document formateur'
    _inherit = ['mail.thread']

    trainer_id = fields.Many2one(
        'lms_resources_trainers.trainer_profile',
        string='Formateur',
        required=True,
        ondelete='cascade'
    )

    document_type_id = fields.Many2one(
        'lms_resources_trainers.trainer_document_type',
        string='Type de document',
        required=True
    )

    name = fields.Char(string='Nom', required=True)

    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Fichier',
        required=True
    )

    issue_date = fields.Date(string='Date d\'émission')
    expiry_date = fields.Date(string='Date d\'expiration')

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('valid', 'Valide'),
        ('expired', 'Expiré'),
        ('archived', 'Archivé')
    ], string='Statut', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    @api.model
    def _cron_check_document_expiry(self):
        """Vérifier les expirations de documents"""
        today = fields.Date.today()
        threshold = today + timedelta(days=30)

        expiring = self.search([
            ('expiry_date', '<=', threshold),
            ('expiry_date', '>=', today),
            ('state', '=', 'valid')
        ])

        for doc in expiring:
            # Créer activité
            doc.trainer_id.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Document {doc.name} expire bientôt',
                note=f'Expiration le {doc.expiry_date}',
                user_id=self.env.user.id
            )


class TrainerDocumentType(models.Model):
    _name = 'lms_resources_trainers.trainer_document_type'
    _description = 'Type de document formateur'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True)
    is_mandatory = fields.Boolean(string='Obligatoire', default=False)
    has_expiry_date = fields.Boolean(string='A une date d\'expiration', default=False)
    validity_duration = fields.Integer(string='Durée de validité (mois)', default=12)


class TrainerAvailability(models.Model):
    _name = 'lms_resources_trainers.trainer_availability'
    _description = 'Disponibilité formateur'

    trainer_id = fields.Many2one(
        'lms_resources_trainers.trainer_profile',
        string='Formateur',
        required=True,
        ondelete='cascade'
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

    start_time = fields.Float(string='Heure début')
    end_time = fields.Float(string='Heure fin')