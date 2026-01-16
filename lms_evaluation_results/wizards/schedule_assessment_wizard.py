# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ScheduleAssessmentWizard(models.TransientModel):
    """
    Assistant pour planifier les évaluations à froid en masse
    """
    # CHANGEMENT : nom du modèle plus court
    _name = 'lms_eval.sched_wizard'
    _description = 'Assistant planification évaluations à froid'

    # Utiliser un nom de champ plus court
    ch_ids = fields.Many2many(
        'slide.channel',
        string='Formations',
        required=True,
        help='Formations pour lesquelles planifier des évaluations'
    )

    survey_30_id = fields.Many2one(
        'survey.survey',
        string='Questionnaire J+30',
        domain="[('is_published', '=', True)]",
        help='Questionnaire pour l\'évaluation à 30 jours'
    )

    survey_90_id = fields.Many2one(
        'survey.survey',
        string='Questionnaire J+90',
        domain="[('is_published', '=', True)]",
        help='Questionnaire pour l\'évaluation à 90 jours'
    )

    create_j30 = fields.Boolean(
        string='Créer évaluations J+30',
        default=True
    )

    create_j90 = fields.Boolean(
        string='Créer évaluations J+90',
        default=True
    )

    partner_ids = fields.Many2many(
        'res.partner',
        string='Participants',
        help='Limiter à ces participants (vide = tous les participants ayant terminé)'
    )

    max_reminders = fields.Integer(
        string='Nombre de rappels',
        default=2,
        help='Nombre maximum de rappels à envoyer'
    )

    reminder_interval_days = fields.Integer(
        string='Intervalle rappels (jours)',
        default=7
    )

    @api.constrains('create_j30', 'create_j90')
    def _check_at_least_one(self):
        """Au moins un type d'évaluation doit être sélectionné"""
        for wizard in self:
            if not wizard.create_j30 and not wizard.create_j90:
                raise ValidationError(_(
                    "Vous devez sélectionner au moins un type d'évaluation (J+30 ou J+90)."
                ))

    @api.constrains('max_reminders')
    def _check_max_reminders(self):
        for wizard in self:
            if wizard.max_reminders < 0 or wizard.max_reminders > 5:
                raise ValidationError(_(
                    "Le nombre de rappels doit être entre 0 et 5."
                ))

    def action_schedule_assessments(self):
        """
        Créer les évaluations pour tous les participants ayant terminé
        """
        self.ensure_one()

        ColdAssessment = self.env['lms_evaluation_results.cold_assessment']
        created_assessments = []

        for channel in self.ch_ids:
            if self.partner_ids:
                partners = self.partner_ids
            else:
                completions = self.env['slide.slide.partner'].search([
                    ('channel_id', '=', channel.id),
                    ('completed', '=', True),
                ])
                partners = completions.mapped('partner_id')

            for partner in partners:
                completion = self.env['slide.slide.partner'].search([
                    ('channel_id', '=', channel.id),
                    ('partner_id', '=', partner.id),
                    ('completed', '=', True),
                ], limit=1, order='x_completion_date desc')

                if not completion or not completion.x_completion_date:
                    continue

                completion_date = completion.x_completion_date

                if self.create_j30:
                    existing = ColdAssessment.search([
                        ('channel_id', '=', channel.id),
                        ('partner_id', '=', partner.id),
                        ('assessment_type', '=', '30_days'),
                    ], limit=1)

                    if not existing:
                        survey = self.survey_30_id or self._get_default_survey('30_days')
                        if survey:
                            assessment = ColdAssessment.create({
                                'channel_id': channel.id,
                                'partner_id': partner.id,
                                'completion_id': completion.id,
                                'completion_date': completion_date,
                                'assessment_type': '30_days',
                                'survey_id': survey.id,
                                'max_reminders': self.max_reminders,
                                'reminder_interval_days': self.reminder_interval_days,
                                'state': 'scheduled',
                            })
                            created_assessments.append(assessment.id)

                if self.create_j90:
                    existing = ColdAssessment.search([
                        ('channel_id', '=', channel.id),
                        ('partner_id', '=', partner.id),
                        ('assessment_type', '=', '90_days'),
                    ], limit=1)

                    if not existing:
                        survey = self.survey_90_id or self._get_default_survey('90_days')
                        if survey:
                            assessment = ColdAssessment.create({
                                'channel_id': channel.id,
                                'partner_id': partner.id,
                                'completion_id': completion.id,
                                'completion_date': completion_date,
                                'assessment_type': '90_days',
                                'survey_id': survey.id,
                                'max_reminders': self.max_reminders,
                                'reminder_interval_days': self.reminder_interval_days,
                                'state': 'scheduled',
                            })
                            created_assessments.append(assessment.id)

        return {
            'name': _('Évaluations planifiées'),
            'type': 'ir.actions.act_window',
            'res_model': 'lms_evaluation_results.cold_assessment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_assessments)],
            'context': self.env.context,
        }

    def _get_default_survey(self, assessment_type):
        """Récupère le questionnaire par défaut"""
        survey = self.env['survey.survey'].search([
            ('title', 'ilike', f'évaluation à froid {assessment_type}'),
            ('is_published', '=', True),
        ], limit=1)

        if not survey:
            survey = self.env['survey.survey'].search([
                ('is_published', '=', True)
            ], limit=1)

        return survey