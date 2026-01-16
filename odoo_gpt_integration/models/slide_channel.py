# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import base64
import logging

_logger = logging.getLogger(__name__)


class SlideChannel(models.Model):
    """Extension du modèle cours pour la configuration IA"""
    _inherit = 'slide.channel'

    ai_provider_config_id = fields.Many2one(
        'ai.provider.config',
        string="Fournisseur IA par Défaut",
        help="Le fournisseur d'IA à utiliser par défaut pour toutes les générations de contenu de ce cours."
    )

    can_edit_ai_config = fields.Boolean(
        compute="_compute_can_edit_ai_config",
        store=False
    )

    @api.depends_context("uid")
    def _compute_can_edit_ai_config(self):
        is_admin = self.env.user.has_group("odoo_gpt_integration.group_elearning_admin")
        for rec in self:
            rec.can_edit_ai_config = bool(is_admin)

class Slide(models.Model):
    """Extension du modèle slide pour la gestion du contexte RAG"""
    _inherit = 'slide.slide'

    # ============================================================================
    # CHAMPS CONTEXTE RAG
    # ============================================================================

    x_ai_context_id = fields.Char(
        string="Context ID RAG",
        readonly=True,
        copy=False,
        help="Identifiant du contexte RAG généré par l'API"
    )
    x_quiz_max_attempts = fields.Integer(
        string="Nombre max de tentatives (Quiz)",
        default=0,
        help="0 = illimité. Sinon, bloque la soumission quand le max est atteint."
    )

    x_ai_context_expires_at = fields.Datetime(
        string="Expiration du Contexte",
        readonly=True,
        copy=False,
        help="Date d'expiration du context_id"
    )

    x_ai_context_file_id = fields.Char(
        string="File ID Original",
        readonly=True,
        copy=False,
        help="Identifiant du fichier utilisé pour créer le contexte"
    )

    x_ai_context_is_expired = fields.Boolean(
        string="Contexte Expiré",
        compute='_compute_context_is_expired',
        store=False
    )

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends('x_ai_context_expires_at')
    def _compute_context_is_expired(self):
        """Vérifie si le contexte RAG est expiré"""
        for slide in self:
            if slide.x_ai_context_expires_at:
                slide.x_ai_context_is_expired = slide.x_ai_context_expires_at < fields.Datetime.now()
            else:
                slide.x_ai_context_is_expired = not bool(slide.x_ai_context_id)

    # ============================================================================
    # ACTIONS UTILISATEUR
    # ============================================================================

    def action_generate_summary(self):
        """Génère un résumé avec gestion automatique du contexte"""
        self.ensure_one()

        if self.slide_category not in ['document', 'article', 'infographic']:
            raise UserError(_("Génération impossible pour ce type de contenu"))

        provider_config = self._get_provider_config()

        return {
            'name': _('Générer un Résumé'),
            'type': 'ir.actions.act_window',
            'res_model': 'ai.summary.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_channel_id': self.channel_id.id,
                'default_slide_id': self.id,
                'default_provider_config_id': provider_config.id,
                'default_language': 'fr',
            }
        }

    def action_generate_question_targeted(self):
        """Génère une question ciblée"""
        self.ensure_one()
        provider_config = self._get_provider_config()

        return {
            'name': _('Générer une Question Ciblée'),
            'type': 'ir.actions.act_window',
            'res_model': 'ai.question.targeted.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_channel_id': self.channel_id.id,
                'default_slide_id': self.id,
                'default_provider_config_id': provider_config.id,
                'default_language': 'fr',
            }
        }

    def action_regenerate_context(self):
        """Force la régénération du contexte RAG pour ce slide"""
        self.ensure_one()

        if self.slide_category not in ['document', 'article', 'infographic']:
            raise UserError(_("La génération de contexte n'est possible que pour les documents et articles."))

        provider_config = self._get_provider_config()

        if not provider_config:
            raise UserError(_("Aucun fournisseur d'IA configuré pour ce cours."))

        # Prépare le contenu
        content = self._prepare_content_for_api()

        if not content:
            raise UserError(_("Ce chapitre ne contient pas de contenu exploitable pour l'IA."))

        # Appel API
        try:
            context_data = self._call_context_api(provider_config, content)

            # Sauvegarde
            self.sudo().write({
                'x_ai_context_id': context_data.get('context_id'),
                'x_ai_context_expires_at': context_data.get('metadata', {}).get('expires_at'),
                'x_ai_context_file_id': f"ODOO_SLIDE_{self.id}",
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('Le contexte RAG a été régénéré avec succès !'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            _logger.error(f"Erreur lors de la régénération du contexte : {str(e)}")
            raise UserError(_(
                "Erreur lors de la communication avec l'API IA.\n"
                "Détails : %s"
            ) % str(e))
        except Exception as e:
            _logger.error(f"Erreur inattendue : {str(e)}")
            raise UserError(_("Une erreur inattendue est survenue : %s") % str(e))

    # ============================================================================
    # MÉTHODES PRIVÉES
    # ============================================================================

    def _get_provider_config(self):
        """Récupère le fournisseur IA configuré"""
        self.ensure_one()

        provider = self.channel_id.ai_provider_config_id
        if not provider:
            provider = self.env['ai.provider.config'].search([('active', '=', True)], limit=1)
        if not provider:
            raise UserError(_("Aucun fournisseur d'IA configuré"))
        return provider

    def _prepare_content_for_api(self):
        """Prépare le contenu du slide pour l'envoi à l'API"""
        self.ensure_one()

        content = None

        if self.binary_content:
            # Contenu PDF/document
            content = self.binary_content.decode('utf-8')
        elif self.slide_category == 'article' and self.html_content:
            # Contenu HTML
            html_bytes = self.html_content.encode('utf-8')
            content = base64.b64encode(html_bytes).decode('utf-8')

        return content

    def _call_context_api(self, provider_config, content):
        """Appelle l'API pour créer/régénérer le contexte"""
        self.ensure_one()

        url = f"{provider_config.api_base_url.strip('/')}/contexts"
        headers = {
            'Authorization': f'Bearer {provider_config.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'file_id': f"ODOO_SLIDE_{self.id}",
            'file_content_base64': content,
            'file_name': self.name or f"slide_{self.id}.pdf",
        }

        _logger.info(f"Régénération du contexte pour slide '{self.name}'")

        response = requests.post(url, headers=headers, json=payload, timeout=180)
        response.raise_for_status()

        return response.json()

    def regenerate_context_if_needed(self):
        """Régénère le contexte si expiré - Utilisé par les wizards"""
        self.ensure_one()

        if not self.x_ai_context_id or self.x_ai_context_is_expired:
            _logger.info(f"Contexte expiré pour slide {self.id}, régénération...")

            provider_config = self._get_provider_config()
            content = self._prepare_content_for_api()

            if not content:
                raise UserError(_("Impossible de régénérer le contexte : contenu manquant"))

            context_data = self._call_context_api(provider_config, content)

            self.sudo().write({
                'x_ai_context_id': context_data.get('context_id'),
                'x_ai_context_expires_at': context_data.get('metadata', {}).get('expires_at'),
                'x_ai_context_file_id': f"ODOO_SLIDE_{self.id}",
            })

            return context_data.get('context_id')

        return self.x_ai_context_id
