const API = new URLSearchParams(window.location.search).get("api")
  || window.NODO_API_BASE
  || (window.location.protocol === "file:" ? "" : window.location.origin);

let state = {
  projectId: null,
  data: null,
  keywords: ["México", "China", "banca", "sistema financiero", "desarrollo económico"],
  objectives: [
    "Analizar las diferencias entre ambos sistemas bancarios",
    "Reconocer diferencias en los procesos históricos",
    "Sugerir mejoras para el sistema bancario mexicano"
  ],
  debugVisible: false
};

const bloomVerbs = {
  Recordar: ["identificar", "reconocer", "describir", "enumerar", "señalar", "definir"],
  Comprender: ["explicar", "interpretar", "resumir", "distinguir", "caracterizar"],
  Aplicar: ["aplicar", "utilizar", "emplear", "calcular", "implementar"],
  Analizar: ["analizar", "comparar", "diferenciar", "examinar", "relacionar", "contrastar"],
  Evaluar: ["evaluar", "valorar", "juzgar", "criticar", "estimar", "determinar"],
  Crear: ["proponer", "diseñar", "formular", "construir", "desarrollar", "plantear"]
};

const bloomDescriptions = {
  Recordar: "Recuperar información básica.",
  Comprender: "Explicar sentido y relaciones.",
  Aplicar: "Usar herramientas o conceptos.",
  Analizar: "Descomponer estructuras y tensiones.",
  Evaluar: "Emitir juicios con criterios.",
  Crear: "Proponer una ruta o producto nuevo."
};

const loadingSteps = [
  ["Analizando tu idea", "Interpretando núcleo temático."],
  ["Ubicando tesis similares", "Buscando afinidades semánticas."],
  ["Reordenando antecedentes", "Priorizando tesis útiles para tu proyecto."],
  ["Analizando objetivos", "Leyendo progresión cognitiva."],
  ["Formulando preguntas", "Construyendo rutas de investigación."],
  ["Buscando asesores", "Ordenando afinidades temáticas e históricas."],
  ["Preparando salida", "Consolidando el análisis completo."]
];

document.addEventListener("DOMContentLoaded", () => {
  maybeLoadLabFixture();
  if (!$("labForm")) return;

  bindLabEvents();
  renderChips();
  renderBloomLocal();
  renderVerbPopup();
});

function $(id) {
  return document.getElementById(id);
}


async function maybeLoadLabFixture() {
  const params = new URLSearchParams(window.location.search);

  if (params.get("labFixture") !== "1") return;

  try {
    const routes = [
      "/static/dev/lab_context_fixture.json",
      "static/dev/lab_context_fixture.json",
      "./dev/lab_context_fixture.json"
    ];

    let data = null;
    let lastError = null;

    for (const route of routes) {
      try {
        const response = await fetch(route, { cache: "no-store" });
        if (!response.ok) throw new Error(`${route}: ${response.status}`);
        data = await response.json();
        break;
      } catch (err) {
        lastError = err;
      }
    }

    if (!data) {
      throw lastError || new Error("No se pudo cargar lab_context_fixture.json");
    }

    state.data = normalizeResponse(data);
    state.projectId = state.data.project_id || "DEV_FIXTURE";

    const labTab = document.querySelector('[data-tab-target="laboratorio"]');
    if (labTab) labTab.click();

    setLoading(false);
    renderAll();

    console.info("Lab fixture cargado sin llamar IA:", state.data);
  } catch (err) {
    console.error(err);
    renderError(err);
  }
}


function bindLabEvents() {
  $("labForm")?.addEventListener("submit", handleRunLab);
  $("addKeywordBtn")?.addEventListener("click", addKeyword);
  $("newKeyword")?.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      addKeyword();
    }
  });

  $("addObjectiveBtn")?.addEventListener("click", addObjective);
  $("newObjective")?.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      addObjective();
    }
  });

  $("verbBulb")?.addEventListener("click", () => {
    $("verbPopup")?.classList.toggle("open");
  });

  $("closeVerbPopup")?.addEventListener("click", () => {
    $("verbPopup")?.classList.remove("open");
  });

  $("debugToggle")?.addEventListener("click", () => {
    state.debugVisible = !state.debugVisible;
    renderDebug();
  });
}

function addKeyword() {
  const input = $("newKeyword");
  const value = input.value.trim();

  if (!value) return;
  if (!state.keywords.includes(value)) state.keywords.push(value);

  input.value = "";
  renderChips();
}

function addObjective() {
  const input = $("newObjective");
  const value = input.value.trim();

  if (!value) return;
  if (!state.objectives.includes(value)) state.objectives.push(value);

  input.value = "";
  renderChips();
  renderBloomLocal();
}

function removeKeyword(index) {
  state.keywords.splice(index, 1);
  renderChips();
}

function removeObjective(index) {
  state.objectives.splice(index, 1);
  renderChips();
  renderBloomLocal();
}

window.removeKeyword = removeKeyword;
window.removeObjective = removeObjective;
window.insertVerb = insertVerb;

function renderChips() {
  $("keywordsContainer").innerHTML = state.keywords.map((keyword, index) => `
    <span class="chip">${escapeHtml(keyword)} <span class="remove" onclick="removeKeyword(${index})">×</span></span>
  `).join("");

  $("objectivesContainer").innerHTML = state.objectives.map((objective, index) => {
    const level = detectBloomLevel(objective);
    return `
      <span class="chip">
        ${escapeHtml(objective)}
        ${level ? `<small>${level}</small>` : ""}
        <span class="remove" onclick="removeObjective(${index})">×</span>
      </span>
    `;
  }).join("");
}

function detectBloomLevel(text) {
  const normalized = normalize(text);

  for (const [level, verbs] of Object.entries(bloomVerbs)) {
    for (const verb of verbs) {
      const re = new RegExp(`\\b${normalize(verb)}\\w*\\b`, "i");
      if (re.test(normalized)) return level;
    }
  }

  return null;
}

function renderBloomLocal() {
  const counts = {};
  Object.keys(bloomVerbs).forEach(level => counts[level] = 0);

  for (const objective of state.objectives) {
    const level = detectBloomLevel(objective);
    if (level) counts[level] += 1;
  }

  $("bloomLocal").innerHTML = Object.keys(bloomVerbs).map(level => `
    <div class="bloom-row">
      <div>
        ${level}
        <small>${bloomDescriptions[level]}</small>
      </div>
      <div class="bloom-count">${counts[level]}</div>
    </div>
  `).join("");
}

function renderVerbPopup() {
  $("verbSuggestionSections").innerHTML = Object.entries(bloomVerbs).map(([level, verbs]) => `
    <div class="verb-section">
      <h4>${level}</h4>
      <div class="verb-chips">
        ${verbs.map(verb => `<button class="verb-chip" type="button" onclick="insertVerb('${verb}')">${verb}</button>`).join("")}
      </div>
    </div>
  `).join("");
}

function insertVerb(verb) {
  const input = $("newObjective");
  const current = input.value.trim();

  input.value = current ? `${capitalize(verb)} ${current}` : `${capitalize(verb)} `;
  input.focus();
  $("verbPopup").classList.remove("open");
}

