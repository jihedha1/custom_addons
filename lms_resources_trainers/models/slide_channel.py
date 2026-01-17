# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SlideChannelResources(models.Model):
    """Extension de slide.channel pour la gestion des ressources"""
    _inherit = 'slide.channel'

    # =====================
    # RESSOURCES NÉCESSAIRES
    # =====================
    required_resources_ids = fields.Many2many(
        'lms_resources_trainers.resource_management',
        'channel_resource_rel',
        'channel_id',
        'resource_id',
        string='Ressources nécessaires',
        help="Salles et équipements requis pour cette formation"
    )

    required_room_capacity = fields.Integer(
        string='Capacité minimale requise',
        help="Nombre de places minimum pour la salle"
    )

    required_equipment_ids = fields.Many2many(
        'lms_resources_trainers.resource_equipment',
        'channel_equipment_rel',
        'channel_id',
        'equipment_id',
        string='Équipements nécessaires',
        help="Équipements techniques requis"
    )

    # =====================
    # SUPPORTS PÉDAGOGIQUES
    # =====================
    material_evaluation_ids = fields.One2many(
        'lms_resources_trainers.material_evaluation',
        'course_id',
        string='Évaluations des supports'
    )

    material_count = fields.Integer(
        string='Nombre de supports évalués',
        compute='_compute_material_stats'
    )

    average_material_score = fields.Float(
        string='Note moyenne des supports',
        digits=(3, 2),
        compute='_compute_material_stats'
    )

    @api.depends('material_evaluation_ids', 'material_evaluation_ids.overall_score')
    def _compute_material_stats(self):
        """Calcule les statistiques des évaluations de supports"""
        for channel in self:
            evals = channel.material_evaluation_ids.filtered(lambda e: e.state == 'completed')
            channel.material_count = len(evals)

            if evals:
                scores = [e.overall_score for e in evals if e.overall_score]
                channel.average_material_score = sum(scores) / len(scores) if scores else 0.0
            else:
                channel.average_material_score = 0.0

    # =====================
    # RÉSERVATIONS LIÉES
    # =====================
    resource_booking_ids = fields.One2many(
        'lms_resources_trainers.resource_booking',
        'course_id',
        string='Réservations de ressources'
    )

    booking_count = fields.Integer(
        string='Nombre de réservations',
        compute='_compute_booking_count'
    )

    @api.depends('resource_booking_ids')
    def _compute_booking_count(self):
        for channel in self:
            channel.booking_count = len(channel.resource_booking_ids)

    # =====================
    # ACTIONS
    # =====================
    def action_view_materials(self):
        """Ouvre les évaluations de supports"""
        self.ensure_one()
        return {
            'name': _('Supports pédagogiques - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'lms_resources_trainers.material_evaluation',
            'view_mode': 'tree,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id}
        }

    def action_view_bookings(self):
        """Ouvre les réservations de ressources"""
        self.ensure_one()
        return {
            'name': _('Réservations - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'lms_resources_trainers.resource_booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id}
        }

    def action_check_resources_availability(self):
        """Vérifie la disponibilité des ressources requises"""
        self.ensure_one()

        if not self.required_resources_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Aucune ressource requise'),
                    'message': _('Cette formation ne nécessite pas de ressources spécifiques.'),
                    'type': 'info',
                }
            }

        # Logique de vérification de disponibilité
        unavailable = []
        for resource in self.required_resources_ids:
            if resource.state != 'available':
                unavailable.append(resource.name)

        if unavailable:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Ressources indisponibles'),
                    'message': _('Les ressources suivantes ne sont pas disponibles : %s') % ', '.join(unavailable),
                    'type': 'warning',
                }
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ressources disponibles'),
                'message': _('Toutes les ressources requises sont disponibles.'),
                'type': 'success',
            }
        }

    @api.constrains('required_room_capacity')
    def _check_room_capacity(self):
        """Vérifie que la capacité requise est cohérente"""
        for channel in self:
            if channel.required_room_capacity < 0:
                raise ValidationError(_('La capacité minimale ne peut pas être négative.'))