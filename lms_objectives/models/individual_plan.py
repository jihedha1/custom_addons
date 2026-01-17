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

    # Type de plan (AJOUTÉ)
    plan_type = fields.Selection([
        ('initial', 'Initial'),
        ('standard', 'Standard'),
        ('remediation', 'Remédiation'),
        ('accelerated', 'Accéléré'),
        ('adapted', 'Adapté'),
    ], string='Type de plan', default='standard', required=True, tracking=True)

    # Template utilisé (AJOUTÉ)
    template_id = fields.Many2one(
        'lms_objectives.plan_template',
        string='Modèle utilisé',
        ondelete='set null'
    )

    # Objectifs liés - CORRIGÉ avec nom de table personnalisé
    objective_ids = fields.Many2many(
        'lms_objectives.smart_objective',
        string='Objectifs associés',
        help="Objectifs SMART de la formation inclus dans ce plan",
        relation='lms_plan_objective_rel',  # Nom court pour éviter l'erreur
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

    # Signature électronique
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

    # Documents Sign
    sign_request_id = fields.Many2one(
        'sign.request',
        string='Demande de signature',
        ondelete='set null'
    )

    signed_document = fields.Binary(
        string='Document signé',
        attachment=True
    )

    signed_filename = fields.Char(
        string='Nom du fichier signé'
    )

    # Documents
    document_id = fields.Many2one(
        'documents.document',
        string='Document archivé',
        ondelete='set null'
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Annexes',
        relation='lms_plan_attachment_rel'  # Nom court pour éviter d'autres erreurs
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
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'lms_objectives.individual_plan') or _('New')
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
        """Ouvrir l'assistant de signature Sign"""
        self.ensure_one()

        # Vérifier si Sign est installé
        if not self.env['ir.module.module'].search([('name', '=', 'sign'), ('state', '=', 'installed')]):
            # Si Sign n'est pas installé, utiliser la signature manuelle
            return {
                'name': _('Signature manuelle'),
                'type': 'ir.actions.act_window',
                'res_model': 'lms_objectives.individual_plan',
                'view_mode': 'form',
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'current'
            }

        # Si Sign est installé, procéder avec la signature électronique
        # Générer le PDF du plan
        pdf_content = self._generate_pdf_content()

        # Créer une demande de signature
        sign_template = self.env.ref('lms_objectives.sign_template_individual_plan', raise_if_not_found=False)

        if not sign_template:
            raise ValidationError(_("Le modèle de signature n'est pas configuré"))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Signer le plan'),
            'res_model': 'sign.send.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': sign_template.id,
                'default_signer_ids': [(0, 0, {
                    'partner_id': self.partner_id.id,
                    'role_id': self.env.ref('sign.sign_item_role_customer').id,
                })],
                'default_reference': self.name,
                'default_subject': _('Plan de formation individualisé - %s') % self.name,
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

    def action_start_progress(self):
        """Démarrer le plan"""
        self.write({'state': 'in_progress'})
        self.message_post(body=_('Plan démarré'))

    def action_start(self):
        """Alias pour action_start_progress"""
        return self.action_start_progress()

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

    def _generate_pdf_content(self):
        """Générer le contenu PDF pour la signature"""
        self.ensure_one()

        report = self.env.ref('lms_objectives.action_report_individual_plan')
        pdf_content, _ = report._render_qweb_pdf(self.ids)

        return pdf_content


class PlanTemplate(models.Model):
    """Modèle de plan de formation"""
    _name = 'lms_objectives.plan_template'
    _description = 'Modèle de plan de formation'

    name = fields.Char(
        string='Nom du modèle',
        required=True
    )

    description = fields.Text(
        string='Description'
    )

    content = fields.Html(
        string='Contenu du modèle',
        help="Utiliser ${variable} pour les champs dynamiques"
    )

    plan_type = fields.Selection([
        ('initial', 'Initial'),
        ('standard', 'Standard'),
        ('remediation', 'Remédiation'),
        ('accelerated', 'Accéléré'),
        ('adapted', 'Adapté'),
    ], string='Type de plan')

    active = fields.Boolean(
        string='Actif',
        default=True
    )