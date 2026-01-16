from odoo import models, fields, api

class SlideChannel(models.Model):
    _inherit = 'slide.channel'
    
    trainer_id = fields.Many2one(
        'lms_resources_trainers.trainer_profile',
        string='Formateur principal',
        help='Formateur assigné à cette formation'
    )
    
    required_resources_ids = fields.Many2many(
        'lms_resources_trainers.resource_management',
        string='Ressources nécessaires'
    )
    
    required_room_capacity = fields.Integer(
        string='Capacité de salle requise'
    )
    
    required_equipment_ids = fields.Many2many(
        'lms_resources_trainers.resource_equipment',
        string='Équipements nécessaires'
    )
    
    @api.onchange('trainer_id')
    def _onchange_trainer_id(self):
        """Mettre à jour les compétences affichées"""
        if self.trainer_id:
            # Mettre à jour les compétences dans la fiche formation
            self.ensure_one()
