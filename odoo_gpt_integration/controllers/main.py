# -*- coding: utf-8 -*-
"""
Contrôleur étendu pour le module website_slides d'Odoo
Support des 3 types de questions et correction IA
"""
import csv
import logging
from io import StringIO
from psycopg2 import IntegrityError
from odoo import http, _, fields
from odoo.http import request
from odoo.addons.website_slides.controllers.main import WebsiteSlides

_logger = logging.getLogger(__name__)


class WebsiteSlidesExtended(WebsiteSlides):
    """
    Extension du contrôleur principal de website_slides
    pour supporter les questions ouvertes avec correction IA
    """

    @http.route(['/slides/slide/<model("slide.slide"):slide>'],
                type='http', auth='public', website=True, sitemap=False)
    def slide_view(self, slide, **kwargs):
        """
        Override : Si c'est un quiz et qu'il contient nos types custom,
        on utilise notre template personnalisé.
        """
        if slide.slide_category == 'quiz' and slide.question_ids:
            has_custom_types = any(
                q.x_question_type in ['simple_choice', 'true_false', 'text_box']
                for q in slide.question_ids
            )
            if has_custom_types:
                _logger.info("Affichage du quiz personnalisé : %s", slide.name)
                return request.render('odoo_gpt_integration.quiz_page_custom', {
                    'slide': slide,
                    'channel': slide.channel_id,
                    'main_object': slide,
                })

        return super().slide_view(slide, **kwargs)

    from odoo import http, fields, _
    from odoo.http import request
    import logging

    _logger = logging.getLogger(__name__)

    @http.route(['/slides/slide/<model("slide.slide"):slide>/quiz/submit'],
                type='json', auth='user', website=True, csrf=False)
    def slide_quiz_submit(self, slide, **kwargs):
        partner = request.env.user.partner_id
        if not partner:
            return {'error': 'no_partner'}

        SlidePartner = request.env['slide.slide.partner'].sudo()
        Pending = request.env['slide.question.pending.answer'].sudo()

        slide_partner = SlidePartner.search([
            ('slide_id', '=', slide.id),
            ('partner_id', '=', partner.id)
        ], limit=1)

        attempts_before = int(slide_partner.quiz_attempts_count or 0) if slide_partner else 0
        max_attempts = int(slide.x_quiz_max_attempts or 0)

        # 1) Bloquer si max atteint (0 = illimité)
        if max_attempts > 0 and attempts_before >= max_attempts:
            return {
                'error': 'max_attempts_reached',
                'attempts': attempts_before,
                'max_attempts': max_attempts,
                'message': _("Vous avez atteint le nombre maximum de tentatives pour ce quiz.")
            }

        # 2) Tentative courante (incrémentée)
        attempt_no = attempts_before + 1

        if not slide.question_ids:
            return {'error': 'no_questions'}

        # 3) Idempotence: si cette tentative existe déjà => double clic / retry => on bloque sans consommer une nouvelle tentative
        already = Pending.search([
            ('user_id', '=', request.env.user.id),
            ('attempt_no', '=', attempt_no),
            ('question_id', 'in', slide.question_ids.ids),
        ], limit=1)
        if already:
            return {
                'error': 'duplicate_submission',
                'message': _("Réponse déjà enregistrée pour cette tentative.")
            }

        results = {}
        pending_count = 0
        graded_points_sum = 0.0
        graded_questions_count = 0
        rows_to_create = []

        for question in slide.question_ids:
            qid = str(question.id)

            # --- lecture réponse ---
            user_answer = None
            if question.x_question_type in ['simple_choice', 'true_false']:
                raw = kwargs.get(f'answer_ids_{qid}')
                if isinstance(raw, (list, tuple)):
                    raw = raw[0] if raw else None
                if raw not in (None, '', False):
                    try:
                        user_answer = int(raw)
                    except Exception:
                        user_answer = None

            elif question.x_question_type == 'text_box':
                user_answer = (kwargs.get(f'text_answer_{qid}') or '').strip()

            # --- skipped ---
            if not user_answer:
                results[qid] = {
                    'skipped': True,
                    'pending': False,
                    'is_correct': False,
                    'score_100': 0,
                    'feedback': _("Aucune réponse fournie."),
                    'question_type': question.x_question_type,
                    'question_text': question.question,
                }
                graded_questions_count += 1
                continue

            # --- correction ---
            result = question._check_answer(user_answer, user_id=request.env.user.id)

            create_pending = bool(result.get('create_pending')) or (result.get('state') == 'pending')
            is_pending = create_pending

            if is_pending:
                pending_count += 1

            is_correct = bool(result.get('answer_is_correct', False))
            score_100 = None

            # score utilisé en “graded” seulement
            if not is_pending:
                if question.x_question_type in ['simple_choice', 'true_false']:
                    score_100 = 100.0 if is_correct else 0.0
                else:
                    score_100 = float(result.get('answer_score') or 0.0)

                graded_points_sum += score_100
                graded_questions_count += 1

            # --- construire ligne DB (pending.answer) ---
            row = {
                'question_id': question.id,
                'partner_id': partner.id,
                'user_id': request.env.user.id,
                'attempt_no': attempt_no,
                'answer_id': user_answer if question.x_question_type in ['simple_choice', 'true_false'] else False,
                'text_answer': user_answer if question.x_question_type == 'text_box' else False,
                'state': 'pending' if is_pending else 'validated',

                # suggestion / feedback
                'is_correct': is_correct if not is_pending else False,
                'score': int(result.get('suggested_score') or result.get('answer_score') or 0),
                'feedback': (result.get('suggested_feedback') or result.get('answer_feedback') or ''),
                'gpt_ideal_answer': result.get('gpt_ideal_answer') or False,
            }

            # si c’est “graded”, on peut remplir final_*
            if not is_pending:
                final_score = int(score_100 or 0)
                row.update({
                    'final_score': final_score,
                    'final_feedback': (result.get('answer_feedback') or ''),
                    'validated_by': request.env.user.id,
                    'validated_date': fields.Datetime.now(),
                })

            rows_to_create.append(row)

            results[qid] = {
                'pending': is_pending,
                'is_correct': None if is_pending else is_correct,
                'score_100': None if is_pending else round(score_100, 2),
                'feedback': result.get('answer_feedback', ''),
                'question_type': question.x_question_type,
                'question_text': question.question,
                'message': _("En attente de correction par l'enseignant") if is_pending else '',
            }

        # 4) Écriture DB atomique
        try:
            with request.env.cr.savepoint():
                if rows_to_create:
                    Pending.create(rows_to_create)
        except IntegrityError:
            request.env.cr.rollback()
            return {
                'error': 'duplicate_submission',
                'message': _("Réponse déjà enregistrée pour cette tentative.")
            }

        # 5) écrire quiz_attempts_count (après succès)
        if not slide_partner:
            slide_partner = SlidePartner.create({
                'slide_id': slide.id,
                'partner_id': partner.id,
                'quiz_attempts_count': attempt_no,
            })
        else:
            slide_partner.write({'quiz_attempts_count': attempt_no})

        # 6) calcul score quiz (sur questions corrigées uniquement)
        percentage = (graded_points_sum / (graded_questions_count * 100.0) * 100.0) if graded_questions_count else 0.0
        passing_threshold = 80.0
        passed = False if pending_count > 0 else (percentage >= passing_threshold)
        message_key = 'pending' if pending_count > 0 else ('passed' if passed else 'failed')

        vals = {}
        if 'quiz_score' in slide_partner._fields:
            vals['quiz_score'] = float(percentage)
        if 'completed' in slide_partner._fields:
            vals['completed'] = bool(passed and pending_count == 0)
        if vals:
            slide_partner.write(vals)

        return {
            'results': results,
            'percentage': round(percentage, 2),
            'passed': passed,
            'pending_count': pending_count,
            'graded_questions_count': graded_questions_count,
            'message_key': message_key,
            'global_message': self._get_global_message(pending_count, graded_questions_count, percentage, passed),
            'attempts': attempt_no,
            'max_attempts': max_attempts,
        }

    def _get_global_message(self, pending_count, graded_count, percentage, passed):
        """Retourne un message global basé sur l'état de correction"""
        if pending_count > 0:
            if graded_count == 0:
                return {
                    'type': 'info',
                    'title': _("Vos réponses sont en attente de correction"),
                    'body': _(
                        "Toutes vos réponses ({pending_count} question(s)) sont en cours de validation par l'enseignant.").format(
                        pending_count=pending_count),
                    'details': _("Vous recevrez une notification dès que vos réponses auront été corrigées."),
                    'show_score': False
                }
            else:
                return {
                    'type': 'warning',
                    'title': _("Correction partielle"),
                    'body': _(
                        "{graded_count} question(s) ont été corrigées, {pending_count} sont en attente de validation.").format(
                        graded_count=graded_count, pending_count=pending_count),
                    'details': _("Score actuel : {percentage}%").format(percentage=round(percentage, 2)),
                    'show_score': True
                }
        else:
            if passed:
                return {
                    'type': 'success',
                    'title': _("Quiz réussi !"),
                    'body': _("Félicitations ! Vous avez obtenu {percentage}%.").format(
                        percentage=round(percentage, 2)),
                    'details': _("Vous pouvez passer au chapitre suivant."),
                    'show_score': True
                }
            else:
                return {
                    'type': 'danger',
                    'title': _("Quiz à réviser"),
                    'body': _("Vous avez obtenu {percentage}%.").format(percentage=round(percentage, 2)),
                    'details': _("Révisez le cours et réessayez."),
                    'show_score': True
                }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _register_quiz_attempt(self, slide, percentage, passed, pending_count=0):
        """
        Enregistre les résultats du quiz (score, état),
        sans gérer le nombre de tentatives (fait AVANT la correction).
        """
        try:
            partner = request.env.user.partner_id
            if not partner:
                _logger.warning("Utilisateur sans partner_id - tentative non enregistrée")
                return

            SlidePartner = request.env['slide.slide.partner'].sudo()
            slide_partner = SlidePartner.search([
                ('slide_id', '=', slide.id),
                ('partner_id', '=', partner.id)
            ], limit=1)

            if not slide_partner:
                _logger.warning(
                    "slide.slide.partner introuvable (slide=%s, partner=%s)",
                    slide.id, partner.id
                )
                return

            vals = {
                'quiz_score': float(percentage),
                'completed': bool(passed and pending_count == 0),
            }

            # Écrire uniquement les champs existants
            vals = {k: v for k, v in vals.items() if k in slide_partner._fields}

            slide_partner.write(vals)

            _logger.info(
                "QUIZ RESULT saved slide=%s partner=%s score=%.2f completed=%s",
                slide.id, partner.id, percentage, vals.get('completed')
            )

        except Exception as e:
            _logger.error(
                "Erreur enregistrement résultat quiz slide=%s : %s",
                slide.id, str(e), exc_info=True
            )


