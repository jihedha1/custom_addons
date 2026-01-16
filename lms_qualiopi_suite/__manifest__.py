{
    'name': 'LMS Qualiopi - Suite Complète',
    'version': '17.0.1.0.0',
    'category': 'Education',
    'summary': 'Suite LMS conforme Qualiopi',
    'description': """
        Module méta qui installe tous les modules nécessaires
        pour une plateforme de formation conforme Qualiopi.

        Inclut:
        - Formevo Core (tracking, progression)
        - Information publique des formations
        - Gestion des présences
        - Qualité et non-conformités
        - Indicateurs publics
    """,
    'author': 'Yonn Technologies',
    'website': 'https://yonn.tech',
    'license': 'LGPL-3',
    'depends': [
        'formevo',
        'lms_public_info',
        'lms_presence',
        'lms_quality',
        'lms_public_kpi',
        'lms_objectives',
        'lms_resources_trainers',
        'lms_trainers_competency',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}