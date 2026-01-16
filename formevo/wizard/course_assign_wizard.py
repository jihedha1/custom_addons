from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CourseAssignWizard(models.TransientModel):
    _name = 'yonn.course.assign.wizard'
    _description = 'Assistant pour assigner des cours'

    assignment_type = fields.Selection([
        ('class', 'Classe'),
        ('individual', 'Individuel')
    ], string="Mode d'assignation", default='class', required=True)

    class_id = fields.Many2one('yonn.student.class', string='Classe')

    def _get_teacher_domain(self):
        """Retourne le domaine pour filtrer les utilisateurs du groupe Enseignant."""
        teacher_group = self.env.ref('formevo.group_yonn_elearning_teacher', raise_if_not_found=False)
        if teacher_group:
            return [('groups_id', 'in', teacher_group.id)]
        return [('id', '=', False)]  # Retourne un domaine vide si le groupe n'est pas trouvé

    def _get_student_domain(self):
        """Retourne le domaine pour filtrer les utilisateurs du groupe Apprenant."""
        student_group = self.env.ref('formevo.group_yonn_elearning_student', raise_if_not_found=False)
        if student_group:
            return [('groups_id', 'in', student_group.id)]
        return [('id', '=', False)]  # Retourne un domaine vide si le groupe n'est pas trouvé

    teacher_id = fields.Many2one(
        'res.users',
        string='Enseignant',
        domain=lambda self: self._get_teacher_domain()
    )

    student_ids = fields.Many2many(
        'res.users',
        string='Étudiants',
        domain=lambda self: self._get_student_domain()
    )
    course_id = fields.Many2one('slide.channel', string='Cours', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        user = self.env.user

        # S'il y a contexte de cours, préremplir enseignant
        if ctx.get('default_course_id'):
            course = self.env['slide.channel'].browse(ctx['default_course_id'])
            res.update({'course_id': course.id,
                        'teacher_id': course.user_id.id})

        # Préremplir enseignant selon profil
        if user.has_group('formevo.group_yonn_elearning_teacher'):
            res['teacher_id'] = user.id

        # Si lancé depuis une classe
        if ctx.get('active_model') == 'yonn.student.class' and ctx.get('active_id'):
            st_class = self.env['yonn.student.class'].browse(ctx['active_id'])
            res.update({
                'class_id': st_class.id,
                'teacher_id': st_class.teacher_id.id,
                'student_ids': [(6, 0, st_class.student_ids.ids)],
                'assignment_type': 'class',
            })

        return res

    @api.onchange('assignment_type', 'class_id')
    def _onchange_assignment_type(self):
        user = self.env.user

        if self.assignment_type == 'class':
            # Mode "Classe" : remplir et verrouiller fields
            if self.class_id:
                self.teacher_id = self.class_id.teacher_id.id
                self.student_ids = self.class_id.student_ids
        else:
            # Mode "Individuel"
            self.class_id = False
            # Laisser enseignant/étudiant libre sauf profil enseignant
            if user.has_group('formevo.group_yonn_elearning_teacher'):
                self.teacher_id = user.id

    @api.onchange('teacher_id')
    def _onchange_teacher(self):
        # Changer de cours si enseignant sélectionné
        self.course_id = False

    @api.depends('assignment_type')
    def _compute_readonly_flags(self):
        for wizard in self:
            wizard.class_id_readonly = wizard.assignment_type == 'class'
            wizard.teacher_id_readonly = wizard.assignment_type == 'class' and bool(wizard.class_id)
            wizard.student_ids_readonly = wizard.assignment_type == 'class' and bool(wizard.class_id)

    class_id_readonly = fields.Boolean(compute='_compute_readonly_flags', store=False)
    teacher_id_readonly = fields.Boolean(compute='_compute_readonly_flags', store=False)
    student_ids_readonly = fields.Boolean(compute='_compute_readonly_flags', store=False)

    def assign(self):
        self.ensure_one()

        if not self.course_id:
            raise ValidationError(_("Sélectionnez un cours à assigner."))

        students = self.student_ids
        if self.assignment_type == 'class' and self.class_id:
            students = self.class_id.student_ids

        if not students:
            raise ValidationError(_("Aucun étudiant sélectionné."))

        # Affectation Many2many eLearning natif (toujours utile)
        partners_to_add = []
        for stu in students:
            pt_id = stu.partner_id.id
            if pt_id and pt_id not in self.course_id.partner_ids.ids:
                partners_to_add.append(pt_id)
        if partners_to_add:
            self.course_id.partner_ids = [(4, pid) for pid in partners_to_add]

        # === SYNCHRO E-LEARNING NATIF : Cas Individuel SEULEMENT ===
        if self.assignment_type == 'individual':
            ChannelPartner = self.env['slide.channel.partner']
            for stu in students:
                pt = stu.partner_id
                if pt and not ChannelPartner.sudo().search([
                    ('channel_id', '=', self.course_id.id),
                    ('partner_id', '=', pt.id)
                ], limit=1):
                    ChannelPartner.sudo().create({
                        'channel_id': self.course_id.id,
                        'partner_id': pt.id,
                    })

        # (Optionnel) Création du suivi slide
        for stu in students:
            pt = stu.partner_id
            for slide in self.course_id.slide_ids:
                if not self.env['slide.slide.partner'].sudo().search([
                    ('slide_id', '=', slide.id),
                    ('partner_id', '=', pt.id),
                    ('channel_id', '=', self.course_id.id)
                ], limit=1):
                    self.env['slide.slide.partner'].sudo().create({
                        'slide_id': slide.id,
                        'partner_id': pt.id,
                        'channel_id': self.course_id.id,
                    })

        # Synchro liste de cours pour la classe (inchangée)
        if self.assignment_type == 'class' and self.class_id:
            if self.course_id not in self.class_id.assigned_course_ids:
                self.class_id.assigned_course_ids = [(4, self.course_id.id)]

        msg = _('Les étudiants sont assignés au cours.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }
    @api.depends('assignment_type')
    def _compute_readonly_flags(self):
        for wizard in self:
            wizard.student_ids_readonly = (wizard.assignment_type == 'class')

    @api.depends('assignment_type')
    def _compute_invisible_flags(self):
        for wizard in self:
            wizard.class_id_invisible = (wizard.assignment_type == 'individual')
    @api.onchange('class_id')
    def _onchange_class_id(self):
        """
        Lorsque l'utilisateur sélectionne une classe, remplit automatiquement
        le champ des étudiants avec les membres de cette classe.
        """
        if self.class_id and self.assignment_type == 'class':
            # Remplace la liste des étudiants par ceux de la classe
            self.student_ids = self.class_id.student_ids
        else:
            # Vide la liste si aucune classe n'est sélectionnée
            self.student_ids = False