class WebsiteSlidesAI(http.Controller):
    """
    Contrôleur pour les fonctionnalités IA additionnelles
    """

    @http.route(['/slides/question/<int:question_id>/hint'],
                type='json', auth='user', website=True, csrf=False)
    def get_question_hint(self, question_id, **kwargs):
        question = request.env['slide.question'].sudo().browse(question_id)
        if not question.exists():
            return {'error': 'question_not_found'}

        # Si le prof a mis un indice
        hint = (getattr(question, 'x_hint', '') or '').strip()
        if hint:
            return {'hint': hint}

        # Fallback
        if getattr(question, 'x_ai_generated', False) and getattr(question, 'x_ai_source_reference', False):
            return {'hint': _("💡 Indice : Cette question porte sur %s") % question.x_ai_source_reference}

        return {'hint': _("💡 Indice : Relisez attentivement le chapitre associé.")}

    @http.route(['/slides/question/<int:question_id>/ai_feedback'],
                type='json', auth='user', website=True, csrf=False)
    def get_ai_feedback_draft(self, question_id, draft_answer=None, **kwargs):
        question = request.env['slide.question'].sudo().browse(question_id)
        if not question.exists():
            return {'error': 'question_not_found'}
        if question.x_question_type != 'text_box':
            return {'error': 'not_open_ended'}
        if not getattr(question, 'is_ai_corrected', False):
            return {'error': 'ai_correction_disabled'}

        return self._analyze_draft_answer(question, draft_answer or "")

    def _analyze_draft_answer(self, question, draft_answer):
        if not draft_answer or len(draft_answer.strip()) < 10:
            return {
                'status': 'too_short',
                'message': _("Votre réponse semble trop courte. Développez votre argumentation."),
                'progress': 0
            }

        include_keywords = []
        if getattr(question, 'ai_include_keywords', False):
            import re
            include_keywords = [
                kw.strip().lower()
                for kw in re.split(r'[,;\n]+', question.ai_include_keywords)
                if kw.strip()
            ]

        draft_lower = draft_answer.lower()
        found_keywords = [kw for kw in include_keywords if kw in draft_lower]

        if include_keywords:
            progress = int((len(found_keywords) / len(include_keywords)) * 100)
        else:
            word_count = len(draft_answer.split())
            progress = min(int((word_count / 50) * 100), 100)

        if progress < 30:
            status = 'weak'
            missing = [kw for kw in include_keywords if kw not in found_keywords][:3]
            message = _("🔴 Votre réponse manque d'éléments clés. Pensez à mentionner : %s") % ', '.join(missing)
        elif progress < 70:
            status = 'medium'
            missing = [kw for kw in include_keywords if kw not in found_keywords][:2]
            message = (_("🟡 Votre réponse est sur la bonne voie. Essayez d'inclure : %s") % ', '.join(
                missing)) if missing \
                else _("🟡 Votre réponse est correcte. Développez encore un peu.")
        else:
            status = 'good'
            message = _("🟢 Votre réponse semble complète !")

        return {
            'status': status,
            'message': message,
            'progress': progress,
            'found_keywords': found_keywords,
            'missing_keywords': [kw for kw in include_keywords if kw not in found_keywords]
        }


