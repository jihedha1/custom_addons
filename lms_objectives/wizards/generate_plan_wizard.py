# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class GeneratePlanWizard(models.TransientModel):
    _name = 'lms_objectives.generate_plan_wizard'
    _description = 'Assistant génération plan individualisé'

    assessment_id = fields.Many2one(
        'lms_objectives.placement_assessment',
        string='Évaluation',
        required=True
    )

    template_id = fields.Many2one(
        'lms_objectives.plan_template',
        string='Modèle',
        help="Modèle de plan à utiliser"
    )

    include_objectives = fields.Boolean(
        string='Inclure les objectifs SMART',
        default=True
    )

    include_recommendations = fields.Boolean(
        string='Inclure les recommandations',
        default=True
    )

    adapt_for_disability = fields.Boolean(
        string='Adapter pour handicap',
        compute='_compute_adapt_for_disability'
    )

    # Ajoutez ces champs manquants
    start_date = fields.Date(
        string='Date de début',
        required=True,
        default=fields.Date.today
    )

    end_date = fields.Date(
        string='Date de fin',
        required=True
    )

    include_assessment = fields.Boolean(
        string='Inclure les résultats du positionnement',
        default=True
    )

    auto_sign = fields.Boolean(
        string='Générer pour signature électronique',
        default=False
    )

    def _compute_adapt_for_disability(self):
        for wizard in self:
            wizard.adapt_for_disability = wizard.assessment_id.partner_id.has_disability

    def action_generate(self):
        """Générer le plan individualisé"""
        self.ensure_one()

        # Récupérer les données
        assessment = self.assessment_id
        partner = assessment.partner_id
        channel = assessment.channel_id

        # Préparer le contenu
        specific_objectives = ""
        if self.include_objectives:
            objectives = self.env['lms_objectives.smart_objective'].search([
                ('channel_id', '=', channel.id)
            ])
            specific_objectives = "<h4>Objectifs SMART adaptés :</h4><ul>"
            for obj in objectives:
                specific_objectives += f"<li>{obj.name}</li>"
            specific_objectives += "</ul>"

        # Adaptations pour handicap
        adaptations = ""
        if self.adapt_for_disability and partner.has_disability:
            adaptations = f"""
            <h4>Adaptations pour handicap :</h4>
            <p><strong>Type :</strong> {dict(partner._fields['disability_type'].selection).get(partner.disability_type)}</p>
            <p><strong>Aménagements nécessaires :</strong></p>
            <ul>
                {''.join(f'<li>{acc.name}</li>' for acc in partner.accommodations_ids)}
            </ul>
            """

        # Créer le plan
        plan_vals = {
            'name': self.env['ir.sequence'].next_by_code('lms_objectives.individual_plan'),
            'assessment_id': assessment.id,
            'partner_id': partner.id,
            'channel_id': channel.id,
            'specific_objectives': specific_objectives,
            'pedagogical_approach': self._generate_pedagogical_approach(assessment),
            'adaptations': adaptations,
            'evaluation_criteria': self._generate_evaluation_criteria(assessment),
            'estimated_hours': channel.total_duration_hours if hasattr(channel, 'total_duration_hours') else 35,
            'start_date': self.start_date,
            'end_date': self.end_date,
        }

        plan = self.env['lms_objectives.individual_plan'].create(plan_vals)

        # Rediriger vers le plan créé
        return {
            'type': 'ir.actions.act_window',
            'name': _('Plan individualisé'),
            'res_model': 'lms_objectives.individual_plan',
            'res_id': plan.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _generate_pedagogical_approach(self, assessment):
        """Générer l'approche pédagogique basée sur le niveau"""
        level = assessment.level
        approaches = {
            'beginner': """
                <h4>Approche pédagogique (Niveau Débutant) :</h4>
                <ul>
                    <li>Pédagogie active avec beaucoup d'exemples concrets</li>
                    <li>Progressivité dans la difficulté</li>
                    <li>Support visuel renforcé</li>
                    <li>Exercices guidés étape par étape</li>
                    <li>Retours fréquents et personnalisés</li>
                </ul>
            """,
            'intermediate': """
                <h4>Approche pédagogique (Niveau Intermédiaire) :</h4>
                <ul>
                    <li>Pédagogie par problèmes et études de cas</li>
                    <li>Mise en situation professionnelle</li>
                    <li>Travaux pratiques encadrés</li>
                    <li>Développement de l'autonomie progressive</li>
                </ul>
            """,
            'advanced': """
                <h4>Approche pédagogique (Niveau Avancé) :</h4>
                <ul>
                    <li>Pédagogie par projet</li>
                    <li>Recherche et analyse critique</li>
                    <li>Production de contenus innovants</li>
                    <li>Auto-évaluation guidée</li>
                </ul>
            """,
            'expert': """
                <h4>Approche pédagogique (Niveau Expert) :</h4>
                <ul>
                    <li>Pédagogie collaborative et co-construction</li>
                    <li>Mentoring inversé</li>
                    <li>Recherche appliquée</li>
                    <li>Production de connaissances</li>
                </ul>
            """,
        }
        return approaches.get(level, "")

    def _generate_evaluation_criteria(self, assessment):
        """Générer les critères d'évaluation"""
        return f"""
        <h4>Critères d'évaluation :</h4>
        <ul>
            <li>Atteinte des objectifs SMART définis</li>
            <li>Participation active aux activités</li>
            <li>Qualité des productions réalisées</li>
            <li>Progression dans l'autonomie</li>
            <li>Application des compétences en situation réelle</li>
        </ul>
        <p><strong>Niveau initial détecté :</strong> {dict(assessment._fields['level'].selection).get(assessment.level)}</p>
        <p><strong>Score de positionnement :</strong> {assessment.score:.2f}%</p>
        """

    def _calculate_duration(self, channel):
        """Calculer la durée estimée"""
        # Base : 1 semaine pour 35h de formation
        weeks = (channel.total_duration_hours if hasattr(channel, 'total_duration_hours') else 35) / 35
        return timedelta(days=int(weeks * 7))