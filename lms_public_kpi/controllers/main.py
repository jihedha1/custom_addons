# custom_addons/lms_public_kpi/controllers/main.py
# -*- coding: utf-8 -*-
"""
Controller pour les indicateurs publics Qualiopi
Version finale corrigée pour Odoo 17
"""
from odoo.http import request
from odoo import http, fields, _
import json
import logging

_logger = logging.getLogger(__name__)


class PublicKPIWebsiteController(http.Controller):
    """Controller pour l'affichage public des KPI Qualiopi"""

    @http.route('/kpis/latest', type='http', auth='public', website=True, sitemap=True)
    def get_latest_kpis(self, **kwargs):
        """
        Affiche le dernier snapshot publié
        Route publique accessible à tous
        """
        snapshot = request.env['public.kpi.snapshot'].sudo().search([
            ('state', '=', 'published')
        ], order='publication_date desc', limit=1)

        if snapshot:
            _logger.info("📊 KPI publics consultés: snapshot #%s (%s)", snapshot.id, snapshot.name)

        return request.render('lms_public_kpi.kpi_public_snapshot_page', {
            'snapshot': snapshot if snapshot else False,
            'main_object': snapshot if snapshot else False,
            'page_name': 'Indicateurs de Performance - Certification Qualiopi',
            'is_latest': True,
        })

    @http.route('/kpis/snapshot/<int:snapshot_id>', type='http', auth='public', website=True)
    def get_kpi_snapshot(self, snapshot_id, **kwargs):
        """
        Affiche un snapshot spécifique par ID
        Accessible seulement si le snapshot est publié
        """
        snapshot = request.env['public.kpi.snapshot'].sudo().browse(snapshot_id)

        if not snapshot.exists():
            _logger.warning("❌ KPI snapshot #%s inexistant", snapshot_id)
            return request.not_found()

        if snapshot.state != 'published':
            _logger.warning("⚠️ Tentative d'accès snapshot non publié #%s", snapshot_id)
            return request.not_found()

        _logger.info("📊 Snapshot #%s consulté: %s", snapshot.id, snapshot.name)

        return request.render('lms_public_kpi.kpi_public_snapshot_page', {
            'snapshot': snapshot,
            'main_object': snapshot,
            'page_name': f'Indicateurs - {snapshot.name}',
            'is_latest': False,
        })

    @http.route('/kpis/snapshot/<int:snapshot_id>/pdf', type='http', auth='public')
    def download_kpi_pdf(self, snapshot_id, **kwargs):
        """
        Téléchargement PDF depuis le site web
        Version corrigée pour Odoo 17
        """
        try:
            # 1. Récupérer le snapshot
            snapshot = request.env['public.kpi.snapshot'].sudo().browse(snapshot_id)

            if not snapshot.exists():
                _logger.error("❌ Snapshot #%s n'existe pas", snapshot_id)
                return request.not_found()

            if snapshot.state != 'published':
                _logger.error("❌ Snapshot #%s non publié (état: %s)", snapshot_id, snapshot.state)
                return request.not_found()

            _logger.info("📊 Génération PDF pour snapshot #%s (%s)", snapshot_id, snapshot.name)

            # 2. ✅ MÉTHODE CORRECTE ODOO 17
            # Utiliser ir.actions.report avec _render_qweb_pdf()
            report_sudo = request.env['ir.actions.report'].sudo()

            # Générer le PDF avec la signature correcte
            pdf_content, content_type = report_sudo._render_qweb_pdf(
                report_ref='lms_public_kpi.report_kpi_snapshot',  # XML ID du rapport
                res_ids=[snapshot_id],
                data=None
            )

            if not pdf_content:
                _logger.error("❌ PDF vide généré")
                return self._render_error_page(
                    "Le rapport PDF est vide. Veuillez vérifier la configuration.",
                    snapshot_id
                )

            # 3. Préparer le fichier
            filename = f'Indicateurs_Qualiopi_{snapshot.name.replace(" ", "_")}.pdf'

            _logger.info("✅ PDF généré avec succès: %d bytes", len(pdf_content))

            # 4. Retourner le PDF
            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="{filename}"')
            ]

            return request.make_response(pdf_content, headers=pdfhttpheaders)

        except Exception as e:
            _logger.error("❌ Erreur génération PDF: %s", str(e), exc_info=True)
            return self._render_error_page(str(e), snapshot_id)

    def _render_error_page(self, error_message, snapshot_id=None):
        """
        Afficher une page d'erreur HTML élégante
        Alternative à website.404 qui peut ne pas être disponible
        """
        # Nettoyer le message d'erreur pour utilisateurs non-admin
        if not request.env.user.has_group('base.group_system'):
            error_message = "Une erreur technique est survenue"

        error_html = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <title>Erreur - Génération PDF</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    padding: 20px;
                }}
                .error-container {{
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 600px;
                    width: 100%;
                    padding: 50px 40px;
                    text-align: center;
                    animation: slideIn 0.5s ease-out;
                }}
                @keyframes slideIn {{
                    from {{
                        opacity: 0;
                        transform: translateY(-30px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
                .error-icon {{
                    font-size: 100px;
                    margin-bottom: 20px;
                    animation: bounce 1s infinite;
                }}
                @keyframes bounce {{
                    0%, 100% {{ transform: translateY(0); }}
                    50% {{ transform: translateY(-10px); }}
                }}
                h1 {{
                    color: #2c3e50;
                    font-size: 32px;
                    margin-bottom: 15px;
                    font-weight: 700;
                }}
                p {{
                    color: #7f8c8d;
                    font-size: 18px;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }}
                .error-details {{
                    background: #fff5f5;
                    border-left: 5px solid #dc3545;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: left;
                    margin-bottom: 30px;
                }}
                .error-details strong {{
                    color: #dc3545;
                    display: block;
                    margin-bottom: 10px;
                    font-size: 14px;
                }}
                .error-details code {{
                    font-family: 'Courier New', monospace;
                    font-size: 13px;
                    color: #721c24;
                    word-break: break-word;
                    display: block;
                    background: white;
                    padding: 10px;
                    border-radius: 5px;
                    margin-top: 5px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 14px 35px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 30px;
                    font-weight: 600;
                    font-size: 16px;
                    transition: all 0.3s ease;
                    margin: 8px;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                }}
                .btn:hover {{
                    transform: translateY(-3px);
                    box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
                }}
                .btn-secondary {{
                    background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
                    box-shadow: 0 4px 15px rgba(108, 117, 125, 0.3);
                }}
                .btn-secondary:hover {{
                    box-shadow: 0 8px 25px rgba(108, 117, 125, 0.5);
                }}
                .footer-note {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #ecf0f1;
                    font-size: 14px;
                    color: #95a5a6;
                }}
                @media (max-width: 600px) {{
                    .error-container {{
                        padding: 30px 20px;
                    }}
                    h1 {{
                        font-size: 24px;
                    }}
                    .error-icon {{
                        font-size: 60px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">📄❌</div>
                <h1>Erreur de génération du PDF</h1>
                <p>Désolé, nous ne pouvons pas générer le rapport PDF pour le moment.</p>

                <div class="error-details">
                    <strong>⚠️ Détails techniques</strong>
                    <code>{error_message}</code>
                </div>

                <div class="actions">
                    {f'<a href="/kpis/snapshot/{snapshot_id}" class="btn">📊 Voir les indicateurs en ligne</a>' if snapshot_id else ''}
                    <a href="/kpis/latest" class="btn btn-secondary">📈 Derniers indicateurs</a>
                    <a href="/" class="btn btn-secondary">🏠 Accueil</a>
                </div>

                <div class="footer-note">
                    <p><strong>💡 Que faire ?</strong></p>
                    <ul style="list-style: none; padding: 0; margin-top: 10px;">
                        <li>✓ Consultez les indicateurs en ligne (sans PDF)</li>
                        <li>✓ Réessayez dans quelques minutes</li>
                        <li>✓ Contactez l'administrateur si le problème persiste</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """

        return request.make_response(
            error_html,
            headers=[
                ('Content-Type', 'text/html; charset=utf-8'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate')
            ]
        )

    @http.route('/kpis/api/latest', type='json', auth='public', csrf=False)
    def get_latest_kpis_api(self, **kwargs):
        """
        API JSON pour récupérer les derniers KPI
        Accessible sans authentification
        """
        try:
            snapshot = request.env['public.kpi.snapshot'].sudo().search([
                ('state', '=', 'published')
            ], order='publication_date desc', limit=1)

            if not snapshot:
                return {
                    'success': False,
                    'error': 'No published snapshot found',
                    'code': 404,
                    'data': None
                }

            # Construire liste KPI
            kpis = []
            for kpi in snapshot.kpi_version_ids.filtered(lambda k: k.state == 'published').sorted('sequence'):
                kpis.append({
                    'id': kpi.id,
                    'name': kpi.name,
                    'value': float(kpi.value) if kpi.value else 0,
                    'unit': kpi.unit or '',
                    'category': {
                        'id': kpi.category_id.id,
                        'name': kpi.category_id.name,
                        'code': kpi.category_id.code,
                    },
                    'description': kpi.description or '',
                    'evolution_rate': round(float(kpi.evolution_rate), 2) if kpi.evolution_rate else 0,
                    'evolution_direction': kpi.evolution_direction or 'stable',
                })

            return {
                'success': True,
                'snapshot': {
                    'id': snapshot.id,
                    'name': snapshot.name,
                    'period_type': snapshot.period_type,
                    'period_start': snapshot.period_start.strftime('%Y-%m-%d') if snapshot.period_start else None,
                    'period_end': snapshot.period_end.strftime('%Y-%m-%d') if snapshot.period_end else None,
                    'publication_date': snapshot.publication_date.strftime(
                        '%Y-%m-%d') if snapshot.publication_date else None,
                },
                'kpis': kpis,
                'count': len(kpis),
                'metadata': {
                    'generated_at': fields.Datetime.now().isoformat(),
                    'source': 'Odoo LMS - Qualiopi',
                }
            }

        except Exception as e:
            _logger.error("❌ Erreur API KPI: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Internal server error',
                'code': 500,
                'message': str(e) if request.env.user.has_group('base.group_system') else 'Une erreur est survenue'
            }

    @http.route('/kpis/widget', type='http', auth='public', website=True, csrf=False)
    def get_kpi_widget(self, limit=6, **kwargs):
        """
        Widget KPI intégrable dans n'importe quelle page
        Usage: <iframe src="/kpis/widget?limit=6"></iframe>
        """
        try:
            limit = int(limit)
            if limit < 1 or limit > 20:
                limit = 6
        except:
            limit = 6

        snapshot = request.env['public.kpi.snapshot'].sudo().search([
            ('state', '=', 'published')
        ], order='publication_date desc', limit=1)

        if not snapshot:
            return request.render('lms_public_kpi.kpi_widget_empty', {
                'message': 'Indicateurs bientôt disponibles'
            })

        kpis = snapshot.kpi_version_ids.filtered(
            lambda k: k.state == 'published'
        ).sorted('sequence')[:limit]

        _logger.info("📊 Widget KPI affiché: %d indicateurs", len(kpis))

        return request.render('lms_public_kpi.kpi_widget_template', {
            'snapshot': snapshot,
            'kpis': kpis,
            'limit': limit,
        })

    @http.route('/kpis/health', type='json', auth='public', csrf=False)
    def health_check(self, **kwargs):
        """
        Endpoint de santé pour monitoring
        Retourne l'état du service KPI
        """
        try:
            total = request.env['public.kpi.snapshot'].sudo().search_count([])
            published = request.env['public.kpi.snapshot'].sudo().search_count([
                ('state', '=', 'published')
            ])

            return {
                'status': 'healthy',
                'service': 'lms_public_kpi',
                'version': '17.0.1.0.0',
                'data': {
                    'snapshots_total': total,
                    'snapshots_published': published,
                },
                'timestamp': fields.Datetime.now().isoformat(),
            }
        except Exception as e:
            _logger.error("Health check failed: %s", str(e))
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': fields.Datetime.now().isoformat(),
            }