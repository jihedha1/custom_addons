from io import StringIO
from odoo import models, fields, api
import csv
import base64
import logging

_logger = logging.getLogger(__name__)

class ExportProgressWizard(models.TransientModel):
    _name = 'formevo.export.progress.wizard'
    _description = 'Export Progress Wizard'

    course_id = fields.Many2one('slide.channel', string='Course', required=True)
    file_data = fields.Binary('File', readonly=True)
    file_name = fields.Char('File Name', readonly=True)

    def export_progress(self):
        # Créer un fichier CSV en mémoire
        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Écrire l'en-tête du fichier CSV
        writer.writerow(['Partner Name', 'Slide Title', 'Completion Status', 'Completion Date', 'Time Spent'])

        # Récupérer les participants et leurs progrès
        progress_records = self.env['slide.slide.partner'].search([
            ('channel_id', '=', self.course_id.id)
        ])

        # Log pour vérifier le nombre de records
        _logger.info(f"Nombre de records à exporter : {len(progress_records)}")

        for record in progress_records:
            partner_name = record.partner_id.name
            slide_title = record.slide_id.name
            completed = 'Yes' if record.completed else 'No'
            completion_date = record.x_completion_date or 'N/A'
            time_spent = record.x_time_spent or 'N/A'

            # Log des données exportées
            _logger.info(f"Exporting: {partner_name}, {slide_title}, {completed}, {completion_date}, {time_spent}")

            # Écrire les données dans le fichier CSV
            writer.writerow([partner_name, slide_title, completed, completion_date, time_spent])

        # Log du contenu du fichier CSV avant la conversion en base64
        _logger.info(f"CSV content: {output.getvalue()}")

        # Sauvegarder le fichier dans un champ binaire pour le téléchargement
        file_data = base64.b64encode(output.getvalue().encode())
        file_name = f"{self.course_id.name}_progress_report.csv"
        self.write({
            'file_data': file_data,
            'file_name': file_name,
        })

        _logger.info(f"File generated: {self.file_name}")

        # Retourner l'action pour ouvrir le fichier dans une nouvelle fenêtre
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'formevo.export.progress.wizard',
            'view_mode': 'form',
            'view_id': False,
            'target': 'new',
            'res_id': self.id,
            'context': {
                'default_file_data': self.file_data,
                'default_file_name': self.file_name,
            },
        }
