from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SlideChannelInherit(models.Model):
    _inherit = 'slide.channel'

    def action_view_dashboard(self):
        """Ouvre le dashboard de progression pour ce cours."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/yonn/course/{self.id}/dashboard',
            'target': 'self',
        }

    def action_view_student_progress(self):
        """
        Ouvre la vue de progression pour tous les étudiants inscrits à ce cours.
        """
        self.ensure_one()
        # On récupère les IDs des partenaires (étudiants) inscrits à ce cours
        partner_ids = self.slide_partner_ids.mapped('partner_id').ids
        name = fields.Char(string="Course Title", translate=True)
        return {
            'name': _("Progression des Étudiants pour le cours : %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'yonn.course.progress',  # Le modèle qui montre la progression
            'view_mode': 'tree,form',
            'domain': [
                ('course_id', '=', self.id),
                ('partner_id', 'in', partner_ids)
            ],
            'target': 'current',  # Ouvre dans la vue principale
        }


class SlideSlideInherit(models.Model):
    _inherit = 'slide.slide'

    name = fields.Char(string='Title', translate=True)

    x_time_limit = fields.Integer(
        string='Durée suggérée (minutes)',
        help='Temps estimé pour compléter ce contenu.'
    )

    # ✅ Ajoutez une méthode pour obtenir les statistiques de complétion
    def get_completion_stats(self):
        """Retourne les statistiques de complétion pour ce slide."""
        self.ensure_one()
        records = self.env['slide.slide.partner'].search([
            ('slide_id', '=', self.id)
        ])

        total = len(records)
        completed = len(records.filtered(lambda r: r.completed))

        return {
            'total_students': total,
            'completed_count': completed,
            'completion_rate': (completed / total * 100) if total > 0 else 0,
            'average_time_spent': sum(records.mapped('x_time_spent')) / total if total > 0 else 0
        }

    def get_tracking_data_for_user(self, partner_id):
        """Retourne les données de tracking pour un partenaire spécifique."""
        self.ensure_one()
        tracking_record = self.env['slide.slide.partner'].search([
            ('slide_id', '=', self.id),
            ('partner_id', '=', partner_id)
        ], limit=1)

        if tracking_record:
            return {
                'time_spent': tracking_record.x_time_spent,
                'completed': tracking_record.completed,  # Utilise le champ standard
                'completion_date': tracking_record.x_completion_date,
                'last_activity': tracking_record.x_last_activity,
            }
        return {
            'time_spent': 0,
            'completed': False,
            'completion_date': False,
            'last_activity': False
        }

class SlidePartnerInherit(models.Model):
    _inherit = 'slide.slide.partner'

    x_time_spent = fields.Integer(
        string='Temps passé (secondes)',
        default=0,
        help="Temps total passé sur ce slide en secondes"
    )

    x_last_activity = fields.Datetime(
        string='Dernière activité',
        default=fields.Datetime.now,
        help="Date/heure de la dernière interaction avec ce slide"
    )

    x_completion_date = fields.Datetime(
        string='Date de complétion Yonn',
        help="Date à laquelle l'apprenant a terminé ce slide selon vos critères"
    )


    x_completion_method = fields.Selection([
        ('auto', 'Automatique (temps écoulé)'),
        ('manual', 'Manuel (apprenant)'),
        ('teacher', 'Validation enseignant'),
        ('quiz', 'Quiz réussi'),
    ], string="Méthode de validation")


    def add_time_spent(self, seconds_to_add):
        """Ajoute du temps passé et met à jour la dernière activité."""
        self.ensure_one()
        self.write({
            'x_time_spent': self.x_time_spent + seconds_to_add,
            'x_last_activity': fields.Datetime.now()
        })


    def toggle_completion(self):
        """Bascule l'état de complétion du slide."""
        self.ensure_one()

        new_state = not self.completed
        values = {
            'completed': new_state,
            'x_last_activity': fields.Datetime.now()
        }

        if new_state:
            values['x_completion_date'] = fields.Datetime.now()
            values['x_completion_method'] = 'manual'
        else:
            values['x_completion_date'] = False
            values['x_completion_method'] = False

        self.write(values)
        return new_state

    def mark_as_completed(self, method='auto', force=False):

        self.ensure_one()

        if not force and self.completed:
            return False  # Déjà complété

        self.write({
            'completed': True,
            'x_completion_date': fields.Datetime.now(),
            'x_completion_method': method,
            'x_last_activity': fields.Datetime.now()
        })
        return True

    # ✅ Contrôle de cohérence
    @api.constrains('x_completion_date', 'completed')
    def _check_completion_consistency(self):
        """Vérifie la cohérence entre le champ standard et votre champ personnalisé."""
        for record in self:
            if record.x_completion_date and not record.completed:
                raise ValidationError(
                    _("Incohérence : Une date de complétion Yonn est définie "
                      "mais le slide n'est pas marqué comme 'completed'.")
                )
