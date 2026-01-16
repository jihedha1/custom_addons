# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class IndividualPlan(models.Model):
    _name = 'lms_objectives.individual_plan'
    _description = 'Plan de formation individualisé'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Référence',
        required=True,
        readonly=True,
        default=lambda self: _('New')
    )

    # Contexte
    assessment_id = fields.Many2one(
        'formation.placement.assessment',
        string='Évaluation de positionnement',
        ondelete='set null'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Apprenant',
        required=True,
        domain="[('is_training_participant', '=', True)]"
    )

    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True
    )

    # Contenu du plan
    specific_objectives = fields.Html(
        string='Objectifs spécifiques',
        required=True,
        help="Objectifs adaptés aux besoins de l'apprenant"
    )

    pedagogical_approach = fields.Html(
        string='Approche pédagogique',
        help="Méthodes et outils pédagogiques recommandés"
    )

    adaptations = fields.Html(
        string='Adaptations nécessaires',
        help="Aménagements spécifiques pour cet apprenant"
    )

    evaluation_criteria = fields.Html(
        string='Critères d\'évaluation',
        help="Comment évaluer la progression de l'apprenant"
    )

    # Planning
    start_date = fields.Date(
        string='Date de début',
        default=fields.Date.context_today
    )

    end_date = fields.Date(
        string='Date de fin'
    )

    estimated_hours = fields.Float(
        string='Heures estimées',
        help="Nombre d'heures estimées pour ce plan"
    )

    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('validated', 'Validé'),
        ('signed', 'Signé'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='draft', track_visibility='onchange')

    # Signature électronique
    signature = fields.Binary(
        string='Signature apprenant',
        attachment=True
    )

    signature_date = fields.Date(
        string='Date de signature'
    )

    signature_name = fields.Char(
        string='Nom signataire'
    )

    # Documents
    document_id = fields.Many2one(
        'documents.document',
        string='Document signé'
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Annexes'
    )

    # Suivi
    progress = fields.Float(
        string='Progression (%)',
        default=0.0,
        track_visibility='onchange'
    )

    completion_date = fields.Date(
        string='Date d\'achèvement'
    )

    evaluation_score = fields.Float(
        string='Score final (%)',
        digits=(5, 2)
    )

    # Séquences
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'formation.individual.plan') or _('New')
        return super(IndividualPlan, self).create(vals)

    # Contraintes
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for plan in self:
            if plan.start_date and plan.end_date and plan.end_date < plan.start_date:
                raise ValidationError(_(
                    "La date de fin doit être postérieure à la date de début."
                ))

    # Actions
    def action_validate(self):
        """Valider le plan"""
        self.write({'state': 'validated'})
        self.message_post(body=_('Plan validé par le formateur'))

    def action_sign(self):
        """Ouvrir l'assistant de signature"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signer le plan'),
            'res_model': 'sign.send.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.env.ref(
                    'lms_objectives.sign_template_individual_plan').id,
                'default_partner_ids': [(6, 0, [self.partner_id.id])],
                'default_individual_plan_id': self.id,
            }
        }

    def action_mark_signed(self):
        """Marquer comme signé"""
        self.write({
            'state': 'signed',
            'signature_date': fields.Date.today(),
            'signature_name': self.partner_id.name
        })
        self.message_post(body=_('Plan signé par l\'apprenant'))

    def action_start_progress(self):
        """Démarrer le plan"""
        self.write({'state': 'in_progress'})

    def action_complete(self):
        """Terminer le plan"""
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.today(),
            'progress': 100.0
        })

    def action_generate_pdf(self):
        """Générer un PDF du plan"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/lms/plan/pdf/{self.id}',
            'target': 'new'
        }