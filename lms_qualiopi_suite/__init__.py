{
    'name': 'LMS Qualiopi Suite - Bundle Complet',
    'version': '17.0.1.0.0',
    'category': 'Learning Management System',
    'summary': 'Suite complète LMS conforme Qualiopi pour Odoo v17',
    'description': """
        Bundle complet incluant tous les modules LMS pour la certification Qualiopi.

        Modules inclus:
        1.  lms_public_info - Information publique (Épic A)
        2.  lms_objectives - Objectifs pédagogiques (Épic B)
        3.  lms_presence - Suivi présence & accessibilité (Épic C)
        4.  lms_resources_trainers - Ressources & formateurs (Épic D)
        5.  lms_trainers_competency - Compétences formateurs (Épic E)
        6.  lms_evaluation_results - Évaluations & résultats (Épic F)
        7.  lms_quality - Amélioration continue (Épic G)
        8.  lms_public_kpi - Indicateurs publics (Épic H)

        Conforme au référentiel national Qualiopi pour les organismes de formation.
    """,
    'author': 'Yonnov\'IA',
    'website': 'https://www.yonnovia.com',
    'license': 'LGPL-3',
    'depends': [
        'formevo',  # Module core existant
        'lms_public_info',
        'lms_objectives',
        'lms_presence',
        'lms_resources_trainers',
        'lms_trainers_competency',
        'lms_evaluation_results',
        'lms_quality',
        'lms_public_kpi',
    ],
    'data': [
        # Configuration automatique
        'data/qualiopi_configuration.xml',
        'data/default_data.xml',
    ],
    'demo': [
        'data/qualiopi_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}