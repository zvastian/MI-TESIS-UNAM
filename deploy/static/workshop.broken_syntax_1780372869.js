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


  function parquetDisplay(value) {
    const text = String(value ?? "").trim();
    if (!text) return "";
    return text.toLocaleUpperCase("es-MX");
  }

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


  const WORKSHOP_CHART_COLORS = [
    "#5F9FA7",
    "#D87472",
    "#D8AA70",
    "#8E9D8A",
    "#6F7178",
    "#7A5262",
    "#A8B7BD",
    "#C7A27A"
  ];


  const WORKSHOP_CHART_TEXT = "#252A33";
  const WORKSHOP_CHART_MUTED = "rgba(37,42,51,.58)";
  const WORKSHOP_CHART_GRID = "rgba(37,42,51,.14)";
  const WORKSHOP_CHART_AXIS = "rgba(37,42,51,.42)";

  function workshopTooltipStyle() {
    return {
      backgroundColor: "rgba(255,255,255,.96)",
      borderColor: "rgba(37,42,51,.16)",
      borderWidth: 1,
      padding: [8, 10],
      textStyle: {
        color: WORKSHOP_CHART_TEXT,
        fontFamily: "Inter, Montserrat, system-ui, sans-serif",
        fontSize: 12
      },
      extraCssText: "box-shadow:none;border-radius:4px;"
    };
  }

  function workshopGridStyle(extra = {}) {
    return {
      left: 48,
      right: 28,
      top: 36,
      bottom: 42,
      containLabel: true,
      ...extra
    };
  }

  function workshopCategoryAxis(data = [], extra = {}) {
    return {
      type: "category",
      data,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: WORKSHOP_CHART_AXIS } },
      axisLabel: {
        color: WORKSHOP_CHART_MUTED,
        fontSize: 11,
        hideOverlap: true
      },
      splitLine: {
        show: true,
        lineStyle: { color: WORKSHOP_CHART_GRID, width: 1 }
      },
      ...extra
    };
  }

  function workshopValueAxis(extra = {}) {
    return {
      type: "value",
      axisTick: { show: false },
      axisLine: { lineStyle: { color: WORKSHOP_CHART_AXIS } },
      axisLabel: {
        color: WORKSHOP_CHART_MUTED,
        fontSize: 11
      },
      splitLine: {
        show: true,
        lineStyle: { color: WORKSHOP_CHART_GRID, width: 1 }
      },
      ...extra
    };
  }

  function workshopBaseOption(extra = {}) {
    return {
      color: WORKSHOP_CHART_COLORS,
      backgroundColor: "transparent",
      textStyle: {
        fontFamily: "Inter, Montserrat, system-ui, sans-serif",
        color: WORKSHOP_CHART_TEXT
      },
      tooltip: workshopTooltipStyle(),
      animationDuration: 520,
      animationEasing: "cubicOut",
      ...extra
    };
  }

  function shortChartLabel(value, max = 18) {
    const text = parquetDisplay(value || "");
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
  }


  const workshopChartInstances = new Map();

  function ensureEChart(id) {
    const el = document.getElementById(id);
    if (!el) return null;

    el.innerHTML = `<div class="workshop-echart" data-chart="${escapeHTML(id)}"></div>`;
    const chartEl = el.querySelector(".workshop-echart");

    if (!window.echarts || !chartEl) {
      el.innerHTML = `
        <div class="workshop-chart-debug">
          <strong>Apache ECharts no cargó</strong>
          <span>El contenedor ${escapeHTML(id)} está disponible, pero falta la librería.</span>
        </div>
      `;
      return null;
    }

    if (workshopChartInstances.has(id)) {
      workshopChartInstances.get(id).dispose();
    }

    const instance = window.echarts.init(chartEl, null, { renderer: "canvas" });
    workshopChartInstances.set(id, instance);
    return instance;
  }

  function resizeWorkshopCharts() {
    for (const chart of workshopChartInstances.values()) {
      chart.resize();
    }
  }

  window.addEventListener("resize", resizeWorkshopCharts);

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
    if (!window.__NODO_WORKSHOP_STARTED) return null;
    if (!window.__NODO_WORKSHOP_STARTED) return null;
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


  function renderEditorial(editorial) {
    const summaryEl = $("#workshopEditorialSummary");
    const findingsEl = $("#workshopEditorialFindings");
    const cardsEl = $("#workshopStoryCards");

    if (!summaryEl || !findingsEl || !cardsEl) return;

    if (!editorial) {
      summaryEl.textContent = "No hay lectura editorial disponible para esta consulta.";
      findingsEl.innerHTML = "";
      cardsEl.innerHTML = "";
      return;
    }

    summaryEl.textContent = editorial.summary || "Consulta procesada sin lectura editorial.";

    const findings = Array.isArray(editorial.findings) ? editorial.findings : [];

    if (findings.length) {
      findingsEl.innerHTML = findings.slice(0, 8).map(item => `
        <article>
          <span>${escapeHTML(item.label || "Hallazgo")}</span>
          <strong>${escapeHTML(item.value ?? "—")}</strong>
          <p>${escapeHTML(item.detail || "")}</p>
        </article>
      `).join("");
    } else {
      findingsEl.innerHTML = `
        <article>
          <span>Sin hallazgos</span>
          <strong>—</strong>
          <p>No se generaron hallazgos para esta consulta.</p>
        </article>
      `;
    }

    const storyCards = Array.isArray(editorial.story_cards) ? editorial.story_cards : [];

    if (storyCards.length) {
      cardsEl.innerHTML = storyCards.map((card, index) => `
        <article style="--story-index:${index}">
          <span>${String(index + 1).padStart(2, "0")}</span>
          <strong>${escapeHTML(card.title || "Lectura")}</strong>
          <p>${escapeHTML(card.body || "")}</p>
        </article>
      `).join("");
    } else {
      cardsEl.innerHTML = "";
    }
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
    const id = selector.startsWith("#") ? selector.slice(1) : selector;
    const rows = (data || [])
      .map(row => ({
        label: String(row.label ?? "Sin dato"),
        count: Number(row.count || 0)
      }))
      .filter(row => row.count > 0)
      .slice(0, limit);

    const el = document.getElementById(id);
    if (!rows.length) {
      if (el) el.innerHTML = `<p class="workshop-empty">Sin datos.</p>`;
      return;
    }

    const chart = ensureEChart(id);
    if (!chart) return;

    const labels = rows.map(row => row.label).reverse();
    const values = rows.map(row => row.count).reverse();
    const max = Math.max(...values, 1);

    chart.setOption({
      title: {
        text: buildAnalysisChartTitle(window.__lastWorkshopAnalysis || {}),
        left: 8,
        top: 4,
        textStyle: {
          color: "rgba(21,24,32,.86)",
          fontSize: 15,
          fontWeight: 700
        }
      },
      color: ["#006AEB"],
      grid: {
        left: 12,
        right: 42,
        top: 12,
        bottom: 10,
        containLabel: true
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: params => {
          const p = params[0];
          return `<strong>${escapeHTML(p.axisValue)}</strong><br>${formatNumber(p.value)} tesis`;
        }
      },
      xAxis: {
        type: "value",
        max: Math.ceil(max * 1.18),
        splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } },
        axisLabel: { color: "rgba(21,24,32,.48)" }
      },
      yAxis: {
        type: "category",
        data: labels,
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: {
          color: "rgba(21,24,32,.70)",
          width: 150,
          overflow: "truncate"
        }
      },
      series: [{
        type: "bar",
        data: values,
        barMaxWidth: 18,
        label: {
          show: true,
          position: "right",
          color: "rgba(21,24,32,.62)",
          formatter: p => formatNumber(p.value)
        },
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: params => WORKSHOP_CHART_COLORS[params.dataIndex % WORKSHOP_CHART_COLORS.length]
        }
      }]
    });

    setTimeout(resizeWorkshopCharts, 40);
  }


  function renderYearBars(data) {
    const rows = (data || [])
      .map(row => ({
        label: String(row.label ?? ""),
        count: Number(row.count || 0)
      }))
      .filter(row => row.label && row.count >= 0);

    if (!rows.length) {
      const el = $("#workshopChartYear");
      if (el) el.innerHTML = `<p class="workshop-empty">Sin datos temporales.</p>`;
      return;
    }

    const chart = ensureEChart("workshopChartYear");
    if (!chart) return;

    const values = rows.map(row => row.count);
    const labels = rows.map(row => row.label);
    const max = Math.max(...values, 1);

    chart.setOption({
      color: ["#006AEB"],
      grid: {
        left: 44,
        right: 24,
        top: 42,
        bottom: 42
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: params => {
          const p = params[0];
          return `<strong>${p.axisValue}</strong><br>${formatNumber(p.value)} tesis`;
        }
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: {
          color: "rgba(21,24,32,.58)",
          interval: Math.ceil(labels.length / 8),
          rotate: labels.length > 20 ? 35 : 0
        },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(21,24,32,.16)" } }
      },
      yAxis: {
        type: "value",
        max: Math.ceil(max * 1.12),
        splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } },
        axisLabel: { color: "rgba(21,24,32,.58)" }
      },
      series: [{
        name: "Tesis",
        type: "bar",
        data: values,
        barMaxWidth: 22,
        itemStyle: {
          borderRadius: [7, 7, 0, 0],
          color: params => {
            const value = params.value;
            if (value === max) return "#E36B2C";
            return "#006AEB";
          }
        },
        emphasis: {
          itemStyle: {
            opacity: 0.82
          }
        }
      }]
    });

    setTimeout(resizeWorkshopCharts, 40);
  }


  function renderAreaChart(data) {
    const rows = (data || [])
      .map(row => ({
        name: String(row.label ?? "Sin dato"),
        value: Number(row.count || 0)
      }))
      .filter(row => row.value > 0);

    const el = document.getElementById("workshopChartArea");
    if (!rows.length) {
      if (el) el.innerHTML = `<p class="workshop-empty">Sin datos de área.</p>`;
      return;
    }

    const chart = ensureEChart("workshopChartArea");
    if (!chart) return;

    chart.setOption({
      title: {
        text: buildAnalysisChartTitle(window.__lastWorkshopAnalysis || {}),
        left: 8,
        top: 4,
        textStyle: {
          color: "rgba(21,24,32,.86)",
          fontSize: 15,
          fontWeight: 700
        }
      },
      color: WORKSHOP_CHART_COLORS,
      tooltip: {
        trigger: "item",
        formatter: params => {
          return `<strong>${escapeHTML(params.name)}</strong><br>${formatNumber(params.value)} tesis · ${params.percent}%`;
        }
      },
      legend: {
        orient: "vertical",
        right: 8,
        top: "center",
        textStyle: {
          color: "rgba(21,24,32,.65)",
          fontSize: 11
        }
      },
      series: [{
        name: "Área",
        type: "pie",
        radius: ["48%", "72%"],
        center: ["38%", "50%"],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 8,
          borderColor: "#fff",
          borderWidth: 2
        },
        label: {
          color: "rgba(21,24,32,.70)",
          formatter: "{b}\\n{d}%"
        },
        data: rows
      }]
    });

    setTimeout(resizeWorkshopCharts, 40);
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
        <td>${escapeHTML(parquetDisplay(row.title) || "—")}</td>
        <td>${escapeHTML(row.year || "—")}</td>
        <td>${escapeHTML(parquetDisplay(row.program) || "—")}</td>
        <td>${escapeHTML(parquetDisplay(row.degree) || "—")}</td>
        <td>${escapeHTML(parquetDisplay(row.plantel) || "—")}</td>
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


  function forceWorkshopTitlesMode() {
    document.body.classList.remove("workshop-analysis-mode");
    document.body.classList.add("workshop-titles-mode");
  }

  function renderReport(report) {
  forceWorkshopTitlesMode();
  state.report = report;

  const resultMode = $("#workshopResultMode");
  const resultTitle = $("#workshopResultTitle");
  const resultCopy = $("#workshopResultCopy");

  if (resultMode) resultMode.textContent = `Búsqueda exacta · ${matchModeLabel(report.match_mode)}`;
  if (resultTitle) resultTitle.textContent = `“${report.query}” en tesis UNAM`;
  if (resultCopy) {
    const period = report.summary.first_year && report.summary.last_year
      ? `${report.summary.first_year}–${report.summary.last_year}`
      : "periodo no determinado";
    resultCopy.textContent = `${formatNumber(report.summary.total_matches)} títulos contienen la consulta. El conjunto cubre ${period} y se agregó por año, programa, nivel, plantel, área y asesor.`;
  }

  renderEditorial(report.editorial);
  renderMetrics(report.summary);

  renderYearBars(report.charts?.by_year?.data || []);
  renderHorizontalBars("#workshopChartProgram", report.charts?.by_program?.data || [], 12);
  renderHorizontalBars("#workshopChartDegree", report.charts?.by_degree?.data || [], 8);
  renderHorizontalBars("#workshopChartPlantel", report.charts?.by_plantel?.data || [], 12);
  renderAreaChart(report.charts?.by_area?.data || []);
  renderHorizontalBars("#workshopChartAdvisor", report.charts?.by_advisor?.data || [], 10);

  renderTerms(report.charts?.top_terms?.data || []);
  renderTable(report.tables?.top_theses || []);
  renderMethod(report.method);

  setStatus("Consulta completada", `${formatNumber(report.summary.total_matches)} tesis encontradas.`);

  // No forzamos scroll aquí: el usuario debe poder recorrer libremente el dashboard.
}

  async function runSearch() {
    forceWorkshopTitlesMode();
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
      forceWorkshopTitlesMode();
      document.body.classList.add("workshop-has-results");
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


  function syncWorkshopScrollMode() {
    const isWorkshop =
      document.body?.dataset?.tab === "taller" ||
      document.querySelector('.tab-panel[data-panel="taller"]')?.matches(':is([style*="visibility: visible"], .is-active)');

    document.documentElement.classList.toggle("workshop-scroll-mode", Boolean(isWorkshop));
  }

  const workshopScrollObserver = new MutationObserver(syncWorkshopScrollMode);

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



  // ============================================================
  // Mesa de análisis — frontend MVP
  // ============================================================



  function ensureAnalysisLab() {
    if (document.getElementById("workshopAnalysisLab")) return;

    const tallerPanel = document.querySelector('.tab-panel[data-panel="taller"]');
    if (!tallerPanel) return;

    const analysisPanel =
      tallerPanel.querySelector('.workshop-panel[data-ws-panel="analysis"]') ||
      tallerPanel.querySelector('.workshop-panel[data-workshop-panel="analysis"]') ||
      tallerPanel.querySelector('[data-ws-panel="analysis"]') ||
      tallerPanel.querySelector('[data-workshop-panel="analysis"]');

    const root =
      analysisPanel ||
      tallerPanel.querySelector("[data-workshop-root]") ||
      tallerPanel.querySelector(".workshop-main") ||
      tallerPanel;

    if (analysisPanel) {
      analysisPanel.replaceChildren();
    }

    const section = document.createElement("section");
    section.className = "wa2 wa2-editorial";
    section.id = "workshopAnalysisLab";

    section.innerHTML = `
      <header class="wa2-hero">
        <div class="wa2-mark" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
        <div class="wa2-hero-copy">
          <p class="eyebrow">Mesa de análisis</p>
          <h2>Construye evidencia visual del acervo UNAM</h2>
          <p>
            Elige una relación visual. La Mesa traduce esa intención a una consulta reproducible
            sobre títulos, años, programas, áreas, niveles, planteles y asesores.
          </p>
        </div>
        <aside class="wa2-method-card">
          <span>Motor</span>
          <strong>DuckDB · Parquet · ECharts</strong>
          <p>Consulta reproducible, tabla auditable y visualización exportable.</p>
        </aside>
      </header>

      <section class="wa2-chooser" aria-labelledby="analysisRelationTitle">
        <div class="wa2-section-title">
          <p class="eyebrow">Relación visual</p>
          <h3>COMIENZA...</h3>
          <p>Tus gráficos guardados aparecerán aquí.</p>
          </div>
          <div class="ws3-saved-tags">
            <span>Tiempo</span>
            <span>Títulos</span>
            <span>Ranking</span>
            <span>Asesores</span>
            <span>Parte del total</span>
          </div>
        </section>
      </section>

      <section class="ws3-workbench" id="workshopStudioWorkbench" hidden>
        <aside class="ws4-sidebar" id="workshopStudioSidebar" aria-label="Taller">
          <button class="ws4-toggle" id="workshopSidebarToggle" type="button" aria-label="Contraer o expandir">☰</button>
          <button class="ws4-nav is-active" type="button" data-ws4-space="create">Creación</button>
          <button class="ws4-nav" type="button" data-ws4-space="graphs">Mis gráficos</button>
        </aside>

        <main class="ws3-canvas">
          <div class="ws3-empty" id="workshopStudioEmpty">
            <img class="ws3-empty-image" src="./t.png" alt="" />
            <h3>COMIENZA...</h3>
          <p>Tus gráficos guardados aparecerán aquí.</p>
            <button class="ws3-empty-create" type="button" data-ws4-space="create">Crear</button>
          </div>
        </main>
      </section>
    `;

    tallerPanel.prepend(studio);

    document.getElementById("workshopStartBtn")?.addEventListener("click", startWorkshopStudio);
    document.getElementById("workshopBackToPreviewBtn")?.addEventListener("click", backToWorkshopPreview);
}


  function backToWorkshopPreview() {
    const home = document.getElementById("workshopStudioHome");
    const workbench = document.getElementById("workshopStudioWorkbench");

    if (workbench) workbench.hidden = true;
    if (home) home.hidden = false;

    document.body.classList.remove("workshop-studio-started", "workshop-analysis-mode", "workshop-titles-mode");
    scheduleWorkshopChartResize("studio-preview");
  }


  function ensureWorkshopPreviewButton() {
    const sidebar = document.querySelector("#workshopStudio .ws3-sidebar");
    if (!sidebar || document.getElementById("workshopBackToPreviewBtn")) return;

    const btn = document.createElement("button");
    btn.id = "workshopBackToPreviewBtn";
    btn.className = "ws3-back";
    btn.type = "button";
    btn.setAttribute("aria-label", "Volver al preview del Taller");
    btn.textContent = "←";

    sidebar.insertBefore(btn, sidebar.firstElementChild);
  }

    window.__NODO_WORKSHOP_STUDIO_SPACE = "create";

    if (!window.__NODO_WORKSHOP_STUDIO_MODE || window.__NODO_WORKSHOP_STUDIO_MODE === "empty") {
      setWorkshopStudioMode("temporal");
    } else {
      setWorkshopStudioMode(window.__NODO_WORKSHOP_STUDIO_MODE);
    }
  }

  
  function ensureWorkshopStudio() {
    const tallerPanel = document.querySelector('.tab-panel[data-panel="taller"]');
    if (!tallerPanel) return null;

    let studio = document.getElementById("workshopStudio");
    if (studio) return studio;

    const root =
      tallerPanel.querySelector("[data-workshop-root]") ||
      tallerPanel.querySelector(".workshop-main") ||
      tallerPanel.querySelector(".workshop") ||
      tallerPanel;

    studio = document.createElement("section");
    studio.className = "ws3";
    studio.id = "workshopStudio";

    studio.innerHTML = `
      <section class="ws3-workbench" id="workshopStudioWorkbench">
        <aside class="ws4-sidebar" id="workshopStudioSidebar" aria-label="Taller">
          <button class="ws4-toggle" id="workshopSidebarToggle" type="button" aria-label="Contraer o expandir">☰</button>
          <button class="ws4-nav" type="button" data-ws4-space="create">Creación</button>
          <button class="ws4-nav is-active" type="button" data-ws4-space="graphs">Mis gráficos</button>
        </aside>
        <main class="ws3-canvas">
          <section class="ws3-empty" id="workshopStudioEmpty">
            <img class="ws3-empty-image" src="./t.png" alt="" />
            <h3>COMIENZA...</h3>
            <p>Tus gráficos guardados aparecerán aquí.</p>
            <button class="ws3-empty-create" type="button" data-ws4-space="create">Crear</button>
          </section>
          <div class="ws3-host" id="workshopStudioHost"></div>
        </main>
      </section>
    `;

    root.appendChild(studio);
    return studio;
  }


  function setWorkshopStudioSpace(space = "graphs") {
    const normalized = space === "create" ? "create" : "graphs";
    const empty = document.getElementById("workshopStudioEmpty");
    const host = document.getElementById("workshopStudioHost");

    document.body.classList.toggle("workshop-space-create", normalized === "create");
    document.body.classList.toggle("workshop-space-graphs", normalized === "graphs");

    document.querySelectorAll("[data-ws4-space]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.ws4Space === normalized);
    });

    if (empty) empty.hidden = normalized !== "graphs";
    if (host) host.hidden = normalized !== "create";

    if (normalized === "create") {
      ensureAnalysisLab();
      scheduleWorkshopChartResize("studio-create");
    }
  }

  document.addEventListener("click", event => {
    const btn = event.target.closest("[data-ws4-space]");
    if (!btn) return;
    event.preventDefault();
    setWorkshopStudioSpace(btn.dataset.ws4Space || "graphs");
  });

