const API = "";

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
  ["Analizando tu idea...", "Interpretando núcleo temático."],
  ["Ubicando tesis similares...", "Buscando afinidades semánticas."],
  ["Reordenando antecedentes...", "Priorizando tesis útiles para tu proyecto."],
  ["Analizando objetivos...", "Leyendo progresión cognitiva."],
  ["Formulando preguntas...", "Construyendo rutas de investigación."]
];

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  renderChips();
  renderBloomLocal();
  renderVerbPopup();
});

function $(id) {
  return document.getElementById(id);
}

function bindEvents() {
  $("labForm").addEventListener("submit", handleRunBasic);

  $("addKeywordBtn").addEventListener("click", addKeyword);
  $("newKeyword").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addKeyword();
    }
  });

  $("addObjectiveBtn").addEventListener("click", addObjective);
  $("newObjective").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addObjective();
    }
  });

  $("verbBulb").addEventListener("click", () => {
    $("verbPopup").classList.toggle("open");
  });

  $("closeVerbPopup").addEventListener("click", () => {
    $("verbPopup").classList.remove("open");
  });

  $("runBibliographyBtn").addEventListener("click", runBibliography);
  $("runAdvisorsBtn").addEventListener("click", runAdvisors);

  $("debugToggle").addEventListener("click", () => {
    state.debugVisible = !state.debugVisible;
    renderDebug();
  });
}

function addKeyword() {
  const input = $("newKeyword");
  const value = input.value.trim();

  if (!value) return;

  if (!state.keywords.includes(value)) {
    state.keywords.push(value);
  }

  input.value = "";
  renderChips();
}

