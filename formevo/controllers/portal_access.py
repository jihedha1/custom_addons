
import logging
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class PortalStudentController(http.Controller):


    @http.route('/my/courses', type='http', auth='user', website=True)
    def portal_my_courses(self, **kwargs):

        user = request.env.user

        if not user.has_group('formevo.group_yonn_elearning_student'):

            return request.redirect('/formations/catalogue')

        enrollments = request.env['slide.channel.partner'].sudo().search([
            ('partner_id', '=', user.partner_id.id)
        ])

        enrolled_channel_ids = enrollments.mapped('channel_id').ids

        enrolled_channels = request.env['slide.channel'].sudo().browse(enrolled_channel_ids)

        courses_data = []
        for channel in enrolled_channels:
            progress = request.env['yonn.course.progress'].search([
                ('partner_id', '=', user.partner_id.id),
                ('course_id', '=', channel.id)
            ], limit=1)

            courses_data.append({
                'channel': channel,
                'progress': progress,
            })

        return request.render('formevo.portal_my_courses_template', {
            'courses_data': courses_data,
            'page_name': 'my_courses',
        })

    @http.route('/my/course/<int:course_id>', type='http', auth='user', website=True)
    def portal_course_detail(self, course_id, **kwargs):

        user = request.env.user

        enrollment = request.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', course_id),
            ('partner_id', '=', user.partner_id.id)
        ], limit=1)

        if not enrollment:
            if user.has_group('formevo.group_yonn_elearning_teacher'):

                channel = request.env['slide.channel'].browse(course_id)
            else:

                raise AccessError(_("Vous n'êtes pas inscrit à ce cours."))
        else:
            # Utiliser le canal de l'enrollment (déjà chargé)
            channel = enrollment.channel_id

        if not channel.exists():
            return request.not_found()

        progress = request.env['yonn.course.progress'].search([
            ('partner_id', '=', user.partner_id.id),
            ('course_id', '=', course_id)
        ], limit=1)

        slide_ids = channel.slide_ids.ids
        slide_partners = request.env['slide.slide.partner'].sudo().search([
            ('slide_id', 'in', slide_ids),
            ('partner_id', '=', user.partner_id.id)
        ])

        slide_partner_map = {sp.slide_id.id: sp for sp in slide_partners}

        slides_data = []
        for slide in channel.slide_ids:
            slide_partner = slide_partner_map.get(slide.id)

            slides_data.append({
                'slide': slide,
                'completed': slide_partner.completed if slide_partner else False,
                'time_spent': slide_partner.x_time_spent if slide_partner else 0,
            })

        return request.render('formevo.portal_course_detail_template', {
            'channel': channel,
            'progress': progress,
            'slides_data': slides_data,
            'page_name': 'course_detail',
        })

    @http.route('/my/course/<int:course_id>/slide/<int:slide_id>', type='http', auth='user', website=True)
    def portal_slide_view(self, course_id, slide_id, **kwargs):

        user = request.env.user

        enrollment = request.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', course_id),
            ('partner_id', '=', user.partner_id.id)
        ], limit=1)

        if not enrollment and not user.has_group('formevo.group_yonn_elearning_teacher'):
            raise AccessError(_("Vous n'êtes pas inscrit à ce cours."))

        slide = request.env['slide.slide'].sudo().browse(slide_id)

        if not slide.exists() or slide.channel_id.id != course_id:
            return request.not_found()
        return request.redirect(f'/slides/slide/{slide.id}')
