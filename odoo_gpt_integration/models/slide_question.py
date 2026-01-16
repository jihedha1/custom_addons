# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import re
import logging

_logger = logging.getLogger(__name__)


class SlideQuestion(models.Model):
    _inherit = 'slide.question'

    # ============================================================================
    # CHAMPS TYPE DE QUESTION
    # ============================================================================

    x_question_type = fields.Selection([
        ('simple_choice', 'Choix Multiple (QCM)'),
        ('true_false', 'Vrai / Faux'),
        ('text_box', 'Réponse Ouverte'),
    ], string="Type de Question",
        default='simple_choice',
        required=True,
        help="Définit le type et la logique de correction de la question")

    # ============================================================================
    # CHAMPS POUR LES MODES DE CORRECTION
    # ============================================================================

    correction_mode = fields.Selection([
        ('manual', 'Correction Manuelle (avec validation enseignant)'),
        ('automatic', 'Correction Automatique (instantanée)')
    ], string="Mode de Correction",
        default='automatic',
        required=True,
        help="""
       • Manuel : Les réponses sont envoyées à l'enseignant pour validation avant affichage
       • Automatique : Les résultats sont affichés immédiatement à l'étudiant
       """)

    # ============================================================================
    # CHAMPS CORRECTION IA
    # ============================================================================

    is_ai_corrected = fields.Boolean(
        string="Correction par IA (GPT)",
        default=False,
        help="Active la correction sémantique via GPT (mode manuel uniquement)"
    )
    x_hint = fields.Html(string="Indice (hint)")

    ai_include_keywords = fields.Text(
        string="Mots-clés à Inclure (Legacy)",
        help="Ancienne méthode - Utiliser le scoring de mots-clés à la place"
    )

    ai_exclude_keywords = fields.Text(
        string="Mots-clés à Exclure (Legacy)",
        help="Ancienne méthode - Utiliser le scoring de mots-clés à la place"
    )

    ai_suggested_keywords = fields.Text(
        string="Mots-clés Suggérés (IA)",
        readonly=True,
        help="Mots-clés suggérés automatiquement par l'IA lors de la génération"
    )

    # ============================================================================
    # CHAMPS SCORING ET RÉPONSES EN ATTENTE
    # ============================================================================

    keyword_scoring = fields.One2many(
        'slide.question.keyword.score',
        'question_id',
        string="Scoring des Mots-clés"
    )

    pending_answers = fields.One2many(
        'slide.question.pending.answer',
        'question_id',
        string="Réponses en Attente de Validation"
    )
    pending_answers_count = fields.Integer(
        string="Réponses en attente",
        compute="_compute_pending_answers_count",
        store=True,
        index=True,
    )

    # ============================================================================
    # CHAMPS MÉTADONNÉES IA
    # ============================================================================

    x_ai_generated = fields.Boolean(
        string="Générée par IA",
        readonly=True,
        default=False,
        copy=False
    )

    x_ai_difficulty_calculated = fields.Selection([
        ('easy', 'Facile'),
        ('medium', 'Moyen'),
        ('hard', 'Difficile'),
    ], string="Difficulté Calculée", readonly=True, copy=False)

    x_ai_source_reference = fields.Char(
        string="Référence Source",
        readonly=True,
        copy=False,
        help="Référence dans le document source (ex: Page 7)"
    )

    x_ai_source_slide_id = fields.Many2one(
        'slide.slide',
        string="Chapitre Source",
        help="Le chapitre duquel cette question a été générée"
    )

    # Statistiques de correction
    ai_correction_attempts = fields.Integer(
        string="Tentatives de Correction",
        default=0,
        readonly=True
    )

    ai_last_correction_error = fields.Text(
        string="Dernière Erreur de Correction",
        readonly=True
    )

    # ============================================================================
    # MÉTHODE PRINCIPALE DE CORRECTION
    # ============================================================================

    def _check_answer(self, answer, user_id=None):
        """
        API interne utilisée par ton contrôleur.
        `answer`:
          - choice: int(answer_id) ou str convertible
          - text_box: string
        Retour attendu:
          {
            'answer_is_correct': bool,
            'answer_score': int (0..100),
            'answer_feedback': str,
            'state': 'graded'|'pending' (optionnel)
          }
        """
        self.ensure_one()

        qtype = self.x_question_type
        mode = self.correction_mode or 'automatic'

        _logger.info("Correction Q%s - Type=%s Mode=%s", self.id, qtype, mode)

        # user_id optionnel (depuis website)
        user = self.env['res.users'].browse(user_id).exists() if user_id else self.env.user
        partner = user.partner_id

        if qtype in ('simple_choice', 'true_false'):
            # answer attendu = answer_id
            try:
                answer_id = int(answer) if answer is not None else False
            except Exception:
                answer_id = False

            return self._check_choice_answer(answer_id, user, partner)

        if qtype == 'text_box':
            text = (answer or '').strip()
            return self._check_text_answer(text, user)

        # fallback
        return {
            'answer_is_correct': False,
            'answer_score': 0,
            'answer_feedback': _("Type de question non supporté."),
        }

    # ============================================================================
    # CORRECTION DES QUESTIONS À CHOIX (QCM / VRAI-FAUX)
    # ============================================================================

    def _check_choice_answer(self, answer_id, user, partner):
        self.ensure_one()
        mode = self.correction_mode or 'automatic'

        if not answer_id:
            return {
                'answer_is_correct': False,
                'answer_score': 0,
                'answer_feedback': _("Aucune réponse sélectionnée."),
            }

        # En mode manuel : on ne révèle pas le résultat, on met en attente
        if mode == 'manual':
            return {
                'answer_is_correct': False,
                'answer_score': 0,
                'answer_feedback': _("Votre réponse est enregistrée et sera validée par l'enseignant."),
                'state': 'pending',
                # important: dire au contrôleur de créer une ligne pending
                'create_pending': True,
                'suggested_score': 0,
                'suggested_feedback': _("Réponse reçue. En attente de validation de l'enseignant."),
            }

        # Mode automatique : correction immédiate
        ans = self.answer_ids.filtered(lambda a: a.id == answer_id)[:1]
        if not ans:
            return {
                'answer_is_correct': False,
                'answer_score': 0,
                'answer_feedback': _("Réponse invalide."),
                'state': 'graded',
            }

        is_correct = bool(ans.is_correct)
        score = 100 if is_correct else 0

        # feedback = commentaire réponse si défini, sinon message simple
        if ans.comment:
            fb = ans.comment
        else:
            fb = _("✅ Bonne réponse !") if is_correct else _("❌ Mauvaise réponse.")

        return {
            'answer_is_correct': is_correct,
            'answer_score': score,
            'answer_feedback': fb,
            'state': 'graded',
        }

    # ============================================================================
    # CORRECTION DES QUESTIONS OUVERTES (TEXT BOX)
    # ============================================================================

    def _check_text_answer(self, user_answer, user_id):
        """
        Correction des questions ouvertes selon le mode
        """
        self.ensure_one()

        # Validation de base
        if not user_answer or len(user_answer.strip()) < 5:
            return {
                'answer_is_correct': False,
                'answer_feedback': _("Réponse trop courte (minimum 5 caractères)"),
                'answer_score': 0,
                'state': 'graded'
            }

        # === MODE MANUEL : Appel GPT + Validation Enseignant ===
        if self.correction_mode == 'manual':
            return self._check_text_manual_mode(user_answer, user_id)

        # === MODE AUTOMATIQUE : Score Mots-clés (sans GPT) ===
        else:
            return self._check_text_automatic_mode(user_answer, user_id)

    # ============================================================================
    # MODE MANUEL : APPEL GPT + VALIDATION
    # ============================================================================

    def _check_text_manual_mode(self, user_answer, user_id):
        """
        Mode manuel : Utilise GPT puis envoie à l'enseignant pour validation
        """
        self.ensure_one()

        # Si GPT désactivé : enregistrer directement pour validation manuelle
        if not self.is_ai_corrected:
            return {
                'answer_is_correct': False,
                'answer_score': 0,
                'answer_feedback': _(
                    "<div class='alert alert-info'>"
                    "<i class='fa fa-user me-2'></i>"
                    "<strong>Correction manuelle</strong><br/>"
                    "Votre réponse sera évaluée par un enseignant."
                    "</div>"
                ),
                'state': 'pending',
                'create_pending': True,
                'suggested_score': 0,
                'suggested_feedback': _("En attente de correction manuelle"),
                'gpt_ideal_answer': False,
            }

        # Sinon, appel GPT pour pré-correction
        try:
            # Appel à l'API GPT pour correction sémantique
            gpt_result = self._call_gpt_correction(user_answer)

            return {
                'answer_is_correct': False,
                'answer_score': 0,
                'answer_feedback': _(
                    "<div class='alert alert-warning'>"
                    "<i class='fa fa-hourglass-half me-2'></i>"
                    "<strong>Correction en cours</strong><br/>"
                    "Votre réponse a été analysée par l'IA et est en attente de validation "
                    "par votre enseignant. Vous recevrez une notification avec le résultat."
                    "</div>"
                ),
                'state': 'pending',
                'create_pending': True,
                'suggested_score': int(gpt_result.get('score', 0) or 0),
                'suggested_feedback': gpt_result.get('feedback', '') or '',
                'gpt_ideal_answer': gpt_result.get('ideal_answer', '') or '',
            }


        except Exception as e:
            _logger.error(f"Erreur appel GPT : {str(e)}", exc_info=True)

            # Fallback : Enregistrer sans correction GPT
            return {
                'answer_is_correct': False,
                'answer_score': 0,
                'answer_feedback': _(
                    "<div class='alert alert-danger'>"
                    "<strong>Erreur technique</strong><br/>"
                    "Une erreur est survenue. Votre réponse sera corrigée manuellement."
                    "</div>"
                ),
                'state': 'pending',
                'create_pending': True,
                'suggested_score': 0,
                'suggested_feedback': _("Correction manuelle requise (erreur IA)"),
                'gpt_ideal_answer': False,
            }

    # ============================================================================
    # MODE AUTOMATIQUE : SCORE MOTS-CLÉS
    # ============================================================================

    def _check_text_automatic_mode(self, user_answer, user_id):

        self.ensure_one()

        user_answer_lower = (user_answer or "").lower()

        feedback_parts = []
        found_keywords = []
        missing_keywords = []
        forbidden_found = []

        # --- Base (positifs) / Pénalités (négatifs) ---
        positive_max = 0  # somme des scores positifs possibles
        positive_found = 0  # somme des scores positifs trouvés
        penalty_abs = 0  # somme des pénalités (valeurs absolues) trouvées

        # 1) Scoring personnalisé (One2many)
        for ks in self.keyword_scoring:
            kw = (ks.keyword or "").strip()
            if not kw:
                continue

            kw_lower = kw.lower()
            val = int(ks.score_value or 0)

            if val > 0:
                positive_max += val
                if kw_lower in user_answer_lower:
                    positive_found += val
                    found_keywords.append({'keyword': kw, 'score': val})
                else:
                    missing_keywords.append({'keyword': kw, 'score': val})

            elif val < 0:
                if kw_lower in user_answer_lower:
                    penalty_abs += abs(val)
                    forbidden_found.append({'keyword': kw, 'penalty': val})  # val est déjà négatif

        # 2) Legacy include/exclude (compat)
        if self.ai_include_keywords:
            include_list = [
                kw.strip() for kw in re.split(r'[,;\n]+', self.ai_include_keywords or '') if kw.strip()
            ]
            for kw in include_list:
                kwl = kw.lower()
                positive_max += 10
                if kwl in user_answer_lower:
                    positive_found += 10
                    found_keywords.append({'keyword': kw, 'score': 10})
                else:
                    missing_keywords.append({'keyword': kw, 'score': 10})

        if self.ai_exclude_keywords:
            exclude_list = [
                kw.strip() for kw in re.split(r'[,;\n]+', self.ai_exclude_keywords or '') if kw.strip()
            ]
            for kw in exclude_list:
                if kw.lower() in user_answer_lower:
                    penalty_abs += 15
                    forbidden_found.append({'keyword': kw, 'penalty': -15})

        # --- Normalisation ---
        if positive_max > 0:
            ratio = (positive_found / positive_max) * 100.0
            final_score = int(round(ratio - penalty_abs))
            final_score = max(0, min(100, final_score))
        else:
            # Aucun scoring défini => fallback longueur
            word_count = len((user_answer or "").split())
            final_score = min(int((word_count / 20) * 100), 100)

        is_correct = final_score >= 50  # Seuil : 50%

        # --- Construction du feedback ---
        feedback_parts.append(
            f"<div class='alert alert-{('success' if is_correct else 'warning')}'>"
            f"<div class='d-flex justify-content-between mb-3'>"
            f"<strong>{'✅ Bonne réponse !' if is_correct else '⚠️ Réponse incomplète'}</strong>"
            f"<span class='badge bg-{('success' if final_score >= 80 else 'warning' if final_score >= 50 else 'danger')}' "
            f"style='font-size: 1.1em;'>{final_score}/100</span>"
            f"</div>"
        )

        if found_keywords:
            feedback_parts.append("<div class='mb-3'>")
            feedback_parts.append("<strong>✅ Éléments corrects identifiés :</strong>")
            feedback_parts.append("<ul class='mb-0 mt-2'>")
            for kw in found_keywords:
                feedback_parts.append(
                    f"<li><code>{kw['keyword']}</code> "
                    f"<span class='badge bg-success'>+{kw['score']}</span></li>"
                )
            feedback_parts.append("</ul></div>")

        if missing_keywords:
            feedback_parts.append("<div class='mb-3'>")
            feedback_parts.append("<strong>📝 Éléments à améliorer :</strong>")
            feedback_parts.append("<ul class='mb-0 mt-2'>")
            for kw in missing_keywords[:3]:
                feedback_parts.append(
                    f"<li>Mentionner <code>{kw['keyword']}</code> "
                    f"<span class='text-muted'>(+{kw['score']} points)</span></li>"
                )
            feedback_parts.append("</ul></div>")

        if forbidden_found:
            feedback_parts.append("<div class='mb-3'>")
            feedback_parts.append("<strong>❌ Erreurs détectées :</strong>")
            feedback_parts.append("<ul class='mb-0 mt-2 text-danger'>")
            for kw in forbidden_found:
                feedback_parts.append(
                    f"<li><code>{kw['keyword']}</code> ne devrait pas être mentionné "
                    f"<span class='badge bg-danger'>{kw['penalty']}</span></li>"
                )
            feedback_parts.append("</ul></div>")

        feedback_parts.append("</div>")
        feedback_html = ''.join(feedback_parts)

        _logger.info("Score automatique Q%s : %s/100 (pos=%s/%s, penalty=%s)",
                     self.id, final_score, positive_found, positive_max, penalty_abs)

        return {
            'answer_is_correct': is_correct,
            'answer_feedback': feedback_html,
            'answer_score': final_score,
            'state': 'graded'
        }
    # ============================================================================
    # APPEL GPT POUR CORRECTION SÉMANTIQUE
    # ============================================================================

    def _call_gpt_correction(self, user_answer):
        """
        Appel à l'API GPT selon la spécification
        POST /corrections/open
        """
        self.ensure_one()

        # Récupérer la configuration du fournisseur IA
        provider_config = self.env['ai.provider.config'].get_default_provider()
        if not provider_config:
            raise UserError(_("Aucun fournisseur IA configuré"))

        # Vérifier le context_id
        if not self.slide_id or not self.slide_id.x_ai_context_id:
            raise UserError(_("Contexte RAG manquant"))
        context_id = self.slide_id.x_ai_context_id

        # Régénérer si expiré
        if self.slide_id.x_ai_context_is_expired:
            context_id = self.slide_id.regenerate_context_if_needed()
            if not context_id:
                raise UserError(_("Impossible de régénérer le contexte"))

        # Préparer les keywords
        include = [kw.keyword for kw in self.keyword_scoring if kw.score_value > 0]
        exclude = [kw.keyword for kw in self.keyword_scoring if kw.score_value < 0]

        # Ajouter les anciens keywords pour compatibilité
        if self.ai_include_keywords:
            include.extend([
                kw.strip()
                for kw in re.split(r'[,;\n]+', self.ai_include_keywords)
                if kw.strip()
            ])

        if self.ai_exclude_keywords:
            exclude.extend([
                kw.strip()
                for kw in re.split(r'[,;\n]+', self.ai_exclude_keywords)
                if kw.strip()
            ])

        # Appel API
        url = f"{provider_config.api_base_url.strip('/')}/corrections/open"
        headers = {
            'Authorization': f'Bearer {provider_config.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'context_id': context_id,
            'question_text': self.question,
            'user_answer': user_answer,
            'include': include,
            'exclude': exclude
        }

        _logger.info(f"Appel GPT correction pour Q{self.id}")

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        return {
            'is_correct': result.get('is_correct', False),
            'score': result.get('score', 0),
            'feedback': result.get('feedback', ''),
            'ideal_answer': result.get('ideal_answer', '')
        }

    # ============================================================================
    # GESTION DES RÉPONSES EN ATTENTE (MODE MANUEL)
    # ============================================================================

    @api.depends("pending_answers.state")
    def _compute_pending_answers_count(self):
        for q in self:
            q.pending_answers_count = sum(1 for a in q.pending_answers if a.state == "pending")

    def _create_pending_answer(self, user, partner, answer_id=False, text_answer=False,
                               suggested_score=0, feedback=False, gpt_ideal_answer=False):
        """
        Crée une réponse en attente (mode manuel).
        """
        self.ensure_one()

        Pending = self.env['slide.question.pending.answer'].sudo()

        vals = {
            'question_id': self.id,
            'user_id': user.id if user else self.env.user.id,
            'partner_id': partner.id if partner else False,
            'answer_id': answer_id or False,
            'text_answer': text_answer or False,
            'score': int(suggested_score or 0),
            'feedback': feedback or False,
            'gpt_ideal_answer': gpt_ideal_answer or False,
            'state': 'pending',
        }

        pending = Pending.create(vals)

        # notifier enseignant (si workflow prévu)
        try:
            pending._notify_teacher()
        except Exception as e:
            _logger.warning("Notify teacher failed for pending %s: %s", pending.id, str(e))

        return pending

    def action_view_pending_answers(self):
        """
        Cette méthode permet à l'enseignant (propriétaire du cours) de consulter
        les réponses des étudiants pour un cours spécifique.
        """
        self.ensure_one()

        # Vérification que l'utilisateur actuel est bien l'enseignant du cours
        if self.slide_id.channel_id.user_id != self.env.user:
            raise UserError(_("Vous n'êtes pas autorisé à consulter les réponses de ce cours."))

        return {
            "type": "ir.actions.act_window",
            "name": "Réponses en attente",
            "res_model": "slide.question.pending.answer",
            "view_mode": "tree,form",
            "domain": [("question_id", "=", self.id)],
            "context": {"default_question_id": self.id},
        }

    def action_validate_all_pending(self):
        self.ensure_one()
        pending = self.pending_answers.filtered(lambda a: a.state == "pending")
        if not pending:
            return True

        # Adapte si ton modèle a d'autres champs à remplir lors de la validation
        pending.write({"state": "validated"})
        return True