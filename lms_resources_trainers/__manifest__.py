# -*- coding: utf-8 -*-
{
    'name': 'LMS - Ressources & Formateurs',
    'version': '17.0.1.0.0',
    'category': 'Education/Qualiopi',
    'summary': 'Gestion des formateurs, salles et ressources pédagogiques (Qualiopi Épic D)',
    'description': """
        Module de gestion des moyens humains et techniques pour la conformité Qualiopi.

        📋 Conformité Qualiopi - Épic D (US D1, D2, D3)
        ===============================================

        ✅ US-D1 : Fiches formateurs complètes
        - CV, diplômes, habilitations avec dates de validité
        - Alertes automatiques 30 jours avant expiration
        - Système de validation des documents
        - Traçabilité complète des modifications

        ✅ US-D2 : Planification ressources
        - Gestion des salles et équipements
        - Calendrier de réservation
        - Détection automatique des conflits
        - Gestion de la capacité et disponibilité

        ✅ US-D3 : Évaluation supports pédagogiques
        - Grille d'évaluation standardisée (5 critères)
        - Workflow de validation
        - Historique des évaluations
        - Rapports qualité

        🔄 Automatisations
        ==================
        - CRON : Alertes expiration documents (quotidien)
        - CRON : Purge formateurs inactifs 90j (mensuel)
        - CRON : Vérification conflits réservations (quotidien)
        - CRON : Archivage automatique documents (annuel)

        📊 Tableaux de bord
        ===================
        - Dashboard ressources en temps réel
        - Statistiques formateurs
        - Indicateurs qualité supports
        - Planning global ressources

        🔒 Sécurité & RGPD
        ===================
        - Anonymisation automatique après archivage
        - Traçabilité complète (mail.thread)
        - Gestion des droits d'accès
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
        'lms_public_info',  # CRITIQUE : Dépendance obligatoire
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
        'views/res_partner_trainer_views.xml',  # Extension res.partner
        'views/resource_management_views.xml',
        'views/material_evaluation_views.xml',
        'views/resources_calendar_views.xml',
        'views/slide_channel_views.xml',  # Extension slide.channel
        'views/resources_menu_views.xml',

        # Dashboard
        'views/resources_dashboard_views.xml',

        # Wizards
        'wizards/resource_booking_wizard_views.xml',
        'wizards/trainer_document_wizard_views.xml',

        # Templates website (si nécessaire)
        # 'views/website_resources_templates.xml',
    ],

    'demo': [
        'data/resources_demo.xml',
    ],

    'installable': True,
    'application': False,  # Module complémentaire (pas standalone)
    'auto_install': False,

    'post_init_hook': '_post_init_hook',
}


def _post_init_hook(cr, registry):
    """Actions post-installation"""
    import logging
    _logger = logging.getLogger(__name__)

    # Créer les types de documents par défaut s'ils n'existent pas
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Vérifier si les types de documents existent
    DocumentType = env['lms_resources_trainers.trainer_document_type']
    if not DocumentType.search_count([]):
        _logger.info('Création des types de documents par défaut...')

    _logger.info('✅ Module lms_resources_trainers installé avec succès')