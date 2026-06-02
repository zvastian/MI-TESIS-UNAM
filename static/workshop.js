
/* TALLER CURADO: módulos visuales + burbujas reales */
(() => {
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
    },
    comparison: {
      label: "Comparación",
      kicker: "Contraste",
      title: "Categorías frente a frente",
      text: "Módulo preparado para comparar dimensiones del acervo."
    },
    series: {
      label: "Series",
      kicker: "Evolución",
      title: "Tendencias anuales del acervo",
      text: "Módulo preparado para observar crecimiento, caída o aparición de temas."
    }
  };

  const AREA_COLORS = {
    "AREA 1": "#5fa5ad",
    "AREA 2": "#d86b65",
    "AREA 3": "#d9ad68",
    "AREA 4": "#7b8794",
    "": "#9aa4ad"
  };

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
  let bubbleRenderQueued = false;
  let bubbleRenderAnimated = true;
  let bubbleDomains = null;

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

    renderTool(activeTool);
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
    }
  }

  function handleWorkshopInput(event) {
    if (event.target.id === "bubbleYearSlider") {
      bubbleYear = Number(event.target.value);
      scheduleBubbleRender(false);
    }
  }

  function handleWorkshopChange(event) {
    if (event.target.id === "bubbleYearSlider") {
      bubbleYear = Number(event.target.value);
      scheduleBubbleRender(true);
      return;
    }

    if (event.target.id === "bubbleDimensionSelect") {
      bubbleDimension = event.target.value;
      bubbleData = null;
      bubbleDomains = null;
      stopBubblePlayback();
      loadBubbleData();
    }
  }

  function renderTool(toolKey) {
    activeTool = TOOLS[toolKey] ? toolKey : "bubbles";

    document.querySelectorAll("[data-workshop-tool]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.workshopTool === activeTool);
    });

    if (activeTool === "bubbles") {
      renderBubbleShell();
      loadBubbleData();
      return;
    }

    renderPlaceholderTool(activeTool);
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
        <div class="wct-chart-note">
          <h2>Trayectorias acumuladas del acervo</h2>
          <p>
            X = antigüedad activa. Y = producción acumulada. Tamaño = producción acumulada.
            Color = área principal. El año se controla abajo.
          </p>
        </div>
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

      <label class="wct-control wct-year-control">
        <span>Año</span>
        <input id="bubbleYearSlider" type="range" min="1954" max="2026" value="${bubbleYear || 2026}" />
      </label>

      <div class="wct-year-readout">
        <span>Corte</span>
        <strong id="bubbleYearLabel">${bubbleYear || 2026}</strong>
      </div>

      <button class="wct-run" id="bubblePlayBtn" type="button">Reproducir</button>
    `;
  }

  async function loadBubbleData() {
    const stage = document.getElementById("bubbleChart");
    if (stage) {
      stage.innerHTML = `<div class="wct-loading">Cargando dataset de ${DIMENSION_LABELS[bubbleDimension].toLowerCase()}...</div>`;
    }

    try {
      const response = await fetch(`/api/workshop/tools/bubbles?dimension=${encodeURIComponent(bubbleDimension)}&limit=50`);
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

    const slider = document.getElementById("bubbleYearSlider");
    if (slider && Number(slider.value) !== Number(bubbleYear)) {
      slider.value = String(bubbleYear);
    }

    const points = buildBubblePoints(bubbleData, bubbleYear);
    const maxCumulative = bubbleDomains?.maxCumulative || Math.max(1, ...points.map(d => d.cumulative));
    const maxAge = bubbleDomains?.maxAge || Math.max(10, ...points.map(d => d.active_age));
    const maxY = bubbleDomains?.maxY || Math.max(10, ...points.map(d => d.cumulative));

    if (!window.echarts) {
      el.innerHTML = `<div class="wct-loading is-error">ECharts no está disponible.</div>`;
      return;
    }

    if (!bubbleChart) {
      bubbleChart = window.echarts.init(el, null, { renderer: "canvas" });
      window.addEventListener("resize", () => bubbleChart?.resize());
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
          return `
            <strong>${escapeHTML(d.label)}</strong><br/>
            Año: ${bubbleYear}<br/>
            Producción acumulada: ${formatNumber(d.cumulative)}<br/>
            Tesis del año: ${formatNumber(d.year_count)}<br/>
            Antigüedad activa: ${formatNumber(d.active_age)} años<br/>
            Área: ${escapeHTML(d.main_area || "SIN DATO")}<br/>
            Programa: ${escapeHTML(d.main_program || "SIN DATO")}<br/>
            Plantel: ${escapeHTML(d.main_plantel || "SIN DATO")}
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
        data: points.map(d => ({
          value: [d.active_age, d.cumulative],
          raw: d,
          itemStyle: {
            color: AREA_COLORS[d.main_area] || AREA_COLORS[""],
            borderColor: "rgba(7,29,56,.24)",
            borderWidth: 1
          }
        })),
        symbolSize(value, params) {
          const d = params.data.raw;
          return 8 + Math.sqrt(d.cumulative / maxCumulative) * 54;
        },
        emphasis: {
          focus: "self",
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

    return points.sort((a, b) => b.cumulative - a.cumulative);
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

  function escapeHTML(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("es-MX").format(Number(value || 0));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountWorkshopCuratedTools);
  } else {
    mountWorkshopCuratedTools();
  }

  window.mountWorkshopCuratedTools = mountWorkshopCuratedTools;
})();
