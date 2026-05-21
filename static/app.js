const $ = (id) => document.getElementById(id);

let currentData = null;
let currentProjectId = null;

function getObjectives() {
  return $("objectives").value
    .split("\n")
    .map(x => x.trim())
    .filter(Boolean);
}

function getKeywords() {
  return $("keywords").value
    .split(",")
    .map(x => x.trim())
    .filter(Boolean);
}

function getPayload() {
  const start = $("start_year").value;
  const end = $("end_year").value;

  return {
    title: $("title").value.trim(),
    keywords: getKeywords(),
    objectives: getObjectives(),
    program: $("program").value.trim(),
    degree: $("degree").value.trim(),
    plantel: $("plantel").value.trim(),
    study_period: {
      applies: Boolean(start || end),
      start_year: start ? Number(start) : null,
      end_year: end ? Number(end) : null,
      label: start && end ? `${start}-${end}` : ""
    }
  };
}

function setLoading(msg) {
  $("status").textContent = msg;
  $("runBtn").disabled = true;
}

function stopLoading() {
  $("runBtn").disabled = false;
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const text = await res.text();

  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(
      `Respuesta no JSON desde ${url}. Status ${res.status}. Body: ${text.slice(0, 240)}`
    );
  }

  if (!res.ok || data?.ok === false) {
    throw new Error(data?.detail || data?.message || `Error HTTP ${res.status}`);
  }

  return data;
}

async function runLab() {
  try {
    setLoading("Recibimos tu petición…");

    const payload = getPayload();

    setLoading("Ubicando tu tesis en el mapa semántico UNAM…");
    const basic = await postJSON("/api/lab/run-basic", payload);

    currentData = basic.data;
    currentProjectId = currentData.project_id;

    setLoading("Listo.");
    render(currentData);
  } catch (err) {
    $("status").textContent = `Error: ${err.message}`;
    console.error(err);
  } finally {
    stopLoading();
  }
}

async function completeLab() {
  if (!currentProjectId) return;

  closeUpgradeModal();

  try {
    setLoading("Buscando asesores relacionados…");

    const advisors = await postJSON("/api/lab/run-advisors", {
      project_id: currentProjectId,
    });

    currentData = advisors.data;

    render(currentData);

    setLoading("Revisando bibliografía relacionada…");

    const bibliography = await postJSON("/api/lab/run-bibliography", {
      project_id: currentProjectId,
    });

    currentData = bibliography.data;

    setLoading("Laboratorio completo.");
    render(currentData);
  } catch (err) {
    $("status").textContent = `Error: ${err.message}`;
    console.error(err);
  } finally {
    stopLoading();
  }
}

function render(data) {
  const root = $("results");
  const ctx = data.context || {};
  const results = data.results || {};

  currentProjectId = data.project_id;

  root.innerHTML = `
    <section class="card">
      <p class="eyebrow">Proyecto</p>
      <h2>${escapeHTML(data.input?.title || "Sin título")}</h2>
      <p><strong>Programa:</strong> ${escapeHTML(data.input?.program || "—")}</p>
      <p><strong>Periodo:</strong> ${escapeHTML(data.input?.study_period?.label || "—")}</p>
    </section>

    ${renderInitialNote(results.initial_note)}
    ${renderSemanticPosition(ctx)}
    ${renderRerank(results.rerank)}
    ${renderBloom(results.bloom)}
    ${renderQuestions(results.questions)}
    ${renderUpgradeCTA(results)}
    ${renderAdvisors(results.advisors, ctx)}
    ${renderBibliography(results.bibliography, ctx)}
    ${renderDebug(data.debug)}
    ${renderUpgradeModal()}
  `;
}

