# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)

class AiProviderConfig(models.Model):
    _name = 'ai.provider.config'

    _description = "Configuration d'un Fournisseur d'IA"

    _order = 'sequence, name'

    name = fields.Char(
        string="Nom de la Configuration",
        required=True,
        help="Ex: 'GPT-4 Turbo', 'Claude 3 Sonnet', 'Modèle Local Llama3'"
    )

    provider_type = fields.Selection(
        [('openai', 'OpenAI'), ('anthropic', 'Anthropic'), ('google', 'Google Gemini'), ('custom', 'Personnalisé')],
        string="Type de Fournisseur",
        default='custom',
        required=True
    )

    api_base_url = fields.Char(string="URL de Base de l'API")

    api_key = fields.Char(string="Clé d'API", help="Votre clé secrète pour ce fournisseur.")

    active = fields.Boolean(default=True, help="Seules les configurations actives seront proposées aux utilisateurs.")

    sequence = fields.Integer(default=10)

    # ===== CHAMPS MANQUANTS =====

    model_name = fields.Char(
        string="Nom du Modèle",
        help="Ex: gpt-4, claude-3-sonnet, gemini-pro"
    )

    temperature = fields.Float(
        string="Température",
        default=0.7,
        help="Entre 0 et 1. Plus bas = plus déterministe, plus haut = plus créatif"
    )

    max_tokens = fields.Integer(
        string="Tokens Maximum",
        default=2000,
        help="Nombre maximum de tokens pour la réponse"
    )

    timeout = fields.Integer(
        string="Timeout (secondes)",
        default=30,
        help="Délai d'attente maximum pour les appels API"
    )

    notes = fields.Text(
        string="Notes",
        help="Notes internes sur cette configuration"
    )

    total_requests = fields.Integer(
        string="Nombre de Requêtes",
        default=0,
        readonly=True,
        help="Nombre total de requêtes effectuées avec cette configuration"
    )

    last_request_date = fields.Datetime(
        string="Dernière Requête",
        readonly=True,
        help="Date et heure de la dernière utilisation de cette configuration"
    )

    # ===== MÉTHODE POUR TESTER LA CONNEXION =====
    def action_test_connection(self):
        """Teste la connexion avec le fournisseur IA (appelé depuis un bouton type=object)"""
        self.ensure_one()

        if not self.api_base_url or not self.api_key:
            raise UserError(_("Configuration incomplète (URL ou clé API manquante)."))

        base_url = (self.api_base_url or "").strip().rstrip("/")
        timeout = self.timeout or 15

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # -----------------------------
        # 1) TEST HEALTH (soft)
        # -----------------------------
        health_url = f"{base_url}/health"

        try:
            r = requests.get(health_url, headers=headers, timeout=timeout)
            _logger.info("AI test_connection: url=%s status=%s", health_url, r.status_code)

            self.sudo().write({
                "total_requests": (self.total_requests or 0) + 1,
                "last_request_date": fields.Datetime.now(),
            })

            if not (200 <= r.status_code < 300):
                msg = _("Connexion échouée (health). Code HTTP: %s\nRéponse: %s") % (
                    r.status_code,
                    (r.text or "")[:500]
                )
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Erreur"),
                        "message": msg,
                        "type": "danger",
                        "sticky": True,
                    },
                }

            # Si model_name n'est pas défini, on met un fallback raisonnable
            model = (self.model_name or "").strip() or "openai/gpt-4o-mini"

            completions_url = f"{base_url}/chat/completions"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
                "temperature": 0,
            }

            r2 = requests.post(completions_url, headers=headers, json=payload, timeout=timeout)
            _logger.info("AI test_completion: url=%s status=%s", completions_url, r2.status_code)

            # Stats : 2ème requête
            self.sudo().write({
                "total_requests": (self.total_requests or 0) + 1,
                "last_request_date": fields.Datetime.now(),
            })

            if not (200 <= r2.status_code < 300):
                # Message plus lisible selon les cas fréquents
                if r2.status_code in (401, 403):
                    friendly = _("Clé API invalide ou droits insuffisants.")
                elif r2.status_code == 404:
                    friendly = _("Endpoint ou modèle introuvable (vérifiez api_base_url et model_name).")
                elif r2.status_code == 429:
                    friendly = _("Quota dépassé / rate limit atteint.")
                else:
                    friendly = _("Erreur lors du test IA.")

                msg = _("Health OK (200) mais test IA échoué.\n%s\nHTTP: %s\nRéponse: %s") % (
                    friendly,
                    r2.status_code,
                    (r2.text or "")[:800]
                )
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Erreur"),
                        "message": msg,
                        "type": "danger",
                        "sticky": True,
                    },
                }

            # Optionnel : extraire un bout de réponse pour confirmer
            try:
                data = r2.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                content = (content or "").strip()
            except Exception:
                content = ""

            success_msg = _("Connexion OK (health + test IA).")
            if content:
                success_msg += _(" Réponse: %s") % content[:80]

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Succès"),
                    "message": success_msg,
                    "type": "success",
                    "sticky": False,
                },
            }

        except requests.exceptions.Timeout:
            raise UserError(_("Timeout: le serveur IA ne répond pas."))
        except requests.exceptions.RequestException as e:
            raise UserError(_("Erreur de connexion: %s") % str(e))