function buildPayload() {
  const applies = $("periodApplies").checked;
  const start = $("startYear").value ? Number($("startYear").value) : null;
  const end = $("endYear").value ? Number($("endYear").value) : null;

  return {
    title: $("title").value.trim(),
    keywords: state.keywords,
    objectives: state.objectives,
    program: $("program").value.trim(),
    degree: $("degree").value.trim(),
    plantel: $("plantel").value.trim(),
    study_period: {
      applies,
      start_year: applies ? start : null,
      end_year: applies ? end : null,
      label: applies && start && end ? `${start}-${end}` : null
    }
  };
}

async function handleRunLab(event) {
  event.preventDefault();

  const payload = buildPayload();

  if (!payload.title || payload.objectives.length === 0) {
    renderError(new Error("Agrega al menos título y un objetivo."));
    return;
  }

  setLoading(true);

  try {
    animateLoading();
    const response = await postJSON("/api/lab/run-full", payload);

    state.data = normalizeResponse(response);
    state.projectId = state.data.project_id;

    setLoading(false);
    renderAll();
  } catch (err) {
    setLoading(false);
    renderError(err);
  }
}

function animateLoading() {
  let index = 0;

  const timer = setInterval(() => {
    const loadingState = $("loadingState");

    if (!loadingState || loadingState.classList.contains("hidden")) {
      clearInterval(timer);
      return;
    }

    const step = loadingSteps[index % loadingSteps.length];
    if ($("loadingTitle")) $("loadingTitle").textContent = step[0];
    if ($("loadingText")) $("loadingText").textContent = step[1];
    index += 1;
  }, 2200);
}

async function postJSON(url, payload) {
  const response = await fetch(API + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const json = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = json.detail || json;
    throw new Error(detail.message || detail.error || detail || "Error en la API");
  }

  return json;
}

function normalizeResponse(response) {
  if (response && response.data) return response.data;
  return response;
}

function setLoading(isLoading) {
  if ($("runLabBtn")) $("runLabBtn").disabled = isLoading;
  $("emptyState")?.classList.toggle("hidden", isLoading);
  $("loadingState")?.classList.toggle("hidden", !isLoading);
  $("modules")?.classList.add("hidden");
}

