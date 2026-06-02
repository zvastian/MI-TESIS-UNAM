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


  
  
  let workshopActiveMode = "temporal";
  let workshopActiveChartView = "bar";
  let workshopActivePalette = "institutional";

const WORKSHOP_MODE_CONFIGS = {
    titles: {
      label: "Títulos",
      prompt: "Búsqueda exacta por título",
      hint: "Busca frases verificables en títulos limpios.",
      group_by: "year",
      compare_by: "",
      limit: "50",
      chartViews: [["bar", "Barras"], ["line", "Línea"], ["table", "Tabla"]]
    },
    temporal: {
      label: "Tiempo",
      prompt: "Evolución temporal",
      hint: "Observa cambios por año dentro del acervo.",
      group_by: "year",
      compare_by: "",
      limit: "60",
      chartViews: [["bar", "Barras"], ["line", "Línea"], ["area", "Área"]]
    },
    ranking: {
      label: "Ranking",
      prompt: "Orden de categorías",
      hint: "Identifica los grupos con mayor concentración.",
      group_by: "program",
      compare_by: "",
      limit: "20",
      chartViews: [["bar", "Barras"], ["lollipop", "Lollipop"], ["treemap", "Treemap"]]
    },
    comparison: {
      label: "Comparación",
      prompt: "Comparación de categorías",
      hint: "Cruza una dimensión principal con una segmentación.",
      group_by: "program",
      compare_by: "degree",
      limit: "40",
      chartViews: [["grouped_bar", "Barras"], ["stacked", "Apiladas"], ["table", "Tabla"]]
    },
    distribution: {
      label: "Distribución",
      prompt: "Distribución del conjunto",
      hint: "Revisa concentración y forma de una variable.",
      group_by: "year",
      compare_by: "",
      limit: "60",
      chartViews: [["bar", "Frecuencia"], ["area", "Área"], ["line", "Perfil"]]
    },
    partwhole: {
      label: "Parte del total",
      prompt: "Composición proporcional",
      hint: "Mide participación dentro del total filtrado.",
      group_by: "degree",
      compare_by: "",
      limit: "20",
      chartViews: [["donut", "Donut"], ["bar", "Barras"], ["treemap", "Treemap"]]
    },
    magnitude: {
      label: "Magnitud",
      prompt: "Tamaños absolutos",
      hint: "Compara volúmenes entre dimensiones.",
      group_by: "area",
      compare_by: "",
      limit: "20",
      chartViews: [["bar", "Barras"], ["treemap", "Treemap"], ["table", "Tabla"]]
    },
    advisors: {
      label: "Asesores",
      prompt: "Actividad de asesores",
      hint: "Explora patrones de dirección y concentración.",
      group_by: "advisor",
      compare_by: "",
      limit: "30",
      chartViews: [["bar", "Ranking"], ["lollipop", "Lollipop"], ["table", "Tabla"]]
    }
  };

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

      <section class="wa2-builder wa2-analysis-blocks" aria-label="Mesa de análisis cuantitativo">
        <nav class="wa2-mode-strip" id="analysisModeStrip" aria-label="Categorías de análisis">
          <button type="button" data-mode-strip="titles">Títulos</button>
          <button type="button" data-mode-strip="temporal">Tiempo</button>
          <button type="button" data-mode-strip="ranking">Ranking</button>
          <button type="button" data-mode-strip="comparison">Comparación</button>
          <button type="button" data-mode-strip="distribution">Distribución</button>
          <button type="button" data-mode-strip="partwhole">Parte del total</button>
          <button type="button" data-mode-strip="magnitude">Magnitud</button>
          <button type="button" data-mode-strip="advisors">Asesores</button>
        </nav>
        <header class="wa2-blocks-head">
          <div>
            <p class="eyebrow">Mesa cuantitativa</p>
            <h3>Define el universo, mide y visualiza.</h3>
          </div>
          <p>
            Cada bloque representa una decisión analítica. La consulta técnica se conserva como método reproducible.
          </p>
        </header>

        <div class="wa2-block-grid">
          <article class="wa2-block wa2-block-universe">
            <span class="wa2-block-index">01</span>
            <div>
              <p class="eyebrow">Universo</p>
              <h4>Conjunto de tesis</h4>
            </div>
            <label class="wa2-block-wide">
              <span>Títulos que contienen</span>
              <input id="analysisTitleContains" type="text" placeholder="inteligencia artificial, banca, muralismo…" />
            </label>
            <div class="wa2-block-row">
              <label>
                <span>Desde</span>
                <input id="analysisYearMin" type="number" min="1900" max="2026" placeholder="2000" />
              </label>
              <label>
                <span>Hasta</span>
                <input id="analysisYearMax" type="number" min="1900" max="2026" placeholder="2026" />
              </label>
            </div>
          </article>

          <article class="wa2-block">
            <span class="wa2-block-index">02</span>
            <div>
              <p class="eyebrow">Medición</p>
              <h4>Métrica</h4>
            </div>
            <label>
              <span>Medir</span>
              <select id="analysisMetric">
                <option value="count">número de tesis</option>
                <option value="distinct_programs" disabled>programas distintos</option>
                <option value="distinct_advisors" disabled>asesores distintos</option>
                <option value="share" disabled>participación porcentual</option>
              </select>
            </label>
          </article>

          <article class="wa2-block">
            <span class="wa2-block-index">03</span>
            <div>
              <p class="eyebrow">Agrupación</p>
              <h4>Dimensión principal</h4>
            </div>
            <label>
              <span>Agrupar por</span>
              <select id="analysisGroupBy">
                <option value="year">año</option>
                <option value="program">programa</option>
                <option value="area">área</option>
                <option value="degree">nivel</option>
                <option value="plantel">plantel</option>
                <option value="advisor">asesor</option>
              </select>
            </label>
          </article>

          <article class="wa2-block">
            <span class="wa2-block-index">04</span>
            <div>
              <p class="eyebrow">Segmentación</p>
              <h4>Comparación</h4>
            </div>
            <label>
              <span>Segmentar por</span>
              <select id="analysisCompareBy">
                <option value="">sin segmentación</option>
                <option value="area">área</option>
                <option value="degree">nivel</option>
                <option value="program">programa</option>
                <option value="plantel">plantel</option>
              </select>
            </label>
          </article>

          <article class="wa2-block wa2-block-output">
            <span class="wa2-block-index">05</span>
            <div>
              <p class="eyebrow">Salida</p>
              <h4>Lectura visual</h4>
            </div>
            <label>
              <span>Límite</span>
              <input id="analysisLimit" type="number" min="5" max="100" value="80" />
            </label>
            <div class="wa2-mode-tools" id="analysisModeTools">
              <div>
                <span>Vista</span>
                <div class="wa2-chart-toolbar" id="analysisChartViews"></div>
              </div>
              <div>
                <span>Color</span>
                <div class="wa2-palette-toolbar" id="analysisPaletteViews">
                  <button type="button" data-palette="institutional">Institucional</button>
                  <button type="button" data-palette="sober">Sobria</button>
                  <button type="button" data-palette="contrast">Contraste</button>
                  <button type="button" data-palette="mono">Mono</button>
                </div>
              </div>
            </div>
          </article>
        </div>

        <footer class="wa2-block-footer">
          <div class="wa2-query-note" id="analysisQueryNote">
            universe=all · metric=count · group_by=year · compare_by=none · chart_type=auto
          </div>
          <button class="workshop-primary wa2-run" id="analysisRunBtn" type="button">
            Ejecutar análisis
          </button>
        </footer>
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


  

  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function scheduleWorkshopChartResize(reason = "unknown") {
    requestAnimationFrame(() => {
      resizeWorkshopCharts();
      setTimeout(resizeWorkshopCharts, 80);
      setTimeout(resizeWorkshopCharts, 240);
    });
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function renderAnalysisDemo(kind) {
    const chart = ensureEChart("analysisDemoChart");
    if (!chart) return;

    const years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"];
    const values = [18, 22, 19, 28, 34, 42, 57, 73];

    if (kind === "partwhole") {
      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "item" },
        legend: {
          bottom: 0,
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { color: WORKSHOP_CHART_MUTED, fontSize: 11 }
        },
        series: [{
          type: "pie",
          radius: ["46%", "72%"],
          center: ["50%", "46%"],
          avoidLabelOverlap: true,
          itemStyle: {
            borderColor: "#fff",
            borderWidth: 2
          },
          label: {
            color: WORKSHOP_CHART_MUTED,
            fontSize: 11,
            formatter: "{b}"
          },
          labelLine: {
            lineStyle: { color: WORKSHOP_CHART_AXIS }
          },
          data: [
            { name: "Área 1", value: 31 },
            { name: "Área 2", value: 42 },
            { name: "Área 3", value: 21 },
            { name: "Área 4", value: 10 }
          ]
        }]
      }), true);
      return;
    }

    if (kind === "ranking" || kind === "magnitude" || kind === "comparison") {
      const labels = kind === "comparison"
        ? ["Economía", "Derecho", "Arquitectura", "Medicina", "Historia"]
        : ["Programa A", "Programa B", "Programa C", "Programa D", "Programa E"];
      const counts = kind === "comparison" ? [92, 81, 64, 58, 47] : [116, 98, 74, 63, 41];

      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "axis", axisPointer: { type: "shadow" } },
        grid: workshopGridStyle({ left: 108, top: 24, bottom: 24 }),
        xAxis: workshopValueAxis(),
        yAxis: workshopCategoryAxis(labels, {
          inverse: true,
          axisLabel: {
            color: WORKSHOP_CHART_MUTED,
            fontSize: 11,
            formatter: value => shortChartLabel(value, 16)
          },
          splitLine: { show: false }
        }),
        series: [{
          type: "bar",
          data: counts,
          barWidth: 16,
          itemStyle: { borderRadius: [0, 2, 2, 0] },
          label: {
            show: true,
            position: "right",
            color: WORKSHOP_CHART_MUTED,
            fontSize: 10
          }
        }]
      }), true);
      return;
    }

    if (kind === "distribution") {
      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "axis" },
        grid: workshopGridStyle({ top: 26, bottom: 34 }),
        xAxis: workshopCategoryAxis(["0-10", "11-20", "21-30", "31-40", "41-50", "51+"], {
          splitLine: { show: false }
        }),
        yAxis: workshopValueAxis(),
        series: [{
          type: "bar",
          data: [14, 38, 62, 45, 24, 11],
          barWidth: 24,
          itemStyle: { color: WORKSHOP_CHART_COLORS[2], borderRadius: [2, 2, 0, 0] }
        }]
      }), true);
      return;
    }

    chart.setOption(workshopBaseOption({
      tooltip: { ...workshopTooltipStyle(), trigger: "axis" },
      grid: workshopGridStyle({ top: 28, bottom: 34 }),
      xAxis: workshopCategoryAxis(years, {
        splitLine: { show: false }
      }),
      yAxis: workshopValueAxis(),
      series: [{
        type: "line",
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2, color: WORKSHOP_CHART_COLORS[0] },
        itemStyle: { color: WORKSHOP_CHART_COLORS[0], borderColor: "#fff", borderWidth: 1.5 },
        areaStyle: { opacity: .26, color: WORKSHOP_CHART_COLORS[0] },
        label: {
          show: true,
          position: "top",
          color: WORKSHOP_CHART_COLORS[0],
          fontSize: 10,
          formatter: params => params.dataIndex === 0 || params.dataIndex === values.length - 1 ? params.value : ""
        },
        data: values
      }]
    }), true);

    setTimeout(resizeWorkshopCharts, 40);
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
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


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function bindAnalysisTemplates() {
    document.querySelectorAll(".wa2-nav-item").forEach(btn => {
      btn.addEventListener("click", () => {
        applyAnalysisTemplate(btn.dataset.template || "temporal");
      });
    });
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
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
      chart_type: workshopActiveChartView || "auto"
    };
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  async function runAnalysis() {
    if (window.__NODO_WORKSHOP_STUDIO_MODE === "titles") {
      return runTitlesAnalysis();
    }
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


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function renderAnalysisReport(report) {
    renderAnalysisSummary(report);
    renderAnalysisChart(report);
    renderAnalysisTable(report.table || []);
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
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
      <strong>${formatNumber(summary.total_rows || 0)} TESIS${escapeHTML(parquetDisplay(topic))}</strong>
      <p>${escapeHTML(editorial.summary || `Agrupación por ${group}. La tabla inferior conserva los datos para auditar o reutilizar la consulta.`)}</p>
    `;
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function renderAnalysisChart(report) {
    const chartData = report.chart?.data || [];
    const chartType = workshopActiveChartView || report.chart?.type || "bar";
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


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function renderAnalysisSimpleChart(chart, chartData, groupBy, chartType) {
    const rows = chartData.slice(0, 80);
    const labels = rows.map(row => parquetDisplay(row.group));
    const values = rows.map(row => Number(row.count || 0));
    const isTemporal = groupBy === "year";

    if (chartType === "donut") {
      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "item" },
        legend: {
          bottom: 0,
          type: "scroll",
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { color: WORKSHOP_CHART_MUTED, fontSize: 11 }
        },
        series: [{
          type: "pie",
          radius: ["44%", "70%"],
          center: ["50%", "45%"],
          itemStyle: { borderColor: "#fff", borderWidth: 2 },
          label: { color: WORKSHOP_CHART_MUTED, fontSize: 11, formatter: "{b}" },
          labelLine: { lineStyle: { color: WORKSHOP_CHART_AXIS } },
          data: rows.map(row => ({ name: parquetDisplay(row.group), value: Number(row.count || 0) }))
        }]
      }), true);
      return;
    }

    if (chartType === "treemap") {
      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "item" },
        series: [{
          type: "treemap",
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          label: { show: true, color: "#fff", fontSize: 11, formatter: "{b}" },
          upperLabel: { show: false },
          itemStyle: { borderColor: "#fff", borderWidth: 2 },
          data: rows.slice(0, 24).map(row => ({ name: parquetDisplay(row.group), value: Number(row.count || 0) }))
        }]
      }), true);
      return;
    }

    if (isTemporal) {
      const asBar = chartType === "bar";
      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "axis" },
        grid: workshopGridStyle({ top: 34, bottom: 44 }),
        xAxis: workshopCategoryAxis(labels, {
          splitLine: { show: false },
          axisLabel: { color: WORKSHOP_CHART_MUTED, fontSize: 11, rotate: labels.length > 18 ? 35 : 0 }
        }),
        yAxis: workshopValueAxis(),
        series: [{
          type: asBar ? "bar" : "line",
          smooth: !asBar,
          symbolSize: asBar ? 0 : 5,
          barWidth: asBar ? 16 : undefined,
          lineStyle: asBar ? undefined : { width: 2, color: WORKSHOP_CHART_COLORS[0] },
          itemStyle: { color: WORKSHOP_CHART_COLORS[0], borderColor: "#fff", borderWidth: asBar ? 0 : 1.5, borderRadius: asBar ? [2,2,0,0] : 0 },
          areaStyle: !asBar && chartType === "area" ? { opacity: .24, color: WORKSHOP_CHART_COLORS[0] } : undefined,
          data: values
        }]
      }), true);
      return;
    }

    const barRows = rows.slice(0, 30);
    const barLabels = barRows.map(row => parquetDisplay(row.group));
    const barValues = barRows.map(row => Number(row.count || 0));

    if (chartType === "lollipop") {
      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "axis" },
        grid: workshopGridStyle({ left: 150, top: 28, bottom: 28 }),
        xAxis: workshopValueAxis(),
        yAxis: workshopCategoryAxis(barLabels, {
          inverse: true,
          axisLabel: { color: WORKSHOP_CHART_MUTED, fontSize: 11, formatter: value => shortChartLabel(value, 22) },
          splitLine: { show: false }
        }),
        series: [
          {
            type: "bar",
            data: barValues,
            barWidth: 2,
            itemStyle: { color: "rgba(37,42,51,.24)" },
            silent: true
          },
          {
            type: "scatter",
            symbolSize: 10,
            data: barValues,
            itemStyle: { color: WORKSHOP_CHART_COLORS[0] },
            label: { show: true, position: "right", color: WORKSHOP_CHART_MUTED, fontSize: 10 }
          }
        ]
      }), true);
      return;
    }

    chart.setOption(workshopBaseOption({
      tooltip: { ...workshopTooltipStyle(), trigger: "axis", axisPointer: { type: "shadow" } },
      grid: workshopGridStyle({ left: 150, top: 28, bottom: 28 }),
      xAxis: workshopValueAxis(),
      yAxis: workshopCategoryAxis(barLabels, {
        inverse: true,
        axisLabel: { color: WORKSHOP_CHART_MUTED, fontSize: 11, formatter: value => shortChartLabel(value, 22) },
        splitLine: { show: false }
      }),
      series: [{
        type: "bar",
        data: barValues,
        barWidth: 16,
        itemStyle: { color: WORKSHOP_CHART_COLORS[0], borderRadius: [0, 2, 2, 0] },
        label: { show: true, position: "right", color: WORKSHOP_CHART_MUTED, fontSize: 10 }
      }]
    }), true);
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function renderAnalysisCompareChart(chart, chartData, groupBy, compareBy, chartType) {
    const groups = [...new Set(chartData.map(row => row.group ?? ""))].slice(0, 28);
    const compares = [...new Set(chartData.map(row => row.compare ?? ""))].slice(0, 8);

    const byKey = new Map();
    chartData.forEach(row => {
      byKey.set(`${row.group ?? "Sin dato"}|||${row.compare ?? "Sin dato"}`, Number(row.count || 0));
    });

    const series = compares.map((compare, index) => ({
      name: parquetDisplay(compare),
      type: groupBy === "year" ? "line" : "bar",
      smooth: groupBy === "year",
      symbolSize: groupBy === "year" ? 4 : 0,
      barMaxWidth: 18,
      stack: groupBy === "year" ? "total" : undefined,
      areaStyle: groupBy === "year" ? { opacity: .16 } : undefined,
      lineStyle: groupBy === "year" ? { width: 1.8 } : undefined,
      itemStyle: {
        color: WORKSHOP_CHART_COLORS[index % WORKSHOP_CHART_COLORS.length],
        borderRadius: groupBy === "year" ? 0 : [2, 2, 0, 0]
      },
      data: groups.map(group => byKey.get(`${group}|||${compare}`) || 0)
    }));

    chart.setOption(workshopBaseOption({
      legend: {
        top: 0,
        type: "scroll",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: WORKSHOP_CHART_MUTED, fontSize: 11 }
      },
      tooltip: {
        ...workshopTooltipStyle(),
        trigger: "axis",
        axisPointer: { type: groupBy === "year" ? "line" : "shadow" }
      },
      grid: workshopGridStyle({ top: 56, bottom: 52 }),
      xAxis: workshopCategoryAxis(groups, {
        axisLabel: {
          color: WORKSHOP_CHART_MUTED,
          fontSize: 11,
          rotate: groups.length > 16 ? 35 : 0,
          formatter: value => shortChartLabel(value, 14)
        },
        splitLine: { show: groupBy === "year", lineStyle: { color: WORKSHOP_CHART_GRID } }
      }),
      yAxis: workshopValueAxis(),
      series
    }), true);
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
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
          <td><strong>${escapeHTML(parquetDisplay(row.group))}</strong></td>
          ${hasCompare ? `<td>${escapeHTML(parquetDisplay(row.compare))}</td>` : ""}
          <td>${formatNumber(count)}</td>
          <td>${pct}</td>
          <td><span class="wa2-reading">${reading}</span></td>
        </tr>
      `;
    }).join("");
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  async function copyAnalysisCSV() {
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


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  async function runTitlesAnalysis() {
    const input = document.getElementById("analysisTitleContains");
    const limit = Number(document.getElementById("analysisLimit")?.value || 100);
    const query = input?.value?.trim();

    if (!query) {
      const summaryEl = document.getElementById("analysisSummary");
      if (summaryEl) {
        summaryEl.innerHTML = `
          <span>Títulos</span>
          <strong>AGREGA UNA CONSULTA</strong>
          <p>Escribe una palabra o frase para buscar en títulos limpios.</p>
        `;
      }
      return;
    }

    const summaryEl = document.getElementById("analysisSummary");
    if (summaryEl) {
      summaryEl.innerHTML = `
        <span>Consultando</span>
        <strong>TÍTULOS LIMPIOS</strong>
        <p>Ejecutando búsqueda exacta sobre title_norm.</p>
      `;
    }

    const report = await fetchJSON("/api/workshop/exact", {
      method: "POST",
      body: JSON.stringify({
        query,
        match_mode: "phrase",
        limit: Math.max(1, Math.min(200, limit || 100))
      })
    });

    window.__lastWorkshopTitles = report;
    renderTitlesInsideAnalysis(report);
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function renderTitlesInsideAnalysis(report) {
    const summaryEl = document.getElementById("analysisSummary");
    const chart = ensureEChart("analysisChart");

    if (summaryEl) {
      const total = report.summary?.total_matches || 0;
      const first = report.summary?.first_year;
      const last = report.summary?.last_year;
      summaryEl.innerHTML = `
        <span>Títulos</span>
        <strong>${formatNumber(total)} TESIS</strong>
        <p>Consulta “${escapeHTML(parquetDisplay(report.query || ""))}” · periodo ${escapeHTML(first && last ? `${first}–${last}` : "NO DETERMINADO")}.</p>
      `;
    }

    const rows = report.charts?.by_year?.data || [];
    if (chart) {
      const labels = rows.map(row => parquetDisplay(row.group ?? row.year ?? row[0]));
      const values = rows.map(row => Number(row.count ?? row.value ?? row[1] ?? 0));

      chart.setOption(workshopBaseOption({
        tooltip: { ...workshopTooltipStyle(), trigger: "axis" },
        grid: workshopGridStyle({ top: 34, bottom: 44 }),
        xAxis: workshopCategoryAxis(labels, {
          splitLine: { show: false },
          axisLabel: { color: WORKSHOP_CHART_MUTED, fontSize: 11, rotate: labels.length > 18 ? 35 : 0 }
        }),
        yAxis: workshopValueAxis(),
        series: [{
          type: "bar",
          data: values,
          barWidth: 16,
          itemStyle: { color: WORKSHOP_CHART_COLORS[0], borderRadius: [2,2,0,0] }
        }]
      }), true);
    }

    const tableRows = report.tables?.top_theses || [];
    renderAnalysisTable(tableRows.map(row => ({
      group: row.title,
      compare: row.program || row.degree || "",
      count: row.year || 0
    })));

    scheduleWorkshopChartResize("titles-analysis");
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function applyWorkshopModeControls(mode) {
    if (!WORKSHOP_MODE_CONFIGS[mode]) return;

    workshopActiveMode = mode;
    const cfg = WORKSHOP_MODE_CONFIGS[mode];

    const groupBy = document.getElementById("analysisGroupBy");
    const compareBy = document.getElementById("analysisCompareBy");
    const summaryEl = document.getElementById("analysisSummary");
    const chartTitle = document.getElementById("analysisChartTitle");
    const builder = document.querySelector(".wa2-builder");

    if (groupBy) groupBy.value = cfg.group_by;
    if (compareBy) compareBy.value = cfg.compare_by;

    if (!cfg.chartViews.some(([value]) => value === workshopActiveChartView)) {
      workshopActiveChartView = cfg.chartViews[0][0];
    }

    if (summaryEl) {
      summaryEl.innerHTML = `
        <span>${escapeHTML(cfg.label)}</span>
        <strong>${escapeHTML(parquetDisplay(cfg.prompt))}</strong>
        <p>${escapeHTML(cfg.hint)} Ajusta tema, años y agrupación antes de generar.</p>
      `;
    }

    if (chartTitle) {
      const active = cfg.chartViews.find(([value]) => value === workshopActiveChartView);
      chartTitle.textContent = active ? active[1] : cfg.label;
    }
    const views = document.getElementById("analysisChartViews");
    if (views) {
      views.innerHTML = cfg.chartViews.map(([value, label]) => `
        <button type="button" data-chart-view="${escapeHTML(value)}" class="${value === workshopActiveChartView ? "is-active" : ""}">
          ${escapeHTML(label)}
        </button>
      `).join("");
    }

    document.querySelectorAll("[data-palette]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.palette === workshopActivePalette);
    });

    const note = document.getElementById("analysisQueryNote");
    if (note) {
      note.textContent = `modo=${mode} · group_by=${cfg.group_by} · compare_by=${cfg.compare_by || "none"} · vista=${workshopActiveChartView} · paleta=${workshopActivePalette}`;
    }
  }


  /* RESTORED FROM workshop.before_graphs_first_t_image_1780372084.js */
  function applyTitlesModeControls() {
    const lab = document.getElementById("workshopAnalysisLab");
    if (lab) {
      lab.classList.add("wa2-mode-titles");
      lab.classList.remove("wa2-mode-temporal", "wa2-mode-ranking", "wa2-mode-comparison", "wa2-mode-distribution", "wa2-mode-partwhole", "wa2-mode-magnitude", "wa2-mode-advisors");
    }

    document.querySelectorAll("[data-mode-strip]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.modeStrip === "titles");
    });

    const groupBy = document.getElementById("analysisGroupBy");
    const compareBy = document.getElementById("analysisCompareBy");
    const limit = document.getElementById("analysisLimit");
    const summaryEl = document.getElementById("analysisSummary");
    const note = document.getElementById("analysisQueryNote");

    if (groupBy) groupBy.value = "year";
    if (compareBy) compareBy.value = "";
    if (limit) limit.value = "100";

    if (summaryEl) {
      summaryEl.innerHTML = `
        <span>Títulos</span>
        <strong>BÚSQUEDA EXACTA EN TÍTULOS</strong>
        <p>Consulta el título limpio normalizado y genera evidencia temporal, disciplinar y tabular.</p>
      `;
    }

    if (note) {
      note.textContent = "modo=titles · endpoint=/api/workshop/exact · match_mode=phrase";
    }

    const views = document.getElementById("analysisChartViews");
    if (views) {
      views.innerHTML = `
        <button type="button" data-chart-view="time_bar" class="is-active">Años</button>
        <button type="button" data-chart-view="bar">Ranking</button>
        <button type="button" data-chart-view="donut">Composición</button>
      `;
    }
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


  function setWorkshopStudioSpace(space) {
    const normalized = space === "create" ? "create" : "graphs";
    const empty = document.getElementById("workshopStudioEmpty");
    const host = document.getElementById("workshopStudioHost");

    document.body.classList.toggle("workshop-space-graphs", normalized === "graphs");
    document.body.classList.toggle("workshop-space-create", normalized === "create");

    document.querySelectorAll("[data-ws4-space]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.ws4Space === normalized);
    });

    if (normalized === "graphs") {
      if (host) {
        host.hidden = true;
        host.style.display = "none";
      }

      if (empty) {
        empty.hidden = false;
        empty.style.display = "grid";
        const title = empty.querySelector("h3");
        const copy = empty.querySelector("p");
        if (title) title.textContent = "¡EXPLORA LA INFORMACIÓN!";
        if (copy) copy.textContent = "Los gráficos que guardes aparecerán aquí.";
      }

      document.body.classList.remove("workshop-analysis-mode", "workshop-titles-mode");
      window.__NODO_WORKSHOP_STUDIO_SPACE = "graphs";
      return;
    }

    if (empty) {
      empty.hidden = true;
      empty.style.display = "none";
    }

    if (host) {
      host.hidden = false;
      host.style.display = "block";
    }

    window.__NODO_WORKSHOP_STUDIO_SPACE = "create";

    ensureAnalysisLab();
    prepareWorkshopStudioPanels();

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
    if (studio) {
      if (studio.parentElement !== tallerPanel) {
        tallerPanel.appendChild(studio);
      }
      return studio;
    }

    const root = tallerPanel;

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
            <h3>¡EXPLORA LA INFORMACIÓN!</h3>
            <p>Los gráficos que guardes aparecerán aquí.</p>
            <button class="ws3-empty-create" type="button" data-ws4-space="create">Crear</button>
          </section>
          <div class="ws3-host" id="workshopStudioHost" hidden></div>
        </main>
      </section>
    `;

    root.appendChild(studio);
    setWorkshopStudioSpace("graphs");
    return studio;
  }

function startWorkshopStudio() {
    const studio = ensureWorkshopStudio();
    if (!studio) return;

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
        if (typeof applyAnalysisTemplate === "function") applyAnalysisTemplate(template);
        if (typeof applyWorkshopModeControls === "function") applyWorkshopModeControls(mode);
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
      event.preventDefault();
      setWorkshopStudioSpace(spaceBtn.dataset.ws4Space || "create");
      return;
    }
  });


})();
