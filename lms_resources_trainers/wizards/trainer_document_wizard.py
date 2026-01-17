# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class TrainerDocumentWizard(models.TransientModel):
    _name = 'lms_resources_trainers.trainer_document_wizard'
    _description = 'Assistant d\'ajout de document formateur'

    # Champs du wizard
    trainer_id = fields.Many2one(
        'res.partner',  # CORRIGÉ : utiliser res.partner au lieu de trainer_profile
        string='Formateur',
        required=True,
        domain="[('is_trainer', '=', True)]"  # Ajouter le domaine
    )

    document_type_id = fields.Many2one(
        'lms_resources_trainers.trainer_document_type',
        string='Type de document',
        required=True
    )

    name = fields.Char(
        string='Nom du document',
        required=True
    )

    attachment = fields.Binary(
        string='Fichier',
        required=True
    )

    attachment_filename = fields.Char(
        string='Nom du fichier'
    )

    issue_date = fields.Date(
        string='Date d\'émission',
        default=fields.Date.today
    )

    expiry_date = fields.Date(
        string='Date d\'expiration'
    )

    notes = fields.Text(string='Notes')

    # Champ pour conditionner le champ expiry_date
    document_type_has_expiry_date = fields.Boolean(
        string='Document avec expiration',
        compute='_compute_document_type_info'
    )

    # Méthodes
    @api.depends('document_type_id')
    def _compute_document_type_info(self):
        """Calcule les informations du type de document"""
        for wizard in self:
            wizard.document_type_has_expiry_date = wizard.document_type_id.has_expiry_date if wizard.document_type_id else False

    @api.onchange('document_type_id')
    def _onchange_document_type_id(self):
        """Mettre à jour les informations selon le type de document"""
        if self.document_type_id:
            self.name = self.document_type_id.name

            if self.document_type_id.has_expiry_date and self.document_type_id.validity_duration:
                self.expiry_date = fields.Date.today() + timedelta(days=self.document_type_id.validity_duration * 30)

    @api.constrains('expiry_date')
    def _check_expiry_date(self):
        for wizard in self:
            if wizard.expiry_date and wizard.expiry_date < fields.Date.today():
                raise ValidationError(_('La date d\'expiration ne peut pas être dans le passé.'))

    def action_add_document(self):
        """Ajouter le document au formateur"""
        self.ensure_one()

        # Créer l'attachement
        attachment = self.env['ir.attachment'].create({
            'name': self.attachment_filename or f'{self.name}.pdf',
            'datas': self.attachment,
            'res_model': 'lms_resources_trainers.trainer_document',
            'res_id': 0,  # Temporaire
        })

        # Créer le document formateur
        document = self.env['lms_resources_trainers.trainer_document'].create({
            'trainer_id': self.trainer_id.id,
            'document_type_id': self.document_type_id.id,
            'name': self.name,
            'attachment_id': attachment.id,
            'issue_date': self.issue_date,
            'expiry_date': self.expiry_date,
            'notes': self.notes,
            'state': 'pending'
        })

        # Mettre à jour l'attachement avec le bon res_id
        attachment.write({'res_id': document.id})

        # Retourner vers le formateur (res.partner)
        return {
            'name': _('Document ajouté'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'res_id': self.trainer_id.id,
            'target': 'current',
            'context': {'form_view_ref': 'base.view_partner_form'}
        }