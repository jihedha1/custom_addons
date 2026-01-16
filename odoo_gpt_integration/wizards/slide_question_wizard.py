# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class SlideQuestionWizard(models.TransientModel):
    """
    Wizard pour création manuelle de questions
    Permet de créer rapidement des questions de différents types
    """
    _name = 'slide.question.wizard'
    _description = "Wizard de création rapide de question"

    # Contexte du cours
    channel_id = fields.Many2one('slide.channel', string="Cours", required=True, readonly=True)
    slide_id = fields.Many2one(
        'slide.slide',
        string="Chapitre Source",
        required=True,
        domain="[('channel_id', '=', channel_id), ('is_category', '=', False), ('slide_category', '!=', 'quiz')]",
        help="Le chapitre qui servira de contexte pour la question."
    )

    # Données de la question
    question = fields.Char(string="Titre de la Question", required=True)

    # ⚠️ CORRECTION : Utiliser les mêmes types que dans slide.question
    x_question_type = fields.Selection([
        ('simple_choice', 'QCM (Choix Multiple)'),
        ('true_false', 'Vrai / Faux'),
        ('text_box', 'Réponse Ouverte'),
    ], string="Type de Question", default='simple_choice', required=True)

    # Réponses dynamiques
    answer_lines = fields.One2many(
        'slide.question.wizard.answer.line',
        'wizard_id',
        string="Réponses"
    )

    @api.onchange('x_question_type')
    def _onchange_question_type(self):
        """
        Génère automatiquement les réponses pour Vrai/Faux
        Nettoie la liste pour les autres types
        """
        self.answer_lines = [(5, 0, 0)]  # Vide la liste

        if self.x_question_type == 'true_false':
            self.answer_lines = [
                (0, 0, {'text_value': 'Vrai', 'is_correct': False}),
                (0, 0, {'text_value': 'Faux', 'is_correct': False}),
            ]

    def action_create_question(self):
        self.ensure_one()

        # Validation UNIQUEMENT pour QCM et Vrai/Faux
        if self.x_question_type in ['simple_choice', 'true_false']:
            correct_answers_count = sum(1 for line in self.answer_lines if line.is_correct)
            incorrect_answers_count = len(self.answer_lines) - correct_answers_count

            if correct_answers_count != 1:
                raise ValidationError("Vous devez sélectionner exactement une réponse correcte.")
            if incorrect_answers_count == 0:
                raise ValidationError("Vous devez avoir au moins une réponse incorrecte.")

        # Étape 1 : Créer le quiz slide
        quiz_slide = self.env['slide.slide'].create({
            'name': self.question,
            'channel_id': self.channel_id.id,
            'slide_category': 'quiz',
            'is_published': False,
            'sequence': self.slide_id.sequence + 1,
        })

        # Étape 2 : Créer la question SANS les réponses
        question_vals = {
            'question': self.question,
            'slide_id': quiz_slide.id,
            'x_question_type': self.x_question_type,
            'x_ai_source_slide_id': self.slide_id.id,
        }

        question = self.env['slide.question'].create(question_vals)

        # Étape 3 : Créer les réponses SEULEMENT pour QCM et Vrai/Faux
        if self.x_question_type in ['simple_choice', 'true_false']:
            for line in self.answer_lines:
                if not line.text_value:
                    raise ValidationError(f"Le texte de la réponse ne peut pas être vide.")

                self.env['slide.answer'].create({
                    'question_id': question.id,
                    'text_value': line.text_value,
                    'is_correct': line.is_correct,
                })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'slide.slide',
            'view_mode': 'form',
            'res_id': quiz_slide.id,
            'target': 'current',
        }

class SlideQuestionWizardAnswerLine(models.TransientModel):
    """Ligne de réponse pour le wizard"""
    _name = 'slide.question.wizard.answer.line'
    _description = "Ligne de réponse pour le wizard"

    wizard_id = fields.Many2one('slide.question.wizard', required=True, ondelete='cascade')
    text_value = fields.Char(string="Texte de la réponse", required=True)
    is_correct = fields.Boolean(string="Correct ?")

    @api.onchange('is_correct')
    def _onchange_is_correct(self):
        if self.is_correct:
            other_lines = self.wizard_id.answer_lines.filtered(
                lambda l: l.id != self.id
            )
            for line in other_lines:
                line.is_correct = False