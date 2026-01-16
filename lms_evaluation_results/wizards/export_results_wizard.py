# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import io
import xlsxwriter


class ExportResultsWizard(models.TransientModel):
    _name = 'lms_evaluation_results.export_results_wizard'
    _description = 'Assistant export résultats'

    export_format = fields.Selection([
        ('xlsx', 'Excel (XLSX)'),
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
    ], string='Format', default='xlsx', required=True)

    include_details = fields.Boolean(
        string='Inclure les détails',
        default=True,
        help="Inclure les données détaillées par formation"
    )

    period_start = fields.Date(
        string='Début période',
        required=True
    )

    period_end = fields.Date(
        string='Fin période',
        required=True
    )

    channel_ids = fields.Many2many(
        'slide.channel',
        string='Formations'
    )

    file_data = fields.Binary(
        string='Fichier généré',
        readonly=True
    )

    filename = fields.Char(
        string='Nom du fichier',
        compute='_compute_filename'
    )

    @api.depends('export_format')
    def _compute_filename(self):
        for wizard in self:
            wizard.filename = f'resultats_qualiopi_{fields.Date.today()}.{wizard.export_format}'

    def action_export(self):
        """Exporter les résultats"""
        self.ensure_one()

        if self.export_format == 'xlsx':
            file_data = self._export_to_xlsx()
        elif self.export_format == 'pdf':
            file_data = self._export_to_pdf()
        else:
            file_data = self._export_to_csv()

        # Mettre à jour le wizard avec le fichier généré
        self.write({
            'file_data': base64.b64encode(file_data)
        })

        # Retourner l'action de téléchargement
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/lms_evaluation_results.export_results_wizard/{self.id}/file_data/{self.filename}?download=true',
            'target': 'self',
        }

    def _export_to_xlsx(self):
        """Exporter vers Excel"""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)

        # Feuille de synthèse
        self._write_summary_sheet(workbook)

        # Feuille de détails
        if self.include_details:
            self._write_details_sheet(workbook)

        workbook.close()
        return output.getvalue()

    def _write_summary_sheet(self, workbook):
        """Écrire la feuille de synthèse"""
        worksheet = workbook.add_worksheet('Synthese')

        # Formatage
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#007bff',
            'font_color': 'white',
            'border': 1
        })

        data_format = workbook.add_format({
            'border': 1
        })

        # En-têtes
        headers = ['Indicateur', 'Valeur', 'Cible', 'Ecart', 'Statut']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Récupérer les données
        dashboard_data = self._get_dashboard_data()

        # Données
        data = [
            ['Taux de completion', f"{dashboard_data.get('completion_rate', 0):.1f}%", '>= 80%',
             self._calculate_gap(dashboard_data.get('completion_rate', 0), 80),
             self._get_status(dashboard_data.get('completion_rate', 0), 80)],
            ['Taux de reussite', f"{dashboard_data.get('success_rate', 0):.1f}%", '>= 75%',
             self._calculate_gap(dashboard_data.get('success_rate', 0), 75),
             self._get_status(dashboard_data.get('success_rate', 0), 75)],
            ['Taux de satisfaction', f"{dashboard_data.get('satisfaction_rate', 0):.1f}%", '>= 85%',
             self._calculate_gap(dashboard_data.get('satisfaction_rate', 0), 85),
             self._get_status(dashboard_data.get('satisfaction_rate', 0), 85)],
            ['Taux abandon', f"{dashboard_data.get('dropout_rate', 0):.1f}%", '<= 10%',
             self._calculate_gap(dashboard_data.get('dropout_rate', 0), 10, inverse=True),
             self._get_status(dashboard_data.get('dropout_rate', 0), 10, inverse=True)],
            ['Taux reponse eval. a chaud', f"{dashboard_data.get('hot_assessment_rate', 0):.1f}%", '>= 70%',
             self._calculate_gap(dashboard_data.get('hot_assessment_rate', 0), 70),
             self._get_status(dashboard_data.get('hot_assessment_rate', 0), 70)],
            ['Taux reponse eval. a froid', f"{dashboard_data.get('cold_assessment_rate', 0):.1f}%", '>= 50%',
             self._calculate_gap(dashboard_data.get('cold_assessment_rate', 0), 50),
             self._get_status(dashboard_data.get('cold_assessment_rate', 0), 50)],
        ]

        for row, row_data in enumerate(data, start=1):
            for col, cell_data in enumerate(row_data):
                worksheet.write(row, col, cell_data, data_format)

        # Ajuster la largeur des colonnes
        worksheet.set_column(0, 0, 30)
        worksheet.set_column(1, 4, 15)

    def _write_details_sheet(self, workbook):
        """Écrire la feuille de détails"""
        worksheet = workbook.add_worksheet('Details par formation')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#28a745',
            'font_color': 'white',
            'border': 1
        })

        # En-têtes
        headers = ['Formation', 'Participants', 'Completion %', 'Reussite %', 'Satisfaction %',
                   'Abandon %', 'Eval. chaude %', 'Eval. froide %']

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Récupérer les données par formation
        formations_data = self._get_formations_data()

        data_format = workbook.add_format({'border': 1})

        for row, formation in enumerate(formations_data, start=1):
            worksheet.write(row, 0, formation['name'], data_format)
            worksheet.write(row, 1, formation['participants'], data_format)
            worksheet.write(row, 2, f"{formation['completion']:.1f}%", data_format)
            worksheet.write(row, 3, f"{formation['success']:.1f}%", data_format)
            worksheet.write(row, 4, f"{formation['satisfaction']:.1f}%", data_format)
            worksheet.write(row, 5, f"{formation['dropout']:.1f}%", data_format)
            worksheet.write(row, 6, f"{formation['hot_eval']:.1f}%", data_format)
            worksheet.write(row, 7, f"{formation['cold_eval']:.1f}%", data_format)

        # Ajuster la largeur des colonnes
        for col in range(len(headers)):
            worksheet.set_column(col, col, 20)

    def _export_to_pdf(self):
        """Exporter vers PDF"""
        # Pour le moment, retourner un placeholder
        # TODO: Implémenter avec reportlab ou wkhtmltopdf
        return "PDF export a implementer".encode('utf-8')

    def _export_to_csv(self):
        """Exporter vers CSV"""
        import csv

        output = io.StringIO()
        writer = csv.writer(output)

        # En-têtes
        writer.writerow(['Indicateur', 'Valeur', 'Cible', 'Ecart', 'Statut'])

        # Données de synthèse
        dashboard_data = self._get_dashboard_data()

        data = [
            ['Taux de completion', f"{dashboard_data.get('completion_rate', 0):.1f}%", '>= 80%',
             self._calculate_gap(dashboard_data.get('completion_rate', 0), 80),
             self._get_status(dashboard_data.get('completion_rate', 0), 80)],
            ['Taux de reussite', f"{dashboard_data.get('success_rate', 0):.1f}%", '>= 75%',
             self._calculate_gap(dashboard_data.get('success_rate', 0), 75),
             self._get_status(dashboard_data.get('success_rate', 0), 75)],
            ['Taux de satisfaction', f"{dashboard_data.get('satisfaction_rate', 0):.1f}%", '>= 85%',
             self._calculate_gap(dashboard_data.get('satisfaction_rate', 0), 85),
             self._get_status(dashboard_data.get('satisfaction_rate', 0), 85)],
        ]

        for row in data:
            writer.writerow(row)

        return output.getvalue().encode('utf-8')

    def _get_dashboard_data(self):
        """Récupérer les données du dashboard"""
        domain = self._build_domain()

        # Utiliser le dashboard pour calculer les indicateurs
        dashboard = self.env['lms_evaluation_results.results_dashboard'].create({
            'period': 'custom',
            'date_start': self.period_start,
            'date_end': self.period_end,
            'channel_ids': [(6, 0, self.channel_ids.ids)] if self.channel_ids else False,
        })

        return {
            'completion_rate': dashboard.completion_rate,
            'success_rate': dashboard.success_rate,
            'satisfaction_rate': dashboard.satisfaction_rate,
            'dropout_rate': dashboard.dropout_rate,
            'hot_assessment_rate': dashboard.hot_assessment_rate,
            'cold_assessment_rate': dashboard.cold_assessment_rate,
        }

    def _get_formations_data(self):
        """Récupérer les données détaillées par formation"""
        domain = self._build_domain()

        formations_data = []

        if 'yonn.course.progress' in self.env:
            progress_recs = self.env['yonn.course.progress'].search(domain)
            channels = set(progress_recs.mapped('course_id'))

            for channel in channels:
                channel_recs = progress_recs.filtered(lambda r: r.course_id == channel)

                if channel_recs:
                    # Calculs
                    total = len(channel_recs)
                    completed = len(channel_recs.filtered(lambda r: r.completion_percentage >= 100))
                    success = len(channel_recs.filtered(lambda r: r.completion_percentage >= 50))
                    dropout = len(channel_recs.filtered(lambda r: r.completion_percentage < 20))

                    # Évaluations
                    cold_assessments = self.env['lms_evaluation_results.cold_assessment'].search([
                        ('channel_id', '=', channel.id),
                        ('state', '=', 'completed'),
                    ])

                    avg_satisfaction = sum(cold_assessments.mapped('satisfaction_rate')) / len(
                        cold_assessments) if cold_assessments else 0

                    formations_data.append({
                        'name': channel.name,
                        'participants': total,
                        'completion': (completed / total) * 100 if total else 0,
                        'success': (success / total) * 100 if total else 0,
                        'satisfaction': avg_satisfaction,
                        'dropout': (dropout / total) * 100 if total else 0,
                        'hot_eval': 0,  # TODO: quand implémenté
                        'cold_eval': (len(cold_assessments) / total) * 100 if total else 0,
                    })

        return formations_data

    def _build_domain(self):
        """Construire le domaine pour filtrer les données"""
        domain = []

        if self.period_start:
            domain.append(('create_date', '>=', self.period_start))

        if self.period_end:
            domain.append(('create_date', '<=', self.period_end))

        if self.channel_ids:
            domain.append(('course_id', 'in', self.channel_ids.ids))

        return domain

    def _calculate_gap(self, value, target, inverse=False):
        """Calculer l'écart par rapport à la cible"""
        if inverse:
            # Pour les indicateurs où moins c'est mieux (ex: abandon)
            gap = target - value
            if gap >= 0:
                return f"+{gap:.1f}%"
            else:
                return f"{gap:.1f}%"
        else:
            # Pour les indicateurs où plus c'est mieux
            gap = value - target
            if gap >= 0:
                return f"+{gap:.1f}%"
            else:
                return f"{gap:.1f}%"

    def _get_status(self, value, target, inverse=False):
        """Obtenir le statut (OK/Alerte/Critique)"""
        if inverse:
            # Pour les indicateurs où moins c'est mieux
            if value <= target:
                return "OK"
            elif value <= target * 1.5:
                return "Alerte"
            else:
                return "Critique"
        else:
            # Pour les indicateurs où plus c'est mieux
            if value >= target:
                return "OK"
            elif value >= target * 0.8:
                return "Alerte"
            else:
                return "Critique"