function renderInitialNote(data) {
  const note = data?.initial_note;
  if (!note) return "";

  return `
    <section class="card">
      <p class="eyebrow">Lectura inicial</p>
      <h2>${escapeHTML(note.title)}</h2>
      <p>${escapeHTML(note.paragraph)}</p>
      <p class="note">${escapeHTML(note.scope_note || "")}</p>

      <h3>Ángulos posibles</h3>
      <div class="grid">
        ${(note.possible_angles || []).map(a => `
          <div class="mini-card">
            <strong>${escapeHTML(a.title)}</strong>
            <p>${escapeHTML(a.description)}</p>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function renderSemanticPosition(ctx) {
  const main = ctx.semantic_position?.main_cluster;
  const top = ctx.top_similar_theses || [];

  return `
    <section class="card">
      <p class="eyebrow">Ubicación semántica</p>
      <h2>${escapeHTML(main?.label || "Sin cluster principal")}</h2>
      <p>El proyecto cae principalmente en ${escapeHTML(main?.macro_domain || "—")}.</p>

      <h3>Tesis cercanas</h3>
      <ol>
        ${top.slice(0, 8).map(t => `
          <li>
            <strong>${escapeHTML(t.title)}</strong>
            <br>
            <span>${escapeHTML(t.year || "s/f")} · ${escapeHTML(t.program || "—")} · similitud ${escapeHTML(t.similarity ?? "—")}</span>
          </li>
        `).join("")}
      </ol>
    </section>
  `;
}

function renderRerank(data) {
  const rr = data?.reranked_theses;
  if (!rr) return "";

  return `
    <section class="card">
      <p class="eyebrow">Tesis priorizadas</p>
      <h2>${escapeHTML(rr.title)}</h2>
      <ol>
        ${(rr.items || []).map(t => `
          <li>
            <strong>${escapeHTML(t.title)}</strong>
            <br>
            <span>${escapeHTML(t.year || "s/f")} · ${escapeHTML(t.program || "—")}</span>
          </li>
        `).join("")}
      </ol>
    </section>
  `;
}

function renderBloom(data) {
  const b = data?.bloom_analysis;
  if (!b) return "";

  return `
    <section class="card">
      <p class="eyebrow">Objetivos</p>
      <h2>${escapeHTML(b.title)}</h2>
      <p>${escapeHTML(b.cognitive_profile)}</p>
      <p class="warning">${escapeHTML(b.main_risk)}</p>

      <h3>Objetivos revisados</h3>
      <ol>
        ${(b.revised_objectives || []).map(o => `<li>${escapeHTML(o)}</li>`).join("")}
      </ol>
    </section>
  `;
}

function renderQuestions(data) {
  const q = data?.research_questions;
  if (!q) return "";

  return `
    <section class="card">
      <p class="eyebrow">Preguntas</p>
      <h2>${escapeHTML(q.title)}</h2>
      <div class="grid">
        ${(q.questions || []).map(item => `
          <div class="mini-card">
            <strong>${escapeHTML(item.type)}</strong>
            <p>${escapeHTML(item.question)}</p>
            <small>${escapeHTML(item.methodological_angle)}</small>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function renderUpgradeCTA(results) {
  const hasAdvisors = Boolean(results?.advisors);
  const hasBibliography = Boolean(results?.bibliography);

  if (hasAdvisors && hasBibliography) return "";

  return `
    <section class="card upgrade-card">
      <p class="eyebrow">Completa tu laboratorio</p>
      <h2>¿Quieres conocer bibliografía y asesores relacionados con tu tesis?</h2>
      <p>
        Podemos extender el análisis con bibliografía recomendada desde tesis cercanas
        y asesores vinculados históricamente con temas similares.
      </p>
      <button type="button" class="secondary-btn" onclick="openUpgradeModal()">
        Completar laboratorio
      </button>
    </section>
  `;
}

function renderUpgradeModal() {
  return `
    <div id="upgradeModal" class="modal-backdrop hidden">
      <div class="modal-card">
        <p class="eyebrow">Crear cuenta</p>
        <h2>Guarda tu laboratorio y desbloquea el análisis completo</h2>
        <p>
          Simulación MVP: en producción, este paso permitiría guardar tu proyecto,
          recuperar resultados y acceder a bibliografía y asesores bajo demanda.
        </p>

        <div class="modal-actions">
          <button type="button" onclick="completeLab()">
            Crear cuenta y continuar
          </button>
          <button type="button" class="ghost-btn" onclick="closeUpgradeModal()">
            Ahora no
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderAdvisors(data, ctx) {
  const a = data?.advisor_recommendations;
  if (!a) return "";

  const evidence = ctx.advisor_evidence || [];
  const byId = {};

  evidence.forEach((item, index) => {
    byId[`A${String(index + 1).padStart(2, "0")}`] = item;
  });

  return `
    <section class="card">
      <p class="eyebrow">Asesores</p>
      <h2>${escapeHTML(a.title)}</h2>
      <ol>
        ${(a.ordered_advisor_ids || []).map(id => {
          const ev = byId[id];
          return `
            <li>
              <strong>${escapeHTML(ev?.advisor_name || id)}</strong>
              <br>
              <span>${escapeHTML(ev?.programs?.join(", ") || "—")} · ${escapeHTML(ev?.last_year || "s/f")}</span>
              ${ev?.representative_titles?.length ? `
                <br><small>${escapeHTML(ev.representative_titles[0])}</small>
              ` : ""}
            </li>
          `;
        }).join("")}
      </ol>
      <p class="note">${escapeHTML(a.disclaimer || "")}</p>
    </section>
  `;
}

function renderBibliography(data, ctx) {
  const b = data?.bibliography_recommendations;

  if (!b) return "";

  const hasItems = Array.isArray(b.items) && b.items.length > 0;

  return `
    <section class="card">
      <p class="eyebrow">Bibliografía</p>
      <h2>${escapeHTML(b.title || "Bibliografía recomendada")}</h2>

      ${hasItems ? `
        <ol>
          ${b.items.map(x => `
            <li>
              <strong>${escapeHTML(x.title || x.bib_id || "Fuente")}</strong>
              <br>
              <span>${escapeHTML(x.source_thesis_title || "")}</span>
            </li>
          `).join("")}
        </ol>
      ` : `
        <p class="note">
          ${escapeHTML(
            b.missing_bibliography_warning ||
            "No hay bibliografía disponible para esta muestra."
          )}
        </p>
      `}

      ${b.coverage_note ? `<p class="note">${escapeHTML(b.coverage_note)}</p>` : ""}
    </section>
  `;
}

function renderDebug(debug) {
  const showDebug = $("showDebug")?.checked;
  if (!showDebug) return "";

  return `
    <section class="card">
      <p class="eyebrow">Debug</p>
      <pre>${escapeHTML(JSON.stringify(debug || [], null, 2))}</pre>
    </section>
  `;
}

function openUpgradeModal() {
  const modal = $("upgradeModal");
  if (modal) modal.classList.remove("hidden");
}

function closeUpgradeModal() {
  const modal = $("upgradeModal");
  if (modal) modal.classList.add("hidden");
}

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
  const form = $("labForm");
  const btn = $("runBtn");

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      e.stopPropagation();
      runLab();
      return false;
    });
  }

  if (btn) {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      runLab();
      return false;
    });
  }
});