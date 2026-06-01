(() => {
  const state = {
    section: "explore",
    exploreMode: "exact",
    matchMode: "phrase",
    threshold: 0.85,
    report: null,
    loading: false,
    facets: null
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function escapeHTML(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatNumber(value) {
    if (value === null || value === undefined || value === "") return "—";
    return new Intl.NumberFormat("es-MX").format(Number(value));
  }

  function setStatus(title, detail = "", kind = "normal") {
    const el = $("#workshopStatus");
    if (!el) return;

    el.classList.toggle("is-error", kind === "error");
    el.innerHTML = `
      <strong>${escapeHTML(title)}</strong>
      ${detail ? `<span>${escapeHTML(detail)}</span>` : ""}
    `;
  }

  async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      ...options
    });

    const text = await response.text();
    let payload = null;

    try {
      payload = text ? JSON.parse(text) : null;
    } catch (err) {
      throw new Error(`Respuesta no JSON desde ${url}: ${text.slice(0, 160)}`);
    }

    if (!response.ok) {
      const detail = payload?.detail || payload?.message || response.statusText;
      throw new Error(Array.isArray(detail) ? JSON.stringify(detail) : String(detail));
    }

    return payload;
  }

  async function loadFacets() {
    try {
      const facets = await fetchJSON("/api/workshop/facets");
      state.facets = facets;

      const label = $("#workshopDatasetLabel");
      if (label) {
        label.textContent = `${formatNumber(facets.total_rows)} tesis · ${facets.year_min || "—"}–${facets.year_max || "—"}`;
      }
    } catch (err) {
      const label = $("#workshopDatasetLabel");
      if (label) label.textContent = "Backend no disponible";
      setStatus("No se pudieron cargar facets", err.message, "error");
    }
  }

  function setSection(section) {
    state.section = section;

    $$("[data-ws-section]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.wsSection === section);
    });

    $$("[data-ws-panel]").forEach(panel => {
      panel.classList.toggle("is-active", panel.dataset.wsPanel === section);
    });
  }

  function setExploreMode(mode) {
    state.exploreMode = mode;

    $$("[data-ws-explore-mode]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.wsExploreMode === mode);
    });

    $$("[data-ws-controls]").forEach(el => {
      el.hidden = el.dataset.wsControls !== mode;
    });

    const resultMode = $("#workshopResultMode");
    const resultTitle = $("#workshopResultTitle");
    const resultCopy = $("#workshopResultCopy");
    const runButton = $("#workshopRunSearch");

    if (mode === "semantic") {
      if (resultMode) resultMode.textContent = `Búsqueda semántica · similitud ≥ ${state.threshold.toFixed(2)}`;
      if (resultTitle) resultTitle.textContent = "Territorio semántico";
      if (resultCopy) resultCopy.textContent = "La interfaz queda preparada; la conexión a embeddings/FAISS se implementa en la siguiente fase.";
      if (runButton) runButton.textContent = "Próximamente";
      setStatus("Búsqueda semántica pendiente", "Fase siguiente: embeddings + índice vectorial + threshold.", "normal");
    } else {
      if (resultMode) resultMode.textContent = `Búsqueda exacta · ${matchModeLabel(state.matchMode)}`;
      if (resultTitle) resultTitle.textContent = "Explora el acervo por título";
      if (resultCopy) resultCopy.textContent = "Busca menciones literales en títulos normalizados y genera agregaciones reproducibles.";
      if (runButton) runButton.textContent = "Buscar";
      setStatus("Listo para consultar", "Ejecuta una búsqueda exacta para generar métricas, gráficas y tabla.", "normal");
    }
  }

  function matchModeLabel(mode) {
    if (mode === "all_words") return "todas las palabras";
    if (mode === "any_word") return "cualquier palabra";
    return "frase en título";
  }

  function setMatchMode(mode) {
    state.matchMode = mode;

    $$("[data-ws-match-mode]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.wsMatchMode === mode);
    });

    const resultMode = $("#workshopResultMode");
    if (resultMode) resultMode.textContent = `Búsqueda exacta · ${matchModeLabel(mode)}`;
  }

  function renderMetrics(summary) {
    const el = $("#workshopMetrics");
    if (!el) return;

    const period = summary.first_year && summary.last_year
      ? `${summary.first_year}–${summary.last_year}`
      : "—";

    el.innerHTML = `
      <article><strong>${formatNumber(summary.total_matches)}</strong><span>Tesis encontradas</span></article>
      <article><strong>${escapeHTML(period)}</strong><span>Periodo cubierto</span></article>
      <article><strong>${escapeHTML(summary.dominant_program || "—")}</strong><span>Programa dominante</span></article>
      <article><strong>${escapeHTML(summary.dominant_degree || "—")}</strong><span>Nivel dominante</span></article>
    `;
  }

  function renderHorizontalBars(selector, data, limit = 12) {
    const el = $(selector);
    if (!el) return;

    const rows = (data || []).slice(0, limit);
    if (!rows.length) {
      el.innerHTML = `<p class="workshop-empty">Sin datos.</p>`;
      return;
    }

    const max = Math.max(...rows.map(row => Number(row.count || 0)), 1);

    el.innerHTML = rows.map(row => {
      const count = Number(row.count || 0);
      const pct = Math.max(3, count / max * 100);
      return `
        <div class="workshop-bar-row">
          <div class="workshop-bar-label" title="${escapeHTML(row.label)}">${escapeHTML(row.label)}</div>
          <div class="workshop-bar-track">
            <div class="workshop-bar-fill" style="width:${pct}%"></div>
          </div>
          <div class="workshop-bar-value">${formatNumber(count)}</div>
        </div>
      `;
    }).join("");
  }

  function renderYearBars(data) {
    const el = $("#workshopChartYear");
    if (!el) return;

    const rows = data || [];
    if (!rows.length) {
      el.innerHTML = `<p class="workshop-empty">Sin datos temporales.</p>`;
      return;
    }

    const max = Math.max(...rows.map(row => Number(row.count || 0)), 1);

    el.innerHTML = `
      <div class="workshop-year-bars">
        ${rows.map(row => {
          const count = Number(row.count || 0);
          const height = Math.max(2, count / max * 100);
          return `
            <div class="workshop-year-bar"
              style="height:${height}%"
              title="${escapeHTML(row.label)} · ${formatNumber(count)} tesis">
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderTerms(data) {
    const el = $("#workshopTopTerms");
    if (!el) return;

    const rows = data || [];
    if (!rows.length) {
      el.innerHTML = `<p class="workshop-empty">Sin términos.</p>`;
      return;
    }

    el.innerHTML = rows.slice(0, 20).map(row => `
      <span>${escapeHTML(row.label)} · ${formatNumber(row.count)}</span>
    `).join("");
  }

  function renderTable(rows) {
    const tbody = $("#workshopThesisTable");
    if (!tbody) return;

    if (!rows || !rows.length) {
      tbody.innerHTML = `<tr><td colspan="5">Sin resultados.</td></tr>`;
      return;
    }

    tbody.innerHTML = rows.slice(0, 50).map(row => `
      <tr>
        <td>${escapeHTML(row.title || "—")}</td>
        <td>${escapeHTML(row.year || "—")}</td>
        <td>${escapeHTML(row.program || "—")}</td>
        <td>${escapeHTML(row.degree || "—")}</td>
        <td>${escapeHTML(row.plantel || "—")}</td>
      </tr>
    `).join("");
  }

  function renderMethod(method) {
    const body = $("#workshopMethodBody");
    if (!body) return;

    const steps = method?.steps || [];
    body.innerHTML = `
      <ol>
        ${steps.map(step => `
          <li><strong>${escapeHTML(step.label)}:</strong> ${escapeHTML(step.detail)}</li>
        `).join("")}
      </ol>
    `;
  }

  function renderReport(report) {
    state.report = report;

    const resultTitle = $("#workshopResultTitle");
    const resultCopy = $("#workshopResultCopy");

    if (resultTitle) resultTitle.textContent = `“${report.query}” en tesis UNAM`;
    if (resultCopy) {
      resultCopy.textContent = `${formatNumber(report.summary.total_matches)} títulos contienen la consulta bajo el modo ${matchModeLabel(report.match_mode)}.`;
    }

    renderMetrics(report.summary);
    renderYearBars(report.charts?.by_year?.data || []);
    renderHorizontalBars("#workshopChartProgram", report.charts?.by_program?.data || [], 12);
    renderHorizontalBars("#workshopChartDegree", report.charts?.by_degree?.data || [], 8);
    renderHorizontalBars("#workshopChartPlantel", report.charts?.by_plantel?.data || [], 12);
    renderTerms(report.charts?.top_terms?.data || []);
    renderTable(report.tables?.top_theses || []);
    renderMethod(report.method);

    setStatus("Consulta completada", `${formatNumber(report.summary.total_matches)} tesis encontradas.`);
  }

  async function runSearch() {
    if (state.exploreMode === "semantic") {
      setStatus("Búsqueda semántica pendiente", "Todavía falta conectar embeddings/FAISS.", "normal");
      return;
    }

    const input = $("#workshopQueryInput");
    const button = $("#workshopRunSearch");
    const query = input?.value?.trim();

    if (!query) {
      setStatus("Escribe un término", "La búsqueda exacta necesita una consulta.", "error");
      return;
    }

    try {
      state.loading = true;
      if (button) button.disabled = true;
      setStatus("Consultando backend", "Ejecutando DuckDB sobre thesis_lookup.parquet…");

      const report = await fetchJSON("/api/workshop/exact", {
        method: "POST",
        body: JSON.stringify({
          query,
          match_mode: state.matchMode,
          limit: 100
        })
      });

      renderReport(report);
    } catch (err) {
      setStatus("Error en búsqueda exacta", err.message, "error");
    } finally {
      state.loading = false;
      if (button) button.disabled = false;
    }
  }

  function exportCsv() {
    const rows = state.report?.tables?.top_theses || [];
    if (!rows.length) {
      setStatus("No hay tabla para exportar", "Ejecuta una consulta primero.", "error");
      return;
    }

    const headers = ["title", "year", "program", "degree", "plantel", "advisor", "url"];
    const csv = [
      headers.join(","),
      ...rows.map(row => headers.map(h => {
        const value = String(row[h] ?? "").replaceAll('"', '""');
        return `"${value}"`;
      }).join(","))
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `nodo_taller_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function copyMethod() {
    const method = state.report?.method;
    if (!method) {
      setStatus("No hay método para copiar", "Ejecuta una consulta primero.", "error");
      return;
    }

    const text = (method.steps || [])
      .map(step => `${step.label}: ${step.detail}`)
      .join("\n");

    try {
      await navigator.clipboard.writeText(text);
      setStatus("Método copiado", "Los pasos de consulta se copiaron al portapapeles.");
    } catch (err) {
      setStatus("No se pudo copiar", err.message, "error");
    }
  }

  function bindEvents() {
    document.addEventListener("click", event => {
      const sectionBtn = event.target.closest("[data-ws-section]");
      if (sectionBtn) {
        setSection(sectionBtn.dataset.wsSection);
      }

      const exploreBtn = event.target.closest("[data-ws-explore-mode]");
      if (exploreBtn) {
        setExploreMode(exploreBtn.dataset.wsExploreMode);
      }

      const matchBtn = event.target.closest("[data-ws-match-mode]");
      if (matchBtn) {
        setMatchMode(matchBtn.dataset.wsMatchMode);
      }
    });

    $("#workshopRunSearch")?.addEventListener("click", runSearch);

    $("#workshopQueryInput")?.addEventListener("keydown", event => {
      if (event.key === "Enter") runSearch();
    });

    $("#workshopExportCsv")?.addEventListener("click", exportCsv);
    $("#workshopCopyMethod")?.addEventListener("click", copyMethod);

    $("#workshopThreshold")?.addEventListener("input", event => {
      state.threshold = Number(event.target.value) / 100;
      const label = $("#workshopThresholdValue");
      if (label) label.textContent = state.threshold.toFixed(2);
      setExploreMode("semantic");
    });
  }

  function init() {
    const root = $("[data-workshop-root]");
    if (!root) return;

    bindEvents();
    loadFacets();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
