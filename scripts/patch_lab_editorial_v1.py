from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

if len(sys.argv) > 1:
    HTML_FILE = Path(sys.argv[1])
else:
    HTML_FILE = Path("static/index.html") if Path("static/index.html").exists() else Path("index.html")

if len(sys.argv) > 2:
    JS_FILE = Path(sys.argv[2])
else:
    JS_FILE = Path("static/app.js") if Path("static/app.js").exists() else Path("app.js")

if not HTML_FILE.exists():
    raise SystemExit(
        f"❌ No encontré HTML: {HTML_FILE}\n"
        f"   Busca en 'static/index.html' o pásalo como argumento: python scripts/patch_lab_editorial_v1.py static/index.html static/app.js"
    )

if not JS_FILE.exists():
    raise SystemExit(
        f"❌ No encontré app.js: {JS_FILE}\n"
        f"   Busca en 'static/app.js' o pásalo como argumento: python scripts/patch_lab_editorial_v1.py static/index.html static/app.js"
    )

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup_dir = Path("backups") / f"lab-editorial-v1-{stamp}"
backup_dir.mkdir(parents=True, exist_ok=True)

shutil.copy2(HTML_FILE, backup_dir / HTML_FILE.name)
shutil.copy2(JS_FILE, backup_dir / JS_FILE.name)

print(f"✅ Backup creado en: {backup_dir}")

html = HTML_FILE.read_text(encoding="utf-8")
js = JS_FILE.read_text(encoding="utf-8")

