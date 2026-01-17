# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta


class PlacementAssessment(models.Model):
    _name = 'lms_objectives.placement_assessment'
    _description = 'Évaluation de positionnement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'assessment_date desc'

    name = fields.Char(
        string='Référence',
        required=True,
        readonly=True,
        default=lambda self: _('New')
    )

    # Contexte
    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Apprenant',
        required=True,
        tracking=True
    )

    # Questionnaire
    survey_id = fields.Many2one(
        'survey.survey',
        string='Questionnaire',
        required=True,
        domain="[('is_placement_survey', '=', True)]"
    )

    user_input_id = fields.Many2one(
        'survey.user_input',
        string='Réponse',
        ondelete='set null'
    )

    # Public cible et durée (AJOUTÉ)
    target_audience = fields.Text(
        string='Public cible',
        help="Description du public visé par ce positionnement"
    )

    estimated_duration = fields.Integer(
        string='Durée estimée (minutes)',
        default=15
    )

    # Configuration (AJOUTÉ)
    auto_assign_on_enrollment = fields.Boolean(
        string='Assignation automatique',
        default=True,
        help="Assigner automatiquement lors de l'inscription à la formation"
    )

    minimum_score = fields.Float(
        string='Score minimum requis (%)',
        default=0.0,
        help="Score minimum pour valider le positionnement"
    )

    auto_generate_plan = fields.Boolean(
        string='Générer plan automatiquement',
        default=False,
        help="Créer automatiquement un plan individualisé selon les résultats"
    )

    # Dates
    assignment_date = fields.Datetime(
        string='Date d\'assignation',
        default=fields.Datetime.now,
        tracking=True
    )

    deadline_date = fields.Datetime(
        string='Date limite',
        compute='_compute_deadline',
        store=True
    )

    assessment_date = fields.Datetime(
        string='Date de réalisation',
        tracking=True
    )

    # Résultats
    score = fields.Float(
        string='Score (%)',
        digits=(5, 2),
        tracking=True
    )

    participant_score = fields.Float(
        string='Score participant',
        digits=(5, 2),
        help="Score brut du participant"
    )

    score_scaled = fields.Float(
        string='Score sur 20',
        compute='_compute_scaled_score',
        store=True
    )

    level = fields.Selection([
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
        ('expert', 'Expert'),
    ], string='Niveau détecté', compute='_compute_level', store=True, tracking=True)

    assessment_result = fields.Selection([
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
        ('expert', 'Expert'),
    ], string='Résultat évaluation', tracking=True)

    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('assigned', 'Assigné'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('expired', 'Expiré'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft', tracking=True)

    # Analyse détaillée (AJOUTÉ)
    strengths = fields.Text(
        string='Points forts',
        help="Compétences déjà maîtrisées"
    )

    improvement_areas = fields.Text(
        string='Axes d\'amélioration',
        help="Compétences à développer"
    )

    # Recommandations
    recommendations = fields.Html(
        string='Recommandations',
        help='Recommandations basées sur les résultats'
    )

    needs_remediation = fields.Boolean(
        string='Nécessite remédiation',
        default=False
    )

    remediation_plan = fields.Html(
        string='Plan de remédiation'
    )

    # Contraintes
    @api.depends('assignment_date')
    def _compute_deadline(self):
        for assessment in self:
            if assessment.assignment_date:
                deadline = assessment.assignment_date + timedelta(days=7)
                assessment.deadline_date = deadline
            else:
                assessment.deadline_date = False

    @api.depends('score', 'participant_score')
    def _compute_scaled_score(self):
        for assessment in self:
            score_to_use = assessment.participant_score or assessment.score
            assessment.score_scaled = score_to_use / 5 if score_to_use else 0

    @api.depends('score', 'participant_score', 'assessment_result')
    def _compute_level(self):
        for assessment in self:
            if assessment.assessment_result:
                assessment.level = assessment.assessment_result
            else:
                score = assessment.participant_score or assessment.score
                if score >= 90:
                    assessment.level = 'expert'
                elif score >= 70:
                    assessment.level = 'advanced'
                elif score >= 40:
                    assessment.level = 'intermediate'
                else:
                    assessment.level = 'beginner'

    @api.constrains('partner_id', 'channel_id')
    def _check_unique_assessment(self):
        for assessment in self:
            existing = self.search([
                ('partner_id', '=', assessment.partner_id.id),
                ('channel_id', '=', assessment.channel_id.id),
                ('state', 'not in', ['cancelled', 'expired']),
                ('id', '!=', assessment.id)
            ])
            if existing:
                raise ValidationError(_(
                    "Une évaluation de positionnement existe déjà pour cet apprenant "
                    "dans cette formation."
                ))

    # Séquence
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'lms_objectives.placement_assessment') or _('New')
        return super(PlacementAssessment, self).create(vals)

    # Actions
    def action_assign(self):
        """Assigner l'évaluation à l'apprenant"""
        for assessment in self:
            assessment.state = 'assigned'

            # Créer le lien survey
            if not assessment.user_input_id:
                user_input = self.env['survey.user_input'].create({
                    'survey_id': assessment.survey_id.id,
                    'partner_id': assessment.partner_id.id,
                    'deadline': assessment.deadline_date,
                })
                assessment.user_input_id = user_input

            # Envoyer l'email d'invitation
            template = self.env.ref(
                'lms_objectives.mail_template_placement_assignment', raise_if_not_found=False)
            if template:
                template.send_mail(assessment.id, force_send=False)

            # Créer une activité de rappel
            assessment.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=assessment.deadline_date.date() if assessment.deadline_date else fields.Date.today(),
                summary=_('Questionnaire de positionnement à compléter'),
                note=_('Veuillez compléter le questionnaire de positionnement '
                       'pour la formation "%s"') % assessment.channel_id.name
            )

    def action_start(self):
        """Marquer comme démarré"""
        self.write({'state': 'in_progress'})

    def action_complete(self):
        """Marquer comme terminé"""
        for assessment in self:
            if assessment.user_input_id and assessment.user_input_id.scoring_percentage:
                assessment.score = assessment.user_input_id.scoring_percentage
                assessment.participant_score = assessment.user_input_id.scoring_percentage
                assessment.assessment_date = fields.Datetime.now()
                assessment.state = 'completed'

                # Générer des recommandations automatiques
                assessment._generate_recommendations()

                # Auto-générer plan si configuré
                if assessment.auto_generate_plan and assessment._needs_individual_plan():
                    assessment._auto_generate_plan()
                else:
                    # Proposer de créer un plan individualisé
                    assessment.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=self.env.user.id,
                        summary=_('Créer plan individualisé'),
                        note=_('Créer un plan de formation individualisé '
                               'basé sur les résultats du positionnement.')
                    )

    def action_generate_plan(self):
        """Générer un plan individualisé"""
        self.ensure_one()

        # Ouvrir le wizard de génération de plan
        return {
            'type': 'ir.actions.act_window',
            'name': _('Générer plan individualisé'),
            'res_model': 'lms_objectives.generate_plan_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_assessment_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_course_id': self.channel_id.id,
            }
        }

    def _needs_individual_plan(self):
        """Vérifier si un plan individualisé est nécessaire"""
        self.ensure_one()
        return self.participant_score < self.minimum_score if self.minimum_score else False

    def _auto_generate_plan(self):
        """Génération automatique d'un plan individualisé"""
        self.ensure_one()

        plan_vals = {
            'partner_id': self.partner_id.id,
            'course_id': self.channel_id.id,
            'assessment_id': self.id,
            'plan_type': 'remediation' if self.needs_remediation else 'standard',
        }

        plan = self.env['lms_objectives.individual_plan'].create(plan_vals)

        self.message_post(
            body=_('Plan individualisé généré automatiquement : %s') % plan.name
        )

    def _generate_recommendations(self):
        """Générer des recommandations basées sur le score"""
        self.ensure_one()

        recommendations = []
        if self.score < 40:
            recommendations.append(_("Niveau débutant détecté"))
            recommendations.append(_("Prévoir des sessions de remédiation"))
            recommendations.append(_("Accentuer les fondamentaux"))
            self.needs_remediation = True
        elif self.score < 70:
            recommendations.append(_("Niveau intermédiaire détecté"))
            recommendations.append(_("Renforcer les concepts clés"))
        elif self.score < 90:
            recommendations.append(_("Niveau avancé détecté"))
            recommendations.append(_("Se concentrer sur les aspects avancés"))
        else:
            recommendations.append(_("Niveau expert détecté"))
            recommendations.append(_("Envisager un parcours accéléré"))

        self.recommendations = '<ul>' + ''.join(
            f'<li>{rec}</li>' for rec in recommendations) + '</ul>'

    # CRON : Assignation automatique
    @api.model
    def _cron_auto_assign_placement(self):
        """
        CRON pour assigner automatiquement les questionnaires
        aux nouveaux inscrits des formations configurées
        """
        # Trouver les formations avec auto-assignation activée
        channels = self.env['slide.channel'].search([
            ('auto_assign_placement', '=', True),
            ('placement_survey_id', '!=', False)
        ])

        for channel in channels:
            # Trouver les participants sans positionnement
            participants = self.env['slide.channel.partner'].search([
                ('channel_id', '=', channel.id),
                ('create_date', '>=', fields.Datetime.now() - timedelta(hours=24))
            ])

            for participant in participants:
                existing = self.search([
                    ('channel_id', '=', channel.id),
                    ('partner_id', '=', participant.partner_id.id)
                ], limit=1)

                if not existing:
                    # Créer et assigner
                    assessment = self.create({
                        'channel_id': channel.id,
                        'partner_id': participant.partner_id.id,
                        'survey_id': channel.placement_survey_id.id,
                    })
                    assessment.action_assign()

    # CRON : Rappels
    @api.model
    def _cron_remind_placement(self):
        """CRON pour envoyer des rappels aux participants"""
        # Chercher les évaluations assignées depuis plus de 3 jours
        deadline = fields.Datetime.now() - timedelta(days=3)
        assessments = self.search([
            ('state', '=', 'assigned'),
            ('assignment_date', '<=', deadline),
            ('deadline_date', '>=', fields.Datetime.now())
        ])

        template = self.env.ref(
            'lms_objectives.mail_template_placement_reminder', raise_if_not_found=False)

        for assessment in assessments:
            if template:
                template.send_mail(assessment.id, force_send=False)

    def action_view_survey_responses(self):
        """Ouvrir les réponses du questionnaire"""
        self.ensure_one()
        if self.user_input_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Réponses du questionnaire',
                'res_model': 'survey.user_input',
                'res_id': self.user_input_id.id,
                'view_mode': 'form',
                'target': 'new',
            }
        return False