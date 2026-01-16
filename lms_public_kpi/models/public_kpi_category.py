# custom_addons/lms_public_kpi/models/public_kpi_category.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PublicKPICategory(models.Model):
    _name = 'public.kpi.category'  # ✅ CORRECTION
    _description = 'Catégorie d\'indicateur public'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nom',
        required=True,
        translate=True
    )

    code = fields.Char(
        string='Code',
        required=True,
        help='Code interne pour référencer la catégorie'
    )

    description = fields.Text(
        string='Description',
        translate=True
    )

    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help='Ordre d\'affichage'
    )

    active = fields.Boolean(
        string='Actif',
        default=True
    )

    # ✅ AJOUT couleur pour affichage
    color = fields.Integer(
        string='Couleur',
        default=0
    )

    # Indicateurs
    kpi_version_ids = fields.One2many(
        'public.kpi.version',
        'category_id',
        string='Indicateurs'
    )

    kpi_count = fields.Integer(
        string='Nombre d\'indicateurs',
        compute='_compute_kpi_count'
    )

    @api.depends('kpi_version_ids')
    def _compute_kpi_count(self):
        for category in self:
            category.kpi_count = len(category.kpi_version_ids)

    # Contraintes
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code de catégorie doit être unique'),
    ]