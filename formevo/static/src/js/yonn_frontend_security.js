/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.FormevoCompletionButton = publicWidget.Widget.extend({
    selector: ".o_wslides_lesson_main, .o_wslides_slides_list_slide, body",

    start: function () {
        return this._super.apply(this, arguments).then(() => {
            this._injectButton();
        });
    },

    _getCurrentSlideId: function () {
        const m = window.location.pathname.match(/\/slides\/slide\/.*-(\d+)(?:\/)?$/);
        return m ? parseInt(m[1]) : null;
    },

    _injectButton: function () {
        if ($(".yonn-completion-btn").length) return;

        const slideId = this._getCurrentSlideId();
        if (!slideId) return;

        const $container =
            $(".o_wslides_slide_content").first()
            .add($(".o_wslides_content").first())
            .add($("main").first())
            .first();

        if (!$container.length) return;

        const $wrapper = $('<div class="mt-3 text-center"></div>');
        const $btn = $(`
            <button type="button"
                    class="btn btn-outline-success yonn-completion-btn"
                    data-slide-id="${slideId}">
                Marquer comme terminé
            </button>
        `);

        $btn.on("click", () => this._toggleCompletion($btn, slideId));

        $wrapper.append($btn);
        $container.append($wrapper);
    },

    _toggleCompletion: function ($btn, slideId) {
        $btn.prop("disabled", true);

        $.ajax({
            url: "/yonn/tracking/toggle_completion",
            type: "POST",
            contentType: "application/json",
            dataType: "json",
            data: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { slide_id: slideId },
            }),
            success: function (response) {
                const result = response.result || response || {};
                const completed = !!result.completed;

                if (completed) {
                    $btn.text("✓ Terminé")
                        .removeClass("btn-outline-success")
                        .addClass("btn-success");
                } else {
                    $btn.text("Marquer comme terminé")
                        .removeClass("btn-success")
                        .addClass("btn-outline-success");
                }
            },
            error: function (err) {
                console.error("[FORMEVO] toggle completion error", err);
            },
            complete: function () {
                $btn.prop("disabled", false);
            },
        });
    },
});

export default publicWidget.registry.FormevoCompletionButton;
