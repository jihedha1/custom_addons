# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class SlideQuestionPendingAnswer(models.Model):
    """
    Modèle pour stocker les réponses en attente de validation enseignant
    Utilisé en mode de correction manuelle
    """
    _name = 'slide.question.pending.answer'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Réponses en attente de validation enseignant"
    _order = 'create_date desc'
    _rec_name = 'display_name'
    _sql_constraints = [
        ('uniq_question_user_attempt', 'unique(question_id, user_id, attempt_no)',
         'Réponse déjà enregistrée pour cette tentative.'),
    ]

    # ============================================================================
    # CHAMPS PRINCIPAUX
    # ============================================================================

    question_id = fields.Many2one(
        'slide.question',
        required=True,
        ondelete='cascade',
        string="Question",
        index=True
    )

    user_id = fields.Many2one(
        'res.users',
        string="Étudiant",
        required=True,
        index=True
    )
    attempt_no = fields.Integer(string="Tentative #", default=1, index=True)

    # Pour QCM/Vrai-Faux
    answer_id = fields.Many2one(
        'slide.answer',
        string="Réponse choisie",
        help="Pour les questions à choix multiple ou vrai/faux"
    )

    # Pour questions ouvertes
    text_answer = fields.Text(
        string="Réponse textuelle",
        help="Pour les questions ouvertes"
    )

    partner_id = fields.Many2one('res.partner', string='Partner')
    slide_id = fields.Many2one('slide.slide', related='question_id.slide_id', store=True, index=True)
    channel_id = fields.Many2one('slide.channel', related='slide_id.channel_id', store=True, index=True)

    # ============================================================================
    # RÉSULTAT DE LA CORRECTION INITIALE (AUTO OU GPT)
    # ============================================================================

    is_correct = fields.Boolean(
        string="Correct (suggestion)",
        default=False,
        help="Résultat suggéré par la correction automatique ou GPT"
    )

    score = fields.Integer(
        string="Score (suggestion)",
        default=0,
        help="Score suggéré (0-100)"
    )

    feedback = fields.Html(
        string="Feedback (suggestion)",
        help="Feedback généré automatiquement"
    )

    gpt_ideal_answer = fields.Text(
        string="Réponse idéale (GPT)",
        help="Réponse idéale suggérée par GPT (si applicable)"
    )

    # ============================================================================
    # VALIDATION ENSEIGNANT
    # ============================================================================

    state = fields.Selection([
        ('pending', 'En attente'),
        ('validated', 'Validé'),
        ('rejected', 'Rejeté'),
        ('corrected', 'Corrigé manuellement')
    ], default='pending',
        required=True,
        string="État",
        index=True)

    teacher_comment = fields.Text(
        string="Commentaire enseignant",
        help="Commentaire additionnel de l'enseignant"
    )

    final_score = fields.Integer(
        string="Score final",
        help="Score final après validation (0-100)"
    )

    final_feedback = fields.Html(
        string="Feedback final",
        help="Feedback final envoyé à l'étudiant"
    )

    validated_by = fields.Many2one(
        'res.users',
        string="Validé par",
        readonly=True
    )

    validated_date = fields.Datetime(
        string="Date de validation",
        readonly=True
    )

    create_date = fields.Datetime(
        string="Date de soumission",
        readonly=True
    )

    # ============================================================================
    # CHAMPS COMPUTÉS
    # ============================================================================

    display_name = fields.Char(
        string="Nom",
        compute='_compute_display_name',
        store=True
    )

    question_text = fields.Char(
        related='question_id.question',
        string="Texte Question",
        readonly=True
    )

    student_name = fields.Char(
        related='user_id.name',
        string="Nom Étudiant",
        readonly=True
    )

    processing_time = fields.Float(
        string="Temps de traitement (s)",
        compute="_compute_processing_time",
        store=True,
        readonly=True,
    )

    is_overdue = fields.Boolean(
        string="En retard",
        compute="_compute_is_overdue",
        store=True,
        index=True,
    )

    # ============================================================================
    # MÉTHODE CREATE BATCH COMPATIBLE
    # ============================================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        pending_records = records.filtered(lambda r: r.state == 'pending')
        if pending_records:
            self._notify_teachers_batch(pending_records)
        return records

    def _notify_teachers_batch(self, pending_records):
        """Notifie les enseignants par lot (mail.activity)"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')

        teacher_records = {}
        for record in pending_records:
            teacher = record.channel_id.user_id if record.channel_id and record.channel_id.user_id else False
            if not teacher:
                continue

            teacher_records.setdefault(teacher.id, {
                'teacher': teacher,
                'records': [],
            })
            teacher_records[teacher.id]['records'].append(record)

        Activity = self.env['mail.activity'].sudo()
        todo_type = self.env.ref('mail.mail_activity_data_todo')
        model_pending = self.env['ir.model']._get_id('slide.question.pending.answer')

        for teacher_id, data in teacher_records.items():
            recs = data['records']
            if not recs:
                continue

            # Grouper par cours (channel) pour un message plus lisible
            per_channel = {}
            for r in recs:
                ch = r.channel_id
                per_channel.setdefault(ch.id if ch else 0, {
                    'channel': ch,
                    'items': []
                })
                per_channel[ch.id if ch else 0]['items'].append(r)

            # Construire un texte riche
            total = len(recs)
            lines = [f"📥 {total} nouvelle(s) réponse(s) en attente de correction."]

            for _, pack in per_channel.items():
                channel = pack['channel']
                channel_name = channel.name if channel else "(Cours inconnu)"
                lines.append("")
                lines.append(f"• Cours : {channel_name} ({len(pack['items'])})")

                # Ajouter quelques exemples (max 3) avec type + lien détail
                for r in pack['items'][:3]:
                    q = r.question_id
                    qtype = getattr(q, "x_question_type", "") or ""
                    mode = getattr(q, "correction_mode", "") or ""
                    mode_label = "Manuel" if mode == "manual" else "Automatique"

                    # lien direct vers l'item à corriger (back-office)
                    backoffice_url = (
                        f"{base_url}/web#id={r.id}&model=slide.question.pending.answer&view_type=form"
                        if base_url else ""
                    )

                    q_short = (q.question or "")[:70]
                    lines.append(f"   - {mode_label} | {qtype} | Q: {q_short}...")
                    if backoffice_url:
                        lines.append(f"     ↳ {backoffice_url}")

            note = "<br/>".join([l.replace("\n", "<br/>") for l in lines])


            Activity.search([
                 ('user_id', '=', teacher_id),
                 ('res_model_id', '=', model_pending),
                 ('activity_type_id', '=', todo_type.id),
                 ('summary', '=', 'Réponses à valider'),
             ]).unlink()

            Activity.create({
                'res_model_id': model_pending,
                'res_id': recs[0].id,  # record de référence (cliquer ouvre celui-ci)
                'activity_type_id': todo_type.id,
                'user_id': teacher_id,
                'summary': f"Réponses à valider ({total})",
                'note': note,
            })

            _logger.info("Notification batch créée pour l'enseignant %s (%d réponses)",
                         data['teacher'].name, total)

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends('user_id', 'question_id', 'create_date')
    def _compute_display_name(self):
        """Génère un nom d'affichage lisible"""
        for record in self:
            if record.user_id and record.question_id:
                date_str = fields.Datetime.to_string(record.create_date)[:10] if record.create_date else ''
                record.display_name = f"{record.user_id.name} - Q{record.question_id.id} ({date_str})"
            else:
                record.display_name = f"Réponse #{record.id}"

    @api.depends("create_date", "state")
    def _compute_is_overdue(self):
        """Vérifie si la réponse est en retard de validation (>48h)"""
        for record in self:
            if record.state == 'pending' and record.create_date:
                delta = fields.Datetime.now() - record.create_date
                record.is_overdue = delta.total_seconds() > (48 * 3600)
            else:
                record.is_overdue = False

    @api.depends("create_date", "write_date", "state")
    def _compute_processing_time(self):
        """Calcule le temps de traitement"""
        for rec in self:
            if rec.create_date and rec.write_date and rec.state in ("validated", "rejected", "corrected"):
                rec.processing_time = (rec.write_date - rec.create_date).total_seconds()
            else:
                rec.processing_time = 0.0

    # ============================================================================
    # ACTIONS
    # ============================================================================

    def action_validate(self):
        """Valide la correction suggérée telle quelle"""
        self.ensure_one()

        if self.state != 'pending':
            raise UserError(_("Cette réponse a déjà été traitée"))

        qtype = self.question_id.x_question_type

        if qtype in ('simple_choice', 'true_false'):
            final_score = 100 if self.is_correct else 0
        else:
            # text_box : utiliser le score suggéré (0..100)
            final_score = int(self.score or 0)

        self.write({
            'state': 'validated',
            'final_score': final_score,
            'final_feedback': self.feedback,
            'validated_by': self.env.user.id,
            'validated_date': fields.Datetime.now()
        })

        self._notify_student()

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.depends('user_id', 'question_id', 'create_date')
    def _compute_display_name(self):
        """Génère un nom d'affichage lisible"""
        for record in self:
            if record.user_id and record.question_id:
                date_str = fields.Datetime.to_string(record.create_date)[:10] if record.create_date else ''
                record.display_name = f"{record.user_id.name} - Q{record.question_id.id} ({date_str})"
            else:
                record.display_name = f"Réponse #{record.id}"

    @api.depends("create_date", "state")
    def _compute_is_overdue(self):
        """Vérifie si la réponse est en retard de validation (>48h)"""
        for record in self:
            if record.state == 'pending' and record.create_date:
                delta = fields.Datetime.now() - record.create_date
                record.is_overdue = delta.total_seconds() > (48 * 3600)
            else:
                record.is_overdue = False

    @api.depends("create_date", "write_date", "state")
    def _compute_processing_time(self):
        """Calcule le temps de traitement"""
        for rec in self:
            if rec.create_date and rec.write_date and rec.state in ("validated", "rejected", "corrected"):
                rec.processing_time = (rec.write_date - rec.create_date).total_seconds()
            else:
                rec.processing_time = 0.0

    # ============================================================================
    # ACTIONS
    # ============================================================================

    def action_reject(self):
        """Rejette la réponse (score = 0)"""
        self.ensure_one()

        if self.state != 'pending':
            raise UserError(_("Cette réponse a déjà été traitée"))

        # Vérification de sécurité pour éviter les double-clics
        current_state = self.env['slide.question.pending.answer'].browse(self.id).state
        if current_state != 'pending':
            raise UserError(_("Cette réponse a déjà été traitée"))

        self.write({
            'state': 'rejected',
            'final_score': 0,
            'final_feedback': self._build_rejection_feedback(),
            'validated_by': self.env.user.id,
            'validated_date': fields.Datetime.now()
        })

        self._notify_student()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_correct_manually(self):
        """Ouvre un wizard pour corriger manuellement"""
        self.ensure_one()

        return {
            'name': _('Corriger Manuellement'),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.question.correction.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_pending_answer_id': self.id,
                'default_student_answer': self.text_answer or (self.answer_id.text_value if self.answer_id else ''),
                'default_suggested_score': self.score,
                'default_suggested_feedback': self.feedback,
            }
        }

    def action_view_question(self):
        """Ouvre la question dans une vue formulaire"""
        self.ensure_one()

        return {
            'name': _('Question'),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.question',
            'res_id': self.question_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_student(self):
        """Ouvre le profil de l'étudiant"""
        self.ensure_one()
        return {
            "name": _("Étudiant"),
            "type": "ir.actions.act_window",
            "res_model": "res.users",
            "res_id": self.user_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # ============================================================================
    # NOTIFICATIONS
    # ============================================================================

    def _notify_student(self):
        """Notifie l'étudiant que sa réponse a été corrigée"""
        template = self.env.ref(
            'odoo_gpt_integration.mail_template_correction_notification',
            raise_if_not_found=False
        )

        for rec in self:
            if not rec.user_id:
                continue

            try:
                if template:
                    template.send_mail(rec.id, force_send=True, raise_exception=False)
                    _logger.info("Notification email (template) envoyée à %s", rec.user_id.email or rec.user_id.name)
                    continue
            except Exception as e:
                _logger.exception("Erreur envoi template pour pending_answer %s: %s", rec.id, e)

            subject = _("✅ Correction disponible - %s") % (rec.channel_id.name or "")
            score = rec.final_score if rec.final_score is not False else 0
            question = rec.question_id.question or _("(Question)")
            course = rec.channel_id.name or ""
            chapter = rec.slide_id.name or ""
            mode = "🤖 Automatique" if rec.question_id.correction_mode == "automatic" else "👨‍🏫 Manuelle (enseignant)"
            url = rec.get_correction_url()

            feedback = rec.final_feedback or ""

            body_html = f"""
              <p>Bonjour {rec.user_id.name},</p>
              <p>Votre correction est disponible pour la question : <b>{question}</b></p>
              <p><b>Cours :</b> {course}</p>
              <p><b>Chapitre :</b> {chapter}</p>
              <p><b>Type de correction :</b> {mode}</p>
              <p><b>Score final :</b> {score}/100</p>
              {f"<p><b>Feedback enseignant :</b></p><div>{feedback}</div>" if feedback else ""}
              <p style="margin-top:16px;">
                <a href="{url}" style="display:inline-block;padding:10px 15px;background:#875A7B;color:#fff;text-decoration:none;border-radius:6px;">
                  👉 Voir la correction
                </a>
              </p>
            """
            if rec.user_id.email:
                try:
                    mail = rec.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': body_html,
                        'email_to': rec.user_id.email,
                    })
                    mail.sudo().send()
                    _logger.info("Notification email (mail.mail) envoyée à %s", rec.user_id.email)
                    continue
                except Exception as e:
                    _logger.exception("Erreur envoi mail.mail pour pending_answer %s: %s", rec.id, e)

            try:
                partner = rec.user_id.partner_id
                if partner:
                    rec.message_post(
                        subject=subject,
                        body=body_html,
                        partner_ids=[partner.id],
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment',
                    )
                    _logger.info("Notification interne envoyée à user %s (partner %s)", rec.user_id.id, partner.id)
            except Exception as e:
                _logger.exception("Erreur notification interne pour pending_answer %s: %s", rec.id, e)

    def _notify_teacher(self):
        """Notifie l'enseignant qu'une nouvelle réponse est en attente (activité)"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')

        Activity = self.env['mail.activity'].sudo()
        todo_type = self.env.ref('mail.mail_activity_data_todo')
        model_id = self.env['ir.model']._get_id('slide.question.pending.answer')

        for rec in self:
            teacher = rec.channel_id.user_id if rec.channel_id and rec.channel_id.user_id else False
            if not teacher:
                continue

            # Infos utiles
            course_name = rec.channel_id.name or "(Cours)"
            quiz_name = rec.slide_id.name or "(Quiz)"
            question_text = (rec.question_id.question or "(Question)")[:120]
            qtype = getattr(rec.question_id, "x_question_type", "") or ""
            mode = getattr(rec.question_id, "correction_mode", "") or ""
            mode_label = "Manuel" if mode == "manual" else "Automatique"

            # Lien direct back-office vers la réponse en attente
            backoffice_url = ""
            if base_url:
                backoffice_url = (
                    f"{base_url}/web#id={rec.id}"
                    f"&model=slide.question.pending.answer"
                    f"&view_type=form"
                )

            # Aperçu réponse étudiant (selon type)
            student_answer = ""
            if rec.text_answer:
                student_answer = (rec.text_answer or "")[:300]
            elif rec.answer_id:
                student_answer = rec.answer_id.text_value or ""

            # Note HTML (beaucoup plus lisible)
            note_parts = [
                f"<p><b>📚 Cours :</b> {course_name}</p>",
                f"<p><b>🧩 Quiz :</b> {quiz_name}</p>",
                f"<p><b>📝 Question :</b> {question_text}</p>",
                f"<p><b>⚙️ Mode :</b> {mode_label} &nbsp;|&nbsp; <b>Type :</b> {qtype}</p>",
            ]

            if student_answer:
                note_parts.append(f"<p><b>👤 Réponse étudiant :</b><br/>{student_answer}</p>")

            # Optionnel : afficher la suggestion auto (score/feedback) si tu veux
            if rec.score is not None:
                note_parts.append(f"<p><b>🤖 Suggestion :</b> Score {rec.score}/100</p>")
            if rec.feedback:
                note_parts.append(f"<p><b>🧠 Feedback suggéré :</b><br/>{rec.feedback}</p>")

            if backoffice_url:
                note_parts.append(f"<p>🔗 <a href='{backoffice_url}'>Ouvrir la correction</a></p>")

            Activity.create({
                'res_model_id': model_id,
                'res_id': rec.id,
                'activity_type_id': todo_type.id,
                'user_id': teacher.id,
                'summary': f"Réponse à valider • {course_name}",
                'note': "".join(note_parts),
            })

            _logger.info(
                "Notification activité créée pour l'enseignant %s (pending_answer %s)",
                teacher.id, rec.id
            )
    # ============================================================================
    # MÉTHODES UTILITAIRES
    # ============================================================================

    def _build_rejection_feedback(self):
        """Construit le feedback pour une réponse rejetée"""
        feedback = f"""
        <div class='alert alert-danger'>
            <strong>❌ Réponse incorrecte</strong><br/>
            {self.teacher_comment or "Votre réponse ne correspond pas aux attentes."}
        </div>
        """
        return feedback

    def _build_notification_message(self):
        """Construit le message de notification"""
        state_labels = {
            'validated': 'validée',
            'rejected': 'rejetée',
            'corrected': 'corrigée'
        }

        message = f"""
        Votre réponse à la question "{self.question_text[:50]}..." a été {state_labels.get(self.state, 'traitée')}.

        Score obtenu : {self.final_score}/100

        {self.teacher_comment or ''}
        """

        return message

    # ============================================================================
    # MÉTHODES DE MASSE
    # ============================================================================

    def action_validate_multiple(self):
        """Valide plusieurs réponses en masse"""
        for record in self:
            if record.state == 'pending':
                record.action_validate()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validation en masse'),
                'message': _('%d réponse(s) validée(s)') % len(self),
                'type': 'success',
            }
        }

    # ============================================================================
    # CONTRAINTES
    # ============================================================================

    @api.constrains('final_score')
    def _check_final_score(self):
        """Vérifie que le score final est entre 0 et 100"""
        for record in self:
            if record.final_score is not False and (record.final_score < 0 or record.final_score > 100):
                raise ValidationError(_("Le score final doit être entre 0 et 100"))

    @api.constrains('answer_id', 'text_answer')
    def _check_answer_content(self):
        """Vérifie qu'au moins un type de réponse est rempli"""
        for record in self:
            if not record.answer_id and not record.text_answer:
                raise ValidationError(_("La réponse doit contenir soit un choix, soit un texte"))

    def get_correction_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        return f"{base}/slides/result/{self.id}/details"
