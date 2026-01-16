# custom_addons/lms_public_kpi/wizard/kpi_rejection_wizard.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class KPIRejectionWizard(models.TransientModel):
    _name = 'kpi.rejection.wizard'
    _description = 'Wizard pour rejeter un snapshot'

    snapshot_id = fields.Many2one(
        'public.kpi.snapshot',
        string='Snapshot',
        required=True,
        readonly=True
    )

    reason = fields.Selection([
        ('incomplete', 'Données incomplètes'),
        ('incorrect', 'Données incorrectes'),
        ('methodology', 'Méthodologie non conforme'),
        ('timing', 'Période inappropriée'),
        ('other', 'Autre raison'),
    ], string='Raison du rejet', required=True)

    notes = fields.Text(
        string='Commentaires',
        required=True,
        help="Expliquez les raisons du rejet et les corrections à apporter"
    )

    notify_creator = fields.Boolean(
        string='Notifier le créateur',
        default=True,
        help="Envoyer un email au créateur du snapshot"
    )

    def action_reject(self):
        """Rejeter le snapshot"""
        self.ensure_one()

        # Retour en brouillon
        self.snapshot_id.write({'state': 'draft'})

        # Message dans le chatter
        reason_text = dict(self._fields['reason'].selection)[self.reason]

        self.snapshot_id.message_post(
            body=_(
                '<strong>❌ Snapshot rejeté</strong><br/>'
                'Raison: <strong>%s</strong><br/>'
                'Commentaires:<br/>%s<br/>'
                'Rejeté par: %s'
            ) % (reason_text, self.notes, self.env.user.name),
            message_type='notification',
            subtype_id=self.env.ref('mail.mt_note').id
        )

        # Créer activité pour le créateur
        if self.notify_creator and self.snapshot_id.create_uid:
            self.snapshot_id.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.snapshot_id.create_uid.id,
                summary=_('🔴 Snapshot rejeté : %s') % self.snapshot_id.name,
                note=_(
                    'Votre snapshot "%s" a été rejeté.\n\n'
                    'Raison: %s\n\n'
                    'Commentaires:\n%s\n\n'
                    'Veuillez apporter les corrections nécessaires et soumettre à nouveau.'
                ) % (self.snapshot_id.name, reason_text, self.notes)
            )

        return {'type': 'ir.actions.act_window_close'}