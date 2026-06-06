
/* TALLER CURADO: módulos visuales + burbujas reales */
(() => {

  function workshopDataFetch(apiUrl, staticPath) {
    const cfg = window.NODO_CONFIG || {};
    if (cfg.mode === "static") {
      const base = String(cfg.dataBaseUrl || "./data").replace(/\/$/, "");
      return fetch(`${base}/${staticPath}`, { cache: "no-store" });
    }
    const apiBase = String(cfg.apiBase || "").replace(/\/$/, "");
    return fetch(`${apiBase}${apiUrl}`, { cache: "no-store" });
  }

  const TOOLS = {
    bubbles: {
      label: "Burbujas",
      kicker: "Exploración multivariable",
      title: "Trayectorias acumuladas del acervo",
      text: "Cada burbuja representa una entidad. El tiempo avanza con el slider; el eje X mide antigüedad activa y el eje Y producción acumulada."
    },
    ranking: {
      label: "Ranking",
      kicker: "Ordenamiento",
      title: "Mayores concentraciones del acervo",
      text: "Módulo preparado para ordenar programas, planteles, áreas o asesores."
    },
    heatmap: {
      label: "Heatmap",
      kicker: "Matriz temporal",
      title: "Intensidad por categoría y año",
      text: "Módulo preparado para detectar concentraciones por año y categoría."
    },    series: {
      label: "Series",
      kicker: "Evolución",
      title: "Tendencias anuales del acervo",
      text: "Módulo preparado para observar crecimiento, caída o aparición de temas."
    }
  };

  const AREA_COLORS = {
    "AREA 1": "#d86b65",
    "AREA 2": "#5fa5ad",
    "AREA 3": "#d9ad68",
    "AREA 4": "#7b8794",
    "": "#9aa4ad"
  };

  const LEVEL_COLORS = {
    "LICENCIATURA": "#b8d8ba",
    "ESPECIALIDAD": "#86b58f",
    "MAESTRÍA": "#4f8f68",
    "MAESTRIA": "#4f8f68",
    "DOCTORADO": "#1f5f45",
    "": "#86b58f"
  };

  const RANKING_YEAR_MIN = 1873;
  const RANKING_YEAR_MAX = 2026;

  const DIMENSION_LABELS = {
    advisor: "Asesores",
    program: "Programas",
    plantel: "Planteles",
    level: "Niveles"
  };

  let activeTool = "bubbles";
  let bubbleDimension = "advisor";
  let bubbleData = null;
  let bubbleYear = null;
  let bubbleChart = null;
  let bubblePlaying = false;
  let bubbleTimer = null;

  let rankingData = null;
  let rankingDimension = "program";
  let rankingView = "bar";
  let rankingLimit = 25;
  let rankingYearMin = RANKING_YEAR_MIN;
  let rankingYearMax = RANKING_YEAR_MAX;
  let rankingAreaFilter = new Set(["AREA 1", "AREA 2", "AREA 3", "AREA 4"]);
  let rankingLevelFilter = new Set(["LICENCIATURA", "ESPECIALIDAD", "MAESTRÍA", "MAESTRIA", "DOCTORADO"]);
  let rankingChart = null;
  let bubbleRenderQueued = false;
  let bubbleRenderAnimated = true;
  let bubbleDomains = null;
  let bubbleAreaFilter = new Set(["AREA 1", "AREA 2", "AREA 3", "AREA 4"]);
  let bubbleLevelFilter = new Set(["LICENCIATURA", "ESPECIALIDAD", "MAESTRÍA", "MAESTRIA", "DOCTORADO"]);
  let bubbleSelectedIds = new Set();

  function cleanLegacy(tallerPanel) {
    tallerPanel.querySelectorAll(
      "main.workshop, #workshopStudio, #workshopAnalysisLab, .wa2, [data-workshop-root]"
    ).forEach(el => {
      el.hidden = true;
      el.style.display = "none";
      el.style.visibility = "hidden";
    });

    document.body.classList.remove(
      "workshop-analysis-mode",
      "workshop-titles-mode",
      "workshop-has-results",
      "workshop-space-create",
      "workshop-space-graphs",
      "workshop-studio-started"
    );
    document.body.classList.add("workshop-curated-tools");
  }

  function mountWorkshopCuratedTools() {
    const tallerPanel = document.querySelector('.tab-panel[data-panel="taller"]');
    if (!tallerPanel) return;

    cleanLegacy(tallerPanel);

    let shell = document.getElementById("workshopCuratedTools");
    if (!shell) {
      shell = document.createElement("section");
      shell.id = "workshopCuratedTools";
      shell.className = "wct-shell";
      shell.innerHTML = `
        <aside class="wct-sidebar" aria-label="Herramientas visuales">
          <p>Taller</p>
          ${Object.entries(TOOLS).map(([key, tool], index) => `
            <button type="button" data-workshop-tool="${key}" class="${index === 0 ? "is-active" : ""}">
              <span>${String(index + 1).padStart(2, "0")}</span>
              ${tool.label}
            </button>
          `).join("")}
        </aside>
        <main class="wct-main">
          <section class="wct-stage" id="workshopToolStage"></section>
          <section class="wct-controls" id="workshopToolControls"></section>
        </main>
      `;
      tallerPanel.prepend(shell);
    }

    shell.hidden = false;
    shell.style.display = "grid";

    shell.addEventListener("click", handleWorkshopClick);
    shell.addEventListener("input", handleWorkshopInput);
    shell.addEventListener("change", handleWorkshopChange);

    activeTool = activeTool || "bubbles";
    bubbleDimension = bubbleDimension || "advisor";

    requestAnimationFrame(() => {
      renderTool(activeTool);
    });
  }

  function handleWorkshopClick(event) {
    const toolBtn = event.target.closest("[data-workshop-tool]");
    if (toolBtn) {
      stopBubblePlayback();
      renderTool(toolBtn.dataset.workshopTool);
      return;
    }

    const playBtn = event.target.closest("#bubblePlayBtn");
    if (playBtn) {
      toggleBubblePlayback();
      return;
    }

    const clearBtn = event.target.closest("#bubbleClearSelectionBtn");
    if (clearBtn) {
      bubbleSelectedIds.clear();
      applyBubbleSelectionStyles();
    }
  }

  function handleWorkshopInput(event) {
    if (event.target.id === "bubbleYearSlider") {
      bubbleYear = Number(event.target.value);
      scheduleBubbleRender(false);
      return;
    }

    if (event.target.id === "rankingLimit") {
      rankingLimit = Number(event.target.value || 25);
      const label = document.getElementById("rankingLimitLabel");
      if (label) label.textContent = String(rankingLimit);
      return;
    }

  }

  function handleWorkshopChange(event) {
    if (event.target.id === "bubbleYearSlider") {
      bubbleYear = Number(event.target.value);
      scheduleBubbleRender(true);
      return;
    }

    if (event.target.id === "rankingDimension") {
      rankingDimension = event.target.value;
      loadRankingData();
      return;
    }

    if (event.target.id === "rankingView") {
      rankingView = event.target.value;
      renderRankingChart();
      return;
    }

    if (event.target.id === "rankingLimit") {
      rankingLimit = Number(event.target.value || 25);
      loadRankingData();
      return;
    }


    if (event.target.matches("[data-ranking-area]")) {
      const area = event.target.dataset.rankingArea;
      if (event.target.checked) rankingAreaFilter.add(area);
      else rankingAreaFilter.delete(area);
      loadRankingData();
      return;
    }

    if (event.target.matches("[data-ranking-level]")) {
      const level = event.target.dataset.rankingLevel;
      const aliases = level === "MAESTRÍA" ? ["MAESTRÍA", "MAESTRIA"] : [level];
      if (event.target.checked) aliases.forEach(v => rankingLevelFilter.add(v));
      else aliases.forEach(v => rankingLevelFilter.delete(v));
      loadRankingData();
      return;
    }

    if (event.target.matches("[data-bubble-area]")) {
      const area = event.target.dataset.bubbleArea;
      if (event.target.checked) {
        bubbleAreaFilter.add(area);
      } else {
        bubbleAreaFilter.delete(area);
      }
      scheduleBubbleRender(true);
      return;
    }

    if (event.target.matches("[data-bubble-level]")) {
      const level = event.target.dataset.bubbleLevel;
      if (event.target.checked) {
        bubbleLevelFilter.add(level);
      } else {
        bubbleLevelFilter.delete(level);
      }
      scheduleBubbleRender(true);
      return;
    }

    if (event.target.id === "bubbleDimensionSelect") {
      bubbleDimension = event.target.value;
      bubbleData = null;
      bubbleDomains = null;
      bubbleAreaFilter = new Set(["AREA 1", "AREA 2", "AREA 3", "AREA 4"]);
      bubbleLevelFilter = new Set(["LICENCIATURA", "ESPECIALIDAD", "MAESTRÍA", "MAESTRIA", "DOCTORADO"]);
      bubbleSelectedIds.clear();
      stopBubblePlayback();

      if (bubbleChart) {
        try { bubbleChart.dispose(); } catch (err) {}
        bubbleChart = null;
      }

      renderBubbleShell();
      loadBubbleData();
      return;
    }
  }

  function renderTool(toolKey) {
    activeTool = TOOLS[toolKey] ? toolKey : "bubbles";

    document.querySelectorAll("[data-workshop-tool]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.workshopTool === activeTool);
    });

    if (activeTool === "bubbles") {
      if (bubbleChart) {
        try { bubbleChart.dispose(); } catch (err) {}
        bubbleChart = null;
      }

      renderBubbleShell();
      loadBubbleData();
      return;
    }

    if (activeTool === "ranking") {
      renderRankingShell();
      loadRankingData();
      return;
    }

    renderPlaceholderTool(activeTool);
  }

  function renderBubbleFilterControl() {
    if (bubbleDimension === "level") {
      return `
        <fieldset class="wct-control wct-area-filter" data-filter-kind="level">
          <legend>Nivel</legend>
          ${[
            ["LICENCIATURA", "Licenciatura"],
            ["ESPECIALIDAD", "Especialidad"],
            ["MAESTRÍA", "Maestría"],
            ["DOCTORADO", "Doctorado"]
          ].map(([value, label]) => `
            <label>
              <input type="checkbox" data-bubble-level="${value}" ${bubbleLevelFilter.has(value) || (value === "MAESTRÍA" && bubbleLevelFilter.has("MAESTRIA")) ? "checked" : ""} />
              <span>${label}</span>
            </label>
          `).join("")}
        </fieldset>
      `;
    }

    return `
      <fieldset class="wct-control wct-area-filter" data-filter-kind="area">
        <legend>Área</legend>
        ${["AREA 1", "AREA 2", "AREA 3", "AREA 4"].map(area => `
          <label>
            <input type="checkbox" data-bubble-area="${area}" ${bubbleAreaFilter.has(area) ? "checked" : ""} />
            <span>${area.replace("AREA", "Área")}</span>
          </label>
        `).join("")}
      </fieldset>
    `;
  }

  function renderBubbleShell() {
    const stage = document.getElementById("workshopToolStage");
    const controls = document.getElementById("workshopToolControls");
    if (!stage || !controls) return;

    if (bubbleChart) {
      try { bubbleChart.dispose(); } catch (err) {}
      bubbleChart = null;
    }

    stage.innerHTML = `
      <div class="wct-chart-frame wct-chart-bubbles">
        <div class="wct-chart-head">
          <span>Exploración multivariable</span>
          <strong id="bubbleDimensionTitle">${DIMENSION_LABELS[bubbleDimension]}</strong>
        </div>
        <div class="wct-echart" id="bubbleChart"></div>
      </div>
    `;

    controls.innerHTML = `
      <div class="wct-control-summary">
        <span>Módulo activo</span>
        <strong>Burbujas</strong>
      </div>

      <label class="wct-control">
        <span>Entidad</span>
        <select id="bubbleDimensionSelect">
          <option value="advisor"${bubbleDimension === "advisor" ? " selected" : ""}>Asesores</option>
          <option value="program"${bubbleDimension === "program" ? " selected" : ""}>Programas</option>
          <option value="plantel"${bubbleDimension === "plantel" ? " selected" : ""}>Planteles</option>
          <option value="level"${bubbleDimension === "level" ? " selected" : ""}>Niveles</option>
        </select>
      </label>

      ${renderBubbleFilterControl()}

      <label class="wct-control wct-year-control">
        <span>Año</span>
        <input id="bubbleYearSlider" type="range" min="1954" max="2026" value="${bubbleYear || 2026}" />
      </label>

      <div class="wct-year-readout">
        <span>Corte</span>
        <strong id="bubbleYearLabel">${bubbleYear || 2026}</strong>
      </div>

      <button class="wct-run" id="bubblePlayBtn" type="button">Reproducir</button>
      <button class="wct-clear-selection" id="bubbleClearSelectionBtn" type="button">Limpiar selección</button>
    `;
  }

  async function loadBubbleData() {
    const stage = document.getElementById("bubbleChart");
    if (stage) {
      stage.innerHTML = `<div class="wct-loading">Cargando dataset de ${DIMENSION_LABELS[bubbleDimension].toLowerCase()}...</div>`;
    }

    try {
      const response = await workshopDataFetch(`/api/workshop/tools/bubbles?dimension=${encodeURIComponent(bubbleDimension)}&limit=50`, `workshop/bubbles_${encodeURIComponent(bubbleDimension)}.json`);
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `HTTP ${response.status}`);
      }

      bubbleData = await response.json();
      bubbleDomains = computeBubbleDomains(bubbleData);
      const years = bubbleData.years || [];
      bubbleYear = years.length ? years[years.length - 1] : 2026;

      const slider = document.getElementById("bubbleYearSlider");
      if (slider && years.length) {
        slider.min = String(years[0]);
        slider.max = String(years[years.length - 1]);
        slider.value = String(bubbleYear);
      }

      const title = document.getElementById("bubbleDimensionTitle");
      if (title) title.textContent = DIMENSION_LABELS[bubbleDimension] || bubbleDimension;

      try {
        scheduleBubbleRender(true);
      } catch (renderErr) {
        console.error("[NODO Taller] Error renderizando burbujas", renderErr);
        if (stage) {
          stage.innerHTML = `<div class="wct-loading is-error">Datos cargados, pero falló el render: ${escapeHTML(renderErr.message)}</div>`;
        }
      }
    } catch (err) {
      console.error("[NODO Taller] Error cargando burbujas", err);
      if (stage) {
        stage.innerHTML = `<div class="wct-loading is-error">No se pudo cargar Burbujas: ${escapeHTML(err.message)}</div>`;
      }
    }
  }

  function scheduleBubbleRender(animated = true) {
    bubbleRenderAnimated = animated;
    if (bubbleRenderQueued) return;

    bubbleRenderQueued = true;
    requestAnimationFrame(() => {
      bubbleRenderQueued = false;
      renderBubbleChart({ animated: bubbleRenderAnimated });
    });
  }

  function computeBubbleDomains(data) {
    let maxCumulative = 1;
    let maxAge = 10;

    for (const entity of data?.entities || []) {
      for (const item of entity.series || []) {
        maxCumulative = Math.max(maxCumulative, Number(item.cumulative || 0));
        maxAge = Math.max(maxAge, Number(item.active_age || 0));
      }
    }

    return {
      maxCumulative,
      maxAge,
      maxY: maxCumulative
    };
  }

  function renderBubbleChart({ animated = true } = {}) {
    if (!bubbleData) return;

    const el = document.getElementById("bubbleChart");
    if (!el) return;

    const yearLabel = document.getElementById("bubbleYearLabel");
    if (yearLabel) yearLabel.textContent = String(bubbleYear);

    const clearBtn = document.getElementById("bubbleClearSelectionBtn");
    if (clearBtn) {
      clearBtn.disabled = bubbleSelectedIds.size === 0;
      clearBtn.textContent = bubbleSelectedIds.size
        ? `Limpiar (${bubbleSelectedIds.size})`
        : "Limpiar selección";
    }

    const slider = document.getElementById("bubbleYearSlider");
    if (slider && Number(slider.value) !== Number(bubbleYear)) {
      slider.value = String(bubbleYear);
    }

    const points = buildBubblePoints(bubbleData, bubbleYear);
    if (!points.length) {
      if (!window.echarts) {
        el.innerHTML = "";
        return;
      }

      if (el.querySelector(".wct-loading")) {
        el.innerHTML = "";
        if (bubbleChart) {
          try { bubbleChart.dispose(); } catch (err) {}
          bubbleChart = null;
        }
      }

      if (!bubbleChart) {
        bubbleChart = window.echarts.init(el, null, { renderer: "canvas" });
        window.addEventListener("resize", () => bubbleChart?.resize());
      }

      bubbleChart.setOption({
        animation: false,
        grid: { left: 56, right: 28, top: 42, bottom: 52, containLabel: true },
        xAxis: {
          type: "value",
          name: "Antigüedad activa",
          min: 0,
          max: bubbleDomains?.maxAge || 10,
          nameLocation: "middle",
          nameGap: 32,
          splitLine: { lineStyle: { color: "rgba(7,29,56,.08)" } },
          axisLine: { lineStyle: { color: "rgba(7,29,56,.35)" } },
          axisLabel: { color: "rgba(7,29,56,.58)" }
        },
        yAxis: {
          type: "value",
          name: "Producción acumulada",
          min: 0,
          max: bubbleDomains?.maxY || 10,
          nameLocation: "middle",
          nameGap: 44,
          splitLine: { lineStyle: { color: "rgba(7,29,56,.08)" } },
          axisLine: { lineStyle: { color: "rgba(7,29,56,.35)" } },
          axisLabel: { color: "rgba(7,29,56,.58)" }
        },
        graphic: [{
          type: "text",
          left: "center",
          top: "middle",
          silent: true,
          style: {
            text: String(bubbleYear),
            fill: "rgba(7,29,56,.055)",
            font: "800 150px Inter, system-ui, sans-serif"
          }
        }],
        series: [{ type: "scatter", data: [] }]
      }, true);

      return;
    }

    const maxCumulative = bubbleDomains?.maxCumulative || Math.max(1, ...points.map(d => d.cumulative));
    const maxAge = bubbleDomains?.maxAge || Math.max(10, ...points.map(d => d.active_age));
    const maxY = bubbleDomains?.maxY || Math.max(10, ...points.map(d => d.cumulative));

    if (!window.echarts) {
      el.innerHTML = `<div class="wct-loading is-error">ECharts no está disponible.</div>`;
      return;
    }

    if (el.querySelector(".wct-loading")) {
      el.innerHTML = "";
      if (bubbleChart) {
        try { bubbleChart.dispose(); } catch (err) {}
        bubbleChart = null;
      }
    }

    if (!bubbleChart) {
      bubbleChart = window.echarts.init(el, null, { renderer: "canvas" });
      window.addEventListener("resize", () => bubbleChart?.resize());

      bubbleChart.on("click", params => {
        const id = params?.data?.raw?.id;
        if (!id) return;

        if (bubbleSelectedIds.has(id)) {
          bubbleSelectedIds.delete(id);
        } else {
          bubbleSelectedIds.add(id);
        }

        applyBubbleSelectionStyles();
      });
    }

    bubbleChart.setOption({
      animation: animated,
      animationDuration: animated ? 420 : 0,
      animationDurationUpdate: animated ? 420 : 0,
      grid: { left: 56, right: 28, top: 42, bottom: 52, containLabel: true },
      color: Object.values(AREA_COLORS),
      tooltip: {
        trigger: "item",
        borderWidth: 1,
        borderColor: "rgba(7,29,56,.16)",
        formatter(params) {
          const d = params.data.raw;
          const name = formatBubbleEntityLabel(d.label);
          const firstYear = d.first_year || "inicio";
          const lastYear = d.last_year || bubbleYear;
          const program = formatBubbleEntityLabel(d.main_program || "SIN DATO");
          const plantel = formatBubbleEntityLabel(d.main_plantel || "SIN DATO");
          const area = d.main_area || "SIN DATO";
          const level = formatBubbleEntityLabel(d.main_level || "");

          return `
            <div class="wct-tooltip">
              <strong>${escapeHTML(name)}</strong>
              <div class="wct-tooltip-main">
                ${formatNumber(d.cumulative)} tesis acumuladas
              </div>
              <div>${formatNumber(d.year_count)} tesis en ${bubbleYear}</div>
              <hr/>
              <span>Actividad</span>
              <div>${escapeHTML(firstYear)}-${escapeHTML(bubbleYear)}: ${formatNumber(d.active_age)} años activos</div>
              <hr/>
              <span>Contexto dominante</span>
              <div>${escapeHTML(program)}</div>
              <div>${escapeHTML(plantel)}</div>
              <div>${escapeHTML(area)}${level ? `: ${escapeHTML(level)}` : ""}</div>
            </div>
          `;
        }
      },
      xAxis: {
        type: "value",
        name: "Antigüedad activa",
        min: 0,
        max: Math.ceil(maxAge * 1.08),
        nameLocation: "middle",
        nameGap: 32,
        splitLine: { lineStyle: { color: "rgba(7,29,56,.08)" } },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.35)" } },
        axisLabel: { color: "rgba(7,29,56,.58)" }
      },
      yAxis: {
        type: "value",
        name: "Producción acumulada",
        min: 0,
        max: Math.ceil(maxY * 1.1),
        nameLocation: "middle",
        nameGap: 44,
        splitLine: { lineStyle: { color: "rgba(7,29,56,.08)" } },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.35)" } },
        axisLabel: { color: "rgba(7,29,56,.58)" }
      },
      graphic: [{
        type: "text",
        left: "center",
        top: "middle",
        silent: true,
        style: {
          text: String(bubbleYear),
          fill: "rgba(7,29,56,.055)",
          font: "800 150px Inter, system-ui, sans-serif"
        }
      }],
      series: [{
        type: "scatter",
        data: points.map(d => {
          const hasSelection = bubbleSelectedIds.size > 0;
          const isSelected = bubbleSelectedIds.has(d.id);
          const opacity = !hasSelection || isSelected ? 0.9 : 0.16;

          return {
            id: `${bubbleDimension}:${d.id}`,
            name: `${bubbleDimension}:${d.label}`,
            value: [d.active_age, d.cumulative],
            raw: { ...d, stable_id: `${bubbleDimension}:${d.id}` },
            selected: isSelected,
            label: {
              show: isSelected,
              formatter: formatBubbleEntityLabel(d.label),
              position: "top",
              color: "#071d38",
              fontWeight: 800,
              fontSize: 10,
              backgroundColor: "rgba(255,255,255,.72)",
              padding: [2, 4]
            },
            itemStyle: {
              color: getBubbleColor(d),
              opacity,
              borderColor: isSelected ? "#071d38" : "rgba(7,29,56,.24)",
              borderWidth: isSelected ? 2 : 1
            }
          };
        }),
        symbolSize(value, params) {
          const d = params.data.raw;
          return 8 + Math.sqrt(d.cumulative / maxCumulative) * 54;
        },
        emphasis: {
          focus: "self",
          itemStyle: {
            opacity: 1,
            borderColor: "#071d38",
            borderWidth: 2
          },
          label: {
            show: true,
            formatter(params) {
              return params.data.raw.label;
            },
            position: "top",
            color: "#071d38",
            fontWeight: 700,
            fontSize: 10
          }
        }
      }]
    }, true);
  }

  function buildBubblePoints(data, year) {
    const points = [];

    for (const entity of data.entities || []) {
      if (bubbleDimension === "level") {
        const normalizedLevel = entity.main_level === "MAESTRIA" ? "MAESTRÍA" : entity.main_level;
        if (!bubbleLevelFilter.has(normalizedLevel) && !bubbleLevelFilter.has(entity.main_level)) continue;
      } else if (!bubbleAreaFilter.has(entity.main_area)) {
        continue;
      }

      const series = entity.series || [];
      let selected = null;

      for (const item of series) {
        if (item.year <= year) selected = item;
        else break;
      }

      if (!selected) continue;

      points.push({
        ...entity,
        year: selected.year,
        year_count: selected.year_count || 0,
        cumulative: selected.cumulative || 0,
        active_age: selected.active_age || 0
      });
    }

    return points.sort((a, b) =>
      `${bubbleDimension}:${String(a.id)}`.localeCompare(`${bubbleDimension}:${String(b.id)}`)
    );
  }

  function applyBubbleSelectionStyles() {
    if (!bubbleChart) return;

    const option = bubbleChart.getOption();
    const currentData = option?.series?.[0]?.data || [];
    const hasSelection = bubbleSelectedIds.size > 0;

    const nextData = currentData.map(item => {
      const raw = item.raw || {};
      const isSelected = bubbleSelectedIds.has(raw.id);
      const opacity = !hasSelection || isSelected ? 0.9 : 0.16;

      return {
        ...item,
        selected: isSelected,
        label: {
          ...(item.label || {}),
          show: isSelected,
          formatter: formatBubbleEntityLabel(raw.label || item.name || ""),
          position: "top",
          color: "#071d38",
          fontWeight: 800,
          fontSize: 10,
          backgroundColor: "rgba(255,255,255,.72)",
          padding: [2, 4]
        },
        itemStyle: {
          ...(item.itemStyle || {}),
          opacity,
          borderColor: isSelected ? "#071d38" : "rgba(7,29,56,.24)",
          borderWidth: isSelected ? 2 : 1
        }
      };
    });

    bubbleChart.setOption({
      animation: false,
      series: [{ data: nextData }]
    }, false);

    const clearBtn = document.getElementById("bubbleClearSelectionBtn");
    if (clearBtn) {
      clearBtn.disabled = bubbleSelectedIds.size === 0;
      clearBtn.textContent = bubbleSelectedIds.size
        ? `Limpiar (${bubbleSelectedIds.size})`
        : "Limpiar selección";
    }
  }

  function toggleBubblePlayback() {
    if (bubblePlaying) {
      stopBubblePlayback();
      return;
    }

    const years = bubbleData?.years || [];
    if (!years.length) return;

    bubblePlaying = true;
    const btn = document.getElementById("bubblePlayBtn");
    if (btn) btn.textContent = "Pausar";

    bubbleTimer = setInterval(() => {
      const currentIndex = years.findIndex(y => y >= bubbleYear);
      const next = currentIndex >= 0 && currentIndex < years.length - 1
        ? years[currentIndex + 1]
        : years[0];

      bubbleYear = next;
      scheduleBubbleRender(true);
    }, 720);
  }

  function stopBubblePlayback() {
    bubblePlaying = false;
    if (bubbleTimer) clearInterval(bubbleTimer);
    bubbleTimer = null;

    const btn = document.getElementById("bubblePlayBtn");
    if (btn) btn.textContent = "Reproducir";
  }

  function renderRankingShell() {
    const stage = document.getElementById("workshopToolStage");
    const controls = document.getElementById("workshopToolControls");
    if (!stage || !controls) return;

    if (rankingChart) {
      try { rankingChart.dispose(); } catch (err) {}
      rankingChart = null;
    }

    stage.innerHTML = `
      <div class="wct-chart-frame wct-chart-ranking">
        <div class="wct-chart-head">
          <span>Concentración y jerarquía</span>
          <strong>Ranking</strong>
        </div>
        <div class="wct-echart" id="rankingChart"></div>
      </div>
    `;

    controls.innerHTML = `
      <div class="wct-control-summary">
        <span>Módulo activo</span>
        <strong>Ranking</strong>
      </div>

      <label class="wct-control">
        <span>Dimensión</span>
        <select id="rankingDimension">
          <option value="program"${rankingDimension === "program" ? " selected" : ""}>Programas</option>
          <option value="advisor"${rankingDimension === "advisor" ? " selected" : ""}>Asesores</option>
          <option value="plantel"${rankingDimension === "plantel" ? " selected" : ""}>Planteles</option>
          <option value="level"${rankingDimension === "level" ? " selected" : ""}>Niveles</option>
          <option value="area"${rankingDimension === "area" ? " selected" : ""}>Áreas</option>
          <option value="degree"${rankingDimension === "degree" ? " selected" : ""}>Grado</option>
        </select>
      </label>

      <label class="wct-control">
        <span>Vista</span>
        <select id="rankingView">
          <option value="bar"${rankingView === "bar" ? " selected" : ""}>Barras</option>
          <option value="lollipop"${rankingView === "lollipop" ? " selected" : ""}>Lollipop</option>
          <option value="pareto"${rankingView === "pareto" ? " selected" : ""}>Pareto</option>
        </select>
      </label>

      <label class="wct-control">
        <span>Límite <b id="rankingLimitLabel">${rankingLimit}</b></span>
        <input id="rankingLimit" type="range" min="5" max="50" step="5" value="${rankingLimit}" />
      </label>

      <div class="wct-control wct-ranking-years wct-ranking-period">
        <span>Periodo</span>
        <div class="wct-period-readout">
          <strong id="rankingYearMinLabel">${rankingYearMin}</strong>
          <strong id="rankingYearMaxLabel">${rankingYearMax}</strong>
        </div>
        <div class="wct-period-track" id="rankingPeriodTrack">
          <button id="rankingYearMinHandle" class="wct-period-handle" type="button" aria-label="Año inicial"></button>
          <button id="rankingYearMaxHandle" class="wct-period-handle" type="button" aria-label="Año final"></button>
        </div>
      </div>

      <fieldset class="wct-control wct-area-filter wct-ranking-filter">
        <legend>Área</legend>
        ${["AREA 1", "AREA 2", "AREA 3", "AREA 4"].map(area => `
          <label>
            <input type="checkbox" data-ranking-area="${area}" ${rankingAreaFilter.has(area) ? "checked" : ""} />
            <span>${area.replace("AREA", "Área")}</span>
          </label>
        `).join("")}
      </fieldset>

      <button
        class="wct-save"
        type="button"
        disabled
        data-save-tool="ranking"
        data-save-view="${rankingView}"
        title="Guardar estará disponible en Mi Espacio"
      >Guardar</button>
    `;

    requestAnimationFrame(() => {
      setupRankingPeriodDrag();
      updateRankingPeriodUI();
    });
  }

  function updateRankingPeriodUI() {
    const track = document.getElementById("rankingPeriodTrack");
    const minHandle = document.getElementById("rankingYearMinHandle");
    const maxHandle = document.getElementById("rankingYearMaxHandle");
    const minLabel = document.getElementById("rankingYearMinLabel");
    const maxLabel = document.getElementById("rankingYearMaxLabel");

    if (!track || !minHandle || !maxHandle) return;

    const span = RANKING_YEAR_MAX - RANKING_YEAR_MIN;
    const minPct = ((rankingYearMin - RANKING_YEAR_MIN) / span) * 100;
    const maxPct = ((rankingYearMax - RANKING_YEAR_MIN) / span) * 100;

    minHandle.style.left = `${minPct}%`;
    maxHandle.style.left = `${maxPct}%`;

    if (minLabel) minLabel.textContent = String(rankingYearMin);
    if (maxLabel) maxLabel.textContent = String(rankingYearMax);
  }

  function setupRankingPeriodDrag() {
    const track = document.getElementById("rankingPeriodTrack");
    const minHandle = document.getElementById("rankingYearMinHandle");
    const maxHandle = document.getElementById("rankingYearMaxHandle");
    if (!track || !minHandle || !maxHandle || track.dataset.bound === "1") return;

    track.dataset.bound = "1";

    const yearFromClientX = clientX => {
      const rect = track.getBoundingClientRect();
      const pct = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      return Math.round(RANKING_YEAR_MIN + pct * (RANKING_YEAR_MAX - RANKING_YEAR_MIN));
    };

    const bindHandle = kind => event => {
      event.preventDefault();

      const move = moveEvent => {
        const year = yearFromClientX(moveEvent.clientX);

        if (kind === "min") rankingYearMin = Math.min(year, rankingYearMax);
        else rankingYearMax = Math.max(year, rankingYearMin);

        updateRankingPeriodUI();
      };

      const end = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", end);
        loadRankingData();
      };

      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", end);
    };

    minHandle.addEventListener("pointerdown", bindHandle("min"));
    maxHandle.addEventListener("pointerdown", bindHandle("max"));

    track.addEventListener("pointerdown", event => {
      if (event.target === minHandle || event.target === maxHandle) return;

      const year = yearFromClientX(event.clientX);
      const dMin = Math.abs(year - rankingYearMin);
      const dMax = Math.abs(year - rankingYearMax);

      if (dMin <= dMax) rankingYearMin = Math.min(year, rankingYearMax);
      else rankingYearMax = Math.max(year, rankingYearMin);

      updateRankingPeriodUI();
      loadRankingData();
    });

    updateRankingPeriodUI();
  }

  async function loadRankingData() {
    const el = document.getElementById("rankingChart");
    if (el) {
      el.innerHTML = `<div class="wct-loading">Cargando ranking...</div>`;
    }

    const params = new URLSearchParams();
    params.set("dimension", rankingDimension);
    params.set("limit", String(rankingLimit));

    if (rankingYearMin) params.set("year_min", rankingYearMin);
    if (rankingYearMax) params.set("year_max", rankingYearMax);

    if (rankingAreaFilter.size && rankingAreaFilter.size < 4) {
      params.set("areas", [...rankingAreaFilter].join(","));
    }

    const normalizedLevels = [...rankingLevelFilter].filter(v => v !== "MAESTRIA");
    if (normalizedLevels.length && normalizedLevels.length < 4) {
      params.set("levels", normalizedLevels.join(","));
    }

    try {
      const response = await workshopDataFetch(`/api/workshop/tools/ranking?${params.toString()}`, `workshop/ranking_${encodeURIComponent(rankingDimension)}.json`);
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `HTTP ${response.status}`);
      }

      rankingData = await response.json();
      renderRankingChart();
    } catch (err) {
      console.error("[NODO Taller] Error cargando ranking", err);
      if (el) {
        el.innerHTML = `<div class="wct-loading is-error">No se pudo cargar Ranking: ${escapeHTML(err.message)}</div>`;
      }
    }
  }

  function renderRankingChart() {
    if (!rankingData) return;

    const el = document.getElementById("rankingChart");
    if (!el) return;

    const rows = rankingData.rows || [];
    if (!window.echarts) {
      el.innerHTML = `<div class="wct-loading is-error">ECharts no está disponible.</div>`;
      return;
    }

    if (el.querySelector(".wct-loading")) {
      el.innerHTML = "";
      if (rankingChart) {
        try { rankingChart.dispose(); } catch (err) {}
        rankingChart = null;
      }
    }

    if (!rankingChart) {
      rankingChart = window.echarts.init(el, null, { renderer: "canvas" });
      window.addEventListener("resize", () => rankingChart?.resize());
    }

    if (!rows.length) {
      rankingChart.setOption({
        graphic: [{
          type: "text",
          left: "center",
          top: "middle",
          style: {
            text: "Sin datos",
            fill: "rgba(7,29,56,.38)",
            font: "300 18px Inter, system-ui, sans-serif"
          }
        }],
        series: []
      }, true);
      return;
    }

    const labels = rows.map(row => formatRankingLabel(row.label));
    const values = rows.map(row => row.count);
    const maxValue = Math.max(...values);
    const colors = rows.map(row => getRankingColor(row));

    const baseOption = {
      animationDurationUpdate: 420,
      grid: { left: 130, right: rankingView === "pareto" ? 64 : 28, top: 36, bottom: 36, containLabel: true },
      tooltip: {
        trigger: "item",
        borderWidth: 1,
        borderColor: "rgba(7,29,56,.16)",
        formatter(params) {
          const row = rows[params.dataIndex];
          return `
            <div class="wct-tooltip">
              <strong>${escapeHTML(formatRankingLabel(row.label))}</strong>
              <div class="wct-tooltip-main">${formatNumber(row.count)} tesis</div>
              <div>Participación: ${(row.share * 100).toFixed(1)}%</div>
              <div>Acumulado: ${(row.cumulative_share * 100).toFixed(1)}%</div>
              <hr/>
              <span>Contexto dominante</span>
              <div>${escapeHTML(row.main_area || "SIN DATO")}: ${escapeHTML(formatRankingLabel(row.main_level || ""))}</div>
              <div>${escapeHTML(formatRankingLabel(row.main_plantel || ""))}</div>
            </div>
          `;
        }
      },
      xAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "rgba(7,29,56,.08)" } },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.32)" } },
        axisLabel: { color: "rgba(7,29,56,.58)" }
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: labels,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.26)" } },
        axisLabel: {
          color: "rgba(7,29,56,.72)",
          width: 120,
          overflow: "truncate"
        }
      }
    };

    if (rankingView === "lollipop") {
      rankingChart.setOption({
        ...baseOption,
        series: [
          {
            type: "bar",
            data: values,
            barWidth: 2,
            itemStyle: { color: "rgba(7,29,56,.22)" },
            silent: true
          },
          {
            type: "scatter",
            data: values,
            symbolSize: value => 8 + Math.sqrt(value / maxValue) * 22,
            itemStyle: {
              color(params) { return colors[params.dataIndex]; },
              borderColor: "rgba(7,29,56,.22)",
              borderWidth: 1
            }
          }
        ]
      }, true);
      return;
    }

    if (rankingView === "pareto") {
      rankingChart.setOption({
        ...baseOption,
        yAxis: [baseOption.yAxis],
        xAxis: [
          baseOption.xAxis,
          {
            type: "value",
            min: 0,
            max: 100,
            position: "top",
            axisLabel: { formatter: "{value}%", color: "rgba(7,29,56,.58)" },
            splitLine: { show: false }
          }
        ],
        series: [
          {
            type: "bar",
            data: values,
            barWidth: 12,
            itemStyle: {
              color(params) { return colors[params.dataIndex]; },
              borderRadius: [0, 2, 2, 0]
            }
          },
          {
            type: "line",
            xAxisIndex: 1,
            data: rows.map(row => Number((row.cumulative_share * 100).toFixed(2))),
            symbolSize: 6,
            lineStyle: { color: "#071d38", width: 2 },
            itemStyle: { color: "#071d38" }
          }
        ]
      }, true);
      return;
    }

    rankingChart.setOption({
      ...baseOption,
      series: [{
        type: "bar",
        data: values,
        barWidth: 13,
        itemStyle: {
          color(params) { return colors[params.dataIndex]; },
          borderRadius: [0, 2, 2, 0]
        },
        label: {
          show: true,
          position: "right",
          color: "rgba(7,29,56,.56)",
          formatter(params) {
            return formatNumber(params.value);
          }
        }
      }]
    }, true);
  }

  function getRankingColor(row) {
    if (rankingDimension === "level") {
      return LEVEL_COLORS[row.label] || LEVEL_COLORS[row.main_level] || LEVEL_COLORS[""];
    }

    return AREA_COLORS[row.main_area] || AREA_COLORS[""];
  }

  function formatRankingLabel(value) {
    return titleCaseName(value || "");
  }

  function renderPlaceholderTool(toolKey) {
    const tool = TOOLS[toolKey];
    const stage = document.getElementById("workshopToolStage");
    const controls = document.getElementById("workshopToolControls");
    if (!stage || !controls) return;

    stage.innerHTML = `
      <div class="wct-chart-frame">
        <div class="wct-chart-head">
          <span>${tool.kicker}</span>
          <strong>${tool.label}</strong>
        </div>
        <div class="wct-plot-area">
          ${renderPlaceholder(toolKey)}
        </div>
        <div class="wct-chart-note">
          <h2>${tool.title}</h2>
          <p>${tool.text}</p>
        </div>
      </div>
    `;

    controls.innerHTML = `
      <div class="wct-control-summary">
        <span>Módulo activo</span>
        <strong>${tool.label}</strong>
      </div>
      <div class="wct-control"><span>Estado</span><select><option>En preparación</option></select></div>
      <div class="wct-control"><span>Dataset</span><select><option>Curado</option></select></div>
      <div class="wct-control"><span>Salida</span><select><option>Visualización</option></select></div>
      <div class="wct-control"><span>Backend</span><select><option>Pendiente</option></select></div>
      <button class="wct-run" type="button">Próximamente</button>
    `;
  }

  function renderPlaceholder(toolKey) {
    if (toolKey === "heatmap") {
      return `<div class="wct-heat">${Array.from({length: 48}, (_, i) => `<b style="--o:${0.12 + (i % 8) * .09}"></b>`).join("")}</div>`;
    }

    if (toolKey === "series") {
      return `<svg viewBox="0 0 640 280" preserveAspectRatio="none"><path d="M20 220 C120 190 150 205 230 155 S360 145 450 92 S560 70 620 38"/><path class="fill" d="M20 220 C120 190 150 205 230 155 S360 145 450 92 S560 70 620 38 L620 260 L20 260 Z"/></svg>`;
    }

    return `<div class="wct-bars">${Array.from({length: 9}, (_, i) => `<b style="--w:${92 - i * 7}%"></b>`).join("")}</div>`;
  }

  function getBubbleColor(d) {
    if (bubbleDimension === "level") {
      return LEVEL_COLORS[d.main_level] || LEVEL_COLORS[""];
    }

    return AREA_COLORS[d.main_area] || AREA_COLORS[""];
  }

  function escapeHTML(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function titleCaseName(value) {
    return String(value || "")
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .map(part => {
        if (["de", "del", "la", "las", "los", "y"].includes(part)) return part;
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join(" ");
  }

  function formatBubbleEntityLabel(value) {
    return titleCaseName(value)
      .replace(/\s*,\s*/g, ", ")
      .trim();
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("es-MX").format(Number(value || 0));
  }

  function cleanupWorkshopCuratedStateWhenInactive() {
    if (document.body?.dataset?.tab === "taller") return;

    stopBubblePlayback?.();

    document.body.classList.remove(
      "workshop-curated-tools",
      "workshop-analysis-mode",
      "workshop-titles-mode",
      "workshop-has-results",
      "workshop-space-create",
      "workshop-space-graphs",
      "workshop-studio-started"
    );
  }

  function ensureInitialBubblesAdvisor() {
    if (!document.getElementById("workshopCuratedTools")) {
      mountWorkshopCuratedTools();
    }

    activeTool = "bubbles";
    bubbleDimension = "advisor";
    bubbleData = null;
    bubbleDomains = null;

    renderTool("bubbles");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      mountWorkshopCuratedTools();
      setTimeout(ensureInitialBubblesAdvisor, 80);
      setTimeout(ensureInitialBubblesAdvisor, 300);
    });
  } else {
    mountWorkshopCuratedTools();
    setTimeout(ensureInitialBubblesAdvisor, 80);
    setTimeout(ensureInitialBubblesAdvisor, 300);
  }

  const workshopTabObserver = new MutationObserver(() => {
    if (document.body?.dataset?.tab === "taller") {
      requestAnimationFrame(() => {
        requestAnimationFrame(ensureInitialBubblesAdvisor);
      });
      setTimeout(ensureInitialBubblesAdvisor, 180);
    } else {
      cleanupWorkshopCuratedStateWhenInactive();
    }
  });

  if (document.body) {
    workshopTabObserver.observe(document.body, {
      attributes: true,
      attributeFilter: ["data-tab"]
    });
  }

  window.mountWorkshopCuratedTools = mountWorkshopCuratedTools;
  window.ensureInitialBubblesAdvisor = ensureInitialBubblesAdvisor;
})();




