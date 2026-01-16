# custom_addons/lms_quality/models/non_conformity.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class QualityNonConformity(models.Model):
    _name = 'quality.non_conformity'  # ✅ CORRIGÉ : suppression du préfixe lms_quality
    _description = 'Non-conformité Qualiopi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'detection_date desc, create_date desc'  # ✅ AMÉLIORÉ

    # Identification
    name = fields.Char(
        string='Référence',
        required=True,
        readonly=True,
        default=lambda self: _('New'),
        copy=False,
        tracking=True  # ✅ AJOUTÉ pour traçabilité
    )

    # Description
    title = fields.Char(
        string='Titre',
        required=True,
        tracking=True  # ✅ CORRIGÉ : track_visibility est obsolète en v17
    )

    description = fields.Html(
        string='Description détaillée',
        required=True,
        tracking=True
    )

    # Classification
    type = fields.Selection([
        ('minor', 'Mineure'),
        ('major', 'Majeure'),
        ('critical', 'Critique'),
    ], string='Type', required=True, default='minor', tracking=True)

    category = fields.Selection([
        ('pedagogical', 'Pédagogique'),
        ('administrative', 'Administrative'),
        ('technical', 'Technique'),
        ('safety', 'Sécurité'),
        ('other', 'Autre'),
    ], string='Catégorie', required=True, default='administrative', tracking=True)

    # Source
    source = fields.Selection([
        ('internal_audit', 'Audit interne'),
        ('external_audit', 'Audit externe'),
        ('complaint', 'Réclamation'),
        ('self_assessment', 'Auto-évaluation'),
        ('monitoring', 'Suivi des indicateurs'),
        ('other', 'Autre'),
    ], string='Source', required=True, default='internal_audit', tracking=True)

    # Dates
    detection_date = fields.Date(
        string='Date de détection',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )

    treatment_deadline = fields.Date(
        string='Échéance de traitement',
        tracking=True
    )

    closure_date = fields.Date(  # ✅ AJOUTÉ : manquait pour traçabilité
        string='Date de clôture',
        readonly=True,
        tracking=True
    )

    # Responsables
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsable traitement',
        required=True,
        tracking=True,
        default=lambda self: self.env.user  # ✅ AJOUTÉ : valeur par défaut
    )

    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('analysis', 'En analyse'),
        ('action_plan', 'Plan d\'action'),
        ('implementation', 'Mise en œuvre'),
        ('verification', 'Vérification'),
        ('closed', 'Clôturé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True, required=True)

    # Actions correctives
    corrective_action_ids = fields.One2many(
        'quality.corrective.action',
        'non_conformity_id',
        string='Actions correctives'
    )

    # Pièces jointes
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'quality_nc_attachment_rel',  # ✅ AJOUTÉ : nom de table explicite
        'nc_id',
        'attachment_id',
        string='Pièces jointes'
    )

    # Indicateurs
    action_count = fields.Integer(
        string='Nombre d\'actions',
        compute='_compute_action_count',
        store=True
    )

    completed_action_count = fields.Integer(
        string='Actions terminées',
        compute='_compute_action_count',
        store=True
    )

    completion_rate = fields.Float(
        string='Taux de complétion',
        compute='_compute_action_count',
        store=True,
        digits=(5, 2)
    )

    # Champs calculés pour les rappels
    is_overdue = fields.Boolean(
        string='En retard',
        compute='_compute_overdue',
        store=True,
        search='_search_is_overdue'  # ✅ AJOUTÉ : pour recherche
    )

    days_overdue = fields.Integer(
        string='Jours de retard',
        compute='_compute_overdue',
        store=True
    )

    # ✅ AJOUTÉ : Champs manquants pour conformité Qualiopi
    impact_qualiopi = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ], string='Impact Qualiopi', tracking=True)

    root_cause = fields.Html(
        string='Cause racine identifiée',
        help='Analyse 5 Pourquoi ou diagramme Ishikawa',
        tracking=True
    )

    immediate_action = fields.Html(
        string='Action immédiate prise',
        help='Mesure conservatoire avant analyse complète',
        tracking=True
    )

    # Méthodes de calcul
    @api.depends('corrective_action_ids', 'corrective_action_ids.state')
    def _compute_action_count(self):
        for nc in self:
            actions = nc.corrective_action_ids
            nc.action_count = len(actions)
            nc.completed_action_count = len(actions.filtered(lambda a: a.state in ['done', 'closed']))
            if nc.action_count > 0:
                nc.completion_rate = (nc.completed_action_count / nc.action_count) * 100
            else:
                nc.completion_rate = 0.0

    @api.depends('treatment_deadline', 'state')
    def _compute_overdue(self):
        today = date.today()
        for nc in self:
            if nc.treatment_deadline and nc.state not in ['closed', 'cancelled']:
                nc.is_overdue = nc.treatment_deadline < today
                if nc.is_overdue:
                    nc.days_overdue = (today - nc.treatment_deadline).days
                else:
                    nc.days_overdue = 0
            else:
                nc.is_overdue = False
                nc.days_overdue = 0

    def _search_is_overdue(self, operator, value):  # ✅ AJOUTÉ
        """Permet de rechercher les NC en retard"""
        today = date.today()
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [
                ('treatment_deadline', '<', today),
                ('state', 'not in', ['closed', 'cancelled'])
            ]
        else:
            return [
                '|',
                ('treatment_deadline', '>=', today),
                ('state', 'in', ['closed', 'cancelled'])
            ]

    # Contraintes
    @api.constrains('detection_date', 'treatment_deadline')
    def _check_dates(self):
        for nc in self:
            if nc.treatment_deadline and nc.treatment_deadline < nc.detection_date:
                raise ValidationError(
                    _("L'échéance de traitement ne peut pas être antérieure à la date de détection")
                )

    # ✅ AJOUTÉ : Contrainte sur titre unique par période
    @api.constrains('title', 'detection_date')
    def _check_unique_title(self):
        for nc in self:
            duplicate = self.search([
                ('id', '!=', nc.id),
                ('title', '=', nc.title),
                ('detection_date', '=', nc.detection_date),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("Une non-conformité avec ce titre existe déjà pour cette date")
                )

    # Séquences
    @api.model_create_multi  # ✅ CORRIGÉ : utilisation de model_create_multi pour v17
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.non_conformity') or _('New')

        ncs = super(QualityNonConformity, self).create(vals_list)

        # Créer une activité pour le responsable
        for nc in ncs:
            nc.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=nc.responsible_user_id.id,
                summary=_('Nouvelle non-conformité à traiter'),
                note=_('Nouvelle non-conformité à traiter: %s') % nc.title
            )

        return ncs

    # Actions du workflow
    def action_start_analysis(self):
        """Démarrer l'analyse de la NC"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Seules les NC en brouillon peuvent être analysées"))

        self.write({'state': 'analysis'})
        self._log_activity(_('Analyse démarrée'))

        # ✅ AJOUTÉ : Notifier le responsable
        self.message_post(
            body=_("L'analyse de cette non-conformité a débuté."),
            subject=_("Début d'analyse"),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

    def action_create_action_plan(self):
        """Créer le plan d'action"""
        self.ensure_one()
        if self.state != 'analysis':
            raise UserError(_("La NC doit être en analyse pour créer un plan d'action"))

        # ✅ AJOUTÉ : Vérifier qu'au moins une action est créée
        if not self.corrective_action_ids:
            raise UserError(
                _("Vous devez créer au moins une action corrective avant de passer au plan d'action")
            )

        self.write({'state': 'action_plan'})
        self._log_activity(_('Plan d\'action créé'))

    def action_start_implementation(self):
        """Démarrer la mise en œuvre"""
        self.ensure_one()
        if self.state != 'action_plan':
            raise UserError(_("Un plan d'action doit être validé avant la mise en œuvre"))

        self.write({'state': 'implementation'})
        self._log_activity(_('Mise en œuvre démarrée'))

    def action_start_verification(self):
        """Démarrer la vérification"""
        self.ensure_one()
        if self.state != 'implementation':
            raise UserError(_("La mise en œuvre doit être terminée avant la vérification"))

        # ✅ AJOUTÉ : Vérifier que toutes les actions sont au moins terminées
        pending_actions = self.corrective_action_ids.filtered(
            lambda a: a.state not in ['done', 'closed']
        )
        if pending_actions:
            raise UserError(
                _("Toutes les actions doivent être au moins terminées avant la vérification. "
                  "Actions en attente : %s") % ', '.join(pending_actions.mapped('name'))
            )

        self.write({'state': 'verification'})
        self._log_activity(_('Vérification démarrée'))

    def action_close(self):
        """Clôturer la NC (via wizard normalement)"""
        self.ensure_one()

        # Vérifier que toutes les actions sont closes
        open_actions = self.corrective_action_ids.filtered(lambda a: a.state != 'closed')
        if open_actions:
            raise UserError(
                _('Impossible de clôturer: %d action(s) corrective(s) encore ouverte(s).') % len(open_actions)
            )

        self.write({
            'state': 'closed',
            'closure_date': fields.Date.today()  # ✅ AJOUTÉ
        })
        self._log_activity(_('Non-conformité clôturée'))

    def action_cancel(self):
        """Annuler la NC"""
        self.ensure_one()

        # ✅ AJOUTÉ : Demander confirmation si des actions sont en cours
        if self.corrective_action_ids.filtered(lambda a: a.state == 'in_progress'):
            raise UserError(
                _("Des actions correctives sont en cours. Veuillez les annuler d'abord.")
            )

        self.write({'state': 'cancelled'})
        self._log_activity(_('Non-conformité annulée'))

    def action_reopen(self):
        """Ré-ouvrir une NC"""
        self.ensure_one()
        if self.state not in ['closed', 'cancelled']:
            raise UserError(_("Seules les NC clôturées ou annulées peuvent être ré-ouvertes"))

        self.write({
            'state': 'analysis',
            'closure_date': False  # ✅ AJOUTÉ
        })
        self._log_activity(_('Non-conformité ré-ouverte'))

    def _log_activity(self, message):
        """Journalisation d'activité"""
        self.ensure_one()
        self.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

    # Méthodes CRON
    @api.model  # ✅ CORRIGÉ : ajout décorateur
    def _cron_check_overdue_nc(self):
        """Vérifie les non-conformités en retard et crée des activités"""
        today = fields.Date.today()

        # ✅ CORRIGÉ : Recherche améliorée
        overdue_ncs = self.search([
            ('state', 'not in', ['closed', 'cancelled']),
            ('treatment_deadline', '<', today),
        ])

        for nc in overdue_ncs:
            # Vérifier si une activité de retard existe déjà
            existing_activity = self.env['mail.activity'].search([
                ('res_id', '=', nc.id),
                ('res_model_id', '=', self.env['ir.model']._get_id('quality.non_conformity')),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_warning').id),
                ('user_id', '=', nc.responsible_user_id.id),
                ('summary', 'ilike', 'retard'),
            ], limit=1)

            if not existing_activity:
                # Créer une activité d'alerte
                nc.activity_schedule(
                    'mail.mail_activity_data_warning',  # ✅ CORRIGÉ : utiliser warning au lieu de todo
                    user_id=nc.responsible_user_id.id,
                    summary=_('⚠️ Non-conformité en retard!'),
                    note=_('Non-conformité en retard de %d jours! Échéance: %s') % (
                        nc.days_overdue, nc.treatment_deadline
                    )
                )

                nc.message_post(
                    body=_('⚠️ Alerte: non-conformité en retard de %d jours') % nc.days_overdue,
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )

        _logger.info(f"CRON NC: {len(overdue_ncs)} non-conformités en retard traitées")

    # ✅ AJOUTÉ : Méthode pour rapport Qualiopi
    def get_quality_statistics(self, date_from=None, date_to=None):
        """Génère les statistiques qualité pour le tableau de bord"""
        domain = []

        if date_from:
            domain.append(('detection_date', '>=', date_from))
        if date_to:
            domain.append(('detection_date', '<=', date_to))

        ncs = self.search(domain)

        return {
            'total': len(ncs),
            'by_type': {
                'minor': len(ncs.filtered(lambda n: n.type == 'minor')),
                'major': len(ncs.filtered(lambda n: n.type == 'major')),
                'critical': len(ncs.filtered(lambda n: n.type == 'critical')),
            },
            'by_state': {
                'open': len(ncs.filtered(lambda n: n.state not in ['closed', 'cancelled'])),
                'closed': len(ncs.filtered(lambda n: n.state == 'closed')),
                'cancelled': len(ncs.filtered(lambda n: n.state == 'cancelled')),
            },
            'overdue': len(ncs.filtered(lambda n: n.is_overdue)),
            'completion_rate': sum(ncs.mapped('completion_rate')) / len(ncs) if ncs else 0,
        }