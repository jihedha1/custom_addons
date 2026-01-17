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
        default=lambda self: _('New'),
        tracking=True
    )

    # Contexte
    assessment_id = fields.Many2one(
        'lms_objectives.placement_assessment',
        string='Évaluation de positionnement',
        ondelete='set null'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Apprenant',
        required=True,
        tracking=True
    )

    course_id = fields.Many2one(
        'slide.channel',
        string='Formation',
        required=True,
        tracking=True
    )

    # Alias pour compatibilité
    channel_id = fields.Many2one(
        'slide.channel',
        string='Formation (alias)',
        related='course_id',
        store=True
    )

    supervisor_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True
    )

    # Type de plan
    plan_type = fields.Selection([
        ('initial', 'Initial'),
        ('standard', 'Standard'),
        ('remediation', 'Remédiation'),
        ('accelerated', 'Accéléré'),
        ('adapted', 'Adapté'),
    ], string='Type de plan', default='standard', required=True, tracking=True)

    # Template utilisé
    template_id = fields.Many2one(
        'lms_objectives.plan_template',
        string='Modèle utilisé',
        ondelete='set null'
    )

    # Objectifs liés
    objective_ids = fields.Many2many(
        'lms_objectives.smart_objective',
        string='Objectifs associés',
        help="Objectifs SMART de la formation inclus dans ce plan",
        relation='lms_plan_objective_rel',
        column1='individual_plan_id',
        column2='smart_objective_id'
    )

    # Contenu du plan
    specific_objectives = fields.Html(
        string='Objectifs spécifiques',
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

    notes = fields.Text(
        string='Notes complémentaires',
        help="Informations additionnelles sur le plan"
    )

    # Planning
    start_date = fields.Date(
        string='Date de début',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )

    end_date = fields.Date(
        string='Date de fin',
        required=True,
        tracking=True
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
    ], string='Statut', default='draft', tracking=True)

    status = fields.Selection(
        related='state',
        string='Statut (alias)',
        store=True
    )

    # Signature manuelle (alternative pour Community)
    signature = fields.Binary(
        string='Signature apprenant',
        attachment=True
    )

    signature_date = fields.Date(
        string='Date de signature',
        tracking=True
    )

    signature_name = fields.Char(
        string='Nom signataire'
    )

    # Alternative pour Community: stocker le PDF signé
    signed_pdf = fields.Binary(
        string='PDF signé',
        attachment=True,
        help="Télécharger le plan signé manuellement"
    )

    signed_pdf_filename = fields.Char(
        string='Nom du fichier PDF'
    )

    # Documents (alternative pour Community)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Annexes',
        relation='lms_plan_attachment_rel'
    )

    # Suivi
    progress = fields.Float(
        string='Progression (%)',
        default=0.0,
        digits=(5, 2),
        tracking=True
    )

    completion_date = fields.Date(
        string='Date d\'achèvement',
        tracking=True
    )

    evaluation_score = fields.Float(
        string='Score final (%)',
        digits=(5, 2),
        tracking=True
    )

    # Séquences
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle batch creation"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'lms_objectives.individual_plan') or _('New')
        return super(IndividualPlan, self).create(vals_list)

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

    def action_sign_manual(self):
        """Ouvrir l'interface de signature manuelle"""
        self.ensure_one()

        return {
            'name': _('Signature manuelle du plan'),
            'type': 'ir.actions.act_window',
            'res_model': 'lms_objectives.individual_plan',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'form_view_ref': 'lms_objectives.individual_plan_sign_form_view',
            }
        }

    def action_mark_signed(self):
        """Marquer comme signé manuellement"""
        self.write({
            'state': 'signed',
            'signature_date': fields.Date.today(),
            'signature_name': self.partner_id.name
        })
        self.message_post(body=_('Plan signé par l\'apprenant'))

    def action_upload_signed_pdf(self):
        """Télécharger un PDF signé"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Télécharger PDF signé'),
            'res_model': 'ir.attachment',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_res_model': 'lms_objectives.individual_plan',
                'default_res_id': self.id,
                'default_name': f'Plan_{self.name}_signe.pdf',
            }
        }

    def action_start_progress(self):
        """Démarrer le plan"""
        self.write({'state': 'in_progress'})
        self.message_post(body=_('Plan démarré'))

    def action_complete(self):
        """Terminer le plan"""
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.today(),
            'progress': 100.0
        })
        self.message_post(body=_('Plan terminé avec succès'))

    def action_generate_pdf(self):
        """Générer un PDF du plan"""
        self.ensure_one()
        return self.env.ref('lms_objectives.action_report_individual_plan').report_action(self)