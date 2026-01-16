# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MaterialEvaluation(models.Model):
    _name = 'lms_resources_trainers.material_evaluation'
    _description = 'Évaluation des supports pédagogiques'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline_date'

    # Identification
    name = fields.Char(
        string='Référence',
        default=lambda self: _('Nouvelle évaluation'),
        required=True
    )

    material_name = fields.Char(
        string='Nom du support',
        required=True,
        tracking=True
    )

    course_id = fields.Many2one(
        'slide.channel',
        string='Formation associée',
        required=True,
        tracking=True
    )

    material_type = fields.Selection([
        ('presentation', 'Présentation'),
        ('document', 'Document'),
        ('video', 'Vidéo'),
        ('exercise', 'Exercice'),
        ('quiz', 'Quiz'),
        ('other', 'Autre')
    ], string='Type de support', required=True, tracking=True)

    # Évaluation
    evaluator_id = fields.Many2one(
        'res.users',
        string='Évaluateur',
        required=True,
        tracking=True
    )

    evaluation_date = fields.Date(
        string="Date d'évaluation",
        tracking=True
    )

    deadline_date = fields.Date(
        string='Date limite',
        required=True,
        tracking=True
    )

    # Critères d'évaluation
    content_quality = fields.Selection([
        ('1', '1 - Insuffisant'),
        ('2', '2 - À améliorer'),
        ('3', '3 - Satisfaisant'),
        ('4', '4 - Bon'),
        ('5', '5 - Excellent')
    ], string='Qualité du contenu', tracking=True)

    pedagogical_relevance = fields.Selection([
        ('1', '1 - Insuffisant'),
        ('2', '2 - À améliorer'),
        ('3', '3 - Satisfaisant'),
        ('4', '4 - Bon'),
        ('5', '5 - Excellent')
    ], string='Pertinence pédagogique', tracking=True)

    technical_quality = fields.Selection([
        ('1', '1 - Insuffisant'),
        ('2', '2 - À améliorer'),
        ('3', '3 - Satisfaisant'),
        ('4', '4 - Bon'),
        ('5', '5 - Excellent')
    ], string='Qualité technique', tracking=True)

    accessibility = fields.Selection([
        ('1', '1 - Insuffisant'),
        ('2', '2 - À améliorer'),
        ('3', '3 - Satisfaisant'),
        ('4', '4 - Bon'),
        ('5', '5 - Excellent')
    ], string='Accessibilité', tracking=True)

    # Résultats
    overall_score = fields.Float(
        string='Note globale',
        compute='_compute_overall_score',
        store=True,
        digits=(3, 2)
    )

    recommendations = fields.Text(string='Recommandations')

    approval_status = fields.Selection([
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('needs_revision', 'Nécessite révision'),
        ('rejected', 'Rejeté')
    ], string='Statut d\'approbation', default='pending', tracking=True)

    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', tracking=True)

    completion_date = fields.Date(string='Date de complétion')

    # Documents
    material_file = fields.Many2one(
        'ir.attachment',
        string='Fichier du support'
    )

    evaluation_report = fields.Many2one(
        'ir.attachment',
        string='Rapport d\'évaluation'
    )

    # Statistiques
    evaluation_duration = fields.Float(
        string='Durée d\'évaluation (heures)',
        tracking=True
    )

    revision_count = fields.Integer(
        string='Nombre de révisions',
        default=0,
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    # Méthodes de calcul
    @api.depends('content_quality', 'pedagogical_relevance', 'technical_quality', 'accessibility')
    def _compute_overall_score(self):
        for evaluation in self:
            scores = []
            if evaluation.content_quality:
                scores.append(int(evaluation.content_quality))
            if evaluation.pedagogical_relevance:
                scores.append(int(evaluation.pedagogical_relevance))
            if evaluation.technical_quality:
                scores.append(int(evaluation.technical_quality))
            if evaluation.accessibility:
                scores.append(int(evaluation.accessibility))

            if scores:
                evaluation.overall_score = sum(scores) / len(scores)
            else:
                evaluation.overall_score = 0.0

    # Contraintes
    @api.constrains('deadline_date')
    def _check_deadline(self):
        for evaluation in self:
            if evaluation.deadline_date and evaluation.deadline_date < fields.Date.today():
                raise ValidationError(_('La date limite ne peut pas être dans le passé.'))

    # Méthodes d'action
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nouvelle évaluation')) == _('Nouvelle évaluation'):
            vals['name'] = self.env['ir.sequence'].next_by_code('lms.material.evaluation') or _('Nouvelle évaluation')
        return super().create(vals)

    def action_start_evaluation(self):
        """Démarrer l'évaluation"""
        for evaluation in self:
            evaluation.write({
                'state': 'in_progress',
                'evaluation_date': fields.Date.today()
            })

            # Envoyer notification à l'évaluateur
            evaluation._send_evaluation_notification()

    def action_complete_evaluation(self):
        """Compléter l'évaluation"""
        for evaluation in self:
            required_fields = ['content_quality', 'pedagogical_relevance', 'recommendations']
            missing_fields = [field for field in required_fields if not getattr(evaluation, field)]

            if missing_fields:
                raise ValidationError(_(
                    f'Veuillez remplir les champs suivants: {", ".join(missing_fields)}'
                ))

            evaluation.write({
                'state': 'completed',
                'completion_date': fields.Date.today(),
                'approval_status': 'pending'
            })

    def action_approve(self):
        """Approuver l'évaluation"""
        self.write({'approval_status': 'approved'})

    def action_request_revision(self):
        """Demander une révision"""
        for evaluation in self:
            evaluation.write({
                'approval_status': 'needs_revision',
                'revision_count': evaluation.revision_count + 1
            })

            # Créer une activité pour l'évaluateur
            evaluation.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=fields.Date.today() + timedelta(days=7),
                user_id=evaluation.evaluator_id.id,
                summary='Révision demandée pour évaluation de support',
                note=f'Veuillez réviser l\'évaluation du support "{evaluation.material_name}"'
            )

    def _send_evaluation_notification(self):
        """Envoyer la notification d'évaluation"""
        template = self.env.ref('lms_resources_trainers.mail_template_material_evaluation')
        for evaluation in self:
            template.send_mail(evaluation.id, force_send=True)

    # Méthode cron pour vérifier les évaluations en retard
    @api.model
    def _cron_check_overdue_evaluations(self):
        """Vérifier les évaluations en retard"""
        today = fields.Date.today()
        overdue_evaluations = self.search([
            ('state', '=', 'in_progress'),
            ('deadline_date', '<', today)
        ])

        for evaluation in overdue_evaluations:
            # Créer une activité pour rappel
            evaluation.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=today,
                user_id=evaluation.evaluator_id.id,
                summary=f'Évaluation en retard: {evaluation.material_name}',
                note=f'L\'évaluation du support "{evaluation.material_name}" est en retard depuis le {evaluation.deadline_date}'
            )