css_patch = r"""
/* ============================================================
   NODO UNAM · LAB EDITORIAL PATCH V1
   Archivo vivo + laboratorio intelectual
   Scope: solo .lab-page
   ============================================================ */

.lab-page {
  --lab-bg: #f5f1e8;
  --lab-paper: #fffdf8;
  --lab-paper-soft: #f9f5ed;
  --lab-ink: #171717;
  --lab-muted: #68655f;
  --lab-faint: #928d83;
  --lab-line: rgba(30, 28, 24, 0.13);
  --lab-line-soft: rgba(30, 28, 24, 0.075);
  --lab-blue: #123f86;
  --lab-blue-deep: #06111f;
  --lab-wine: #6f213b;
  --lab-gold: #b79a57;

  min-height: 100vh;
  height: 100vh;
  overflow: auto;
  color: var(--lab-ink);
  background:
    linear-gradient(90deg, rgba(6,17,31,0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(6,17,31,0.035) 1px, transparent 1px),
    radial-gradient(circle at 14% 10%, rgba(18, 63, 134, 0.09), transparent 30%),
    radial-gradient(circle at 88% 12%, rgba(111, 33, 59, 0.055), transparent 28%),
    linear-gradient(180deg, #fffdf8 0%, var(--lab-bg) 100%);
  background-size:
    42px 42px,
    42px 42px,
    auto,
    auto,
    auto;
  padding: 118px clamp(22px, 5vw, 74px) 92px;
}

.lab-inner {
  width: min(1220px, 100%);
  margin: 0 auto;
}

.lab-intro {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: clamp(28px, 5vw, 72px);
  align-items: end;
  margin-bottom: clamp(36px, 5vw, 76px);
  padding-bottom: clamp(28px, 4vw, 48px);
  border-bottom: 1px solid var(--lab-line);
}

.lab-intro::before {
  content: "LABORATORIO / ARCHIVO SEMÁNTICO";
  position: absolute;
  top: -28px;
  left: 0;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  letter-spacing: 0.14em;
  font-size: 10px;
  color: var(--lab-faint);
}

.lab-title {
  max-width: 760px;
  margin: 0;
  font-family: "Cormorant", Georgia, serif;
  font-size: clamp(58px, 8vw, 118px);
  line-height: 0.82;
  letter-spacing: 0.018em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--lab-ink);
}

.lab-intro p {
  max-width: 560px;
  margin: 0;
  font-size: 14px;
  line-height: 1.85;
  letter-spacing: 0.012em;
  text-transform: none;
  color: var(--lab-muted);
}

.lab-page .eyebrow,
.lab-page .meta,
.lab-page .source-line,
.lab-page .lab-mini-label,
.lab-page .lab-field label {
  color: var(--lab-faint);
}

.lab-page .eyebrow,
.lab-mini-label,
.lab-field label {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.13em;
  font-size: 10px;
  font-weight: 400;
}

.lab-form {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
  gap: 26px 24px;
  padding: clamp(26px, 4vw, 46px);
  border: 1px solid var(--lab-line);
  background:
    linear-gradient(180deg, rgba(255,253,248,0.96), rgba(249,245,237,0.92));
  box-shadow: none;
}

.lab-form::before {
  content: "Describe una idea, no llenes un trámite.";
  position: absolute;
  right: 28px;
  top: -11px;
  padding: 0 10px;
  background: var(--lab-bg);
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  letter-spacing: 0.11em;
  text-transform: uppercase;
  font-size: 9px;
  color: var(--lab-faint);
}

.lab-field {
  display: grid;
  gap: 9px;
}

.lab-field:first-child,
.lab-field:nth-child(2),
.lab-field:has(textarea) {
  grid-column: span 2;
}

.lab-field input,
.lab-field textarea,
.lab-field select {
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--lab-line);
  background: transparent;
  color: var(--lab-ink);
  outline: 0;
  padding: 13px 2px 12px;
  font-family: "Montserrat", system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.55;
  box-shadow: none;
}

.lab-field textarea {
  min-height: 108px;
  resize: vertical;
}

.lab-field input:focus,
.lab-field textarea:focus,
.lab-field select:focus {
  border-color: var(--lab-blue);
  box-shadow: 0 6px 0 -5px rgba(18, 63, 134, 0.55);
}

.lab-compact-grid {
  grid-column: span 2;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.lab-chip-editor,
.lab-period,
.bloom-preview {
  padding: 20px;
  border: 1px solid var(--lab-line-soft);
  background: rgba(255, 253, 248, 0.54);
}

.lab-inline-control {
  display: flex;
  gap: 10px;
}

.lab-icon-btn,
.lab-primary-btn,
.lab-secondary-btn {
  min-height: 42px;
  border: 1px solid var(--lab-blue-deep);
  background: transparent;
  color: var(--lab-blue-deep);
  padding: 0 16px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 10px;
  font-weight: 400;
  cursor: pointer;
  transition: background 140ms ease, color 140ms ease, border-color 140ms ease;
}

.lab-primary-btn {
  justify-self: start;
  min-width: 220px;
  background: var(--lab-blue-deep);
  color: #fffdf8;
}

.lab-primary-btn:hover {
  background: var(--lab-blue);
  border-color: var(--lab-blue);
}

.lab-primary-btn:disabled {
  cursor: wait;
  opacity: 0.58;
}

.lab-secondary-btn:hover,
.lab-icon-btn:hover {
  background: var(--lab-blue-deep);
  color: #fffdf8;
}

.chip,
.pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 29px;
  padding: 6px 10px;
  border: 1px solid var(--lab-line);
  border-radius: 999px;
  background: rgba(255,253,248,0.64);
  color: #383631;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.085em;
  font-size: 9px;
  font-weight: 400;
}

.chip small {
  color: var(--lab-blue);
  font-weight: 700;
}

.remove {
  cursor: pointer;
  color: var(--lab-wine);
  font-weight: 800;
}

.bloom-preview {
  grid-column: span 2;
}

.bloom-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 34px;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid var(--lab-line-soft);
  text-transform: none;
  letter-spacing: 0;
  font-size: 13px;
  font-weight: 600;
}

.bloom-row small {
  display: block;
  margin-top: 4px;
  color: var(--lab-muted);
  font-weight: 400;
  line-height: 1.5;
}

.bloom-count {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--lab-blue-deep);
  color: #fffdf8;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10px;
}

.verb-popup {
  padding: 22px;
  border: 1px solid var(--lab-line);
  background: #fffdf8;
  box-shadow: none;
}

.verb-section h4 {
  margin: 0 0 10px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 10px;
  color: var(--lab-faint);
}

.verb-chip {
  border: 1px solid var(--lab-line);
  border-radius: 999px;
  background: transparent;
  padding: 7px 10px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 9px;
  cursor: pointer;
}

.lab-status {
  margin-top: clamp(38px, 5vw, 72px);
  padding: clamp(30px, 5vw, 58px);
  border: 1px solid var(--lab-line);
  background:
    linear-gradient(180deg, rgba(255,253,248,0.78), rgba(249,245,237,0.68));
  box-shadow: none;
}

.lab-status h2 {
  margin: 0 0 14px;
  max-width: 720px;
  font-family: "Cormorant", Georgia, serif;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  font-size: clamp(34px, 4.4vw, 64px);
  line-height: 0.94;
  color: var(--lab-ink);
}

.lab-status p:not(.eyebrow) {
  max-width: 720px;
  font-size: 14px;
  line-height: 1.8;
  text-transform: none;
  letter-spacing: 0.01em;
  color: var(--lab-muted);
}

.lab-results {
  margin-top: clamp(42px, 6vw, 88px);
}

.timeline {
  position: sticky;
  top: 74px;
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  margin: 0 0 34px;
  padding: 10px 0;
  border-top: 1px solid var(--lab-line);
  border-bottom: 1px solid var(--lab-line);
  background: rgba(245, 241, 232, 0.88);
  backdrop-filter: blur(16px);
}

.timeline-step {
  display: grid;
  gap: 3px;
  min-width: 145px;
  padding: 8px 18px 8px 0;
  margin-right: 22px;
  border-right: 1px solid var(--lab-line-soft);
}

.timeline-step small {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  color: var(--lab-faint);
  font-size: 9px;
  letter-spacing: 0.12em;
}

.timeline-step strong {
  font-family: "Cormorant", Georgia, serif;
  text-transform: uppercase;
  letter-spacing: 0.045em;
  font-size: 19px;
  line-height: 1;
  color: var(--lab-ink);
}

.lab-module {
  position: relative;
  margin: 0 0 clamp(34px, 5vw, 68px);
  padding: clamp(30px, 5vw, 58px);
  border: 1px solid var(--lab-line);
  background: rgba(255, 253, 248, 0.72);
  box-shadow: none;
}

.lab-module::before {
  content: "";
  position: absolute;
  left: -1px;
  top: -1px;
  bottom: -1px;
  width: 4px;
  background: linear-gradient(180deg, var(--lab-blue), rgba(18,63,134,0.08));
  opacity: 0.85;
}

.module-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.module-head h2,
.lab-module h2 {
  margin: 0;
  max-width: 820px;
  font-family: "Cormorant", Georgia, serif;
  text-transform: uppercase;
  letter-spacing: 0.032em;
  font-size: clamp(36px, 4.8vw, 68px);
  line-height: 0.92;
  color: var(--lab-ink);
}

.lab-module h3 {
  margin: 0 0 12px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 10px;
  font-weight: 400;
  color: var(--lab-blue);
}

.lab-module p {
  max-width: 820px;
  margin: 0 0 16px;
  font-size: 14px;
  line-height: 1.82;
  text-transform: none;
  letter-spacing: 0.006em;
  color: var(--lab-muted);
}

.initial-reading-intro {
  max-width: 760px;
  font-size: 17px !important;
  line-height: 1.78 !important;
  color: #2f2d29 !important;
}

.initial-reading-sequence {
  display: grid;
  gap: 18px;
  margin-top: 30px;
}

.initial-reading-block {
  opacity: 1;
  transform: none;
  padding: 22px 0 6px;
  border-top: 1px solid var(--lab-line);
}

.initial-reading-block.visible {
  opacity: 1;
}

.initial-reading-block p,
.initial-scope-lines p,
.initial-cautions li {
  max-width: 820px;
  color: #37342f;
  font-size: 15px;
  line-height: 1.78;
}

.initial-cautions {
  margin: 0;
  padding-left: 20px;
}

.initial-cautions li + li {
  margin-top: 8px;
}

.location-intro,
.bloom-intro {
  font-size: 15px !important;
  line-height: 1.82 !important;
}

.location-summary-line {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  margin: 28px 0 26px;
  border: 1px solid var(--lab-line);
  background: var(--lab-line);
}

.location-summary-line p {
  margin: 0;
  padding: 16px;
  background: rgba(255,253,248,0.84);
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.075em;
  font-size: 10px;
  line-height: 1.55;
}

.lab-atlas-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin: 28px 0 16px;
  padding: 14px 0;
  border-top: 1px solid var(--lab-line);
  border-bottom: 1px solid var(--lab-line);
}

.lab-atlas-mode-group {
  display: inline-flex;
  gap: 6px;
}

.lab-atlas-mode-btn,
.lab-atlas-control select {
  min-height: 34px;
  border: 1px solid var(--lab-line);
  background: transparent;
  color: var(--lab-ink);
  padding: 0 11px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 9px;
  cursor: pointer;
}

.lab-atlas-mode-btn.active {
  background: var(--lab-blue-deep);
  border-color: var(--lab-blue-deep);
  color: #fffdf8;
}

.lab-atlas-current-view span,
.lab-atlas-control {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 9px;
  color: var(--lab-faint);
}

.lab-atlas-sigma-shell {
  position: relative;
  min-height: clamp(420px, 62vh, 680px);
  border: 1px solid rgba(170, 205, 240, 0.20);
  background:
    radial-gradient(circle at 50% 42%, rgba(18, 63, 134, 0.38), rgba(6, 17, 31, 0.96) 58%, #06111f 100%);
  overflow: hidden;
}

.lab-atlas-sigma-shell::after {
  content: "Cada punto es una tesis cercana. La posición sugiere vecindad semántica, no jerarquía académica.";
  position: absolute;
  left: 18px;
  bottom: 16px;
  max-width: 440px;
  color: rgba(234,244,255,0.62);
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 9px;
  line-height: 1.55;
  pointer-events: none;
}

.lab-atlas-overlay {
  position: absolute;
  z-index: 3;
  left: 18px;
  top: 18px;
  pointer-events: none;
}

.lab-atlas-overlay-card {
  padding: 13px 15px;
  border: 1px solid rgba(234,244,255,0.20);
  background: rgba(6,17,31,0.68);
  backdrop-filter: blur(12px);
}

.lab-atlas-overlay-card span {
  display: block;
  margin-bottom: 5px;
  color: rgba(234,244,255,0.62);
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.11em;
  font-size: 9px;
}

.lab-atlas-overlay-card strong {
  display: block;
  max-width: 320px;
  color: #eaf4ff;
  font-family: "Cormorant", Georgia, serif;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 24px;
  line-height: 0.98;
}

.lab-atlas-sigma {
  position: absolute;
  inset: 0;
}

.lab-atlas-detail {
  margin-top: 16px;
  padding: 20px;
  border: 1px solid var(--lab-line);
  background: rgba(255,253,248,0.58);
}

.lab-atlas-detail strong {
  display: block;
  margin-bottom: 8px;
  font-family: "Cormorant", Georgia, serif;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 30px;
  line-height: 1;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  border: 1px solid var(--lab-line);
  background: var(--lab-line);
}

.thesis-card {
  min-height: 230px;
  padding: 24px;
  background: rgba(255,253,248,0.86);
}

.thesis-top {
  margin-bottom: 18px;
}

.thesis-card h3 {
  margin: 0 0 14px;
  font-family: "Cormorant", Georgia, serif;
  text-transform: uppercase;
  letter-spacing: 0.035em;
  font-size: 28px;
  line-height: 0.98;
  color: var(--lab-ink);
}

.thesis-card .meta {
  margin-bottom: 14px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 9px;
  line-height: 1.55;
  color: var(--lab-faint);
}

.bloom-reading {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 30px 0;
  border: 1px solid var(--lab-line);
  background: var(--lab-line);
}

.bloom-reading section {
  padding: 22px;
  background: rgba(255,253,248,0.82);
}

.bloom-section {
  margin-top: 30px;
  padding-top: 24px;
  border-top: 1px solid var(--lab-line);
}

.bloom-objective-list {
  display: grid;
  gap: 14px;
}

.bloom-objective-item {
  padding: 20px;
  border: 1px solid var(--lab-line-soft);
  background: rgba(255,253,248,0.58);
}

.bloom-objective-topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 9px;
  color: var(--lab-faint);
}

.bloom-original {
  color: #302e2a !important;
}

.question-card,
.advisor-card {
  padding: 24px;
  border: 1px solid var(--lab-line);
  background: rgba(255,253,248,0.76);
}

.question-card h3,
.advisor-card h3 {
  font-family: "Cormorant", Georgia, serif;
  text-transform: uppercase;
  letter-spacing: 0.035em;
  font-size: 30px;
  line-height: 1;
  color: var(--lab-ink);
}

.advisor-card .score,
.score {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  color: var(--lab-faint);
}

.debug-panel {
  margin-top: 24px;
  padding: 20px;
  border: 1px solid var(--lab-line);
  background: #111;
  color: #e7e7e7;
  overflow: auto;
  font-size: 11px;
}

.hidden {
  display: none !important;
}

@media (max-width: 980px) {
  .lab-intro,
  .lab-form,
  .lab-compact-grid {
    grid-template-columns: 1fr;
  }

  .lab-field:first-child,
  .lab-field:nth-child(2),
  .lab-field:has(textarea),
  .bloom-preview {
    grid-column: auto;
  }

  .location-summary-line,
  .bloom-reading,
  .card-grid {
    grid-template-columns: 1fr;
  }

  .timeline {
    position: relative;
    top: auto;
  }

  .lab-atlas-sigma-shell {
    min-height: 420px;
  }
}

@media (max-width: 640px) {
  .lab-page {
    padding: 96px 18px 70px;
  }

  .lab-title {
    font-size: 54px;
  }

  .lab-module,
  .lab-form,
  .lab-status {
    padding: 24px;
  }

  .module-head h2,
  .lab-module h2 {
    font-size: 38px;
  }

  .timeline-step {
    min-width: 120px;
    margin-right: 12px;
  }
}
"""

