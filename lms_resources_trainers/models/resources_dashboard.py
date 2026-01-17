# custom_addons/lms_resources_trainers/models/resources_dashboard.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResourcesDashboard(models.TransientModel):
    """Dashboard transitoire pour statistiques ressources"""
    _name = 'lms_resources_trainers.dashboard'
    _description = 'Tableau de bord Ressources & Formateurs'

    # =====================
    # KPI FORMATEURS
    # =====================
    active_trainers = fields.Integer(
        string='Formateurs actifs',
        compute='_compute_trainer_stats'
    )

    trainers_percentage = fields.Float(
        string='% formateurs',
        compute='_compute_trainer_stats',
        digits=(5, 2)
    )

    @api.depends_context('company')
    def _compute_trainer_stats(self):
        """Calcule statistiques formateurs"""
        for dashboard in self:
            total_partners = self.env['res.partner'].search_count([])
            active_trainers = self.env['res.partner'].search_count([
                ('is_trainer', '=', True),
                ('trainer_state', '=', 'active')
            ])

            dashboard.active_trainers = active_trainers
            dashboard.trainers_percentage = (active_trainers / total_partners * 100) if total_partners else 0

    # =====================
    # KPI RESSOURCES
    # =====================
    available_resources = fields.Integer(
        string='Ressources disponibles',
        compute='_compute_resource_stats'
    )

    resources_utilization = fields.Float(
        string='Taux utilisation',
        compute='_compute_resource_stats',
        digits=(5, 2)
    )

    @api.depends_context('company')
    def _compute_resource_stats(self):
        """Calcule statistiques ressources"""
        for dashboard in self:
            total_resources = self.env['lms_resources_trainers.resource_management'].search_count([])
            available = self.env['lms_resources_trainers.resource_management'].search_count([
                ('state', '=', 'available')
            ])

            dashboard.available_resources = available
            dashboard.resources_utilization = (
                        (total_resources - available) / total_resources * 100) if total_resources else 0

    # =====================
    # KPI RÉSERVATIONS
    # =====================
    monthly_bookings = fields.Integer(
        string='Réservations du mois',
        compute='_compute_booking_stats'
    )

    bookings_growth = fields.Float(
        string='Croissance réservations',
        compute='_compute_booking_stats',
        digits=(5, 2)
    )

    @api.depends_context('company')
    def _compute_booking_stats(self):
        """Calcule statistiques réservations"""
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        for dashboard in self:
            today = datetime.today()
            first_day_current = today.replace(day=1)
            first_day_previous = first_day_current - relativedelta(months=1)

            current_month = self.env['lms_resources_trainers.resource_booking'].search_count([
                ('start_date', '>=', first_day_current),
                ('start_date', '<', today)
            ])

            previous_month = self.env['lms_resources_trainers.resource_booking'].search_count([
                ('start_date', '>=', first_day_previous),
                ('start_date', '<', first_day_current)
            ])

            dashboard.monthly_bookings = current_month
            dashboard.bookings_growth = (
                        (current_month - previous_month) / previous_month * 100) if previous_month else 0

    # =====================
    # KPI ÉVALUATIONS
    # =====================
    completed_evaluations = fields.Integer(
        string='Évaluations complétées',
        compute='_compute_evaluation_stats'
    )

    average_material_score = fields.Float(
        string='Note moyenne supports',
        compute='_compute_evaluation_stats',
        digits=(3, 2)
    )

    @api.depends_context('company')
    def _compute_evaluation_stats(self):
        """Calcule statistiques évaluations"""
        for dashboard in self:
            completed = self.env['lms_resources_trainers.material_evaluation'].search([
                ('state', '=', 'completed')
            ])

            dashboard.completed_evaluations = len(completed)

            if completed:
                scores = [e.overall_score for e in completed if e.overall_score]
                dashboard.average_material_score = sum(scores) / len(scores) if scores else 0.0
            else:
                dashboard.average_material_score = 0.0

    # =====================
    # GRAPHIQUES (Placeholder)
    # =====================
    trainers_by_status_chart = fields.Text(
        string='Graphique formateurs',
        compute='_compute_charts'
    )

    bookings_by_type_chart = fields.Text(
        string='Graphique réservations',
        compute='_compute_charts'
    )

    def _compute_charts(self):
        """Génère données pour graphiques"""
        for dashboard in self:
            # Placeholder - à implémenter avec Chart.js ou équivalent
            dashboard.trainers_by_status_chart = '{}'
            dashboard.bookings_by_type_chart = '{}'

    # =====================
    # ALERTES
    # =====================
    alerts_list = fields.One2many(
        'lms_resources_trainers.dashboard_alert',
        compute='_compute_alerts'
    )

    def _compute_alerts(self):
        """Génère liste des alertes"""
        for dashboard in self:
            # Documents expirant
            expiring_docs = self.env['lms_resources_trainers.trainer_document'].search([
                ('is_expiring_soon', '=', True),
                ('state', '=', 'valid')
            ])

            # Évaluations en retard
            overdue_evals = self.env['lms_resources_trainers.material_evaluation'].search([
                ('deadline_date', '<', fields.Date.today()),
                ('state', '=', 'in_progress')
            ])

            # Placeholder - liste vide pour l'instant
            dashboard.alerts_list = False

    # =====================
    # ÉVALUATIONS ACTIVES
    # =====================
    active_evaluations = fields.One2many(
        'lms_resources_trainers.material_evaluation',
        compute='_compute_active_evaluations'
    )

    def _compute_active_evaluations(self):
        """Liste évaluations en cours"""
        for dashboard in self:
            dashboard.active_evaluations = self.env['lms_resources_trainers.material_evaluation'].search([
                ('state', '=', 'in_progress')
            ], limit=10)


class DashboardAlert(models.TransientModel):
    """Alertes dashboard (modèle transitoire)"""
    _name = 'lms_resources_trainers.dashboard_alert'
    _description = 'Alerte Dashboard'

    type = fields.Selection([
        ('urgent', 'Urgent'),
        ('warning', 'Avertissement'),
        ('info', 'Information')
    ], string='Type', required=True)

    message = fields.Char(string='Message', required=True)
    date = fields.Date(string='Date', default=fields.Date.today)
    action = fields.Char(string='Action')