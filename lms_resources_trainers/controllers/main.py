# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class ResourcesController(http.Controller):

    @http.route('/lms/trainers', type='http', auth='public', website=True)
    def trainers_list(self, **kwargs):
        """Page publique des formateurs (compétences seulement)"""
        trainers = request.env['lms_resources_trainers.trainer_profile'].sudo().search([
            ('state', '=', 'active')
        ])

        return request.render('lms_resources_trainers.trainers_public_list', {
            'trainers': trainers,
        })

    @http.route('/lms/trainer/<int:trainer_id>', type='http', auth='public', website=True)
    def trainer_details(self, trainer_id, **kwargs):
        """Détails publics d'un formateur (compétences seulement)"""
        trainer = request.env['lms_resources_trainers.trainer_profile'].sudo().browse(trainer_id)

        return request.render('lms_resources_trainers.trainer_public_details', {
            'trainer': trainer,
        })

    @http.route('/lms/resources/booking', type='http', auth='user', website=True)
    def resource_booking_form(self, **kwargs):
        """Formulaire de réservation de ressources en ligne"""
        resources = request.env['lms_resources_trainers.resource_management'].sudo().search([
            ('available_for_booking', '=', True)
        ])

        return request.render('lms_resources_trainers.resource_booking_form', {
            'resources': resources,
        })