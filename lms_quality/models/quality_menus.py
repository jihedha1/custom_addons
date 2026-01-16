# custom_addons/lms_quality/models/quality_menus.py
# -*- coding: utf-8 -*-
"""
Modèles pour les tableaux de bord et indicateurs qualité
"""
from odoo import models, fields, api, _
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


class QualityDashboard(models.TransientModel):
    """
    Modèle transient pour le tableau de bord qualité
    Utilisé pour afficher les statistiques et indicateurs
    """
    _name = 'quality.dashboard'
    _description = 'Tableau de bord Qualité'

    # Statistiques générales
    count_nc_total = fields.Integer(
        string='Total NC',
        compute='_compute_statistics'
    )

    count_nc_open = fields.Integer(
        string='NC ouvertes (nombre)',
        compute='_compute_statistics'
    )

    count_nc_closed = fields.Integer(
        string='NC clôturées',
        compute='_compute_statistics'
    )

    count_nc_overdue = fields.Integer(
        string='NC en retard',
        compute='_compute_statistics'
    )

    # Par type
    count_nc_minor = fields.Integer(
        string='NC mineures',
        compute='_compute_statistics'
    )

    count_nc_major = fields.Integer(
        string='NC majeures',
        compute='_compute_statistics'
    )

    count_nc_critical = fields.Integer(
        string='NC critiques',
        compute='_compute_statistics'
    )

    # Période d'analyse
    date_from = fields.Date(
        string='Depuis',
        default=lambda self: date.today() - relativedelta(months=12)
    )

    date_to = fields.Date(
        string='Jusqu\'à',
        default=fields.Date.today
    )

    # Listes dynamiques
    open_nc_ids = fields.Many2many(
        'quality.non_conformity',
        string='NC ouvertes',
        compute='_compute_lists'
    )

    overdue_action_ids = fields.Many2many(
        'quality.corrective.action',
        string='Actions en retard',
        compute='_compute_lists'
    )

    @api.depends('date_from', 'date_to')
    def _compute_statistics(self):
        """Calcule les statistiques qualité"""
        for dashboard in self:
            domain = []
            if dashboard.date_from:
                domain.append(('detection_date', '>=', dashboard.date_from))
            if dashboard.date_to:
                domain.append(('detection_date', '<=', dashboard.date_to))

            NC = self.env['quality.non_conformity']

            # Tous les NC
            all_ncs = NC.search(domain)
            dashboard.count_nc_total = len(all_ncs)

            # Par état
            dashboard.count_nc_open = len(all_ncs.filtered(
                lambda n: n.state not in ['closed', 'cancelled']
            ))
            dashboard.count_nc_closed = len(all_ncs.filtered(
                lambda n: n.state == 'closed'
            ))
            dashboard.count_nc_overdue = len(all_ncs.filtered(
                lambda n: n.is_overdue
            ))

            # Par type
            dashboard.count_nc_minor = len(all_ncs.filtered(
                lambda n: n.type == 'minor'
            ))
            dashboard.count_nc_major = len(all_ncs.filtered(
                lambda n: n.type == 'major'
            ))
            dashboard.count_nc_critical = len(all_ncs.filtered(
                lambda n: n.type == 'critical'
            ))

    @api.depends('date_from', 'date_to')
    def _compute_lists(self):
        """Prépare les listes pour affichage"""
        for dashboard in self:
            # NC ouvertes
            dashboard.open_nc_ids = self.env['quality.non_conformity'].search([
                ('state', 'not in', ['closed', 'cancelled'])
            ])

            # Actions en retard
            dashboard.overdue_action_ids = self.env['quality.corrective.action'].search([
                ('is_overdue', '=', True)
            ])

    def action_view_nc(self, state_filter=None):
        """Ouvre la vue des NC avec filtre"""
        action = self.env.ref('lms_quality.action_non_conformity').read()[0]

        if state_filter:
            action['domain'] = [('state', '=', state_filter)]

        return action

    def action_view_overdue_actions(self):
        """Ouvre la vue des actions en retard"""
        return {
            'name': _('Actions en retard'),
            'type': 'ir.actions.act_window',
            'res_model': 'quality.corrective.action',
            'view_mode': 'tree,form',
            'domain': [('is_overdue', '=', True)],
            'context': {'search_default_overdue': 1}
        }


class QualityIndicator(models.Model):
    """
    Indicateurs qualité publics pour conformité Qualiopi
    """
    _name = 'quality.indicator'
    _description = 'Indicateur qualité public'
    _order = 'period desc, indicator_type'

    name = fields.Char(
        string='Nom de l\'indicateur',
        required=True,
        compute='_compute_name',
        store=True
    )

    indicator_type = fields.Selection([
        ('satisfaction', 'Taux de satisfaction'),
        ('success', 'Taux de réussite'),
        ('completion', 'Taux de complétion'),
        ('complaint', 'Taux de réclamation'),
        ('nc_rate', 'Taux de non-conformité'),
        ('response_time', 'Délai moyen de réponse'),
    ], string='Type', required=True)

    period = fields.Selection([
        ('month', 'Mensuel'),
        ('quarter', 'Trimestriel'),
        ('year', 'Annuel'),
    ], string='Période', required=True, default='quarter')

    date_from = fields.Date(
        string='Date début',
        required=True
    )

    date_to = fields.Date(
        string='Date fin',
        required=True
    )

    value = fields.Float(
        string='Valeur (%)',
        digits=(5, 2)
    )

    target = fields.Float(
        string='Objectif (%)',
        digits=(5, 2)
    )

    is_published = fields.Boolean(
        string='Publié',
        default=False,
        help='Afficher sur le site web'
    )

    source = fields.Text(
        string='Source des données',
        help='Traçabilité de la mesure'
    )

    comments = fields.Html(
        string='Commentaires',
        help='Analyse et actions si nécessaire'
    )

    @api.depends('indicator_type', 'date_from', 'date_to')
    def _compute_name(self):
        """Génère le nom de l'indicateur"""
        for indicator in self:
            type_label = dict(self._fields['indicator_type'].selection).get(
                indicator.indicator_type, ''
            )
            period_label = dict(self._fields['period'].selection).get(
                indicator.period, ''
            )

            indicator.name = f"{type_label} - {period_label} - {indicator.date_from.strftime('%m/%Y') if indicator.date_from else ''}"

    @api.model
    def compute_nc_indicators(self, date_from, date_to):
        """
        Calcule automatiquement les indicateurs basés sur les NC
        """
        NC = self.env['quality.non_conformity']

        # Domaine de période
        domain = [
            ('detection_date', '>=', date_from),
            ('detection_date', '<=', date_to),
        ]

        ncs = NC.search(domain)

        # Calculer taux de NC
        total_formations = 100  # À récupérer depuis module formations
        nc_rate = (len(ncs) / total_formations * 100) if total_formations > 0 else 0

        # Calculer délai moyen de traitement
        closed_ncs = ncs.filtered(lambda n: n.state == 'closed' and n.closure_date)
        if closed_ncs:
            total_days = sum([
                (nc.closure_date - nc.detection_date).days
                for nc in closed_ncs
            ])
            avg_response_time = total_days / len(closed_ncs)
        else:
            avg_response_time = 0

        return {
            'nc_rate': nc_rate,
            'response_time': avg_response_time,
            'total_nc': len(ncs),
            'closed_nc': len(closed_ncs),
        }