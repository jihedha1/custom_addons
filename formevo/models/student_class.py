from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentClass(models.Model):
    _name = 'yonn.student.class'
    _description = 'Classe d’étudiants pour Yonn eLearning'
    _order = 'name'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # === CHAMPS PRINCIPAUX ===
    name = fields.Char(
        string='Nom de la classe', required=True, trim=True, tracking=True
    )
    description = fields.Text(string='Description', tracking=True)
    active = fields.Boolean(string='Actif', default=True, tracking=True)

    student_count = fields.Integer(
        string="Nombre d'étudiants", compute='_compute_student_count', store=True
    )

    total_enrollments = fields.Integer(
        string='Total inscriptions', compute='_compute_total_enrollments',
        help="Étudiants × cours"
    )
    student_ids = fields.Many2many(
        'res.users', 'yonn_class_student_rel', 'class_id', 'student_id',
        string='Étudiants',
        domain=lambda self: self._get_student_domain(),
        help="Limité au groupe Apprenants"
    )

    teacher_id = fields.Many2one(
        'res.users', string='Enseignant responsable', required=True,
        domain=lambda self: self._get_teacher_domain(),
    )

    assigned_course_ids = fields.Many2many(
        'slide.channel', 'yonn_class_course_rel', 'class_id', 'course_id',
        string='Cours assignés',
        help="Seuls les cours de l’enseignant responsable sont sélectionnables.",
    )

    course_count = fields.Integer(string="Nombre de cours", compute="_compute_course_count", store=True)

    @api.depends('assigned_course_ids', 'assigned_course_ids.partner_ids')
    def _compute_course_count(self):
        for rec in self:
            rec.course_count = len(rec.assigned_course_ids)

    @api.depends('assigned_course_ids', 'student_ids')
    def _compute_total_enrollments(self):
        SlideChannelPartner = self.env['slide.channel.partner']
        for rec in self:
            rec.total_enrollments = SlideChannelPartner.search_count([
                ('channel_id', 'in', rec.assigned_course_ids.ids),
                ('partner_id', 'in', rec.student_ids.mapped('partner_id').ids),
            ])

    @api.onchange('teacher_id')
    def _onchange_teacher_id(self):
        self.assigned_course_ids = False

    def action_view_courses(self):
        self.ensure_one()
        return {
            'name': _("Cours assignés"),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.assigned_course_ids.ids)],
            'context': dict(self.env.context, default_teacher_id=self.teacher_id.id),
            'target': 'current',
        }

    # === DOMAINES MÉTHODES ===
    @api.model
    def _get_teacher_domain(self):
        teacher = self.env.ref(
            'formevo.group_yonn_elearning_teacher',
            raise_if_not_found=False
        )
        director = self.env.ref(
            'formevo.group_yonn_elearning_director',
            raise_if_not_found=False
        )
        gids = [g.id for g in (teacher, director) if g]
        return [('groups_id', 'in', gids)] if gids else []

    @api.model
    def _get_student_domain(self):
        group = self.env.ref(
            'formevo.group_yonn_elearning_student',
            raise_if_not_found=False
        )
        return [('groups_id', 'in', [group.id])] if group else []
    # === MÉTHODES COMPUTE ===
    @api.depends('student_ids')
    def _compute_student_count(self):
        for rec in self:
            rec.student_count = len(rec.student_ids)

    @api.depends('assigned_course_ids')
    def _compute_course_count(self):
        for rec in self:
            rec.course_count = len(rec.assigned_course_ids)

    @api.depends('student_ids', 'assigned_course_ids.partner_ids')
    def _compute_total_enrollments(self):
        """
        Calcule le nombre réel d'inscriptions en comptant les enregistrements
        dans le modèle 'slide.channel.partner'.
        """
        for rec in self:
            # Si aucun étudiant ou cours n'est assigné à la classe, le total est 0.
            if not rec.student_ids or not rec.assigned_course_ids:
                rec.total_enrollments = 0
                continue

            # On recherche dans le bon modèle : slide.channel.partner
            count = self.env['slide.channel.partner'].search_count([
                ('channel_id', 'in', rec.assigned_course_ids.ids),
                ('partner_id', 'in', rec.student_ids.mapped('partner_id').ids),
            ])
            rec.total_enrollments = count
    def action_view_student_progress(self):
        return {
            'name': "Progression Étudiants",
            'type': 'ir.actions.act_window',
            'res_model': 'yonn.course.progress',
            'view_mode': 'tree,kanban,form',
            'domain': [
                ('partner_id', 'in', self.student_ids.mapped('partner_id').ids)
            ],
        }
    def action_view_enrollments(self):
        return {
            'name': _("Inscriptions"),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel.partner',
            'view_mode': 'tree,form',
            'domain': [
                ('channel_id', 'in', self.assigned_course_ids.ids),
                ('partner_id', 'in', self.student_ids.mapped('partner_id').ids),
            ],
        }

    def action_view_students(self, *args):
        return {
            'name': _("Étudiants de la classe"),
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.student_ids.ids)],
        }

    def action_assign_courses_to_students(self):
        for rec in self:
            if not rec.student_ids or not rec.assigned_course_ids:
                raise ValidationError(_("Sélection incomplète."))
            partner_ids = rec.student_ids.mapped('partner_id').ids
            rec.assigned_course_ids.write({'partner_ids': [(4, pid) for pid in partner_ids]})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Les cours ont été assignés aux étudiants.'),
                'type': 'success',
            },
        }

    # Méthode à placer côté Yonn student_class ou à appeler après chaque modification
    def action_sync_students_with_course(self):

        ChannelPartner = self.env['slide.channel.partner']
        for rec in self:
            if not rec.student_ids or not rec.assigned_course_ids:
                continue
            partner_ids = rec.student_ids.mapped('partner_id').ids
            for course in rec.assigned_course_ids:
                # (1) Ajout natif
                course.partner_ids = [(6, 0, partner_ids)]
                # (2) Inscription réelle dans la table channel/partner
                for pid in partner_ids:
                    if not ChannelPartner.sudo().search([
                        ('channel_id', '=', course.id),
                        ('partner_id', '=', pid)
                    ], limit=1):
                        ChannelPartner.sudo().create({
                            'channel_id': course.id,
                            'partner_id': pid,
                        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synchronisation Odoo eLearning'),
                'message': _('Inscriptions et participations créées pour tous les étudiants et cours.'),
                'type': 'success',
            },
        }

    # Aliases pour compatibilité XML
    actionassigncoursestostudents = action_assign_courses_to_students
    actionviewstudentprogress    = action_view_student_progress
    actionviewenrollments        = action_view_enrollments
