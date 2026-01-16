# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SlideQuestionCorrectionWizard(models.TransientModel):
    """
    Wizard pour permettre à l'enseignant de corriger manuellement une réponse
    en attente de validation
    """
    _name = 'slide.question.correction.wizard'
    _description = "Assistant de correction manuelle"

    # ============================================================================
    # CHAMPS
    # ============================================================================

    pending_answer_id = fields.Many2one(
        'slide.question.pending.answer',
        string="Réponse en attente",
        required=True,
        ondelete='cascade'
    )

    # Informations en lecture seule - CHAMPS DIRECTS (pas related)
    question_text = fields.Text(
        string="Texte Question",
        readonly=True
    )

    question_type = fields.Selection([
        ('simple_choice', 'Choix Multiple (QCM)'),
        ('true_false', 'Vrai / Faux'),
        ('text_box', 'Réponse Ouverte'),
    ], string="Type de question", readonly=True)

    student_name = fields.Char(
        string="Étudiant",
        readonly=True
    )

    student_email = fields.Char(
        string="Email étudiant",
        readonly=True
    )

    student_answer = fields.Text(
        string="Réponse de l'étudiant",
        readonly=True
    )

    submission_date = fields.Datetime(
        string="Date de soumission",
        readonly=True
    )

    # Suggestions automatiques (GPT ou scoring)
    suggested_score = fields.Integer(
        string="Score suggéré",
        readonly=True
    )

    suggested_feedback = fields.Html(
        string="Feedback suggéré",
        readonly=True
    )

    gpt_ideal_answer = fields.Text(
        string="Réponse idéale (GPT)",
        readonly=True
    )

    # Champs de correction par l'enseignant
    final_score = fields.Integer(
        string="Score final",
        required=True,
        default=0,
        help="Score attribué (0-100)"
    )

    final_feedback = fields.Html(
        string="Feedback personnalisé",
        help="Feedback à envoyer à l'étudiant"
    )

    teacher_comment = fields.Text(
        string="Commentaire interne",
        help="Commentaire visible uniquement par les enseignants (optionnel)"
    )

    # Options
    notify_student = fields.Boolean(
        string="Notifier l'étudiant",
        default=True,
        help="Envoyer une notification à l'étudiant"
    )

    use_suggested_feedback = fields.Boolean(
        string="Utiliser le feedback suggéré",
        default=True,
        help="Utiliser le feedback généré automatiquement"
    )

    # Champs computés
    score_difference = fields.Integer(
        string="Écart de score",
        compute='_compute_score_difference',
        help="Différence entre score suggéré et score final"
    )

    correction_quality = fields.Selection([
        ('excellent', 'Excellente (80-100)'),
        ('good', 'Bonne (60-79)'),
        ('average', 'Moyenne (40-59)'),
        ('poor', 'Insuffisante (0-39)')
    ], string="Qualité",
        compute='_compute_correction_quality')

    # ============================================================================
    # VALEURS PAR DÉFAUT
    # ============================================================================

    @api.model
    def default_get(self, fields_list):
        """Charge les valeurs par défaut depuis la réponse en attente"""
        res = super(SlideQuestionCorrectionWizard, self).default_get(fields_list)

        if self.env.context.get('default_pending_answer_id'):
            pending_answer = self.env['slide.question.pending.answer'].browse(
                self.env.context['default_pending_answer_id']
            )

            if pending_answer.exists():
                # Charger les informations de base
                res.update({
                    'question_text': pending_answer.question_id.question if pending_answer.question_id else '',
                    'question_type': pending_answer.question_id.x_question_type if pending_answer.question_id else 'simple_choice',
                    'student_name': pending_answer.user_id.name if pending_answer.user_id else '',
                    'student_email': pending_answer.user_id.email if pending_answer.user_id else '',
                    'submission_date': pending_answer.create_date,
                })

                # Charger la réponse de l'étudiant
                if pending_answer.text_answer:
                    res['student_answer'] = pending_answer.text_answer
                elif pending_answer.answer_id:
                    res['student_answer'] = pending_answer.answer_id.text_value or ''

                # Charger les suggestions
                res['suggested_score'] = pending_answer.score or 0
                res['suggested_feedback'] = pending_answer.feedback or ''
                res['gpt_ideal_answer'] = pending_answer.gpt_ideal_answer or ''

                # Par défaut, utiliser le score suggéré
                res['final_score'] = pending_answer.score or 0

                # Par défaut, utiliser le feedback suggéré
                if pending_answer.feedback:
                    res['final_feedback'] = pending_answer.feedback

        return res

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends('final_score', 'suggested_score')
    def _compute_score_difference(self):
        """Calcule l'écart entre score suggéré et final"""
        for wizard in self:
            wizard.score_difference = wizard.final_score - wizard.suggested_score

    @api.depends('final_score')
    def _compute_correction_quality(self):
        """Détermine la qualité de la correction selon le score"""
        for wizard in self:
            if wizard.final_score >= 80:
                wizard.correction_quality = 'excellent'
            elif wizard.final_score >= 60:
                wizard.correction_quality = 'good'
            elif wizard.final_score >= 40:
                wizard.correction_quality = 'average'
            else:
                wizard.correction_quality = 'poor'

    # ============================================================================
    # ONCHANGE
    # ============================================================================

    @api.onchange('use_suggested_feedback')
    def _onchange_use_suggested_feedback(self):
        """Remplit automatiquement le feedback si option cochée"""
        if self.use_suggested_feedback and self.suggested_feedback:
            self.final_feedback = self.suggested_feedback
        elif not self.use_suggested_feedback:
            self.final_feedback = self._generate_basic_feedback()

    @api.onchange('final_score')
    def _onchange_final_score(self):
        """Génère un feedback basique si vide et met à jour la qualité"""
        if not self.final_feedback:
            self.final_feedback = self._generate_basic_feedback()

    # ============================================================================
    # CONTRAINTES
    # ============================================================================

    @api.constrains('final_score')
    def _check_final_score(self):
        """Vérifie que le score est entre 0 et 100"""
        for wizard in self:
            if wizard.final_score < 0 or wizard.final_score > 100:
                raise ValidationError(_("Le score doit être entre 0 et 100"))

    # ============================================================================
    # ACTIONS PRINCIPALES
    # ============================================================================

    def action_validate_correction(self):
        """Valide la correction et met à jour la réponse en attente"""
        self.ensure_one()

        if not self.final_feedback:
            raise UserError(_("Le feedback ne peut pas être vide"))

        # Construire le feedback final complet
        final_feedback_html = self._build_final_feedback()

        # Mettre à jour la réponse en attente
        self.pending_answer_id.write({
            'state': 'corrected',
            'final_score': self.final_score,
            'final_feedback': final_feedback_html,
            'teacher_comment': self.teacher_comment,
            'validated_by': self.env.user.id,
            'validated_date': fields.Datetime.now()
        })

        # Notifier l'étudiant si demandé
        if self.notify_student:
            self.pending_answer_id._notify_student()

        # Logger l'action
        _logger.info(
            f"Correction manuelle - Q{self.pending_answer_id.question_id.id} - "
            f"User {self.pending_answer_id.user_id.id} - "
            f"Score: {self.final_score}/100 - "
            f"Enseignant: {self.env.user.name}"
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Correction enregistrée'),
                'message': _('La correction a été enregistrée avec succès'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }

    def action_accept_suggestion(self):
        """Accepte la suggestion automatique sans modification"""
        self.ensure_one()

        self.pending_answer_id.action_validate()

        _logger.info(
            f"Suggestion acceptée - Q{self.pending_answer_id.question_id.id} - "
            f"User {self.pending_answer_id.user_id.id} - "
            f"Score: {self.suggested_score}/100"
        )

        return {'type': 'ir.actions.act_window_close'}

    def action_reject_answer(self):
        """Rejette la réponse (score = 0)"""
        self.ensure_one()

        self.final_score = 0

        if not self.final_feedback:
            self.final_feedback = """
            <div class='alert alert-danger'>
                <strong>❌ Réponse incorrecte</strong><br/>
                Votre réponse ne correspond pas aux attentes.
            </div>
            """

        return self.action_validate_correction()

    # ============================================================================
    # ACTIONS SECONDAIRES
    # ============================================================================

    def action_view_question_context(self):
        """Ouvre le contexte complet de la question (slide, cours)"""
        self.ensure_one()

        return {
            'name': _('Contexte de la Question'),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.slide',
            'res_id': self.pending_answer_id.question_id.slide_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_student_profile(self):
        """Ouvre le profil complet de l'étudiant"""
        self.ensure_one()

        return {
            'name': _('Profil Étudiant'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'res_id': self.pending_answer_id.user_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_preview_feedback(self):
        """Prévisualise le feedback final avant validation"""
        self.ensure_one()

        preview_html = self._build_final_feedback()

        return {
            'name': _('Prévisualisation du Feedback'),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.question.correction.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'preview_mode': True,
                'preview_html': preview_html
            }
        }

    # ============================================================================
    # MÉTHODES PRIVÉES
    # ============================================================================

    def _generate_basic_feedback(self):
        """Génère un feedback basique selon le score"""
        if self.final_score >= 80:
            return """
            <div class='alert alert-success'>
                <strong>✅ Excellente réponse !</strong><br/>
                Vous avez bien compris le sujet et votre réponse est complète.
            </div>
            """
        elif self.final_score >= 60:
            return """
            <div class='alert alert-info'>
                <strong>👍 Bonne réponse</strong><br/>
                Votre réponse contient les éléments principaux. Quelques améliorations sont possibles.
            </div>
            """
        elif self.final_score >= 40:
            return """
            <div class='alert alert-warning'>
                <strong>⚠️ Réponse partiellement correcte</strong><br/>
                Certains éléments sont corrects mais la réponse manque de précision ou de complétude.
            </div>
            """
        else:
            return """
            <div class='alert alert-danger'>
                <strong>❌ Réponse insuffisante</strong><br/>
                La réponse ne correspond pas aux attentes. Revoyez le cours et réessayez.
            </div>
            """

    def _build_final_feedback(self):
        """Construit le feedback final avec score et commentaires"""
        self.ensure_one()

        # Déterminer la couleur du badge selon le score
        if self.final_score >= 80:
            badge_class = 'success'
            icon = '✅'
            title = 'Excellente réponse'
        elif self.final_score >= 60:
            badge_class = 'info'
            icon = '👍'
            title = 'Bonne réponse'
        elif self.final_score >= 40:
            badge_class = 'warning'
            icon = '⚠️'
            title = 'Réponse acceptable'
        else:
            badge_class = 'danger'
            icon = '❌'
            title = 'Réponse insuffisante'

        # Construire le HTML avec un design soigné
        feedback_parts = [
            f"<div class='card border-{badge_class} mb-3'>",
            f"<div class='card-header bg-{badge_class} text-white'>",
            f"<div class='d-flex justify-content-between align-items-center'>",
            f"<h5 class='mb-0'>{icon} {title}</h5>",
            f"<span class='badge bg-white text-{badge_class}' style='font-size: 1.3em;'>",
            f"{self.final_score}/100",
            "</span>",
            "</div>",
            "</div>",
            "<div class='card-body'>",
        ]

        # Ajouter le feedback principal
        if self.final_feedback:
            feedback_parts.append(self.final_feedback)

        # Ajouter le commentaire enseignant si présent
        if self.teacher_comment:
            feedback_parts.extend([
                "<hr/>",
                "<div class='alert alert-light mb-0'>",
                "<strong>💬 Commentaire de l'enseignant :</strong><br/>",
                f"<p class='mb-0'>{self.teacher_comment}</p>",
                "</div>"
            ])

        # Ajouter la signature
        feedback_parts.extend([
            "</div>",
            "<div class='card-footer text-muted small'>",
            f"Corrigé par {self.env.user.name} le {fields.Datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            "</div>",
            "</div>"
        ])

        return ''.join(feedback_parts)

    # ============================================================================
    # TEMPLATES DE FEEDBACK
    # ============================================================================

    @api.model
    def get_feedback_templates(self):
        """Retourne une liste de templates de feedback pré-définis"""
        return {
            'excellent': {
                'score': 95,
                'feedback': """
                <div class='alert alert-success'>
                    <strong>✅ Excellente réponse !</strong><br/>
                    Votre réponse démontre une compréhension approfondie du sujet.
                    Tous les points clés sont abordés avec précision.
                </div>
                """
            },
            'good': {
                'score': 75,
                'feedback': """
                <div class='alert alert-info'>
                    <strong>👍 Bonne réponse</strong><br/>
                    Vous avez bien compris l'essentiel. Quelques détails pourraient
                    être ajoutés pour une réponse complète.
                </div>
                """
            },
            'incomplete': {
                'score': 50,
                'feedback': """
                <div class='alert alert-warning'>
                    <strong>⚠️ Réponse incomplète</strong><br/>
                    Vous êtes sur la bonne voie mais votre réponse manque de
                    développement. Pensez à étayer vos propos.
                </div>
                """
            },
            'incorrect': {
                'score': 20,
                'feedback': """
                <div class='alert alert-danger'>
                    <strong>❌ Réponse incorrecte</strong><br/>
                    Votre réponse contient des erreurs importantes. Revoyez le
                    cours et n'hésitez pas à poser des questions.
                </div>
                """
            },
        }

    def action_apply_template(self):
        """Applique un template de feedback"""
        self.ensure_one()
        template_key = self.env.context.get("template_key")
        templates = self.get_feedback_templates()
        if template_key in templates:
            template = templates[template_key]
            self.write({
                'final_score': template['score'],
                'final_feedback': template['feedback']
            })

        return True