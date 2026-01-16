# custom_addons/lms_presence/models/attendance_line.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class FormationAttendanceLine(models.Model):
    _name = 'lms_presence.attendance_line'
    _description = 'Ligne de présence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_date_start desc, participant_name asc'

    # ========== RELATIONS ==========
    session_id = fields.Many2one(
        'lms_presence.attendance_session',
        string='Session',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    participant_id = fields.Many2one(
        'res.partner',
        string='Participant',
        required=True,
        domain="[('is_training_participant', '=', True)]",
        index=True
    )

    training_type = fields.Selection(
        related='session_id.training_type',
        store=True,
        readonly=True
    )
    # ========== INFORMATIONS SESSION ==========
    session_name = fields.Char(
        string='Nom session',
        related='session_id.name',
        store=True,
        readonly=True
    )

    session_date_start = fields.Datetime(
        string='Début session',
        related='session_id.date_start',
        store=True,
        readonly=True
    )

    session_date_end = fields.Datetime(
        string='Fin session',
        related='session_id.date_end',
        store=True,
        readonly=True
    )

    session_location = fields.Char(
        string='Lieu',
        related='session_id.location',
        store=True,
        readonly=True
    )

    session_state = fields.Selection(
        related='session_id.state',
        string='Statut de la session',
        store=True,
        readonly=True
    )

    teacher_id = fields.Many2one(
        'res.users',
        string='Enseignant',
        related='session_id.teacher_id',
        store=True,
        readonly=True
    )

    # ========== INFORMATIONS PARTICIPANT ==========
    participant_name = fields.Char(
        string='Nom participant',
        related='participant_id.name',
        store=True,
        readonly=True
    )

    participant_email = fields.Char(
        string='Email',
        related='participant_id.email',
        store=True,
        readonly=True
    )

    participant_phone = fields.Char(
        string='Téléphone',
        related='participant_id.phone',
        store=True,
        readonly=True
    )

    has_disability = fields.Boolean(
        string='Handicap',
        related='participant_id.has_disability',
        store=True,
        readonly=True
    )

    disability_type = fields.Selection(
        string='Type handicap',
        related='participant_id.disability_type',
        store=True,
        readonly=True
    )

    disability_description = fields.Text(
        string='Aménagements nécessaires',
        related='participant_id.disability_description',
        store=True,
        readonly=True
    )

    emergency_contact = fields.Char(
        string='Contact urgence',
        related='participant_id.emergency_contact',
        store=True,
        readonly=True
    )

    emergency_phone = fields.Char(
        string='Téléphone urgence',
        related='participant_id.emergency_phone',
        store=True,
        readonly=True
    )

    # ========== PRÉSENCE ==========
    check_in = fields.Datetime(
        string='Heure d\'arrivée',
        tracking=True
    )

    check_out = fields.Datetime(
        string='Heure de départ',
        tracking=True
    )

    worked_hours = fields.Float(
        string='Heures présentes',
        compute='_compute_worked_hours',
        store=True,
        digits=(5, 2)
    )

    state = fields.Selection([
        ('draft', 'Non défini'),
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('late', 'En retard'),
        ('excused', 'Absence justifiée'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft', tracking=True)

    # ========== VALIDATIONS ==========
    validated_by_participant = fields.Boolean(
        string='Validé par participant',
        default=False,
        tracking=True
    )

    validated_by_teacher = fields.Boolean(
        string='Validé par enseignant',
        default=False,
        tracking=True
    )

    validation_date_participant = fields.Datetime(
        string='Date validation participant'
    )

    validation_date_teacher = fields.Datetime(
        string='Date validation enseignant'
    )

    # ========== RETARDS ==========
    is_late = fields.Boolean(
        string='En retard',
        compute='_compute_lateness',
        store=True
    )

    late_minutes = fields.Integer(
        string='Minutes de retard',
        compute='_compute_lateness',
        store=True
    )

    late_reason = fields.Char(
        string='Motif du retard'
    )

    # ========== ABSENCES ==========
    absence_reason = fields.Selection([
        ('illness', 'Maladie'),
        ('professional', 'Raison professionnelle'),
        ('personal', 'Raison personnelle'),
        ('transport', 'Problème transport'),
        ('other', 'Autre'),
    ], string='Motif absence')

    absence_justification = fields.Text(
        string='Justification'
    )

    absence_justification_file = fields.Binary(
        string='Justificatif'
    )

    absence_justification_filename = fields.Char(
        string='Nom fichier justificatif'
    )

    # ========== NOTES ==========
    notes = fields.Text(string='Notes')

    teacher_notes = fields.Text(
        string='Notes enseignant',
        help='Notes internes pour l\'enseignant'
    )

    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        related='session_id.channel_id',
        store=True,
        readonly=True
    )

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for line in self:
            if line.check_in and line.check_out:
                delta = line.check_out - line.check_in
                line.worked_hours = delta.total_seconds() / 3600
            else:
                line.worked_hours = 0.0

    @api.depends('check_in', 'session_date_start')
    def _compute_lateness(self):
        for line in self:
            if line.check_in and line.session_date_start:
                if line.check_in > line.session_date_start:
                    delta = line.check_in - line.session_date_start
                    line.is_late = True
                    line.late_minutes = int(delta.total_seconds() / 60)
                else:
                    line.is_late = False
                    line.late_minutes = 0
            else:
                line.is_late = False
                line.late_minutes = 0

    # ========== CONTRAINTES ==========
    @api.constrains('check_in', 'check_out')
    def _check_times(self):
        for line in self:
            if line.check_out and line.check_in and line.check_out <= line.check_in:
                raise ValidationError(_("L'heure de départ doit être postérieure à l'heure d'arrivée"))

    # ========== ACTIONS ==========
    def action_validate_teacher(self):
        """Validation par l'enseignant"""
        for line in self:
            line.validated_by_teacher = True
            line.validation_date_teacher = fields.Datetime.now()

            # Confirmer la présence si pas encore fait
            if line.state == 'draft' and line.validated_by_participant:
                line.state = 'present'

    def action_mark_absent(self):
        """Marquer comme absent"""
        self.write({
            'state': 'absent',
            'check_in': False,
            'check_out': False,
            'validated_by_participant': False,
            'validated_by_teacher': True,
            'validation_date_teacher': fields.Datetime.now(),
        })

    def action_mark_present(self):
        """Marquer comme présent"""
        self.write({
            'state': 'present',
            'validated_by_teacher': True,
            'validation_date_teacher': fields.Datetime.now(),
        })

    def action_mark_late(self):
        """Marquer comme retardataire"""
        if not self.check_in:
            self.check_in = fields.Datetime.now()
        self.state = 'late'

    def _create_teacher_activity(self):
        """Crée une activité pour l'enseignant"""
        self.ensure_one()

        # Créer l'activité
        self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': _('Validation de présence requise'),
            'note': _('Le participant %s a validé sa présence pour la session "%s" et attend votre validation.') %
                    (self.participant_name, self.session_name),
            'user_id': self.teacher_id.id,
            'res_id': self.id,
            'res_model_id': self.env['ir.model']._get_id('lms_presence.attendance_line'),
            'date_deadline': fields.Date.today(),
        })

    # ========== NOTIFICATIONS ==========
    def _notify_handicap_to_teacher(self):
        """Notifie l'enseignant si le participant a un handicap"""
        self.ensure_one()

        if self.has_disability and self.session_state == 'confirmed':
            template = self.env.ref('lms_presence.mail_template_handicap_notification')
            if template:
                template.send_mail(self.id, force_send=False)

    @api.model
    def create(self, vals):
        """Surcharge de création pour notifications"""
        line = super(FormationAttendanceLine, self).create(vals)

        # Notifier l'enseignant si handicap
        if line.has_disability:
            line._notify_handicap_to_teacher()

        return line

    def action_validate_participant(self):
        """Validation par le participant - US-C2: Validation présence en ligne"""
        for line in self:
            # Pour les formations en ligne/hybrides, une simple validation suffit
            if line.training_type in ['online', 'hybrid']:
                line.validated_by_participant = True
                line.validation_date_participant = fields.Datetime.now()

                # Si la session est en cours ou confirmée, marquer comme présent
                if line.session_state in ['in_progress', 'confirmed']:
                    line.state = 'present'
                    line.check_in = fields.Datetime.now()

                    # Créer une activité pour validation enseignant
                    line._create_teacher_activity()

            # Pour le présentiel, on enregistre l'heure d'arrivée
            elif line.training_type == 'in_person':
                if not line.check_in:
                    line.check_in = fields.Datetime.now()
                line.validated_by_participant = True
                line.validation_date_participant = fields.Datetime.now()

                # Si la session est en cours, marquer comme présent
                if line.session_state == 'in_progress':
                    line.state = 'present'

                    # Créer une activité pour validation enseignant
                    line._create_teacher_activity()

            # Log pour traçabilité Qualiopi
            line._log_presence_validation()

    @api.model_create_multi
    def create(self, vals_list):
        """Création en batch avec notifications"""
        # Création des lignes
        lines = super(FormationAttendanceLine, self).create(vals_list)

        # Post-traitement en batch
        lines_with_disability = lines.filtered(lambda l: l.has_disability)
        if lines_with_disability:
            # Notifications en batch si possible
            for line in lines_with_disability:
                line._notify_handicap_to_teacher()

        return lines