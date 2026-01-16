# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


# ==============================================================================
# CLASSE DE BASE POUR LES WIZARDS IA (AVEC GESTION API CONFORME)
# ==============================================================================
class AiBaseWizard(models.AbstractModel):
    _name = 'ai.base.wizard'
    _description = "Wizard de base pour les opérations IA"

    channel_id = fields.Many2one('slide.channel', string="Cours", readonly=True, required=True)
    language = fields.Selection([
        ('fr', 'Français'),
        ('en', 'Anglais'),
        ('ar', 'Arabe')
    ], string="Langue", default='fr', required=True)

    provider_config_id = fields.Many2one(
        'ai.provider.config',
        string="Fournisseur IA",
        required=True
    )

    def _call_api(self, endpoint, payload, timeout=120):
        """
        Méthode centralisée pour appeler l'API
        CONFORME À LA SPEC : Gestion du CONTEXT_NOT_FOUND
        """
        if not self.provider_config_id:
            raise UserError(_("Aucun fournisseur d'IA configuré"))

        config = self.provider_config_id
        base_url = config.api_base_url
        api_key = config.api_key

        if not base_url or not api_key:
            raise UserError(_("Configuration incomplète (URL ou clé API manquante)"))

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        url = f"{base_url.strip('/')}/{endpoint.strip('/')}"

        try:
            _logger.info(f"Appel API : {url}")
            _logger.debug(f"Payload : {json.dumps(payload, indent=2)}")

            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()

            data = response.json()
            _logger.info(f"Réponse API reçue avec succès")
            return data

        except requests.exceptions.HTTPError as e:
            # GESTION SPEC : CONTEXT_NOT_FOUND
            if e.response.status_code == 404:
                error_data = e.response.json() if e.response.content else {}
                if error_data.get('error') == 'CONTEXT_NOT_FOUND':
                    return {'error': 'CONTEXT_NOT_FOUND'}

            _logger.error(f"Erreur HTTP {e.response.status_code} : {e.response.text}")
            raise UserError(_(f"Erreur API : {e.response.status_code} - {e.response.text}"))

        except requests.exceptions.Timeout:
            _logger.error(f"Timeout lors de l'appel à {url}")
            raise UserError(_("L'API ne répond pas. Veuillez réessayer."))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Erreur de connexion : {str(e)}")
            raise UserError(_(f"Impossible de contacter l'API : {str(e)}"))

    def _get_or_create_context_for_slide(self, slide):
        """
        Récupère ou crée un contexte pour un slide
        CONFORME À LA SPEC : Gestion automatique de l'expiration
        """
        # Vérifier l'expiration
        is_expired = (
                not slide.x_ai_context_id or
                (slide.x_ai_context_expires_at and
                 slide.x_ai_context_expires_at < fields.Datetime.now())
        )

        # Si valide, on retourne
        if not is_expired:
            _logger.info(f"Réutilisation du contexte {slide.x_ai_context_id}")
            return slide.x_ai_context_id

        # Sinon, création/recréation
        _logger.info(f"Création d'un nouveau contexte pour '{slide.name}'")

        import base64

        # Prépare le contenu
        content = None
        if slide.binary_content:
            content = slide.binary_content.decode('utf-8')
        elif slide.slide_category == 'article' and slide.html_content:
            html_bytes = slide.html_content.encode('utf-8')
            content = base64.b64encode(html_bytes).decode('utf-8')

        if not content:
            _logger.warning(f"Slide '{slide.name}' sans contenu exploitable")
            return None

        # Appel API conforme à la spec
        payload = {
            'file_id': f"ODOO_SLIDE_{slide.id}",
            'file_content_base64': content,
            'file_name': slide.name or f"slide_{slide.id}.pdf",
        }

        response_data = self._call_api('contexts', payload, timeout=180)

        if response_data and not response_data.get('error'):
            # Sauvegarde selon la spec
            slide.sudo().write({
                'x_ai_context_id': response_data.get('context_id'),
                'x_ai_context_expires_at': response_data.get('metadata', {}).get('expires_at'),
                'x_ai_context_file_id': f"ODOO_SLIDE_{slide.id}",
            })
            return response_data.get('context_id')

        return None

    def _handle_context_not_found(self, slides, original_call_func):
        """
        Gestion automatique du CONTEXT_NOT_FOUND
        CONFORME À LA SPEC : Retry transparent
        """
        _logger.warning("CONTEXT_NOT_FOUND détecté, régénération automatique...")

        # Régénère tous les contextes
        new_context_ids = []
        for slide in slides:
            slide.sudo().write({
                'x_ai_context_id': False,
                'x_ai_context_expires_at': False,
            })
            context_id = self._get_or_create_context_for_slide(slide)
            if context_id:
                new_context_ids.append(context_id)

        if not new_context_ids:
            raise UserError(_("Impossible de régénérer les contextes"))

        # Retry de l'appel original
        return original_call_func(new_context_ids)


