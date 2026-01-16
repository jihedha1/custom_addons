/** @odoo-module **/

console.warn("[FORMEVO] time_tracker loaded");

function getSlideIdFromUrl() {
    // /slides/slide/title-of-slide-42
    const match = window.location.pathname.match(/-(\d+)(?:\/)?$/);
    return match ? parseInt(match[1], 10) : null;
}

function findContainer() {
    // Sans fullscreen : zone juste sous le contenu du slide
    return (
        document.querySelector(".o_wslides_slide_content") ||
        document.querySelector(".o_wslides_slide_main") ||
        document.querySelector(".o_wslides_content")
    );
}

async function callJsonRoute(url, slideId) {
    const resp = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        // JSON-RPC compatible avec @http.route(type='json')
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: { slide_id: slideId },
        }),
    });

    const payload = await resp.json();
    return payload.result || payload;
}

async function toggleCompletion(slideId) {
    return await callJsonRoute("/yonn/tracking/toggle_completion", slideId);
}

async function getCompletionStatus(slideId) {
    return await callJsonRoute("/yonn/tracking/get_completion_status", slideId);
}

function applyButtonState(button, completed) {
    if (completed) {
        button.textContent = "✓ Terminé";
        button.classList.remove("btn-outline-success");
        button.classList.add("btn-success");
    } else {
        button.textContent = "Marquer comme terminé";
        button.classList.remove("btn-success");
        button.classList.add("btn-outline-success");
    }
}

function injectButton() {
    // éviter double injection
    if (document.querySelector(".yonn-completion-btn")) return;

    const slideId = getSlideIdFromUrl();
    if (!slideId) return;

    const container = findContainer();
    if (!container) return;

    const wrapper = document.createElement("div");
    wrapper.className = "yonn-completion-wrapper";
    wrapper.style.textAlign = "center";
    wrapper.style.marginTop = "16px";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-success yonn-completion-btn";
    button.textContent = "Marquer comme terminé";

    // (Optionnel) info texte sous le bouton (date)
    const info = document.createElement("div");
    info.className = "text-muted mt-2";
    info.style.fontSize = "13px";

    wrapper.appendChild(button);
    wrapper.appendChild(info);
    container.appendChild(wrapper);

    // Lock anti multi-clic
    let isToggling = false;

    button.addEventListener("click", async () => {
        if (isToggling) return;
        isToggling = true;
        button.disabled = true;

        try {
            const result = await toggleCompletion(slideId);

            // Certains retours peuvent être {status:'success', completed: bool, completion_date: iso}
            const completed = !!result?.completed;
            applyButtonState(button, completed);

            if (result?.completion_date) {
                info.textContent = "Terminé le " + new Date(result.completion_date).toLocaleString();
            } else {
                info.textContent = "";
            }
        } catch (e) {
            console.error("[FORMEVO] completion error", e);
        } finally {
            button.disabled = false;
            isToggling = false;
        }
    });

    // Etat initial au chargement
    (async () => {
        try {
            const result = await getCompletionStatus(slideId);
            const completed = !!result?.completed;
            applyButtonState(button, completed);

            if (result?.completion_date) {
                info.textContent = "Terminé le " + new Date(result.completion_date).toLocaleString();
            }
        } catch (e) {
            console.warn("[FORMEVO] status load failed", e);
        }
    })();
}

function boot() {
    injectButton();

    // Si rendu dynamique: observer le DOM
    const observer = new MutationObserver(() => {
        injectButton();
        if (document.querySelector(".yonn-completion-btn")) {
            observer.disconnect();
        }
    });

    observer.observe(document.documentElement, { childList: true, subtree: true });

    // retentes (souvent utile sur slides)
    setTimeout(injectButton, 500);
    setTimeout(injectButton, 1500);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
} else {
    boot();
}
