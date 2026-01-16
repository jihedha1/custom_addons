# custom_addons/lms_public_info/models/slide_channel.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class SlideChannelQualiopi(models.Model):
    _name = 'slide.channel'
    _inherit = ['slide.channel', 'mail.thread']

    # =====================
    # CHAMPS QUALIOPI OBLIGATOIRES
    # =====================

    # CORRECTION : Deux champs pour objectifs (compatibilité)
    learning_objectives = fields.Html(
        string='Objectifs pédagogiques (Qualiopi)',
        tracking=False,
        help='Objectifs d\'apprentissage mesurables et précis'
    )

    # Pour compatibilité avec l'ancien champ
    pedagogical_objectives = fields.Html(
        string='Objectifs pédagogiques',
        compute='_compute_pedagogical_objectives',
        inverse='_inverse_pedagogical_objectives',
        store=True,
        help='Alias pour learning_objectives'
    )

    @api.depends('learning_objectives')
    def _compute_pedagogical_objectives(self):
        for channel in self:
            channel.pedagogical_objectives = channel.learning_objectives

    def _inverse_pedagogical_objectives(self):
        for channel in self:
            channel.learning_objectives = channel.pedagogical_objectives

    prerequisites = fields.Html(
        string='Prérequis',
        tracking=False,
        help='Connaissances, compétences ou équipements nécessaires'
    )

    target_audience = fields.Html(
        string='Public cible',
        tracking=False,
        help='Description du public visé par la formation'
    )

    # Durée et planning
    total_duration_hours = fields.Float(
        string='Durée totale (heures)',
        tracking=True,
        help='Durée totale de la formation en heures'
    )

    duration_days = fields.Integer(
        string='Durée (jours)',
        compute='_compute_duration_days',
        store=True,
        help='Durée calculée en jours (à partir des heures)'
    )

    @api.depends('total_duration_hours')
    def _compute_duration_days(self):
        """Calcule la durée en jours à partir des heures"""
        for channel in self:
            if channel.total_duration_hours:
                channel.duration_days = int(channel.total_duration_hours / 7)  # 7h = 1 jour
            else:
                channel.duration_days = 0

    duration_details = fields.Html(
        string='Détails de la durée',
        tracking=False,
        help='Répartition du temps (présentiel, distanciel, travail personnel)'
    )

    # Tarification
    price = fields.Float(
        string='Prix public (€ HT)',
        digits=(12, 2),
        tracking=True
    )

    price_details = fields.Text(
        string='Détails tarifaires',
        tracking=True,
        help='Modalités de paiement, financements possibles, etc.'
    )

    # =====================
    # MODALITÉS
    # =====================

    training_modality = fields.Selection(
        selection=[
            ('presentiel', 'Présentiel'),
            ('distanciel', 'Distanciel'),
            ('hybride', 'Hybride (Blended Learning)'),
            ('classroom', 'Présentiel (Anglais)'),
            ('remote', 'Distanciel (Anglais)'),
            ('blended', 'Mixte (Anglais)'),
            ('self_paced', 'Auto-formation'),
        ],
        string='Modalité',
        default='distanciel',
        tracking=True,
        required=False
    )

    modality_details = fields.Html(
        string='Détails des modalités',
        tracking=False,
        help='Description détaillée des modalités de formation'
    )

    # Niveau
    training_level = fields.Selection([
        ('initiation', 'Initiation'),
        ('intermediaire', 'Intermédiaire'),
        ('avance', 'Avancé'),
        ('expert', 'Expert')
    ], string="Niveau")

    # Accessibilité
    accessibility_info = fields.Html(
        string='Informations accessibilité',
        tracking=False ,
        help='Aménagements pour personnes en situation de handicap'
    )

    # =====================
    # CERTIFICATION - CORRECTION
    # =====================

    delivers_certificate = fields.Boolean(
        string='Délivre une attestation',
        default=True,
        tracking=True
    )

    certificate_name = fields.Char(
        string="Nom de l'attestation",
        default='Attestation de formation',
        tracking=True
    )

    # =====================
    # COMPÉTENCES FORMATEUR
    # =====================

    trainer_competency_ids = fields.Many2many(
        'lms_public_info.trainer_competency',
        string='Compétences requises',
        relation='slide_channel_trainer_competency_rel',
        column1='channel_id',
        column2='competency_id'
    )

    # =====================
    # FORMATEUR ASSIGNÉ
    # =====================

    trainer_partner_id = fields.Many2one(
        'res.partner',
        string='Formateur assigné',
        domain=[('is_trainer', '=', True)],
        tracking=True
    )

    # =====================
    # FILTRES PUBLICATION
    # =====================

    difficulty_level = fields.Selection(
        selection=[
            ('beginner', 'Débutant'),
            ('intermediate', 'Intermédiaire'),
            ('advanced', 'Avancé'),
            ('expert', 'Expert'),
        ],
        string='Niveau de difficulté',
        tracking=True
    )
    training_type = fields.Selection(
        selection=[
            ('initial', 'Formation initiale'),
            ('continuous', 'Formation continue'),
            ('apprenticeship', 'Alternance'),
            ('vae', 'VAE'),
            ('other', 'Autre'),
        ],
        string='Type de formation',
        default='continuous',
        tracking=True
    )

    # =====================
    # VALIDATION PUBLICATION
    # =====================

    publication_ready = fields.Boolean(
        string='Prêt pour publication',
        compute='_compute_publication_ready',
        store=False,
        tracking=True
    )

    missing_fields = fields.Text(
        string='Champs manquants',
        compute='_compute_publication_ready',
        store=False
    )

    # =====================
    # RENDEZ-VOUS
    # =====================

    appointment_available = fields.Boolean(
        string='RDV disponibles',
        default=False,
        tracking=True
    )

    # =====================
    # MÉTHODES DE CALCUL
    # =====================

    @api.depends(
        'learning_objectives', 'prerequisites', 'target_audience',
        'total_duration_hours', 'price', 'training_modality',
        'accessibility_info', 'trainer_competency_ids'
    )
    def _compute_publication_ready(self):
        """Vérifie si tous les champs obligatoires sont remplis"""
        for channel in self:
            missing = []

            # Liste des champs obligatoires pour publication
            required_fields = [
                ('learning_objectives', 'Objectifs pédagogiques'),
                ('prerequisites', 'Prérequis'),
                ('target_audience', 'Public cible'),
                ('total_duration_hours', 'Durée totale'),
                ('price', 'Prix'),
                ('training_modality', 'Modalité de formation'),
                ('accessibility_info', 'Informations accessibilité'),
            ]

            for field_name, field_label in required_fields:
                field_value = getattr(channel, field_name)
                if not field_value:
                    missing.append(field_label)
                elif isinstance(field_value, (int, float)) and field_value <= 0:
                    missing.append(field_label)

            # Vérifier au moins une compétence formateur
            if not channel.trainer_competency_ids:
                missing.append('Compétences formateur')

            channel.missing_fields = ', '.join(missing) if missing else ''
            channel.publication_ready = len(missing) == 0

    # =====================
    # CONTRAINTES
    # =====================

    @api.constrains('total_duration_hours')
    def _check_duration(self):
        for channel in self:
            if channel.total_duration_hours < 0:
                raise ValidationError(_("La durée ne peut pas être négative"))

    @api.constrains('price')
    def _check_price(self):
        for channel in self:
            if channel.price < 0:
                raise ValidationError(_("Le prix ne peut pas être négatif"))

    # =====================
    # SURCHARGES
    # =====================

    def write(self, vals):
        """Empêche la publication si champs manquants"""
        if 'is_published' in vals and vals['is_published']:
            for channel in self:
                if not channel.publication_ready:
                    raise UserError(_(
                        "Impossible de publier la formation '%s'. "
                        "Champs manquants : %s"
                    ) % (channel.name, channel.missing_fields))

        return super(SlideChannelQualiopi, self).write(vals)

    # =====================
    # ACTIONS
    # =====================

    def action_validate_publication(self):
        """Valider la publication"""
        for channel in self:
            if channel.publication_ready:
                channel.write({'is_published': True})
                channel.message_post(body=_('Formation publiée avec succès'))
            else:
                raise UserError(_(
                    "Impossible de publier : %s"
                ) % channel.missing_fields)

    def action_create_appointment(self):
        """Créer un type de rendez-vous pour cette formation"""
        self.ensure_one()

        if not self.appointment_type_id:
            appointment_type = self.env['calendar.appointment.type'].create({
                'name': _('Information - %s') % self.name,
                'category': 'custom',
                'duration': 30,
                'assign_method': 'time_auto_assign',
            })
            self.appointment_type_id = appointment_type

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.appointment.type',
            'res_id': self.appointment_type_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_competencies(self):
        """Voir les compétences associées"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Compétences - {self.name}',
            'res_model': 'lms_public_info.trainer_competency',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.trainer_competency_ids.ids)],
            'context': {'create': False}
        }
