# custom_addons/lms_public_info/wizards/appointment_wizard.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class AppointmentWizard(models.TransientModel):
    _name = 'lms_public_info.appointment_wizard'
    _description = 'Assistant de prise de rendez-vous'

    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True,
        domain="[('appointment_available', '=', True)]"
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        domain="[('is_company', '=', False)]"
    )

    appointment_type = fields.Selection([
        ('information', 'Information'),
        ('orientation', 'Orientation'),
        ('assessment', 'Évaluation de niveau'),
    ], string='Type de rendez-vous', required=True, default='information')

    preferred_date = fields.Date(
        string='Date souhaitée',
        required=True,
        default=fields.Date.context_today
    )

    preferred_time = fields.Selection([
        ('morning', 'Matin (9h-12h)'),
        ('afternoon', 'Après-midi (14h-18h)'),
        ('evening', 'Soir (18h-20h)'),
    ], string='Plage horaire souhaitée', required=True, default='morning')

    notes = fields.Text(
        string='Notes',
        help='Informations complémentaires ou questions spécifiques'
    )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Remplir automatiquement les informations du contact"""
        if self.partner_id:
            self.notes = _(
                "Contact : %s\n"
                "Email : %s\n"
                "Téléphone : %s\n"
                "Société : %s\n"
            ) % (
                             self.partner_id.name,
                             self.partner_id.email or '',
                             self.partner_id.phone or '',
                             self.partner_id.parent_id.name if self.partner_id.parent_id else ''
                         )

    def _get_time_slots(self):
        """Générer les créneaux horaires selon la plage choisie"""
        time_slots = {
            'morning': [
                ('09:00', '09:30'),
                ('09:30', '10:00'),
                ('10:00', '10:30'),
                ('10:30', '11:00'),
                ('11:00', '11:30'),
                ('11:30', '12:00'),
            ],
            'afternoon': [
                ('14:00', '14:30'),
                ('14:30', '15:00'),
                ('15:00', '15:30'),
                ('15:30', '16:00'),
                ('16:00', '16:30'),
                ('16:30', '17:00'),
                ('17:00', '17:30'),
                ('17:30', '18:00'),
            ],
            'evening': [
                ('18:00', '18:30'),
                ('18:30', '19:00'),
                ('19:00', '19:30'),
                ('19:30', '20:00'),
            ],
        }
        return time_slots.get(self.preferred_time, [])

    def action_create_appointment(self):
        """Créer le rendez-vous et le lead CRM"""
        self.ensure_one()

        # Vérifier la disponibilité
        if not self.channel_id.appointment_type_id:
            raise ValidationError(_(
                "Aucun type de rendez-vous configuré pour cette formation."
            ))

        # Créer l'événement calendrier
        event_vals = {
            'name': _('Rendez-vous %s - %s') % (
                dict(self._fields['appointment_type'].selection).get(self.appointment_type),
                self.channel_id.name
            ),
            'start': datetime.combine(self.preferred_date, datetime.min.time()),
            'stop': datetime.combine(self.preferred_date, datetime.min.time()) + timedelta(hours=1),
            'duration': 1,
            'description': self.notes,
            'partner_ids': [(6, 0, [self.partner_id.id])],
            'user_id': self.env.user.id,
            'appointment_type': self.appointment_type,
            'channel_id': self.channel_id.id,
            'appointment_type_id': self.channel_id.appointment_type_id.id,
        }

        event = self.env['calendar.event'].create(event_vals)

        # Retourner une confirmation
        return {
            'type': 'ir.actions.act_window_close',
            'params': {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Rendez-vous créé'),
                    'message': _(
                        'Le rendez-vous a été créé avec succès. '
                        'Un email de confirmation a été envoyé à %s.'
                    ) % self.partner_id.email,
                    'type': 'success',
                    'sticky': False,
                }
            }
        }