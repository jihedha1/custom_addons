{
    'name': 'LMS Evaluation Results & Cold Assessment',
    'version': '1.0.0',
    'category': 'Education/Qualiopi',
    'summary': 'Évaluations à froid et tableau de bord résultats',
    'description': """
        Module d'évaluations à froid et tableau de bord résultats pour Qualiopi
        US-F2, F4

        Fonctionnalités :
        - Évaluations à froid (J+30/J+90)
        - Planificateur automatique des évaluations
        - Tableau de bord des résultats (satisfaction, réussite, abandons)
        - Rapports consolidés exportables
    """,
    'author': 'Votre Société',
    'website': 'https://www.votresociete.com',
    'depends': ['formevo', 'survey', 'website'],
    'data': [
        'security/evaluation_security.xml',
        'security/ir.model.access.csv',
        'data/evaluation_data.xml',
        'data/cold_assessment_cron.xml',
        'data/survey_templates_cold.xml',
        'views/cold_assessment_views.xml',
        'views/results_dashboard_views.xml',
        'views/slide_channel_views.xml',
        'views/evaluation_results_templates.xml',
        'views/evaluation_menu_views.xml',
        'wizards/schedule_assessment_wizard_views.xml',
        'wizards/export_results_wizard_views.xml',
    ],
    'demo': [
        'data/evaluation_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}