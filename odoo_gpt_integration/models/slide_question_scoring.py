# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SlideQuestionKeywordScore(models.Model):
    """
    Modèle pour le scoring des mots-clés en correction automatique
    Permet d'attribuer des scores positifs (bonus) ou négatifs (pénalités)
    """
    _name = 'slide.question.keyword.score'
    _description = "Scoring des mots-clés pour correction automatique"
    _order = 'sequence, id'

    # ============================================================================
    # CHAMPS
    # ============================================================================

    question_id = fields.Many2one(
        'slide.question',
        required=True,
        ondelete='cascade',
        string="Question",
        index=True
    )

    sequence = fields.Integer(
        default=10,
        help="Ordre d'affichage et de traitement"
    )

    keyword = fields.Char(
        string="Mot-clé",
        required=True,
        help="Mot ou expression à rechercher dans la réponse (sensible à la casse)"
    )

    score_value = fields.Integer(
        string="Score",
        required=True,
        default=10,
        help="""
        Score attribué si le mot-clé est trouvé :
        • Positif (+10, +20, etc.) : Mot-clé attendu → bonus
        • Négatif (-10, -20, etc.) : Mot-clé interdit → pénalité

        Exemples :
        - "photosynthèse" : +20 points
        - "chlorophylle" : +15 points
        - "faux" : -10 points
        """
    )

    description = fields.Char(
        string="Description",
        help="Note pour l'enseignant sur ce mot-clé (non visible par l'étudiant)"
    )

    keyword_type = fields.Selection([
        ('required', 'Requis (bonus)'),
        ('forbidden', 'Interdit (pénalité)'),
        ('bonus', 'Bonus optionnel')
    ], string="Type",
        compute='_compute_keyword_type',
        store=True,
        help="Déterminé automatiquement selon le score")

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends('score_value')
    def _compute_keyword_type(self):
        """Détermine le type de mot-clé selon le score"""
        for record in self:
            if record.score_value > 15:
                record.keyword_type = 'required'
            elif record.score_value < 0:
                record.keyword_type = 'forbidden'
            else:
                record.keyword_type = 'bonus'

    # ============================================================================
    # CONTRAINTES
    # ============================================================================

    @api.constrains('keyword')
    def _check_keyword_not_empty(self):
        """Vérifie que le mot-clé n'est pas vide"""
        for record in self:
            if not record.keyword or not record.keyword.strip():
                raise ValidationError(_("Le mot-clé ne peut pas être vide"))

    @api.constrains('score_value')
    def _check_score_range(self):
        """Vérifie que le score est dans une plage raisonnable"""
        for record in self:
            if record.score_value == 0:
                raise ValidationError(_("Le score ne peut pas être zéro (utilisez un score positif ou négatif)"))
            if abs(record.score_value) > 100:
                raise ValidationError(_("Le score doit être entre -100 et +100"))

    # ============================================================================
    # MÉTHODES UTILITAIRES
    # ============================================================================

    def name_get(self):
        """Affichage personnalisé dans les listes"""
        result = []
        for record in self:
            sign = '+' if record.score_value > 0 else ''
            name = f"{record.keyword} ({sign}{record.score_value})"
            result.append((record.id, name))
        return result

    @api.model
    def create_from_legacy_keywords(self, question_id):
        """
        Migration : Crée des enregistrements de scoring depuis les anciens champs
        ai_include_keywords et ai_exclude_keywords
        """
        question = self.env['slide.question'].browse(question_id)

        if not question.exists():
            return

        sequence = 10

        # Mots-clés à inclure (ancienne méthode)
        if question.ai_include_keywords:
            import re
            include_list = [
                kw.strip()
                for kw in re.split(r'[,;\n]+', question.ai_include_keywords)
                if kw.strip()
            ]

            for keyword in include_list:
                # Vérifier si déjà existant
                existing = self.search([
                    ('question_id', '=', question.id),
                    ('keyword', '=ilike', keyword)
                ])

                if not existing:
                    self.create({
                        'question_id': question.id,
                        'keyword': keyword,
                        'score_value': 10,
                        'description': 'Migré depuis ai_include_keywords',
                        'sequence': sequence
                    })
                    sequence += 10

        # Mots-clés à exclure (ancienne méthode)
        if question.ai_exclude_keywords:
            import re
            exclude_list = [
                kw.strip()
                for kw in re.split(r'[,;\n]+', question.ai_exclude_keywords)
                if kw.strip()
            ]

            for keyword in exclude_list:
                # Vérifier si déjà existant
                existing = self.search([
                    ('question_id', '=', question.id),
                    ('keyword', '=ilike', keyword)
                ])

                if not existing:
                    self.create({
                        'question_id': question.id,
                        'keyword': keyword,
                        'score_value': -15,
                        'description': 'Migré depuis ai_exclude_keywords',
                        'sequence': sequence
                    })
                    sequence += 10

    def action_duplicate(self):
        self.ensure_one()
        return self.copy({
            "sequence": (self.sequence or 10) + 1,
            "keyword": f"{self.keyword} (copie)",
        })

    def action_invert_score(self):
        for rec in self:
            rec.score_value = - (rec.score_value or 0)
        return True
