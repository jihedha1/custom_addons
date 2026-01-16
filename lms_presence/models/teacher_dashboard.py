# custom_addons/lms_presence/models/teacher_dashboard.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api


class TeacherDashboard(models.TransientModel):
    _name = 'lms_presence.teacher_dashboard'
    _description = 'Tableau de bord enseignant'

    teacher_id = fields.Many2one(
        'res.users',
        string='Enseignant',
        default=lambda self: self.env.user
    )

    today_sessions_count = fields.Integer(
        string='Sessions aujourd\'hui',
        compute='_compute_dashboard'
    )

    pending_validations_count = fields.Integer(
        string='Validations en attente',
        compute='_compute_dashboard'
    )

    @api.depends('teacher_id')
    def _compute_dashboard(self):
        for record in self:
            today = fields.Date.today()

            # Sessions du jour
            sessions = self.env['lms_presence.attendance_session'].search([
                ('teacher_id', '=', record.teacher_id.id),
                ('date_start', '>=', today),
                ('date_start', '<', fields.Datetime.to_string(
                    fields.Datetime.from_string(str(today)) +
                    __import__('datetime').timedelta(days=1)
                )),
            ])
            record.today_sessions_count = len(sessions)

            # Validations en attente
            pending = self.env['lms_presence.attendance_line'].search([
                ('teacher_id', '=', record.teacher_id.id),
                ('validated_by_participant', '=', True),
                ('validated_by_teacher', '=', False),
            ])
            record.pending_validations_count = len(pending)