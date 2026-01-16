# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class Competency(models.Model):
    _name = 'lms_trainers_competency.competency'
    _description = 'Compétence'
    _order = 'name'

    name = fields.Char(string='Nom', required=True)
    competency_type_id = fields.Many2one(
        'lms_trainers_competency.competency_type',
        string='Type de compétence'
    )
    description = fields.Text(string='Description')
    validity_duration = fields.Integer(
        string='Durée de validité (mois)',
        default=12,
        help='Durée en mois avant qu\'un renouvellement soit nécessaire'
    )
    renewal_ids = fields.One2many(
        'lms_trainers_competency.competency_renewal',
        'competency_id',
        string='Renouvellements'
    )


class CompetencyType(models.Model):
    _name = 'lms_trainers_competency.competency_type'
    _description = 'Type de compétence'

    name = fields.Char(string='Nom', required=True)
    description = fields.Text(string='Description')


class CompetencyRenewal(models.Model):
    _name = 'lms_trainers_competency.competency_renewal'
    _description = 'Renouvellement de compétence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'renewal_date'

    # Identification
    name = fields.Char(
        string='Référence',
        default=lambda self: _('Nouveau renouvellement'),
        required=True
    )

    competency_id = fields.Many2one(
        'lms_trainers_competency.competency',
        string='Compétence',
        required=True,
        tracking=True
    )

    trainer_id = fields.Many2one(
        'lms_resources_trainers.trainer_profile',
        string='Formateur',
        required=True,
        tracking=True
    )

    # Dates
    creation_date = fields.Date(
        string='Date de création',
        default=fields.Date.today,
        readonly=True
    )

    renewal_date = fields.Date(
        string='Date de renouvellement',
        required=True,
        tracking=True
    )

    completion_date = fields.Date(
        string='Date de réalisation',
        tracking=True
    )

    days_until_renewal = fields.Integer(
        string='Jours restants',
        compute='_compute_days_until_renewal',
        store=True
    )

    # Responsable et évaluation
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True
    )

    evaluation_method = fields.Selection([
        ('training', 'Formation'),
        ('assessment', 'Évaluation'),
        ('certification', 'Certification'),
        ('experience', 'Validation par l\'expérience'),
        ('other', 'Autre')
    ], string='Méthode d\'évaluation', tracking=True)

    evaluation_details = fields.Text(string='Détails de l\'évaluation')

    result = fields.Selection([
        ('passed', 'Réussi'),
        ('failed', 'Échoué'),
        ('pending', 'En attente')
    ], string='Résultat', tracking=True)

    score = fields.Float(string='Score', digits=(3, 2))

    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifié'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('overdue', 'En retard')
    ], string='Statut', default='draft', tracking=True)

    # Documents
    proof_document = fields.Many2one(
        'ir.attachment',
        string='Justificatif'
    )

    notes = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    # Méthodes de calcul
    @api.depends('renewal_date')
    def _compute_days_until_renewal(self):
        today = fields.Date.today()
        for renewal in self:
            if renewal.renewal_date:
                delta = renewal.renewal_date - today
                renewal.days_until_renewal = delta.days
            else:
                renewal.days_until_renewal = 0

    # Contraintes
    @api.constrains('renewal_date')
    def _check_renewal_date(self):
        for renewal in self:
            if renewal.renewal_date and renewal.renewal_date < fields.Date.today():
                renewal.state = 'overdue'

    # Méthodes d'action
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nouveau renouvellement')) == _('Nouveau renouvellement'):
            vals['name'] = self.env['ir.sequence'].next_by_code('lms.competency.renewal') or _('Nouveau renouvellement')
        return super().create(vals)

    def action_plan(self):
        """Planifier le renouvellement"""
        for renewal in self:
            renewal.write({'state': 'planned'})

    def action_start(self):
        """Démarrer le renouvellement"""
        for renewal in self:
            renewal.write({'state': 'in_progress'})

    def action_complete(self, result='passed', score=0.0):
        """Compléter le renouvellement"""
        for renewal in self:
            renewal.write({
                'state': 'completed',
                'completion_date': fields.Date.today(),
                'result': result,
                'score': score
            })

    def action_cancel(self):
        """Annuler le renouvellement"""
        self.write({'state': 'cancelled'})

    # Méthodes cron
    @api.model
    def _cron_check_renewal_due(self):
        """Vérifier les renouvellements dus"""
        today = fields.Date.today()
        thirty_days_later = today + timedelta(days=30)

        # Renouvellements à venir (dans les 30 jours)
        upcoming_renewals = self.search([
            ('state', 'in', ['draft', 'planned']),
            ('renewal_date', '<=', thirty_days_later),
            ('renewal_date', '>=', today)
        ])

        for renewal in upcoming_renewals:
            # Envoyer notification
            template = self.env.ref('lms_trainers_competency.mail_template_competency_renewal_due')
            template.send_mail(renewal.id, force_send=True)

            # Créer activité
            renewal.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=renewal.renewal_date,
                user_id=renewal.responsible_id.id,
                summary=f'Renouvellement de compétence: {renewal.competency_id.name}',
                note=f'Le renouvellement de la compétence {renewal.competency_id.name} pour {renewal.trainer_id.name} est prévu pour le {renewal.renewal_date}'
            )

    @api.model
    def _cron_schedule_renewal_activities(self):
        """Planifier les activités de renouvellement annuelles"""
        # Pour chaque formateur actif, créer des activités de renouvellement pour l'année à venir
        active_trainers = self.env['lms_resources_trainers.trainer_profile'].search([
            ('state', '=', 'active')
        ])

        for trainer in active_trainers:
            # Créer un renouvellement pour chaque compétence du formateur
            for skill in trainer.skills_ids:
                renewal_date = fields.Date.today() + timedelta(days=365)  # Dans un an

                self.create({
                    'competency_id': skill.id,  # On suppose que les compétences sont liées
                    'trainer_id': trainer.id,
                    'renewal_date': renewal_date,
                    'responsible_id': self.env.user.id,
                    'state': 'planned',
                    'evaluation_method': 'assessment'
                })