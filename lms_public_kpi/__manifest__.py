# custom_addons/lms_public_kpi/__manifest__.py
{
    'name': 'LMS Public KPIs',
    'version': '17.0.1.0.0',  # ✅ Version Odoo 17
    'category': 'Education/Qualiopi',
    'summary': 'Indicateurs publics Qualiopi pour site web',
    'description': """
        Module de gestion et publication des indicateurs publics Qualiopi

        Conformité Épic H - US-H1, H2
        ================================

        Fonctionnalités :
        -----------------
        - Publication de KPIs sur le site web (US-H1)
        - Mise à jour manuelle et automatique (US-H2)
        - Historique des versions et snapshots
        - Calculs automatiques depuis les données
        - Interface de gestion backend
        - API JSON publique
        - Widgets website intégrables

        Conformité Qualiopi :
        --------------------
        - Critère 1 : Information du public
        - Critère 7 : Amélioration continue
        - Transparence et traçabilité
        - Mise à jour périodique
    """,
    'author': 'Yonnov\'IA',
    'website': 'https://www.yonnovia.com',
    'depends': [
        'base',
        'mail',
        'website',
        'website_slides',  # ✅ Pour eLearning
        'survey',  # ✅ Pour enquêtes satisfaction
    ],
    'data': [
        # Sécurité (doit être en premier)
        'security/public_kpi_security.xml',
        'security/ir.model.access.csv',

        # Données de base
        'data/public_kpi_categories.xml',
        'data/public_kpi_cron.xml',

        # Vues backend
        'views/public_kpi_snapshot_views.xml',
        'views/public_kpi_version_views.xml',
        'views/public_kpi_category_views.xml',  # ✅ AJOUT
        'views/public_kpi_menu_views.xml',

        # Templates website
        'views/website_kpis_template.xml',

        'reports/kpi_reports.xml',
    ],
    'demo': [
        'data/public_kpi_demo.xml',
    ],
    'assets': {  # ✅ AJOUT assets pour CSS/JS personnalisé
        'web.assets_frontend': [
            'lms_public_kpi/static/src/css/kpi_public.css',
        ],

    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 100,
}