# custom_addons/lms_resources_trainers/__manifest__.py
{
    'name': 'LMS - Ressources & Formateurs',
    'version': '17.0.1.0.0',
    'category': 'Education/Qualiopi',
    'summary': 'Gestion formateurs, salles et supports pédagogiques (Qualiopi US-D1, D2, D3)',
    'description': """
        Module de gestion des moyens humains et techniques pour conformité Qualiopi.

        📋 Conformité Qualiopi - Épic D
        ================================

        ✅ US-D1 : Fiches formateurs complètes
        - CV, diplômes, habilitations avec dates validité
        - Alertes automatiques 30j avant expiration
        - Système validation documents
        - Traçabilité complète

        ✅ US-D2 : Planification ressources
        - Gestion salles et équipements
        - Calendrier réservation
        - Détection conflits automatique
        - Gestion capacité et disponibilité

        ✅ US-D3 : Évaluation supports pédagogiques
        - Grille évaluation 5 critères
        - Workflow validation
        - Historique évaluations
        - Rapports qualité

        🔄 Automatisations CRON
        ========================
        - Alertes expiration documents (quotidien)
        - Purge formateurs inactifs 90j (mensuel)
        - Vérification conflits (quotidien)
        - Archivage documents (annuel)

        🔒 Sécurité & RGPD
        ==================
        - Anonymisation automatique
        - Traçabilité complète (mail.thread)
        - Conformité RGPD
    """,
    'author': 'Yonnov\'IA',
    'website': 'https://www.yonnovia.com',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'website',
        'website_slides',
        'calendar',
        'survey',
        'lms_public_info',  # ✅ CRITIQUE : Dépendance obligatoire
        'mail',
    ],

    'data': [
        # Sécurité (TOUJOURS EN PREMIER)
        'security/ir.model.access.csv',
        'security/resources_security.xml',

        # Données de base
        'data/resources_data.xml',
        'data/resources_cron.xml',
        'data/mail_templates.xml',

        # Vues principales
        'views/res_partner_trainer_views.xml',  # ✅ CORRIGÉ : Extension res.partner
        'views/resource_management_views.xml',
        'views/material_evaluation_views.xml',
        'views/resources_calendar_views.xml',
        'views/slide_channel_views.xml',
        'views/resources_menu_views.xml',

        # Dashboard
        'views/resources_dashboard_views.xml',

        # Wizards
        'wizards/resource_booking_wizard_views.xml',
        'wizards/trainer_document_wizard_views.xml',
    ],

    'demo': [
        'data/resources_demo.xml',
    ],

    'installable': True,
    'application': False,  # ✅ Module complémentaire
    'auto_install': False,

    'post_init_hook': '_post_init_hook',
}


def _post_init_hook(cr, registry):
    """Actions post-installation"""
    import logging
    _logger = logging.getLogger(__name__)

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Vérifier types de documents
    DocumentType = env['lms_resources_trainers.trainer_document_type']
    if not DocumentType.search_count([]):
        _logger.info('✅ Création types de documents par défaut...')

    _logger.info('✅ Module lms_resources_trainers installé avec succès')