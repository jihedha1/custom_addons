# /formevo/controllers/main.py

import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError

# On importe le contrôleur natif pour pouvoir l'hériter proprement
from odoo.addons.website_slides.controllers.main import WebsiteSlides

_logger = logging.getLogger(__name__)


class YonnElearningController(WebsiteSlides):
    """
    Ce contrôleur hérite du contrôleur natif de website_slides pour y ajouter
    notre logique de tracking et nos nouvelles pages (dashboards).
    """

    # =====================================================
    #  1. TRACKING DU TEMPS (MÉTHODE CÔTÉ SERVEUR)
    # =====================================================

    def _track_time_spent(self):
        """
        Logique de suivi du temps appelée à chaque changement de page.
        Cette méthode est plus robuste que le tracking 100% JS.
        """
        last_slide_id = request.session.get('tracking_slide_id')
        start_time_ts = request.session.get('tracking_start_time')
        user = request.env.user

        # On ne fait rien si l'utilisateur n'est pas connecté ou si c'est sa première page
        if not user.partner_id or not last_slide_id or not start_time_ts:
            return

        try:
            start_time = datetime.fromtimestamp(start_time_ts)
            time_spent = (datetime.now() - start_time).total_seconds()

            # On ignore les sessions trop courtes (< 5s) ou trop longues (> 1h)
            if 5 < time_spent < 3600:
                slide_partner = request.env['slide.slide.partner'].search([
                    ('slide_id', '=', last_slide_id),
                    ('partner_id', '=', user.partner_id.id)
                ], limit=1)

                if slide_partner:
                    slide_partner.sudo().add_time_spent(int(time_spent))
                    _logger.info(
                        f"Yonn Tracking: {int(time_spent)}s ajoutées au slide {last_slide_id} pour {user.name}")

        except Exception as e:
            _logger.warning(f"Yonn Tracking: Impossible de tracker le temps pour le slide {last_slide_id}. Erreur: {e}")

        # On nettoie la session pour éviter de recompter
        request.session.pop('tracking_slide_id', None)
        request.session.pop('tracking_start_time', None)

    # On surcharge la méthode qui affiche un chapitre pour y intégrer notre logique
    @http.route()
    def slide_view(self, slide, **kwargs):
        # D'abord, on exécute notre logique de tracking pour la page précédente
        self._track_time_spent()

        # Ensuite, on démarre le tracking pour la page actuelle
        if request.env.user.partner_id:
            request.session['tracking_slide_id'] = slide.id
            request.session['tracking_start_time'] = datetime.now().timestamp()

        # Enfin, on appelle la méthode originale pour qu'Odoo affiche la page
        response = super(YonnElearningController, self).slide_view(slide, **kwargs)

        return response

    def _can_access_dashboard(self, user, course):
        """Vérifie si l'utilisateur peut accéder au dashboard du cours."""
        if user.has_group('formevo.group_yonn_elearning_director'):
            return True
        if user.has_group('formevo.group_yonn_elearning_teacher'):
            return course.user_id.id == user.id
        return False

    @http.route('/yonn/course/<int:course_id>/dashboard', type='http', auth='user', website=True)
    def course_dashboard(self, course_id, **kwargs):
        """Dashboard de progression pour enseignants et directeurs."""
        try:
            course = request.env['slide.channel'].browse(course_id).exists()
            if not course or not self._can_access_dashboard(request.env.user, course):
                raise AccessError("Vous n'avez pas les droits pour accéder à ce tableau de bord.")

            # On utilise le modèle 'yonn.course.progress' pour obtenir les données, c'est plus propre
            progress_records = request.env['yonn.course.progress'].search([('course_id', '=', course.id)])

            # On ne garde que les apprenants
            student_progress = progress_records.filtered(
                lambda p: p.partner_id.user_ids and p.partner_id.user_ids.has_group(
                    'formevo.group_yonn_elearning_student')
            )

            summary = {
                'total_students': len(student_progress),
                'total_slides': course.total_slides,
                'avg_completion': (sum(student_progress.mapped('completion_percentage')) / len(
                    student_progress)) if student_progress else 0,
            }

            return request.render('formevo.course_dashboard_template', {
                'course': course,
                'student_progress_list': student_progress,  # On envoie la liste des records
                'summary': summary,
                'page_name': 'course_dashboard'
            })
        except AccessError as e:
            return request.render('formevo.access_error_template', {'error_message': str(e)})
        except Exception as e:
            _logger.error(f"Erreur dashboard cours {course_id}: {e}")
            return request.render('formevo.error_template', {'error_message': "Une erreur est survenue."})

    @http.route('/yonn/student/dashboard', type='http', auth='user', website=True)
    def student_dashboard(self, **kwargs):
        """Dashboard personnel pour les apprenants."""
        try:
            user = request.env.user
            if not user.has_group('formevo.group_yonn_elearning_student'):
                raise AccessError("Accès réservé aux apprenants.")

            # On cherche directement les enregistrements de progression de l'utilisateur
            progress_records = request.env['yonn.course.progress'].search([
                ('partner_id', '=', user.partner_id.id)
            ])

            return request.render('formevo.student_dashboard_template', {
                'progress_records': progress_records,
                'user': user,
                'page_name': 'student_dashboard'
            })
        except Exception as e:
            _logger.error(f"Erreur dashboard étudiant pour {user.name}: {e}")
            return request.render('formevo.error_template', {'error_message': "Une erreur est survenue."})

    @http.route('/yonn/tracking/toggle_completion', type='json', auth='user', website=True, csrf=False)
    def toggle_completion(self, slide_id=None, **kwargs):
        """Bascule l'état de complétion d'un slide. Appelé par le JS."""
        try:

            # Lire le body JSON (robuste)
            payload = {}
            try:
                raw = request.httprequest.get_data(as_text=True) or ""
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}

            slide_id = (
                    slide_id
                    or kwargs.get('slide_id')
                    or payload.get('slide_id')
                    or (payload.get('params') or {}).get('slide_id')
            )

            if not slide_id:
                return {'status': 'error', 'message': 'missing_slide_id'}

            slide_id = int(slide_id)

            slide_partner = request.env['slide.slide.partner'].sudo().search([
                ('slide_id', '=', slide_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            if not slide_partner:
                slide = request.env['slide.slide'].sudo().browse(slide_id)
                slide_partner = request.env['slide.slide.partner'].sudo().create({
                    'slide_id': slide.id,
                    'partner_id': request.env.user.partner_id.id,
                    'channel_id': slide.channel_id.id,
                })

            new_status = slide_partner.toggle_completion()
            return {'status': 'success', 'completed': new_status}

        except Exception as e:
            _logger.error(f"Erreur de basculement de complétion pour slide {slide_id}: {e}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/yonn/tracking/get_completion_status', type='json', auth='user', website=True, csrf=False)
    def get_completion_status(self, slide_id=None, **kwargs):
        payload = {}
        try:
            raw = request.httprequest.get_data(as_text=True) or ""
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}

        slide_id = (
                slide_id
                or kwargs.get('slide_id')
                or payload.get('slide_id')
                or (payload.get('params') or {}).get('slide_id')
        )

        if not slide_id:
            return {'status': 'error', 'message': 'missing_slide_id'}

        slide_id = int(slide_id)
        partner = request.env.user.partner_id

        sp = request.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', slide_id),
            ('partner_id', '=', partner.id),
        ], limit=1)

        completed = sp.completed if sp else False
        return {'status': 'success', 'completed': completed}