# ==============================================================================
# 1. WIZARD PRINCIPAL (LE MENU) - MANQUANT DANS VOTRE CODE
# ==============================================================================
class AiMainWizard(models.TransientModel):
    _name = 'ai.main.wizard'
    _description = "Menu principal de génération par IA"

    channel_id = fields.Many2one('slide.channel', string="Cours", readonly=True, required=True)
    language = fields.Selection(
        [('fr', 'Français'), ('en', 'Anglais'), ('ar', 'Arabe')],
        string="Langue de Génération",
        default='fr',
        required=True
    )
    provider_config_id = fields.Many2one(
        'ai.provider.config',
        string="Fournisseur IA",
        domain="[('active', '=', True)]",
        help="Le fournisseur configuré sur le cours est sélectionné par défaut.",
        required=True
    )

    @api.model
    def default_get(self, fields_list):
        """Pré-remplit le fournisseur avec celui du cours."""
        res = super().default_get(fields_list)
        if self.env.context.get('default_channel_id'):
            channel = self.env['slide.channel'].browse(self.env.context['default_channel_id'])
            if channel.ai_provider_config_id:
                res['provider_config_id'] = channel.ai_provider_config_id.id
        return res

    def _launch_wizard(self, wizard_name, action_name):
        """Lance un wizard spécialisé en passant la configuration via le contexte."""
        self.ensure_one()
        return {
            'name': _(action_name),
            'type': 'ir.actions.act_window',
            'res_model': wizard_name,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_channel_id': self.channel_id.id,
                'default_language': self.language,
                'default_provider_config_id': self.provider_config_id.id,
            }
        }

    def action_launch_summary_wizard(self):
        return self._launch_wizard('ai.summary.wizard', 'Générer un Résumé')

    def action_launch_quiz_batch_wizard(self):
        return self._launch_wizard('ai.quiz.batch.wizard', 'Générer un Quiz par Lot')

    def action_launch_question_targeted_wizard(self):
        return self._launch_wizard('ai.question.targeted.wizard', 'Générer une Question Ciblée')


# ==============================================================================
# 2. WIZARD : GÉNÉRATION DE RÉSUMÉ
# ==============================================================================
class AiSummaryWizard(models.TransientModel):
    _name = 'ai.summary.wizard'
    _inherit = 'ai.base.wizard'
    _description = "Wizard de génération de résumé"

    slide_id = fields.Many2one(
        'slide.slide',
        string="Chapitre Source",
        required=True,
        domain="[('channel_id', '=', channel_id), ('is_category', '=', False), ('slide_category', 'in', ['document', 'article'])]"
    )
    length = fields.Integer(string="Longueur (mots)", default=200, required=True)

    def action_generate_summary(self):
        """
        Génère un résumé
        CONFORME À LA SPEC : POST /summaries
        """
        self.ensure_one()

        # Obtenir le context_id
        context_id = self._get_or_create_context_for_slide(self.slide_id)
        if not context_id:
            raise UserError(_("Impossible de créer un contexte pour ce chapitre"))

        # Prépare le payload conforme à la spec
        payload = {
            'context_id': context_id,
            'config': {
                'length': self.length,
                'language': self.language
            }
        }

        # Appel API
        response_data = self._call_api('summaries', payload)

        # Gestion du CONTEXT_NOT_FOUND
        if response_data.get('error') == 'CONTEXT_NOT_FOUND':
            response_data = self._handle_context_not_found(
                [self.slide_id],
                lambda ctx_ids: self._call_api('summaries', {
                    'context_id': ctx_ids[0],
                    'config': {'length': self.length, 'language': self.language}
                })
            )

        if not response_data or not response_data.get('summary_text'):
            raise UserError(_("L'API n'a retourné aucun résumé"))

        # Création du slide résumé conforme à la spec
        keywords = ', '.join(response_data.get('keywords', []))
        html_content = f"""
        <div class="ai-generated-summary">
            <h1>{response_data.get('slide_title', 'Résumé')}</h1>
            <div class="summary-content">
                <p>{response_data['summary_text']}</p>
            </div>
            <hr/>
            <div class="summary-keywords">
                <h3>Mots-clés :</h3>
                <p>{keywords}</p>
            </div>
        </div>
        """

        new_slide = self.env['slide.slide'].create({
            'name': response_data.get('slide_title', f"Résumé - {self.slide_id.name}"),
            'channel_id': self.channel_id.id,
            'slide_category': 'article',
            'html_content': html_content,
            'is_published': False,
            'sequence': self.slide_id.sequence + 1,
        })

        self.env.user.notify_success(message=_("Résumé créé avec succès !"))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'slide.slide',
            'view_mode': 'form',
            'res_id': new_slide.id,
            'target': 'current',
        }