function renderAll() {
  const modules = $("modules");

  $("emptyState")?.classList.add("hidden");
  $("loadingState")?.classList.add("hidden");
  modules?.classList.remove("hidden");

  renderTimeline();
  renderInitialNote();
  renderSemantic();
  renderTheses();
  renderBloom();
  renderQuestions();
  renderAdvisors();
  renderLocationPlaceholder();
  renderDebug();

  modules?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderTimeline() {
  const steps = [
    ["01", "Lectura inicial"],
    ["02", "Tesis cercanas"],
    ["03", "Objetivos"],
    ["04", "Preguntas"],
    ["05", "Asesores"]
  ];

  $("timeline").innerHTML = steps.map(step => `
    <div class="timeline-step">
      <small>${step[0]}</small>
      <strong>${step[1]}</strong>
    </div>
  `).join("");
}

function renderInitialNote() {
  const results = state.data.results || {};
  const note = results.initial_note || {};
  const root = note.initial_note || note.conceptual_interpretation || note;

  const title = root.title || "Lectura inicial";
  const summary = root.paragraph || root.summary || root.initial_reading || root.interpretation || root.conceptual_reading || root.note || "";
  const reformulation = root.one_sentence_reframe || root.reformulation || root.reformulated_title || root.reformulated_project || "";
  const routes = root.possible_angles || root.routes || root.possible_routes || root.research_routes || [];

  $("moduleInitial").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Lectura inicial</p>
        <h2>${escapeHtml(title)}</h2>
      </div>
    </div>
    ${summary ? `<p>${escapeHtml(summary)}</p>` : `<p>Se generó una lectura conceptual inicial del proyecto.</p>`}
    ${reformulation ? `<div class="quote">${escapeHtml(reformulation)}</div>` : ""}
    ${Array.isArray(routes) && routes.length ? `
      <div class="card-grid two-col">
        ${routes.slice(0, 4).map(route => `
          <div class="result-card">
            <strong>${escapeHtml(route.title || route.route || "Ruta posible")}</strong>
            <p>${escapeHtml(route.description || route.note || route)}</p>
          </div>
        `).join("")}
      </div>
    ` : ""}
  `;
}

function renderSemantic() {
  const context = state.data.context || {};
  const semantic = context.semantic_position || context.location || {};
  const keywords = context.keywords_detected || state.data.input?.keywords || [];

  const mainCluster = semantic.main_cluster || {};
  const clusterLabel = readableLabel(
    semantic.main_cluster_label ||
    mainCluster.label ||
    semantic.macro_label ||
    semantic.main_cluster
  ) || "Cluster semántico cercano";

  const mainArea = readableLabel(
    semantic.main_area ||
    semantic.area ||
    mainCluster.main_area ||
    mainCluster.macro_domain
  ) || "No especificada";

  $("moduleSemantic").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Ubicación semántica</p>
        <h2>Territorio académico detectado</h2>
      </div>
    </div>
    <div class="card-grid two-col">
      <div class="result-card">
        <strong>Cluster principal</strong>
        <p>${escapeHtml(clusterLabel)}</p>
      </div>
      <div class="result-card">
        <strong>Área dominante</strong>
        <p>${escapeHtml(mainArea)}</p>
      </div>
    </div>
    <div class="pill-row">
      ${keywords.slice(0, 12).map(keyword => `<span class="pill">${escapeHtml(keyword.keyword || keyword)}</span>`).join("")}
    </div>
  `;
}

function readableLabel(value) {
  if (value == null || value === "") return "";
  if (typeof value === "string" || typeof value === "number") return value;
  if (Array.isArray(value)) return value.map(readableLabel).filter(Boolean).join(" · ");

  if (typeof value === "object") {
    return value.label ||
      value.name ||
      value.title ||
      value.main_area ||
      value.macro_domain ||
      value.macro_label ||
      value.micro_label ||
      value.id ||
      "";
  }

  return String(value);
}

function renderTheses() {
  const results = state.data.results || {};
  const rerank = results.rerank || {};
  const context = state.data.context || {};
  const root = rerank.reranked_theses || rerank.thesis_recommendations || rerank;
  const theses = root.items || root.theses || context.top_similar_theses || [];

  $("moduleTheses").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Tesis afines</p>
        <h2>Tesis más útiles para tu proyecto</h2>
      </div>
    </div>
    <div class="card-grid">
      ${theses.slice(0, 8).map((thesis, index) => `
        <article class="thesis-card">
          <div class="thesis-top">
            <span class="pill">#${thesis.rank || index + 1}</span>
          </div>
          <h3>${escapeHtml(thesis.title || thesis.thesis_title || "Tesis sin título")}</h3>
          <p class="meta">${escapeHtml([thesis.year, thesis.program, thesis.degree, thesis.plantel].filter(Boolean).join(" · "))}</p>
          ${thesis.reason ? `<p>${escapeHtml(thesis.reason)}</p>` : ""}
        </article>
      `).join("") || `<p>No se recibieron tesis afines.</p>`}
    </div>
  `;
}

function renderBloom() {
  const bloom = (state.data.results || {}).bloom || {};
  const analysis = bloom.bloom_analysis || bloom;
  const ladder = analysis.objective_ladder || [];
  const revised = analysis.revised_objectives || [];

  $("moduleBloom").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Bloom</p>
        <h2>${escapeHtml(analysis.title || "Análisis cognitivo de tus objetivos")}</h2>
      </div>
    </div>
    ${analysis.cognitive_profile ? `<p>${escapeHtml(analysis.cognitive_profile)}</p>` : ""}
    ${analysis.main_risk ? `<div class="quote">${escapeHtml(analysis.main_risk)}</div>` : ""}
    ${ladder.length ? `
      <div class="ladder">
        ${ladder.map(item => `
          <div class="ladder-item">
            <div class="ladder-level">${escapeHtml(item.detected_level || "")}</div>
            <strong>${escapeHtml(item.original_objective || "")}</strong>
            <p>${escapeHtml(item.diagnosis || "")}</p>
            ${item.improvement ? `<p class="meta">Mejora: ${escapeHtml(item.improvement)}</p>` : ""}
          </div>
        `).join("")}
      </div>
    ` : ""}
    ${revised.length ? `
      <div class="result-card">
        <strong>Objetivos reescritos</strong>
        <ol>
          ${revised.map(objective => `<li>${escapeHtml(objective)}</li>`).join("")}
        </ol>
      </div>
    ` : ""}
    ${analysis.final_note ? `<p class="meta">${escapeHtml(analysis.final_note)}</p>` : ""}
  `;
}

function renderQuestions() {
  const questions = (state.data.results || {}).questions || {};
  const root = questions.research_questions || questions.questions || questions;
  const items = root.items || root.questions || [];

  $("moduleQuestions").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Preguntas</p>
        <h2>${escapeHtml(root.title || "Preguntas de investigación")}</h2>
      </div>
    </div>
    <div class="card-grid">
      ${items.map((item, index) => `
        <details class="question-card" ${index === 0 ? "open" : ""}>
          <summary>
            <strong>${escapeHtml(item.type || item.question_type || "Pregunta")}</strong>
            ${escapeHtml(item.question || item.text || item)}
          </summary>
          ${item.methodological_angle ? `<p class="meta">Método: ${escapeHtml(item.methodological_angle)}</p>` : ""}
          ${item.why_it_matters ? `<p>${escapeHtml(item.why_it_matters)}</p>` : ""}
        </details>
      `).join("") || `<p>No se recibieron preguntas de investigación.</p>`}
    </div>
  `;
}

function renderAdvisors() {
  const advisors = (state.data.results || {}).advisors || {};
  const root = advisors.advisor_recommendations || advisors;
  const items = root.items || [];

  $("moduleAdvisors").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Asesores</p>
        <h2>${escapeHtml(root.title || "Asesores relacionados")}</h2>
      </div>
    </div>
    <div class="card-grid">
      ${items.map(item => `
        <article class="advisor-card">
          <strong>${item.rank ? `${item.rank}. ` : ""}${escapeHtml(item.advisor_name || item.name || item.advisor_id)}</strong>
          <div class="pill-row">
            ${(item.programs || []).map(program => `<span class="pill">${escapeHtml(program)}</span>`).join("")}
            ${item.last_year ? `<span class="pill">Último año: ${escapeHtml(item.last_year)}</span>` : ""}
          </div>
          ${(item.representative_titles || []).slice(0, 2).map(title => `
            <p class="source-line">Tesis relacionada: ${escapeHtml(title)}</p>
          `).join("")}
        </article>
      `).join("") || `<p>No se recibieron asesores relacionados.</p>`}
    </div>
    ${root.disclaimer ? `<p class="meta">${escapeHtml(root.disclaimer)}</p>` : ""}
  `;
}

function renderLocationPlaceholder() {
  const location =
    state.data.context?.inferred_atlas_position ||
    state.data.results?.inferred_atlas_position ||
    state.data.inferred_atlas_position ||
    state.data.location ||
    state.data.context?.location ||
    state.data.results?.location;

  const module = $("moduleLocation");
  if (!module) return;

  module.classList.remove("hidden");

  if (!location || !location.available) {
    module.innerHTML = `
      <div class="module-head">
        <div>
          <p class="eyebrow">Ubicación en el atlas</p>
          <h2>Territorio semántico</h2>
        </div>
      </div>
      <p>
        Aún no hay suficiente evidencia para ubicar este proyecto dentro del atlas semántico.
      </p>
    `;
    return;
  }

  const confidence = Number(location.confidence || 0);
  const confidencePct = Math.round(confidence * 100);
  const confidenceLabel = location.confidence_label || "detectada";
  const macroId = location.macrocluster_id ?? "—";
  const microId = location.microcluster_id ?? "—";
  const macroLabel = location.macro_label || `Macrocluster ${macroId}`;
  const microLabel = location.micro_label || `Microcluster ${microId}`;
  const matched = location.matched_thesis_count ?? location.evidence_count ?? 0;
  const projectTitle = state.data.input?.title || state.data.context?.user_project?.title || "Tu proyecto";

  module.innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Ubicación en el atlas</p>
        <h2>Micro universo de evidencia</h2>
      </div>
    </div>

    <p>
      ${escapeHtml(location.interpretation || "El laboratorio usó las tesis similares como evidencia para inferir su ubicación dentro del Atlas.")}
    </p>

    <div class="card-grid two-col">
      <div class="result-card">
        <strong>Macrocluster</strong>
        <p>${escapeHtml(macroLabel)}</p>
      </div>
      <div class="result-card">
        <strong>Microcluster</strong>
        <p>${escapeHtml(microLabel)}</p>
      </div>
      <div class="result-card">
        <strong>Confianza</strong>
        <p>${escapeHtml(confidenceLabel)} · ${confidencePct}%</p>
      </div>
      <div class="result-card">
        <strong>Evidencia</strong>
        <p>${escapeHtml(String(matched))} tesis similares cruzadas</p>
      </div>
    </div>

    <div class="lab-atlas-toolbar">
      <div class="lab-atlas-mode-group" aria-label="Modo de visualización">
        <button class="lab-atlas-mode-btn active" type="button" data-lab-map-mode="universe">Universo</button>
        <button class="lab-atlas-mode-btn" type="button" data-lab-map-mode="analytic">Analítico</button>
      </div>

      <label class="lab-atlas-control">
        Agrupar por
        <select id="labAtlasGroupBy">
          <option value="program">Programa</option>
          <option value="degree">Nivel</option>
          <option value="area">Área</option>
          <option value="plantel">Plantel</option>
          <option value="period">Periodo</option>
        </select>
      </label>
    </div>

    <div class="lab-atlas-sigma-shell">
      <div class="lab-atlas-overlay">
        <div class="lab-atlas-overlay-card">
          <span>Territorio inferido</span>
          <strong>${escapeHtml(microLabel)}</strong>
        </div>
      </div>
      <div class="lab-atlas-sigma" id="labAtlasSigma"></div>
    </div>

    <div class="lab-atlas-tooltip" id="labAtlasTooltip"></div>

    <div class="lab-atlas-detail" id="labAtlasDetail">
      <p class="lab-mini-label">Selecciona una tesis del mapa</p>
      <strong>Explora la evidencia</strong>
      <p>Haz clic en cualquier nodo para ver programa, nivel, periodo y similitud.</p>
    </div>
  `;

  requestAnimationFrame(() => {
    renderLabMiniSigmaMap({
      container: $("labAtlasSigma"),
      tooltip: $("labAtlasTooltip"),
      detail: $("labAtlasDetail"),
      module,
      location,
      projectTitle
    });
  });
}

function buildLabAtlasMicroMap({ macroId, microId, macroLabel, microLabel, projectTitle, evidence }) {
  const width = 980;
  const height = 580;

  const macro = { x: 490, y: 70, r: 34 };
  const micro = { x: 490, y: 180, r: 30 };
  const project = { x: 490, y: 310, r: 42 };

  const items = evidence.slice(0, 10);
  const thesisNodes = items.map((item, index) => {
    const count = Math.max(items.length, 1);
    const startX = 125;
    const endX = 855;
    const x = count === 1 ? 490 : startX + (index * (endX - startX)) / (count - 1);
    const y = 465 + (index % 2 === 0 ? -16 : 18);
    const similarity = Number(item.similarity || 0);
    const r = 13 + Math.max(0, Math.min(1, similarity)) * 10;

    return { item, index, x, y, r, similarity };
  });

  const edgeToTheses = thesisNodes.map(node => {
    const opacity = 0.18 + Math.max(0, Math.min(1, node.similarity)) * 0.52;
    const width = 0.8 + Math.max(0, Math.min(1, node.similarity)) * 2.8;

    return `
      <line
        class="lab-atlas-edge thesis-edge"
        x1="${project.x}"
        y1="${project.y + project.r - 4}"
        x2="${node.x}"
        y2="${node.y - node.r}"
        stroke-opacity="${opacity.toFixed(3)}"
        stroke-width="${width.toFixed(2)}"
      />
    `;
  }).join("");

  const thesisMarkup = thesisNodes.map(node => {
    const item = node.item;
    const label = item.program || item.year || item.area || "tesis";
    const title = item.title || item.thesis_id || "Tesis relacionada";

    return `
      <g
        class="lab-atlas-thesis-node"
        data-evidence-index="${node.index}"
        tabindex="0"
        role="button"
        aria-label="${escapeHtml(title)}"
      >
        <circle cx="${node.x}" cy="${node.y}" r="${node.r}" />
        <text x="${node.x}" y="${node.y + 4}" text-anchor="middle">${node.index + 1}</text>
        <foreignObject x="${node.x - 62}" y="${node.y + node.r + 8}" width="124" height="54">
          <div xmlns="http://www.w3.org/1999/xhtml" class="lab-atlas-node-caption">
            <strong>${escapeHtml(label)}</strong>
            <span>${escapeHtml(String(item.similarity ?? ""))}</span>
          </div>
        </foreignObject>
        <title>${escapeHtml(title)}</title>
      </g>
    `;
  }).join("");

  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Micro mapa de ubicación semántica">
      <defs>
        <radialGradient id="labAtlasGlow" cx="50%" cy="45%" r="60%">
          <stop offset="0%" stop-color="#D7ECFF" stop-opacity="0.95" />
          <stop offset="60%" stop-color="#8CCBFF" stop-opacity="0.18" />
          <stop offset="100%" stop-color="#06111F" stop-opacity="0" />
        </radialGradient>
      </defs>

      <rect class="lab-atlas-bg" x="0" y="0" width="${width}" height="${height}" rx="26" />
      <circle cx="${project.x}" cy="${project.y}" r="230" fill="url(#labAtlasGlow)" opacity="0.58" />

      <line class="lab-atlas-edge trunk-edge" x1="${macro.x}" y1="${macro.y + macro.r}" x2="${micro.x}" y2="${micro.y - micro.r}" />
      <line class="lab-atlas-edge trunk-edge" x1="${micro.x}" y1="${micro.y + micro.r}" x2="${project.x}" y2="${project.y - project.r}" />

      ${edgeToTheses}

      <g class="lab-atlas-cluster-node macro-node">
        <circle cx="${macro.x}" cy="${macro.y}" r="${macro.r}" />
        <text x="${macro.x}" y="${macro.y + 5}" text-anchor="middle">M${escapeHtml(String(macroId))}</text>
        <foreignObject x="${macro.x - 210}" y="${macro.y - 66}" width="420" height="40">
          <div xmlns="http://www.w3.org/1999/xhtml" class="lab-atlas-cluster-label">
            <span>Macrocluster</span>
            <strong>${escapeHtml(macroLabel)}</strong>
          </div>
        </foreignObject>
      </g>

      <g class="lab-atlas-cluster-node micro-node">
        <circle cx="${micro.x}" cy="${micro.y}" r="${micro.r}" />
        <text x="${micro.x}" y="${micro.y + 5}" text-anchor="middle">μ${escapeHtml(String(microId))}</text>
        <foreignObject x="${micro.x - 230}" y="${micro.y - 70}" width="460" height="44">
          <div xmlns="http://www.w3.org/1999/xhtml" class="lab-atlas-cluster-label">
            <span>Microcluster</span>
            <strong>${escapeHtml(microLabel)}</strong>
          </div>
        </foreignObject>
      </g>

      <g class="lab-atlas-project-node">
        <circle cx="${project.x}" cy="${project.y}" r="${project.r}" />
        <text x="${project.x}" y="${project.y - 2}" text-anchor="middle">PROYECTO</text>
        <text x="${project.x}" y="${project.y + 16}" text-anchor="middle">USUARIO</text>
        <foreignObject x="${project.x - 230}" y="${project.y + project.r + 18}" width="460" height="58">
          <div xmlns="http://www.w3.org/1999/xhtml" class="lab-atlas-project-caption">
            ${escapeHtml(projectTitle)}
          </div>
        </foreignObject>
      </g>

      ${thesisMarkup}
    </svg>
  `;
}

function renderDebug() {
  const panel = $("debugPanel");

  if (!state.debugVisible) {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");
  panel.textContent = JSON.stringify({
    project_id: state.projectId,
    debug: state.data?.debug || [],
    results_keys: Object.keys(state.data?.results || {})
  }, null, 2);
}

function renderError(err) {
  $("loadingState")?.classList.add("hidden");
  $("modules")?.classList.add("hidden");

  const emptyState = $("emptyState");
  if (!emptyState) return;

  emptyState.classList.remove("hidden");
  emptyState.innerHTML = `
    <div class="error-box">
      <strong>No se pudo generar el laboratorio.</strong>
      <p>${escapeHtml(err.message || String(err))}</p>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function capitalize(value) {
  value = String(value || "");
  return value.charAt(0).toUpperCase() + value.slice(1);
}



let labMiniSigmaRenderer = null;
let labMiniSigmaGraph = null;
let labMiniSigmaState = {
  mode: "universe",
  groupBy: "program",
  hoveredNode: null,
  selectedNode: "PROJECT"
};

function renderLabMiniSigmaMap({ container, tooltip, detail, module, location, projectTitle }) {
  const libs = window.NODO_GRAPH_LIBS;

  if (!container || !libs?.Graph || !libs?.Sigma) {
    container.innerHTML = `
      <div class="lab-atlas-empty">
        No se pudo cargar la visualización interactiva. Graphology/Sigma no está disponible.
      </div>
    `;
    return;
  }

  if (labMiniSigmaRenderer) {
    try {
      labMiniSigmaRenderer.kill();
    } catch (_) {}
    labMiniSigmaRenderer = null;
    labMiniSigmaGraph = null;
  }

  const { Graph, Sigma } = libs;
  const evidence = Array.isArray(location.evidence) ? location.evidence.slice(0, 10) : [];

  const graph = new Graph({ multi: false, type: "undirected" });
  labMiniSigmaGraph = graph;

  const macroLabel = location.macro_label || `Macrocluster ${location.macrocluster_id ?? ""}`;
  const microLabel = location.micro_label || `Microcluster ${location.microcluster_id ?? ""}`;

  graph.addNode("MACRO", {
    nodeKind: "context",
    label: "",
    fullLabel: macroLabel,
    displayLabel: macroLabel,
    x: 0,
    y: 2.5,
    size: 136,
    color: "#123A63",
    baseColor: "#123A63"
  });

  graph.addNode("MACRO_LABEL", {
    nodeKind: "contextLabel",
    label: macroLabel,
    fullLabel: macroLabel,
    displayLabel: macroLabel,
    x: 0,
    y: 2.5,
    size: 0.2,
    color: "rgba(0,0,0,0)"
  });

  graph.addNode("MICRO", {
    nodeKind: "context",
    label: "",
    fullLabel: microLabel,
    displayLabel: microLabel,
    x: 0,
    y: 1.55,
    size: 40,
    color: "#4FA3FF",
    baseColor: "#4FA3FF"
  });

  graph.addNode("MICRO_LABEL", {
    nodeKind: "contextLabel",
    label: microLabel,
    fullLabel: microLabel,
    displayLabel: microLabel,
    x: 0,
    y: 1.55,
    size: 0.2,
    color: "rgba(0,0,0,0)"
  });

  graph.addNode("PROJECT", {
    nodeKind: "project",
    label: "PROYECTO",
    fullLabel: projectTitle,
    displayLabel: projectTitle,
    x: 0,
    y: 0,
    size: 17,
    color: "#FFE88A",
    baseColor: "#FFE88A"
  });

  graph.addEdgeWithKey("MACRO_MICRO", "MACRO", "MICRO", {
    type: "line",
    size: 1.6,
    color: "rgba(215,236,255,0.38)"
  });

  graph.addEdgeWithKey("MICRO_PROJECT", "MICRO", "PROJECT", {
    type: "line",
    size: 1.8,
    color: "rgba(215,236,255,0.46)"
  });

  evidence.forEach((item, index) => {
    const id = item.thesis_id || `T${index + 1}`;
    const angle = (-Math.PI * 0.08) + (index / Math.max(evidence.length, 1)) * Math.PI * 2;
    const radius = 2.15 + (index % 2) * 0.28;
    const similarity = Number(item.similarity || 0);
    const size = 7.5 + similarity * 6.5;

    const degreeLabel = String(item.degree || item.level || "")
      .replace("Licenciatura", "LICENCIATURA")
      .replace("Maestría", "MAESTRÍA")
      .replace("Maestria", "MAESTRÍA")
      .replace("Doctorado", "DOCTORADO");

    const programLabel = String(item.program || "sin programa")
      .replace("ciencias politicas y administracion publica", "c. políticas")
      .replace("relaciones internacionales", "rel. intern.")
      .replace("administracion", "admin.")
      .replace("contaduria", "contaduría")
      .replace("economia", "economía");

    const yearLabel = String(item.year || "s/f");
    const bottomLabel = `${programLabel}, ${yearLabel}`;

    graph.addNode(id, {
      ...item,
      nodeKind: "thesis",
      label: "",
      fullLabel: item.title || id,
      displayLabel: String(item.title || id).toUpperCase(),
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius - 0.1,
      size,
      baseSize: size,
      color: labMiniColorForGroup(item.program, index),
      baseColor: labMiniColorForGroup(item.program, index),
      evidenceIndex: index
    });

    graph.addNode(`${id}::LEVEL_LABEL`, {
      nodeKind: "thesisLabel",
      labelRole: "level",
      thesisId: id,
      label: String(degreeLabel).toUpperCase(),
      fullLabel: String(degreeLabel).toUpperCase(),
      displayLabel: String(degreeLabel).toUpperCase(),
      x: 0,
      y: 0,
      size: 0.2,
      color: "rgba(0,0,0,0)"
    });

    graph.addNode(`${id}::META_LABEL`, {
      nodeKind: "thesisLabel",
      labelRole: "program",
      thesisId: id,
      label: String(bottomLabel).toUpperCase(),
      fullLabel: String(bottomLabel).toUpperCase(),
      displayLabel: String(bottomLabel).toUpperCase(),
      rawLabel: String(bottomLabel).toUpperCase(),
      x: 0,
      y: 0,
      size: 0.2,
      color: "rgba(0,0,0,0)"
    });

    graph.addNode(`${id}::YEAR_LABEL`, {
      nodeKind: "thesisLabel",
      labelRole: "year",
      thesisId: id,
      label: "",
      fullLabel: "",
      displayLabel: "",
      x: 0,
      y: 0,
      size: 0.2,
      color: "rgba(0,0,0,0)"
    });

    graph.addEdgeWithKey(`PROJECT_${id}`, "PROJECT", id, {
      type: "line",
      size: 0.55,
      color: "rgba(215, 226, 236, 0.32)",
      baseColor: "rgba(215, 226, 236, 0.32)",
      targetColor: "#D7ECFF"
    });
  });

  const renderer = new Sigma(graph, container, {
    renderEdgeLabels: false,
    allowInvalidContainer: true,
    defaultEdgeType: "line",
    labelFont: "Montserrat",
    labelSize: 10,
    labelWeight: "600",
    labelColor: { color: "#EAF4FF" },
    defaultEdgeColor: "rgba(215,236,255,0.20)",
    enableEdgeEvents: false,
    enableCameraZooming: false,
    enableCameraPanning: false,
    enableNodeDragging: false,
    minCameraRatio: 0.70,
    maxCameraRatio: 1.85,
    nodeReducer: (node, data) => {
      const res = { ...data };
      const isHovered = node === labMiniSigmaState.hoveredNode;
      const isSelected = node === labMiniSigmaState.selectedNode;

      if (data.nodeKind === "project") {
        res.color = "#FFE88A";
        res.label = "PROYECTO";
        res.size = labMiniSigmaState.mode === "analytic" ? 16 : data.size;
      }

      if (data.nodeKind === "context") {
        if (labMiniSigmaState.mode === "analytic") {
          res.hidden = true;
          return res;
        }

        res.label = "";
        res.color = data.baseColor;

        if (node === "MACRO") {
          res.size = 136;
        }

        if (node === "MICRO") {
          res.size = 40;
        }
      }

      if (data.nodeKind === "contextLabel") {
        if (labMiniSigmaState.mode === "analytic") {
          res.hidden = true;
          return res;
        }

        res.label = data.displayLabel || data.fullLabel || "";
        res.size = 0.2;
        res.color = "rgba(0,0,0,0)";
        res.forceLabel = true;
      }

      if (data.nodeKind === "thesisLabel") {
        if (labMiniSigmaState.mode === "analytic") {
          res.hidden = true;
          return res;
        }

        // En universo:
        // - ocultar nivel
        // - ocultar año separado
        // - dejar solo el label inferior combinado: PROGRAMA, AÑO
        if (data.labelRole === "level" || data.labelRole === "year") {
          res.hidden = true;
          return res;
        }

        res.label = data.displayLabel || data.fullLabel || "";
        res.labelSize = 8.2;
        res.labelWeight = "600";
        res.labelColor = { color: "rgba(234,244,255,0.86)" };
        res.size = 0.1;
        res.color = "rgba(0,0,0,0)";
        res.forceLabel = true;
      }

      if (data.nodeKind === "thesis") {
        // Sin número dentro del nodo en Universo; labels viven arriba/abajo.
        res.label = "";
        res.color = data.baseColor || data.color;

        if (isHovered || isSelected) {
          res.size = Number(data.baseSize || data.size || 8) * 1.35;
          res.highlighted = true;
        }
      }

      if (data.nodeKind === "group") {
        res.label = data.displayLabel;
        res.size = 0.2;
        res.color = "rgba(0,0,0,0)";
        res.forceLabel = true;
      }

      if (labMiniSigmaState.selectedNode && node !== labMiniSigmaState.selectedNode) {
        const selectedKind = graph.hasNode(labMiniSigmaState.selectedNode)
          ? graph.getNodeAttribute(labMiniSigmaState.selectedNode, "nodeKind")
          : null;

        if (selectedKind === "thesis") {
          const neighbors = new Set(graph.neighbors(labMiniSigmaState.selectedNode));
          if (!neighbors.has(node) && data.nodeKind !== "group") {
            res.color = "rgba(145,170,195,0.34)";
          }
        }
      }

      return res;
    },
    edgeReducer: (edge, data) => {
      const res = { ...data };
      const [source, target] = graph.extremities(edge);

      if (labMiniSigmaState.mode === "analytic") {
        // En el modo analítico el objetivo es leer agrupaciones,
        // no relaciones radiales. Ocultamos todos los edges.
        res.hidden = true;
        return res;
      }

      if (labMiniSigmaState.mode === "universe") {
        res.color = "rgba(215, 226, 236, 0.38)";
        res.size = 0.75;
      }

      if (labMiniSigmaState.selectedNode) {
        if (![source, target].includes(labMiniSigmaState.selectedNode)) {
          res.color = "rgba(215, 226, 236, 0.12)";
        } else {
          res.color = labMiniSigmaState.mode === "universe"
            ? "rgba(235, 240, 245, 0.58)"
            : "rgba(215,236,255,0.72)";
          res.size = labMiniSigmaState.mode === "universe"
            ? 0.95
            : Math.max(Number(data.size || 1), 1.8);
        }
      }

      return res;
    }
  });

  labMiniSigmaRenderer = renderer;

  function refreshMiniLayout(animate = true) {
    const shell = container.closest(".lab-atlas-sigma-shell");
    if (shell) {
      shell.classList.toggle("is-analytic", labMiniSigmaState.mode === "analytic");

      const overlay = shell.querySelector(".lab-atlas-overlay");
      if (overlay) overlay.style.display = labMiniSigmaState.mode === "analytic" ? "none" : "";
    }

    const theses = evidence.slice(0, 10).map((item, index) => ({
      ...item,
      id: item.thesis_id || `T${index + 1}`,
      level: item.degree
    }));

    for (const node of [...graph.nodes()]) {
      if (graph.getNodeAttribute(node, "nodeKind") === "group") {
        graph.dropNode(node);
      }
    }

    const explorePalette = [
      "#174EA6", "#7A1E3A", "#5A9A7A", "#9A6A8F", "#D08A2E",
      "#6B4BB7", "#3E7C8B", "#A14D4D", "#76664B", "#4D6A3F",
      "#284B63", "#8C6A5D", "#B08A00", "#706C61"
    ];

    const areaPalette = {
      "Area 1": "#D7ECFF",
      "Area 2": "#8CCBFF",
      "Area 3": "#4FA3FF",
      "Area 4": "#2D6BFF",
      "Por Clasificar": "#6B7C93"
    };

    const labels = [...new Set(theses.map(item => labMiniCategoryValue(item, labMiniSigmaState.groupBy)))];

    if (labMiniSigmaState.groupBy === "period" || labMiniSigmaState.groupBy === "year") {
      labels.sort((a, b) => {
        const ax = Number(String(a).match(/\d{4}/)?.[0] || 9999);
        const bx = Number(String(b).match(/\d{4}/)?.[0] || 9999);
        return ax - bx;
      });
    } else {
      labels.sort();
    }

    const colorMap = new Map();
    labels.forEach((label, index) => {
      const color = labMiniSigmaState.groupBy === "area"
        ? (areaPalette[label] || explorePalette[index % explorePalette.length])
        : explorePalette[index % explorePalette.length];

      colorMap.set(label, color);
    });

    const getGroupColor = label => colorMap.get(label) || "#174EA6";

    theses.forEach((item) => {
      const id = item.id;
      if (!graph.hasNode(id)) return;

      const category = labMiniCategoryValue(item, labMiniSigmaState.groupBy);

      // Universo: todas las tesis similares usan el mismo azul claro del proyecto original.
      // Analítico: se colorean por categoría con la paleta tipo Explore.
      const color = labMiniSigmaState.mode === "universe"
        ? "#D7ECFF"
        : getGroupColor(category);

      graph.mergeNodeAttributes(id, {
        color,
        baseColor: color,
        categoryLabel: category
      });
    });

    const groups = labMiniGroupTheses(theses, labMiniSigmaState.groupBy);

    if (labMiniSigmaState.mode === "analytic") {
      groups.forEach(([label, items], groupIndex) => {
        const id = `GROUP::${label}`;
        const color = getGroupColor(label);

        graph.addNode(id, {
          nodeKind: "group",
          type: "circle",
          x: 0,
          y: 0,
          size: 18,
          color: "rgba(0,0,0,0)",
          label: labMiniNormalizedCategoryLabel(label),
          fullLabel: labMiniNormalizedCategoryLabel(label),
          displayLabel: labMiniNormalizedCategoryLabel(label),
          count: items.length,
          category: labMiniSigmaState.groupBy,
          groupColor: color
        });
      });
    }

    const positions = labMiniSigmaState.mode === "universe"
      ? labMiniComputeUniversePositions(theses)
      : labMiniComputeAnalyticPositions(theses, groups);

    if (animate) {
      labMiniAnimateToPositions(graph, renderer, positions, 850);
    } else {
      for (const [id, pos] of Object.entries(positions)) {
        if (!graph.hasNode(id)) continue;
        graph.setNodeAttribute(id, "x", pos.x);
        graph.setNodeAttribute(id, "y", pos.y);
      }
      renderer.refresh();
    }

    centerLabMiniSigmaCamera(renderer, animate);
  }

  renderer.on("enterNode", ({ node, event }) => {
    labMiniSigmaState.hoveredNode = node;
    const attrs = graph.getNodeAttributes(node);
    updateLabMiniTooltip(tooltip, attrs, event.original);
    renderer.refresh();
  });

  renderer.on("leaveNode", () => {
    labMiniSigmaState.hoveredNode = null;
    tooltip?.classList.remove("visible");
    renderer.refresh();
  });

  renderer.on("clickNode", ({ node }) => {
    const attrs = graph.getNodeAttributes(node);
    if (attrs.nodeKind === "group" || attrs.nodeKind === "thesisLabel" || attrs.nodeKind === "contextLabel") return;

    labMiniSigmaState.selectedNode = labMiniSigmaState.selectedNode === node ? null : node;
    renderLabMiniDetail(detail, attrs);
    renderer.refresh();
  });

  renderer.on("clickStage", () => {
    labMiniSigmaState.selectedNode = null;
    tooltip?.classList.remove("visible");
    renderer.refresh();
  });

  module.querySelectorAll("[data-lab-map-mode]").forEach(button => {
    button.addEventListener("click", () => {
      labMiniSigmaState.mode = button.dataset.labMapMode || "universe";

      module.querySelectorAll("[data-lab-map-mode]").forEach(btn => {
        btn.classList.toggle("active", btn === button);
      });

      refreshMiniLayout(true);
    });
  });

  const groupSelect = module.querySelector("#labAtlasGroupBy");
  if (groupSelect) {
    groupSelect.value = labMiniSigmaState.groupBy || "program";
    groupSelect.addEventListener("change", () => {
      labMiniSigmaState.groupBy = groupSelect.value;
      labMiniSigmaState.mode = "analytic";

      module.querySelectorAll("[data-lab-map-mode]").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.labMapMode === "analytic");
      });

      refreshMiniLayout(true);
    });
  }

  labMiniSigmaState.mode = "universe";
  labMiniSigmaState.groupBy = "program";
  labMiniSigmaState.selectedNode = "PROJECT";

  refreshMiniLayout(false);
  renderLabMiniDetail(detail, graph.getNodeAttributes("PROJECT"));

  setTimeout(() => centerLabMiniSigmaCamera(renderer, false), 120);
}


function centerLabMiniSigmaCamera(renderer, animate = false) {
  if (!renderer || !labMiniSigmaGraph) return;

  requestAnimationFrame(() => {
    try {
      renderer.resize();
      renderer.refresh();

      const graph = labMiniSigmaGraph;

      const ids = graph.nodes().filter(id => {
        const attrs = graph.getNodeAttributes(id);
        if (!attrs) return false;

        if (labMiniSigmaState.mode === "analytic") {
          return ["project", "thesis", "group"].includes(attrs.nodeKind);
        }

        return !["group"].includes(attrs.nodeKind);
      });

      const xs = [];
      const ys = [];

      ids.forEach(id => {
        const x = Number(graph.getNodeAttribute(id, "x"));
        const y = Number(graph.getNodeAttribute(id, "y"));

        if (Number.isFinite(x) && Number.isFinite(y)) {
          xs.push(x);
          ys.push(y);
        }
      });

      const minX = xs.length ? Math.min(...xs) : 0;
      const maxX = xs.length ? Math.max(...xs) : 0;
      const minY = ys.length ? Math.min(...ys) : 0;
      const maxY = ys.length ? Math.max(...ys) : 0;

      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;

      const width = Math.max(maxX - minX, 1);
      const height = Math.max(maxY - minY, 1);

      const camera = renderer.getCamera();

      const target = labMiniSigmaState.mode === "analytic"
        ? {
            x: centerX,
            y: centerY,
            ratio: Math.max(width / 5.2, height / 3.4, 0.82),
            angle: 0
          }
        : {
            // Aumentar x centra la cámara más a la derecha,
            // haciendo que el contenido aparezca más a la izquierda.
            x: centerX + 0.42,
            y: centerY,
            ratio: Math.max(width / 5.35, height / 2.95, 1.08),
            angle: 0
          };

      camera.setState(target);
      renderer.refresh();

      setTimeout(() => {
        renderer.resize();
        camera.setState(target);
        renderer.refresh();
      }, 80);
    } catch (_) {}
  });
}



function labMiniClamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function labMiniDecadeLabel(year) {
  if (!year) return "SIN FECHA";
  const start = Math.floor(Number(year) / 10) * 10;
  return `${start}-${start + 9}`;
}

function labMiniCategoryValue(node, category) {
  if (category === "year" || category === "period") return node.period || labMiniDecadeLabel(node.year);
  if (category === "program") return node.program || "SIN PROGRAMA";
  if (category === "plantel") return node.plantel || "SIN PLANTEL";
  if (category === "degree" || category === "level") return node.degree || node.level || "SIN NIVEL";
  if (category === "area") return node.area || "SIN ÁREA";
  return "SIN CATEGORÍA";
}

function labMiniNormalizedCategoryLabel(label) {
  return String(label || "SIN DATO").toUpperCase();
}

function labMiniGroupTheses(theses, groupBy) {
  const groups = new Map();

  for (const n of theses) {
    const key = labMiniCategoryValue(n, groupBy);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(n);
  }

  let entries = [...groups.entries()];

  entries.sort((a, b) => {
    const aMax = Math.max(...a[1].map(n => Number(n.similarity || 0)));
    const bMax = Math.max(...b[1].map(n => Number(n.similarity || 0)));
    return bMax - aMax || b[1].length - a[1].length;
  });

  return entries;
}


function labMiniEstimateLabelAnchorOffset(label) {
  // Sigma dibuja labels hacia la derecha desde x.
  // Este offset intenta que el centro visual del texto coincida con el centro del nodo.
  //
  // Aproximación:
  // - labelSize ~8.6px
  // - ancho promedio por carácter ~0.54em
  // - conversión aproximada px -> unidades grafo para esta cámara/layout.
  const text = String(label || "");
  const chars = text.length;

  // Caracteres angostos/pesados ajustan un poco el ancho percibido.
  const narrow = (text.match(/[ilI1\., ]/g) || []).length;
  const wide = (text.match(/[MWmwÁÉÍÓÚÑ]/g) || []).length;

  const visualChars = chars - narrow * 0.38 + wide * 0.28;

  // Offset base en coordenadas de grafo.
  // Clamp para evitar que labels muy largos se vayan demasiado a la izquierda.
  const offset = visualChars * 0.030;

  return Math.max(0.18, Math.min(offset, 0.68));
}


function labMiniComputeUniversePositions(theses) {
  // Universo narrativo fijo y compacto:
  // macro-sol parcial -> microcluster -> proyecto -> top 10 evidencia.
  // Importante: Sigma dibuja labels hacia la derecha del punto,
  // por eso las etiquetas se colocan ligeramente a la izquierda del nodo.
  const positions = {
    MACRO: { x: -6.95, y: 0 },
    MACRO_LABEL: { x: -5.68, y: -1.52 },
    MICRO: { x: -4.10, y: 0 },
    MICRO_LABEL: { x: -4.18, y: -0.84 },
    PROJECT: { x: -2.22, y: 0 }
  };

  const sorted = [...theses].sort((a, b) => Number(b.similarity || 0) - Number(a.similarity || 0));

  // Más compacto y menos cargado a la derecha.
  const columns = [
    { x: -0.45, ys: [-1.46, -0.73, 0, 0.73, 1.46] },
    { x: 0.82, ys: [-1.46, -0.73, 0, 0.73, 1.46] }
  ];

  sorted.slice(0, 10).forEach((n, i) => {
    const id = n.thesis_id || `T${i + 1}`;
    const col = i < 5 ? columns[0] : columns[1];
    const row = i < 5 ? i : i - 5;

    const x = col.x;
    const y = col.ys[row];

    positions[id] = { x, y };

    // Eje Y visual de Sigma: valores mayores suelen aparecer más arriba.
    // Labels separados para que no se encimen y para dar jerarquía visual.
    // Ocultar label superior de nivel
    positions[`${id}::LEVEL_LABEL`] = { x: 0, y: -2.45 };

    // Sigma pinta el texto hacia la derecha desde el punto.
    // Para centrar el texto bajo el nodo, estimamos su longitud visual
    // y movemos el anchor a la izquierda proporcionalmente.
    const labelText = [
      n.program || "sin programa",
      n.year || "s/f"
    ].filter(Boolean).join(", ").toUpperCase();

    const labelOffset = labMiniEstimateLabelAnchorOffset(labelText);
    positions[`${id}::META_LABEL`] = { x: x - labelOffset, y: y - 0.28 };

    // Ocultar año separado
    positions[`${id}::YEAR_LABEL`] = { x: 0, y: -2.45 };
  });

  return positions;
}

function labMiniComputeAnalyticPositions(theses, groups) {
  // Analítico reducido:
  // proyecto abajo centrado; tesis arriba agrupadas.
  // IMPORTANTE: no mandar nodos ocultos a -999, porque Sigma los usa
  // para normalizar el encuadre aunque el reducer los oculte.
  const positions = {
    MACRO: { x: 0, y: -2.45 },
    MICRO: { x: 0, y: -2.45 },
    MACRO_LABEL: { x: 0, y: -2.45 },
    MICRO_LABEL: { x: 0, y: -2.45 },
    PROJECT: { x: 0, y: -2.45 }
  };

  theses.forEach((node, i) => {
    const id = node.thesis_id || `T${i + 1}`;
    positions[`${id}::LEVEL_LABEL`] = { x: 0, y: -2.45 };
    positions[`${id}::META_LABEL`] = { x: 0, y: -2.45 };
    positions[`${id}::YEAR_LABEL`] = { x: 0, y: -2.45 };
  });

  const groupCount = groups.length;
  const cols = Math.min(4, Math.max(1, Math.ceil(Math.sqrt(groupCount))));
  const xGap = 2.35;
  const yGap = 1.55;
  const startX = -((cols - 1) * xGap) / 2;
  const startY = 1.10;

  groups.forEach(([label, items], gi) => {
    const col = gi % cols;
    const row = Math.floor(gi / cols);
    const cx = startX + col * xGap;
    const cy = startY - row * yGap;

    const sortedItems = [...items].sort((a, b) => Number(b.similarity || 0) - Number(a.similarity || 0));

    const n = sortedItems.length;
    const innerCols = Math.ceil(Math.sqrt(n));
    const spacing = n > 8 ? 0.32 : 0.40;
    const width = (innerCols - 1) * spacing;
    const rows = Math.ceil(n / innerCols);
    const height = (rows - 1) * spacing;

    sortedItems.forEach((node, i) => {
      const id = node.thesis_id || `T${i + 1}`;
      const ix = i % innerCols;
      const iy = Math.floor(i / innerCols);

      positions[id] = {
        x: cx - width / 2 + ix * spacing,
        y: cy - height / 2 + iy * spacing
      };
    });

    const groupId = `GROUP::${label}`;
    positions[groupId] = {
      x: cx,
      y: cy + 0.62
    };
  });

  return positions;
}

function labMiniAnimateToPositions(graph, renderer, positions, duration = 850) {
  const start = {};
  const ids = Object.keys(positions);

  for (const id of ids) {
    if (!graph.hasNode(id)) continue;
    start[id] = {
      x: graph.getNodeAttribute(id, "x"),
      y: graph.getNodeAttribute(id, "y")
    };
  }

  const startTime = performance.now();

  function ease(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function frame(now) {
    const t = labMiniClamp((now - startTime) / duration, 0, 1);
    const k = ease(t);

    for (const id of ids) {
      if (!graph.hasNode(id) || !start[id]) continue;

      const sx = start[id].x;
      const sy = start[id].y;
      const tx = positions[id].x;
      const ty = positions[id].y;

      graph.setNodeAttribute(id, "x", sx + (tx - sx) * k);
      graph.setNodeAttribute(id, "y", sy + (ty - sy) * k);
    }

    renderer.refresh();

    if (t < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}


function updateLabMiniTooltip(tooltip, attrs, event) {
  if (!tooltip || !attrs) return;

  const title = attrs.fullLabel || attrs.title || attrs.displayLabel || attrs.label || "Nodo";
  const meta = [
    attrs.program,
    attrs.degree,
    attrs.area,
    attrs.period,
    attrs.similarity ? `Similitud ${attrs.similarity}` : null
  ].filter(Boolean).join(" · ");

  tooltip.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <p>${escapeHtml(meta || attrs.nodeKind || "")}</p>
  `;

  tooltip.style.left = `${event.clientX + 14}px`;
  tooltip.style.top = `${event.clientY + 14}px`;
  tooltip.classList.add("visible");
}

function renderLabMiniDetail(detail, attrs) {
  if (!detail || !attrs) return;

  if (attrs.nodeKind === "thesisLabel" || attrs.nodeKind === "contextLabel") {
    return;
  }

  if (attrs.nodeKind === "project") {
    detail.innerHTML = `
      <p class="lab-mini-label">Proyecto del usuario</p>
      <strong>${escapeHtml(attrs.fullLabel || "Tu proyecto")}</strong>
      <p>Centro del micro universo. Las tesis alrededor son las más cercanas semánticamente.</p>
    `;
    return;
  }

  if (attrs.nodeKind === "context") {
    detail.innerHTML = `
      <p class="lab-mini-label">${escapeHtml(attrs.label || "Territorio")}</p>
      <strong>${escapeHtml(attrs.fullLabel || attrs.displayLabel || "Cluster")}</strong>
      <p>Territorio semántico usado para contextualizar la ubicación del proyecto.</p>
    `;
    return;
  }

  detail.innerHTML = `
    <p class="lab-mini-label">Tesis relacionada</p>
    <strong>${escapeHtml(attrs.fullLabel || attrs.title || attrs.thesis_id || "Tesis relacionada")}</strong>
    <p>
      ${escapeHtml(attrs.program || "Programa no disponible")}
      ${attrs.degree ? ` · ${escapeHtml(attrs.degree)}` : ""}
      ${attrs.year ? ` · ${escapeHtml(String(attrs.year))}` : ""}
      ${attrs.period ? ` · ${escapeHtml(attrs.period)}` : ""}
    </p>
    <p class="source-line">
      ${attrs.area ? `${escapeHtml(attrs.area)} · ` : ""}
      ${attrs.plantel ? `${escapeHtml(attrs.plantel)} · ` : ""}
      Similitud ${escapeHtml(String(attrs.similarity ?? "—"))}
    </p>
  `;
}

function labMiniColorForGroup(value, index = 0) {
  // Misma lógica visual del Explore analítico: categorías con paleta diversa.
  const palette = [
    "#174EA6", "#7A1E3A", "#5A9A7A", "#9A6A8F", "#D08A2E",
    "#6B4BB7", "#3E7C8B", "#A14D4D", "#76664B", "#4D6A3F",
    "#284B63", "#8C6A5D", "#B08A00", "#706C61"
  ];

  const key = String(value || "Sin dato");
  let hash = 0;

  for (let i = 0; i < key.length; i += 1) {
    hash = ((hash << 5) - hash) + key.charCodeAt(i);
    hash |= 0;
  }

  return palette[Math.abs(hash + index) % palette.length];
}


