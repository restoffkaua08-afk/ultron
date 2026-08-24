/* ULTRON — UI utilities. Vanilla JS, sem build step. */
(function () {
  "use strict";

  // ---- Theme toggle ----
  const html = document.documentElement;
  const stored = localStorage.getItem("ultron.theme");
  if (stored) html.setAttribute("data-theme", stored);

  const themeBtn = document.querySelector("[data-theme-toggle]");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      const current = html.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      html.setAttribute("data-theme", next);
      localStorage.setItem("ultron.theme", next);
    });
  }

  // ---- Command palette ----
  const trigger = document.querySelector("[data-cmd-palette]");
  const panel = document.querySelector("[data-cmd-palette-panel]");
  const input = document.querySelector("[data-cmd-palette-input]");
  const results = document.querySelector("[data-cmd-palette-results]");
  const close = document.querySelector("[data-cmd-palette-close]");

  function openPalette() {
    if (!panel) return;
    panel.hidden = false;
    setTimeout(function () { if (input) input.focus(); }, 50);
  }
  function hidePalette() {
    if (!panel) return;
    panel.hidden = true;
    if (input) input.value = "";
    if (results) results.innerHTML = '<div class="cmd-empty">Digite para buscar…</div>';
  }

  if (trigger) trigger.addEventListener("click", openPalette);
  if (close) close.addEventListener("click", hidePalette);
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      openPalette();
    } else if (e.key === "Escape" && panel && !panel.hidden) {
      hidePalette();
    }
  });

  // Live search
  let searchTimer = null;
  if (input && results) {
    input.addEventListener("input", function () {
      clearTimeout(searchTimer);
      const q = input.value.trim();
      if (!q) {
        results.innerHTML = '<div class="cmd-empty">Digite para buscar…</div>';
        return;
      }
      searchTimer = setTimeout(function () { doSearch(q); }, 150);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        const first = results.querySelector(".cmd-result");
        if (first) first.click();
      }
    });
  }

  async function doSearch(q) {
    try {
      const r = await fetch("/api/v1/manifests/search?q=" + encodeURIComponent(q) + "&limit=20");
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      const items = (data.results || []).map(function (entry) {
        const m = entry.manifest;
        return {
          id: m.id + "@" + m.version,
          label: m.id,
          meta: m.kind,
          url: "/manifest/" + m.id + "@" + m.version,
        };
      });
      if (!items.length) {
        results.innerHTML = '<div class="cmd-empty">Nenhum resultado.</div>';
        return;
      }
      results.innerHTML = items.map(function (it) {
        return '<div class="cmd-result" data-url="' + it.url + '">' +
               '<span>' + esc(it.label) + '</span>' +
               '<span class="cmd-result-meta">' + esc(it.meta) + '</span>' +
               '</div>';
      }).join("");
      results.querySelectorAll(".cmd-result").forEach(function (el) {
        el.addEventListener("click", function () {
          window.location.href = el.dataset.url;
        });
      });
    } catch (e) {
      results.innerHTML = '<div class="cmd-empty">Erro ao buscar.</div>';
    }
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
})();
