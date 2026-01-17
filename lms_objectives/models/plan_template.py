# lms_objectives/models/plan_template.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PlanTemplate(models.Model):
    """Modèle de plan de formation"""
    _name = 'lms_objectives.plan_template'
    _description = 'Modèle de plan de formation'
    _order = 'name'

    name = fields.Char(
        string='Nom du modèle',
        required=True,
    )

    description = fields.Text(
        string='Description'
    )

    # Type de plan
    plan_type = fields.Selection([
        ('initial', 'Initial'),
        ('standard', 'Standard'),
        ('remediation', 'Remédiation'),
        ('accelerated', 'Accéléré'),
        ('adapted', 'Adapté'),
    ], string='Type de plan', default='standard')

    # Contenu par défaut
    default_specific_objectives = fields.Html(
        string='Objectifs spécifiques par défaut'
    )

    default_pedagogical_approach = fields.Html(
        string='Approche pédagogique par défaut'
    )

    default_adaptations = fields.Html(
        string='Adaptations par défaut'
    )

    default_evaluation_criteria = fields.Html(
        string='Critères d\'évaluation par défaut'
    )

    default_notes = fields.Text(
        string='Notes par défaut'
    )

    # Durée par défaut
    default_estimated_hours = fields.Float(
        string='Heures estimées par défaut',
        default=20.0
    )

    default_duration_days = fields.Integer(
        string='Durée en jours par défaut',
        default=30
    )

    # Objectifs par défaut
    default_objective_ids = fields.Many2many(
        'lms_objectives.smart_objective',
        string='Objectifs par défaut',
        help="Objectifs SMART inclus par défaut dans ce modèle"
    )

    # Statut
    active = fields.Boolean(
        string='Actif',
        default=True
    )

    # Séquences créées
    plan_ids = fields.One2many(
        'lms_objectives.individual_plan',
        'template_id',
        string='Plans créés'
    )

    plan_count = fields.Integer(
        string='Nombre de plans',
        compute='_compute_plan_count',
        store=True
    )

    @api.depends('plan_ids')
    def _compute_plan_count(self):
        for template in self:
            template.plan_count = len(template.plan_ids)