# ==============================================================================
# 3. WIZARD : GÉNÉRATION DE QUIZ PAR LOT
# ==============================================================================
class AiQuizBatchWizard(models.TransientModel):
    _name = 'ai.quiz.batch.wizard'
    _inherit = 'ai.base.wizard'
    _description = "Wizard de génération de quiz par lot"

    slide_ids = fields.Many2many(
        'slide.slide',
        'ai_quiz_batch_wizard_slide_rel',
        'wizard_id',
        'slide_id',
        string="Chapitres Sources",
        required=True,
        domain="[('channel_id', '=', channel_id), ('is_category', '=', False), ('slide_category', 'in', ['document', 'article'])]"
    )
    quiz_title = fields.Char(string="Titre du Quiz", default="Quiz de Révision", required=True)

    question_group_lines = fields.One2many(
        'ai.quiz.batch.wizard.line',
        'wizard_id',
        string="Composition du Quiz"
    )

    def action_generate_quiz(self):
        """
        Génère un quiz complet
        CONFORME À LA SPEC : POST /quizzes/batch
        """
        self.ensure_one()

        if not self.slide_ids:
            raise UserError(_("Sélectionnez au moins un chapitre"))
        if not self.question_group_lines:
            raise UserError(_("Définissez au moins un groupe de questions"))

        # Obtenir les context_ids
        context_ids = []
        for slide in self.slide_ids:
            ctx_id = self._get_or_create_context_for_slide(slide)
            if ctx_id:
                context_ids.append(ctx_id)

        if not context_ids:
            raise UserError(_("Impossible d'obtenir des contextes pour ces chapitres"))

        # Prépare le payload conforme à la spec
        question_groups = []
        for line in self.question_group_lines:
            question_groups.append({
                'question_type': line.question_type,
                'count': line.count,
                'config': {
                    'difficulty': line.difficulty,
                    'language': self.language
                }
            })

        payload = {
            'context_ids': context_ids,
            'quiz_title': self.quiz_title,
            'question_groups': question_groups
        }

        # Appel API
        response_data = self._call_api('quizzes/batch', payload, timeout=300)

        # Gestion CONTEXT_NOT_FOUND
        if response_data.get('error') == 'CONTEXT_NOT_FOUND':
            response_data = self._handle_context_not_found(
                self.slide_ids,
                lambda ctx_ids: self._call_api('quizzes/batch', {
                    'context_ids': ctx_ids,
                    'quiz_title': self.quiz_title,
                    'question_groups': question_groups
                }, timeout=300)
            )

        if not response_data or not response_data.get('questions'):
            raise UserError(_("L'API n'a retourné aucune question"))

        # Création du quiz conforme à la spec
        quiz_slide = self.env['slide.slide'].create({
            'name': response_data.get('quiz_title', self.quiz_title),
            'channel_id': self.channel_id.id,
            'slide_category': 'quiz',
            'is_published': False,
        })

        # Création des questions selon la spec
        for q_data in response_data['questions']:
            self._create_question_from_api_response(quiz_slide, q_data)

        self.env.user.notify_success(
            message=_("Quiz créé avec %d questions !") % len(response_data['questions'])
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'slide.slide',
            'view_mode': 'form',
            'res_id': quiz_slide.id,
            'target': 'current',
        }

    def _create_question_from_api_response(self, quiz_slide, q_data):
        """
        Crée une question depuis la réponse API
        CONFORME À LA SPEC : Mapping des types et structure
        """
        # Mapping des types API vers Odoo
        type_mapping = {
            'QCM_UNIQUE': 'simple_choice',
            'VRAI_FAUX': 'true_false',
            'REPONSE_OUVERTE': 'text_box',
        }

        api_type = q_data.get('question_type')
        odoo_type = type_mapping.get(api_type, 'simple_choice')

        # Prépare les valeurs de base
        metadata = q_data.get('metadata', {})
        question_vals = {
            'slide_id': quiz_slide.id,
            'question': q_data.get('question_title'),
            'x_question_type': odoo_type,
            'x_ai_generated': True,
            'x_ai_difficulty_calculated': metadata.get('difficulty_calculated'),
            'x_ai_source_reference': metadata.get('source_reference'),
        }

        # Traitement spécifique pour questions ouvertes
        if odoo_type == 'text_box':
            keywords = q_data.get('suggested_keywords', [])
            question_vals.update({
                'is_ai_corrected': True,
                'ai_suggested_keywords': ', '.join(keywords),
                'ai_include_keywords': ', '.join(keywords),  # Par défaut
            })

        # Création de la question
        new_question = self.env['slide.question'].create(question_vals)

        # Création des réponses (QCM/Vrai-Faux) selon la spec
        if odoo_type in ['simple_choice', 'true_false'] and 'answers_data' in q_data:
            for answer_data in q_data['answers_data']:
                self.env['slide.answer'].create({
                    'question_id': new_question.id,
                    'text_value': answer_data.get('text_value'),
                    'is_correct': answer_data.get('is_correct', False),
                    'comment': answer_data.get('comment', ''),
                })

        return new_question


