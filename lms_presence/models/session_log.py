# models/session_log.py
from odoo import models, fields, api

class FormationSessionLog(models.Model):
    _name = 'lms_presence.session_log'
    _description = 'Journal des sessions de formation'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # <-- AJOUTEZ CETTE LIGNE

    session_id = fields.Many2one(
        'lms_presence.attendance_session',
        string='Session',
        required=True,
        ondelete='cascade',
        index=True
    )

    action_type = fields.Selection([
        ('create', 'Création'),
        ('write', 'Modification'),
        ('state_change', 'Changement de statut'),
        ('regenerate', 'Regénération'),
        ('notification', 'Notification'),
        ('absence_detection', 'Détection absence'),
        ('trainer_change', 'Changement formateur'),
        ('location_change', 'Changement lieu'),
        ('schedule_change', 'Modification planning'),
    ], string='Type d\'action', required=True, tracking=True)  # <-- tracking=True pour suivre les changements

    description = fields.Text(string='Description', tracking=True)

    user_id = fields.Many2one(
        'res.users',
        string='Utilisateur',
        default=lambda self: self.env.user,
        required=True
    )

    create_date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True
    )

    participant_id = fields.Many2one('res.partner', string='Participant concerné')
    email_message_id = fields.Char(string='ID Message email', help='Identifiant du message envoyé')

    log_category = fields.Selection([
        ('session', 'Session'),
        ('attendance', 'Présence'),
        ('notification', 'Notification'),
        ('inactivity', 'Inactivité'),
        ('system', 'Système'),
    ], string='Catégorie', default='session')