start_marker = "/* ============================================================\n   NODO UNAM · LAB EDITORIAL PATCH V1"
end_marker = "/* END NODO LAB EDITORIAL PATCH V1 */"

css_patch = css_patch.strip() + "\n" + end_marker + "\n"

# Remove previous version if present
html = re.sub(
    r"/\* ============================================================\n   NODO UNAM · LAB EDITORIAL PATCH V1.*?/\* END NODO LAB EDITORIAL PATCH V1 \*/\n?",
    "",
    html,
    flags=re.S
)

if "</style>" not in html:
    raise SystemExit("❌ No encontré </style> en el HTML. No inyecté CSS.")

html = html.replace("</style>", css_patch + "\n  </style>", 1)

# ---------- JS PATCHES ----------

# 1) Add helper to reveal initial reading without typewriter.
helper = r"""
/* NODO LAB EDITORIAL PATCH V1 — JS helpers */
function revealInitialReadingImmediately() {
  const container = $("initialReadingSequence");
  if (!container) return;

  const steps = Array.from(container.querySelectorAll("[data-initial-step]"));
  steps.forEach(step => {
    step.classList.add("visible");
    const targets = Array.from(step.querySelectorAll("[data-typewriter]"));
    targets.forEach(target => {
      if (target.dataset.fullText) {
        target.textContent = target.dataset.fullText;
      }
      target.classList.remove("typing");
    });
  });
}
/* END NODO LAB EDITORIAL PATCH V1 — JS helpers */
"""

