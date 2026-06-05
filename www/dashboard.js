(function () {
    function syncThemeButton() {
        var isDark = document.documentElement.getAttribute("data-theme") === "dark";
        document.querySelectorAll(".theme-toggle .icon-slot").forEach(function (el) {
            el.textContent = isDark ? "L" : "D";
            el.setAttribute("aria-hidden", "true");
        });
        document.querySelectorAll(".theme-toggle").forEach(function (btn) {
            btn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
            btn.setAttribute("title", isDark ? "Switch to light theme" : "Switch to dark theme");
        });
    }

    function markReady() {
        document.body.classList.add("dashboard-ready");
        syncThemeButton();
    }

    document.addEventListener("DOMContentLoaded", markReady);
    document.addEventListener("shiny:connected", markReady);

    new MutationObserver(syncThemeButton).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"],
    });
})();
