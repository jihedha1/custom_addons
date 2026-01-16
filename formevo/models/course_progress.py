# /home/ubuntu/upload/course_progress.py

import collections
from odoo import models, fields, api
from odoo.osv import expression


class CourseProgress(models.Model):
    _name = 'yonn.course.progress'
    _description = 'Rapport de Progression agrégée par Apprenant/Cours'
    _rec_name = 'display_name'

    # --- CHAMPS (Aucun changement ici) ---
    partner_id = fields.Many2one('res.partner', string='Apprenant', readonly=True)
    course_id = fields.Many2one('slide.channel', string='Cours', readonly=True)
    user_id = fields.Many2one('res.users', string='Responsable du Cours', related='course_id.user_id', store=True)
    display_name = fields.Char(string='Nom', compute='_compute_display_name')
    total_slides = fields.Integer(string='Total Contenus', compute='_compute_progress_stats')
    completed_slides = fields.Integer(string='Contenus Terminés', compute='_compute_progress_stats')
    completion_percentage = fields.Float(string='Complétion (%)', compute='_compute_progress_stats',
                                         search='_search_completion_percentage', group_operator='avg')
    total_time_spent = fields.Integer(string='Temps Total (secondes)', compute='_compute_progress_stats')
    formatted_time_spent = fields.Char(string='Temps Passé', compute='_compute_formatted_time')
    last_activity = fields.Datetime(string='Dernière Activité', compute='_compute_progress_stats',
                                    search='_search_last_activity')

    # --- MÉTHODES COMPUTE et SEARCH (Aucun changement ici) ---
    @api.depends('partner_id.name', 'course_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.partner_id.name or 'N/A'} - {record.course_id.name or 'N/A'}"

    def _compute_progress_stats(self):
        for record in self:
            if not record.partner_id or not record.course_id:
                record.total_slides = record.completed_slides = record.total_time_spent = 0
                record.completion_percentage = 0.0
                record.last_activity = False
                continue
            sp = self.env['slide.slide.partner'].search(
                [('partner_id', '=', record.partner_id.id), ('channel_id', '=', record.course_id.id)])
            slides = record.course_id.slide_ids.filtered(lambda s: not s.is_category)
            record.total_slides = len(slides)
            record.completed_slides = len(sp.filtered('completed'))
            record.total_time_spent = sum(sp.mapped('x_time_spent'))
            record.completion_percentage = (
                                                       record.completed_slides / record.total_slides) * 100.0 if record.total_slides else 0.0
            dates = [d for d in sp.mapped('x_last_activity') if d]
            record.last_activity = max(dates) if dates else False

    @api.depends('total_time_spent')
    def _compute_formatted_time(self):
        for record in self:
            secs = record.total_time_spent
            mins, sec = divmod(secs, 60)
            hr, mn = divmod(mins, 60)
            record.formatted_time_spent = f"{int(hr):02d}:{int(mn):02d}:{int(sec):02d}"

    def _search_completion_percentage(self, operator, value):
        # ... (cette méthode ne change pas)
        all_sp = self.env['slide.slide.partner'].search([])
        stats = collections.defaultdict(lambda: {'completed': 0, 'total': 0})
        for p in all_sp:
            if p.channel_id and p.partner_id and p.channel_id.total_slides > 0:
                key = (p.channel_id.id, p.partner_id.id)
                stats[key]['total'] += 1
                if p.completed: stats[key]['completed'] += 1
        valid = []
        for (course_id, _), s in stats.items():
            perc = (s['completed'] / s['total']) * 100 if s['total'] else 0
            if {'=': perc == value, '>': perc > value, '<': perc < value, '>=': perc >= value, '<=': perc <= value}.get(
                    operator, False):
                valid.append(course_id)
        return [('course_id', 'in', list(set(valid)))]

    def _search_last_activity(self, operator, value):
        # ... (cette méthode ne change pas)
        sp = self.env['slide.slide.partner'].search([('x_last_activity', operator, value)])
        return [('course_id', 'in', sp.mapped('channel_id').ids)]

    # --- READ_GROUP FINAL ET COMPLET ---
        # Dans /home/ubuntu/upload/course_progress.py

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """
        Surcharge de read_group, version hybride et stable.
        On laisse super() faire le gros du travail sur les champs stockés,
        puis on enrichit le résultat avec nos champs calculés.
        """
        # Étape 1: Création des enregistrements en mémoire (logique inchangée et fonctionnelle)
        teacher_domain = [('user_id', '=', self.env.uid)]
        courses = self.env['slide.channel'].search(teacher_domain)
        slide_partners = self.env['slide.slide.partner'].search([('channel_id', 'in', courses.ids)])
        partner_course_pairs = {(sp.partner_id, sp.channel_id) for sp in slide_partners if
                                sp.partner_id and sp.channel_id}
        if not partner_course_pairs: return []

        existing_records = self.search([('partner_id', 'in', [p.id for p, c in partner_course_pairs]),
                                        ('course_id', 'in', [c.id for p, c in partner_course_pairs])])
        existing_pairs = {(rec.partner_id, rec.course_id) for rec in existing_records}
        records_to_create = [{'partner_id': p.id, 'course_id': c.id} for p, c in partner_course_pairs if
                             (p, c) not in existing_pairs]
        if records_to_create: self.env[self._name].create(records_to_create)

        # Étape 2: On identifie les champs que super() peut gérer et ceux que nous devons calculer
        stockable_fields = {f.split(':')[0] for f in fields if
                            self._fields[f.split(':')[0]].store or f.split(':')[0] in ('id', 'display_name')}
        computed_fields = [f for f in fields if f.split(':')[0] not in stockable_fields]

        # Étape 3: On appelle super() UNIQUEMENT avec les champs qu'il peut gérer
        res = super(CourseProgress, self).read_group(domain, list(stockable_fields), groupby, offset=offset,
                                                     limit=limit, orderby=orderby, lazy=lazy)

        # Étape 4: On enrichit le résultat avec nos champs calculés
        if computed_fields:
            for group in res:
                # On trouve les enregistrements correspondant à ce groupe
                records_in_group = self.search(group['__domain'])

                # On calcule les agrégats pour les champs non stockés
                for field_name_full in computed_fields:
                    field_name = field_name_full.split(':')[0]
                    field_obj = self._fields[field_name]

                    if field_obj.group_operator == 'avg':
                        total = sum(records_in_group.mapped(field_name))
                        group[field_name_full] = total / len(records_in_group) if records_in_group else 0
                    elif field_obj.type in ('integer', 'float'):
                        group[field_name_full] = sum(records_in_group.mapped(field_name))
                    else:
                        group[field_name_full] = records_in_group[0][field_name] if records_in_group else False

        return res