js = re.sub(
    r"/\* NODO LAB EDITORIAL PATCH V1 — JS helpers \*/.*?/\* END NODO LAB EDITORIAL PATCH V1 — JS helpers \*/\n?",
    "",
    js,
    flags=re.S
)

insert_after = """function $(id) {
  return document.getElementById(id);
}
"""

if insert_after in js:
    js = js.replace(insert_after, insert_after + "\n" + helper + "\n", 1)
else:
    print("⚠️ No encontré function $(id). No inserté helper JS.")

# 2) Replace typewriter call with immediate reveal.
js = js.replace("    animateInitialReading();", "    revealInitialReadingImmediately();")

# 3) Timeline as editorial chapters.
timeline_old = '''  const steps = [
    ["01", "Lectura inicial"],
    ["02", "Ubicación en UNAM"],
    ["03", "Tesis cercanas"],
    ["04", "Objetivos"],
    ["05", "Preguntas"],
    ["06", "Asesores"]
  ];'''

timeline_new = '''  const steps = [
    ["I", "Lectura"],
    ["II", "Cartografía"],
    ["III", "Conversaciones"],
    ["IV", "Andamiaje"],
    ["V", "Preguntas"],
    ["VI", "Interlocutores"]
  ];'''

if timeline_old in js:
    js = js.replace(timeline_old, timeline_new, 1)
