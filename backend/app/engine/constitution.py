"""ConstitutionResolver — löst die effektive Konstitution einer Session auf (PROJ-6).

Store = Markdown-Dateien (kein DB/Vault im MVP), bei JEDEM Aufruf frisch gelesen
→ editierbar ohne Deploy:

    <constitution_dir>/global.md              # gilt immer
    <constitution_dir>/roles/<rolle>.md       # optionaler Zusatz/Override je Rolle

Beginnt eine Rollendatei mit der Marker-Zeile ``<!-- mode: replace -->``, ersetzt
sie die globale Konstitution; sonst wird sie angehängt.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

REPLACE_MARKER = "<!-- mode: replace -->"
_VALID_ROLE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class ResolvedConstitution:
    text: str          # der tatsächlich zu injizierende Prompt-Text (kann "" sein)
    source: str        # menschenlesbare Herkunft, z. B. "global+rolle:architect"
    role: str | None   # die aufgelöste Rolle (oder None)


def is_valid_role(role: str) -> bool:
    """Nur sichere Rollennamen (verhindert Pfad-Traversal über den Dateinamen)."""
    return bool(_VALID_ROLE.match(role))


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (FileNotFoundError, IsADirectoryError, OSError):
        return None


def resolve_constitution(role: str | None, constitution_dir: str) -> ResolvedConstitution:
    """Liest global + (optional) Rollendatei und bildet die effektive Konstitution.

    Wirft ``ValueError`` bei ungültigem Rollennamen.
    """
    global_text = (_read(os.path.join(constitution_dir, "global.md")) or "").strip()

    if role is None:
        return ResolvedConstitution(text=global_text, source="global" if global_text else "leer", role=None)

    if not is_valid_role(role):
        raise ValueError(f"Ungültiger Rollenname '{role}'. Erlaubt: Buchstaben, Ziffern, '-', '_'.")

    role_raw = _read(os.path.join(constitution_dir, "roles", f"{role}.md"))
    if role_raw is None:
        # Rolle ohne eigene Datei → globale Konstitution gilt (Edge-Case der Spec).
        src = "global" if global_text else "leer"
        return ResolvedConstitution(text=global_text, source=src, role=role)

    role_text = role_raw.strip()
    first_line = role_text.splitlines()[0].strip() if role_text else ""
    if first_line == REPLACE_MARKER:
        body = "\n".join(role_text.splitlines()[1:]).strip()
        return ResolvedConstitution(text=body, source=f"rolle:{role} (replace)", role=role)

    # Append-Modus (Default).
    if global_text and role_text:
        return ResolvedConstitution(text=f"{global_text}\n\n{role_text}", source=f"global+rolle:{role}", role=role)
    text = role_text or global_text
    return ResolvedConstitution(text=text, source=f"rolle:{role}" if role_text else "global", role=role)


def list_roles(constitution_dir: str) -> list[str]:
    """Vorhandene Rollen (Dateinamen ohne .md) im roles/-Verzeichnis."""
    roles_dir = os.path.join(constitution_dir, "roles")
    try:
        names = [f[:-3] for f in os.listdir(roles_dir) if f.endswith(".md")]
    except (FileNotFoundError, NotADirectoryError, OSError):
        return []
    return sorted(names)


def combine_with_extra(constitution_text: str, extra: str | None) -> str:
    """Hängt einen optionalen, session-spezifischen Zusatz NACH der Konstitution an.

    Der Zusatz kann die Konstitution nicht entfernen (zentrale Enforcement, #24).
    """
    extra = (extra or "").strip()
    if constitution_text and extra:
        return f"{constitution_text}\n\n{extra}"
    return constitution_text or extra
