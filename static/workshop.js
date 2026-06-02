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


  const WORKSHOP_CHART_COLORS = [
    "#006AEB",
    "#E36B2C",
    "#2F9870",
    "#7353C9",
    "#D4A017",
    "#D64C7F",
    "#1D8FA3",
    "#5B6C86"
  ];

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
          <h3>¿Qué quieres observar?</h3>
        </div>

        <nav class="wa2-nav" aria-label="Categorías visuales">
          <button class="wa2-nav-item is-active" type="button" data-template="temporal">
            <small>01</small>
            <strong>Tiempo</strong>
            <span>Evolución por año</span>
          </button>
          <button class="wa2-nav-item" type="button" data-template="comparison">
            <small>02</small>
            <strong>Comparación</strong>
            <span>Categorías frente a frente</span>
          </button>
          <button class="wa2-nav-item" type="button" data-template="ranking">
            <small>03</small>
            <strong>Ranking</strong>
            <span>Mayor a menor</span>
          </button>
          <button class="wa2-nav-item" type="button" data-template="distribution">
            <small>04</small>
            <strong>Distribución</strong>
            <span>Concentración y dispersión</span>
          </button>
          <button class="wa2-nav-item" type="button" data-template="partwhole">
            <small>05</small>
            <strong>Parte del total</strong>
            <span>Composición proporcional</span>
          </button>
          <button class="wa2-nav-item" type="button" data-template="magnitude">
            <small>06</small>
            <strong>Magnitud</strong>
            <span>Tamaños absolutos</span>
          </button>
        </nav>
      </section>

      <section class="wa2-guide">
        <article class="wa2-intro" id="analysisVocabIntro">
          <p class="eyebrow">Tiempo</p>
          <h3 id="analysisRelationTitle">Cambio a través de los años</h3>
          <p id="analysisRelationCopy">Úsalo para observar cuándo aparece, crece o se concentra un tema dentro del acervo.</p>
        </article>

        <article class="wa2-demo-card">
          <div class="wa2-card-head">
            <span>Demo visual</span>
            <strong id="analysisDemoLabel">Barras temporales</strong>
          </div>
          <div id="analysisDemoChart" class="wa2-demo"></div>
        </article>

        <aside class="wa2-types" id="analysisChartTypes"></aside>
      </section>

      <section class="wa2-builder" aria-label="Constructor de consulta">
        <div class="wa2-builder-copy">
          <p class="eyebrow">Constructor</p>
          <h3>Formula la pregunta como una frase.</h3>
          <p>
            La interfaz mantiene el lenguaje visual arriba y deja la consulta técnica visible
            sólo como método reproducible.
          </p>
        </div>

        <div class="wa2-sentence">
          <span>Quiero ver</span>
          <label>
            <span>agrupado por</span>
            <select id="analysisGroupBy">
              <option value="year">año</option>
              <option value="program">programa</option>
              <option value="area">área</option>
              <option value="degree">nivel</option>
              <option value="plantel">plantel</option>
              <option value="advisor">asesor</option>
            </select>
          </label>

          <label>
            <span>comparado con</span>
            <select id="analysisCompareBy">
              <option value="">sin comparación</option>
              <option value="area">área</option>
              <option value="degree">nivel</option>
              <option value="program">programa</option>
              <option value="plantel">plantel</option>
            </select>
          </label>

          <label class="wa2-wide">
            <span>sobre títulos que contienen</span>
            <input id="analysisTitleContains" type="text" placeholder="inteligencia artificial, banca, muralismo…" />
          </label>

          <label>
            <span>desde</span>
            <input id="analysisYearMin" type="number" min="1900" max="2026" placeholder="2000" />
          </label>

          <label>
            <span>hasta</span>
            <input id="analysisYearMax" type="number" min="1900" max="2026" placeholder="2026" />
          </label>

          <label>
            <span>máximo</span>
            <input id="analysisLimit" type="number" min="5" max="100" value="80" />
          </label>

          <button class="workshop-primary wa2-run" id="analysisRunBtn" type="button">
            Generar visualización
          </button>
        </div>

        <div class="wa2-query-note" id="analysisQueryNote">
          group_by=year · compare_by=none · chart_type=auto
        </div>
      </section>

      <section class="wa2-result">
        <article class="wa2-summary" id="analysisSummary">
          <span>Plantilla seleccionada</span>
          <strong>Tiempo</strong>
          <p>Agrega un tema o analiza todo el acervo. La lectura aparecerá aquí cuando generes la visualización.</p>
        </article>

        <article class="wa2-chart">
          <div class="wa2-card-head">
            <span>Visualización</span>
            <strong id="analysisChartTitle">Gráfico reproducible</strong>
          </div>
          <div id="analysisChart"></div>
        </article>

        <article class="wa2-table-card">
          <div class="wa2-card-head">
            <span>Datos y método</span>
            <button class="workshop-secondary" id="analysisCopyBtn" type="button">Copiar CSV</button>
          </div>
          <div class="workshop-table-wrap">
            <table class="workshop-table wa2-table">
              <thead id="analysisTableHead"></thead>
              <tbody id="analysisTableBody"></tbody>
            </table>
          </div>
        </article>
      </section>
    `;

    root.appendChild(section);

    const runBtn = document.getElementById("analysisRunBtn");
    if (runBtn) runBtn.addEventListener("click", runAnalysis);

    const copyBtn = document.getElementById("analysisCopyBtn");
    if (copyBtn) copyBtn.addEventListener("click", copyAnalysisCSV);

    bindAnalysisTemplates();
    applyAnalysisTemplate("temporal");
  }






  function scheduleWorkshopChartResize(reason = "unknown") {
    requestAnimationFrame(() => {
      resizeWorkshopCharts();
      setTimeout(resizeWorkshopCharts, 80);
      setTimeout(resizeWorkshopCharts, 240);
    });
  }


  function applyAnalysisTemplate(template) {
    const groupBy = document.getElementById("analysisGroupBy");
    const compareBy = document.getElementById("analysisCompareBy");
    const yearMin = document.getElementById("analysisYearMin");
    const yearMax = document.getElementById("analysisYearMax");
    const limit = document.getElementById("analysisLimit");

    if (!groupBy || !compareBy) return;

    const configs = {
      temporal: {
        title: "Tiempo",
        subtitle: "Cambio a través de los años",
        body: "Úsalo para observar cuándo aparece, crece o se concentra un tema dentro del acervo.",
        group_by: "year",
        compare_by: "",
        limit: "80",
        year_min: "2000",
        year_max: "2026",
        chartLabel: "Línea / barras temporales",
        chartTypes: [
          ["Línea", "tendencia continua"],
          ["Barras temporales", "conteos por año"],
          ["Área", "volumen acumulado"],
          ["Heatmap", "año por categoría"]
        ],
        demo: "temporal"
      },
      comparison: {
        title: "Comparación",
        subtitle: "Categorías frente a frente",
        body: "Compara programas, áreas, niveles, planteles o asesores para ver diferencias claras entre grupos.",
        group_by: "program",
        compare_by: "degree",
        limit: "30",
        year_min: "",
        year_max: "",
        chartLabel: "Barras agrupadas",
        chartTypes: [
          ["Barras agrupadas", "comparación directa"],
          ["Barras horizontales", "categorías largas"],
          ["Dot plot", "diferencias finas"],
          ["Small multiples", "series comparables"]
        ],
        demo: "comparison"
      },
      ranking: {
        title: "Ranking",
        subtitle: "Ordenar de mayor a menor",
        body: "Encuentra qué programas, planteles, áreas o asesores concentran más tesis dentro de un conjunto.",
        group_by: "program",
        compare_by: "",
        limit: "20",
        year_min: "",
        year_max: "",
        chartLabel: "Ranking de barras",
        chartTypes: [
          ["Barras ranking", "top categorías"],
          ["Lollipop", "ranking editorial"],
          ["Tabla ordenada", "lectura exacta"],
          ["Highlight bars", "enfatizar un grupo"]
        ],
        demo: "ranking"
      },
      distribution: {
        title: "Distribución",
        subtitle: "Concentración y dispersión",
        body: "Observa la forma del conjunto: dónde se acumulan las tesis y qué valores aparecen como extremos.",
        group_by: "year",
        compare_by: "",
        limit: "60",
        year_min: "",
        year_max: "",
        chartLabel: "Histograma / distribución",
        chartTypes: [
          ["Histograma", "frecuencia por rangos"],
          ["Boxplot", "valores extremos"],
          ["Strip plot", "puntos individuales"],
          ["Densidad", "forma suavizada"]
        ],
        demo: "distribution"
      },
      partwhole: {
        title: "Parte del total",
        subtitle: "Composición proporcional",
        body: "Muestra qué proporción ocupa cada área, nivel, programa o plantel dentro del conjunto filtrado.",
        group_by: "area",
        compare_by: "",
        limit: "20",
        year_min: "",
        year_max: "",
        chartLabel: "Dona / barra 100%",
        chartTypes: [
          ["Dona", "composición simple"],
          ["Treemap", "peso relativo"],
          ["Barra 100%", "comparar proporciones"],
          ["Waffle", "lectura modular"]
        ],
        demo: "partwhole"
      },
      magnitude: {
        title: "Magnitud",
        subtitle: "Tamaños absolutos",
        body: "Compara el tamaño bruto de conjuntos: cuántas tesis hay por programa, plantel, área o nivel.",
        group_by: "plantel",
        compare_by: "",
        limit: "25",
        year_min: "",
        year_max: "",
        chartLabel: "Barras / burbujas",
        chartTypes: [
          ["Barras", "magnitud absoluta"],
          ["Burbujas", "tamaño visual"],
          ["Packed circles", "conjuntos compactos"],
          ["Treemap", "áreas proporcionales"]
        ],
        demo: "magnitude"
      }
    };

    const cfg = configs[template] || configs.temporal;

    groupBy.value = cfg.group_by;
    compareBy.value = cfg.compare_by;
    if (yearMin) yearMin.value = cfg.year_min;
    if (yearMax) yearMax.value = cfg.year_max;
    if (limit) limit.value = cfg.limit;

    document.querySelectorAll(".wa2-nav-item").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.template === template);
    });

    const intro = document.getElementById("analysisVocabIntro");
    if (intro) {
      intro.innerHTML = `
        <p class="eyebrow">${escapeHTML(cfg.title)}</p>
        <h3 id="analysisRelationTitle">${escapeHTML(cfg.subtitle)}</h3>
        <p id="analysisRelationCopy">${escapeHTML(cfg.body)}</p>
      `;
    }

    const demoLabel = document.getElementById("analysisDemoLabel");
    if (demoLabel) demoLabel.textContent = cfg.chartLabel;

    const types = document.getElementById("analysisChartTypes");
    if (types) {
      types.innerHTML = cfg.chartTypes.map(([name, desc]) => `
        <article>
          <span>${escapeHTML(name)}</span>
          <p>${escapeHTML(desc)}</p>
        </article>
      `).join("");
    }

    const note = document.getElementById("analysisQueryNote");
    if (note) {
      note.textContent = `group_by=${cfg.group_by} · compare_by=${cfg.compare_by || "none"} · limit=${cfg.limit} · chart_type=auto`;
    }

    const summaryEl = document.getElementById("analysisSummary");
    if (summaryEl) {
      summaryEl.innerHTML = `
        <span>Relación visual</span>
        <strong>${escapeHTML(cfg.title)}</strong>
        <p>${escapeHTML(cfg.body)} Agrega un tema en el título o deja el campo vacío para analizar todo el acervo.</p>
      `;
    }

    const chartTitle = document.getElementById("analysisChartTitle");
    if (chartTitle) chartTitle.textContent = cfg.chartLabel;

    renderAnalysisDemo(cfg.demo);
    scheduleWorkshopChartResize("template");
  }



  function bindAnalysisTemplates() {
    document.querySelectorAll(".wa2-nav-item").forEach(btn => {
      btn.addEventListener("click", () => {
        applyAnalysisTemplate(btn.dataset.template || "temporal");
      });
    });
  }



  function renderAnalysisDemo(kind) {
    const chart = ensureEChart("analysisDemoChart");
    if (!chart) return;

    const palette = WORKSHOP_CHART_COLORS;
    const years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"];
    const values = [18, 22, 19, 28, 34, 42, 57, 73];

    const baseGrid = {
      left: 34,
      right: 18,
      top: 28,
      bottom: 28,
      containLabel: true
    };

    if (kind === "partwhole") {
      chart.setOption({
        color: palette,
        tooltip: { trigger: "item" },
        series: [{
          type: "pie",
          radius: ["46%", "72%"],
          center: ["50%", "52%"],
          itemStyle: { borderRadius: 8, borderColor: "#fff", borderWidth: 2 },
          data: [
            { name: "Nivel A", value: 42 },
            { name: "Nivel B", value: 28 },
            { name: "Nivel C", value: 18 },
            { name: "Nivel D", value: 12 }
          ]
        }]
      }, true);
      return;
    }

    if (kind === "distribution") {
      chart.setOption({
        color: [palette[2]],
        grid: baseGrid,
        tooltip: { trigger: "axis" },
        xAxis: {
          type: "category",
          data: ["0–5", "6–10", "11–15", "16–20", "21–25", "26+"],
          axisTick: { show: false }
        },
        yAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } } },
        series: [{
          type: "bar",
          data: [8, 18, 31, 22, 13, 6],
          barMaxWidth: 34,
          itemStyle: { borderRadius: [8, 8, 0, 0] }
        }]
      }, true);
      return;
    }

    if (kind === "ranking" || kind === "comparison" || kind === "magnitude") {
      const labels = ["Programa A", "Programa B", "Programa C", "Programa D", "Programa E"].reverse();
      const data = [75, 61, 48, 32, 21].reverse();

      chart.setOption({
        color: palette,
        grid: { left: 18, right: 34, top: 24, bottom: 18, containLabel: true },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        xAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } } },
        yAxis: {
          type: "category",
          data: labels,
          axisTick: { show: false },
          axisLine: { show: false }
        },
        series: [{
          type: "bar",
          data,
          barMaxWidth: 20,
          label: { show: true, position: "right" },
          itemStyle: {
            borderRadius: [0, 8, 8, 0],
            color: params => palette[params.dataIndex % palette.length]
          }
        }]
      }, true);
      return;
    }

    if (kind === "correlation") {
      chart.setOption({
        color: [palette[3]],
        grid: baseGrid,
        tooltip: { trigger: "item" },
        xAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } } },
        yAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } } },
        series: [{
          type: "scatter",
          symbolSize: val => Math.max(8, val[2] / 2),
          data: [[10, 12, 20], [20, 23, 30], [31, 28, 42], [45, 40, 28], [57, 51, 50], [72, 65, 36]]
        }]
      }, true);
      return;
    }

    if (kind === "flow") {
      chart.setOption({
        color: palette,
        tooltip: { trigger: "item" },
        series: [{
          type: "sankey",
          layout: "none",
          emphasis: { focus: "adjacency" },
          data: [
            { name: "Área" }, { name: "Programa" }, { name: "Nivel" }, { name: "Plantel" }
          ],
          links: [
            { source: "Área", target: "Programa", value: 10 },
            { source: "Programa", target: "Nivel", value: 8 },
            { source: "Nivel", target: "Plantel", value: 6 }
          ]
        }]
      }, true);
      return;
    }

    chart.setOption({
      color: [palette[0], palette[1]],
      grid: baseGrid,
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        data: years,
        axisTick: { show: false },
        axisLabel: { color: "rgba(21,24,32,.58)" }
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } },
        axisLabel: { color: "rgba(21,24,32,.58)" }
      },
      series: [{
        type: "line",
        smooth: true,
        symbolSize: 7,
        areaStyle: { opacity: 0.12 },
        lineStyle: { width: 3 },
        data: values
      }]
    }, true);

    setTimeout(resizeWorkshopCharts, 40);
  }

  function readAnalysisRequest() {
    const groupBy = document.getElementById("analysisGroupBy")?.value || "year";
    const compareBy = document.getElementById("analysisCompareBy")?.value || null;
    const yearMin = document.getElementById("analysisYearMin")?.value;
    const yearMax = document.getElementById("analysisYearMax")?.value;
    const titleContains = document.getElementById("analysisTitleContains")?.value?.trim();
    const limit = Number(document.getElementById("analysisLimit")?.value || 50);

    const filters = {};

    if (yearMin) filters.year_min = Number(yearMin);
    if (yearMax) filters.year_max = Number(yearMax);
    if (titleContains) filters.title_contains = titleContains;

    return {
      group_by: groupBy,
      compare_by: compareBy || null,
      filters,
      limit: Math.max(1, Math.min(100, limit || 50)),
      chart_type: "auto"
    };
  }

  async function runAnalysis() {
    const summaryEl = document.getElementById("analysisSummary");
    if (summaryEl) {
      summaryEl.innerHTML = `
        <span>Procesando</span>
        <strong>Consultando DuckDB…</strong>
        <p>Generando agrupaciones sobre thesis_lookup.parquet.</p>
      `;
    }

    try {
      const req = readAnalysisRequest();

      const response = await fetch("/api/workshop/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const report = await response.json();
      window.__lastWorkshopAnalysis = report;

      renderAnalysisReport(report);
      scheduleWorkshopChartResize("analysis-report");
    } catch (err) {
      console.error("[NODO Taller] Error en Mesa de análisis", err);
      if (summaryEl) {
        summaryEl.innerHTML = `
          <span>Error</span>
          <strong>No se pudo generar el análisis</strong>
          <p>${escapeHTML(err.message || String(err))}</p>
        `;
      }
    }
  }

  function renderAnalysisReport(report) {
    renderAnalysisSummary(report);
    renderAnalysisChart(report);
    renderAnalysisTable(report.table || []);
  }

  function renderAnalysisSummary(report) {
    const el = document.getElementById("analysisSummary");
    if (!el) return;

    const summary = report.summary || {};
    const editorial = report.editorial || {};
    const req = report.request || {};
    const filters = req.filters || {};
    const topic = filters.title_contains ? ` sobre “${filters.title_contains}”` : "";
    const group = summary.group_by || req.group_by || "variable";

    el.innerHTML = `
      <span>${escapeHTML(report.chart?.type || "visualización")}</span>
      <strong>${formatNumber(summary.total_rows || 0)} tesis${escapeHTML(topic)}</strong>
      <p>${escapeHTML(editorial.summary || `Agrupación por ${group}. La tabla inferior conserva los datos para auditar o reutilizar la consulta.`)}</p>
    `;
  }

  function renderAnalysisChart(report) {
    const chartData = report.chart?.data || [];
    const chartType = report.chart?.type || "bar";
    const groupBy = report.summary?.group_by || "group";
    const compareBy = report.summary?.compare_by || null;

    const chart = ensureEChart("analysisChart");
    if (!chart) return;

    if (!chartData.length) {
      chart.setOption({
        title: { text: "Sin datos para graficar", left: "center", top: "middle" }
      });
      return;
    }

    if (compareBy) {
      renderAnalysisCompareChart(chart, chartData, groupBy, compareBy, chartType);
    } else {
      renderAnalysisSimpleChart(chart, chartData, groupBy, chartType);
    }

    setTimeout(resizeWorkshopCharts, 40);
  }



  function buildAnalysisChartTitle(report) {
    const req = report.request || {};
    const filters = req.filters || {};
    const group = req.group_by || "variable";
    const compare = req.compare_by;
    const topic = filters.title_contains ? ` sobre “${filters.title_contains}”` : "";
    const years = filters.year_min || filters.year_max
      ? `, ${filters.year_min || "inicio"}–${filters.year_max || "actualidad"}`
      : "";

    if (compare) {
      return `Tesis${topic} agrupadas por ${group} y comparadas por ${compare}${years}`;
    }

    return `Tesis${topic} agrupadas por ${group}${years}`;
  }

  function renderAnalysisSimpleChart(chart, rows, groupBy, chartType) {
    const labels = rows.map(row => String(row.group ?? "Sin dato"));
    const values = rows.map(row => Number(row.count || 0));

    const isTime = groupBy === "year" || chartType === "time_bar";

    chart.setOption({
      color: ["#006AEB"],
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: params => {
          const p = params[0];
          return `<strong>${escapeHTML(p.axisValue)}</strong><br>${formatNumber(p.value)} tesis`;
        }
      },
      grid: {
        left: isTime ? 48 : 16,
        right: 36,
        top: 36,
        bottom: isTime ? 44 : 24,
        containLabel: true
      },
      xAxis: isTime ? {
        type: "category",
        data: labels,
        axisLabel: { color: "rgba(21,24,32,.60)", rotate: labels.length > 20 ? 35 : 0 },
        axisTick: { show: false }
      } : {
        type: "value",
        splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } },
        axisLabel: { color: "rgba(21,24,32,.55)" }
      },
      yAxis: isTime ? {
        type: "value",
        splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } },
        axisLabel: { color: "rgba(21,24,32,.55)" }
      } : {
        type: "category",
        data: labels.slice().reverse(),
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: "rgba(21,24,32,.68)", width: 180, overflow: "truncate" }
      },
      series: [{
        type: "bar",
        data: isTime ? values : values.slice().reverse(),
        barMaxWidth: 22,
        label: isTime ? undefined : {
          show: true,
          position: "right",
          color: "rgba(21,24,32,.62)",
          formatter: p => formatNumber(p.value)
        },
        itemStyle: {
          borderRadius: isTime ? [8, 8, 0, 0] : [0, 8, 8, 0],
          color: params => WORKSHOP_CHART_COLORS[params.dataIndex % WORKSHOP_CHART_COLORS.length]
        }
      }]
    }, true);
  }

  function renderAnalysisCompareChart(chart, rows, groupBy, compareBy, chartType) {
    const groups = [...new Set(rows.map(row => String(row.group ?? "Sin dato")))];
    const compares = [...new Set(rows.map(row => String(row.compare ?? "Sin dato")))].slice(0, 8);

    const lookup = new Map();
    for (const row of rows) {
      lookup.set(`${row.group}|||${row.compare}`, Number(row.count || 0));
    }

    const isTime = groupBy === "year" || chartType === "stacked_time";

    const series = compares.map((compare, idx) => ({
      name: compare,
      type: "bar",
      stack: isTime ? "total" : undefined,
      barMaxWidth: 26,
      data: groups.map(group => lookup.get(`${group}|||${compare}`) || 0),
      itemStyle: {
        borderRadius: isTime ? [3, 3, 0, 0] : [0, 6, 6, 0],
        color: WORKSHOP_CHART_COLORS[idx % WORKSHOP_CHART_COLORS.length]
      }
    }));

    chart.setOption({
      color: WORKSHOP_CHART_COLORS,
      legend: {
        top: 0,
        type: "scroll",
        textStyle: { color: "rgba(21,24,32,.65)", fontSize: 11 }
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" }
      },
      grid: {
        left: 48,
        right: 28,
        top: 52,
        bottom: 48,
        containLabel: true
      },
      xAxis: {
        type: "category",
        data: groups,
        axisLabel: {
          color: "rgba(21,24,32,.60)",
          rotate: groups.length > 18 ? 35 : 0
        },
        axisTick: { show: false }
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "rgba(21,24,32,.08)" } },
        axisLabel: { color: "rgba(21,24,32,.55)" }
      },
      series
    }, true);
  }

  function renderAnalysisTable(rows) {
    const head = document.getElementById("analysisTableHead");
    const body = document.getElementById("analysisTableBody");
    if (!head || !body) return;

    if (!rows.length) {
      head.innerHTML = "";
      body.innerHTML = `<tr><td>Sin datos</td></tr>`;
      return;
    }

    const hasCompare = Object.prototype.hasOwnProperty.call(rows[0], "compare");
    const total = rows.reduce((sum, row) => sum + Number(row.count || 0), 0) || 1;

    head.innerHTML = `
      <tr>
        <th>${hasCompare ? "Grupo" : "Categoría"}</th>
        ${hasCompare ? "<th>Comparación</th>" : ""}
        <th>Tesis</th>
        <th>Participación</th>
        <th>Lectura</th>
      </tr>
    `;

    body.innerHTML = rows.slice(0, 200).map((row, index) => {
      const count = Number(row.count || 0);
      const share = count / total;
      const pct = `${(share * 100).toFixed(1)}%`;
      const reading = index === 0
        ? "Concentración principal"
        : share >= 0.15
          ? "Peso alto"
          : share >= 0.05
            ? "Peso medio"
            : "Presencia baja";

      return `
        <tr>
          <td><strong>${escapeHTML(row.group ?? "Sin dato")}</strong></td>
          ${hasCompare ? `<td>${escapeHTML(row.compare ?? "Sin dato")}</td>` : ""}
          <td>${formatNumber(count)}</td>
          <td>${pct}</td>
          <td><span class="wa2-reading">${reading}</span></td>
        </tr>
      `;
    }).join("");
  }

  function copyAnalysisCSV() {
    const report = window.__lastWorkshopAnalysis;
    const rows = report?.table || [];

    if (!rows.length) {
      navigator.clipboard?.writeText("No hay datos para copiar.");
      return;
    }

    const hasCompare = Object.prototype.hasOwnProperty.call(rows[0], "compare");
    const headers = hasCompare ? ["group", "compare", "count"] : ["group", "count"];

    const csv = [
      headers.join(","),
      ...rows.map(row => headers.map(h => `"${String(row[h] ?? "").replaceAll('"', '""')}"`).join(","))
    ].join("\n");

    navigator.clipboard?.writeText(csv);
  }



  // ============================================================
  // Taller internal mode fix: "Títulos" vs "Mesa de análisis"
  // ============================================================

  function normalizeWorkshopModeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function getWorkshopTallerPanel() {
    return document.querySelector('.tab-panel[data-panel="taller"]');
  }

  function renameWorkshopInternalExploreToTitles() {
    const tallerPanel = getWorkshopTallerPanel();
    if (!tallerPanel) return;

    const candidates = tallerPanel.querySelectorAll("button, a, span, strong, h2, h3, p");

    candidates.forEach(el => {
      const raw = el.textContent || "";
      const text = raw.trim();
      const normalized = normalizeWorkshopModeText(text);

      // Solo renombrar la etiqueta interna exacta.
      // No tocamos textos largos tipo "Explorar un tema..." ni el tab global.
      if (normalized === "explorar") {
        el.textContent = raw.replace(/Explorar/i, "Títulos");
      }

      if (normalized === "busqueda exacta" || normalized === "búsqueda exacta") {
        // No cambiamos esto; sigue siendo el método dentro de Títulos.
      }
    });
  }

  function detectWorkshopAnalysisModeFromActiveElements() {
    const tallerPanel = document.querySelector('.tab-panel[data-panel="taller"]');
    if (!tallerPanel) return false;

    // Fuente de verdad: sólo la navegación interna del Taller.
    // No leer .is-active dentro de #workshopAnalysisLab, porque la Mesa
    // tiene su propia nav de plantillas (.wa2-nav-item.is-active).
    const activeSectionButton = tallerPanel.querySelector(
      '.workshop-nav-btn[data-ws-section].is-active, [data-ws-section].is-active'
    );

    if (activeSectionButton) {
      return activeSectionButton.dataset.wsSection === "analysis";
    }

    const checkedAnalysisButton = tallerPanel.querySelector(
      '.workshop-nav-btn[data-ws-section="analysis"][aria-selected="true"]'
    );

    if (checkedAnalysisButton) return true;

    const checkedTitlesButton = tallerPanel.querySelector(
      '.workshop-nav-btn[data-ws-section="explore"][aria-selected="true"], .workshop-nav-btn[data-ws-section="titles"][aria-selected="true"]'
    );

    if (checkedTitlesButton) return false;

    // Fallback conservador: si no hay botón activo claro, Títulos.
    return false;
  }

  function setWorkshopAnalysisMode(isAnalysis) {
    document.body.classList.toggle("workshop-analysis-mode", Boolean(isAnalysis));
    document.body.classList.toggle("workshop-titles-mode", !Boolean(isAnalysis));
  }

  function syncWorkshopTitlesAndAnalysisMode() {
    renameWorkshopInternalExploreToTitles();

    const tallerPanel = getWorkshopTallerPanel();
    const lab = document.getElementById("workshopAnalysisLab");

    if (!tallerPanel || !lab) return;

    // Si por cualquier razón quedó fuera del panel Taller, regresarlo al Taller.
    if (!tallerPanel.contains(lab)) {
      const root =
        tallerPanel.querySelector("[data-workshop-root]") ||
        tallerPanel.querySelector(".workshop-main") ||
        tallerPanel;
      root.appendChild(lab);
    }

    const isAnalysis = detectWorkshopAnalysisModeFromActiveElements();
    setWorkshopAnalysisMode(isAnalysis);
  }

  function bindWorkshopTitlesAndAnalysisMode() {
    if (window.__workshopTitlesAnalysisModeBound) return;
    window.__workshopTitlesAnalysisModeBound = true;

    document.addEventListener("click", event => {
      const tallerPanel = getWorkshopTallerPanel();
      if (!tallerPanel) return;

      const target = event.target.closest("button, a, [role='tab'], [data-workshop-mode], [data-mode]");
      if (!target || !tallerPanel.contains(target)) return;

      const text = normalizeWorkshopModeText(target.textContent);

      if (text.includes("mesa") || text.includes("analisis")) {
        setWorkshopAnalysisMode(true);
        scheduleWorkshopChartResize("analysis-mode");
        setTimeout(syncWorkshopTitlesAndAnalysisMode, 30);
        return;
      }

      if (text.includes("titulos") || text.includes("explorar")) {
        setWorkshopAnalysisMode(false);
        setTimeout(syncWorkshopTitlesAndAnalysisMode, 30);
      }
    });

    const observer = new MutationObserver(() => {
      syncWorkshopTitlesAndAnalysisMode();
    });

    if (document.body) {
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "aria-selected", "data-active"]
      });
    }

    window.addEventListener("load", syncWorkshopTitlesAndAnalysisMode);
    document.addEventListener("DOMContentLoaded", syncWorkshopTitlesAndAnalysisMode);

    setTimeout(syncWorkshopTitlesAndAnalysisMode, 100);
    setTimeout(syncWorkshopTitlesAndAnalysisMode, 500);
    setTimeout(syncWorkshopTitlesAndAnalysisMode, 1200);
  }

  bindWorkshopTitlesAndAnalysisMode();

  function init() {
    const root = $("[data-workshop-root]");
    if (!root) return;

    bindEvents();
    ensureAnalysisLab();

    workshopScrollObserver.observe(document.body, {
      attributes: true,
      attributeFilter: ["data-tab", "class", "style"]
    });

    syncWorkshopScrollMode();
    loadFacets();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