else:
    print("⚠️ No encontré bloque exacto de timeline. Lo dejé intacto.")

# 4) Safer copy changes. No dynamic fields touched.
copy_replacements = {
    "Lectura inicial": "Lectura del proyecto",
    "Comprendí tu tesis así": "Una primera lectura de tu proyecto",
    "Ubicación en UNAM": "Cartografía semántica",
    "Aquí se encuentra tu tesis": "Tu proyecto dentro del archivo UNAM",
    "Tesis afines": "Conversaciones cercanas",
    "Tesis más útiles para tu proyecto": "Tesis que dialogan con tu proyecto",
    "Objetivos Bloom": "Andamiaje intelectual",
    "Tus objetivos, analizados": "Cómo piensa tu proyecto",
    "El laboratorio revisó tus objetivos como una progresión cognitiva: qué operaciones intelectuales ya aparecen,\n      dónde hay saltos y qué nivel conviene reforzar.": "El laboratorio leyó tus objetivos como una arquitectura de pensamiento: qué operaciones intelectuales ya están presentes, qué pasos faltan y dónde puede ganar profundidad tu investigación.",
    "Preguntas": "Preguntas de investigación",
    "Asesores": "Interlocutores académicos",
    "Selecciona una tesis del mapa": "Selecciona un punto del mapa",
    "Explora la evidencia": "Explora la conversación",
    "En modo universo verás la ubicación narrativa; en modo analítico verás cómo se compone el vecindario cercano.": "El mapa muestra el vecindario semántico que sostiene esta lectura. Cada punto abre una posible relación académica.",
    "Top ${escapeHtml(String(topCount))} tesis cercanas": "${escapeHtml(String(topCount))} tesis cercanas",
    "Territorio inferido": "Territorio semántico",
    "Salida": "Lectura",
    "El análisis aparecerá aquí": "Aquí aparecerá tu laboratorio",
    "Después de enviar el formulario, verás la lectura inicial, tesis afines, objetivos, preguntas y asesores en una sola secuencia.": "Después de enviar tu idea, NODO la leerá como proyecto académico: primero la interpreta, luego la ubica en el archivo UNAM y finalmente abre conversaciones, preguntas e interlocutores posibles."
}