class SlideSlidePartnerStats(http.Controller):
    """
    Contrôleur pour le suivi de progression des étudiants
    """

    @http.route(['/slides/my_progress/<int:channel_id>'],
                type='http', auth='user', website=True)
    def my_progress(self, channel_id, **kwargs):
        channel = request.env['slide.channel'].browse(channel_id)
        partner = request.env.user.partner_id
        if not channel.exists() or not partner:
            return request.redirect('/slides')

        slide_partners = request.env['slide.slide.partner'].search([
            ('partner_id', '=', partner.id),
            ('slide_id.channel_id', '=', channel_id),
            ('slide_id.slide_category', '=', 'quiz')
        ])

        total_quizzes = len(slide_partners)
        completed_quizzes = len(slide_partners.filtered('completed')) if 'completed' in slide_partners._fields else 0

        if slide_partners and 'quiz_score' in slide_partners._fields:
            average_score = sum(slide_partners.mapped('quiz_score')) / len(slide_partners)
        else:
            average_score = 0

        total_attempts = sum(slide_partners.mapped(
            'quiz_attempts_count')) if slide_partners and 'quiz_attempts_count' in slide_partners._fields else 0

        return request.render('odoo_gpt_integration.student_progress_page', {
            'channel': channel,
            'stats': {
                'total_quizzes': total_quizzes,
                'completed_quizzes': completed_quizzes,
                'average_score': round(average_score, 1),
                'total_attempts': total_attempts,
            },
            'slide_partners': slide_partners,
        })

    @http.route(['/slides/question/<int:question_id>/reset'],
                type='json', auth='user', website=True, csrf=False)
    def reset_question_attempt(self, question_id, **kwargs):
        question = request.env['slide.question'].browse(question_id)
        if not question.exists():
            return {'error': 'question_not_found'}

        # Permissions : mieux que base.group_user
        if not (request.env.user.has_group('website_slides.group_website_slides_officer')
                or request.env.user.has_group('website_slides.group_website_slides_manager')):
            return {'error': 'permission_denied'}

        try:
            question.sudo().write({
                'ai_correction_attempts': 0,
                'ai_last_correction_error': False,
            })
            return {'success': True, 'message': _('Question réinitialisée avec succès')}
        except Exception as e:
            _logger.error("Erreur reset question %s: %s", question_id, str(e), exc_info=True)
            return {'error': str(e)}


