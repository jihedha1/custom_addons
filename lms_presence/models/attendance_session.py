# custom_addons/lms_presence/models/attendance_session.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class FormationAttendanceSession(models.Model):
    _name = 'lms_presence.attendance_session'
    _description = 'Session de formation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    # ========== CHAMP OBLIGATOIRE ==========
    name = fields.Char(
        string='Nom de la session',
        required=True,
        tracking=True
    )

    # ========== FORMATION (AVEC SLIDE.CHANNEL) ==========
    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True,
        domain="[('is_published', '=', True)]",
        tracking=True
    )

    # Champs related depuis slide.channel
    channel_name = fields.Char(
        string='Nom de la formation',
        related='channel_id.name',
        store=False,
        readonly=True
    )

    # ⚠️ CORRECTION: Utiliser Html au lieu de Text pour correspondre à slide.channel.description
    channel_description = fields.Html(
        string='Description de la formation',
        related='channel_id.description',
        store=False,
        readonly=True
    )

    # ========== PLANNING ==========
    date_start = fields.Datetime(
        string='Date et heure de début',
        required=True,
        default=lambda self: fields.Datetime.now(),
        tracking=True
    )

    date_end = fields.Datetime(
        string='Date et heure de fin',
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(hours=2),
        tracking=True
    )

    duration_hours = fields.Float(
        string='Durée (heures)',
        compute='_compute_duration',
        store=True
    )

    location = fields.Char(
        string='Lieu',
        help='Salle, adresse ou lien visioconférence',
        tracking=True
    )

    # ========== TYPE DE FORMATION ==========
    training_type = fields.Selection([
        ('in_person', 'Présentiel'),
        ('online', 'En ligne'),
        ('hybrid', 'Hybride'),
    ], string='Type de formation',
        default='in_person',
        required=True,
        tracking=True,
        help="Type de formation pour adapter le suivi de présence"
    )

    # ========== RESPONSABLES ==========
    teacher_id = fields.Many2one(
        'res.users',
        string='Enseignant principal',
        required=True,
        domain="[('share', '=', False)]",
        tracking=True
    )

    assistant_ids = fields.Many2many(
        'res.users',
        'session_assistant_rel',
        string='Assistants'
    )

    # ========== PARTICIPANTS ==========
    attendee_ids = fields.Many2many(
        'res.partner',
        'session_attendee_rel',
        string='Participants inscrits',
        domain="[('is_training_participant', '=', True)]"
    )

    # ========== LIGNES DE PRÉSENCE ==========
    attendance_line_ids = fields.One2many(
        'lms_presence.attendance_line',
        'session_id',
        string='Feuille de présence'
    )

    # ========== STATUT ==========
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft', tracking=True)

    # ========== CONTRÔLES ==========
    auto_generate_attendance = fields.Boolean(
        string='Générer automatiquement la feuille de présence',
        default=True,
        help='Crée automatiquement les lignes de présence pour les participants inscrits'
    )

    # ========== COMPTEURS ==========
    total_attendees = fields.Integer(
        string='Total participants',
        compute='_compute_counts',
        store=True
    )

    present_count = fields.Integer(
        string='Présents',
        compute='_compute_counts',
        store=True
    )

    absent_count = fields.Integer(
        string='Absents',
        compute='_compute_counts',
        store=True
    )

    late_count = fields.Integer(
        string='Retards',
        compute='_compute_counts',
        store=True
    )

    attendance_rate = fields.Float(
        string='Taux de présence (%)',
        compute='_compute_counts',
        store=True,
        digits=(5, 2)
    )

    # ========== NOTES ==========
    notes = fields.Text(string='Notes')

    # ========== PIÈCES JOINTES ==========
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Documents associés'
    )

    # ========== MÉTHODES COMPUTE ==========
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for session in self:
            if session.date_start and session.date_end:
                delta = session.date_end - session.date_start
                session.duration_hours = delta.total_seconds() / 3600
            else:
                session.duration_hours = 0.0

    @api.depends('attendance_line_ids', 'attendance_line_ids.state')
    def _compute_counts(self):
        for session in self:
            lines = session.attendance_line_ids
            session.total_attendees = len(lines)
            session.present_count = len(lines.filtered(lambda l: l.state == 'present'))
            session.absent_count = len(lines.filtered(lambda l: l.state == 'absent'))
            session.late_count = len(lines.filtered(lambda l: l.state == 'late'))

            if session.total_attendees > 0:
                session.attendance_rate = (session.present_count / session.total_attendees) * 100
            else:
                session.attendance_rate = 0.0

    # ========== CONTRAINTES ==========
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for session in self:
            if session.date_end <= session.date_start:
                raise ValidationError(_("La date de fin doit être postérieure à la date de début"))

    # ========== MÉTHODES CRUD ==========
    @api.model
    def create(self, vals):
        """Surcharge de création pour générer automatiquement les lignes de présence"""
        session = super(FormationAttendanceSession, self).create(vals)

        if session.auto_generate_attendance and session.attendee_ids:
            session._generate_attendance_lines()

        # Log Qualiopi
        session._log_action('create', _('Session créée'))

        return session

    def write(self, vals):
        """Surcharge d'écriture pour logging Qualiopi"""
        # ✅ AMÉLIORATION: Capturer changements critiques pour traçabilité
        old_values = {}
        for session in self:
            old_values[session.id] = {
                'teacher': session.teacher_id.name if 'teacher_id' in vals else None,
                'location': session.location if 'location' in vals else None,
            }

        result = super(FormationAttendanceSession, self).write(vals)

        # Log Qualiopi pour modifications importantes
        for session in self:
            if 'teacher_id' in vals and old_values[session.id]['teacher']:
                session._log_action(
                    'trainer_change',
                    _('Formateur changé: %s → %s') % (
                        old_values[session.id]['teacher'],
                        session.teacher_id.name
                    )
                )

            if 'location' in vals and old_values[session.id]['location']:
                session._log_action(
                    'location_change',
                    _('Lieu modifié: %s → %s') % (
                        old_values[session.id]['location'],
                        vals['location']
                    )
                )

            if 'date_start' in vals or 'date_end' in vals:
                session._log_action(
                    'schedule_change',
                    _('Planning modifié')
                )

        return result

    # ========== MÉTHODES MÉTIER ==========
    def _generate_attendance_lines(self):
        """Génère les lignes de présence pour les participants inscrits"""
        AttendanceLine = self.env['lms_presence.attendance_line']

        for session in self:
            # Supprimer les anciennes lignes
            session.attendance_line_ids.unlink()

            # Créer les nouvelles lignes
            for attendee in session.attendee_ids:
                AttendanceLine.create({
                    'session_id': session.id,
                    'participant_id': attendee.id,
                })

    def _log_action(self, action_type, description):
        """Journalisation des actions pour traçabilité Qualiopi"""
        self.ensure_one()
        self.env['lms_presence.session_log'].create({
            'session_id': self.id,
            'action_type': action_type,
            'description': description,
            'user_id': self.env.user.id,
        })

    # ========== ACTIONS ==========
    def action_confirm(self):
        self.write({'state': 'confirmed'})
        self._log_action('state_change', _('Session confirmée'))

    def action_start(self):
        self.write({'state': 'in_progress'})
        self._log_action('state_change', _('Session démarrée'))

    def action_finish(self):
        self.write({'state': 'done'})
        self._log_action('state_change', _('Session terminée'))

        # Notifier les participants absents
        self._notify_absent_participants()

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self._log_action('state_change', _('Session annulée'))

    def action_regenerate_attendance(self):
        """Regénère la feuille de présence"""
        self._generate_attendance_lines()
        self._log_action('regenerate', _('Feuille de présence régénérée'))

    def _notify_absent_participants(self):
        """Notifie les participants absents"""
        template = self.env.ref('lms_presence.mail_template_absent_notification', raise_if_not_found=False)
        if template:
            for line in self.attendance_line_ids.filtered(lambda l: l.state == 'absent'):
                template.send_mail(line.id, force_send=False)

    # ========== MÉTHODES CRON ==========
    @api.model
    def _cron_session_reminders(self):
        """Envoie les rappels J-7, J-3, J-1 avant les sessions"""
        today = fields.Date.today()

        # Rappels à envoyer
        reminder_days = [7, 3, 1]

        for days in reminder_days:
            target_date = today + timedelta(days=days)

            # Trouver les sessions qui commencent ce jour
            sessions = self.search([
                ('state', '=', 'confirmed'),
                ('date_start', '>=', fields.Datetime.to_string(
                    datetime.combine(target_date, datetime.min.time())
                )),
                ('date_start', '<', fields.Datetime.to_string(
                    datetime.combine(target_date + timedelta(days=1), datetime.min.time())
                )),
            ])

            for session in sessions:
                session._send_reminder_emails(days)

        _logger.info("Cron rappels sessions exécuté")
        return True

    def _send_reminder_emails(self, days_before):
        """Envoie les emails de rappel aux participants"""
        self.ensure_one()

        template = self.env.ref('lms_presence.mail_template_session_reminder', raise_if_not_found=False)
        if not template:
            _logger.warning("Template de rappel non trouvé")
            return

        for line in self.attendance_line_ids:
            if line.participant_id.email:
                template.with_context(days_before=days_before).send_mail(
                    line.id,
                    force_send=False
                )

            # ✅ AJOUT: Rappel handicap pour J-7
            if days_before == 7 and line.has_disability:
                handicap_template = self.env.ref(
                    'lms_presence.mail_template_handicap_notification',
                    raise_if_not_found=False
                )
                if handicap_template:
                    handicap_template.send_mail(line.id, force_send=False)

        self._log_action('notification', _('Rappels J-%s envoyés') % days_before)

    @api.model
    def _cron_sync_participants(self):
        """Synchronise les participants des formations avec les sessions"""
        sessions = self.search([
            ('state', 'in', ['draft', 'confirmed']),
            ('date_start', '>=', fields.Datetime.now()),
        ])

        for session in sessions:
            if session.auto_generate_attendance:
                # Vérifier si de nouveaux participants ont été ajoutés
                existing_participants = session.attendance_line_ids.mapped('participant_id')
                new_participants = session.attendee_ids - existing_participants

                for participant in new_participants:
                    self.env['lms_presence.attendance_line'].create({
                        'session_id': session.id,
                        'participant_id': participant.id,
                    })

        _logger.info("Cron synchronisation participants exécuté")
        return True

    @api.model
    def _cron_detect_absences(self):
        """Détecte automatiquement les absences pour les sessions terminées"""
        # Sessions terminées il y a moins de 2 heures
        two_hours_ago = fields.Datetime.now() - timedelta(hours=2)

        sessions = self.search([
            ('state', '=', 'done'),
            ('date_end', '>=', two_hours_ago),
        ])

        for session in sessions:
            for line in session.attendance_line_ids:
                # Si pas de check-in et non déjà marqué comme absent
                if not line.check_in and line.state == 'draft':
                    line.write({
                        'state': 'absent',
                        'validated_by_teacher': True,
                        'validation_date_teacher': fields.Datetime.now(),
                    })

                    # ✅ LOG QUALIOPI
                    session._log_action(
                        'absence_detection',
                        _('Absence automatique détectée: %s') % line.participant_name
                    )

        _logger.info("Cron détection absences exécuté")
        return True

    # ✅ NOUVEAU: Cron relances inactivité (US-C4)
    @api.model
    def _cron_inactivity_reminders(self):
        """Relance les participants inactifs"""
        three_days_ago = fields.Datetime.now() - timedelta(days=3)

        sessions = self.search([
            ('state', '=', 'in_progress'),
            ('date_start', '<=', three_days_ago),
        ])

        for session in sessions:
            inactive_lines = session.attendance_line_ids.filtered(
                lambda l: l.state == 'draft' and not l.check_in
            )

            for line in inactive_lines:
                template = self.env.ref(
                    'lms_presence.mail_template_inactivity_reminder',
                    raise_if_not_found=False
                )
                if template and line.participant_id.email:
                    template.send_mail(line.id, force_send=False)

                    # LOG QUALIOPI - Preuve d'envoi
                    session._log_action(
                        'notification',
                        _('Relance inactivité envoyée à %s') % line.participant_name
                    )

        _logger.info("Cron relance inactivité exécuté")
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """Création en batch avec génération automatique des lignes de présence"""
        # Pré-traitement si nécessaire
        for vals in vals_list:
            # Vous pouvez préparer les valeurs ici si besoin
            pass

        # Création des sessions
        sessions = super(FormationAttendanceSession, self).create(vals_list)

        # Post-traitement en batch
        sessions_to_process = sessions.filtered(lambda s: s.auto_generate_attendance and s.attendee_ids)
        if sessions_to_process:
            sessions_to_process._generate_attendance_lines()

        # Logging en batch
        for session in sessions:
            session._log_action('create', _('Session créée'))

        return sessions