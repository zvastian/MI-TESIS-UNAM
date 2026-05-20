from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from normalizers import normalize_module_output
from validators import validate_module_output


class LabBusyError(RuntimeError):
    pass


@dataclass
class StepResult:
    step: str
    ok: bool
    script: str | None = None
    duration_seconds: float = 0.0
    validation: str = "not_checked"
    error: str | None = None
    output_file: str | None = None


class LabOrchestrator:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.projects_dir = base_dir / "projects"
        self.outputs_dir = base_dir / "outputs"
        self.payloads_dir = base_dir / "payloads"

        self.projects_dir.mkdir(exist_ok=True)
        self.outputs_dir.mkdir(exist_ok=True)
        self.payloads_dir.mkdir(exist_ok=True)

        self._lock = threading.Lock()
        self.strict_scripts = os.getenv("LAB_STRICT_SCRIPTS", "0") == "1"

    def run_basic(self, lab_input: dict[str, Any]) -> dict[str, Any]:
        with self._exclusive():
            project_id = self._new_project_id()
            project_dir = self.projects_dir / project_id
            project_outputs = project_dir / "outputs"
            project_outputs.mkdir(parents=True, exist_ok=True)

            self._write_json(project_dir / "input.json", lab_input)
            self._write_json(self.payloads_dir / "input.json", lab_input)
            self._write_json(self.payloads_dir / "lab_input.json", lab_input)

            debug: list[StepResult] = []

            debug.append(self._run_script("context", "scripts/thesis.py"))
            self._persist_context(project_dir)

            debug.append(self._run_script("conceptual_payload", "payloads/build_conceptual_payload.py"))
            debug.append(self._run_script("initial_note", "scripts/ai_initial_note.py"))
            debug.append(self._normalize_validate_persist(
                module="initial_note",
                candidates=[self.outputs_dir / "ai_conceptual_interpretation.json"],
                destination=project_outputs / "initial_note.json",
            ))

            debug.append(self._run_script("rerank_payload", "payloads/build_rerank_payload.py"))
            debug.append(self._run_script("rerank", "scripts/ai_rerank.py"))
            debug.append(self._normalize_validate_persist(
                module="rerank",
                candidates=[self.outputs_dir / "ai_rerank_groq_llama.json"],
                destination=project_outputs / "rerank.json",
            ))

            debug.append(self._run_script("bloom_payload", "payloads/build_bloom_payload.py"))
            debug.append(self._run_script("bloom", "scripts/ai_bloom.py"))
            debug.append(self._normalize_validate_persist(
                module="bloom",
                candidates=[self.outputs_dir / "ai_bloom_groq_20b.json"],
                destination=project_outputs / "bloom.json",
            ))

            debug.append(self._run_script("questions_payload", "payloads/build_questions_payload.py"))
            debug.append(self._run_script("questions", "scripts/ai_questions.py"))
            debug.append(self._normalize_validate_persist(
                module="questions",
                candidates=[self.outputs_dir / "ai_questions_groq_20b.json"],
                destination=project_outputs / "questions.json",
            ))

            self._write_debug(project_outputs, debug)
            return self.consolidate_project(project_id)

    def run_bibliography(self, project_id: str) -> dict[str, Any]:
        with self._exclusive():
            project_dir = self._require_project(project_id)
            project_outputs = project_dir / "outputs"
            self._restore_project_context(project_dir)

            context = self._safe_read(project_dir / "context_minimal.json") or {}
            if not context.get("bibliography_summaries"):
                self._write_json(project_outputs / "bibliography.json", {
                    "bibliography_recommendations": {
                        "title": "Bibliografía recomendada",
                        "items": [],
                        "coverage_note": "",
                        "missing_bibliography_warning": "No hay bibliografía disponible para esta muestra."
                    }
                })
                return self.consolidate_project(project_id)

            debug: list[StepResult] = []

            debug.append(self._run_script("bibliography_payload", "payloads/build_bibliography_payload.py"))
            debug.append(self._run_script("bibliography", "scripts/ai_bibliography.py"))
            debug.append(self._normalize_validate_persist(
                module="bibliography",
                candidates=[self.outputs_dir / "ai_bibliography_groq_20b.json"],
                destination=project_outputs / "bibliography.json",
            ))

            self._append_debug(project_outputs, debug)
            return self.consolidate_project(project_id)

    def run_advisors(self, project_id: str) -> dict[str, Any]:
        with self._exclusive():
            project_dir = self._require_project(project_id)
            project_outputs = project_dir / "outputs"

            self._restore_project_context(project_dir)

            debug: list[StepResult] = []

            debug.append(self._run_script("advisors_payload", "payloads/build_advisors_payload.py"))
            debug.append(self._run_script("advisors", "scripts/ai_advisors.py"))
            debug.append(self._normalize_validate_persist(
                module="advisors",
                candidates=[self.outputs_dir / "ai_advisors.json"],
                destination=project_outputs / "advisors.json",
            ))

            self._append_debug(project_outputs, debug)
            return self.consolidate_project(project_id)

    def consolidate_project(self, project_id: str) -> dict[str, Any]:
        project_dir = self._require_project(project_id)
        out = project_dir / "outputs"

        return {
            "project_id": project_id,
            "input": self._safe_read(project_dir / "input.json"),
            "context": self._safe_read(project_dir / "context_minimal.json"),
            "results": {
                "initial_note": self._safe_read(out / "initial_note.json"),
                "rerank": self._safe_read(out / "rerank.json"),
                "bloom": self._safe_read(out / "bloom.json"),
                "questions": self._safe_read(out / "questions.json"),
                "bibliography": self._safe_read(out / "bibliography.json"),
                "advisors": self._safe_read(out / "advisors.json"),
            },
            "debug": self._safe_read(out / "debug.json") or [],
        }

    def _exclusive(self):
        orchestrator = self

        class Guard:
            def __enter__(self):
                acquired = orchestrator._lock.acquire(blocking=False)
                if not acquired:
                    raise LabBusyError("Ya hay un laboratorio en proceso. Espera a que termine.")
                return self

            def __exit__(self, exc_type, exc, tb):
                orchestrator._lock.release()

        return Guard()

    def _run_script(self, step: str, script_name: str) -> StepResult:
        script = self.base_dir / script_name
        started = time.time()

        if not script.exists():
            if self.strict_scripts:
                raise FileNotFoundError(f"No encontré el script requerido: {script_name}")
            return StepResult(
                step=step,
                ok=True,
                script=None,
                duration_seconds=round(time.time() - started, 3),
                validation="missing_script_skipped",
                error=f"Script no encontrado: {script_name}",
            )

        python_bin = self.base_dir / ".venv" / "bin" / "python"

        try:
            subprocess.run(
                [str(python_bin), str(script)],
                cwd=self.base_dir,
                check=True,
                timeout=480,
                env={
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONPATH": str(self.base_dir / "scripts"),
                },
            )

            return StepResult(
                step=step,
                ok=True,
                script=script_name,
                duration_seconds=round(time.time() - started, 3),
                validation="script_ok",
            )

        except subprocess.TimeoutExpired as exc:
            return StepResult(
                step=step,
                ok=False,
                script=script_name,
                duration_seconds=round(time.time() - started, 3),
                validation="script_timeout",
                error=f"Timeout: {exc}",
            )

        except subprocess.CalledProcessError as exc:
            return StepResult(
                step=step,
                ok=False,
                script=script_name,
                duration_seconds=round(time.time() - started, 3),
                validation="script_failed",
                error=f"Script failed with code {exc.returncode}",
            )

    def _normalize_validate_persist(
        self,
        module: str,
        candidates: list[Path],
        destination: Path,
    ) -> StepResult:
        started = time.time()
        source = self._first_existing(candidates)

        if source is None:
            msg = f"No encontré output para módulo {module}"
            if self.strict_scripts:
                raise FileNotFoundError(msg)
            return StepResult(
                step=f"{module}_persist",
                ok=False,
                duration_seconds=round(time.time() - started, 3),
                validation="missing_output",
                error=msg,
            )

        try:
            raw = self._read_json(source)
            normalized = normalize_module_output(module, raw)
            ok, msg = validate_module_output(module, normalized)

            destination.parent.mkdir(parents=True, exist_ok=True)

            if ok:
                self._write_json(destination, normalized)
                return StepResult(
                    step=f"{module}_persist",
                    ok=True,
                    duration_seconds=round(time.time() - started, 3),
                    validation="passed",
                    output_file=str(destination),
                )

            error_path = destination.with_suffix(".error.json")
            self._write_json(error_path, {
                "module": module,
                "validation": {"valid": False, "message": msg},
                "source": str(source),
                "raw": raw,
                "normalized": normalized,
            })

            return StepResult(
                step=f"{module}_persist",
                ok=False,
                duration_seconds=round(time.time() - started, 3),
                validation=f"failed: {msg}",
                error=f"Validation failed for {module}: {msg}",
                output_file=str(error_path),
            )

        except Exception as exc:
            error_path = destination.with_suffix(".exception.json")
            self._write_json(error_path, {
                "module": module,
                "source": str(source),
                "error": str(exc),
            })

            return StepResult(
                step=f"{module}_persist",
                ok=False,
                duration_seconds=round(time.time() - started, 3),
                validation="exception",
                error=str(exc),
                output_file=str(error_path),
            )

    def _persist_context(self, project_dir: Path) -> None:
        self._copy_first_existing(
            [
                self.payloads_dir / "context_minimal.json",
                self.payloads_dir / "thesis_context_example.json",
            ],
            project_dir / "context_minimal.json",
        )

    def _restore_project_context(self, project_dir: Path) -> None:
        context = project_dir / "context_minimal.json"
        if context.exists():
            shutil.copy2(context, self.payloads_dir / "context_minimal.json")

        input_file = project_dir / "input.json"
        if input_file.exists():
            shutil.copy2(input_file, self.payloads_dir / "input.json")
            shutil.copy2(input_file, self.payloads_dir / "lab_input.json")

    def _new_project_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"lab_{stamp}_{uuid.uuid4().hex[:8]}"

    def _require_project(self, project_id: str) -> Path:
        project_dir = self.projects_dir / project_id
        if not project_dir.exists():
            raise FileNotFoundError(f"No existe el proyecto {project_id}")
        return project_dir

    def _first_existing(self, candidates: list[Path]) -> Path | None:
        for path in candidates:
            if path.exists():
                return path
        return None

    def _copy_first_existing(self, candidates: list[Path], destination: Path) -> bool:
        destination.parent.mkdir(parents=True, exist_ok=True)

        for src in candidates:
            if src.exists():
                shutil.copy2(src, destination)
                return True

        if self.strict_scripts:
            raise FileNotFoundError(
                f"No encontré ningún archivo esperado para {destination.name}: {candidates}"
            )

        return False

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _safe_read(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            return self._read_json(path)
        except Exception:
            return {"_error": f"No se pudo leer JSON: {path.name}"}

    def _write_debug(self, outputs_dir: Path, debug: list[StepResult]) -> None:
        self._write_json(outputs_dir / "debug.json", [d.__dict__ for d in debug])

    def _append_debug(self, outputs_dir: Path, debug: list[StepResult]) -> None:
        existing = self._safe_read(outputs_dir / "debug.json") or []
        existing.extend([d.__dict__ for d in debug])
        self._write_json(outputs_dir / "debug.json", existing)