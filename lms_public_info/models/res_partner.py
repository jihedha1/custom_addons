# custom_addons/lms_public_info/models/res_partner.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, datetime, timedelta


class ResPartnerTrainer(models.Model):
    _inherit = 'res.partner'

    # =====================
    # STATUT FORMATEUR
    # =====================

    is_trainer = fields.Boolean(
        string='Est formateur',
        default=False,
        help="Cocher si ce partenaire est un formateur"
    )

    trainer_type = fields.Selection([
        ('internal', 'Interne'),
        ('external', 'Externe'),
        ('freelance', 'Indépendant'),
    ], string='Type de formateur', default='external')

    # =====================
    # COMPÉTENCES
    # =====================

    competency_ids = fields.Many2many(
        'lms_public_info.trainer_competency',
        relation='trainer_competency_partner_rel',  # MÊME TABLE !
        column1='partner_id',
        column2='competency_id',  # Inversé par rapport à l'autre modèle
        string='Compétences'
    )

    # =====================
    # INFORMATIONS PROFESSIONNELLES
    # =====================

    diploma = fields.Text(
        string='Diplômes',
        help='Diplômes obtenus'
    )

    certifications = fields.Text(
        string='Certifications',
        help='Certifications professionnelles'
    )

    professional_experience = fields.Text(
        string='Expérience professionnelle',
        help='Expérience dans le domaine de formation'
    )

    training_experience = fields.Text(
        string='Expérience pédagogique',
        help='Expérience en tant que formateur'
    )

    # =====================
    # DOCUMENTS - SIMPLIFIÉS (sans dépendance à documents)
    # =====================

    cv_attachment = fields.Binary(
        string='CV',
        attachment=True
    )

    cv_filename = fields.Char(
        string='Nom du fichier CV'
    )

    # SUPPRIMER les champs Many2many problématiques pour l'instant
    # diploma_attachment_ids = fields.Many2many(...)
    # certification_attachment_ids = fields.Many2many(...)

    # =====================
    # DISPONIBILITÉS - SIMPLIFIÉ
    # =====================

    # SUPPRIMER le One2many vers un modèle qui n'existe pas
    # availability_ids = fields.One2many('trainer.availability', 'partner_id', string='Disponibilités')

    # À la place, ajouter un champ texte simple
    availability_notes = fields.Text(
        string='Notes de disponibilité',
        help='Disponibilités et contraintes horaires'
    )

    # =====================
    # HABILITATIONS - SIMPLIFIÉES
    # =====================

    habilitation_name = fields.Char(
        string='Nom de l\'habilitation'
    )

    habilitation_date = fields.Date(
        string='Date d\'habilitation'
    )

    habilitation_expiry_date = fields.Date(
        string='Date d\'expiration'
    )

    # =====================
    # FORMATIONS ANIMÉES
    # =====================

    trained_channel_ids = fields.Many2many(
        'slide.channel',
        'partner_trained_channel_rel',
        'partner_id',
        'channel_id',
        string='Formations animées',
        compute='_compute_trained_channels',
        store=False
    )

    trained_channel_count = fields.Integer(
        string='Nombre de formations',
        compute='_compute_trained_channels',
        store=False
    )

    last_activity_date = fields.Date(
        string='Dernière activité',
        default=fields.Date.today
    )

    # =====================
    # CALCULS ET STATUTS
    # =====================

    habilitation_status = fields.Selection([
        ('valid', 'Valide'),
        ('expiring', 'Expire bientôt'),
        ('expired', 'Expirée'),
        ('none', 'Aucune'),
    ], string='Statut habilitation', compute='_compute_habilitation_status', store=True)

    days_to_expiry = fields.Integer(
        string='Jours avant expiration',
        compute='_compute_habilitation_status',
        store=True
    )

    inactive_months = fields.Integer(
        string='Mois d\'inactivité',
        compute='_compute_inactive_months',
        store=True
    )

    # =====================
    # MÉTHODES DE CALCUL
    # =====================

    @api.depends('is_trainer', 'competency_ids')
    def _compute_trained_channels(self):
        """Calcule les formations où le formateur est compétent"""
        for partner in self:
            if partner.is_trainer and partner.competency_ids:
                channels = self.env['slide.channel'].search([
                    ('trainer_competency_ids', 'in', partner.competency_ids.ids)
                ])
                partner.trained_channel_ids = channels
                partner.trained_channel_count = len(channels)
            else:
                partner.trained_channel_ids = False
                partner.trained_channel_count = 0

    @api.depends('habilitation_expiry_date')
    def _compute_habilitation_status(self):
        """Calcule le statut de l'habilitation"""
        today = date.today()
        for partner in self:
            if not partner.habilitation_expiry_date:
                partner.habilitation_status = 'none'
                partner.days_to_expiry = 0
            else:
                days = (partner.habilitation_expiry_date - today).days
                partner.days_to_expiry = days

                if days < 0:
                    partner.habilitation_status = 'expired'
                elif days <= 30:
                    partner.habilitation_status = 'expiring'
                else:
                    partner.habilitation_status = 'valid'

    @api.depends('last_activity_date')
    def _compute_inactive_months(self):
        """Calcule les mois d'inactivité"""
        today = date.today()
        for partner in self:
            if partner.last_activity_date:
                delta = today - partner.last_activity_date
                partner.inactive_months = delta.days // 30
            else:
                partner.inactive_months = 0

    # =====================
    # CONTRAINTES
    # =====================

    @api.constrains('is_trainer', 'competency_ids')
    def _check_trainer_competencies(self):
        """Vérifie qu'un formateur a au moins une compétence"""
        for partner in self:
            if partner.is_trainer and not partner.competency_ids:
                raise ValidationError(_(
                    "Un formateur doit avoir au moins une compétence."
                ))

    @api.constrains('habilitation_date', 'habilitation_expiry_date')
    def _check_habilitation_dates(self):
        """Vérifie que la date d'expiration est après la date d'habilitation"""
        for partner in self:
            if (partner.habilitation_date and partner.habilitation_expiry_date and
                    partner.habilitation_expiry_date <= partner.habilitation_date):
                raise ValidationError(_(
                    "La date d'expiration doit être postérieure à la date d'habilitation."
                ))

    # =====================
    # ACTIONS
    # =====================

    def action_check_expiry(self):
        """Vérifie les expirations et crée des activités"""
        expiring = self.search([
            ('habilitation_status', '=', 'expiring'),
            ('is_trainer', '=', True),
        ])

        for trainer in expiring:
            # Créer une activité si l'utilisateur a un compte
            if trainer.user_ids:
                trainer.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=trainer.user_ids[0].id,
                    summary=_('Habilitation à renouveler'),
                    note=_('Votre habilitation expire dans {days} jours').format(
                        days=trainer.days_to_expiry)
                )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vérification terminée'),
                'message': _('{count} formateur(s) avec habilitation expirant bientôt').format(
                    count=len(expiring)),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_mark_activity(self):
        """Marquer une activité pour aujourd'hui"""
        self.write({
            'last_activity_date': fields.Date.today()
        })

    def action_cleanup_inactive(self):
        """Nettoyer les formateurs inactifs depuis plus de 3 mois"""
        threshold = date.today() - timedelta(days=90)  # 3 mois
        inactive = self.search([
            ('is_trainer', '=', True),
            ('last_activity_date', '<', threshold),
            ('inactive_months', '>=', 3),
        ])

        cleaned_count = 0
        for trainer in inactive:
            # Marquer comme non formateur
            trainer.write({
                'is_trainer': False,
                'competency_ids': [(5, 0, 0)],  # Retirer toutes les compétences
            })
            cleaned_count += 1

            # Log l'action
            trainer.message_post(
                body=_('Formateur désactivé après {months} mois d\'inactivité').format(
                    months=trainer.inactive_months)
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Nettoyage terminé'),
                'message': _('{count} formateur(s) inactif(s) ont été nettoyés').format(
                    count=cleaned_count),
                'type': 'success',
                'sticky': False,
            }
        }

    # =====================
    # CRON JOBS
    # =====================

    def _cron_check_expiring_habilitation(self):
        """Cron job pour vérifier les habilitations expirant bientôt"""
        return self.action_check_expiry()

    def _cron_cleanup_inactive_trainers(self):
        """Cron job pour nettoyer les formateurs inactifs"""
        return self.action_cleanup_inactive()

    # =====================
    # SURCHARGES
    # =====================

    def write(self, vals):
        """Surcharge pour mettre à jour la date d'activité"""
        if 'is_trainer' in vals and vals['is_trainer']:
            vals['last_activity_date'] = fields.Date.today()
        return super(ResPartnerTrainer, self).write(vals)