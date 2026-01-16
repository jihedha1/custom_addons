# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class SlideQuestion(models.Model):
    _inherit = 'slide.question'

    # Champs de traçabilité des corrections
    ai_correction_attempts = fields.Integer(
        string="Tentatives de Correction IA",
        default=0,
        readonly=True,
        help="Nombre de fois où la correction IA a été tentée"
    )
    ai_last_correction_error = fields.Text(
        string="Dernière Erreur IA",
        readonly=True,
        help="Message de la dernière erreur rencontrée"
    )
    ai_correction_queue_ids = fields.One2many(
        'ai.correction.queue',
        'question_id',
        string="File d'Attente de Corrections"
    )

    def _check_answer_ouverte_robust(self, user_answer, **kwargs):
        """
        Correction robuste avec fallback intelligent

        Workflow :
        1. Vérification du contexte (avec récupération auto)
        2. Tentative de correction IA
        3. Si échec : mise en file d'attente + fallback
        4. Notification enseignant si nécessaire
        """
        self.ensure_one()

        # Étape 1 : Vérifier si la correction IA est activée
        if not self.is_ai_corrected:
            return self._fallback_manual_correction(user_answer)

        # Étape 2 : Vérifier et récupérer le contexte RAG
        context_id = self._ensure_valid_context()
        if not context_id:
            return self._fallback_context_missing(user_answer)

        # Étape 3 : Tentative de correction IA
        try:
            correction_result = self._call_ai_correction_api(
                context_id,
                user_answer,
                **kwargs
            )

            # Succès : on incrémente le compteur et on retourne
            self.sudo().write({
                'ai_correction_attempts': self.ai_correction_attempts + 1,
                'ai_last_correction_error': False,
            })

            return correction_result

        except requests.exceptions.Timeout:
            _logger.warning(f"Timeout de l'API pour la question {self.id}")
            return self._fallback_timeout(user_answer)

        except requests.exceptions.RequestException as e:
            _logger.error(f"Erreur API pour la question {self.id}: {str(e)}")
            return self._fallback_api_error(user_answer, str(e))

        except Exception as e:
            _logger.error(f"Erreur inattendue pour la question {self.id}: {str(e)}")
            return self._fallback_unknown_error(user_answer, str(e))

    def _ensure_valid_context(self):
        """
        S'assure qu'un contexte RAG valide existe
        Tente de le recréer automatiquement si expiré
        """
        if not self.slide_id:
            _logger.warning(f"Question {self.id} sans slide source")
            return None

        # Vérifier l'expiration
        is_expired = (
                self.slide_id.x_ai_context_expires_at and
                self.slide_id.x_ai_context_expires_at < fields.Datetime.now()
        )

        # Si contexte valide, on le retourne
        if self.slide_id.x_ai_context_id and not is_expired:
            return self.slide_id.x_ai_context_id

        # Sinon, tentative de récréation automatique
        _logger.info(f"Recréation du contexte pour le slide '{self.slide_id.name}'")

        try:
            # Utilise la méthode du wizard (à refactoriser dans une classe utilitaire)
            wizard = self.env['ai.base.wizard'].new({
                'channel_id': self.slide_id.channel_id.id,
                'provider_config_id': self.slide_id.channel_id.ai_provider_config_id.id,
            })
            context_id = wizard._get_or_create_context_for_slide(self.slide_id)

            if context_id:
                _logger.info(f"Contexte recréé avec succès : {context_id}")
                return context_id
            else:
                _logger.warning(f"Échec de recréation du contexte pour le slide {self.slide_id.id}")
                return None

        except Exception as e:
            _logger.error(f"Erreur lors de la recréation du contexte : {str(e)}")
            return None

    def _call_ai_correction_api(self, context_id, user_answer, **kwargs):
        """Appel à l'API de correction avec parsing enrichi"""
        provider_config = self.slide_id.channel_id.ai_provider_config_id

        if not provider_config:
            raise UserError(_("Aucun fournisseur IA configuré"))

        base_url = provider_config.api_base_url
        api_key = provider_config.api_key
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        url = f"{base_url.strip('/')}/corrections/open"
        payload = {
            'context_id': context_id,
            'question_text': self.question,
            'user_answer': user_answer,
            'expected_keywords': self._parse_keywords(),
            'request_detailed_feedback': True,  # Demande un feedback détaillé
        }

        _logger.info(f"Appel API de correction pour question {self.id}")

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        response_data = response.json()

        # Parse et enrichit la réponse
        return self._build_correction_result(response_data)

    def _parse_keywords(self):
        """Parse les mots-clés suggérés par l'IA"""
        if not self.ai_suggested_keywords:
            return []
        return [k.strip() for k in self.ai_suggested_keywords.split(',') if k.strip()]

    def _build_correction_result(self, api_response):
        """Construit un résultat de correction enrichi"""
        is_correct = api_response.get('is_correct', False)
        score = api_response.get('score', 0)  # Score sur 100

        # Construction du feedback HTML enrichi
        feedback_parts = []

        # 1. Résultat global avec score
        if is_correct:
            feedback_parts.append(
                f"<div class='alert alert-success'>"
                f"<strong>✓ Bonne réponse !</strong> "
                f"Score : {score}/100"
                f"</div>"
            )
        else:
            feedback_parts.append(
                f"<div class='alert alert-warning'>"
                f"<strong>⚠ Réponse incomplète</strong> "
                f"Score : {score}/100"
                f"</div>"
            )

        # 2. Feedback détaillé
        feedback_text = api_response.get('feedback', '')
        if feedback_text:
            feedback_parts.append(f"<p><strong>Analyse :</strong></p><p>{feedback_text}</p>")

        # 3. Points positifs
        positive_points = api_response.get('positive_points', [])
        if positive_points:
            feedback_parts.append("<p><strong>✓ Points positifs :</strong></p><ul>")
            for point in positive_points:
                feedback_parts.append(f"<li>{point}</li>")
            feedback_parts.append("</ul>")

        # 4. Points à améliorer
        improvement_points = api_response.get('improvement_points', [])
        if improvement_points:
            feedback_parts.append("<p><strong>⚠ À améliorer :</strong></p><ul>")
            for point in improvement_points:
                feedback_parts.append(f"<li>{point}</li>")
            feedback_parts.append("</ul>")

        # 5. Réponse idéale (si pertinent)
        ideal_answer = api_response.get('ideal_answer', '')
        if ideal_answer and not is_correct:
            feedback_parts.append(
                f"<hr/>"
                f"<p><strong>💡 Exemple de réponse complète :</strong></p>"
                f"<p><em>{ideal_answer}</em></p>"
            )

        # 6. Ressources complémentaires
        resources = api_response.get('suggested_resources', [])
        if resources:
            feedback_parts.append("<p><strong>📚 Pour aller plus loin :</strong></p><ul>")
            for resource in resources:
                feedback_parts.append(f"<li>{resource}</li>")
            feedback_parts.append("</ul>")

        feedback_html = ''.join(feedback_parts)

        return {
            'answer_is_correct': is_correct,
            'answer_feedback': feedback_html,
            'answer_score': score,  # Peut être utilisé pour analytics
        }

    # ========================================================================
    # MÉTHODES DE FALLBACK
    # ========================================================================

    def _fallback_manual_correction(self, user_answer):
        """Fallback : correction manuelle requise"""
        return {
            'answer_is_correct': False,
            'answer_feedback': _(
                "<div class='alert alert-info'>"
                "<strong>📝 Correction manuelle</strong><br/>"
                "Cette question nécessite une correction par un enseignant. "
                "Votre réponse a été enregistrée et sera évaluée prochainement."
                "</div>"
            )
        }

    def _fallback_context_missing(self, user_answer):
        """Fallback : contexte RAG manquant"""
        # Mise en file d'attente pour traitement ultérieur
        self._queue_for_later_correction(user_answer, 'CONTEXT_MISSING')

        # Notification à l'enseignant
        self._notify_teacher_correction_issue('context_missing')

        return {
            'answer_is_correct': False,
            'answer_feedback': _(
                "<div class='alert alert-warning'>"
                "<strong>⚠️ Correction temporairement indisponible</strong><br/>"
                "Votre réponse a été enregistrée et sera corrigée automatiquement "
                "dès que possible. Vous serez notifié du résultat."
                "</div>"
            )
        }

    def _fallback_timeout(self, user_answer):
        """Fallback : timeout de l'API"""
        self._queue_for_later_correction(user_answer, 'TIMEOUT')

        return {
            'answer_is_correct': False,
            'answer_feedback': _(
                "<div class='alert alert-warning'>"
                "<strong>⏱️ Délai de réponse dépassé</strong><br/>"
                "La correction prend plus de temps que prévu. "
                "Votre réponse sera corrigée dans les prochaines minutes."
                "</div>"
            )
        }

    def _fallback_api_error(self, user_answer, error_msg):
        """Fallback : erreur de l'API"""
        self.sudo().write({
            'ai_last_correction_error': f"API Error: {error_msg}",
            'ai_correction_attempts': self.ai_correction_attempts + 1,
        })

        self._queue_for_later_correction(user_answer, 'API_ERROR')
        self._notify_teacher_correction_issue('api_error')

        return {
            'answer_is_correct': False,
            'answer_feedback': _(
                "<div class='alert alert-danger'>"
                "<strong>⚠️ Erreur technique</strong><br/>"
                "Une erreur est survenue lors de la correction automatique. "
                "Un enseignant a été notifié et corrigera votre réponse manuellement."
                "</div>"
            )
        }

    def _fallback_unknown_error(self, user_answer, error_msg):
        """Fallback : erreur inconnue"""
        self.sudo().write({
            'ai_last_correction_error': f"Unknown Error: {error_msg}",
            'ai_correction_attempts': self.ai_correction_attempts + 1,
        })

        self._queue_for_later_correction(user_answer, 'UNKNOWN_ERROR')
        self._notify_teacher_correction_issue('unknown_error')

        return self._fallback_api_error(user_answer, error_msg)

    # ========================================================================
    # GESTION DE LA FILE D'ATTENTE
    # ========================================================================

    def _queue_for_later_correction(self, user_answer, error_type):
        """Met la réponse en file d'attente pour correction ultérieure"""
        self.env['ai.correction.queue'].create({
            'question_id': self.id,
            'user_answer': user_answer,
            'error_type': error_type,
            'retry_count': 0,
            'state': 'pending',
        })
        _logger.info(
            f"Réponse mise en file d'attente pour la question {self.id} "
            f"(raison: {error_type})"
        )

    def _notify_teacher_correction_issue(self, issue_type):
        """Notifie l'enseignant d'un problème de correction"""
        # À implémenter : envoi d'un email ou notification in-app
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        course_name = self.slide_id.channel_id.name if self.slide_id and self.slide_id.channel_id else ''
        slide_name = self.slide_id.name if self.slide_id else ''
        question_text = self.question or ''
        question_url = f"{base_url}/web#id={self.id}&model=slide.question&view_type=form"

        subject = _("⚠️ Problème de correction IA — %s") % (course_name or slide_name or "eLearning")

        body_html = f"""
        <p>Bonjour,</p>

        <p>
        Un problème est survenu lors de la correction IA d’une question.
        </p>

        <ul>
        <li><b>Cours :</b> {course_name or '-'}</li>
        <li><b>Quiz :</b> {slide_name or '-'}</li>
        <li><b>Question :</b> {question_text}</li>
        <li><b>Type :</b> {self.x_question_type or '-'}</li>
        <li><b>Problème :</b> {issue_type}</li>
        <li><b>Tentatives IA :</b> {self.ai_correction_attempts}</li>
        </ul>

        <p>
        <a href="{question_url}">🔗 Ouvrir la question dans Odoo</a>
        </p>

        <p>Veuillez vérifier la config IA ou corriger manuellement les réponses en attente.</p>
        """

    def _get_base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')

