/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Widget Quiz E-Learning avec IA
 * Support complet des 3 types de questions avec correction auto/manuelle
 * Aligné sur la logique du contrôleur main.py
 */

publicWidget.registry.PortalResultsWidget = publicWidget.Widget.extend({
    selector: ".o_wslides_lesson_main, .o_wslides_slides_list_slide",

    events: {
        "click .js-refresh-stats": "_onRefreshStats",
        "mouseenter .btn-outline-primary": "_onButtonHover",
    },

    start: function () {
        return this._super.apply(this, arguments).then(() => {
            this._loadPendingCount();
            this._setupTooltips();
        });
    },

    /**
     * Charge le nombre de réponses en attente
     * Affiche un badge dynamique
     */
    _loadPendingCount: function () {
        const self = this;

        // Ne charger que si l'utilisateur est connecté
        if (!this._isLoggedIn()) {
            return;
        }

        const slideId = this._getCurrentSlideId(); // Récupère l'ID du slide actuel

        $.ajax({
            url: '/slides/my_results/pending_count',
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: { slide_id: slideId || false }, // Passer le slide_id (ou false pour global)
            }),
            success: function (response) {
                const result = response.result || {};
                const pendingCount = result.pending_count || 0;

                if (pendingCount > 0) {
                    self._displayPendingBadge(pendingCount, slideId);
                }
            },
            error: function (error) {
                console.log('Unable to load pending count:', error);
            }
        });
    },

    /**
     * Affiche un badge avec le nombre de réponses en attente
     */
    _displayPendingBadge: function (count, slideId) {
        const title = slideId
            ? `${count} réponse(s) en attente pour ce quiz`
            : `${count} réponse(s) en attente de correction`;

        // 1) Page quiz fullscreen : bouton "Voir détails"
        const $targets = this.$('a[href*="/slides/my_results"], button.js-open-results');

        // Si rien trouvé dans ce widget root, fallback global DOM
        const $finalTargets = $targets.length ? $targets : $('a[href*="/slides/my_results"]');

        $finalTargets.each(function () {
            const $el = $(this);

            if ($el.find('.pending-count-badge').length > 0) return;

            const $badge = $('<span>')
                .addClass('badge bg-warning ms-2 pending-count-badge')
                .attr('title', title)
                .attr('data-bs-toggle', 'tooltip')
                .text(count);

            $el.append($badge);
        });
    },

    _getCurrentSlideId: function () {
        // Extrait l'ID du slide depuis l'URL
        const m = window.location.pathname.match(/\/slides\/slide\/.*-(\d+)$/);
        return m ? parseInt(m[1]) : null;
    },

    _onRefreshStats: function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);

        $btn.html('<i class="fa fa-spinner fa-spin"></i> Chargement...')
            .prop('disabled', true);

        setTimeout(() => window.location.reload(), 500);
    },

    _onButtonHover: function (ev) {
        const $btn = $(ev.currentTarget);
        $btn.addClass('shadow-sm');
        $btn.one('mouseleave', function () {
            $btn.removeClass('shadow-sm');
        });
    },

    /**
     * Active les tooltips Bootstrap
     */
    _setupTooltips: function () {
        const Bootstrap = window.bootstrap;

        if (!Bootstrap || !Bootstrap.Tooltip) {
            console.warn("Bootstrap tooltips not available. Skipping tooltips init.");
            return;
        }

        this.$('[data-bs-toggle="tooltip"]').each(function () {
            try {
                Bootstrap.Tooltip.getOrCreateInstance(this);
            } catch (e) {
                new Bootstrap.Tooltip(this);
            }
        });
    },

    _isLoggedIn: function () {
        return $('.o_portal_navbar').length > 0 || $('header .js_usermenu').length > 0;
    },
});

export default publicWidget.registry.PortalResultsWidget;
