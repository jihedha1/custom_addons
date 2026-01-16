# custom_addons/lms_presence/__manifest__.py
{
    'name': 'LMS Presence & Accessibility Tracking',
    'version': '1.0.0',
    'category': 'Education/Qualiopi',
    'summary': 'Système de présence, handicap et relances conformes Qualiopi',
    'description': """
        Module de suivi de présence, accessibilité et traçabilité pour conformité Qualiopi
    """,
    'author': 'Votre Société',
    'website': 'https://www.votresociete.com',
    'depends': ['base', 'mail', 'calendar', 'website_slides',
                'formevo'],
    'data': [
        # 1. SÉCURITÉ - Groupes d'abord
        'security/presence_security.xml',
        # 2. SÉCURITÉ - CSV (modèles auto-générés à ce stade)
        'security/ir.model.access.csv',
        # 3. VUES
        'views/res_partner_views.xml',
        'views/attendance_session_views.xml',
        'views/attendance_line_views.xml',
        # 'views/slide_channel_views.xml',  # Commenté temporairement

        # 4. WIZARDS
        'wizards/batch_validation_wizard_views.xml',
        'views/session_log_views.xml',
        'views/presence_menu_views.xml',
        # 5. DATA - Templates et crons EN DERNIER
        'data/presence_mail_templates.xml',
        'data/presence_cron.xml',
        'data/presence_rules.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
