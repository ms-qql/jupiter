"""File-backed UI-Check runner service (PROJ-14).

The UI-Check pipeline already owns its artifacts. This service only bridges the
Jupiter browser UI to that local contract: spawn scripts, cancel known child
processes, and read run folders defensively.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..config import settings

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_PHASE_ORDER = ("capture", "lighthouse", "branding", "scoring", "redesign", "mockup")
_DIMENSION_LABELS = {
    "visuell": "Visuell",
    "visual": "Visuell",
    "slop": "KI-Generik",
    "performance": "Performance",
    "accessibility": "Accessibility",
    "conversion": "Conversion",
}
_SEVERITY = {
    "hoch": "high",
    "high": "high",
    "mittel": "medium",
    "medium": "medium",
    "niedrig": "low",
    "low": "low",
}


class UiCheckNotFound(KeyError):
    pass


class UiCheckConflict(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _domain(url: str | None) -> str:
    if not url:
        return "unbekannt"
    host = urlparse(url).netloc or urlparse(f"https://{url}").netloc or url
    return host.removeprefix("www.") or "unbekannt"


def _url_hash(url: str | None, fallback: str) -> str:
    if not url:
        return fallback
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _safe_run_id(run_id: str) -> str:
    if not _RUN_ID_RE.match(run_id) or "/" in run_id or ".." in run_id:
        raise UiCheckNotFound(run_id)
    return run_id


class UiCheckService:
    def __init__(self, project_path: str | None = None) -> None:
        self.project_path = Path(project_path or settings.ui_check_project_path).resolve()
        self.runs_dir = self.project_path / "runs"
        self.data_file = self.project_path / "data" / "runs.jsonl"
        self._processes: dict[str, subprocess.Popen[bytes]] = {}

    def list_runs(self) -> dict[str, Any]:
        runs = [self._summary(p) for p in self._run_dirs()]
        runs.sort(key=lambda row: row.get("created_at") or row["run_id"], reverse=True)
        active = next((r["run_id"] for r in runs if r["status"] in {"queued", "running"}), None)
        return {"runs": runs, "active_run_id": active}

    def get_run(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        if not path.exists():
            raise UiCheckNotFound(run_id)
        return self._detail(path)

    def start_run(self, payload: Any) -> dict[str, str]:
        self._ensure_project()
        run_dir = self._next_run_dir(str(payload.url))
        run_dir.mkdir(parents=True, exist_ok=False)
        self._write_initial_status(run_dir, payload)

        # ui-check-auto.sh verkettet Collect → Judge-Pass (headless Claude) →
        # Finalize in EINEM Prozess. Ohne den automatischen Judge-Pass blieb der
        # Lauf sonst dauerhaft bei awaiting_judge stehen (UI: „Läuft").
        cmd = [str(self.project_path / "scripts" / "ui-check-auto.sh"), str(payload.url), "--out", str(run_dir)]
        if payload.industry:
            cmd += ["--industry", payload.industry]
        if payload.prompt:
            cmd += ["--prompt", payload.prompt]
        if payload.desktop:
            cmd.append("--desktop")
        # Der Judge ist immer Claude (visuelle Rubrik-Bewertung). Bei Claude-Läufen
        # das gewählte Modell durchreichen; sonst nutzt das Skript seinen Default.
        if payload.ai_provider == "claude" and payload.ai_model:
            cmd += ["--judge-model", payload.ai_model]
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.project_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes[run_dir.name] = proc
        return {"run_id": run_dir.name, "status": "running"}

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        run_id = _safe_run_id(run_id)
        proc = self._processes.get(run_id)
        if proc and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
        path = self._run_path(run_id)
        if not path.exists():
            raise UiCheckNotFound(run_id)
        status = _read_json(path / "status.json")
        status.update({
            "run_id": run_id,
            "status": "cancelled",
            "phase": "cancelled",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        self._write_json(path / "status.json", status)
        return self._detail(path)

    def start_redesign(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        if not path.exists():
            raise UiCheckNotFound(run_id)
        if not (path / "scores.json").exists():
            raise UiCheckConflict("Redesign braucht einen abgeschlossenen Audit-Lauf mit scores.json.")
        if run_id in self._processes and self._processes[run_id].poll() is None:
            raise UiCheckConflict("Fuer diesen Lauf arbeitet bereits ein Prozess.")
        cmd = [str(self.project_path / "scripts" / "redesign.sh"), str(path)]
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.project_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes[run_id] = proc
        return self._detail(path)

    def artifact_path(self, run_id: str, kind: str) -> Path:
        path = self._run_path(run_id)
        mapping = {
            "report": path / "report.md",
            "scores": path / "scores.json",
            "tokens": path / "branding" / "tokens.json",
            "mockup": path / "mockup.html",
        }
        if kind.startswith("screenshot-"):
            meta = _read_json(path / "meta.json")
            try:
                idx = int(kind.split("-", 1)[1])
                rel = meta.get("screenshots", [])[idx].get("path")
            except (ValueError, IndexError, AttributeError):
                rel = None
            target = path / rel if rel else path / "__missing__"
        else:
            target = mapping.get(kind, path / "__missing__")
        target = target.resolve()
        if not str(target).startswith(str(path.resolve())) or not target.exists():
            raise UiCheckNotFound(kind)
        return target

    def _ensure_project(self) -> None:
        if not (self.project_path / "scripts" / "ui-check.sh").exists():
            raise UiCheckConflict(f"UI-Check-Projekt nicht gefunden: {self.project_path}")

    def _run_dirs(self) -> list[Path]:
        if not self.runs_dir.exists():
            return []
        return [p for p in self.runs_dir.iterdir() if p.is_dir()]

    def _run_path(self, run_id: str) -> Path:
        return (self.runs_dir / _safe_run_id(run_id)).resolve()

    def _next_run_dir(self, url: str) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        domain = re.sub(r"[^a-zA-Z0-9.-]", "-", _domain(url))
        for n in range(1, 1000):
            candidate = self.runs_dir / f"{today}-{domain}-{n:03d}"
            if not candidate.exists():
                return candidate
        raise UiCheckConflict("Kein freier Run-Ordner gefunden.")

    def _summary(self, path: Path) -> dict[str, Any]:
        status = _read_json(path / "status.json")
        ctx = _read_json(path / "ui-check.json")
        scores = _read_json(path / "scores.json")
        meta = _read_json(path / "meta.json")
        url = status.get("final_url") or ctx.get("final_url") or status.get("url") or ctx.get("url") or meta.get("url")
        raw_status = status.get("status") or ("done" if scores else "error")
        mapped_status = self._status(path.name, raw_status)
        return {
            "run_id": path.name,
            "created_at": status.get("started_at") or ctx.get("started_at") or scores.get("timestamp"),
            "url_hash": _url_hash(url, path.name),
            "display_url": url,
            "mode": ctx.get("mode") or "auto",
            "depth": "redesign" if (path / "redesign").exists() or (path / "mockup.html").exists() else "audit",
            "industry": status.get("industry_tag") or ctx.get("industry_tag") or scores.get("meta", {}).get("industry_tag"),
            "status": mapped_status,
            "rubric_version": ctx.get("rubric_version") or scores.get("rubric_version"),
            "score_total": scores.get("total"),
            "redesign_score": self._redesign_score(path),
            "ai_provider": ctx.get("ai_provider"),
            "ai_model": ctx.get("ai_model"),
        }

    def _detail(self, path: Path) -> dict[str, Any]:
        base = self._summary(path)
        status = _read_json(path / "status.json")
        ctx = _read_json(path / "ui-check.json")
        scores = _read_json(path / "scores.json")
        base.update({
            "phase": status.get("phase"),
            "progress": self._progress(status, bool(scores)),
            "prompt": status.get("user_prompt") or ctx.get("user_prompt"),
            "dimensions": self._dimensions(scores),
            "findings": self._findings(scores),
            "branding": self._branding(path, base["display_url"]),
            "artifacts": self._artifacts(path),
            "status_message": self._status_message(status, bool(scores)),
        })
        return base

    def _status(self, run_id: str, raw: str) -> str:
        proc = self._processes.get(run_id)
        if proc and proc.poll() is None:
            return "running"
        if raw in {"done"}:
            return "done"
        if raw in {"cancelled", "aborted"}:
            return "cancelled"
        if raw in {"running", "queued", "awaiting_judge"}:
            return "running"
        return "error"

    def _progress(self, status: dict[str, Any], has_scores: bool) -> int:
        if has_scores:
            return 100
        phase = status.get("phase")
        if phase == "awaiting_judge":
            return 60
        phases = status.get("phases") if isinstance(status.get("phases"), dict) else {}
        done = sum(1 for p in _PHASE_ORDER if phases.get(p, {}).get("status") in {"ok", "degraded"})
        return min(95, int(done / len(_PHASE_ORDER) * 100))

    def _status_message(self, status: dict[str, Any], has_scores: bool) -> str:
        if has_scores:
            return "Audit abgeschlossen."
        if status.get("phase") == "awaiting_judge":
            return "Datenerfassung abgeschlossen, Judge-Pass läuft …"
        if status.get("phase") == "judge_failed":
            err = status.get("phases", {}).get("scoring", {}).get("error")
            return err or "Judge-Pass fehlgeschlagen."
        if status.get("status") == "error":
            return "Lauf fehlgeschlagen."
        if status.get("status") in {"cancelled", "aborted"}:
            err = status.get("phases", {}).get("scoring", {}).get("error")
            return err or "Lauf abgebrochen."
        return status.get("phase") or "Lauf wird vorbereitet."

    def _dimensions(self, scores: dict[str, Any]) -> list[dict[str, Any]]:
        dims = scores.get("dimensions")
        if not isinstance(dims, dict):
            return []
        rows = []
        for key, value in dims.items():
            if isinstance(value, dict):
                rows.append({
                    "key": key,
                    "label": _DIMENSION_LABELS.get(key, key.title()),
                    "source": str(value.get("source") or "scores.json"),
                    "score": value.get("score"),
                })
        return rows

    def _findings(self, scores: dict[str, Any]) -> list[dict[str, Any]]:
        raw = scores.get("findings")
        if not isinstance(raw, list):
            return []
        findings = []
        for item in raw[:50]:
            if not isinstance(item, dict):
                continue
            findings.append({
                "severity": _SEVERITY.get(str(item.get("severity", "")).lower(), "medium"),
                "title": str(item.get("title") or "Befund"),
                "description": str(item.get("evidence") or item.get("description") or ""),
                "location": str(item.get("location") or item.get("source") or ""),
            })
        return findings

    def _branding(self, path: Path, url: str | None) -> dict[str, Any] | None:
        tokens = _read_json(path / "branding" / "tokens.json")
        meta = _read_json(path / "branding" / "branding-meta.json")
        if not tokens and not meta:
            return None
        colors = self._token_colors(tokens)
        fonts = self._token_fonts(tokens)
        logo_file = meta.get("logo", {}).get("file") if isinstance(meta.get("logo"), dict) else None
        return {
            "name": _domain(url).split(".")[0].title(),
            "domain": _domain(url),
            "logo_path": f"branding/{logo_file}" if logo_file else None,
            "colors": colors[:12],
            "fonts": fonts[:8],
            "voice": None,
            "token_count": len(colors) + len(fonts),
        }

    def _token_colors(self, tokens: dict[str, Any]) -> list[str]:
        found: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                v = value.get("$value")
                if isinstance(v, str) and re.match(r"^#[0-9a-fA-F]{3,8}$", v) and v not in found:
                    found.append(v)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(tokens.get("color", {}))
        return found

    def _token_fonts(self, tokens: dict[str, Any]) -> list[str]:
        font = tokens.get("font")
        if not isinstance(font, dict):
            return []
        out = []
        for item in font.values():
            if isinstance(item, dict):
                value = item.get("$value")
                if isinstance(value, str):
                    out.append(value.split(",", 1)[0].strip())
        return out

    def _artifacts(self, path: Path) -> dict[str, Any]:
        meta = _read_json(path / "meta.json")
        screenshots = []
        for idx, shot in enumerate(meta.get("screenshots", []) if isinstance(meta.get("screenshots"), list) else []):
            if isinstance(shot, dict) and shot.get("path") and (path / shot["path"]).exists():
                screenshots.append(f"screenshot-{idx}")
        return {
            "report": "report" if (path / "report.md").exists() else None,
            "scores": "scores" if (path / "scores.json").exists() else None,
            "tokens": "tokens" if (path / "branding" / "tokens.json").exists() else None,
            "mockup": "mockup" if (path / "mockup.html").exists() else None,
            "screenshots": screenshots or None,
        }

    def _redesign_score(self, path: Path) -> int | float | None:
        after = _read_json(path / "after-score.json")
        return after.get("total") if after else None

    def _write_initial_status(self, run_dir: Path, payload: Any) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        data = {
            "run_id": run_dir.name,
            "url": str(payload.url),
            "status": "queued",
            "phase": "queued",
            "industry_tag": payload.industry,
            "user_prompt": payload.prompt,
            "desktop": payload.desktop,
            "started_at": now,
            "updated_at": now,
        }
        self._write_json(run_dir / "status.json", data)
        self._write_json(run_dir / "ui-check.json", {
            "run_id": run_dir.name,
            "url": str(payload.url),
            "mode": payload.mode,
            "depth": payload.depth,
            "ai_provider": payload.ai_provider,
            "ai_model": payload.ai_model,
            "industry_tag": payload.industry,
            "user_prompt": payload.prompt,
            "desktop": payload.desktop,
            "started_at": now,
        })

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
