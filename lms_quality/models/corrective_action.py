# custom_addons/lms_quality/models/corrective_action.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class QualityCorrectiveAction(models.Model):
    _name = 'quality.corrective.action'  # ✅ CORRIGÉ : suppression du préfixe lms_quality
    _description = 'Action corrective'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline asc, create_date desc'

    name = fields.Char(
        string='Référence',
        required=True,
        readonly=True,
        default=lambda self: _('New'),
        copy=False,
        tracking=True  # ✅ AJOUTÉ
    )

    non_conformity_id = fields.Many2one(
        'quality.non_conformity',
        string='Non-conformité',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    description = fields.Text(
        string='Description',
        required=True,
        tracking=True
    )

    objective = fields.Text(
        string='Objectif',
        required=True,
        help='Résultat attendu de l\'action corrective',
        tracking=True
    )

    # Responsable
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        required=True,
        tracking=True,
        default=lambda self: self.env.user  # ✅ AJOUTÉ
    )

    # Planning
    start_date = fields.Date(
        string='Date de début',
        default=fields.Date.context_today,
        tracking=True
    )

    deadline = fields.Date(
        string='Échéance',
        required=True,
        tracking=True
    )

    # Suivi
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('closed', 'Clôturé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True, required=True)

    progress = fields.Integer(
        string='Progression (%)',
        default=0,
        tracking=True
    )

    completion_date = fields.Date(
        string='Date de réalisation',
        readonly=True,  # ✅ AJOUTÉ
        tracking=True
    )

    # Évaluation
    effectiveness = fields.Selection([
        ('not_evaluated', 'Non évalué'),
        ('effective', 'Efficace'),
        ('partially_effective', 'Partiellement efficace'),
        ('not_effective', 'Non efficace'),
    ], string='Efficacité', default='not_evaluated', tracking=True)

    evaluation_notes = fields.Text(
        string='Notes évaluation',
        tracking=True
    )

    # Pièces jointes
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'quality_action_attachment_rel',  # ✅ AJOUTÉ : nom de table explicite
        'action_id',
        'attachment_id',
        string='Pièces jointes'
    )

    # Indicateurs
    is_overdue = fields.Boolean(
        string='En retard',
        compute='_compute_overdue',
        store=True,
        search='_search_is_overdue'  # ✅ AJOUTÉ
    )

    days_overdue = fields.Integer(
        string='Jours de retard',
        compute='_compute_overdue',
        store=True
    )

    # ✅ AJOUTÉ : Champs manquants pour suivi Qualiopi
    action_type = fields.Selection([
        ('corrective', 'Corrective'),
        ('preventive', 'Préventive'),
        ('improvement', 'Amélioration'),
    ], string='Type d\'action', default='corrective', tracking=True)

    resources_needed = fields.Text(
        string='Ressources nécessaires',
        help='Personnel, budget, matériel...',
        tracking=True
    )

    success_criteria = fields.Text(
        string='Critères de réussite',
        help='Comment mesurer l\'efficacité de l\'action',
        tracking=True
    )

    # Méthodes de calcul
    @api.depends('deadline', 'state')
    def _compute_overdue(self):
        today = fields.Date.today()
        for action in self:
            if action.deadline and action.state not in ['closed', 'cancelled', 'done']:
                action.is_overdue = action.deadline < today
                if action.is_overdue:
                    action.days_overdue = (today - action.deadline).days
                else:
                    action.days_overdue = 0
            else:
                action.is_overdue = False
                action.days_overdue = 0

    def _search_is_overdue(self, operator, value):  # ✅ AJOUTÉ
        """Permet de rechercher les actions en retard"""
        today = fields.Date.today()
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [
                ('deadline', '<', today),
                ('state', 'not in', ['closed', 'cancelled', 'done'])
            ]
        else:
            return [
                '|',
                ('deadline', '>=', today),
                ('state', 'in', ['closed', 'cancelled', 'done'])
            ]

    # Contraintes
    @api.constrains('start_date', 'deadline')
    def _check_dates(self):
        for action in self:
            if action.start_date and action.deadline and action.deadline < action.start_date:
                raise ValidationError(
                    _("L'échéance ne peut pas être antérieure à la date de début")
                )

    @api.constrains('progress')
    def _check_progress(self):
        for action in self:
            if action.progress < 0 or action.progress > 100:
                raise ValidationError(
                    _("La progression doit être comprise entre 0 et 100%")
                )

    # ✅ AJOUTÉ : Contrainte cohérence état/progression
    @api.constrains('state', 'progress')
    def _check_state_progress(self):
        for action in self:
            if action.state == 'done' and action.progress < 100:
                raise ValidationError(
                    _("Une action terminée doit avoir une progression de 100%")
                )

    # Séquences
    @api.model_create_multi  # ✅ CORRIGÉ
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('quality.corrective.action') or _('New')

        actions = super(QualityCorrectiveAction, self).create(vals_list)

        # Créer une activité pour le responsable
        for action in actions:
            action.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=action.responsible_user_id.id,
                summary=_('Nouvelle action corrective'),
                note=_('Nouvelle action corrective: %s') % action.description[:100]
            )

        return actions

    # Actions du workflow
    def action_start(self):
        """Démarrer l'action corrective"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Seules les actions en brouillon peuvent être démarrées"))

        self.write({
            'state': 'in_progress',
            'start_date': fields.Date.today()  # ✅ AJOUTÉ : mise à jour date début
        })
        self.message_post(
            body=_('Action corrective démarrée'),
            message_type='notification'
        )

    def action_mark_done(self):
        """Marquer comme terminé"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_("Seules les actions en cours peuvent être marquées comme terminées"))

        # ✅ AJOUTÉ : Vérifier progression
        if self.progress < 100:
            raise UserError(
                _("La progression doit être à 100% avant de marquer l'action comme terminée")
            )

        self.write({
            'state': 'done',
            'completion_date': fields.Date.today(),
            'progress': 100,
        })
        self.message_post(
            body=_('Action corrective terminée'),
            message_type='notification'
        )

        # ✅ AJOUTÉ : Notifier le responsable de la NC
        if self.non_conformity_id:
            self.non_conformity_id.message_post(
                body=_("L'action corrective '%s' a été marquée comme terminée") % self.name,
                message_type='notification'
            )

    def action_close(self):
        """Clôturer l'action après évaluation"""
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("Seules les actions terminées peuvent être clôturées"))

        # ✅ AJOUTÉ : Vérifier évaluation
        if self.effectiveness == 'not_evaluated':
            raise UserError(
                _("Vous devez évaluer l'efficacité de l'action avant de la clôturer")
            )

        self.write({'state': 'closed'})
        self.message_post(
            body=_('Action corrective clôturée - Efficacité: %s') % dict(
                self._fields['effectiveness'].selection
            ).get(self.effectiveness),
            message_type='notification'
        )

    def action_cancel(self):
        """Annuler l'action"""
        self.ensure_one()

        # ✅ AJOUTÉ : Demander confirmation si en cours
        if self.state == 'in_progress' and self.progress > 50:
            raise UserError(
                _("Cette action est déjà à %d%%. Êtes-vous sûr de vouloir l'annuler?") % self.progress
            )

        self.write({'state': 'cancelled'})
        self.message_post(
            body=_('Action corrective annulée'),
            message_type='notification'
        )

    # ✅ AJOUTÉ : Méthode onchange pour échéance
    @api.onchange('non_conformity_id')
    def _onchange_non_conformity(self):
        """Proposer échéance basée sur NC"""
        if self.non_conformity_id and self.non_conformity_id.treatment_deadline:
            # Proposer 7 jours avant échéance NC
            self.deadline = self.non_conformity_id.treatment_deadline - timedelta(days=7)

    # Méthodes CRON
    @api.model
    def _cron_remind_corrective_actions(self):
        """Rappels pour actions correctives proches de l'échéance"""
        today = fields.Date.today()
        reminder_date = today + timedelta(days=7)  # Rappel 7 jours avant

        actions_to_remind = self.search([
            ('state', 'in', ['draft', 'in_progress']),
            ('deadline', '<=', reminder_date),
            ('deadline', '>=', today),
        ])

        for action in actions_to_remind:
            days_remaining = (action.deadline - today).days

            # Vérifier si activité existe déjà
            existing_reminder = self.env['mail.activity'].search([
                ('res_id', '=', action.id),
                ('res_model_id', '=', self.env['ir.model']._get_id('quality.corrective.action')),
                ('user_id', '=', action.responsible_user_id.id),
                ('summary', 'ilike', 'échéance'),
                ('date_deadline', '=', action.deadline),
            ], limit=1)

            if not existing_reminder:
                activity_type = 'mail.mail_activity_data_todo'
                if days_remaining <= 3:
                    activity_type = 'mail.mail_activity_data_warning'

                action.activity_schedule(
                    activity_type,
                    user_id=action.responsible_user_id.id,
                    date_deadline=action.deadline,
                    summary=_('⏰ Échéance proche - Action corrective'),
                    note=_('Il reste %d jour(s) pour terminer cette action corrective') % days_remaining
                )

        _logger.info(f"CRON Actions: {len(actions_to_remind)} rappels envoyés")

    # ✅ AJOUTÉ : Rapport de progression
    def get_progress_report(self):
        """Génère un rapport de progression pour le tableau de bord"""
        self.ensure_one()

        return {
            'name': self.name,
            'description': self.description[:100],
            'progress': self.progress,
            'state': self.state,
            'days_remaining': (self.deadline - fields.Date.today()).days if self.deadline else None,
            'is_overdue': self.is_overdue,
            'effectiveness': self.effectiveness,
        }