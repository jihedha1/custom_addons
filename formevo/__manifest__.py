{
    'name': 'FORMEVO',
    'version': '17.0.1.0.0',
    'summary': 'Extension du module eLearning natif avec suivi du temps et progression avancée',
    'category': 'Education',
    'author': 'Yonn Technologies',
    'website': 'https://yonn.tech',
    'license': 'LGPL-3',
    'depends': [
        'web',
        'website_slides',
        'website',
        'portal',
        'muk_web_theme',
        'crm',
        'calendar',
        'survey',
        'hr',
        'project',
    ],
    'data': [
        'data/user_groups.xml',
        'data/theme_config.xml',
        'security/ir.model.access.csv',

        'wizard/user_group_wizard_view.xml',
        'wizard/course_assign_wizard_view.xml',
        'wizard/export_progress_wizard_view.xml',

        'views/course_progress_views.xml',
        'views/student_class_views.xml',
        'views/slide_views.xml',
        'views/slide_channel_views.xml',
        'views/tracking_views.xml',
        'views/website_formation_template.xml',
        #'views/website_rdv_form.xml',

        'views/menu.xml',
    ],
    'post_init_hook': 'configure_theme_automatically',

    'assets': {
        'web.assets_backend': [
            'formevo/static/src/scss/custom_colors.scss',
        ],
        'web.assets_frontend_lazy': [
            'formevo/static/src/js/completion_button_widget.js',
        ],

        # Website normal (hors fullscreen)
        'web.assets_frontend': [
            'formevo/static/src/js/yonn_frontend_security.js',
        ],
    },

    'icon': 'formevo/static/description/icon.jpg',
    'installable': True,
    'application': True,
    'auto_install': False,
}
