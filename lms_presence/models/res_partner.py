# custom_addons/lms_presence/models/res_partner.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ========== PARTICIPANT ==========
    is_training_participant = fields.Boolean(
        string='Participant aux formations',
        default=False,
        help='Cocher si ce contact est un participant aux formations'
    )

    # ========== HANDICAP ==========
    has_disability = fields.Boolean(
        string='Handicap reconnu',
        default=False,
        help='Cocher si le participant a un handicap reconnu'
    )

    disability_type = fields.Selection([
        ('motor', 'Handicap moteur'),
        ('visual', 'Handicap visuel'),
        ('hearing', 'Handicap auditif'),
        ('cognitive', 'Handicap cognitif'),
        ('psychic', 'Handicap psychique'),
        ('other', 'Autre'),
    ], string='Type de handicap')

    disability_description = fields.Text(
        string='Description des aménagements',
        help='Décrivez les aménagements nécessaires pour ce participant'
    )

    # ========== PIÈCES JOINTES HANDICAP ==========
    disability_attachment_ids = fields.Many2many(
        'ir.attachment',
        'partner_disability_attachment_rel',
        'partner_id',
        'attachment_id',
        string='Justificatifs handicap',
        help='Documents justificatifs du handicap (RQTH, certificats médicaux, etc.)'
    )

    # ========== CONTACT URGENCE ==========
    emergency_contact = fields.Char(
        string='Contact d\'urgence',
        help='Nom du contact en cas d\'urgence'
    )

    emergency_phone = fields.Char(
        string='Téléphone d\'urgence',
        help='Numéro de téléphone du contact d\'urgence'
    )

    # ========== STATISTIQUES ==========
    attendance_line_ids = fields.One2many(
        'lms_presence.attendance_line',
        'participant_id',
        string='Historique de présence'
    )

    attendance_count = fields.Integer(
        string='Nombre de participations',
        compute='_compute_attendance_count'
    )

    presence_rate = fields.Float(
        string='Taux de présence (%)',
        compute='_compute_attendance_count',
        digits=(5, 2)
    )

    @api.depends('attendance_line_ids', 'attendance_line_ids.state')
    def _compute_attendance_count(self):
        for partner in self:
            lines = partner.attendance_line_ids
            partner.attendance_count = len(lines)

            if lines:
                present_count = len(lines.filtered(lambda l: l.state in ['present', 'late']))
                partner.presence_rate = (present_count / len(lines)) * 100
            else:
                partner.presence_rate = 0.0

    def action_view_attendances(self):
        """Ouvre la liste des présences du participant"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Historique de présence',
            'res_model': 'lms_presence.attendance_line',
            'view_mode': 'tree,form',
            'domain': [('participant_id', '=', self.id)],
            'context': {'default_participant_id': self.id},
        }