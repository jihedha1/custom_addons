/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Widget Quiz E-Learning avec IA
 * Support complet des 3 types de questions avec correction auto/manuelle
 * Aligné sur la logique du contrôleur main.py
 */

publicWidget.registry.QuizWidget = publicWidget.Widget.extend({
    selector: '.o_wslides_lesson_content_type_quiz',
    xmlDependencies: ['/website_slides/static/src/xml/slide_fullscreen.xml'],

    events: {
        'click .o_wslides_quiz_submit': '_onSubmitQuiz',
        'input .question-text-answer': '_onTextAnswerInput',
        'click .btn-show-hint': '_onShowHint',
        'change input.question-answer': '_onAnswerChange',
        'click .o_wslides_quiz_continue': '_onContinueCourse',
    },

    /**
     * Initialisation
     */
    start: function () {
        return this._super.apply(this, arguments).then(() => {
            this._setupAIFeedback();
            this._initializeQuestions();
            this._restoreProgress();
        });
    },

    /**
     * Configure le feedback IA en temps réel pour les questions ouvertes
     */
    _setupAIFeedback: function () {
        const self = this;

        this.$('.question-text-answer[data-ai-enabled="true"]').each(function () {
            const $textarea = $(this);
            const questionId = $textarea.attr('name').replace('text_answer_', '');
            const $feedback = $textarea.closest('.question-openended').find('.ai-feedback-live');

            let debounceTimer;

            $textarea.on('input', function () {
                clearTimeout(debounceTimer);
                const draftAnswer = $textarea.val();

                // Masquer le feedback si trop court
                if (draftAnswer.length < 20) {
                    $feedback.hide();
                    return;
                }

                $feedback.show();

                // Attendre 1.5 secondes avant d'analyser
                debounceTimer = setTimeout(function () {
                    self._getAIFeedbackDraft(questionId, draftAnswer, $feedback);
                }, 1500);
            });
        });
    },

    /**
     * Obtient un feedback IA en temps réel
     */
    _getAIFeedbackDraft: function (questionId, draftAnswer, $feedbackContainer) {
        $.ajax({
            url: '/slides/question/' + questionId + '/ai_feedback',
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    draft_answer: draftAnswer
                }
            }),
            success: function (response) {
                const result = response.result || {};
                if (result.error) {
                    console.warn('AI feedback error:', result.error);
                    return;
                }

                const $progressBar = $feedbackContainer.find('.progress-bar');
                const $progressText = $feedbackContainer.find('.progress-text');
                const $message = $feedbackContainer.find('.feedback-message');
                const progress = result.progress || 0;
                const status = result.status || 'weak';

                // Mise à jour de la couleur selon le statut
                $progressBar.removeClass('bg-danger bg-warning bg-success');
                if (status === 'weak') {
                    $progressBar.addClass('bg-danger');
                } else if (status === 'medium') {
                    $progressBar.addClass('bg-warning');
                } else {
                    $progressBar.addClass('bg-success');
                }

                $progressBar.css('width', progress + '%');
                $progressText.text(progress + '%');
                $message.html(result.message);
            },
            error: function (error) {
                console.error('Error getting AI feedback:', error);
            }
        });
    },

    /**
     * Initialise l'affichage des questions
     */
    _initializeQuestions: function () {
        // Numérotation automatique
        this.$('.slide-question').each(function (index) {
            const $title = $(this).find('.question-title');
            if ($title.find('.question-number').length === 0) {
                $title.prepend(
                    `<span class="question-number badge bg-primary me-2">Question ${index + 1}</span>`
                );
            }
        });

        // Effet hover sur les réponses
        this.$('.form-check, .btn-group-toggle label').hover(
            function () { $(this).addClass('shadow-sm'); },
            function () { $(this).removeClass('shadow-sm'); }
        );

        // Compteur de mots pour les questions ouvertes
        this.$('.question-text-answer').each(function () {
            const $textarea = $(this);
            const $counter = $('<small class="text-muted d-block mt-1">0 mots</small>');
            $textarea.after($counter);

            $textarea.on('input', function () {
                const wordCount = $(this).val().trim().split(/\s+/).filter(w => w.length > 0).length;
                $counter.text(wordCount + ' mot' + (wordCount > 1 ? 's' : ''));
            });
        });
    },

    /**
     * Restaure la progression (si localStorage disponible)
     */
    _restoreProgress: function () {
        // Note: localStorage n'est pas disponible dans les artifacts Claude
        // Mais garde la logique pour l'environnement Odoo réel
        if (typeof localStorage === 'undefined') return;

        const slideId = this._getSlideId();
        if (!slideId) return;

        const savedAnswers = localStorage.getItem('quiz_progress_' + slideId);
        if (savedAnswers) {
            try {
                const answers = JSON.parse(savedAnswers);
                Object.keys(answers).forEach(questionId => {
                    const answer = answers[questionId];
                    if (answer.type === 'choice') {
                        this.$('input[name="answer_ids_' + questionId + '"][value="' + answer.value + '"]').prop('checked', true);
                    } else if (answer.type === 'text') {
                        this.$('textarea[name="text_answer_' + questionId + '"]').val(answer.value);
                    }
                });
            } catch (e) {
                console.error('Error restoring progress:', e);
            }
        }
    },

    /**
     * Sauvegarde la progression (si localStorage disponible)
     */
    _saveProgress: function () {
        if (typeof localStorage === 'undefined') return;

        const slideId = this._getSlideId();
        if (!slideId) return;

        const answers = this._collectAnswers();
        try {
            localStorage.setItem('quiz_progress_' + slideId, JSON.stringify(answers));
        } catch (e) {
            console.error('Error saving progress:', e);
        }
    },

    /**
     * Handler pour le changement de réponse
     */
    _onAnswerChange: function (ev) {
        this._saveProgress();
    },

    /**
     * Handler pour l'input de texte
     */
    _onTextAnswerInput: function (ev) {
        this._saveProgress();
    },

    /**
     * Gère la soumission du quiz
     */
    _onSubmitQuiz: function (ev) {
        ev.preventDefault();
        const self = this;

        // Validation
        if (!this._validateAnswers()) {
            this._showNotification(
                'Attention',
                'Veuillez répondre à toutes les questions avant de soumettre.',
                'warning'
            );
            return;
        }

        // Confirmation
        if (!confirm('Êtes-vous sûr de vouloir soumettre vos réponses ? Cette action est définitive.')) {
            return;
        }

        this._showLoader();

        const slideId = this._getSlideId();
        if (!slideId) {
            this._hideLoader();
            this._showNotification('Erreur', 'Impossible de déterminer le quiz.', 'danger');
            return;
        }

        // Préparation des données selon le format attendu par main.py
        const answers = this._collectAnswers();
        const params = {};

        Object.keys(answers).forEach(function (questionId) {
            const answer = answers[questionId];
            if (answer.type === 'choice') {
                // Format: answer_ids_123 = "456"
                params['answer_ids_' + questionId] = String(answer.value);
            } else if (answer.type === 'text') {
                // Format: text_answer_123 = "contenu"
                params['text_answer_' + questionId] = answer.value;
            }
        });

        // Soumission
        $.ajax({
            url: `/slides/slide/${slideId}/quiz/submit`,
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: params
            }),
            success: function (response) {
                self._hideLoader();
                const result = response.result || {};

                if (result.error) {
                    // Afficher le message serveur si disponible
                    const msg = result.message || 'Une erreur est survenue lors de la soumission.';
                    self._showNotification('Erreur', msg, 'danger');

                    // Bonus : afficher attempts/max si présents
                    if (result.max_attempts !== undefined && result.attempts !== undefined) {
                        console.warn(`Quiz attempts: ${result.attempts}/${result.max_attempts}`);
                    }
                    return;
                }

                // Nettoyage de la progression sauvegardée
                if (typeof localStorage !== 'undefined') {
                    localStorage.removeItem('quiz_progress_' + slideId);
                }

                self._displayResults(result);
            },
            error: function (xhr, status, error) {
                self._hideLoader();
                console.error('Quiz submission error:', error);
                self._showNotification(
                    'Erreur',
                    'Impossible de soumettre le quiz. Veuillez vérifier votre connexion et réessayer.',
                    'danger'
                );
            }
        });
    },

    /**
     * Collecte toutes les réponses du quiz
     */
    _collectAnswers: function () {
        const answers = {};

        // Questions à choix (QCM et Vrai/Faux)
        this.$('input.question-answer:checked').each(function () {
            const $input = $(this);
            const nameMatch = $input.attr('name').match(/answer_ids_(\d+)/);
            if (!nameMatch) return;

            const questionId = nameMatch[1];
            const answerId = parseInt($input.val());

            if (!answers[questionId]) {
                answers[questionId] = {
                    type: 'choice',
                    value: $input.attr('type') === 'checkbox' ? [] : null
                };
            }

            if ($input.attr('type') === 'checkbox') {
                // Support multi-choix (si implémenté plus tard)
                answers[questionId].value.push(answerId);
            } else {
                answers[questionId].value = answerId;
            }
        });

        // Questions ouvertes
        this.$('textarea.question-text-answer').each(function () {
            const $textarea = $(this);
            const nameMatch = $textarea.attr('name').match(/text_answer_(\d+)/);
            if (!nameMatch) return;

            const questionId = nameMatch[1];
            const text = $textarea.val().trim();

            if (text) {
                answers[questionId] = {
                    type: 'text',
                    value: text
                };
            }
        });

        return answers;
    },

    /**
     * Valide que toutes les questions ont une réponse
     */
    _onContinueCourse: function (ev) {
        ev.preventDefault();

        // 1) Essayer de réutiliser le bouton "Next" natif Odoo (selon template / version)
        const $next =
            $('a.o_wslides_lesson_next:visible').first()
            .add($('a.o_wslides_lesson_navigation_next:visible').first())
            .add($('a[data-slide-action="next"]:visible').first())
            .add($('a[accesskey="n"]:visible').first())
            .add($('a[rel="next"]:visible').first())
            .filter(function () {
                const href = $(this).attr('href');
                return href && href !== '#';
            })
            .first();

        if ($next.length) {
            window.location.href = $next.attr('href');
            return;
        }

        // 2) Fallback : si on ne trouve pas le lien "next", renvoyer vers le cours
        // (au moins l’utilisateur ne reste pas bloqué)
        const channelId = this.$el.data('channel-id') || this.$el.closest('[data-channel-id]').data('channel-id');
        if (channelId) {
            window.location.href = `/slides/${channelId}`;
            return;
        }

        // 3) Dernier fallback : page cours
        window.location.href = '/slides';
    },

    _validateAnswers: function () {
        let allAnswered = true;

        this.$('.slide-question').each(function () {
            const $question = $(this);
            const hasChoiceAnswer = $question.find('input.question-answer:checked').length > 0;
            const $textarea = $question.find('textarea.question-text-answer');
            const hasTextAnswer = $textarea.length > 0 && $textarea.val().trim() !== '';

            if (!hasChoiceAnswer && !hasTextAnswer) {
                allAnswered = false;
                $question.addClass('border-danger border-3');

                // Scroll vers la première question manquante
                if (allAnswered === false) {
                    $('html, body').animate({
                        scrollTop: $question.offset().top - 100
                    }, 500);
                }

                setTimeout(() => $question.removeClass('border-danger border-3'), 3000);
            }
        });

        return allAnswered;
    },

    /**
     * Affiche les résultats du quiz
     * Gère les 3 cas: correction automatique, en attente, et erreur
     */
    _displayResults: function (result) {
        const self = this;

        // Masquer le formulaire
        this.$('.o_wslides_quiz_form').hide();

        // Afficher le score global en premier
        this._displayGlobalScore(result);

        // Afficher les résultats individuels
        if (result.results) {
            Object.keys(result.results).forEach(function (questionId) {
                const questionResult = result.results[questionId];
                const $question = self.$(`.slide-question[data-question-id="${questionId}"]`);
                if ($question.length === 0) return;

                // Créer ou récupérer la zone de feedback
                let $feedback = $question.find('.question-feedback');
                if ($feedback.length === 0) {
                    $feedback = $('<div class="question-feedback mt-3"></div>');
                    $question.find('.card-body').append($feedback);
                }

                // Construire le contenu du feedback
                let feedbackHtml = '';

                if (questionResult.pending) {
                    // Mode manuel - En attente de validation
                    feedbackHtml = `
                        <div class="alert alert-info">
                            <div class="d-flex align-items-center">
                                <i class="fa fa-clock-o fa-2x me-3"></i>
                                <div>
                                    <h5 class="mb-1">⏳ En attente de validation</h5>
                                    <p class="mb-0">
                                        Votre réponse a été enregistrée et sera corrigée par votre enseignant.
                                        Vous recevrez une notification dès que la correction sera disponible.
                                    </p>
                                </div>
                            </div>
                        </div>
                    `;
                } else if (questionResult.skipped) {
                    // Question sautée
                    feedbackHtml = `
                        <div class="alert alert-warning">
                            <i class="fa fa-exclamation-triangle me-2"></i>
                            <strong>Question non répondue</strong>
                        </div>
                    `;
                } else {
                    // Correction automatique
                    const isCorrect = questionResult.is_correct;
                    const score = questionResult.score_100;
                    const alertClass = isCorrect ? 'alert-success' : 'alert-danger';
                    const icon = isCorrect ? '✅' : '❌';
                    const title = isCorrect ? 'Bonne réponse !' : 'Réponse incorrecte';

                    feedbackHtml = `
                        <div class="alert ${alertClass}">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h5 class="mb-0">${icon} ${title}</h5>
                                ${score !== null ? `<span class="badge bg-dark">${Math.round(score)}/100</span>` : ''}
                            </div>
                            ${questionResult.feedback ? `<p class="mb-0">${questionResult.feedback}</p>` : ''}
                        </div>
                    `;
                }

                $feedback.html(feedbackHtml).show();

                // Désactiver les champs
                $question.find('input, textarea, button').prop('disabled', true);
            });
        }

        // Scroll vers le haut
        $('html, body').animate({ scrollTop: this.$el.offset().top - 100 }, 500);
    },

    /**
     * Affiche le score global
     */
    _displayGlobalScore: function (result) {
        const percentage = result.percentage || 0;
        const passed = result.passed || false;
        const pendingCount = result.pending_count || 0;
        const gradedCount = result.graded_questions_count || 0;

        let scoreClass = 'success';
        let icon = '🎉';
        let message = '';

        if (pendingCount > 0) {
            // Il y a des questions en attente
            scoreClass = 'info';
            icon = '⏳';
            message = `Certaines réponses sont en attente de validation enseignant (${pendingCount} question${pendingCount > 1 ? 's' : ''})`;
        } else if (passed) {
            icon = '🎉';
            message = 'Félicitations ! Vous avez réussi ce quiz !';
            scoreClass = 'success';
        } else {
            icon = '📚';
            message = 'Continuez vos efforts ! Révisez et réessayez.';
            scoreClass = percentage >= 50 ? 'warning' : 'danger';
        }

        const $scoreDisplay = $(`<div class="alert alert-${scoreClass} text-center mb-4">`)
            .html(
                `<h3 class="mb-3">${icon} ${message}</h3>
                 ${gradedCount > 0 ? `
                 <div class="score-display my-3">
                     <div class="display-4 fw-bold">${Math.round(percentage)}%</div>
                     <p class="text-muted mb-0">Score sur les questions corrigées (${gradedCount})</p>
                 </div>
                 ` : ''}
                 ${pendingCount > 0 ? `
                 <p class="mb-0">
                     <i class="fa fa-info-circle me-2"></i>
                     ${pendingCount} réponse${pendingCount > 1 ? 's' : ''} en attente de validation
                 </p>
                 ` : ''}`
            );

        // Boutons d'action
        const $actions = $('<div class="text-center mt-3">');
        if (passed && pendingCount === 0) {
            $actions.append(
                '<a href="#" class="btn btn-primary btn-lg"><i class="fa fa-arrow-right me-2"></i>Continuer le cours</a>'
            );
        } else if (pendingCount === 0) {
            $actions.append(
              '<a href="#" class="btn btn-primary btn-lg o_wslides_quiz_continue">' +
              '<i class="fa fa-arrow-right me-2"></i>Continuer le cours</a>'
            );
        } else {
            $actions.append(
              '<a href="#" class="btn btn-primary btn-lg o_wslides_quiz_continue">' +
              '<i class="fa fa-arrow-right me-2"></i>Continuer</a>'
            );
        }

        // AJOUTER CE LIEN POUR ACCÉDER AUX RÉSULTATS
        $actions.append(`
            <div class="mt-3">
                <a href="/slides/my_results" class="btn btn-outline-info btn-sm">
                    <i class="fa fa-list me-1"></i>Voir tous mes résultats
                </a>
            </div>
        `);

        $scoreDisplay.append($actions);
        this.$el.prepend($scoreDisplay);

        // Handler pour réessayer
        $actions.find('.o_wslides_quiz_retry').on('click', (e) => {
            e.preventDefault();
            location.reload();
        });
    },

    /**
     * Affiche un indice pour une question
     */
    _onShowHint: function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const questionId = $btn.data('question-id');

        $.ajax({
            url: '/slides/question/' + questionId + '/hint',
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {}
            }),
            success: function (response) {
                const result = response.result || {};
                if (result.error) return;

                const $hintDisplay = $('<div class="alert alert-info mt-2 hint-display">')
                    .html('<i class="fa fa-lightbulb-o me-2"></i>' + result.hint);

                $btn.closest('.slide-question').find('.card-body').append($hintDisplay);
                $btn.fadeOut();
            },
            error: function (error) {
                console.error('Error getting hint:', error);
            }
        });
    },

    /**
     * Récupère l'ID du slide depuis l'URL ou un attribut
     */

    _getSlideId: function () {
        // Méthode 1: depuis l'URL
        const match = window.location.pathname.match(/\/slides\/slide\/(\d+)/);
        if (match) return parseInt(match[1]);

        // Méthode 2: depuis data-slide-id
        const dataSlideId = this.$el.data('slide-id');
        if (dataSlideId) return parseInt(dataSlideId);

        // Méthode 3: depuis l'action du formulaire
        const $form = this.$el.closest('form');
        const actionMatch = $form.attr('action') ? $form.attr('action').match(/\/(\d+)\//) : null;
        if (actionMatch) return parseInt(actionMatch[1]);

        return null;
    },

    /**
     * Affiche un loader pendant le traitement
     */
    _showLoader: function () {
        if (this.$('.quiz-loader').length > 0) return;

        const $loader = $('<div class="quiz-loader text-center py-5">')
            .html(
                `<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                    <span class="visually-hidden">Correction en cours...</span>
                 </div>
                 <p class="mt-3 text-muted">
                     <i class="fa fa-clock-o me-2"></i>
                     Correction en cours, veuillez patienter...
                 </p>`
            );

        this.$('.o_wslides_quiz_submit').prop('disabled', true);
        this.$el.append($loader);
    },

    /**
     * Masque le loader
     */
    _hideLoader: function () {
        this.$('.quiz-loader').remove();
        this.$('.o_wslides_quiz_submit').prop('disabled', false);
    },

    /**
     * Affiche une notification toast
     */
    _showNotification: function (title, message, type) {
        const alertClass = `alert-${type || 'info'}`;
        const icons = {
            success: 'fa-check-circle',
            danger: 'fa-exclamation-triangle',
            warning: 'fa-exclamation-circle',
            info: 'fa-info-circle'
        };
        const icon = icons[type] || icons.info;

        const $notification = $(`
            <div class="alert ${alertClass} alert-dismissible fade show position-fixed shadow-lg"
                 style="top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 500px;"
                 role="alert">
                <div class="d-flex align-items-start">
                    <i class="fa ${icon} fa-lg me-3 mt-1"></i>
                    <div class="flex-grow-1">
                        <strong>${title}</strong>
                        <p class="mb-0 mt-1">${message}</p>
                    </div>
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            </div>
        `);

        $('body').append($notification);

        setTimeout(() => {
            $notification.fadeOut(300, function() {
                $(this).remove();
            });
        }, 5000);
    },
});

export default publicWidget.registry.QuizWidget;