class SlideQuizExport(http.Controller):
    """
    Contrôleur pour l'export des résultats de quiz
    """

    @http.route(['/slides/quiz/<int:slide_id>/export/csv'],
                type='http', auth='user', website=True)
    def export_quiz_results_csv(self, slide_id, **kwargs):
        slide = request.env['slide.slide'].browse(slide_id)
        if not slide.exists() or slide.slide_category != 'quiz':
            return request.redirect('/slides')

        if not (request.env.user.has_group('website_slides.group_website_slides_officer')
                or request.env.user.has_group('website_slides.group_website_slides_manager')):
            return request.redirect('/slides')

        slide_partners = request.env['slide.slide.partner'].search([('slide_id', '=', slide_id)])

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(['Étudiant', 'Email', 'Score', 'Tentatives', 'Réussi', 'Date dernière tentative'])

        for sp in slide_partners:
            score = getattr(sp, 'quiz_score', 0.0)
            attempts = getattr(sp, 'quiz_attempts_count', 0)
            completed = getattr(sp, 'completed', False)

            writer.writerow([
                sp.partner_id.name,
                sp.partner_id.email or '',
                f"{float(score):.1f}%",
                attempts,
                'Oui' if completed else 'Non',
                sp.write_date.strftime('%Y-%m-%d %H:%M') if sp.write_date else ''
            ])

        csv_data = output.getvalue()
        output.close()

        headers = [
            ('Content-Type', 'text/csv; charset=utf-8'),
            ('Content-Disposition', f'attachment; filename="quiz_{slide.id}_results.csv"')
        ]
        return request.make_response(csv_data, headers)

    @http.route(['/slides/my_results'],
                type='http', auth='user', website=True, sitemap=False)
    def my_quiz_results(self, channel_id=None, slide_id=None, state=None, **kwargs):
        """
        Page pour que l'étudiant voie TOUS ses résultats
        Support des filtres : cours, quiz, statut
        """
        partner = request.env.user.partner_id

        # Construction du domaine de recherche avec filtres
        domain = [('user_id', '=', request.env.user.id)]

        # Filtre par cours
        if channel_id:
            try:
                domain.append(('channel_id', '=', int(channel_id)))
            except (ValueError, TypeError):
                pass

        # Filtre par quiz spécifique
        if slide_id:
            try:
                domain.append(('slide_id', '=', int(slide_id)))
            except (ValueError, TypeError):
                pass

        # Filtre par statut
        if state and state in ['pending', 'validated', 'corrected', 'rejected']:
            domain.append(('state', '=', state))

        # Récupérer les réponses filtrées
        pending_answers = request.env['slide.question.pending.answer'].search(
            domain,
            order='create_date DESC'
        )

        # Statistiques (sur les résultats filtrés)
        total_answers = len(pending_answers)
        pending_answers_count = len(pending_answers.filtered(lambda a: a.state == 'pending'))
        corrected_answers = len(pending_answers.filtered(lambda a: a.state in ['validated', 'corrected']))

        # Calculer le score moyen (si disponible)
        # Score moyen basé sur pending_answer UNIQUEMENT,
        # en prenant LA DERNIÈRE réponse corrigée pour chaque question (par quiz)
        corrected = pending_answers.filtered(
            lambda a: a.state in ['validated', 'corrected'] and a.final_score is not False
        )

        # key = (slide_id, question_id) -> garder la dernière tentative / dernière date
        latest_by_question = {}
        for a in corrected:
            key = (a.slide_id.id if a.slide_id else False, a.question_id.id if a.question_id else False)

            prev = latest_by_question.get(key)
            if not prev:
                latest_by_question[key] = a
                continue

            # critère "plus récent" : attempt_no d'abord, sinon create_date
            a_attempt = int(a.attempt_no or 0)
            p_attempt = int(prev.attempt_no or 0)

            if a_attempt > p_attempt:
                latest_by_question[key] = a
            elif a_attempt == p_attempt and a.create_date and prev.create_date and a.create_date > prev.create_date:
                latest_by_question[key] = a

        latest_scores = [float(rec.final_score or 0.0) for rec in latest_by_question.values()]
        avg_score = (sum(latest_scores) / len(latest_scores)) if latest_scores else 0.0

        return request.render('odoo_gpt_integration.my_quiz_results_page', {
            'partner': partner,
            'pending_answers': pending_answers,
            'total_answers': total_answers,
            'pending_answers_count': pending_answers_count,
            'corrected_answers': corrected_answers,
            'avg_score': round(avg_score, 1),
            'user': request.env.user,
            # Passer les paramètres de filtre pour les conserver dans la vue
            'filter_channel_id': channel_id,
            'filter_slide_id': slide_id,
            'filter_state': state,
        })

    @http.route(['/slides/result/<int:answer_id>/details'],
                type='http', auth='user', website=True, sitemap=False)
    def answer_details(self, answer_id, **kwargs):
        """
        Page de détail d'une réponse spécifique
        """
        pending_answer = request.env['slide.question.pending.answer'].search([
            ('id', '=', answer_id),
            ('user_id', '=', request.env.user.id)  # Sécurité : seulement ses propres réponses
        ], limit=1)

        if not pending_answer:
            return request.redirect('/slides/my_results')

        return request.render('odoo_gpt_integration.answer_details_page', {
            'answer': pending_answer,
            'question': pending_answer.question_id,
            'channel': pending_answer.channel_id,
        })

    @http.route('/slides/my_results/pending_count', type='json', auth='user', website=True, csrf=False)
    def pending_count(self, slide_id=None, **kw):
        partner = request.env.user.partner_id
        dom = [('partner_id', '=', partner.id), ('state', '=', 'pending')]
        if slide_id:
            dom.append(('slide_id', '=', int(slide_id)))

        count = request.env['slide.question.pending.answer'].sudo().search_count(dom)
        return {'pending_count': count}
