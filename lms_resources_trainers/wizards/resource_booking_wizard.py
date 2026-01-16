# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta


class ResourceBookingWizard(models.TransientModel):
    _name = 'lms_resources_trainers.resource_booking_wizard'
    _description = 'Assistant de réservation de ressource'

    # Champs du wizard
    resource_id = fields.Many2one(
        'lms_resources_trainers.resource_management',
        string='Ressource',
        required=True,
        domain="[('available_for_booking', '=', True), ('state', '=', 'available')]"
    )

    start_date = fields.Datetime(
        string='Date de début',
        required=True,
        default=lambda self: fields.Datetime.now()
    )

    end_date = fields.Datetime(
        string='Date de fin',
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(hours=2)
    )

    duration_hours = fields.Float(
        string='Durée (heures)',
        compute='_compute_duration',
        store=True
    )

    requester_id = fields.Many2one(
        'res.partner',
        string='Demandeur',
        required=True,
        default=lambda self: self.env.user.partner_id
    )

    trainer_id = fields.Many2one(
        'lms_resources_trainers.trainer_profile',
        string='Formateur'
    )

    course_id = fields.Many2one(
        'slide.channel',
        string='Formation'
    )

    purpose = fields.Text(
        string='Objet',
        required=True
    )

    participants_count = fields.Integer(
        string='Nombre de participants',
        default=1
    )

    # Informations de disponibilité
    is_available = fields.Boolean(
        string='Disponible',
        compute='_compute_availability'
    )

    conflicting_bookings = fields.Many2many(
        'lms_resources_trainers.resource_booking',
        string='Réservations en conflit',
        compute='_compute_availability'
    )

    # Options
    send_confirmation = fields.Boolean(
        string='Envoyer confirmation',
        default=True
    )

    create_calendar_event = fields.Boolean(
        string='Créer événement calendrier',
        default=True
    )

    # Méthodes de calcul
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for wizard in self:
            if wizard.start_date and wizard.end_date:
                delta = wizard.end_date - wizard.start_date
                wizard.duration_hours = delta.total_seconds() / 3600
            else:
                wizard.duration_hours = 0.0

    @api.depends('resource_id', 'start_date', 'end_date')
    def _compute_availability(self):
        for wizard in self:
            if wizard.resource_id and wizard.start_date and wizard.end_date:
                # Vérifier les conflits
                conflicts = self.env['lms_resources_trainers.resource_booking'].search([
                    ('resource_id', '=', wizard.resource_id.id),
                    ('state', '=', 'confirmed'),
                    ('start_date', '<', wizard.end_date),
                    ('end_date', '>', wizard.start_date)
                ])

                wizard.conflicting_bookings = conflicts
                wizard.is_available = len(conflicts) == 0
            else:
                wizard.conflicting_bookings = False
                wizard.is_available = False

    # Contraintes
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for wizard in self:
            if wizard.start_date >= wizard.end_date:
                raise ValidationError(_('La date de début doit être avant la date de fin.'))

            if wizard.start_date < fields.Datetime.now():
                raise ValidationError(_('La date de début ne peut pas être dans le passé.'))

    @api.constrains('participants_count')
    def _check_participants(self):
        for wizard in self:
            if wizard.participants_count < 1:
                raise ValidationError(_('Le nombre de participants doit être au moins 1.'))
            if wizard.resource_id.capacity and wizard.participants_count > wizard.resource_id.capacity:
                raise ValidationError(_(
                    f'La capacité maximale de la ressource est {wizard.resource_id.capacity} personnes.'
                ))

    # Méthodes d'action
    def action_check_availability(self):
        """Vérifier la disponibilité sans réserver"""
        self.ensure_one()

        if not self.is_available:
            conflict_names = ', '.join(self.conflicting_bookings.mapped('name'))
            raise UserError(_(
                f'La ressource n\'est pas disponible. Conflits avec: {conflict_names}'
            ))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Disponible'),
                'message': _('La ressource est disponible pour cette plage horaire.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_book_resource(self):
        """Effectuer la réservation"""
        self.ensure_one()

        # Vérifier la disponibilité
        if not self.is_available:
            conflict_names = ', '.join(self.conflicting_bookings.mapped('name'))
            raise UserError(_(
                f'La ressource n\'est pas disponible. Conflits avec: {conflict_names}'
            ))

        # Créer la réservation
        booking = self.env['lms_resources_trainers.resource_booking'].create({
            'resource_id': self.resource_id.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'requester_id': self.requester_id.id,
            'trainer_id': self.trainer_id.id if self.trainer_id else False,
            'course_id': self.course_id.id if self.course_id else False,
            'purpose': self.purpose,
            'participants_count': self.participants_count,
            'state': 'confirmed'
        })

        # Envoyer confirmation si demandé
        if self.send_confirmation:
            booking._send_confirmation_email()

        # Créer événement calendrier si demandé
        if self.create_calendar_event:
            self._create_calendar_event(booking)

        # Retourner vers la réservation créée
        return {
            'name': _('Réservation créée'),
            'type': 'ir.actions.act_window',
            'res_model': 'lms_resources_trainers.resource_booking',
            'view_mode': 'form',
            'res_id': booking.id,
            'target': 'current',
        }

    def _create_calendar_event(self, booking):
        """Créer un événement dans le calendrier"""
        event = self.env['calendar.event'].create({
            'name': f'Réservation: {booking.resource_id.name} - {booking.purpose}',
            'start': booking.start_date,
            'stop': booking.end_date,
            'location': booking.resource_id.location,
            'description': f"""
            Réservation de ressource: {booking.name}
            Ressource: {booking.resource_id.name}
            Demandeur: {booking.requester_id.name}
            Participants: {booking.participants_count}
            Objet: {booking.purpose}
            """,
            'partner_ids': [(4, booking.requester_id.id)],
            'resource_ids': [(4, booking.resource_id.id)],
        })

        booking.write({'calendar_event_id': event.id})

    @api.onchange('resource_id')
    def _onchange_resource_id(self):
        """Mettre à jour le nombre de participants maximum"""
        if self.resource_id and self.resource_id.capacity:
            self.participants_count = min(self.participants_count or 1, self.resource_id.capacity)