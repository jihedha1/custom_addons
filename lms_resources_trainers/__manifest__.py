{
    'name': 'LMS - Ressources & Formateurs',
    'version': '17.0.1.0.0',
    'category': 'Learning Management System',
    'summary': 'Gestion des formateurs, salles et ressources pédagogiques',
    'description': """
        Module de gestion des moyens humains et techniques pour la conformité Qualiopi.

        Fonctionnalités:
        - Fiches formateurs avec CV, diplômes, habilitations
        - Gestion des salles et ressources matérielles
        - Évaluations des supports pédagogiques
        - Planification et gestion des conflits
        - Alertes expiration automatiques (30 jours)
        - Purge formateurs inactifs (3 mois)
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
        'lms_public_info',  # CRITIQUE : Dépendance vers lms_public_info
    ],
    'data': [
        # Sécurité
        'security/ir.model.access.csv',
        'security/resources_security.xml',

        # Données
        'data/resources_data.xml',
        'data/resources_cron.xml',
        'data/mail_templates.xml',

        # Vues
        'views/trainer_profile_views.xml',
        'views/resource_management_views.xml',
        'views/material_evaluation_views.xml',
        'views/resources_calendar_views.xml',
        'views/resources_menu_views.xml',

        # Wizards
        'wizards/resource_booking_wizard_views.xml',
        'wizards/trainer_document_wizard_views.xml',
    ],

    'installable': True,
    'application': False,  # Module complémentaire
    'auto_install': False,
}