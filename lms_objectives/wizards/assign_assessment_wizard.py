# custom_addons/lms_objectives/wizards/assign_assessment_wizard.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AssignAssessmentWizard(models.TransientModel):
    _name = 'lms_objectives.assign_assessment_wizard'
    _description = 'Assistant assignation questionnaires positionnement'

    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True
    )

    survey_id = fields.Many2one(
        'survey.survey',
        string='Questionnaire',
        required=True,
    )

    partner_ids = fields.Many2many(
        'res.partner',
        string='Apprenants',
        required=True,

    )

    send_email = fields.Boolean(
        string='Envoyer email d\'invitation',
        default=True
    )

    create_activity = fields.Boolean(
        string='Créer activité de rappel',
        default=True
    )

    def action_assign(self):
        """Assigner les questionnaires aux apprenants"""
        self.ensure_one()

        assessments_created = []
        for partner in self.partner_ids:
            # Vérifier si une évaluation existe déjà
            existing = self.env['lms_objectives.placement_assessment'].search([
                ('partner_id', '=', partner.id),
                ('channel_id', '=', self.channel_id.id),
                ('state', 'not in', ['cancelled', 'expired']),
            ])

            if not existing:
                # Créer l'évaluation
                assessment = self.env['lms_objectives.placement_assessment'].create({
                    'channel_id': self.channel_id.id,
                    'partner_id': partner.id,
                    'survey_id': self.survey_id.id,
                })

                if self.send_email:
                    assessment.action_assign()

                assessments_created.append(assessment.name)

        # Message de confirmation
        return {
            'type': 'ir.actions.act_window_close',
            'params': {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Questionnaires assignés'),
                    'message': _('%d questionnaires ont été assignés avec succès.') % len(self.partner_ids),
                    'type': 'success',
                    'sticky': False,
                }
            }
        }