for old, new in copy_replacements.items():
    js = js.replace(old, new)

# 5) Make loading language less AI-demo and more archival.
loading_old = '''const loadingSteps = [
  ["Analizando tu idea", "Interpretando núcleo temático."],
  ["Ubicando tesis similares", "Buscando afinidades semánticas."],
  ["Reordenando antecedentes", "Priorizando tesis útiles para tu proyecto."],
  ["Analizando objetivos", "Leyendo progresión cognitiva."],
  ["Formulando preguntas", "Construyendo rutas de investigación."],
  ["Buscando asesores", "Ordenando afinidades temáticas e históricas."],
  ["Preparando salida", "Consolidando el análisis completo."]
];'''

loading_new = '''const loadingSteps = [
  ["Leyendo tu proyecto", "Identificando problema, objetos y alcance."],
  ["Abriendo el archivo UNAM", "Buscando vecindades semánticas entre tesis."],
  ["Trazando conversaciones", "Ordenando antecedentes cercanos por utilidad académica."],
  ["Revisando objetivos", "Reconociendo la arquitectura intelectual del proyecto."],
  ["Formulando rutas", "Construyendo preguntas posibles de investigación."],
  ["Buscando interlocutores", "Detectando trayectorias académicas relacionadas."],
  ["Cerrando la lectura", "Preparando una salida legible y navegable."]
];'''

if loading_old in js:
    js = js.replace(loading_old, loading_new, 1)
else:
    print("⚠️ No encontré loadingSteps exacto. Lo dejé intacto.")

HTML_FILE.write_text(html, encoding="utf-8")
JS_FILE.write_text(js, encoding="utf-8")

print("✅ Patch aplicado.")
print(f"   HTML modificado: {HTML_FILE}")
print(f"   JS modificado:   {JS_FILE}")
print("")
print("Para revertir:")
print(f"cp {backup_dir / HTML_FILE.name} {HTML_FILE}")
print(f"cp {backup_dir / JS_FILE.name} {JS_FILE}")
