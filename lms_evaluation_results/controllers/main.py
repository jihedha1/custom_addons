# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition
from datetime import datetime, timedelta
import json


class EvaluationResultsWebsiteController(http.Controller):

    @http.route('/lms/results/export', type='http', auth='user')
    def export_results(self, **kwargs):
        """Exporter les résultats"""
        wizard = request.env['lms_evaluation_results.export_results_wizard'].create({
            'export_format': kwargs.get('format', 'xlsx'),
            'period_start': kwargs.get('start_date'),
            'period_end': kwargs.get('end_date'),
            'channel_ids': [(6, 0, [int(cid) for cid in kwargs.get('channel_ids', '').split(',') if cid])],
        })

        wizard.action_export()

        return request.make_response(
            wizard.file_data,
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', content_disposition(wizard.filename))
            ]
        )

    @http.route('/lms/results/dashboard', type='http', auth='user', website=True)
    def results_dashboard(self, **kwargs):
        """Tableau de bord des résultats pour les managers"""
        # Vérifier les permissions
        if not request.env.user.has_group('lms_evaluation_results.group_evaluation_manager'):
            return request.redirect('/web/login')

        return request.render('lms_evaluation_results.results_dashboard_page', {
            'user': request.env.user,
        })

    @http.route('/formations/resultats', type='http', auth='public', website=True)
    def public_results(self, **kwargs):
        """
        Page publique des résultats Qualiopi
        Accessible à tous pour transparence
        """
        # Période par défaut : 12 derniers mois
        date_end = datetime.now().date()
        date_start = date_end - timedelta(days=365)

        # Créer dashboard temporaire pour calculs
        dashboard = request.env['lms_evaluation_results.results_dashboard'].sudo().create({
            'period': 'year',
            'date_start': date_start,
            'date_end': date_end,
        })

        # Récupérer les témoignages récents
        testimonials = []
        cold_assessments = request.env['lms_evaluation_results.cold_assessment'].sudo().search([
            ('state', '=', 'completed'),
            ('feedback', '!=', False),
            ('satisfaction_rate', '>=', 80),
        ], limit=5, order='response_date desc')

        for assessment in cold_assessments:
            if assessment.feedback:
                testimonials.append({
                    'feedback': assessment.feedback,
                    'partner_name': assessment.partner_id.name,
                    'formation_name': assessment.channel_id.name,
                    'score': assessment.satisfaction_rate,
                })

        # Calculer taux réponse J+30 et J+90
        cold_30 = request.env['lms_evaluation_results.cold_assessment'].sudo().search_count([
            ('assessment_type', '=', '30_days'),
            ('state', '=', 'completed'),
            ('create_date', '>=', date_start),
        ])
        cold_30_total = request.env['lms_evaluation_results.cold_assessment'].sudo().search_count([
            ('assessment_type', '=', '30_days'),
            ('state', 'in', ['sent', 'completed', 'expired']),
            ('create_date', '>=', date_start),
        ])

        cold_90 = request.env['lms_evaluation_results.cold_assessment'].sudo().search_count([
            ('assessment_type', '=', '90_days'),
            ('state', '=', 'completed'),
            ('create_date', '>=', date_start),
        ])
        cold_90_total = request.env['lms_evaluation_results.cold_assessment'].sudo().search_count([
            ('assessment_type', '=', '90_days'),
            ('state', 'in', ['sent', 'completed', 'expired']),
            ('create_date', '>=', date_start),
        ])

        return request.render('lms_evaluation_results.evaluation_results_public_page', {
            # Indicateurs
            'completion_rate': dashboard.completion_rate,
            'satisfaction_rate': dashboard.satisfaction_rate,
            'success_rate': dashboard.success_rate,
            'dropout_rate': dashboard.dropout_rate,
            'total_participants': dashboard.total_participants,
            'total_completions': dashboard.total_completions,

            # Évaluations à froid
            'cold_30_response_rate': (cold_30 / cold_30_total * 100) if cold_30_total else 0,
            'cold_90_response_rate': (cold_90 / cold_90_total * 100) if cold_90_total else 0,
            'professional_impact_rate': dashboard.professional_impact_rate,

            # Métadonnées
            'period_label': '12 derniers mois',
            'last_update_date': datetime.now().strftime('%d/%m/%Y'),

            # Témoignages
            'testimonials': testimonials,
        })

    @http.route('/lms/results/api/summary', type='json', auth='user')
    def get_results_summary(self, **kwargs):
        """API pour récupérer les résultats résumés"""
        period = kwargs.get('period', 'month')
        channel_id = kwargs.get('channel_id')
        trainer_id = kwargs.get('trainer_id')

        # Créer dashboard
        dashboard = request.env['lms_evaluation_results.results_dashboard'].create({
            'period': period,
        })

        return {
            'success': True,
            'data': {
                'completion_rate': dashboard.completion_rate,
                'satisfaction_rate': dashboard.satisfaction_rate,
                'success_rate': dashboard.success_rate,
                'dropout_rate': dashboard.dropout_rate,
            },
        }