# -*- coding: utf-8 -*-

def post_init_hook(cr, registry):
    """Post-initialization hook for Qualiopi Suite"""
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Activer les configurations par défaut
    config_params = env['ir.config_parameter'].sudo()

    # Configurer les paramètres Qualiopi
    default_configs = {
        'lms_qualiopi.enabled': 'True',
        'lms_qualiopi.version': 'V01',
        'lms_qualiopi.audit_mode': 'True',
        'lms_qualiopi.kpi_refresh_days': '30',
        'lms_qualiopi.document_retention_years': '5',
        'lms_qualiopi.notify_expiry_days': '30',
        'lms_qualiopi.auto_archive_months': '3',
    }

    for key, value in default_configs.items():
        if not config_params.get_param(key):
            config_params.set_param(key, value)

    # Créer les répertoires Documents par défaut
    documents_folder = env['documents.folder']

    qualiopi_folders = {
        'Qualiopi - Preuves': 'Preuves de conformité Qualiopi',
        'Qualiopi - Audits': 'Rapports et plans d\'audit',
        'Qualiopi - Actions Correctives': 'Plans d\'action et suivis',
        'Qualiopi - Indicateurs': 'KPI et tableaux de bord',
        'Qualiopi - Formateurs': 'Dossiers formateurs',
        'Qualiopi - Supports': 'Supports pédagogiques validés',
    }

    for folder_name, description in qualiopi_folders.items():
        if not documents_folder.search([('name', '=', folder_name)]):
            documents_folder.create({
                'name': folder_name,
                'description': description,
                'company_id': env.company.id,
            })

    # Configurer les modèles d'email par défaut
    _setup_default_email_templates(env)

    print("✅ Suite Qualiopi initialisée avec succès!")


def _setup_default_email_templates(env):
    """Configurer les modèles d'email par défaut"""
    # Cette fonction serait étendue avec des templates spécifiques
    pass


def uninstall_hook(cr, registry):
    """Cleanup lors de la désinstallation"""
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Supprimer les paramètres de configuration
    config_params = env['ir.config_parameter'].sudo()

    qualiopi_params = config_params.search([
        ('key', 'like', 'lms_qualiopi.%')
    ])
    qualiopi_params.unlink()

    print("🧹 Suite Qualiopi désinstallée proprement")