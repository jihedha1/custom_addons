# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json


class ResultsDashboard(models.TransientModel):
    """
    Tableau de bord des résultats - Conformité Qualiopi US-F4
    """
    _name = 'lms_evaluation_results.results_dashboard'
    _description = 'Tableau de bord des résultats'

    # ========== FILTRES ==========
    period = fields.Selection([
        ('week', 'Semaine'),
        ('month', 'Mois'),
        ('quarter', 'Trimestre'),
        ('year', 'Année'),
        ('custom', 'Personnalisé'),
    ], string='Période', default='month', required=True)

    date_start = fields.Date(
        string='Date début',
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )

    date_end = fields.Date(
        string='Date fin',
        default=fields.Date.today
    )

    channel_ids = fields.Many2many(
        'slide.channel',
        string='Formations',
        help="Filtrer par formations spécifiques"
    )

    trainer_id = fields.Many2one(
        'res.partner',
        string='Formateur',
        domain="[('is_company', '=', False)]"
    )

    # ========== INDICATEURS GLOBAUX ==========
    total_participants = fields.Integer(
        string='Total participants',
        compute='_compute_global_indicators'
    )

    total_completions = fields.Integer(
        string='Total formations terminées',
        compute='_compute_global_indicators'
    )

    completion_rate = fields.Float(
        string='Taux de complétion (%)',
        compute='_compute_global_indicators',
        digits=(5, 2)
    )

    success_rate = fields.Float(
        string='Taux de réussite (%)',
        compute='_compute_global_indicators',
        digits=(5, 2)
    )

    satisfaction_rate = fields.Float(
        string='Taux de satisfaction (%)',
        compute='_compute_global_indicators',
        digits=(5, 2)
    )

    dropout_rate = fields.Float(
        string="Taux d'abandon (%)",
        compute='_compute_global_indicators',
        digits=(5, 2)
    )

    # ========== ÉVALUATIONS ==========
    hot_assessment_rate = fields.Float(
        string='Taux réponse éval. à chaud (%)',
        compute='_compute_assessment_indicators',
        digits=(5, 2)
    )

    cold_assessment_rate = fields.Float(
        string='Taux réponse éval. à froid (%)',
        compute='_compute_assessment_indicators',
        digits=(5, 2)
    )

    cold_assessments_sent = fields.Integer(
        string='Évaluations à froid envoyées',
        compute='_compute_assessment_indicators'
    )

    cold_assessments_completed = fields.Integer(
        string='Évaluations à froid complétées',
        compute='_compute_assessment_indicators'
    )

    professional_impact_rate = fields.Float(
        string='Taux impact professionnel (%)',
        compute='_compute_assessment_indicators',
        digits=(5, 2)
    )

    # ========== GRAPHIQUES (JSON) ==========
    chart_completion_trend = fields.Text(
        string='Tendance complétion',
        compute='_compute_charts'
    )

    chart_satisfaction_trend = fields.Text(
        string='Tendance satisfaction',
        compute='_compute_charts'
    )

    chart_success_by_channel = fields.Text(
        string='Réussite par formation',
        compute='_compute_charts'
    )

    chart_assessment_response_rates = fields.Text(
        string='Taux de réponse évaluations',
        compute='_compute_charts'
    )

    # ========== TOP PERFORMERS ==========
    top_channels = fields.Text(
        string='Meilleures formations',
        compute='_compute_performers'
    )

    bottom_channels = fields.Text(
        string='Formations à améliorer',
        compute='_compute_performers'
    )

    top_trainers = fields.Text(
        string='Meilleurs formateurs',
        compute='_compute_performers'
    )

    # ========== MÉTHODES COMPUTE ==========
    @api.depends('period', 'date_start', 'date_end', 'channel_ids', 'trainer_id')
    def _compute_global_indicators(self):
        """Calcule les indicateurs globaux"""
        for dashboard in self:
            domain = dashboard._get_base_domain()

            # Intégration avec formevo
            if 'yonn.course.progress' in self.env:
                progress_recs = self.env['yonn.course.progress'].search(domain)

                dashboard.total_participants = len(set(progress_recs.mapped('partner_id').ids))
                dashboard.total_completions = len(progress_recs.filtered(
                    lambda r: r.completion_percentage >= 100.0
                ))

                if progress_recs:
                    dashboard.completion_rate = (
                        dashboard.total_completions / len(progress_recs)
                    ) * 100.0
                else:
                    dashboard.completion_rate = 0.0

                success = len(progress_recs.filtered(
                    lambda r: r.completion_percentage >= 50.0
                ))
                dashboard.success_rate = (
                    (success / len(progress_recs)) * 100.0
                ) if progress_recs else 0.0

                active = progress_recs.filtered(lambda r: r.last_activity)
                if active:
                    dropout = len(active.filtered(
                        lambda r: r.completion_percentage < 20.0
                    ))
                    dashboard.dropout_rate = (dropout / len(active)) * 100.0
                else:
                    dashboard.dropout_rate = 0.0

            else:
                dashboard.total_participants = 0
                dashboard.total_completions = 0
                dashboard.completion_rate = 0.0
                dashboard.success_rate = 0.0
                dashboard.dropout_rate = 0.0

            # Satisfaction
            satisfaction_scores = []

            cold_domain = dashboard._get_base_domain()
            cold_domain.append(('state', '=', 'completed'))
            cold_assessments = self.env['lms_evaluation_results.cold_assessment'].search(
                cold_domain
            )

            if cold_assessments:
                avg_cold = sum(cold_assessments.mapped('satisfaction_rate')) / len(cold_assessments)
                satisfaction_scores.append(avg_cold)

            dashboard.satisfaction_rate = (
                sum(satisfaction_scores) / len(satisfaction_scores)
            ) if satisfaction_scores else 0.0

    @api.depends('period', 'date_start', 'date_end', 'channel_ids', 'trainer_id')
    def _compute_assessment_indicators(self):
        """Calcule les indicateurs liés aux évaluations"""
        for dashboard in self:
            domain = dashboard._get_base_domain()

            cold_assessments = self.env['lms_evaluation_results.cold_assessment'].search(domain)

            dashboard.cold_assessments_sent = len(cold_assessments.filtered(
                lambda a: a.state in ['sent', 'in_progress', 'completed', 'expired']
            ))

            dashboard.cold_assessments_completed = len(cold_assessments.filtered(
                lambda a: a.state == 'completed'
            ))

            if dashboard.cold_assessments_sent > 0:
                dashboard.cold_assessment_rate = (
                    dashboard.cold_assessments_completed / dashboard.cold_assessments_sent
                ) * 100.0
            else:
                dashboard.cold_assessment_rate = 0.0

            dashboard.hot_assessment_rate = 0.0

            completed = cold_assessments.filtered(lambda a: a.state == 'completed')
            if completed:
                applied = len(completed.filtered(lambda a: a.applied_skills))
                dashboard.professional_impact_rate = (applied / len(completed)) * 100.0
            else:
                dashboard.professional_impact_rate = 0.0

    @api.depends('period', 'date_start', 'date_end', 'channel_ids', 'trainer_id')
    def _compute_charts(self):
        """Génère les données des graphiques en JSON"""
        for dashboard in self:
            completion_data = dashboard._get_completion_trend()
            dashboard.chart_completion_trend = json.dumps(completion_data)

            satisfaction_data = dashboard._get_satisfaction_trend()
            dashboard.chart_satisfaction_trend = json.dumps(satisfaction_data)

            success_data = dashboard._get_success_by_channel()
            dashboard.chart_success_by_channel = json.dumps(success_data)

            response_data = [{
                'label': 'À chaud',
                'value': dashboard.hot_assessment_rate
            }, {
                'label': 'À froid',
                'value': dashboard.cold_assessment_rate
            }]
            dashboard.chart_assessment_response_rates = json.dumps(response_data)

    @api.depends('period', 'date_start', 'date_end', 'channel_ids', 'trainer_id')
    def _compute_performers(self):
        """Calcule les top/bottom performers"""
        for dashboard in self:
            top_data = dashboard._get_top_channels(limit=5)
            dashboard.top_channels = json.dumps(top_data)

            bottom_data = dashboard._get_bottom_channels(limit=5)
            dashboard.bottom_channels = json.dumps(bottom_data)

            trainer_data = dashboard._get_top_trainers(limit=5)
            dashboard.top_trainers = json.dumps(trainer_data)

    # ========== MÉTHODES PRIVÉES ==========
    def _get_base_domain(self):
        """Construit le domaine de recherche de base"""
        self.ensure_one()

        domain = []

        date_start, date_end = self._get_period_dates()
        if date_start and date_end:
            domain.append(('create_date', '>=', date_start))
            domain.append(('create_date', '<=', date_end))

        if self.channel_ids:
            domain.append(('course_id', 'in', self.channel_ids.ids))

        if self.trainer_id:
            channels = self.env['slide.channel'].search([
                ('user_id.partner_id', '=', self.trainer_id.id)
            ])
            domain.append(('course_id', 'in', channels.ids))

        return domain

    def _get_period_dates(self):
        """Retourne les dates de début et fin selon la période"""
        self.ensure_one()

        today = fields.Date.today()

        if self.period == 'custom':
            return self.date_start, self.date_end
        elif self.period == 'week':
            start = today - timedelta(days=7)
            return start, today
        elif self.period == 'month':
            start = today - timedelta(days=30)
            return start, today
        elif self.period == 'quarter':
            start = today - timedelta(days=90)
            return start, today
        elif self.period == 'year':
            start = today - timedelta(days=365)
            return start, today

        return None, None

    def _get_completion_trend(self):
        """Retourne la tendance de complétion sur 6 mois"""
        self.ensure_one()

        if 'yonn.course.progress' not in self.env:
            return []

        data = []
        today = fields.Date.today()

        for i in range(5, -1, -1):
            start = today - timedelta(days=(i + 1) * 30)
            end = today - timedelta(days=i * 30)

            domain = self._get_base_domain()
            domain.append(('last_activity', '>=', start))
            domain.append(('last_activity', '<', end))

            recs = self.env['yonn.course.progress'].search(domain)

            if recs:
                avg = sum(recs.mapped('completion_percentage')) / len(recs)
            else:
                avg = 0.0

            data.append({
                'label': start.strftime('%m/%Y'),
                'value': round(avg, 2)
            })

        return data

    def _get_satisfaction_trend(self):
        """Retourne la tendance de satisfaction sur 6 mois"""
        self.ensure_one()

        data = []
        today = fields.Date.today()

        for i in range(5, -1, -1):
            start = today - timedelta(days=(i + 1) * 30)
            end = today - timedelta(days=i * 30)

            domain = self._get_base_domain()
            domain.append(('scheduled_date', '>=', start))
            domain.append(('scheduled_date', '<', end))
            domain.append(('state', '=', 'completed'))

            assessments = self.env['lms_evaluation_results.cold_assessment'].search(domain)

            if assessments:
                avg = sum(assessments.mapped('satisfaction_rate')) / len(assessments)
            else:
                avg = 0.0

            data.append({
                'label': start.strftime('%m/%Y'),
                'value': round(avg, 2)
            })

        return data

    def _get_success_by_channel(self):
        """Retourne le taux de réussite par formation"""
        self.ensure_one()

        if 'yonn.course.progress' not in self.env:
            return []

        data = []
        domain = self._get_base_domain()

        progress_recs = self.env['yonn.course.progress'].search(domain)
        channels = set(progress_recs.mapped('course_id'))

        for channel in channels:
            channel_recs = progress_recs.filtered(lambda r: r.course_id == channel)

            if channel_recs:
                success = len(channel_recs.filtered(
                    lambda r: r.completion_percentage >= 100.0
                ))
                rate = (success / len(channel_recs)) * 100.0

                data.append({
                    'channel_id': channel.id,
                    'label': channel.name,
                    'value': round(rate, 2)
                })

        data.sort(key=lambda x: x['value'], reverse=True)
        return data[:10]

    def _get_top_channels(self, limit=5):
        """Retourne les meilleures formations"""
        data = self._get_success_by_channel()
        return data[:limit]

    def _get_bottom_channels(self, limit=5):
        """Retourne les formations à améliorer"""
        data = self._get_success_by_channel()
        data.sort(key=lambda x: x['value'])
        return data[:limit]

    def _get_top_trainers(self, limit=5):
        """Retourne les meilleurs formateurs"""
        self.ensure_one()

        if 'yonn.course.progress' not in self.env:
            return []

        data = []
        domain = self._get_base_domain()

        progress_recs = self.env['yonn.course.progress'].search(domain)
        channels = set(progress_recs.mapped('course_id'))

        trainer_map = {}
        for channel in channels:
            if not channel.user_id or not channel.user_id.partner_id:
                continue

            trainer = channel.user_id.partner_id
            channel_recs = progress_recs.filtered(lambda r: r.course_id == channel)

            if channel_recs:
                avg = sum(channel_recs.mapped('completion_percentage')) / len(channel_recs)

                if trainer.id not in trainer_map:
                    trainer_map[trainer.id] = {
                        'id': trainer.id,
                        'name': trainer.name,
                        'values': []
                    }

                trainer_map[trainer.id]['values'].append(avg)

        for trainer_data in trainer_map.values():
            avg = sum(trainer_data['values']) / len(trainer_data['values'])
            data.append({
                'id': trainer_data['id'],
                'name': trainer_data['name'],
                'value': round(avg, 2)
            })

        data.sort(key=lambda x: x['value'], reverse=True)
        return data[:limit]

    # ========== ACTIONS ==========
    def action_refresh(self):
        """Rafraîchir le dashboard"""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_export_pdf(self):
        """Exporter en PDF"""
        return self.env.ref(
            'lms_evaluation_results.action_export_results_wizard'
        ).read()[0]