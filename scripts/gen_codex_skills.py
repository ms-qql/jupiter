#!/usr/bin/env python3
"""PROJ-50: Generator — Claude-abc-Skills → Codex-taugliche Varianten.

Quelle der Wahrheit bleiben die Claude-Originale unter ``~/.claude/skills/abc-*``.
Dieser Generator leitet daraus reproduzierbar (idempotent) eine Codex-Variante unter
``$CODEX_HOME/skills/abc-*`` ab — KEIN Symlink, weil die Claude-Ismen (Agent/Explore-
Subagenten, ``AskUserQuestion``, Skill-Chaining über das ``Skill``-Tool, absolute
``/home/dev/.claude/...``-Pfade, CodeGraph-MCP) Codex' shell-basiertes Tool-Modell
stören würden. Die fachliche Phasen-Logik (Was/Warum, Akzeptanzkriterien, Status-
Update-Contract, INDEX.md-Pflege) bleibt unangetastet.

Transformationen (alle deterministisch):
  1. Frontmatter: ``name``/``description`` behalten; Claude-only-Keys (``argument-hint``,
     ``user-invocable``) entfernen; ``metadata.short-description`` ergänzen.
  2. Body-Regelwerk (``RULES``): Claude-Tool-Referenzen + absolute ``.claude``-Pfade
     durch Codex-Äquivalente ersetzen bzw. klar als „in Codex nicht verfügbar" markieren.
  3. Codex-Präambel direkt nach der H1 einfügen (Tool-/Umgebungsunterschiede).
  4. Optionales Per-Skill-Overlay (``scripts/codex_skill_overlays/<name>.md``) anhängen —
     für Stellen, die echte Umformulierung statt Regel-Ersetzung brauchen.

Aufruf:
  python scripts/gen_codex_skills.py            # schreibt nach $CODEX_HOME/skills
  python scripts/gen_codex_skills.py --check     # nur prüfen (CI): Drift → Exit 1
  python scripts/gen_codex_skills.py --dry-run   # Diff-Vorschau, nichts schreiben
  python scripts/gen_codex_skills.py --dest DIR --src DIR  # Pfade überschreiben

Nach dem Schreiben: **Codex neu starten**, damit neue/aktualisierte Skills geladen werden.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

# Nur die abc-Workflow-Skills portieren (alle, gemäß Design-Entscheidung 2 der Spec).
SKILL_GLOB = "abc-*"

DEFAULT_SRC = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude")) / "skills"
DEFAULT_DEST = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"
OVERLAY_DIR = Path(__file__).with_name("codex_skill_overlays")

# Frontmatter-Keys, die in Codex keinen Sinn ergeben (Claude-Code-spezifisch).
DROP_FRONTMATTER_KEYS = {"argument-hint", "user-invocable", "allowed-tools", "model"}

GENERATED_MARKER = "<!-- GENERIERT von scripts/gen_codex_skills.py (PROJ-50) — NICHT direkt editieren; Quelle: ~/.claude/skills -->"

# Codex-Präambel: erklärt die Tool-/Umgebungsunterschiede, ohne die Phasen-Logik zu ändern.
PREAMBLE = """\
> **Codex-Hinweis (automatisch ergänzt, PROJ-50).** Diese Skill ist die **Codex-Variante**
> einer Claude-Code-Skill. Codex arbeitet **shell-basiert** und hat einige der unten
> erwähnten Claude-Werkzeuge NICHT. Übersetze beim Abarbeiten sinngemäß:
> - **`AskUserQuestion` / Auswahl-Dialoge** → stelle die Frage als normalen Text und
>   **warte auf die Antwort des Nutzers im nächsten Turn** (Multi-Turn ist verfügbar).
> - **`Agent` / `Explore` / Sub-Agenten** → es gibt keine Sub-Agenten; nutze direkte
>   Shell-/Suchbefehle (`rg`, `grep`, `sed`, `find`, Datei lesen) selbst.
> - **Skill-Chaining über das `Skill`-Tool** → rufe Folge-Skills **nicht** automatisch auf;
>   schlage dem Nutzer den nächsten Schritt vor (er startet ihn als neuen Turn/Session).
> - **CodeGraph-MCP** → ggf. nicht verfügbar; nutze ersatzweise `rg`/`grep`.
> - **Absolute `/home/dev/.claude/...`-Pfade** sind Claude-spezifisch und hier irrelevant.
>
> Die **fachliche Logik** (Was/Warum, Akzeptanzkriterien, Status-Update-Contract,
> Pflege von `features/INDEX.md` und der Spec) gilt für Codex **unverändert**.

