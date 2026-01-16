# custom_addons/lms_public_info/__manifest__.py
{
    'name': 'LMS Public Information',
    'version': '1.0.0',
    'category': 'Education/Qualiopi',
    'summary': 'Gestion des informations publiques et compétences formateur',
    'description': """
        Module de gestion des informations publiques pour conformité Qualiopi
        US-A1, A2, A3 + Compétences formateur

        Fonctionnalités :
        - Fiche formation avec objectifs, durée, prérequis, tarif
        - Prise de RDV en ligne avec création lead CRM
        - Publication/retrait avec filtres
        - Gestion des compétences formateur
        - Validation des champs obligatoires pour publication
    """,
    'author': 'Votre Société',
    'website': 'https://www.votresociete.com',
    'depends': ['formevo', 'crm', 'calendar', 'hr_skills','mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/public_info_security.xml',
        'data/public_info_data.xml',
        'data/mail_templates.xml',
        'views/trainer_competency_views.xml',
        'views/slide_channel_views.xml',
        'views/res_partner_views.xml',
        'views/website_public_info.xml',
        'views/public_info_menu_views.xml',
        'wizards/appointment_wizard_views.xml',
    ],
    'demo': [
        'data/public_info_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}