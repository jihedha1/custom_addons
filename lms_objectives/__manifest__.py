{
    'name': 'LMS Objectives & Placement Assessment',
    'version': '1.0.0',
    'category': 'Education/Qualiopi',
    'summary': 'Objectifs SMART, positionnement et plans individualisés',
    'description': """
        Module de gestion des objectifs pédagogiques et positionnement pour Qualiopi
        US-B1, B2, B3

        Fonctionnalités :
        - Objectifs pédagogiques mesurables (SMART)
        - Questionnaires de positionnement avant formation
        - Plans de formation individualisés
        - Intégration avec Surveys Odoo
    """,
    'author': 'Votre Société',
    'website': 'https://www.votresociete.com',
    'depends': ['formevo', 'survey'],
    'data': [
        'security/objectives_security.xml',
        'security/ir.model.access.csv',

        'data/objectives_data.xml',
        'data/survey_templates.xml',
        'data/placement_cron.xml',
        'views/smart_objective_views.xml',
        'views/placement_assessment_views.xml',
        'views/individual_plan_views.xml',
        'views/slide_channel_views.xml',
        'views/res_partner_views.xml',
        'views/plan_template_views.xml',
        #'views/objectives_dashboard.xml',
        'views/objectives_menu_views.xml',
        'wizards/generate_plan_wizard_views.xml',
        'wizards/assign_assessment_wizard_views.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}