# ==============================================================================
# MODÈLE DE FILE D'ATTENTE
# ==============================================================================
class AiCorrectionQueue(models.Model):
    _name = 'ai.correction.queue'
    _description = "File d'attente pour corrections IA différées"
    _order = 'create_date'

    question_id = fields.Many2one('slide.question', required=True, ondelete='cascade')
    user_answer = fields.Text(required=True)
    error_type = fields.Selection([
        ('CONTEXT_MISSING', 'Contexte Manquant'),
        ('TIMEOUT', 'Délai Dépassé'),
        ('API_ERROR', 'Erreur API'),
        ('UNKNOWN_ERROR', 'Erreur Inconnue'),
    ], required=True)
    retry_count = fields.Integer(default=0)
    state = fields.Selection([
        ('pending', 'En Attente'),
        ('processing', 'En Cours'),
        ('done', 'Traité'),
        ('failed', 'Échec'),
    ], default='pending', required=True)
    result = fields.Text(string="Résultat de la Correction")

    @api.model
    def cron_process_queue(self):
        """Cron job pour traiter la file d'attente"""
        pending = self.search([
            ('state', '=', 'pending'),
            ('retry_count', '<', 3),
        ], limit=50)

        for item in pending:
            try:
                item.state = 'processing'
                result = item.question_id._check_answer_ouverte_robust(
                    item.user_answer
                )
                item.write({
                    'state': 'done',
                    'result': str(result),
                })
            except Exception as e:
                item.write({
                    'retry_count': item.retry_count + 1,
                    'state': 'failed' if item.retry_count >= 3 else 'pending',
                })
                _logger.error(f"Échec du retry pour {item.id}: {str(e)}")