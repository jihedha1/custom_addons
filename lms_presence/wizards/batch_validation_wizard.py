# custom_addons/lms_presence/wizards/batch_validation_wizard.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class BatchValidationWizard(models.TransientModel):
    _name = 'lms_presence.batch_validation_wizard'
    _description = 'Assistant de validation en lot'

    session_id = fields.Many2one(
        'lms_presence.attendance_session',
        string='Session',
        required=True
    )

    # ✅ CORRECTION : Ajouter un nom court pour la table de relation
    line_ids = fields.Many2many(
        'lms_presence.attendance_line',
        'presence_batch_wizard_line_rel',  # Nom court < 63 caractères
        'wizard_id',
        'line_id',
        string='Lignes à valider'
    )

    validation_type = fields.Selection([
        ('present', 'Marquer présent'),
        ('absent', 'Marquer absent'),
        ('validate', 'Valider (enseignant)'),
    ], string='Action', required=True, default='validate')

    def action_validate(self):
        """Exécute la validation en lot"""
        self.ensure_one()

        for line in self.line_ids:
            if self.validation_type == 'present':
                line.action_mark_present()
            elif self.validation_type == 'absent':
                line.action_mark_absent()
            elif self.validation_type == 'validate':
                line.action_validate_teacher()

        return {'type': 'ir.actions.act_window_close'}