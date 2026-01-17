# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    # Objectifs SMART
    smart_objective_ids = fields.One2many(
        'lms_objectives.smart_objective',
        'channel_id',
        string='Objectifs pédagogiques SMART'
    )

    smart_objective_count = fields.Integer(
        string='Nombre d\'objectifs',
        compute='_compute_smart_objective_count'
    )

    # Positionnement
    placement_survey_id = fields.Many2one(
        'survey.survey',
        string='Questionnaire de positionnement',
        domain="[('is_placement_survey', '=', True)]",
        help="Questionnaire à faire passer avant la formation"
    )

    auto_assign_placement = fields.Boolean(
        string='Assignation automatique du positionnement',
        default=False,
        help="Assigner automatiquement le questionnaire lors de l'inscription"
    )

    has_placement_survey = fields.Boolean(
        string='A un questionnaire de positionnement',
        compute='_compute_has_placement_survey',
        store=True
    )

    # Computes
    @api.depends('smart_objective_ids')
    def _compute_smart_objective_count(self):
        for channel in self:
            channel.smart_objective_count = len(channel.smart_objective_ids)

    @api.depends('placement_survey_id')
    def _compute_has_placement_survey(self):
        for channel in self:
            channel.has_placement_survey = bool(channel.placement_survey_id)

    # Actions
    def action_view_objectives(self):
        """Voir les objectifs de cette formation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Objectifs pédagogiques',
            'res_model': 'lms_objectives.smart_objective',
            'view_mode': 'tree,form',
            'domain': [('channel_id', '=', self.id)],
            'context': {'default_channel_id': self.id}
        }

    def action_view_placement_assessments(self):
        """Voir les évaluations de positionnement"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Évaluations de positionnement',
            'res_model': 'lms_objectives.placement_assessment',
            'view_mode': 'tree,form',
            'domain': [('channel_id', '=', self.id)],
            'context': {'default_channel_id': self.id}
        }

    def action_view_individual_plans(self):
        """Voir les plans individualisés"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Plans individualisés',
            'res_model': 'lms_objectives.individual_plan',
            'view_mode': 'tree,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id}
        }


class Survey(models.Model):
    _inherit = 'survey.survey'

    is_placement_survey = fields.Boolean(
        string='Questionnaire de positionnement',
        default=False,
        help="Ce questionnaire est utilisé pour évaluer le niveau avant formation"
    )

    # Relation inverse pour voir quelles formations utilisent ce questionnaire
    channel_ids = fields.One2many(
        'slide.channel',
        'placement_survey_id',
        string='Formations utilisant ce questionnaire'
    )


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Plans individualisés
    individual_plan_ids = fields.One2many(
        'lms_objectives.individual_plan',
        'partner_id',
        string='Plans de formation'
    )

    # Évaluations de positionnement
    placement_assessment_ids = fields.One2many(
        'lms_objectives.placement_assessment',
        'partner_id',
        string='Évaluations de positionnement'
    )