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
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Apprenant',
        required=True,
        domain="[('is_training_participant', '=', True)]"
    )

    # Questionnaire
    survey_id = fields.Many2one(
        'survey.survey',
        string='Questionnaire',
        required=True,
        domain="[('category', '=', 'placement')]"
    )

    user_input_id = fields.Many2one(
        'survey.user_input',
        string='Réponse',
        ondelete='set null'
    )

    # Dates
    assignment_date = fields.Datetime(
        string='Date d\'assignation',
        default=fields.Datetime.now
    )

    deadline_date = fields.Datetime(
        string='Date limite',
        compute='_compute_deadline',
        store=True
    )

    assessment_date = fields.Datetime(
        string='Date de réalisation'
    )

    # Résultats
    score = fields.Float(
        string='Score (%)',
        digits=(5, 2)
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
    ], string='Niveau détecté', compute='_compute_level', store=True)

    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('assigned', 'Assigné'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('expired', 'Expiré'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft', track_visibility='onchange')

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

    @api.depends('score')
    def _compute_scaled_score(self):
        for assessment in self:
            assessment.score_scaled = assessment.score / 5 if assessment.score else 0

    @api.depends('score')
    def _compute_level(self):
        for assessment in self:
            if assessment.score >= 90:
                assessment.level = 'expert'
            elif assessment.score >= 70:
                assessment.level = 'advanced'
            elif assessment.score >= 40:
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
                'formation.placement.assessment') or _('New')
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
                'lms_objectives.mail_template_placement_assignment')
            template.send_mail(assessment.id, force_send=False)

            # Créer une activité de rappel
            assessment.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=assessment.deadline_date,
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
                assessment.assessment_date = fields.Datetime.now()
                assessment.state = 'completed'

                # Générer des recommandations automatiques
                assessment._generate_recommendations()

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
        return {
            'type': 'ir.actions.act_window',
            'name': _('Créer plan individualisé'),
            'res_model': 'formation.individual.plan',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_assessment_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_channel_id': self.channel_id.id,
                'default_name': _('Plan individualisé - %s') % self.partner_id.name
            }
        }

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