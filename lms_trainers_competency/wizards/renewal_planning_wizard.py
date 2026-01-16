# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class RenewalPlanningWizard(models.TransientModel):
    _name = 'lms_trainers_competency.renewal_planning_wizard'
    _description = 'Assistant de planification des renouvellements'

    # Champs du wizard
    trainer_ids = fields.Many2many(
        'lms_resources_trainers.trainer_profile',
        string='Formateurs',
        required=True,
        domain="[('state', '=', 'active')]"
    )

    competency_ids = fields.Many2many(
        'lms_trainers_competency.competency',
        string='Compétences',
        required=True
    )

    planning_period = fields.Selection([
        ('30', '30 jours'),
        ('60', '60 jours'),
        ('90', '90 jours'),
        ('180', '6 mois'),
        ('365', '1 an')
    ], string='Période de planification', default='365', required=True)

    start_date = fields.Date(
        string='Date de début',
        default=fields.Date.today,
        required=True
    )

    evaluation_method = fields.Selection([
        ('training', 'Formation'),
        ('assessment', 'Évaluation'),
        ('certification', 'Certification'),
        ('experience', 'Validation par l\'expérience'),
        ('other', 'Autre')
    ], string='Méthode d\'évaluation par défaut', default='assessment')

    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable par défaut',
        default=lambda self: self.env.user
    )

    # Options
    create_activities = fields.Boolean(
        string='Créer des activités',
        default=True
    )

    send_notifications = fields.Boolean(
        string='Envoyer des notifications',
        default=False
    )

    # Méthodes
    @api.onchange('planning_period')
    def _onchange_planning_period(self):
        """Mettre à jour la date de début selon la période"""
        if self.planning_period:
            self.start_date = fields.Date.today()

    def action_plan_renewals(self):
        """Planifier les renouvellements"""
        self.ensure_one()

        Renewal = self.env['lms_trainers_competency.competency_renewal']
        created_renewals = []

        for trainer in self.trainer_ids:
            for competency in self.competency_ids:
                # Calculer la date de renouvellement
                renewal_date = self.start_date + timedelta(days=int(self.planning_period))

                # Créer le renouvellement
                renewal = Renewal.create({
                    'competency_id': competency.id,
                    'trainer_id': trainer.id,
                    'renewal_date': renewal_date,
                    'responsible_id': self.responsible_id.id,
                    'evaluation_method': self.evaluation_method,
                    'state': 'planned'
                })

                created_renewals.append(renewal.id)

                # Créer une activité si demandé
                if self.create_activities:
                    renewal.activity_schedule(
                        'mail.mail_activity_data_todo',
                        date_deadline=renewal_date - timedelta(days=30),  # Rappel 30 jours avant
                        user_id=self.responsible_id.id,
                        summary=f'Renouvellement planifié: {competency.name}',
                        note=f'Renouvellement de la compétence {competency.name} pour {trainer.name} prévu le {renewal_date}'
                    )

                # Envoyer notification si demandé
                if self.send_notifications:
                    template = self.env.ref('lms_trainers_competency.mail_template_competency_renewal_due')
                    template.send_mail(renewal.id, force_send=True)

        # Retourner vers les renouvellements créés
        return {
            'name': _('Renouvellements planifiés'),
            'type': 'ir.actions.act_window',
            'res_model': 'lms_trainers_competency.competency_renewal',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_renewals)],
            'context': self.env.context,
        }