function startWorkshopStudio() {
    window.__NODO_WORKSHOP_STARTED = true;

    document.body.classList.add("workshop-studio-started");
    document.body.classList.remove("workshop-analysis-mode");
    document.body.classList.add("workshop-titles-mode");

    const home = document.getElementById("workshopStudioHome");
    const workbench = document.getElementById("workshopStudioWorkbench");

    if (home) home.hidden = true;
    if (workbench) workbench.hidden = false;

    ensureWorkshopPreviewButton();

    ensureAnalysisLab();
    prepareWorkshopStudioPanels();

    if (typeof loadFacets === "function") {
      try { loadFacets(); } catch (err) { console.warn("[NODO Taller] loadFacets diferido falló", err); }
    }

    setWorkshopStudioSpace("graphs");
    scheduleWorkshopChartResize("studio-start");
  }

  function prepareWorkshopStudioPanels() {
    const host = document.getElementById("workshopStudioHost");
    const tallerPanel = document.querySelector('.tab-panel[data-panel="taller"]');
    if (!host || !tallerPanel) return;

    const titlesPanel =
      tallerPanel.querySelector('.workshop-panel[data-ws-panel="explore"]') ||
      tallerPanel.querySelector('.workshop-panel[data-workshop-panel="explore"]') ||
      tallerPanel.querySelector('[data-ws-panel="explore"]');

    if (titlesPanel && !titlesPanel.dataset.ws3Moved) {
      titlesPanel.dataset.ws3Moved = "true";
      titlesPanel.classList.add("ws3-mode-panel", "ws3-titles-panel");
      host.appendChild(titlesPanel);
    }

    const analysisLab = document.getElementById("workshopAnalysisLab");
    if (analysisLab && !analysisLab.dataset.ws3Moved) {
      analysisLab.dataset.ws3Moved = "true";
      analysisLab.classList.add("ws3-mode-panel", "ws3-analysis-panel");
      host.appendChild(analysisLab);
    }
  }

  function setWorkshopStudioMode(mode) {
    const studio = document.getElementById("workshopStudio");
    const empty = document.getElementById("workshopStudioEmpty");
    const titlesPanel = document.querySelector(".ws3-titles-panel");
    const analysisLab = document.getElementById("workshopAnalysisLab");

    if (!studio) return;

    const analysisModes = ["titles", "temporal", "ranking", "comparison", "distribution", "partwhole", "magnitude", "advisors"];
    const isAnalysis = analysisModes.includes(mode);
    const isTitles = false;
    const isEmpty = mode === "empty";

    window.__NODO_WORKSHOP_STUDIO_MODE = mode;
if (empty) empty.hidden = !isEmpty;

    if (titlesPanel) {
      titlesPanel.hidden = !isTitles;
      titlesPanel.style.display = isTitles ? "block" : "none";
      titlesPanel.style.visibility = isTitles ? "visible" : "hidden";
    }

    if (analysisLab) {
      analysisLab.hidden = !isAnalysis;
      analysisLab.style.display = isAnalysis ? "grid" : "none";
      analysisLab.style.visibility = isAnalysis ? "visible" : "hidden";
    }

    document.body.classList.toggle("workshop-analysis-mode", isAnalysis);
    document.body.classList.toggle("workshop-titles-mode", isTitles);

    document.querySelectorAll("[data-mode-strip]").forEach(btn => {
      btn.classList.toggle("is-active", isTitles && btn.dataset.modeStrip === "titles");
    });

    if (isAnalysis) {
      if (mode === "titles") {
        applyTitlesModeControls();
      } else {
        const template = mode === "advisors" ? "ranking" : mode;
        applyAnalysisTemplate(template);
        applyWorkshopModeControls(mode);
      }

      if (mode !== "titles" && mode === "advisors") {
        const groupBy = document.getElementById("analysisGroupBy");
        const compareBy = document.getElementById("analysisCompareBy");
        const summaryEl = document.getElementById("analysisSummary");
        const chartTitle = document.getElementById("analysisChartTitle");

        if (groupBy) groupBy.value = "advisor";
        if (compareBy) compareBy.value = "";
        if (chartTitle) chartTitle.textContent = "Ranking de asesores";
        if (summaryEl) {
          summaryEl.innerHTML = `
            <span>Asesores</span>
            <strong>TRAYECTORIAS Y CONCENTRACIÓN</strong>
            <p>Construye rankings y lecturas sobre dirección de tesis. Puedes filtrar por tema o periodo antes de generar.</p>
          `;
        }
      }
    }

    scheduleWorkshopChartResize("studio-mode");
  }

  document.addEventListener("DOMContentLoaded", ensureWorkshopStudio);


  document.addEventListener("click", event => {
    if (event.target.closest("#workshopBackToPreviewBtn")) {
      backToWorkshopPreview();
    }
  });

  document.addEventListener("click", event => {
    const btn = event.target.closest("[data-mode-strip]");
    if (!btn) return;

    const mode = btn.dataset.modeStrip || "temporal";
    setWorkshopStudioMode(mode);
  });

  document.addEventListener("click", event => {
    const toggle = event.target.closest("#workshopSidebarToggle");
    if (toggle) {
      document.getElementById("workshopStudioSidebar")?.classList.toggle("is-collapsed");
      return;
    }

    const spaceBtn = event.target.closest("[data-ws4-space]");
    if (spaceBtn) {
      setWorkshopStudioSpace(spaceBtn.dataset.ws4Space || "create");
    }
  });



  /* WS4 FINAL SPACE CONTROLLER */
  function setWorkshopStudioSpaceFinal(space) {
    const normalized = space === "create" ? "create" : "graphs";
    const empty = document.getElementById("workshopStudioEmpty");
    const host = document.getElementById("workshopStudioHost");

    document.body.classList.toggle("workshop-space-create", normalized === "create");
    document.body.classList.toggle("workshop-space-graphs", normalized === "graphs");

    document.querySelectorAll("[data-ws4-space]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.ws4Space === normalized);
    });

    if (empty) empty.hidden = normalized !== "graphs";
    if (host) host.hidden = normalized !== "create";
  }

  document.addEventListener("click", event => {
    const btn = event.target.closest("[data-ws4-space]");
    if (!btn) return;
    event.preventDefault();
    setWorkshopStudioSpaceFinal(btn.dataset.ws4Space || "graphs");
  });

  requestAnimationFrame(() => {
    if (document.body.dataset.tab === "taller" && document.getElementById("workshopStudio")) {
      setWorkshopStudioSpaceFinal("graphs");
    }
  });
  /* END WS4 FINAL SPACE CONTROLLER */

})();