function addObjective() {
  const input = $("newObjective");
  const value = input.value.trim();

  if (!value) return;

  if (!state.objectives.includes(value)) {
    state.objectives.push(value);
  }

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

function renderChips() {
  $("keywordsContainer").innerHTML = state.keywords.map((k, i) => `
    <span class="chip">${escapeHtml(k)} <span class="remove" onclick="removeKeyword(${i})">×</span></span>
  `).join("");

  $("objectivesContainer").innerHTML = state.objectives.map((o, i) => {
    const level = detectBloomLevel(o);
    return `
      <span class="chip">
        ${escapeHtml(o)}
        ${level ? `<small>· ${level}</small>` : ""}
        <span class="remove" onclick="removeObjective(${i})">×</span>
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
  Object.keys(bloomVerbs).forEach(k => counts[k] = 0);

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
        ${verbs.map(v => `<button class="verb-chip" type="button" onclick="insertVerb('${v}')">${v}</button>`).join("")}
      </div>
    </div>
  `).join("");
}

function insertVerb(verb) {
  const input = $("newObjective");
  const current = input.value.trim();

  if (!current) {
    input.value = capitalize(verb) + " ";
  } else {
    input.value = capitalize(verb) + " " + current;
  }

  input.focus();
  $("verbPopup").classList.remove("open");
}

function buildPayload() {
  const title = $("title").value.trim();
  const degree = $("degree").value.trim();
  const program = $("program").value.trim();
  const plantel = $("plantel").value.trim();

  const applies = $("periodApplies").checked;
  const start = $("startYear").value ? Number($("startYear").value) : null;
  const end = $("endYear").value ? Number($("endYear").value) : null;

  return {
    title,
    keywords: state.keywords,
    objectives: state.objectives,
    program,
    degree,
    plantel,
    study_period: {
      applies,
      start_year: applies ? start : null,
      end_year: applies ? end : null,
      label: applies && start && end ? `${start}-${end}` : null
    }
  };
}

async function handleRunBasic(e) {
  e.preventDefault();

  const payload = buildPayload();

  if (!payload.title || payload.objectives.length === 0) {
    alert("Agrega al menos título y un objetivo.");
    return;
  }

  setLoading(true, 0);

  try {
    animateLoading();

    const response = await postJSON("/api/lab/run-basic", payload);

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
  let i = 0;

  const timer = setInterval(() => {
    if ($("loadingState").classList.contains("hidden")) {
      clearInterval(timer);
      return;
    }

    const step = loadingSteps[i % loadingSteps.length];
    $("loadingTitle").textContent = step[0];
    $("loadingText").textContent = step[1];
    i += 1;
  }, 2500);
}

async function runBibliography() {
  if (!state.projectId) return;

  $("runBibliographyBtn").disabled = true;
  $("runBibliographyBtn").querySelector("small").textContent = "Seleccionando bibliografía...";

  try {
    const response = await postJSON("/api/lab/run-bibliography", { project_id: state.projectId });
    state.data = normalizeResponse(response);
    renderBibliography();
    renderDebug();
  } catch (err) {
    renderModuleError("moduleBibliography", err);
  } finally {
    $("runBibliographyBtn").disabled = false;
    $("runBibliographyBtn").querySelector("small").textContent = "Selecciona fuentes reales extraídas de tesis afines.";
  }
}

async function runAdvisors() {
  if (!state.projectId) return;

  $("runAdvisorsBtn").disabled = true;
  $("runAdvisorsBtn").querySelector("small").textContent = "Buscando asesores...";

  try {
    const response = await postJSON("/api/lab/run-advisors", { project_id: state.projectId });
    state.data = normalizeResponse(response);
    renderAdvisors();
    renderDebug();
  } catch (err) {
    renderModuleError("moduleAdvisors", err);
  } finally {
    $("runAdvisorsBtn").disabled = false;
    $("runAdvisorsBtn").querySelector("small").textContent = "Ordena asesores por afinidad temática histórica.";
  }
}

async function postJSON(url, payload) {
  const res = await fetch(API + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const json = await res.json();

  if (!res.ok) {
    const detail = json.detail || json;
    throw new Error(detail.message || detail.error || "Error en la API");
  }

  return json;
}

function normalizeResponse(response) {
  if (response && response.data) return response.data;
  return response;
}

function setLoading(isLoading) {
  $("emptyState").classList.toggle("hidden", isLoading);
  $("loadingState").classList.toggle("hidden", !isLoading);
  $("modules").classList.add("hidden");
}

function renderAll() {
  $("emptyState").classList.add("hidden");
  $("loadingState").classList.add("hidden");
  $("modules").classList.remove("hidden");

  renderTimeline();
  renderInitialNote();
  renderSemantic();
  renderTheses();
  renderBloom();
  renderQuestions();
  renderBibliography();
  renderAdvisors();
  renderDebug();

  document.querySelector("#results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderTimeline() {
  const steps = [
    ["01", "Lectura inicial"],
    ["02", "Tesis cercanas"],
    ["03", "Objetivos"],
    ["04", "Preguntas"],
    ["05", "Completar"]
  ];

  $("timeline").innerHTML = steps.map(s => `
    <div class="timeline-step active">
      <small>${s[0]}</small>
      <strong>${s[1]}</strong>
    </div>
  `).join("");
}

function renderInitialNote() {
  const results = state.data.results || {};
  const note = results.initial_note || {};
  const root = note.initial_note || note.conceptual_interpretation || note;

  const title = root.title || "Lectura inicial";
  const summary = root.summary || root.initial_reading || root.interpretation || root.conceptual_reading || root.note || "";
  const reformulation = root.reformulation || root.reformulated_title || root.reformulated_project || "";
  const routes = root.routes || root.possible_routes || root.research_routes || [];

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
        ${routes.slice(0,4).map(r => `
          <div class="result-card">
            <strong>${escapeHtml(r.title || r.route || "Ruta posible")}</strong>
            <p>${escapeHtml(r.description || r.note || r)}</p>
          </div>
        `).join("")}
      </div>
    ` : ""}
  `;
}

function renderSemantic() {
  const ctx = state.data.context || {};
  const semantic = ctx.semantic_position || {};
  const keywords = ctx.keywords_detected || [];

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
        <p>${escapeHtml(semantic.main_cluster_label || semantic.main_cluster || "Cluster semántico cercano")}</p>
      </div>

      <div class="result-card">
        <strong>Área dominante</strong>
        <p>${escapeHtml(semantic.main_area || semantic.area || "No especificada")}</p>
      </div>
    </div>

    <div class="pill-row">
      ${keywords.slice(0,12).map(k => `
        <span class="pill">${escapeHtml(k.keyword || k)}</span>
      `).join("")}
    </div>
  `;
}

function renderTheses() {
  const results = state.data.results || {};
  const rerank = results.rerank || {};
  const ctx = state.data.context || {};

  const rr = rerank.reranked_theses || rerank.thesis_recommendations || rerank;
  const theses = rr.items || rr.theses || ctx.top_similar_theses || [];

  $("moduleTheses").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Tesis afines</p>
        <h2>Tesis más útiles para tu proyecto</h2>
      </div>
    </div>

    <div class="card-grid">
      ${theses.slice(0, 8).map((t, i) => `
        <article class="thesis-card">
          <div class="thesis-top">
            <span class="pill">#${t.rank || i + 1}</span>
          </div>
          <h3>${escapeHtml(t.title || t.thesis_title || "Tesis sin título")}</h3>
          <p class="meta">
            ${escapeHtml([t.year, t.program, t.degree, t.plantel].filter(Boolean).join(" · "))}
          </p>
          ${t.reason ? `<p>${escapeHtml(t.reason)}</p>` : ""}
        </article>
      `).join("")}
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
          ${revised.map(o => `<li>${escapeHtml(o)}</li>`).join("")}
        </ol>
      </div>
    ` : ""}

    ${analysis.final_note ? `<p class="meta">${escapeHtml(analysis.final_note)}</p>` : ""}
  `;
}

function renderQuestions() {
  const q = (state.data.results || {}).questions || {};
  const root = q.research_questions || q.questions || q;
  const items = root.items || root.questions || [];

  $("moduleQuestions").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Preguntas</p>
        <h2>${escapeHtml(root.title || "Preguntas de investigación")}</h2>
      </div>
    </div>

    <div class="card-grid">
      ${items.map((item, i) => `
        <details class="question-card" ${i === 0 ? "open" : ""}>
          <summary>
            <strong>${escapeHtml(item.type || item.question_type || "Pregunta")}</strong>
            ${escapeHtml(item.question || item.text || item)}
          </summary>
          ${item.methodological_angle ? `<p class="meta">Método: ${escapeHtml(item.methodological_angle)}</p>` : ""}
          ${item.why_it_matters ? `<p>${escapeHtml(item.why_it_matters)}</p>` : ""}
        </details>
      `).join("")}
    </div>
  `;
}

function renderBibliography() {
  const bib = (state.data.results || {}).bibliography;

  if (!bib) return;

  const br = bib.bibliography_recommendations || bib;
  const items = br.items || [];

  $("moduleBibliography").classList.remove("hidden");
  $("moduleBibliography").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Bibliografía</p>
        <h2>${escapeHtml(br.title || "Bibliografía recomendada")}</h2>
      </div>
    </div>

    <div class="card-grid">
      ${items.map(item => `
        <article class="bib-card">
          <strong>${item.rank}. ${escapeHtml(item.title || item.clean_title || "Fuente sin título")}</strong>
          <p class="source-line">Extraído de la tesis: ${escapeHtml(item.source_thesis_title || "No disponible")}</p>
        </article>
      `).join("")}
    </div>

    ${br.coverage_note ? `<p class="meta">Nota: ${escapeHtml(br.coverage_note)}</p>` : ""}
    ${br.missing_bibliography_warning ? `<p class="meta">Vacío: ${escapeHtml(br.missing_bibliography_warning)}</p>` : ""}
  `;
}

function renderAdvisors() {
  const adv = (state.data.results || {}).advisors;

  if (!adv) return;

  const ar = adv.advisor_recommendations || adv;
  const items = ar.items || [];

  $("moduleAdvisors").classList.remove("hidden");
  $("moduleAdvisors").innerHTML = `
    <div class="module-head">
      <div>
        <p class="eyebrow">Asesores</p>
        <h2>${escapeHtml(ar.title || "Asesores relacionados")}</h2>
      </div>
    </div>

    <div class="card-grid">
      ${items.map(item => `
        <article class="advisor-card">
          <strong>${item.rank}. ${escapeHtml(item.advisor_name || item.name || item.advisor_id)}</strong>
          <div class="pill-row">
            ${(item.programs || []).map(p => `<span class="pill">${escapeHtml(p)}</span>`).join("")}
            ${item.last_year ? `<span class="pill">Último año: ${item.last_year}</span>` : ""}
          </div>
          ${(item.representative_titles || []).slice(0,2).map(t => `
            <p class="source-line">Tesis relacionada: ${escapeHtml(t)}</p>
          `).join("")}
        </article>
      `).join("")}
    </div>

    ${ar.disclaimer ? `<p class="meta">${escapeHtml(ar.disclaimer)}</p>` : ""}
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
  $("emptyState").classList.remove("hidden");
  $("emptyState").innerHTML = `
    <div class="error-box">
      <strong>No se pudo generar el laboratorio.</strong>
      <p>${escapeHtml(err.message || String(err))}</p>
    </div>
  `;
}

function renderModuleError(moduleId, err) {
  const el = $(moduleId);
  el.classList.remove("hidden");
  el.innerHTML = `
    <div class="error-box">
      <strong>Error recuperable</strong>
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
