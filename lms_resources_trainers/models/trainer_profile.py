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
    
    # Champs de base
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
        readonly=False
    )
    
    email = fields.Char(
        string='Email',
        related='partner_id.email',
        store=True,
        readonly=False
    )
    
    phone = fields.Char(
        string='Téléphone',
        related='partner_id.phone',
        store=True,
        readonly=False
    )
    
    # Informations professionnelles
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
    
    # SOLUTION: Relation Many2many SIMPLIFIÉE
    skills_ids = fields.Many2many(
        'lms_public_info.trainer_skill',
        string='Compétences',
        tracking=True
    )
    
    # Tarification et disponibilité
    hourly_rate = fields.Float(
        string='Tarif horaire (€)',
        tracking=True
    )
    
    daily_rate = fields.Float(
        string='Tarif journalier (€)',
        compute='_compute_daily_rate',
        store=True
    )
    
    availability_ids = fields.One2many(
        'lms_resources_trainers.trainer_availability',
        'trainer_id',
        string='Disponibilités'
    )
    
    # Documents
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
    
    # Historique et statistiques
    training_count = fields.Integer(
        string='Nombre de formations',
        compute='_compute_training_stats'
    )
    
    last_training_date = fields.Date(
        string='Dernière formation',
        compute='_compute_training_stats'
    )
    
    average_rating = fields.Float(
        string='Note moyenne',
        digits=(3, 2),
        compute='_compute_training_stats'
    )
    
    # Statut et dates
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
        tracking=True
    )
    
    # Liens avec autres modèles
    training_ids = fields.One2many(
        'calendar.event',
        'trainer_id',
        string='Formations attribuées'
    )
    
    evaluation_ids = fields.One2many(
        'survey.user_input',
        'trainer_id',
        string='Évaluations'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )
    
    # Méthodes de calcul
    @api.depends('hourly_rate')
    def _compute_daily_rate(self):
        for trainer in self:
            trainer.daily_rate = trainer.hourly_rate * 7
    
    @api.depends('document_ids', 'document_ids.document_type_id', 'document_ids.state')
    def _compute_documents_status(self):
        for trainer in self:
            mandatory_types = self.env['lms_resources_trainers.trainer_document_type'].search([
                ('is_mandatory', '=', True)
            ])
            
            completed_types = trainer.document_ids.filtered(
                lambda d: d.document_type_id in mandatory_types and d.state == 'valid'
            ).mapped('document_type_id')
            
            trainer.mandatory_documents_complete = len(completed_types) >= len(mandatory_types)
    
    @api.depends('training_ids', 'evaluation_ids')
    def _compute_training_stats(self):
        for trainer in self:
            trainings = trainer.training_ids.filtered(lambda t: t.active)
            trainer.training_count = len(trainings)
            
            if trainings:
                trainer.last_training_date = max(trainings.mapped('start_date'))
            
            evaluations = trainer.evaluation_ids.filtered(
                lambda e: e.scoring_percentage >= 0 and e.state == 'done'
            )
            if evaluations:
                trainer.average_rating = sum(e.scoring_percentage for e in evaluations) / len(evaluations)
            else:
                trainer.average_rating = 0.0
    
    # Contraintes
    @api.constrains('hourly_rate')
    def _check_hourly_rate(self):
        for trainer in self:
            if trainer.hourly_rate < 0:
                raise ValidationError(_('Le tarif horaire doit être positif.'))
    
    # Méthodes d'action
    def action_activate(self):
        """Activer le formateur"""
        for trainer in self:
            if not trainer.mandatory_documents_complete:
                raise UserError(_('Tous les documents obligatoires doivent être valides avant activation.'))
            
            trainer.write({
                'state': 'active',
                'activation_date': fields.Date.today(),
                'last_activity_date': fields.Date.today()
            })
    
    def action_deactivate(self):
        """Désactiver le formateur"""
        self.write({'state': 'inactive'})
    
    def action_archive(self):
        """Archiver le formateur après 3 mois d'inactivité"""
        for trainer in self:
            if trainer.state == 'inactive' and trainer.last_activity_date:
                inactivity_period = (fields.Date.today() - trainer.last_activity_date).days
                if inactivity_period >= 90:
                    trainer.write({'state': 'archived'})
                    trainer._send_inactive_notification()
    
    def _send_inactive_notification(self):
        """Envoyer une notification d'inactivité"""
        template = self.env.ref('lms_resources_trainers.mail_template_trainer_inactive')
        for trainer in self:
            template.send_mail(trainer.id, force_send=True)
    
    # Méthode cron
    @api.model
    def _cron_clean_inactive_trainers(self):
        """Supprimer les formateurs inactifs depuis plus de 3 mois"""
        three_months_ago = fields.Date.today() - timedelta(days=90)
        inactive_trainers = self.search([
            ('state', '=', 'inactive'),
            ('last_activity_date', '<', three_months_ago)
        ])
        
        for trainer in inactive_trainers:
            trainer.action_archive()
        
        _logger.info(f'{len(inactive_trainers)} formateurs archivés pour inactivité.')