"""

# Regelwerk: (Pattern, Ersatz). Reihenfolge zählt (spezifisch vor generisch).
# WICHTIG: Die CodeGraph-CLI (`codegraph init -i`, `codegraph index`) bleibt UNANGETASTET —
# sie ist ein Shell-Binary und in Codex nutzbar. Nur die MCP-Tools (`codegraph_*`,
# Unterstrich-Form) und Explore-/Sub-Agenten sind in Codex nicht verfügbar.
RULES: list[tuple[str, str]] = [
    # Absolute Claude-Skill-Pfade → Skill-Benennung (kein toter Pfad).
    (r"/home/dev/\.claude/skills/(abc-[a-z0-9-]+)/SKILL\.md", r"die Skill »\1«"),
    # Übrige absolute .claude-Pfade neutralisieren.
    (r"/home/dev/\.claude/[A-Za-z0-9_./-]+", "(Claude-spezifischer Pfad — in Codex irrelevant)"),
    # Inline-„Run CodeGraph exploration (MANDATORY…)" (engl., z. B. in „Before Starting").
    # Ersatztext bewusst OHNE Tokens, die spätere Regeln erneut matchen (kein „Explore-Agent").
    (r"\*\*Run CodeGraph exploration[^*]*\*\*[^\n]*", "**Code zuerst per Shell erkunden** (`rg`/`grep`/Dateien lesen — in Codex weder CodeGraph-MCP noch Sub-Agenten)."),
    # Englische Explore-/Sub-Agent-Phrasen (vom dt. Regelwerk nicht erfasst).
    (r"(?:[Dd]elegate exploration to|go through|spawn|launch|use) an Explore agent",
     "nutze direkte Shell-/Suchbefehle (`rg`/`grep`) selbst — in Codex gibt es keine Sub-Agenten"),
    (r"\ban?\s+Explore\s+agent\b", "direkte Shell-/Suchbefehle (keine Sub-Agenten in Codex)"),
    (r"\bExplore agent(s)?\b", "direkte Shell-/Suchbefehle (keine Sub-Agenten in Codex)"),
    # CodeGraph-MCP-Tools (Unterstrich-Form) — existieren in Codex nicht. CLI bleibt!
    (r"`codegraph_[a-z_]+`(\s*/\s*`codegraph_[a-z_]+`)*",
     "`rg`/`grep` (in Codex kein CodeGraph-MCP)"),
    (r"\bcodegraph_[a-z_]+\b", "rg/grep (kein CodeGraph-MCP in Codex)"),
    # Claude-Tool-Namen in Fließtext markieren.
    (r"\bAskUserQuestion\b", "eine Klartext-Rückfrage an den Nutzer (in Codex: kein AskUserQuestion-Tool)"),
    (r"\b(Explore|Agent|Task)-(Sub)?[Aa]gent(en)?\b", "direkte Shell-/Suchbefehle (in Codex: keine Sub-Agenten)"),
    (r"\bspawn(e|st)?\s+(einen|an)\s+(Explore|Agent)\b", "nutze direkte Shell-/Suchbefehle"),
]
COMPILED = [(re.compile(p), r) for p, r in RULES]

# Level-2-Abschnitte, deren GANZER Inhalt durch eine Codex-Notiz ersetzt wird (statt nur
# einzelne Tool-Namen zu markieren) — weil sie eine Claude-spezifische MANDATORY-Prozedur
# beschreiben (Explore-Agent + CodeGraph-MCP), die Codex sonst ins Leere laufen ließe.
CODEGRAPH_SECTION_RE = re.compile(r"[Cc]ode[Gg]raph\s+Exploration")
CODEGRAPH_SECTION_NOTE = """\
> **Codex (PROJ-50):** In Codex gibt es **keine** Explore-/Sub-Agenten und i. d. R. **kein**
> CodeGraph-MCP. Erkunde den Code stattdessen **direkt per Shell**: `rg`/`grep` für Symbole
> und Referenzen, Dateien gezielt lesen, `ls`/`find` für die Struktur. Die CodeGraph-**CLI**
> (`codegraph init -i`, `codegraph index`) ist dagegen nutzbar, falls vorhanden.
>
> Die fachliche Absicht bleibt unverändert: **erst den echten Code lesen, dann entwerfen** —
> Annahmen vermeiden. Der frühere „CodeGraph (MANDATORY)"-Agenten-Schritt entfällt in Codex.
"""


def replace_level2_section(body: str, heading_match: re.Pattern, note: str) -> str:
    """Ersetzt den Inhalt eines `## …`-Abschnitts (bis zur nächsten `## `-Überschrift)
    durch ``note``; die Überschrift selbst bleibt erhalten. Greift nur, wenn vorhanden."""
    lines = body.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("## ") and heading_match.search(line):
            out.append("## CodeGraph / Code-Erkundung (Codex)")
            out.append("")
            out.append(note.rstrip())
            out.append("")
            i += 1
            while i < n and not lines[i].startswith("## "):
                i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def split_frontmatter(text: str) -> tuple[list[str], str]:
    """Zerlegt ``text`` in (Frontmatter-Zeilen ohne ---, Rest-Body). Kein FM → ([], text)."""
    if not text.startswith("---"):
        return [], text
    end = text.find("\n---", 3)
    if end == -1:
        return [], text
    fm = text[3:end].strip("\n").splitlines()
    body = text[end + 4:].lstrip("\n")
    return fm, body


def transform_frontmatter(fm: list[str]) -> tuple[str, str]:
    """Filtert Claude-only-Keys, liefert (frontmatter_out, name).

    Bug #1-Fix (QA): die Frontmatter wird **YAML-bewusst** geparst (`yaml.safe_load`),
    damit `name`/`description` auch bei Block-Scalars (`description: >-`, Text auf
    Folgezeilen) korrekt sind — die frühere zeilenbasierte Extraktion griff sonst den
    Scalar-Indikator `>-` als „Wert" ab → leere `short-description`.

    Die ORIGINAL-Zeilen (gefiltert um Claude-only-Keys) bleiben erhalten, damit die
    Description-Formatierung 1:1 übernommen wird; nur `metadata.short-description` wird
    aus dem geparsten `description` abgeleitet.
    """
    parsed = yaml.safe_load("\n".join(fm)) or {}
    name = str(parsed.get("name") or "").strip()
    description = str(parsed.get("description") or "").strip()

    # Original-Zeilen behalten, aber Claude-only-Keys (inkl. ihrer Block-Fortsetzungen)
    # herausfiltern. Eine Fortsetzungant ist eine eingerückte Zeile ohne `key:` am Anfang.
    kept: list[str] = []
    skipping = False
    for line in fm:
        stripped = line.strip()
        is_continuation = line[:1] in (" ", "\t") and not re.match(r"^\s*[\w-]+:", line)
        if skipping and is_continuation:
            continue
        skipping = False
        key = line.split(":", 1)[0].strip()
        if key in DROP_FRONTMATTER_KEYS:
            skipping = True  # auch evtl. folgende Block-Zeilen dieses Keys überspringen
            continue
        kept.append(line)

    short = (description or name).strip().strip('"')
    short = " ".join(short.split())  # Folded-Scalar-Umbrüche zu Leerzeichen glätten
    if len(short) > 80:
        short = short[:77].rstrip() + "…"
    fm_out = "---\n" + "\n".join(kept) + "\nmetadata:\n  short-description: " + short + "\n---\n"
    return fm_out, name


def transform_body(body: str, name: str) -> str:
    """Wendet Präambel + Regelwerk + optionales Overlay an."""
    # Präambel direkt nach der ersten H1 (oder ganz oben, falls keine H1).
    lines = body.splitlines()
    insert_at = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            insert_at = i + 1
            break
    head = "\n".join(lines[:insert_at])
    tail = "\n".join(lines[insert_at:])
    out = (head + "\n\n" + PREAMBLE + tail) if head else (PREAMBLE + tail)

    # Claude-spezifische MANDATORY-Prozedur-Abschnitte komplett durch eine Codex-Notiz
    # ersetzen (Bug #2), BEVOR die feineren Regeln laufen.
    out = replace_level2_section(out, CODEGRAPH_SECTION_RE, CODEGRAPH_SECTION_NOTE)

    for rx, repl in COMPILED:
        out = rx.sub(repl, out)

    overlay = OVERLAY_DIR / f"{name}.md"
    if overlay.is_file():
        out = out.rstrip() + "\n\n---\n\n" + overlay.read_text(encoding="utf-8").rstrip() + "\n"
    return out


def render(src_skill: Path) -> str:
    text = (src_skill / "SKILL.md").read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    fm_out, name = transform_frontmatter(fm)
    body_out = transform_body(body, name or src_skill.name)
    return fm_out + GENERATED_MARKER + "\n\n" + body_out.rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generiert Codex-Varianten der abc-Skills (PROJ-50).")
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="Claude-Skills-Verzeichnis")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Codex-Skills-Zielverzeichnis")
    ap.add_argument("--check", action="store_true", help="Nur prüfen (CI): Drift → Exit 1")
    ap.add_argument("--dry-run", action="store_true", help="Nichts schreiben, nur anzeigen")
    args = ap.parse_args()

    skills = sorted(p for p in args.src.glob(SKILL_GLOB) if (p / "SKILL.md").is_file())
    if not skills:
        print(f"FEHLER: keine abc-Skills unter {args.src}", file=sys.stderr)
        return 2

    drift = 0
    written = 0
    for skill in skills:
        rendered = render(skill)
        out_path = args.dest / skill.name / "SKILL.md"
        existing = out_path.read_text(encoding="utf-8") if out_path.is_file() else None
        if existing == rendered:
            continue
        if args.check:
            print(f"DRIFT: {out_path}")
            drift += 1
            continue
        if args.dry_run:
            print(f"WÜRDE SCHREIBEN: {out_path} ({len(rendered)} B)")
            written += 1
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
        print(f"geschrieben: {out_path}")
        written += 1

    if args.check:
        if drift:
            print(f"\n{drift} Skill(s) driften — `python scripts/gen_codex_skills.py` ausführen.", file=sys.stderr)
            return 1
        print(f"OK: alle {len(skills)} Codex-Skills aktuell.")
        return 0
    print(f"\nFertig: {written} geschrieben, {len(skills)-written} unverändert.")
    if written and not args.dry_run:
        print("→ Codex neu starten, damit die neuen/aktualisierten Skills geladen werden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
