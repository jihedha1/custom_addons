# custom_addons/lms_evaluation_results/models/cold_assessment.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ColdAssessment(models.Model):
    """
    Modèle pour les évaluations à froid (J+30/J+90)
    Conforme Qualiopi - US-F2
    """
    _name = 'lms_evaluation_results.cold_assessment'
    _description = 'Évaluation à froid'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc'

    # ========== CHAMPS DE BASE ==========
    name = fields.Char(
        string='Référence',
        required=True,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True
    )

    # ========== CONTEXTE FORMATION ==========
    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True,
        tracking=True,
        help="Formation concernée par cette évaluation"
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Apprenant',
        required=True,
        tracking=True,
        help="Participant à évaluer"
    )

    # Intégration avec formevo (yonn.course.progress)
    progress_id = fields.Many2one(
        'yonn.course.progress',
        string='Progression formevo',
        help="Lien avec la progression formevo"
    )

    completion_date = fields.Date(
        string='Date de fin de formation',
        required=True,
        tracking=True,
        help="Date à laquelle l'apprenant a terminé la formation"
    )

    # ========== QUESTIONNAIRE ==========
    assessment_type = fields.Selection([
        ('30_days', 'J+30 (1 mois après)'),
        ('90_days', 'J+90 (3 mois après)'),
        ('custom', 'Personnalisé'),
    ], string='Type d\'évaluation',
        required=True,
        default='30_days',
        tracking=True,
        help="Délai après la formation pour cette évaluation"
    )

    survey_id = fields.Many2one(
        'survey.survey',
        string='Questionnaire',
        required=True,
        domain="[('is_published', '=', True)]",
        help="Questionnaire d'évaluation à envoyer"
    )

    user_input_id = fields.Many2one(
        'survey.user_input',
        string='Réponse apprenant',
        readonly=True,
        help="Lien vers les réponses de l'apprenant"
    )

    # ========== PLANNING & DATES ==========
    scheduled_date = fields.Date(
        string='Date planifiée',
        compute='_compute_scheduled_date',
        store=True,
        help="Date calculée automatiquement selon le type (J+30 ou J+90)"
    )

    sent_date = fields.Datetime(
        string='Date d\'envoi',
        readonly=True,
        tracking=True
    )

    response_date = fields.Datetime(
        string='Date de réponse',
        readonly=True,
        help="Quand l'apprenant a complété le questionnaire"
    )

    deadline_date = fields.Date(
        string='Date limite réponse',
        compute='_compute_deadline_date',
        store=True,
        help="Date limite pour répondre (scheduled_date + 15 jours)"
    )

    # ========== RELANCES ==========
    reminder_sent = fields.Boolean(
        string='Rappel envoyé',
        default=False,
        readonly=True,
        tracking=True
    )

    reminder_count = fields.Integer(
        string='Nombre de rappels envoyés',
        default=0,
        readonly=True
    )

    max_reminders = fields.Integer(
        string='Nombre maximum de rappels',
        default=2,
        help="Nombre de rappels à envoyer si pas de réponse"
    )

    reminder_interval_days = fields.Integer(
        string='Intervalle rappels (jours)',
        default=7,
        help="Délai entre chaque rappel"
    )

    last_reminder_date = fields.Date(
        string='Date dernier rappel',
        readonly=True
    )

    # ========== RÉSULTATS ==========
    score = fields.Float(
        string='Score (%)',
        digits=(5, 2),
        readonly=True,
        help="Score global obtenu par l'apprenant"
    )

    satisfaction_rate = fields.Float(
        string='Taux de satisfaction',
        compute='_compute_satisfaction',
        store=True,
        digits=(5, 2),
        help="Calculé à partir du score"
    )

    effectiveness_rate = fields.Float(
        string='Taux d\'efficacité',
        compute='_compute_effectiveness',
        store=True,
        digits=(5, 2),
        help="Basé sur l'application professionnelle"
    )

    feedback = fields.Text(
        string='Feedback libre',
        readonly=True,
        help="Commentaires de l'apprenant extraits du questionnaire"
    )

    # ========== IMPACT PROFESSIONNEL ==========
    professional_impact = fields.Selection([
        ('none', 'Aucun'),
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('very_high', 'Très élevé'),
    ], string='Impact professionnel',
        help="Impact déclaré par l'apprenant sur sa pratique professionnelle"
    )

    applied_skills = fields.Boolean(
        string='Compétences appliquées',
        default=False,
        help="L'apprenant a-t-il mis en pratique les compétences acquises ?"
    )

    career_progression = fields.Boolean(
        string='Progression de carrière',
        default=False,
        help="La formation a-t-elle contribué à une évolution professionnelle ?"
    )

    # ========== WORKFLOW ==========
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('scheduled', 'Planifiée'),
        ('sent', 'Envoyée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('expired', 'Expirée'),
        ('cancelled', 'Annulée'),
    ], string='Statut',
        default='draft',
        required=True,
        tracking=True
    )

    # ========== CHAMPS CALCULÉS ==========
    @api.depends('completion_date', 'assessment_type')
    def _compute_scheduled_date(self):
        """Calcule la date d'envoi selon le type d'évaluation"""
        for assessment in self:
            if not assessment.completion_date:
                assessment.scheduled_date = False
                continue

            if assessment.assessment_type == '30_days':
                assessment.scheduled_date = assessment.completion_date + timedelta(days=30)
            elif assessment.assessment_type == '90_days':
                assessment.scheduled_date = assessment.completion_date + timedelta(days=90)
            else:
                # Type personnalisé : par défaut 30 jours
                assessment.scheduled_date = assessment.completion_date + timedelta(days=30)

    @api.depends('scheduled_date')
    def _compute_deadline_date(self):
        """Calcule la date limite de réponse (scheduled + 15 jours)"""
        for assessment in self:
            if assessment.scheduled_date:
                assessment.deadline_date = assessment.scheduled_date + timedelta(days=15)
            else:
                assessment.deadline_date = False

    @api.depends('score')
    def _compute_satisfaction(self):
        """Calcule le taux de satisfaction à partir du score"""
        for assessment in self:
            if not assessment.score:
                assessment.satisfaction_rate = 0.0
                continue

            if assessment.score >= 80:
                assessment.satisfaction_rate = 95.0
            elif assessment.score >= 60:
                assessment.satisfaction_rate = 75.0
            elif assessment.score >= 40:
                assessment.satisfaction_rate = 55.0
            else:
                assessment.satisfaction_rate = 30.0

    @api.depends('applied_skills', 'career_progression', 'professional_impact')
    def _compute_effectiveness(self):
        """Calcule l'efficacité basée sur l'impact professionnel"""
        for assessment in self:
            effectiveness = 0.0

            if assessment.applied_skills:
                effectiveness += 40.0

            if assessment.career_progression:
                effectiveness += 30.0

            # Multiplicateur selon l'impact
            impact_multiplier = {
                'none': 0.0,
                'low': 0.3,
                'medium': 0.6,
                'high': 0.8,
                'very_high': 1.0,
            }
            effectiveness += 30.0 * impact_multiplier.get(assessment.professional_impact or 'none', 0)

            assessment.effectiveness_rate = effectiveness

    # ========== CONTRAINTES ==========
    @api.constrains('completion_date')
    def _check_completion_date(self):
        """La date de fin de formation ne peut pas être dans le futur"""
        for assessment in self:
            if assessment.completion_date and assessment.completion_date > fields.Date.today():
                raise ValidationError(_(
                    "La date de fin de formation ne peut pas être dans le futur."
                ))

    @api.constrains('max_reminders')
    def _check_max_reminders(self):
        """Limiter le nombre de rappels pour éviter le spam"""
        for assessment in self:
            if assessment.max_reminders < 0 or assessment.max_reminders > 5:
                raise ValidationError(_(
                    "Le nombre de rappels doit être entre 0 et 5."
                ))

    # ========== SÉQUENCE ==========
    @api.model
    def create(self, vals):
        """Génère une séquence unique pour chaque évaluation"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'lms_evaluation_results.cold_assessment'
            ) or _('New')
        return super(ColdAssessment, self).create(vals)

    # ========== ACTIONS WORKFLOW ==========
    def action_schedule(self):
        """Planifier l'évaluation"""
        for assessment in self:
            if assessment.state != 'draft':
                raise UserError(_("Seules les évaluations en brouillon peuvent être planifiées."))

            assessment.write({'state': 'scheduled'})
            assessment.message_post(
                body=_('Évaluation planifiée pour le %s') % assessment.scheduled_date
            )

    def action_send(self):
        """Envoyer l'évaluation à l'apprenant"""
        for assessment in self:
            if assessment.state not in ['scheduled', 'draft']:
                raise UserError(_("Cette évaluation ne peut pas être envoyée dans son état actuel."))

            # Vérifier que l'apprenant a un email
            if not assessment.partner_id.email:
                raise UserError(_(
                    "L'apprenant %s n'a pas d'adresse email configurée."
                ) % assessment.partner_id.name)

            # Créer l'user_input si pas déjà fait
            if not assessment.user_input_id:
                user_input = self.env['survey.user_input'].create({
                    'survey_id': assessment.survey_id.id,
                    'partner_id': assessment.partner_id.id,
                    'deadline': assessment.deadline_date,
                    'email': assessment.partner_id.email,
                })
                assessment.user_input_id = user_input.id

            # Envoyer l'invitation par email
            try:
                template = self.env.ref('lms_evaluation_results.mail_template_cold_assessment')
                template.send_mail(assessment.id, force_send=True)

                assessment.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now()
                })

                assessment.message_post(
                    body=_('Évaluation envoyée à %s') % assessment.partner_id.email
                )

            except Exception as e:
                _logger.error(f"Erreur envoi évaluation {assessment.name}: {e}")
                raise UserError(_(
                    "Impossible d'envoyer l'évaluation : %s"
                ) % str(e))

    def action_complete(self):
        """Marquer comme terminée et extraire les résultats"""
        for assessment in self:
            if not assessment.user_input_id:
                raise UserError(_("Aucune réponse n'a été enregistrée pour cette évaluation."))

            if assessment.user_input_id.state != 'done':
                raise UserError(_("L'apprenant n'a pas encore complété le questionnaire."))

            # Extraire les résultats du survey
            assessment._extract_survey_results()

            assessment.write({
                'state': 'completed',
                'response_date': fields.Datetime.now()
            })

            assessment.message_post(
                body=_('Évaluation complétée - Score: %.1f%%') % assessment.score
            )

    def action_send_reminder(self):
        """Envoyer un rappel à l'apprenant"""
        for assessment in self:
            if assessment.state != 'sent':
                continue

            if assessment.reminder_count >= assessment.max_reminders:
                _logger.warning(
                    f"Nombre maximum de rappels atteint pour {assessment.name}"
                )
                continue

            try:
                template = self.env.ref('lms_evaluation_results.mail_template_cold_reminder')
                template.send_mail(assessment.id, force_send=True)

                assessment.write({
                    'reminder_sent': True,
                    'reminder_count': assessment.reminder_count + 1,
                    'last_reminder_date': fields.Date.today()
                })

                assessment.message_post(
                    body=_('Rappel %d/%d envoyé') % (
                        assessment.reminder_count,
                        assessment.max_reminders
                    )
                )

            except Exception as e:
                _logger.error(f"Erreur envoi rappel {assessment.name}: {e}")

    def action_cancel(self):
        """Annuler l'évaluation"""
        for assessment in self:
            if assessment.state == 'completed':
                raise UserError(_("Une évaluation terminée ne peut pas être annulée."))

            assessment.write({'state': 'cancelled'})
            assessment.message_post(body=_('Évaluation annulée'))

    # ========== MÉTHODES PRIVÉES ==========
    def _extract_survey_results(self):
        """Extrait les résultats du questionnaire survey"""
        self.ensure_one()

        if not self.user_input_id:
            return

        # Score global
        if self.user_input_id.scoring_percentage:
            self.score = self.user_input_id.scoring_percentage

        # Extraire le feedback textuel
        feedback_lines = []
        for line in self.user_input_id.user_input_line_ids:
            if line.question_id.question_type in ['text_box', 'char_box']:
                if line.value_text_box:
                    feedback_lines.append(
                        f"**{line.question_id.title}:**\n{line.value_text_box}"
                    )

        if feedback_lines:
            self.feedback = "\n\n".join(feedback_lines)

        # Extraire les champs spécifiques
        for line in self.user_input_id.user_input_line_ids:
            question_title = line.question_id.title.lower()

            # Compétences appliquées
            if 'appliqué' in question_title or 'pratique' in question_title:
                if line.answer_type == 'suggestion':
                    self.applied_skills = line.suggested_answer_id.value == 'correct'

            # Progression carrière
            if 'carrière' in question_title or 'évolution' in question_title:
                if line.answer_type == 'suggestion':
                    self.career_progression = line.suggested_answer_id.value == 'correct'

    # ========== MÉTHODES CRON ==========
    @api.model
    def _cron_schedule_cold_assessments(self):
        """Planifier automatiquement les évaluations à froid"""
        _logger.info("CRON: Planification évaluations à froid - DÉBUT")

        date_limite = fields.Date.today() - timedelta(days=1)

        # Intégration avec formevo (yonn.course.progress)
        if 'yonn.course.progress' in self.env:
            completions = self.env['yonn.course.progress'].search([
                ('completion_percentage', '>=', 100.0),
                ('last_activity', '=', date_limite),
            ])

            created_count = 0
            for completion in completions:
                # Vérifier qu'il n'existe pas déjà
                existing = self.search([
                    ('channel_id', '=', completion.course_id.id),
                    ('partner_id', '=', completion.partner_id.id),
                    ('assessment_type', '=', '30_days'),
                ], limit=1)

                if existing:
                    continue

                # Créer J+30
                survey_30 = self._get_default_survey('30_days')
                if survey_30:
                    self.create({
                        'channel_id': completion.course_id.id,
                        'partner_id': completion.partner_id.id,
                        'progress_id': completion.id,
                        'completion_date': date_limite,
                        'assessment_type': '30_days',
                        'survey_id': survey_30.id,
                        'state': 'scheduled',
                    })
                    created_count += 1

                # Créer J+90
                survey_90 = self._get_default_survey('90_days')
                if survey_90:
                    self.create({
                        'channel_id': completion.course_id.id,
                        'partner_id': completion.partner_id.id,
                        'progress_id': completion.id,
                        'completion_date': date_limite,
                        'assessment_type': '90_days',
                        'survey_id': survey_90.id,
                        'state': 'scheduled',
                    })
                    created_count += 1

            _logger.info(f"CRON: {created_count} évaluations créées")

    @api.model
    def _cron_send_cold_assessments(self):
        """Envoyer automatiquement les évaluations planifiées"""
        _logger.info("CRON: Envoi évaluations à froid - DÉBUT")

        today = fields.Date.today()
        assessments = self.search([
            ('state', '=', 'scheduled'),
            ('scheduled_date', '<=', today),
        ])

        sent_count = 0
        for assessment in assessments:
            try:
                assessment.action_send()
                sent_count += 1
            except Exception as e:
                _logger.error(f"Erreur envoi {assessment.name}: {e}")

        _logger.info(f"CRON: {sent_count} évaluations envoyées")

    @api.model
    def _cron_send_reminders(self):
        """Envoyer des rappels pour les évaluations en attente"""
        _logger.info("CRON: Envoi rappels - DÉBUT")

        today = fields.Date.today()

        assessments = self.search([
            ('state', '=', 'sent'),
            ('reminder_count', '<', 'max_reminders'),
        ])

        sent_count = 0
        for assessment in assessments:
            if not assessment.last_reminder_date:
                days_since_sent = (today - assessment.sent_date.date()).days
                if days_since_sent >= assessment.reminder_interval_days:
                    assessment.action_send_reminder()
                    sent_count += 1
            else:
                days_since_last = (today - assessment.last_reminder_date).days
                if days_since_last >= assessment.reminder_interval_days:
                    assessment.action_send_reminder()
                    sent_count += 1

        _logger.info(f"CRON: {sent_count} rappels envoyés")

    @api.model
    def _cron_check_expired(self):
        """Marquer comme expirées les évaluations dépassées"""
        _logger.info("CRON: Vérification expirations - DÉBUT")

        today = fields.Date.today()

        expired = self.search([
            ('state', 'in', ['sent', 'in_progress']),
            ('deadline_date', '<', today),
        ])

        for assessment in expired:
            assessment.write({'state': 'expired'})
            assessment.message_post(
                body=_('Évaluation expirée - Aucune réponse reçue avant la date limite')
            )

        _logger.info(f"CRON: {len(expired)} évaluations expirées")

    # ========== MÉTHODES UTILITAIRES ==========
    @api.model
    def _get_default_survey(self, assessment_type):
        """Récupère le questionnaire par défaut pour un type d'évaluation"""
        survey = self.env['survey.survey'].search([
            ('title', 'ilike', f'évaluation à froid {assessment_type}'),
            ('is_published', '=', True),
        ], limit=1)

        if not survey:
            survey = self.env['survey.survey'].search([
                ('is_published', '=', True)
            ], limit=1)

        return survey