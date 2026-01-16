# custom_addons/lms_public_kpi/models/public_kpi_version.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class PublicKPIVersion(models.Model):
    _name = 'public.kpi.version'  # ✅ CORRECTION
    _description = 'Version d\'un indicateur public'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # ✅ AJOUT mail.activity.mixin
    _order = 'sequence, id'

    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True  # ✅ CORRECTION: tracking au lieu de track_visibility
    )

    snapshot_id = fields.Many2one(
        'public.kpi.snapshot',
        string='Snapshot',
        required=True,
        ondelete='cascade',
        tracking=True
    )

    # Catégorie
    category_id = fields.Many2one(
        'public.kpi.category',
        string='Catégorie',
        required=True,
        tracking=True
    )

    # Valeur
    value = fields.Float(
        string='Valeur',
        digits=(16, 2),
        tracking=True
    )

    unit = fields.Char(
        string='Unité',
        required=True,
        default='%',
        tracking=True
    )

    # Métadonnées
    description = fields.Text(
        string='Description',
        help='Description publique de l\'indicateur',
        tracking=True
    )

    calculation_method = fields.Selection([
        ('manual', 'Saisie manuelle'),
        ('auto_average', 'Moyenne automatique'),
        ('auto_sum', 'Somme automatique'),
        ('auto_rate', 'Taux automatique'),
        ('external', 'Source externe'),
    ], string='Méthode de calcul', default='manual', tracking=True)

    data_source_model = fields.Char(
        string='Modèle source',
        help='Modèle Odoo utilisé pour le calcul automatique',
        tracking=True
    )

    data_source_domain = fields.Char(
        string='Domaine source',
        help='Domaine pour filtrer les données source',
        tracking=True
    )

    # Statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
        ('archived', 'Archivé'),
    ], string='Statut', default='draft', tracking=True)

    # Affichage
    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help='Ordre d\'affichage dans les listes'
    )

    display_color = fields.Selection([
        ('primary', 'Bleu'),
        ('secondary', 'Gris'),
        ('success', 'Vert'),
        ('danger', 'Rouge'),
        ('warning', 'Orange'),
        ('info', 'Cyan'),
        ('light', 'Clair'),
        ('dark', 'Foncé'),
    ], string='Couleur d\'affichage', default='primary')

    # Évolution
    previous_value = fields.Float(
        string='Valeur précédente',
        digits=(16, 2),
        tracking=True
    )

    evolution_rate = fields.Float(
        string='Taux d\'évolution (%)',
        compute='_compute_evolution',
        store=True,
        digits=(5, 2)
    )

    evolution_direction = fields.Selection([
        ('up', '↑ Hausse'),
        ('down', '↓ Baisse'),
        ('stable', '→ Stable'),
    ], string='Direction', compute='_compute_evolution', store=True)

    # Preuves
    evidence_notes = fields.Text(
        string='Notes de preuve',
        help='Explication de la source et du calcul'
    )

    evidence_attachment_ids = fields.Many2many(
        'ir.attachment',
        'kpi_version_attachment_rel',  # ✅ AJOUT nom relation explicite
        'kpi_version_id',
        'attachment_id',
        string='Preuves justificatives'
    )

    # Dates
    last_calculation_date = fields.Datetime(
        string='Dernier calcul',
        tracking=True
    )

    @api.depends('value', 'previous_value')
    def _compute_evolution(self):
        for kpi in self:
            if kpi.previous_value and kpi.previous_value != 0:
                evolution = ((kpi.value - kpi.previous_value) / abs(kpi.previous_value)) * 100
                kpi.evolution_rate = evolution

                if evolution > 1.0:
                    kpi.evolution_direction = 'up'
                elif evolution < -1.0:
                    kpi.evolution_direction = 'down'
                else:
                    kpi.evolution_direction = 'stable'
            else:
                kpi.evolution_rate = 0.0
                kpi.evolution_direction = 'stable'

    # Contraintes
    @api.constrains('value')
    def _check_value(self):
        for kpi in self:
            if kpi.value < 0:
                raise ValidationError(_("La valeur ne peut pas être négative"))

    # Actions
    def action_calculate(self):
        """Calculer la valeur automatiquement"""
        for kpi in self:
            if kpi.calculation_method != 'manual':
                try:
                    # Implémenter le calcul selon la méthode
                    if kpi.calculation_method == 'auto_average':
                        kpi.value = self._calculate_average(kpi)
                    elif kpi.calculation_method == 'auto_sum':
                        kpi.value = self._calculate_sum(kpi)
                    elif kpi.calculation_method == 'auto_rate':
                        kpi.value = self._calculate_rate(kpi)

                    kpi.last_calculation_date = fields.Datetime.now()
                    kpi.evidence_notes = _("Calculé automatiquement le %s") % kpi.last_calculation_date

                except Exception as e:
                    raise UserError(_("Erreur lors du calcul: %s") % str(e))

    def _calculate_average(self, kpi):
        """Calculer une moyenne - À IMPLÉMENTER selon besoins"""
        # ✅ TODO: Implémenter calcul réel depuis survey ou eLearning
        return 75.5

    def _calculate_sum(self, kpi):
        """Calculer une somme - À IMPLÉMENTER selon besoins"""
        # ✅ TODO: Implémenter calcul réel
        return 150

    def _calculate_rate(self, kpi):
        """Calculer un taux - À IMPLÉMENTER selon besoins"""
        # ✅ TODO: Implémenter calcul réel
        # Exemple: taux de réussite
        # Model = self.env[kpi.data_source_model]
        # domain = eval(kpi.data_source_domain)
        # total = Model.search_count(domain)
        # success = Model.search_count(domain + [('state', '=', 'done')])
        # return (success / total * 100) if total > 0 else 0
        return 85.2

    def action_publish(self):
        """Publier l'indicateur"""
        self.write({
            'state': 'published',
            'last_calculation_date': fields.Datetime.now(),
        })
        self.message_post(body=_('Indicateur publié'))  # ✅ AJOUT message

    def action_archive(self):
        """Archiver l'indicateur"""
        self.write({'state': 'archived'})
        self.message_post(body=_('Indicateur archivé'))  # ✅ AJOUT message