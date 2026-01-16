{
    'name': 'LMS - Compétences des Formateurs',
    'version': '17.0.1.0.0',
    'category': 'Learning Management System',
    'summary': 'Suivi des compétences et mises à jour des formateurs',
    'description': """
        Module de suivi des compétences et des mises à jour des formateurs pour la conformité Qualiopi.
        - Historique des interventions par formateur
        - Planification des mises à jour de compétences
        - Suivi des formations des formateurs
    """,
    'author': 'Yonnov\'IA',
    'website': 'https://www.yonnovia.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'lms_resources_trainers',
        'hr',
        'calendar',
    ],
    'data': [
        # Sécurité
        'security/ir.model.access.csv',
        'security/competency_security.xml',

        # Données
        'data/competency_data.xml',
        'data/competency_cron.xml',
        'data/mail_templates.xml',
        'data/competency_demo.xml',

        # Vues
        'views/competency_renewal_views.xml',
        'views/trainer_training_views.xml',
        'views/competency_dashboard_views.xml',
        'views/competency_menu_views.xml',

        # Wizards
        'wizards/renewal_planning_wizard_views.xml',
    ],
    'demo': [
        'data/competency_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}