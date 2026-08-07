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
import shutil
import signal
import subprocess
import threading
from collections import defaultdict
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
# UI-Label → claude-CLI-Modell-Alias (die CLI kennt keine Labels mit Leerzeichen).
_CLAUDE_MODEL_ALIAS = {
    "Claude Sonnet": "sonnet",
    "Claude Opus": "opus",
    "Claude Haiku": "haiku",
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


class UiCheckRegistryError(RuntimeError):
    """Registry-Katalog fehlt oder ist nicht lesbar (PROJ-21 Edge Case)."""


class UiCheckRegistryGap(RuntimeError):
    """`registry-only` verlangt, aber mindestens eine Sektion hat keinen passenden Block."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            "Registry-only: keine passenden Blocks fuer Sektionen: " + ", ".join(missing)
        )


class UiCheckBrandingIncomplete(RuntimeError):
    """Branding-Profil existiert, aber Pflichtteile (Tokens/Theme) fehlen."""

    def __init__(self, slug: str, missing: list[str]) -> None:
        self.slug = slug
        self.missing = missing
        super().__init__(
            f"Branding-Profil '{slug}' ist unvollstaendig, es fehlen: " + ", ".join(missing)
        )


# Sektionstyp-Synonyme, gespiegelt aus scripts/registry-select.mjs (SECTION_ALIASES),
# damit der Backend-Vorab-Check dieselben Sektionen matcht wie der echte Selector.
_SECTION_ALIASES = {
    "nav": "nav", "navbar": "nav", "header": "nav",
    "hero": "hero", "intro": "hero",
    "about": "about", "ueber-uns": "about", "ueber": "about", "about-us": "about", "story": "about",
    "services": "services", "leistungen": "services", "angebot": "services", "angebote": "services",
    "loesungen": "services", "features": "services",
    "portfolio": "portfolio", "cases": "portfolio", "case-studies": "portfolio", "referenzen": "portfolio",
    "projekte": "portfolio", "work": "portfolio",
    "process": "process", "prozess": "process", "ablauf": "process", "steps": "process",
    "wie-es-funktioniert": "process",
    "team": "team", "people": "team", "das-team": "team",
    "trust": "trust", "awards": "trust", "auszeichnungen": "trust", "zertifikate": "trust",
    "partner": "trust", "logos": "trust",
    "social-proof": "social-proof", "testimonials": "social-proof", "stimmen": "social-proof",
    "bewertungen": "social-proof", "reviews": "social-proof",
    "faq": "faq", "fragen": "faq",
    "cta": "cta", "kontakt": "cta", "contact": "cta", "abschluss": "cta", "call-to-action": "cta",
    "anfrage": "cta",
    "footer": "footer", "fuss": "footer",
}
_BRANDING_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_INDUSTRY_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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
        self._cancelled_runs: set[str] = set()
        self._chain_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

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

    def start_run(self, payload: Any, screenshot: Any | None = None) -> dict[str, str]:
        self._ensure_project()
        run_dir = self._next_run_dir(str(payload.url))
        run_dir.mkdir(parents=True, exist_ok=False)
        screenshot_path = None
        if screenshot is not None:
            screenshot_path = run_dir / "uploaded-screenshot.png"
            try:
                self._save_screenshot(screenshot, screenshot_path)
            except Exception:
                shutil.rmtree(run_dir)
                raise
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
        if screenshot_path:
            cmd += ["--screenshot", str(screenshot_path)]
        # Der Judge ist immer Claude (visuelle Rubrik-Bewertung). Bei Claude-Läufen
        # das gewählte Modell als CLI-Alias durchreichen. Das Frontend schickt ein
        # Label ("Claude Sonnet") — die claude-CLI kennt nur Aliasse (sonnet/opus/
        # haiku); ein unbekanntes Modell ließe den Judge mit Exit 1 scheitern.
        if payload.ai_provider == "claude":
            alias = _CLAUDE_MODEL_ALIAS.get(payload.ai_model or "")
            if alias:
                cmd += ["--judge-model", alias]
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.project_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        run_id = run_dir.name
        # AC-3: depth="redesign" + full_pipeline soll nicht nur den Audit starten,
        # sondern fachlich /ui-check → /ui-redesign → /ui-images-fill →
        # /ui-mockup-export verketten. Die Skripte laufen fire-and-forget (Popen),
        # daher beobachtet ein Hintergrund-Thread den laufenden Prozess per
        # .wait() und startet bei Erfolg (Exit 0 ok / 1 degradiert) den naechsten
        # Schritt. Ein harter Fehler (Exit >=2) bricht die Kette ab und schreibt
        # chain_error in status.json — kein Task-Queue-System, minimal-invasiv.
        if payload.depth == "redesign" and payload.full_pipeline:
            gen_model_args = []
            if payload.ai_provider == "claude":
                alias = _CLAUDE_MODEL_ALIAS.get(payload.ai_model or "")
                if alias:
                    gen_model_args = ["--gen-model", alias]
            steps = [
                ("redesign", [str(self.project_path / "scripts" / "redesign-auto.sh"), str(run_dir)] + gen_model_args),
                ("images", [str(self.project_path / "scripts" / "images-fill.sh"), str(run_dir)]),
                ("mockup", [str(self.project_path / "scripts" / "mockup-export.sh"), str(run_dir)]),
            ]
            self._processes[run_id] = proc
            self._run_chain(run_id, run_dir, proc, steps, first_step_name="audit")
        else:
            self._processes[run_id] = proc
        return {"run_id": run_id, "status": "running"}

    @staticmethod
    def _save_screenshot(source: Any, target: Path) -> None:
        """Store one bounded PNG inside its newly-created run directory."""
        header = source.read(8)
        if header != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Bitte einen PNG-Screenshot hochladen.")
        total = len(header)
        with target.open("wb") as output:
            output.write(header)
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > settings.upload_max_file_bytes:
                    raise ValueError(
                        f"Screenshot zu groß (max. {settings.upload_max_file_bytes // (1024 * 1024)} MB)."
                    )
                output.write(chunk)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        run_id = _safe_run_id(run_id)
        # Chain-Worker-Thread haengt in proc.wait() und wuerde ein SIGTERM als
        # harten Fehler (chain_error) interpretieren und "cancelled" ueberschreiben.
        self._cancelled_runs.add(run_id)
        # Gleicher Lock wie der Chain-Schrittwechsel: sonst kann killpg genau in
        # der Luecke zwischen "alter Schritt beendet" und "naechster Schritt
        # eingetragen" noch die veraltete (bereits beendete) Proc-Referenz
        # treffen und der frisch gestartete naechste Schritt liefe unbeeinflusst
        # weiter, obwohl der Lauf schon als "cancelled" markiert wird.
        with self._chain_locks[run_id]:
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
        # redesign-auto.sh verkettet INIT → Generierung (headless Claude,
        # ui-redesign) → Verify. redesign.sh allein scaffoldet nur und stoppt bei
        # awaiting_generation — die Generierung würde sonst nie ausgelöst.
        cmd = [str(self.project_path / "scripts" / "redesign-auto.sh"), str(path)]
        ctx = _read_json(path / "ui-check.json")
        if ctx.get("ai_provider") == "claude":
            alias = _CLAUDE_MODEL_ALIAS.get(ctx.get("ai_model") or "")
            if alias:
                cmd += ["--gen-model", alias]
        self._spawn_exclusive(run_id, cmd)
        return self._detail(path)

    def start_images(self, run_id: str, force: bool = False, only: str | None = None) -> dict[str, Any]:
        run_id = _safe_run_id(run_id)
        path = self._run_path(run_id)
        if not path.exists():
            raise UiCheckNotFound(run_id)
        if not (path / "redesign").exists():
            raise UiCheckConflict("Bilder fuellen braucht einen vorhandenen Redesign-Lauf (redesign/).")
        cmd = [str(self.project_path / "scripts" / "images-fill.sh"), str(path)]
        if force:
            cmd.append("--force")
        if only in {"safe", "bold"}:
            cmd += ["--only", only]
        self._spawn_exclusive(run_id, cmd)
        return self._detail(path)

    def start_mockup_export(self, run_id: str, force: bool = False) -> dict[str, Any]:
        run_id = _safe_run_id(run_id)
        path = self._run_path(run_id)
        if not path.exists():
            raise UiCheckNotFound(run_id)
        if not (path / "redesign").exists():
            raise UiCheckConflict("Mockup-Export braucht einen vorhandenen Redesign-Lauf (redesign/).")
        if (path / "mockup.html").exists() and not force:
            raise UiCheckConflict(
                "mockup.html existiert bereits fuer diesen Lauf. Erneuten Export mit force=true erzwingen."
            )
        cmd = [str(self.project_path / "scripts" / "mockup-export.sh"), str(path)]
        if force:
            cmd.append("--force")
        self._spawn_exclusive(run_id, cmd)
        return self._detail(path)

    def start_recycle(
        self,
        run_id: str,
        min_total: int | None = None,
        min_visual: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        run_id = _safe_run_id(run_id)
        path = self._run_path(run_id)
        if not path.exists():
            raise UiCheckNotFound(run_id)
        if not (path / "redesign").exists():
            raise UiCheckConflict("Registry-Recycling braucht einen vorhandenen Redesign-Lauf (redesign/).")
        cmd = ["node", str(self.project_path / "scripts" / "registry-recycle.mjs"), "--run", str(path)]
        if min_total is not None:
            cmd += ["--min-total", str(min_total)]
        if min_visual is not None:
            cmd += ["--min-visual", str(min_visual)]
        if force:
            cmd.append("--force")
        self._spawn_exclusive(run_id, cmd)
        return self._detail(path)

    def list_registry(self) -> dict[str, Any]:
        data = self._read_registry_raw()
        version = None
        version_file = self.project_path / "registry" / "VERSION"
        if version_file.exists():
            try:
                first_line = version_file.read_text(encoding="utf-8").splitlines()
                version = first_line[0].strip() if first_line else None
            except OSError:
                version = None
        items = []
        for raw in data.get("items", []):
            if not isinstance(raw, dict):
                continue
            meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
            files = []
            for f in raw.get("files", []) if isinstance(raw.get("files"), list) else []:
                if isinstance(f, dict) and f.get("path"):
                    files.append({"path": f["path"], "type": f.get("type")})
            items.append({
                "name": raw.get("name") or "",
                "type": raw.get("type") or "",
                "title": raw.get("title"),
                "description": raw.get("description"),
                "section": meta.get("section"),
                "style": meta.get("style"),
                "industry": meta.get("industry") or [],
                "interactive": bool(meta.get("interactive")),
                "source": meta.get("source"),
                "image_slots": meta.get("image_slots") or [],
                "files": files,
                "assembler_selectable": raw.get("type") == "registry:block",
            })
        return {"items": items, "version": version}

    def list_branding_profiles(self) -> dict[str, Any]:
        branding_dir = self.project_path / "branding"
        profiles: list[dict[str, Any]] = []
        if not branding_dir.exists():
            return {"profiles": profiles}
        for entry in sorted(p for p in branding_dir.iterdir() if p.is_dir()):
            profile = _read_json(entry / "profile.json")
            current = entry / "current"
            tokens = _read_json(current / "tokens.json")
            missing = []
            if not (current / "tokens.json").exists():
                missing.append("tokens.json")
            if not (current / "tailwind-theme.css").exists():
                missing.append("tailwind-theme.css")
            has_logo = (current / "logo.svg").exists() or (current / "logo.png").exists()
            profiles.append({
                "slug": entry.name,
                "name": profile.get("name"),
                "industry": profile.get("industry"),
                "tags": profile.get("tags") or [],
                "active_version": profile.get("active_version"),
                "colors": self._token_colors(tokens)[:12],
                "fonts": self._token_fonts(tokens)[:8],
                "has_logo": has_logo,
                "complete": not missing,
                "missing": missing,
            })
        return {"profiles": profiles}

    def start_assemble(self, payload: Any) -> dict[str, Any]:
        branding = payload.branding
        industry = payload.industry
        if not _BRANDING_SLUG_RE.match(branding):
            raise UiCheckConflict(f"Ungueltiger Branding-Slug: {branding}")
        if not _INDUSTRY_TAG_RE.match(industry):
            raise UiCheckConflict(f"Ungueltiger Industrie-Tag: {industry}")

        profile_dir = self.project_path / "branding" / branding / "current"
        if not profile_dir.exists():
            raise UiCheckNotFound(f"branding/{branding}")
        missing_profile = []
        if not (profile_dir / "tokens.json").exists():
            missing_profile.append("tokens.json")
        if not (profile_dir / "tailwind-theme.css").exists():
            missing_profile.append("tailwind-theme.css")
        if missing_profile:
            raise UiCheckBrandingIncomplete(branding, missing_profile)

        sections = list(payload.sections) or ["hero", "trust", "features", "pricing", "cta"]
        overrides = {o.section: o for o in payload.overrides}
        blocks = self._registry_blocks()

        pins: list[str] = []
        excludes: set[str] = set()
        active_sections: list[str] = []
        for sec in sections:
            override = overrides.get(sec)
            if override and override.decision == "exclude":
                continue  # Sektion bewusst weglassen — nicht Teil des Sektionsplans.
            active_sections.append(sec)
            if override and override.decision == "block" and override.block:
                pins.append(f"{sec}={override.block}")
            elif override and override.decision == "generate":
                # assemble.sh/registry-select.mjs kennen keinen "force generate"-Flag
                # pro Sektion — nur --exclude auf Blocknamen. Wir schliessen daher
                # gezielt alle fuer diese Sektion passenden Blocks aus, was den
                # Selector zuverlaessig auf "generate" fuer diese Sektion zwingt.
                matches = self._candidates_for_section(blocks, sec, industry, set())
                excludes.update(b["name"] for b in matches)

        if not active_sections:
            raise UiCheckConflict("Sektionsplan ist nach Ausschluessen leer.")

        if payload.registry_only:
            # Explizit vom Nutzer gepinnte oder auf "generate" gesetzte Sektionen
            # sind keine unbeabsichtigte Luecke — nur "auto"-Sektionen ohne Treffer
            # zaehlen als harte registry-only-Luecke.
            check_sections = [
                s for s in active_sections
                if not (overrides.get(s) and overrides[s].decision in {"block", "generate"})
            ]
            missing = self._missing_sections(blocks, check_sections, industry)
            if missing:
                raise UiCheckRegistryGap(missing)

        run_dir = self._next_assemble_run_dir(branding, industry)
        cmd = [
            str(self.project_path / "scripts" / "assemble.sh"),
            "--branding", branding,
            "--industry", industry,
            "--sections", ",".join(active_sections),
            "--out", str(run_dir),
        ]
        if payload.prompt:
            cmd += ["--prompt", payload.prompt]
        for pin in pins:
            cmd += ["--pin", pin]
        for excl in sorted(excludes):
            cmd += ["--exclude", excl]
        if payload.registry_only:
            cmd.append("--registry-only")

        self._processes[run_dir.name] = self._spawn(cmd)
        return {"run_id": run_dir.name, "status": "running", "run_type": "assemble"}

    def delete_run(self, run_id: str) -> None:
        run_id = _safe_run_id(run_id)
        proc = self._processes.get(run_id)
        if proc and proc.poll() is None:
            raise UiCheckConflict("Lauf kann nicht geloescht werden, waehrend er noch laeuft — erst abbrechen.")
        path = self._run_path(run_id)
        if not path.exists():
            raise UiCheckNotFound(run_id)
        # Defensive Pfadbegrenzung: nur direkte Kinder des runs-Ordner duerfen
        # geloescht werden, niemals der Elternordner selbst (Path-Traversal).
        if path.resolve() == self.runs_dir.resolve():
            raise UiCheckNotFound(run_id)
        shutil.rmtree(path, ignore_errors=False)
        self._processes.pop(run_id, None)

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
        run_type = self._run_type(path)
        # ctx.get("mode") ist bei Assemble-Laeufen "assemble" (assemble.sh
        # ueberlaedt denselben Feldnamen fuer sein Greenfield-Kennzeichen) — das
        # ist kein gueltiger Wert fuer das Landing/App-Mode-Feld der Audit-Antwort.
        raw_mode = ctx.get("mode")
        mode = raw_mode if raw_mode in {"auto", "landing", "app"} else "auto"
        return {
            "run_id": path.name,
            "created_at": status.get("started_at") or ctx.get("started_at") or scores.get("timestamp"),
            "url_hash": _url_hash(url, path.name),
            "display_url": url,
            "mode": mode,
            "depth": "redesign" if (path / "redesign").exists() or (path / "mockup.html").exists() else "audit",
            "run_type": run_type,
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
            "mockup_status": self._mockup_status(path),
            "registry_selection": self._registry_selection(path),
            "chain_error": status.get("chain_error"),
        })
        return base

    def _run_type(self, path: Path) -> str:
        redesign_ctx = _read_json(path / "redesign" / "redesign-context.json")
        ui_check_ctx = _read_json(path / "ui-check.json")
        if redesign_ctx.get("source") == "assemble" or ui_check_ctx.get("mode") == "assemble":
            return "assemble"
        return "audit_redesign"

    def _mockup_status(self, path: Path) -> dict[str, Any]:
        rd = path / "redesign"
        fill = _read_json(rd / "images-fill.json")
        counts = fill.get("counts") if isinstance(fill.get("counts"), dict) else {}
        filled = counts.get("filled") or 0
        placeholder = counts.get("placeholder") or 0
        total = filled + placeholder
        exported = (path / "mockup.html").exists()
        return {
            "safe_ready": (rd / "safe").exists(),
            "bold_ready": (rd / "bold").exists(),
            "exported": exported,
            "export_conflict": exported,
            "images": {
                "total_slots": total,
                "filled_slots": filled,
                "placeholder_slots": placeholder,
                "degraded": total > 0 and placeholder > 0,
            },
            "score_delta": self._score_delta(path),
        }

    def _score_delta(self, path: Path) -> int | float | None:
        before = _read_json(path / "scores.json").get("total")
        after = self._redesign_score(path)
        if before is None or after is None:
            return None
        return after - before

    def _registry_selection(self, path: Path) -> dict[str, Any]:
        rd = path / "redesign"

        def variant(name: str) -> list[dict[str, Any]]:
            sel = _read_json(rd / f"registry-selection.{name}.json")
            sections = sel.get("sections") if isinstance(sel.get("sections"), list) else []
            out = []
            for section in sections:
                if isinstance(section, dict):
                    out.append({
                        "id": section.get("id"),
                        "type": section.get("type"),
                        "decision": section.get("decision"),
                        "block": section.get("block"),
                        "reason": section.get("reason"),
                    })
            return out

        return {"safe": variant("safe"), "bold": variant("bold")}

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
                elif isinstance(value, list) and value and isinstance(value[0], str):
                    # Branding-Profile (DTCG fontFamily) speichern $value als Liste
                    # ("Geist", "ui-sans-serif", ...) statt als Komma-String.
                    out.append(value[0].strip())
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
        # Atomar schreiben (tmp + os.replace): status.json wird vom Dashboard
        # gepollt, waehrend der Hintergrund-Thread der Pipeline-Kette parallel
        # schreibt — ein truncate-in-place wuerde dem Poller sonst gelegentlich
        # eine leere/kaputte Datei zeigen.
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _reject_running(self, run_id: str) -> None:
        proc = self._processes.get(run_id)
        if proc and proc.poll() is None:
            raise UiCheckConflict("Fuer diesen Lauf arbeitet bereits ein Prozess.")

    def _spawn(self, cmd: list[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            cmd,
            cwd=str(self.project_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _spawn_exclusive(self, run_id: str, cmd: list[str]) -> subprocess.Popen[bytes]:
        # Gleicher Lock wie der Chain-Worker beim Schrittwechsel, damit ein
        # manueller Einzelschritt-Start nicht in das kurze Zeitfenster zwischen
        # "Prozess beendet" und "naechster Prozess eingetragen" reinlaufen kann.
        with self._chain_locks[run_id]:
            self._reject_running(run_id)
            proc = self._spawn(cmd)
            self._processes[run_id] = proc
            return proc

    def _run_chain(
        self,
        run_id: str,
        path: Path,
        first_proc: subprocess.Popen[bytes],
        steps: list[tuple[str, list[str]]],
        first_step_name: str,
    ) -> None:
        def worker() -> None:
            proc = first_proc
            step_name = first_step_name
            remaining = list(steps)
            while True:
                returncode = proc.wait()
                if run_id in self._cancelled_runs:
                    self._cancelled_runs.discard(run_id)
                    return
                if returncode not in (0, 1):
                    self._write_chain_error(path, step_name, returncode)
                    return
                if not remaining:
                    return
                step_name, cmd = remaining.pop(0)
                with self._chain_locks[run_id]:
                    proc = self._spawn(cmd)
                    self._processes[run_id] = proc

        threading.Thread(target=worker, daemon=True).start()

    def _write_chain_error(self, path: Path, step: str, returncode: int) -> None:
        status = _read_json(path / "status.json")
        status["chain_error"] = {
            "step": step,
            "returncode": returncode,
            "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        status["status"] = "error"
        self._write_json(path / "status.json", status)

    def _read_registry_raw(self) -> dict[str, Any]:
        reg_path = self.project_path / "registry" / "registry.json"
        try:
            with reg_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError as exc:
            raise UiCheckRegistryError(f"Registry-Katalog nicht gefunden: {reg_path}") from exc
        except json.JSONDecodeError as exc:
            raise UiCheckRegistryError(f"Registry-Katalog ist fehlerhaft (kein gueltiges JSON): {reg_path}") from exc
        except OSError as exc:
            raise UiCheckRegistryError(f"Registry-Katalog nicht lesbar: {reg_path}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise UiCheckRegistryError(f"Registry-Katalog hat ein unerwartetes Format: {reg_path}")
        return data

    def _registry_blocks(self) -> list[dict[str, Any]]:
        data = self._read_registry_raw()
        blocks = []
        for item in data.get("items", []):
            if (
                isinstance(item, dict)
                and item.get("type") == "registry:block"
                and isinstance(item.get("meta"), dict)
                and item["meta"].get("section")
            ):
                blocks.append(item)
        return blocks

    def _canon_section(self, section_type: str) -> str:
        key = str(section_type or "").lower()
        return _SECTION_ALIASES.get(key, key)

    def _matches_industry(self, item: dict[str, Any], industry: str | None) -> bool:
        if not industry:
            return True
        tags = item.get("meta", {}).get("industry") or []
        return any(industry in tag or tag in industry for tag in tags)

    def _candidates_for_section(
        self,
        blocks: list[dict[str, Any]],
        section_type: str,
        industry: str | None,
        exclude: set[str],
    ) -> list[dict[str, Any]]:
        canon = self._canon_section(section_type)
        return [
            b for b in blocks
            if self._canon_section(b["meta"]["section"]) == canon
            and self._matches_industry(b, industry)
            and b.get("name") not in exclude
        ]

    def _missing_sections(
        self, blocks: list[dict[str, Any]], sections: list[str], industry: str | None
    ) -> list[str]:
        return [s for s in sections if not self._candidates_for_section(blocks, s, industry, set())]

    def _next_assemble_run_dir(self, branding: str, industry: str) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        base = f"{today}-assemble-{branding}-{industry}"
        for n in range(1, 1000):
            candidate = self.runs_dir / f"{base}-{n:03d}"
            if not candidate.exists():
                return candidate
        raise UiCheckConflict("Kein freier Run-Ordner fuer Assemble gefunden.")
