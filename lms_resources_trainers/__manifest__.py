{
    'name': 'LMS - Ressources & Formateurs',
    'version': '17.0.1.0.0',
    'category': 'Learning Management System',
    'summary': 'Gestion des formateurs, salles et ressources pédagogiques',
    'description': """
        Module de gestion des moyens humains et techniques pour la conformité Qualiopi.
        - Fiches formateurs avec CV, diplômes, habilitations
        - Gestion des salles et ressources matérielles
        - Évaluations des supports pédagogiques
        - Planification et gestion des conflits de ressources
    """,
    'author': 'Yonnov\'IA',
    'website': 'https://www.yonnovia.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'website',
        'website_slides',  # eLearning
        'calendar',
        'survey',
        'hr',
    ],
    'data': [
        # Sécurité
        'security/ir.model.access.csv',
        'security/resources_security.xml',

        # Données
        'data/resources_data.xml',
        'data/resources_cron.xml',
        'data/mail_templates.xml',
        'data/resources_demo.xml',

        # Vues
        'views/trainer_profile_views.xml',
        'views/resource_management_views.xml',
        'views/material_evaluation_views.xml',
        'views/slide_channel_views.xml',
        'views/res_partner_views.xml',
        'views/resources_calendar_views.xml',
        'views/resources_dashboard_views.xml',
        'views/resources_menu_views.xml',

        # Wizards
        'wizards/resource_booking_wizard_views.xml',
        'wizards/trainer_document_wizard_views.xml',
    ],
    'demo': [
        'data/resources_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}