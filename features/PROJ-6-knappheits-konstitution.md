# PROJ-6: Knappheits-Konstitution

## Status: In Progress
**Created:** 2026-06-22
**Last Updated:** 2026-06-22 (Backend implementiert)

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — Konstitution wird beim Session-Start injiziert

## Beschreibung
Output-Kultur zentral durchgesetzt (#24): ein global gepflegter System-Prompt („Konstitution"), der bei jedem Session-Start injiziert wird und Disziplin erzwingt — keine Vorreden, keine Wiederholungen, keine „Soll ich…?"-Schleifen. Pro Rolle/Skill überschreibbar. Klein, aber prägt das Verhalten **aller** Sessions (deshalb früh in der Bau-Reihenfolge).

## User Stories
- Als Nutzer möchte ich, dass alle Sessions standardmäßig knapp und ohne Geschnatter antworten, um Tokens zu sparen.
- Als Nutzer möchte ich die Konstitution pro Rolle überschreiben können, wenn eine Rolle bewusst mehr Ausführlichkeit braucht.
- Als Nutzer möchte ich die effektive Konstitution einer Session einsehen können (Transparenz).

## Acceptance Criteria
- [x] Ein zentral gepflegter globaler System-Prompt (Konstitution) wird beim Start jeder Session injiziert.
- [x] Inhalt erzwingt: keine Vorreden, keine Wiederholungen, keine „Soll ich…?"-Schleifen, knappe Antworten.
- [x] Pro Rolle/Skill kann die Konstitution ergänzt oder überschrieben werden.
- [x] Die **effektive** Konstitution einer Session (global + Rollen-Override) ist einsehbar.

## Edge Cases
- Rolle ohne Override → globale Konstitution gilt.
- Konflikt zwischen globaler Regel und Rollen-Regel → Rollen-Override gewinnt, nachvollziehbar dokumentiert.
- Leere/fehlende Konstitution → Session startet trotzdem (kein Hard-Fail).

## Technical Requirements (optional)
- Konstitution als **versioniertes Artefakt** (Vault/Config), nicht hartcodiert — so bleibt sie ohne Deploy editierbar.
- Zusammenspiel mit PROJ-1: Injektion beim `claude -p`-Start (System-Prompt-Mechanismus).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-22 · **Stack:** FastAPI + Postgres/Hal-Vault (UI später) · **Branch:** dev

### A) Komponenten-Struktur (Backend; Editieren der Konstitution später via MD-Reader #16)
```
Konstitution (Engine-Layer)
├── Konstitutions-Store (Dateien — editierbar ohne Deploy, Repo-versioniert)
│   ├── constitution/global.md            ← Basis-Konstitution (gilt IMMER)
│   └── constitution/roles/<rolle>.md     ← optionaler Zusatz/Override je Rolle
├── ConstitutionResolver (Service)
│   ├── liest global.md + roles/<rolle>.md FRISCH bei jedem Session-Start
│   ├── Modus: append (Default) | replace (Marker in Zeile 1 der Rollendatei)
│   └── liefert „effektive Konstitution" (Text) + Quelle (global / global+rolle / rolle-replace)
└── Einspeisung → LaunchSpec.system_prompt_append → `--append-system-prompt` (PROJ-1-Hook, existiert)
```

### B) Datenmodell (Klartext)
**Konstitutions-Store = Markdown-Dateien** (kein DB/Vault nötig im MVP):
- `global.md` — die Basisregeln als Prosa.
- `roles/<rolle>.md` — optionaler Text je Rolle. Beginnt die Datei mit dem Marker `<!-- mode: replace -->`, **ersetzt** sie die globale Konstitution; sonst wird sie **angehängt**.

**Session bekommt neue Felder:**
- `role` (optional, frei wählbarer String; ohne → nur global) — bis Smart Launcher (#12, P1) Rollen automatisch setzt, wird `role` beim Start übergeben.
- `effective_constitution` (der tatsächlich injizierte Text) + `constitution_source` (z. B. `global`, `global+rolle:backend`, `rolle:backend (replace)`) — für die Einsehbarkeit (AC).
- `extra_system_prompt` (optional, ersetzt das alte client-`system_prompt_append`): wird **immer NACH** der Konstitution angehängt — kann die Konstitution nicht entfernen.

**Default-Inhalt `global.md`** (Prosa, DE — editierbar): keine Vorreden/Floskeln; Frage nicht wiederholen; keine „Soll ich…?"-Rückfrage-Schleifen; direkt mit Antwort/Aktion beginnen; knappe, strukturierte Ausgaben; Code/Diffs ohne umschweifende Erklärungen.

### C) API-Form (nur Endpunkte, kein Code)
```
GET  /constitution                 → globale Konstitution + Liste vorhandener Rollen (Transparenz)
GET  /constitution/{role}          → effektive Konstitution einer Rolle (Vorschau)
GET  /sessions/{id}/constitution   → effektive Konstitution DIESER Session (role + text + source)  [AC]
POST /sessions  (erweitert)        → akzeptiert optional `role` und optional `extra_system_prompt`
GET  /sessions/{id}  (erweitert)   → enthält jetzt auch `role` + `constitution_source`
```
Der Resolver liest die Dateien bei **jedem** Start frisch → Edits wirken auf die nächste Session ohne Neustart/Deploy.

### D) Tech-Entscheidungen (warum)
- **Store als MD-Dateien, nicht DB/JSON.** Prosa bleibt lesbar/editierbar ohne Escaping; spiegelt die spätere Heimat im Hal-Vault (MD, Obsidian-DNA #16) → einfache Migration. „Ohne Deploy editierbar" erfüllt durch frisches Einlesen pro Session-Start.
- **Injektion über den bestehenden `--append-system-prompt`-Hook (PROJ-1).** Kein neuer Mechanismus. Ein vollständiger System-Prompt-Replace ist im Subscription-Headless weder nötig noch vorgesehen — die „Override"-Semantik der Spec ist Jupiter-intern (global vs. Rolle).
- **Konstitution server-autoritativ, NICHT pro-Request client-überschreibbar.** Das alte client-`system_prompt_append` entfällt; `extra_system_prompt` wird nur **zusätzlich** angehängt → zentrale Output-Enforcement (#24) bleibt gewahrt, Flexibilität bleibt erhalten.
- **Resolution im Manager** (vor der `LaunchSpec`-Erstellung). Single Responsibility; das Schema bleibt schlank; der effektive Text landet im `SessionState` → einsehbar.
- **append (Default) + replace (Marker)** erfüllt „ergänzt ODER überschrieben" ohne komplexes Konfig-Format.
- **Unbekannte/fehlende Rolle → global**; fehlende `global.md` → kein `--append-system-prompt`, Session startet trotzdem (Edge-Cases der Spec abgedeckt, kein Hard-Fail).

### E) Abhängigkeiten
**Keine neuen Pakete** — reine Datei-I/O + vorhandenes FastAPI/Pydantic. Default-Konstitution wird als MD-Datei mit dem Repo ausgeliefert (versioniert).

### Hinweis für /abc-backend
PROJ-1s client-`system_prompt_append` wird zu `extra_system_prompt` umbenannt und immer **hinter** die Konstitution gehängt; der QA-Test, der `system_prompt_append` referenziert, ist entsprechend anzupassen.

### Implementation Notes (Backend Developer)
**Datum:** 2026-06-22 · **Branch:** dev · **Stand:** Backend fertig, QA ausstehend · **Tests:** `pytest` → **59 grün** (17 neue für PROJ-6).

**Gebaute Teile:**
- **Store (MD):** `backend/constitution/global.md` (Default-Terseness-Regeln, DE) + `backend/constitution/roles/architect.md` (Append-Beispiel). Pfad via `settings.constitution_dir` (`JUPITER_CONSTITUTION_DIR`).
- **`engine/constitution.py`** — reiner Resolver: `resolve_constitution(role, dir)` (append/replace via Marker `<!-- mode: replace -->`), `is_valid_role` (Regex `^[A-Za-z0-9_-]{1,64}$` → verhindert Pfad-Traversal), `list_roles`, `combine_with_extra`. Liest Dateien bei **jedem** Aufruf frisch → Edits ohne Deploy wirksam.
- **`engine/manager.py`** — `create()` nimmt jetzt `role` + `extra_system_prompt`; löst die Konstitution auf, hängt `extra` dahinter, injiziert das Ergebnis über den bestehenden `LaunchSpec.system_prompt_append` → `--append-system-prompt`. `SessionState` trägt `role`, `constitution_source`, `effective_constitution`.
- **API:** `GET /sessions/{id}/constitution` (effektiv, AC) · `GET /constitution` (global + Rollen) · `GET /constitution/{role}` (Vorschau). `POST /sessions` akzeptiert `role` + `extra_system_prompt`; `GET /sessions/{id}` zeigt `role` + `constitution_source`.

**Umgesetzte Design-Entscheidung:** Das client-`system_prompt_append` aus PROJ-1 wurde **entfernt**; stattdessen `extra_system_prompt`, das **immer nach** der Konstitution angehängt wird → zentrale Output-Enforcement (#24) ist nicht client-umgehbar.

**Edge-Cases abgedeckt (Tests):** fehlende `global.md` → leer, kein Hard-Fail; Rolle ohne Datei → global; replace-Marker; ungültige Rolle → `ValueError`/422/400.

**Hinweis für QA:** Live-Wirkung (knappere Outputs) optional via `scripts/smoke_driver.py` prüfbar (injiziert jetzt automatisch die globale Konstitution) — verbraucht Quota, nicht in CI.

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
