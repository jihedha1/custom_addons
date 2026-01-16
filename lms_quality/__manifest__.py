# custom_addons/lms_quality/__manifest__.py
{
    'name': 'LMS Quality Management',
    'version': '17.0.1.0.0',
    'category': 'Education/Qualiopi',
    'summary': 'Gestion des non-conformités et actions correctives Qualiopi',
    'description': """
Module de gestion de la qualité pour la conformité Qualiopi
=============================================================

US-G1, G2, G3 du backlog Formevo

Fonctionnalités principales
----------------------------
* Déclaration et suivi de non-conformités
* Plan d'actions correctives avec échéances et responsables
* Tableau de bord qualité avec indicateurs
* Traçabilité complète des actions (audit trail)
* Workflow complet de traitement des NC
* Alertes automatiques (échéances, retards)
* Assistant de clôture avec checklist Qualiopi
* Indicateurs publics pour site web
* Rapports et statistiques qualité

Conformité Qualiopi
-------------------
* Critère 6 : Recueil et traitement des appréciations
* Critère 7 : Amélioration continue
* Traçabilité des preuves
* Exports pour audits
    """,
    'author': 'Yonnov\'IA',
    'website': 'https://www.yonnovia.com',
    'depends': [
        'base',
        'mail',
        'web',
        # ✅ CORRIGÉ : Dépendances optionnelles gérées différemment
        # 'formevo',  # Module parent LMS - si disponible
        # 'project',  # Pour tasks - si disponible
        # 'documents', # Pour archivage - si disponible
    ],
    'data': [
        # Sécurité (ordre important!)
        'security/quality_security.xml',
        'security/ir.model.access.csv',

        # Données de base
        'data/quality_data.xml',
        'data/quality_cron.xml',

        # Vues principales
        'views/non_conformity_views.xml',
        'views/corrective_action_views.xml',
        'views/quality_dashboard_views.xml',
        'views/quality_menu_views.xml',

        # Wizards
        'wizards/close_nc_wizard_views.xml',
    ],
    'demo': [
        'data/quality_demo.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 150,

    # ✅ AJOUTÉ : Post-install hook
    'post_init_hook': 'post_install_hook',
}