/* WCT SHARED CHART GEOMETRY START */
function getWorkshopChartGrid(type) {
  const base = {
    top: 56,
    right: 38,
    bottom: 76,
    left: 76,
    containLabel: true,
  };

  if (type === "heatmap") {
    return {
      ...base,
      left: 142,
      bottom: 64,
    };
  }

  if (type === "series") {
    return {
      ...base,
      left: 76,
      bottom: 84,
    };
  }

  return base;
}
/* WCT SHARED CHART GEOMETRY END */

/* WCT HEATMAP UNIFIED START */
(() => {
  const HEATMAP_MODES = [
    ["temporal", "Temporal"],
    ["program_level", "Programa × Nivel"],
    ["area_level", "Área × Nivel"],
    ["program_area", "Programa × Área"],
  ];

  const HEATMAP_TEMPORAL_SCALES = [
    ["log", "Log"],
    ["absolute", "Absoluta"],
    ["year_share", "Participación anual"],
  ];

  const HEATMAP_MATRIX_SCALES = [
    ["log", "Log"],
    ["absolute", "Absoluta"],
    ["row_share", "Participación fila"],
  ];

  const HEATMAP_DIMENSIONS = [
    ["advisor", "Asesores"],
    ["program", "Programas"],
    ["area", "Áreas"],
    ["level", "Niveles"],
    ["plantel", "Planteles"],
    ["degree", "Grados"],
  ];

  let heatmapState = {
    mode: "temporal",
    dimension: "advisor",
    scale: "log",
    limit: 15,
    yearMin: 2000,
    yearMax: 2026,
  };

  let heatmapChart = null;
  let heatmapAbort = null;

  function heatmapTitleCase(value) {
    return String(value || "")
      .toLocaleLowerCase("es-MX")
      .split(/(\s+|\/|-)/)
      .map(part => {
        if (!part || /^\s+$/.test(part) || part === "/" || part === "-") {
          return part;
        }
        return part.charAt(0).toLocaleUpperCase("es-MX") + part.slice(1);
      })
      .join("");
  }

  function heatmapStage() {
    return document.getElementById("workshopToolStage");
  }

  function heatmapControls() {
    return document.getElementById("workshopToolControls");
  }

  function setHeatmapToolActive() {
    document.querySelectorAll("[data-workshop-tool]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.workshopTool === "heatmap");
    });
  }

  function activeScaleOptions() {
    return heatmapState.mode === "temporal"
      ? HEATMAP_TEMPORAL_SCALES
      : HEATMAP_MATRIX_SCALES;
  }

  function normalizeScaleForMode() {
    const valid = new Set(activeScaleOptions().map(([value]) => value));
    if (!valid.has(heatmapState.scale)) {
      heatmapState.scale = activeScaleOptions()[0][0];
    }
  }

  function renderHeatmapShell() {
    const stage = heatmapStage();
    const controls = heatmapControls();
    if (!stage || !controls) return;

    normalizeScaleForMode();
    setHeatmapToolActive();

    stage.innerHTML = `
      <section class="wct-heatmap-stage" aria-label="Heatmap">
        <div class="wct-heatmap-chart" id="heatmapChart">
          <div class="wct-loading">Cargando matriz...</div>
        </div>
      </section>
    `;

    controls.innerHTML = `
      <div class="wct-control-summary">
        <span>Módulo activo</span>
        <strong>Heatmap</strong>
      </div>

      <label class="wct-control wct-heatmap-matrix-control">
        <span>Matriz</span>
        <select id="heatmapMatrixSelect">
          ${HEATMAP_MODES.map(([value, label]) => `
            <option value="${value}" ${value === heatmapState.mode ? "selected" : ""}>${label}</option>
          `).join("")}
        </select>
      </label>

      <label class="wct-control" id="heatmapDimensionControl" style="${heatmapState.mode === "temporal" ? "" : "display:none;"}">
        <span>Entidad</span>
        <select id="heatmapDimensionSelect">
          ${HEATMAP_DIMENSIONS.map(([value, label]) => `
            <option value="${value}" ${value === heatmapState.dimension ? "selected" : ""}>${label}</option>
          `).join("")}
        </select>
      </label>

      <label class="wct-control">
        <span>Escala</span>
        <select id="heatmapScaleSelect">
          ${activeScaleOptions().map(([value, label]) => `
            <option value="${value}" ${value === heatmapState.scale ? "selected" : ""}>${label}</option>
          `).join("")}
        </select>
      </label>

      <label class="wct-control wct-heatmap-limit">
        <span>Límite <strong id="heatmapLimitLabel">${heatmapState.limit}</strong></span>
        <input id="heatmapLimitRange" type="range" min="5" max="50" step="5" value="${heatmapState.limit}">
      </label>

      <div class="wct-control wct-heatmap-period">
        <span>Periodo</span>
        <div>
          <input id="heatmapYearMin" type="number" min="1873" max="2026" value="${heatmapState.yearMin}">
          <input id="heatmapYearMax" type="number" min="1873" max="2026" value="${heatmapState.yearMax}">
        </div>
      </div>

      <button class="wct-save" type="button" disabled aria-disabled="true">Guardar</button>
    `;

    bindHeatmapControls();
    loadHeatmapData();
  }

  function bindHeatmapControls() {
    document.getElementById("heatmapMatrixSelect")?.addEventListener("change", event => {
      heatmapState.mode = event.target.value;
      normalizeScaleForMode();
      renderHeatmapShell();
    });

    document.getElementById("heatmapDimensionSelect")?.addEventListener("change", event => {
      heatmapState.dimension = event.target.value;
      loadHeatmapData();
    });

    document.getElementById("heatmapScaleSelect")?.addEventListener("change", event => {
      heatmapState.scale = event.target.value;
      loadHeatmapData();
    });

    document.getElementById("heatmapLimitRange")?.addEventListener("input", event => {
      heatmapState.limit = Number(event.target.value) || 15;
      const label = document.getElementById("heatmapLimitLabel");
      if (label) label.textContent = String(heatmapState.limit);
      loadHeatmapData();
    });

    const onPeriodChange = () => {
      const min = Number(document.getElementById("heatmapYearMin")?.value || 2000);
      const max = Number(document.getElementById("heatmapYearMax")?.value || 2026);
      heatmapState.yearMin = Math.min(min, max);
      heatmapState.yearMax = Math.max(min, max);
      document.getElementById("heatmapYearMin").value = String(heatmapState.yearMin);
      document.getElementById("heatmapYearMax").value = String(heatmapState.yearMax);
      loadHeatmapData();
    };

    document.getElementById("heatmapYearMin")?.addEventListener("change", onPeriodChange);
    document.getElementById("heatmapYearMax")?.addEventListener("change", onPeriodChange);
  }

  async function loadHeatmapData() {
    const chartEl = document.getElementById("heatmapChart");
    if (!chartEl) return;

    if (heatmapAbort) heatmapAbort.abort();
    heatmapAbort = new AbortController();

    chartEl.innerHTML = `<div class="wct-loading">Cargando heatmap...</div>`;

    try {
      if (heatmapState.mode === "temporal") {
        const params = new URLSearchParams({
          dimension: heatmapState.dimension,
          scale: heatmapState.scale,
          limit: String(heatmapState.limit),
          year_min: String(heatmapState.yearMin),
          year_max: String(heatmapState.yearMax),
        });

        const response = await fetch(`/api/workshop/tools/heatmap?${params}`, {
          signal: heatmapAbort.signal,
        });

        if (!response.ok) {
          const text = await response.text();
          throw new Error(`HTTP ${response.status}: ${text.slice(0, 180)}`);
        }

        renderHeatmapTemporal(await response.json());
        return;
      }

      const params = new URLSearchParams({
        matrix: heatmapState.mode,
        scale: heatmapState.scale,
        limit: String(heatmapState.limit),
        year_min: String(heatmapState.yearMin),
        year_max: String(heatmapState.yearMax),
      });

      const response = await fetch(`/api/workshop/tools/heatmap-matrix?${params}`, {
        signal: heatmapAbort.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text.slice(0, 180)}`);
      }

      renderHeatmapMatrix(await response.json());
    } catch (err) {
      if (err.name === "AbortError") return;

      chartEl.innerHTML = `
        <div class="wct-empty-state">
          <strong>No se pudo cargar el heatmap</strong>
          <span>${String(err.message || err)}</span>
        </div>
      `;
    }
  }

  function ensureChartEl() {
    const chartEl = document.getElementById("heatmapChart");
    if (!chartEl) return null;

    if (!window.echarts) {
      chartEl.innerHTML = `<div class="wct-loading">Esperando motor gráfico...</div>`;
      return null;
    }

    chartEl.innerHTML = "";

    if (heatmapChart) {
      heatmapChart.dispose();
      heatmapChart = null;
    }

    heatmapChart = echarts.init(chartEl, null, { renderer: "canvas" });
    return chartEl;
  }

  function renderHeatmapTemporal(payload) {
    const chartEl = ensureChartEl();
    if (!chartEl) {
      setTimeout(() => renderHeatmapTemporal(payload), 120);
      return;
    }

    const years = payload.years || [];
    const labels = payload.labels || [];
    const cells = payload.cells || [];

    if (!years.length || !labels.length) {
      chartEl.innerHTML = `
        <div class="wct-empty-state">
          <strong>Sin datos para el periodo seleccionado</strong>
          <span>Ajusta entidad, escala o años.</span>
        </div>
      `;
      return;
    }

    const data = cells.map(cell => [
      cell.year_index,
      cell.label_index,
      Number(cell.value || 0),
      Number(cell.raw || 0),
      cell.x,
      cell.y,
    ]);

    const values = data.map(d => Number(d[2])).filter(Number.isFinite);
    const maxValue = Math.max(1, ...values);

    heatmapChart.setOption({
      animation: false,
      grid: getWorkshopChartGrid("heatmap"),
      tooltip: {
        borderWidth: 1,
        borderColor: "rgba(7,29,56,.16)",
        backgroundColor: "rgba(255,255,255,.96)",
        textStyle: {
          color: "#071d38",
          fontFamily: "Inter, Arial, sans-serif",
          fontSize: 12,
        },
        formatter(params) {
          const year = years[params.value[0]];
          const label = labels[params.value[1]];
          const raw = params.value[3];
          return `
            <strong>${heatmapTitleCase(label)}</strong><br>
            Año: ${year}<br>
            Tesis: ${Number(raw).toLocaleString("es-MX")}
          `;
        },
      },
      xAxis: {
        type: "category",
        data: years,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.22)" } },
        axisLabel: {
          color: "rgba(7,29,56,.62)",
          fontSize: 10,
          interval: Math.max(0, Math.floor(years.length / 12)),
        },
      },
      yAxis: {
        type: "category",
        data: labels.map(heatmapTitleCase),
        inverse: true,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.22)" } },
        axisLabel: {
          color: "rgba(7,29,56,.72)",
          fontSize: 10,
          width: 108,
          overflow: "truncate",
          hideOverlap: true,
        },
      },
      visualMap: {
        min: 0,
        max: maxValue,
        dimension: 2,
        show: false,
        inRange: {
          color: ["#f7f9fb", "#e3edf0", "#a8cfd2", "#5f9ca5", "#071d38"],
        },
      },
      series: [{
        type: "heatmap",
        data,
        encode: {
          x: 0,
          y: 1,
          value: 2,
        },
        progressive: 0,
        itemStyle: {
          borderWidth: 1,
          borderColor: "rgba(255,255,255,.72)",
        },
        emphasis: {
          itemStyle: {
            borderColor: "#071d38",
            borderWidth: 1.5,
          },
        },
      }],
    }, true);

    requestAnimationFrame(() => {
      heatmapChart?.resize();
      setTimeout(() => heatmapChart?.resize(), 80);
    });
  }

  function renderHeatmapMatrix(payload) {
    const chartEl = ensureChartEl();
    if (!chartEl) {
      setTimeout(() => renderHeatmapMatrix(payload), 120);
      return;
    }

    const rows = payload.rows || [];
    const columns = payload.columns || [];
    const cells = payload.cells || [];

    if (!rows.length || !columns.length) {
      chartEl.innerHTML = `
        <div class="wct-empty-state">
          <strong>Sin datos para esta matriz</strong>
          <span>Ajusta periodo o límite.</span>
        </div>
      `;
      return;
    }

    const values = cells.map(c => Number(c.value || 0)).filter(Number.isFinite);
    const maxValue = Math.max(1, ...values);

    heatmapChart.setOption({
      animation: false,
      grid: getWorkshopChartGrid("heatmap"),
      tooltip: {
        borderWidth: 1,
        borderColor: "rgba(7,29,56,.16)",
        backgroundColor: "rgba(255,255,255,.96)",
        textStyle: {
          color: "#071d38",
          fontFamily: "Inter, Arial, sans-serif",
          fontSize: 12,
        },
        formatter(params) {
          const col = columns[params.value[0]];
          const row = rows[params.value[1]];
          const raw = params.value[3];
          return `
            <strong>${heatmapTitleCase(row)}</strong><br>
            ${heatmapTitleCase(col)}<br>
            Tesis: ${Number(raw).toLocaleString("es-MX")}
          `;
        },
      },
      xAxis: {
        type: "category",
        data: columns.map(heatmapTitleCase),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.22)" } },
        axisLabel: {
          color: "rgba(7,29,56,.68)",
          fontSize: 10,
          interval: 0,
          rotate: columns.length > 6 ? 28 : 0,
        },
      },
      yAxis: {
        type: "category",
        data: rows.map(heatmapTitleCase),
        inverse: true,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.22)" } },
        axisLabel: {
          color: "rgba(7,29,56,.72)",
          fontSize: 10,
          width: 128,
          overflow: "truncate",
        },
      },
      visualMap: {
        min: 0,
        max: maxValue,
        dimension: 2,
        show: false,
        inRange: {
          color: ["#f7f9fb", "#e3edf0", "#a8cfd2", "#5f9ca5", "#071d38"],
        },
      },
      series: [{
        type: "heatmap",
        data: cells.map(cell => [
          cell.column_index,
          cell.row_index,
          Number(cell.value || 0),
          Number(cell.raw || 0),
          cell.x,
          cell.y,
        ]),
        encode: {
          x: 0,
          y: 1,
          value: 2,
        },
        itemStyle: {
          borderWidth: 1,
          borderColor: "rgba(255,255,255,.76)",
        },
        emphasis: {
          itemStyle: {
            borderColor: "#071d38",
            borderWidth: 1.5,
          },
        },
      }],
    }, true);

    requestAnimationFrame(() => {
      heatmapChart?.resize();
      setTimeout(() => heatmapChart?.resize(), 80);
    });
  }

  document.addEventListener("click", event => {
    const btn = event.target.closest?.('[data-workshop-tool="heatmap"]');
    if (!btn) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    renderHeatmapShell();
  }, true);

  window.mountWorkshopHeatmap = renderHeatmapShell;
  window.renderWorkshopHeatmap = renderHeatmapShell;
})();
/* WCT HEATMAP UNIFIED END */


/* WCT SERIES FRONTEND START */
(() => {
  const SERIES_DIMENSIONS = [
    ["level", "Niveles"],
    ["area", "Áreas"],
    ["program", "Programas"],
    ["plantel", "Planteles"],
    ["advisor", "Asesores"],
  ];

  const SERIES_METRICS = [
    ["count", "Producción"],
    ["share_of_year", "Participación"],
    ["index_base_100", "Índice 100"],
  ];

  const SERIES_VIEWS = [
    ["line", "Línea"],
    ["area", "Área"],
    ["bar", "Barras"],
  ];

  const SERIES_COLORS = ["#071d38", "#d86b65", "#5fa5ad", "#d9ad68", "#758476", "#7b8794", "#b58b9f", "#4f6f8f"];

  let seriesState = {
    dimension: "level",
    metric: "count",
    view: "line",
    limit: 8,
    yearMin: 2000,
    yearMax: 2026,
  };

  let seriesChart = null;
  let seriesAbort = null;

  function seriesTitleCase(value) {
    return String(value || "")
      .toLocaleLowerCase("es-MX")
      .split(/(\s+|\/|-)/)
      .map(part => {
        if (!part || /^\s+$/.test(part) || part === "/" || part === "-") return part;
        return part.charAt(0).toLocaleUpperCase("es-MX") + part.slice(1);
      })
      .join("");
  }

  function renderSeriesShell() {
    const stage = document.getElementById("workshopToolStage");
    const controls = document.getElementById("workshopToolControls");
    if (!stage || !controls) return;

    document.querySelectorAll("[data-workshop-tool]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.workshopTool === "series");
    });

    stage.innerHTML = `
      <section class="wct-series-stage" aria-label="Series">
        <div class="wct-series-chart" id="seriesChart">
          <div class="wct-loading">Cargando series...</div>
        </div>
      </section>
    `;

    controls.innerHTML = `
      <div class="wct-control-summary">
        <span>Módulo activo</span>
        <strong>Series</strong>
      </div>

      <label class="wct-control">
        <span>Serie</span>
        <select id="seriesDimensionSelect">
          ${SERIES_DIMENSIONS.map(([value, label]) => `
            <option value="${value}" ${value === seriesState.dimension ? "selected" : ""}>${label}</option>
          `).join("")}
        </select>
      </label>

      <label class="wct-control">
        <span>Lectura</span>
        <select id="seriesMetricSelect">
          ${SERIES_METRICS.map(([value, label]) => `
            <option value="${value}" ${value === seriesState.metric ? "selected" : ""}>${label}</option>
          `).join("")}
        </select>
      </label>

      <label class="wct-control">
        <span>Vista</span>
        <select id="seriesViewSelect">
          ${SERIES_VIEWS.map(([value, label]) => `
            <option value="${value}" ${value === seriesState.view ? "selected" : ""}>${label}</option>
          `).join("")}
        </select>
      </label>

      <label class="wct-control wct-series-limit">
        <span>Límite <strong id="seriesLimitLabel">${seriesState.limit}</strong></span>
        <input id="seriesLimitRange" type="range" min="4" max="20" step="1" value="${seriesState.limit}">
      </label>

      <div class="wct-control wct-series-period">
        <span>Periodo</span>
        <div>
          <input id="seriesYearMin" type="number" min="1873" max="2026" value="${seriesState.yearMin}">
          <input id="seriesYearMax" type="number" min="1873" max="2026" value="${seriesState.yearMax}">
        </div>
      </div>

      <button class="wct-save" type="button" disabled aria-disabled="true">Guardar</button>
    `;

    bindSeriesControls();
    loadSeriesData();
  }

  function bindSeriesControls() {
    document.getElementById("seriesDimensionSelect")?.addEventListener("change", event => {
      seriesState.dimension = event.target.value;
      if (seriesState.dimension === "area" || seriesState.dimension === "level") {
        seriesState.limit = seriesState.dimension === "area" ? 4 : 4;
      }
      renderSeriesShell();
    });

    document.getElementById("seriesMetricSelect")?.addEventListener("change", event => {
      seriesState.metric = event.target.value;
      loadSeriesData();
    });

    document.getElementById("seriesViewSelect")?.addEventListener("change", event => {
      seriesState.view = event.target.value;
      loadSeriesData();
    });

    document.getElementById("seriesLimitRange")?.addEventListener("input", event => {
      seriesState.limit = Number(event.target.value) || 8;
      const label = document.getElementById("seriesLimitLabel");
      if (label) label.textContent = String(seriesState.limit);
      loadSeriesData();
    });

    const onPeriodChange = () => {
      const min = Number(document.getElementById("seriesYearMin")?.value || 2000);
      const max = Number(document.getElementById("seriesYearMax")?.value || 2026);
      seriesState.yearMin = Math.min(min, max);
      seriesState.yearMax = Math.max(min, max);
      loadSeriesData();
    };

    document.getElementById("seriesYearMin")?.addEventListener("change", onPeriodChange);
    document.getElementById("seriesYearMax")?.addEventListener("change", onPeriodChange);
  }

  async function loadSeriesData() {
    const chartEl = document.getElementById("seriesChart");
    if (!chartEl) return;

    if (seriesAbort) seriesAbort.abort();
    seriesAbort = new AbortController();

    chartEl.innerHTML = `<div class="wct-loading">Cargando series...</div>`;

    const params = new URLSearchParams({
      dimension: seriesState.dimension,
      limit: String(seriesState.limit),
      year_min: String(seriesState.yearMin),
      year_max: String(seriesState.yearMax),
    });

    try {
      const response = await fetch(`/api/workshop/tools/series?${params}`, {
        signal: seriesAbort.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text.slice(0, 180)}`);
      }

      renderSeriesChart(await response.json());
    } catch (err) {
      if (err.name === "AbortError") return;
      chartEl.innerHTML = `
        <div class="wct-empty-state">
          <strong>No se pudieron cargar las series</strong>
          <span>${String(err.message || err)}</span>
        </div>
      `;
    }
  }

  function renderSeriesChart(payload) {
    const chartEl = document.getElementById("seriesChart");
    if (!chartEl) return;

    if (!window.echarts) {
      chartEl.innerHTML = `<div class="wct-loading">Esperando motor gráfico...</div>`;
      setTimeout(() => renderSeriesChart(payload), 120);
      return;
    }

    const years = payload.years || [];
    const labels = payload.labels || [];
    const rows = payload.rows || [];

    if (!years.length || !labels.length) {
      chartEl.innerHTML = `
        <div class="wct-empty-state">
          <strong>Sin datos para el periodo seleccionado</strong>
          <span>Ajusta dimensión o años.</span>
        </div>
      `;
      return;
    }

    const byLabelYear = new Map();
    rows.forEach(row => {
      byLabelYear.set(`${row.label}::${row.year}`, row);
    });

    chartEl.innerHTML = "";

    if (seriesChart) {
      seriesChart.dispose();
      seriesChart = null;
    }

    seriesChart = echarts.init(chartEl, null, { renderer: "canvas" });

    const metric = seriesState.metric;
    const isShare = metric === "share_of_year";
    const isIndex = metric === "index_base_100";

    const series = labels.map((label, index) => ({
      name: seriesTitleCase(label),
      type: seriesState.view === "bar" ? "bar" : "line",
      stack: seriesState.view === "area" ? "series-total" : undefined,
      smooth: seriesState.view !== "bar",
      symbol: "none",
      areaStyle: seriesState.view === "area" ? { opacity: 0.18 } : undefined,
      lineStyle: { width: index < 4 ? 2 : 1.4 },
      itemStyle: { color: SERIES_COLORS[index % SERIES_COLORS.length] },
      data: years.map(year => {
        const row = byLabelYear.get(`${label}::${year}`);
        const value = row ? row[metric] : 0;
        return Number(value || 0);
      }),
    }));

    seriesChart.setOption({
      animation: false,
      color: SERIES_COLORS,
      grid: getWorkshopChartGrid("series"),
      tooltip: {
        trigger: "axis",
        borderWidth: 1,
        borderColor: "rgba(7,29,56,.16)",
        backgroundColor: "rgba(255,255,255,.96)",
        textStyle: { color: "#071d38", fontFamily: "Inter, Arial, sans-serif", fontSize: 12 },
        valueFormatter(value) {
          if (isShare) return `${(Number(value) * 100).toFixed(1)}%`;
          if (isIndex) return Number(value).toFixed(1);
          return Number(value).toLocaleString("es-MX");
        },
      },
      legend: {
        type: "scroll",
        bottom: 14,
        left: 24,
        right: 24,
        textStyle: { color: "rgba(7,29,56,.72)", fontSize: 10 },
      },
      xAxis: {
        type: "category",
        data: years,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(7,29,56,.22)" } },
        axisLabel: { color: "rgba(7,29,56,.62)", fontSize: 10 },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(7,29,56,.08)" } },
        axisLabel: {
          color: "rgba(7,29,56,.62)",
          formatter(value) {
            if (isShare) return `${Math.round(value * 100)}%`;
            if (isIndex) return `${Math.round(value)}`;
            return Number(value).toLocaleString("es-MX");
          },
        },
      },
      series,
    }, true);

    requestAnimationFrame(() => {
      seriesChart?.resize();
      setTimeout(() => seriesChart?.resize(), 80);
    });
  }

  document.addEventListener("click", event => {
    const btn = event.target.closest?.('[data-workshop-tool="series"]');
    if (!btn) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    renderSeriesShell();
  }, true);

  window.mountWorkshopSeries = renderSeriesShell;
})();
/* WCT SERIES FRONTEND END */

