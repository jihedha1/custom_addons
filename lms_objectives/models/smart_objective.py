# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SmartObjective(models.Model):
    _name = 'lms_objectives.smart_objective'
    _description = 'Objectif pédagogique SMART'
    _order = 'sequence, id'

    name = fields.Char(
        string='Intitulé',
        required=True,
        translate=True
    )

    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True,
        ondelete='cascade'
    )

    # Critères SMART
    specific = fields.Text(
        string='Spécifique (S)',
        required=True,
        help="Que doit-on réaliser exactement ?"
    )

    measurable = fields.Text(
        string='Mesurable (M)',
        required=True,
        help="Comment mesurer le résultat ?"
    )

    achievable = fields.Text(
        string='Atteignable (A)',
        required=True,
        help="L'objectif est-il réaliste ?"
    )

    relevant = fields.Text(
        string='Pertinent (R)',
        required=True,
        help="En quoi est-ce important pour la formation ?"
    )

    time_bound = fields.Text(
        string='Temporel (T)',
        required=True,
        help="Quel est le délai pour l'atteindre ?"
    )

    # Compétences visées
    skill_ids = fields.Many2many(
        'lms_public_info.trainer_competency',
        string='Compétences visées'
    )

    # Niveau de maîtrise attendu
    mastery_level = fields.Selection([
        ('awareness', 'Prise de conscience'),
        ('comprehension', 'Compréhension'),
        ('application', 'Application'),
        ('analysis', 'Analyse'),
        ('synthesis', 'Synthèse'),
        ('evaluation', 'Évaluation'),
    ], string='Niveau de maîtrise', default='application')

    # Évaluation
    evaluation_method = fields.Selection([
        ('quiz', 'Quiz/Test'),
        ('project', 'Projet pratique'),
        ('case_study', 'Étude de cas'),
        ('presentation', 'Présentation'),
        ('participation', 'Participation active'),
        ('other', 'Autre'),
    ], string='Méthode d\'évaluation', default='quiz')

    # Métadonnées
    sequence = fields.Integer(
        string='Séquence',
        default=10
    )

    weight = fields.Float(
        string='Poids (%)',
        default=100.0,
        help="Poids de l'objectif dans l'évaluation globale"
    )

    is_mandatory = fields.Boolean(
        string='Obligatoire',
        default=True,
        help="L'objectif doit-il être obligatoirement atteint ?"
    )

    # Suivi
    achievement_rate = fields.Float(
        string='Taux d\'atteinte',
        compute='_compute_achievement',
        store=True,
        digits=(5, 2)
    )

    @api.depends('channel_id')
    def _compute_achievement(self):
        # À compléter avec la logique de calcul
        for objective in self:
            objective.achievement_rate = 0.0

    @api.constrains('weight')
    def _check_weight(self):
        for objective in self:
            if objective.weight < 0 or objective.weight > 100:
                raise ValidationError(_("Le poids doit être compris entre 0 et 100%"))

    # Format SMART pour affichage
    def format_smart(self):
        self.ensure_one()
        return _("""
        <b>S</b> (Spécifique) : {specific}<br/>
        <b>M</b> (Mesurable) : {measurable}<br/>
        <b>A</b> (Atteignable) : {achievable}<br/>
        <b>R</b> (Pertinent) : {relevant}<br/>
        <b>T</b> (Temporel) : {time_bound}
        """).format(
            specific=self.specific,
            measurable=self.measurable,
            achievable=self.achievable,
            relevant=self.relevant,
            time_bound=self.time_bound
        )