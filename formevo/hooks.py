from odoo import api, SUPERUSER_ID
import base64
import os

def setup_theme_config(env):
    """Configure les couleurs, logo et bannière automatiquement"""

    # Récupérer la société principale
    company = env['res.company'].search([('id', '=', 1)], limit=1)
    if company:
        # Charger et appliquer le logo
        logo_path = os.path.join(os.path.dirname(__file__), 'static/src/img/logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as logo_file:
                logo_data = base64.b64encode(logo_file.read())
                company.write({'logo': logo_data})

    # Appliquer les paramètres de couleurs du thème MuK
    try:
        env['ir.config_parameter'].sudo().set_param('muk_web_theme.primary_color', '#09171E')
        env['ir.config_parameter'].sudo().set_param('muk_web_theme.secondary_color', '#1B3E41')
        env['ir.config_parameter'].sudo().set_param('muk_web_theme.accent_color', '#2B6559')
        env['ir.config_parameter'].sudo().set_param('muk_web_theme.navbar_color', '#031F2D')
        env['ir.config_parameter'].sudo().set_param('muk_web_theme.background_color', '#274B4C')

        # Charger et appliquer la bannière du menu apps
        banner_path = os.path.join(os.path.dirname(__file__), 'static/src/img/banner.jpg')
        if os.path.exists(banner_path):
            with open(banner_path, 'rb') as banner_file:
                banner_data = base64.b64encode(banner_file.read())
                env['ir.config_parameter'].sudo().set_param('muk_web_theme.background_image', banner_data)
    except Exception as e:
        _logger = env.get('ir.logging').sudo()._logger()
        _logger.error(f"Erreur lors de la configuration du thème : {e}")
