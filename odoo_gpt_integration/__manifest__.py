{
    'name': "Intégration IA GPT pour E-Learning",
    'version': '1.0',
    'summary': "Génère des résumés et des quiz pour les cours Odoo via une API GPT externe.",
    'author': "Hallem Jihed",
    'category': 'Website/eLearning',
    'depends': [
        'website_slides', 'mail', 'base'
    ],  # Dépendance cruciale au module eLearning d'Odoo
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/ai_config_views.xml',
        'views/ai_wizards_views.xml',
        'views/slide_question_wizard_views.xml',
        'views/slide_channel_views.xml',
        'views/slide_question_views.xml',
        'views/website_quiz_templates.xml',
        'views/correction_wizard_views.xml',
        'views/keyword_scoring_views.xml',
        'views/pending_answer_views.xml',
        'views/my_quiz_results.xml',
        'views/portal_quiz_button_views.xml',
        'views/slide_quiz_attempts_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'odoo_gpt_integration/static/src/js/quiz_frontend.js',
            'odoo_gpt_integration/static/src/scss/quiz_styles.scss',
            'odoo_gpt_integration/static/src/js/portal_results.js'
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
