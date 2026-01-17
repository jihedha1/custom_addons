# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta


class ResourceManagement(models.Model):
    _name = 'lms_resources_trainers.resource_management'
    _description = 'Gestion des ressources'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # =====================
    # IDENTIFICATION
    # =====================
    name = fields.Char(string='Nom', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)

    resource_type_id = fields.Many2one(
        'lms_resources_trainers.resource_type',
        string='Type de ressource',
        required=True,
        tracking=True
    )

    # =====================
    # CARACTÉRISTIQUES
    # =====================
    description = fields.Text(string='Description')
    capacity = fields.Integer(string='Capacité (personnes)', tracking=True)
    location = fields.Char(string='Localisation', required=True, tracking=True)
    floor = fields.Char(string='Étage')
    building = fields.Char(string='Bâtiment')

    # =====================
    # ÉQUIPEMENTS
    # =====================
    equipment_ids = fields.Many2many(
        'lms_resources_trainers.resource_equipment',
        'resource_equipment_rel',
        'resource_id',
        'equipment_id',
        string='Équipements'
    )

    technical_specifications = fields.Html(string='Spécifications techniques')

    # =====================
    # DISPONIBILITÉ
    # =====================
    available_for_booking = fields.Boolean(
        string='Disponible pour réservation',
        default=True,
        tracking=True
    )

    booking_ids = fields.One2many(
        'lms_resources_trainers.resource_booking',
        'resource_id',
        string='Réservations'
    )

    upcoming_bookings = fields.Integer(
        string='Réservations à venir',
        compute='_compute_booking_stats'
    )

    current_booking_id = fields.Many2one(
        'lms_resources_trainers.resource_booking',
        string='Réservation en cours',
        compute='_compute_current_booking'
    )

    # =====================
    # MAINTENANCE
    # =====================
    maintenance_schedule = fields.Selection([
        ('weekly', 'Hebdomadaire'),
        ('monthly', 'Mensuelle'),
        ('quarterly', 'Trimestrielle'),
        ('yearly', 'Annuelle')
    ], string='Planning de maintenance')

    last_maintenance_date = fields.Date(string='Dernière maintenance')
    next_maintenance_date = fields.Date(string='Prochaine maintenance')
    maintenance_notes = fields.Text(string='Notes de maintenance')

    # =====================
    # STATUT
    # =====================
    state = fields.Selection([
        ('available', 'Disponible'),
        ('occupied', 'Occupé'),
        ('maintenance', 'En maintenance'),
        ('out_of_service', 'Hors service')
    ], string='Statut', default='available', tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    # =====================
    # MÉTHODES COMPUTE
    # =====================
    @api.depends('booking_ids', 'booking_ids.state', 'booking_ids.end_date')
    def _compute_booking_stats(self):
        """Calcule le nombre de réservations à venir"""
        today = fields.Date.today()
        for resource in self:
            upcoming = resource.booking_ids.filtered(
                lambda b: b.end_date >= today and b.state == 'confirmed'
            )
            resource.upcoming_bookings = len(upcoming)

    @api.depends('booking_ids', 'booking_ids.start_date', 'booking_ids.end_date', 'booking_ids.state')
    def _compute_current_booking(self):
        """Trouve la réservation en cours"""
        now = fields.Datetime.now()
        for resource in self:
            current = resource.booking_ids.filtered(
                lambda b: b.start_date <= now <= b.end_date and b.state == 'confirmed'
            )
            resource.current_booking_id = current[0] if current else False

    # =====================
    # CONTRAINTES
    # =====================
    @api.constrains('capacity')
    def _check_capacity(self):
        for resource in self:
            if resource.capacity < 0:
                raise ValidationError(_('La capacité doit être positive.'))

    @api.constrains('code')
    def _check_code_unique(self):
        for resource in self:
            if self.search_count([('code', '=', resource.code), ('id', '!=', resource.id)]) > 0:
                raise ValidationError(_('Le code doit être unique.'))

    # =====================
    # MÉTHODES D'ACTION
    # =====================
    def action_check_availability(self, start_date, end_date):
        """Vérifie la disponibilité sur une période"""
        self.ensure_one()

        conflicting_bookings = self.booking_ids.filtered(
            lambda b: (
                    b.state == 'confirmed' and
                    not (end_date <= b.start_date or start_date >= b.end_date)
            )
        )

        return len(conflicting_bookings) == 0

    def action_book_resource(self, start_date, end_date, requester_id, purpose):
        """Réserve la ressource"""
        self.ensure_one()

        if not self.available_for_booking:
            raise UserError(_('Cette ressource n\'est pas disponible pour réservation.'))

        if not self.action_check_availability(start_date, end_date):
            raise UserError(_('La ressource n\'est pas disponible sur cette période.'))

        booking = self.env['lms_resources_trainers.resource_booking'].create({
            'resource_id': self.id,
            'start_date': start_date,
            'end_date': end_date,
            'requester_id': requester_id,
            'purpose': purpose,
            'state': 'confirmed'
        })

        return booking

    def action_put_in_maintenance(self, duration_days=7):
        """Met la ressource en maintenance"""
        for resource in self:
            resource.write({
                'state': 'maintenance',
                'last_maintenance_date': fields.Date.today(),
                'next_maintenance_date': fields.Date.today() + timedelta(days=duration_days)
            })

    def action_make_available(self):
        """Rend la ressource disponible"""
        self.write({'state': 'available'})

    def action_view_bookings(self):
        """Ouvre les réservations de la ressource"""
        self.ensure_one()
        return {
            'name': _('Réservations - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'lms_resources_trainers.resource_booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('resource_id', '=', self.id)],
            'context': {'default_resource_id': self.id}
        }


class ResourceType(models.Model):
    _name = 'lms_resources_trainers.resource_type'
    _description = 'Type de ressource'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    icon = fields.Char(string='Icône FontAwesome', default='fa-cube')


class ResourceEquipment(models.Model):
    _name = 'lms_resources_trainers.resource_equipment'
    _description = 'Équipement de ressource'

    name = fields.Char(string='Nom', required=True)
    description = fields.Text(string='Description')
    technical_specs = fields.Text(string='Spécifications techniques')


class ResourceBooking(models.Model):
    _name = 'lms_resources_trainers.resource_booking'
    _description = 'Réservation de ressource'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    # =====================
    # IDENTIFICATION
    # =====================
    name = fields.Char(
        string='Référence',
        default=lambda self: _('Nouvelle réservation'),
        required=True
    )

    resource_id = fields.Many2one(
        'lms_resources_trainers.resource_management',
        string='Ressource',
        required=True,
        tracking=True
    )

    # =====================
    # DATES
    # =====================
    start_date = fields.Datetime(string='Date de début', required=True, tracking=True)
    end_date = fields.Datetime(string='Date de fin', required=True, tracking=True)

    duration = fields.Float(
        string='Durée (heures)',
        compute='_compute_duration',
        store=True
    )

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for booking in self:
            if booking.start_date and booking.end_date:
                delta = booking.end_date - booking.start_date
                booking.duration = delta.total_seconds() / 3600
            else:
                booking.duration = 0.0

    # =====================
    # REQUÉRANT
    # =====================
    requester_id = fields.Many2one(
        'res.partner',
        string='Demandeur',
        required=True,
        tracking=True
    )

    trainer_id = fields.Many2one(
        'lms_resources_trainers.trainer_profile',
        string='Formateur'
    )

    course_id = fields.Many2one(
        'slide.channel',
        string='Formation'
    )

    purpose = fields.Text(string='Objet', required=True, tracking=True)
    participants_count = fields.Integer(string='Nombre de participants', tracking=True)

    # =====================
    # STATUT
    # =====================
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('in_use', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', tracking=True)

    confirmation_date = fields.Datetime(string='Date de confirmation')
    confirmed_by = fields.Many2one('res.users', string='Confirmé par')

    notes = fields.Text(string='Notes')
    company_id = fields.Many2one('res.company', string='Société', default=lambda self: self.env.company)

    # =====================
    # CONTRAINTES
    # =====================
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for booking in self:
            if booking.start_date >= booking.end_date:
                raise ValidationError(_('La date de début doit être avant la date de fin.'))

    @api.constrains('participants_count')
    def _check_participants(self):
        for booking in self:
            if booking.participants_count < 0:
                raise ValidationError(_('Le nombre de participants doit être positif.'))

            if booking.resource_id.capacity and booking.participants_count > booking.resource_id.capacity:
                raise ValidationError(_(
                    'La capacité maximale de la ressource est %d personnes.'
                ) % booking.resource_id.capacity)

    # =====================
    # MÉTHODES
    # =====================
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nouvelle réservation')) == _('Nouvelle réservation'):
            vals['name'] = self.env['ir.sequence'].next_by_code('lms.resource.booking') or _('Nouvelle réservation')
        return super().create(vals)

    def action_confirm(self):
        """Confirme la réservation"""
        for booking in self:
            if not booking.resource_id.action_check_availability(booking.start_date, booking.end_date):
                raise UserError(_('La ressource n\'est pas disponible sur cette période.'))

            booking.write({
                'state': 'confirmed',
                'confirmation_date': fields.Datetime.now(),
                'confirmed_by': self.env.user.id
            })

            booking._send_confirmation_email()

    def action_cancel(self):
        """Annule la réservation"""
        self.write({'state': 'cancelled'})

    def _send_confirmation_email(self):
        """Envoie l'email de confirmation"""
        template = self.env.ref('lms_resources_trainers.mail_template_resource_booking', raise_if_not_found=False)
        if template:
            for booking in self:
                if booking.requester_id.email:
                    template.send_mail(booking.id, force_send=True)

    @api.model
    def _cron_check_active_bookings(self):
        """Vérifie les réservations actives"""
        now = fields.Datetime.now()

        # Réservations qui doivent commencer
        starting = self.search([
            ('state', '=', 'confirmed'),
            ('start_date', '<=', now),
            ('end_date', '>', now)
        ])
        starting.write({'state': 'in_use'})

        # Réservations terminées
        completed = self.search([
            ('state', 'in', ['confirmed', 'in_use']),
            ('end_date', '<', now)
        ])
        completed.write({'state': 'completed'})