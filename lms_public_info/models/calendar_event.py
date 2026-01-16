# custom_addons/lms_public_info/models/calendar_event.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CalendarEventQualiopi(models.Model):
    _inherit = 'calendar.event'

    # =====================
    # LIEN AVEC FORMATION
    # =====================

    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation concernée',
        domain="[('appointment_available', '=', True)]"
    )

    # =====================
    # INFORMATIONS QUALIOPI
    # =====================

    appointment_type = fields.Selection([
        ('information', 'Information'),
        ('orientation', 'Orientation'),
        ('assessment', 'Évaluation de niveau'),
        ('custom', 'Personnalisé'),
    ], string='Type de rendez-vous', default='information')

    # =====================
    # SURCHARGES
    # =====================

    @api.model
    def create(self, vals):
        """Créer un lead CRM à partir du rendez-vous"""
        event = super(CalendarEventQualiopi, self).create(vals)

        # Si c'est un rendez-vous lié à une formation, créer un lead
        if event.channel_id and event.partner_ids:
            event._create_crm_lead()

        return event

    def _create_crm_lead(self):
        """Créer un lead CRM à partir du rendez-vous"""
        Lead = self.env['crm.lead']

        for event in self:
            if not event.channel_id or not event.partner_ids:
                continue

            # Trouver le contact principal
            main_partner = event.partner_ids[0]

            # Créer le lead
            lead_vals = {
                'name': _('Rendez-vous information - %s') % event.channel_id.name,
                'partner_id': main_partner.id,
                'contact_name': main_partner.name,
                'email_from': main_partner.email,
                'phone': main_partner.phone,
                'description': _(
                    "Rendez-vous pris pour la formation : %s\n"
                    "Date : %s\n"
                    "Type : %s\n"
                    "Notes : %s"
                ) % (
                                   event.channel_id.name,
                                   event.start,
                                   dict(self._fields['appointment_type'].selection).get(event.appointment_type),
                                   event.description or ''
                               ),
                'type': 'opportunity',
                'stage_id': self.env.ref('crm.stage_lead1').id,
                'user_id': event.user_id.id,
                'tag_ids': [(4, self.env.ref('lms_public_info.tag_appointment_lead').id)],
            }

            lead = Lead.create(lead_vals)

            # Lier le lead à l'événement
            event.message_post(
                body=_('Lead CRM créé : <a href="#" data-oe-model="crm.lead" data-oe-id="%d">%s</a>') %
                     (lead.id, lead.name)
            )

    # =====================
    # ACTIONS
    # =====================

    def action_view_lead(self):
        """Voir le lead CRM associé"""
        self.ensure_one()

        # Trouver le lead associé (via les messages)
        messages = self.env['mail.message'].search([
            ('model', '=', 'calendar.event'),
            ('res_id', '=', self.id),
            ('body', 'ilike', 'Lead CRM créé')
        ])

        if not messages:
            raise UserError(_("Aucun lead CRM associé à ce rendez-vous"))

        # Extraire l'ID du lead du message
        import re
        match = re.search(r'data-oe-id="(\d+)"', messages[0].body)
        if match:
            lead_id = int(match.group(1))
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'crm.lead',
                'res_id': lead_id,
                'view_mode': 'form',
                'target': 'current',
            }

        raise UserError(_("Impossible de trouver le lead CRM associé"))