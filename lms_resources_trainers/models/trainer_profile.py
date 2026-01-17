# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ResPartnerTrainerExtended(models.Model):
    """Extension du modèle res.partner pour les formateurs (Resources & Documents)"""
    _inherit = 'res.partner'

    # =====================
    # TARIFICATION (ajout aux champs existants de lms_public_info)
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
        help="Calculé automatiquement : tarif horaire × 7"
    )

    @api.depends('hourly_rate')
    def _compute_daily_rate(self):
        for partner in self:
            partner.daily_rate = partner.hourly_rate * 7 if partner.hourly_rate else 0.0

    # =====================
    # DISPONIBILITÉS
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
    ], string='Statut de disponibilité', default='available', tracking=True)

    # =====================
    # DOCUMENTS ET HABILITATIONS (refonte)
    # =====================
    trainer_document_ids = fields.One2many(
        'lms_resources_trainers.trainer_document',
        'trainer_id',
        string='Documents administratifs',
        help="CV, diplômes, certifications, habilitations"
    )

    document_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_document_stats'
    )

    mandatory_documents_complete = fields.Boolean(
        string='Documents obligatoires complets',
        compute='_compute_document_stats',
        store=True,
        help="Tous les documents obligatoires sont-ils présents et valides ?"
    )

    expiring_documents_count = fields.Integer(
        string='Documents expirant bientôt',
        compute='_compute_document_stats',
        help="Nombre de documents expirant dans les 30 jours"
    )

    @api.depends('trainer_document_ids', 'trainer_document_ids.state',
                 'trainer_document_ids.document_type_id', 'trainer_document_ids.expiry_date')
    def _compute_document_stats(self):
        """Calcule les statistiques sur les documents"""
        for partner in self:
            if not partner.is_trainer:
                partner.document_count = 0
                partner.mandatory_documents_complete = False
                partner.expiring_documents_count = 0
                continue

            docs = partner.trainer_document_ids
            partner.document_count = len(docs)

            # Documents obligatoires
            mandatory_types = self.env['lms_resources_trainers.trainer_document_type'].search([
                ('is_mandatory', '=', True)
            ])
            valid_mandatory = docs.filtered(
                lambda d: d.state == 'valid' and d.document_type_id.is_mandatory
            )
            partner.mandatory_documents_complete = len(valid_mandatory) >= len(mandatory_types)

            # Documents expirant bientôt
            today = fields.Date.today()
            threshold = today + timedelta(days=30)
            expiring = docs.filtered(
                lambda d: d.expiry_date and today <= d.expiry_date <= threshold and d.state == 'valid'
            )
            partner.expiring_documents_count = len(expiring)

    # =====================
    # STATISTIQUES FORMATIONS
    # =====================
    training_session_count = fields.Integer(
        string='Sessions animées',
        compute='_compute_training_stats',
        help="Nombre total de sessions de formation animées"
    )

    last_training_date = fields.Date(
        string='Dernière session',
        compute='_compute_training_stats',
        store=True
    )

    average_training_rating = fields.Float(
        string='Note moyenne',
        digits=(3, 2),
        compute='_compute_training_stats',
        help="Note moyenne des évaluations de sessions"
    )

    @api.depends('is_trainer')
    def _compute_training_stats(self):
        """Calcule les statistiques de formation"""
        for partner in self:
            if not partner.is_trainer:
                partner.training_session_count = 0
                partner.last_training_date = False
                partner.average_training_rating = 0.0
                continue

            # Sessions via slide.channel
            channels = self.env['slide.channel'].search([
                ('trainer_partner_id', '=', partner.id)
            ])
            partner.training_session_count = len(channels)

            # Dernière session via calendar.event
            events = self.env['calendar.event'].search([
                ('partner_ids', 'in', [partner.id]),
                ('start', '<=', fields.Datetime.now())
            ], order='start desc', limit=1)
            partner.last_training_date = events[0].start.date() if events else False

            # Note moyenne (placeholder - à implémenter avec survey)
            partner.average_training_rating = 0.0

    # =====================
    # ACTIVITÉ ET ARCHIVAGE
    # =====================
    activation_date = fields.Date(
        string="Date d'activation",
        tracking=True,
        help="Date à laquelle le formateur a été activé"
    )

    inactivity_days = fields.Integer(
        string="Jours d'inactivité",
        compute='_compute_inactivity_days',
        help="Nombre de jours depuis la dernière activité"
    )

    trainer_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('archived', 'Archivé')
    ], string='Statut formateur', default='draft', tracking=True)

    @api.depends('last_activity_date', 'last_training_date')
    def _compute_inactivity_days(self):
        """Calcule les jours d'inactivité"""
        for partner in self:
            if not partner.is_trainer:
                partner.inactivity_days = 0
                continue

            dates = [
                partner.last_activity_date,
                partner.last_training_date
            ]
            valid_dates = [d for d in dates if d]

            if valid_dates:
                last_activity = max(valid_dates)
                delta = fields.Date.today() - last_activity
                partner.inactivity_days = delta.days
            else:
                partner.inactivity_days = 0

    # =====================
    # CONTRAINTES
    # =====================
    @api.constrains('hourly_rate')
    def _check_hourly_rate(self):
        for partner in self:
            if partner.is_trainer and partner.hourly_rate < 0:
                raise ValidationError(_('Le tarif horaire doit être positif.'))

    @api.constrains('is_trainer', 'trainer_document_ids')
    def _check_trainer_mandatory_documents(self):
        """Vérifie que les documents obligatoires sont présents pour activer un formateur"""
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
        """Active le formateur après validation des documents"""
        for partner in self:
            if not partner.is_trainer:
                raise UserError(_('Ce contact n\'est pas marqué comme formateur.'))

            if not partner.mandatory_documents_complete:
                raise UserError(_(
                    'Impossible d\'activer le formateur. '
                    'Les documents obligatoires ne sont pas complets.'
                ))

            partner.write({
                'trainer_state': 'active',
                'activation_date': fields.Date.today(),
            })

            partner.message_post(
                body=_('Formateur activé le %s') % fields.Date.today(),
                subject=_('Activation formateur')
            )

    def action_deactivate_trainer(self):
        """Désactive le formateur"""
        self.write({'trainer_state': 'inactive'})

    def action_archive_trainer(self):
        """Archive le formateur après 90 jours d'inactivité"""
        for partner in self:
            if partner.inactivity_days >= 90:
                partner.write({'trainer_state': 'archived'})
                partner._anonymize_trainer_data()

                _logger.info(f'Formateur {partner.name} archivé après {partner.inactivity_days} jours d\'inactivité')

    def _anonymize_trainer_data(self):
        """Anonymise les données pour RGPD"""
        for partner in self:
            # Archiver les documents
            partner.trainer_document_ids.write({'state': 'archived'})

            # Log RGPD
            partner.message_post(
                body=_('Données anonymisées pour conformité RGPD'),
                subject=_('Archivage RGPD')
            )

    def action_view_documents(self):
        """Ouvre la liste des documents du formateur"""
        self.ensure_one()
        return {
            'name': _('Documents - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'lms_resources_trainers.trainer_document',
            'view_mode': 'tree,form',
            'domain': [('trainer_id', '=', self.id)],
            'context': {'default_trainer_id': self.id}
        }

    def action_view_trainings(self):
        """Ouvre les formations du formateur"""
        self.ensure_one()
        return {
            'name': _('Formations - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel',
            'view_mode': 'tree,form',
            'domain': [('trainer_partner_id', '=', self.id)],
        }

    def action_view_availability(self):
        """Ouvre le calendrier de disponibilité"""
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
        """Nettoie les formateurs inactifs > 90 jours"""
        three_months_ago = fields.Date.today() - timedelta(days=90)

        inactive_trainers = self.search([
            ('is_trainer', '=', True),
            ('trainer_state', '=', 'inactive'),
            ('last_activity_date', '<=', three_months_ago)
        ])

        count = 0
        for trainer in inactive_trainers:
            trainer.action_archive_trainer()
            count += 1

        _logger.info(f'{count} formateurs archivés automatiquement')
        return count

    @api.model
    def _cron_send_expiration_alerts(self):
        """Envoie des alertes pour les documents expirant bientôt"""
        trainers_with_expiring_docs = self.search([
            ('is_trainer', '=', True),
            ('trainer_state', '=', 'active'),
            ('expiring_documents_count', '>', 0)
        ])

        for trainer in trainers_with_expiring_docs:
            # Récupérer les documents expirants
            today = fields.Date.today()
            threshold = today + timedelta(days=30)

            expiring_docs = trainer.trainer_document_ids.filtered(
                lambda d: d.expiry_date and today <= d.expiry_date <= threshold and d.state == 'valid'
            )

            for doc in expiring_docs:
                # Créer une activité
                trainer.activity_schedule(
                    'mail.mail_activity_data_todo',
                    date_deadline=doc.expiry_date - timedelta(days=7),
                    summary=f'Document "{doc.name}" expire bientôt',
                    note=f'Le document {doc.document_type_id.name} expire le {doc.expiry_date}',
                    user_id=self.env.user.id
                )

        _logger.info(f'Alertes envoyées pour {len(trainers_with_expiring_docs)} formateurs')


# =====================
# MODÈLES LIÉS
# =====================

class TrainerDocument(models.Model):
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

    name = fields.Char(
        string='Nom du document',
        required=True,
        tracking=True
    )

    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Fichier',
        required=True,
        ondelete='cascade'
    )

    issue_date = fields.Date(
        string="Date d'émission",
        tracking=True
    )

    expiry_date = fields.Date(
        string="Date d'expiration",
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente de validation'),
        ('valid', 'Valide'),
        ('expired', 'Expiré'),
        ('archived', 'Archivé')
    ], string='Statut', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    days_to_expiry = fields.Integer(
        string='Jours avant expiration',
        compute='_compute_days_to_expiry'
    )

    is_expiring_soon = fields.Boolean(
        string='Expire bientôt',
        compute='_compute_days_to_expiry'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        """Calcule les jours avant expiration"""
        today = fields.Date.today()
        for doc in self:
            if doc.expiry_date:
                delta = doc.expiry_date - today
                doc.days_to_expiry = delta.days
                doc.is_expiring_soon = 0 < delta.days <= 30
            else:
                doc.days_to_expiry = 0
                doc.is_expiring_soon = False

    @api.model
    def create(self, vals):
        """Génère automatiquement le nom si non fourni"""
        if 'name' not in vals or not vals['name']:
            doc_type = self.env['lms_resources_trainers.trainer_document_type'].browse(vals['document_type_id'])
            trainer = self.env['res.partner'].browse(vals['trainer_id'])
            vals['name'] = f"{doc_type.name} - {trainer.name}"

        return super().create(vals)

    def action_validate(self):
        """Valide le document"""
        self.write({'state': 'valid'})

    def action_expire(self):
        """Marque le document comme expiré"""
        self.write({'state': 'expired'})

    @api.model
    def _cron_check_document_expiry(self):
        """Vérifie les expirations et met à jour les statuts"""
        today = fields.Date.today()

        # Marquer comme expirés
        expired = self.search([
            ('expiry_date', '<', today),
            ('state', '=', 'valid')
        ])
        expired.write({'state': 'expired'})

        _logger.info(f'{len(expired)} documents marqués comme expirés')


class TrainerDocumentType(models.Model):
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
        default=12,
        help="Durée en mois entre émission et expiration"
    )

    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code doit être unique !'),
    ]


class TrainerAvailability(models.Model):
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
        help="Heure au format décimal (ex: 9.5 pour 9h30)"
    )

    end_time = fields.Float(
        string='Heure fin',
        required=True,
        help="Heure au format décimal (ex: 17.5 pour 17h30)"
    )

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for availability in self:
            if availability.start_time >= availability.end_time:
                raise ValidationError(_("L'heure de début doit être avant l'heure de fin."))

            if availability.start_time < 0 or availability.end_time > 24:
                raise ValidationError(_("Les heures doivent être entre 0 et 24."))