class AiQuizBatchWizardLine(models.TransientModel):
    _name = 'ai.quiz.batch.wizard.line'
    _description = "Ligne de configuration pour quiz par lot"

    wizard_id = fields.Many2one('ai.quiz.batch.wizard', required=True, ondelete='cascade')

    # CONFORME À LA SPEC : Types exacts de l'API
    question_type = fields.Selection([
        ('QCM_UNIQUE', 'QCM (Choix Multiple)'),
        ('VRAI_FAUX', 'Vrai / Faux'),
        ('REPONSE_OUVERTE', 'Réponse Ouverte'),
    ], string="Type", required=True, default='QCM_UNIQUE')

    count = fields.Integer(string="Nombre", default=5, required=True)

    difficulty = fields.Selection([
        ('easy', 'Facile'),
        ('medium', 'Moyen'),
        ('hard', 'Difficile'),
    ], string="Difficulté", default='medium', required=True)


# ==============================================================================
# 4. WIZARD : GÉNÉRATION DE QUESTION CIBLÉE
# ==============================================================================
class AiQuestionTargetedWizard(models.TransientModel):
    _name = 'ai.question.targeted.wizard'
    _inherit = 'ai.base.wizard'
    _description = "Wizard de génération de question ciblée"

    slide_id = fields.Many2one(
        'slide.slide',
        string="Chapitre Source",
        required=True,
        domain="[('channel_id', '=', channel_id), ('is_category', '=', False), ('slide_category', 'in', ['document', 'article'])]"
    )

    # CONFORME À LA SPEC
    question_type = fields.Selection([
        ('QCM_UNIQUE', 'QCM (Choix Multiple)'),
        ('VRAI_FAUX', 'Vrai / Faux'),
        ('REPONSE_OUVERTE', 'Réponse Ouverte'),
    ], string="Type", required=True, default='QCM_UNIQUE')

    difficulty = fields.Selection([
        ('easy', 'Facile'),
        ('medium', 'Moyen'),
        ('hard', 'Difficile'),
    ], string="Difficulté", default='medium')

    focus_on = fields.Char(
        string="Sujet Spécifique",
        help="Ex: 'Le Cycle de Calvin'"
    )

    def action_generate_question(self):
        """
        Génère une question ciblée
        CONFORME À LA SPEC : POST /questions/single_targeted
        """
        self.ensure_one()

        # Obtenir le context_id
        context_id = self._get_or_create_context_for_slide(self.slide_id)
        if not context_id:
            raise UserError(_("Impossible de créer un contexte"))

        # Prépare le payload conforme à la spec
        config = {
            'question_type': self.question_type,
            'language': self.language,
        }

        if self.difficulty:
            config['difficulty'] = self.difficulty
        if self.focus_on:
            config['focus_on'] = self.focus_on

        payload = {
            'context_id': context_id,
            'config': config
        }

        # Appel API
        response_data = self._call_api('questions/single_targeted', payload)

        # Gestion CONTEXT_NOT_FOUND
        if response_data.get('error') == 'CONTEXT_NOT_FOUND':
            response_data = self._handle_context_not_found(
                [self.slide_id],
                lambda ctx_ids: self._call_api('questions/single_targeted', {
                    'context_id': ctx_ids[0],
                    'config': config
                })
            )

        if not response_data or not response_data.get('question_title'):
            raise UserError(_("L'API n'a retourné aucune question"))

        # Créer la question (elle sera attachée à un quiz existant ou nouveau)
        wizard_question = self.env['ai.quiz.batch.wizard'].new({})
        new_question = wizard_question._create_question_from_api_response(
            self.slide_id,  # Temporaire, l'utilisateur choisira le quiz
            response_data
        )

        # Ouvre la question pour édition/validation
        return {
            'name': _('Question Générée'),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.question',
            'view_mode': 'form',
            'res_id': new_question.id,
            'target': 'new',
        }