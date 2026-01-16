# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TrainerTrainingType(models.Model):
    _name = 'lms_trainers_competency.trainer_training_type'
    _description = 'Type de formation pour formateur'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')


class TrainerTraining(models.Model):
    _name = 'lms_trainers_competency.trainer_training'
    _description = 'Formation de formateur'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    # Identification
    name = fields.Char(
        string='Nom de la formation',
        required=True,
        tracking=True
    )

    trainer_id = fields.Many2one(
        'lms_resources_trainers.trainer_profile',
        string='Formateur',
        required=True,
        tracking=True
    )

    training_type_id = fields.Many2one(
        'lms_trainers_competency.trainer_training_type',
        string='Type de formation',
        tracking=True
    )

    # Dates
    start_date = fields.Date(
        string='Date de début',
        required=True,
        tracking=True
    )

    end_date = fields.Date(
        string='Date de fin',
        required=True,
        tracking=True
    )

    duration_days = fields.Integer(
        string='Durée (jours)',
        compute='_compute_duration',
        store=True
    )

    # Organisation
    organizer = fields.Char(
        string='Organisme',
        required=True,
        tracking=True
    )

    location = fields.Char(string='Lieu')

    cost = fields.Float(
        string='Coût (€)',
        tracking=True
    )

    funded_by = fields.Selection([
        ('company', 'Entreprise'),
        ('trainer', 'Formateur'),
        ('mixed', 'Mixte'),
        ('other', 'Autre')
    ], string='Financé par', default='company', tracking=True)

    # Contenu et résultats
    objectives = fields.Text(string='Objectifs')

    content = fields.Html(string='Contenu')

    skills_developed = fields.Text(string='Compétences développées')

    certificate_obtained = fields.Boolean(string='Certificat obtenu')

    certificate_document = fields.Many2one(
        'ir.attachment',
        string='Document du certificat'
    )

    evaluation_score = fields.Float(
        string='Note d\'évaluation',
        digits=(3, 2)
    )

    feedback = fields.Text(string='Retour du formateur')

    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', tracking=True)

    completion_date = fields.Date(string='Date de complétion')

    # Documents
    training_materials = fields.Many2many(
        'ir.attachment',
        string='Supports de formation'
    )

    notes = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    # Méthodes de calcul
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for training in self:
            if training.start_date and training.end_date:
                delta = training.end_date - training.start_date
                training.duration_days = delta.days + 1  # Inclusif
            else:
                training.duration_days = 0

    # Contraintes
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for training in self:
            if training.start_date and training.end_date and training.start_date > training.end_date:
                raise ValidationError(_('La date de début doit être avant la date de fin.'))

    @api.constrains('cost')
    def _check_cost(self):
        for training in self:
            if training.cost < 0:
                raise ValidationError(_('Le coût ne peut pas être négatif.'))

    # Méthodes d'action
    def action_plan(self):
        """Planifier la formation"""
        for training in self:
            training.write({'state': 'planned'})

            # Envoyer notification
            training._send_scheduled_notification()

    def action_start(self):
        """Démarrer la formation"""
        self.write({'state': 'in_progress'})

    def action_complete(self):
        """Terminer la formation"""
        for training in self:
            training.write({
                'state': 'completed',
                'completion_date': fields.Date.today()
            })

    def action_cancel(self):
        """Annuler la formation"""
        self.write({'state': 'cancelled'})

    def _send_scheduled_notification(self):
        """Envoyer une notification de planification"""
        template = self.env.ref('lms_trainers_competency.mail_template_trainer_training_scheduled')
        for training in self:
            template.send_mail(training.id, force_send=True)