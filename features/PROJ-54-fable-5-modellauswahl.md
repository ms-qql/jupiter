# PROJ-54: Fable 5 als wählbares Claude-Modell (temporär)

## Status: Architected
**Created:** 2026-07-02
**Last Updated:** 2026-07-02

## Kontext / Motivation
Anthropic hat Fable 5 vorgestellt — laut Anbieter das **leistungsstärkste Modell**, aber
nur **zeitlich begrenzt** (ca. eine Woche) verfügbar. Jupiters eingebaute `claude`-Engine
kennt bislang ausschließlich die Aliase `haiku`, `sonnet`, `opus`; eine Fable-Session wird
an der Pydantic-Validierung mit „Unbekanntes Modell" abgewiesen. Die Claude-Code-CLI
(v2.1.190) akzeptiert `fable` bereits als offiziellen `--model`-Alias — es fehlt nur die
Freischaltung auf Jupiter-Seite.

**Sonnet 5 ist NICHT Teil dieses Features:** Der Alias `sonnet` wird 1:1 an `claude --model`
durchgereicht; die CLI löst ihn selbst auf die jeweils aktuelle Sonnet-Version (Sonnet 5)
auf. Dafür ist kein Code-Change nötig (nur eine aktuelle CLI-Binary auf dem VPS).

## Scope
- **A1 — nur der Neue-Session-Dialog.** Fable ist im Modell-Dropdown beim Session-Start
  wählbar. **Nicht** als Default in den App-Einstellungen und **nicht** in den Micro-Apps
  (Video Summary, Buch-Nuggets behalten `sonnet`/`opus`), weil Fable nach ~1 Woche verfällt
  und ein fixer Default dann Laufzeitfehler erzeugen würde.
- **B2 — Label „temporär".** Fable erscheint im Dropdown mit sprechendem, als flüchtig
  gekennzeichnetem Label (z. B. „Fable 5 (temporär)").

## Dependencies
- Requires: PROJ-1 (Engine-Treiber: Claude headless) — reicht `--model` an die CLI durch.
- Bezug: PROJ-51 (Engine-/Modellverwaltung), PROJ-19/PROJ-52 (Usage/Token-Zuordnung via `_model_alias`).

## User Stories
- Als Solo-Entwickler möchte ich beim Session-Start **Fable 5** als Modell auswählen können,
  um für anspruchsvolle Aufgaben das leistungsstärkste Modell zu nutzen, solange es verfügbar ist.
- Als Solo-Entwickler möchte ich im Dropdown **erkennen, dass Fable temporär** ist, damit ich
  weiß, dass diese Wahl nur begrenzt funktioniert.
- Als Solo-Entwickler möchte ich, dass eine **Fable-Session korrekt in der Token-/Usage-Ansicht**
  auftaucht (nicht „n/v"), damit die Kosten-/Verbrauchssicht vollständig bleibt.
- Als Solo-Entwickler möchte ich, dass **Sonnet 5 automatisch** greift, ohne etwas umzustellen.

## Acceptance Criteria
- [ ] Im Neue-Session-Dialog ist `fable` als viertes Claude-Modell wählbar (neben haiku/sonnet/opus).
- [ ] Der Eintrag trägt ein Label, das Fable als **temporär**/zeitlich begrenzt kennzeichnet
      (z. B. „Fable 5 (temporär)"), umgesetzt über die bestehende `modelLabel()`-Funktion.
- [ ] Eine mit `fable` gestartete Claude-Session wird vom Backend **akzeptiert** (kein
      „Unbekanntes Modell"-Fehler) und startet einen `claude --model fable`-Subprozess.
- [ ] Die Usage-/Token-Zuordnung erkennt Fable: `_model_alias()` mappt eine aufgelöste
      `claude-fable-…`-ID zurück auf den Alias `fable` (kein „n/v").
- [ ] `sonnet` bleibt unverändert und wird von der CLI automatisch auf Sonnet 5 aufgelöst —
      **keine** Jupiter-Code-Änderung dafür nötig (nur als Regressions-/Doku-Check).
- [ ] Fable ist **nicht** Default in App-Einstellungen und **nicht** in den Micro-Apps
      (Video Summary/Buch-Nuggets unverändert).
- [ ] Bestehende Sessions (haiku/sonnet/opus) sowie Fremd-Engines (Codex/OpenRouter/…) sind
      unverändert (keine Regression).

## Edge Cases
- **Fable-Verfügbarkeit endet:** Nach Ablauf lehnt die CLI `--model fable` ggf. zur Laufzeit
  ab. Die Session soll dann sauber als fehlgeschlagen enden (klare Fehlermeldung), nicht still
  hängen. Das „temporär"-Label ist der präventive Hinweis; ein aktives Deaktivieren beim
  Ablauf ist **nicht** Teil dieses Features.
- **Veraltete CLI-Binary:** Kennt die installierte `claude`-CLI `fable` nicht, schlägt der
  Start fehl → gleiche Fehlerbehandlung wie oben; Abhilfe ist ein CLI-Update (kein Code).
- **Usage-Mapping-Kollision:** Der Substring-Match in `_model_alias()` muss `fable` eindeutig
  erkennen, ohne haiku/sonnet/opus zu beeinträchtigen (disjunkte Aliase → unkritisch).
- **Fable bei Fremd-Engines:** `fable` ist ein reiner Claude-Alias; für Nicht-Claude-Engines
  bleibt die Modellliste aus `engines.yaml` maßgeblich (Fable taucht dort nicht auf).
- **Default nach Engine-Wechsel:** Der Standard neuer Sessions bleibt `sonnet`; Fable muss
  bewusst gewählt werden.

## Technical Requirements (optional)
- **Betroffene Allowlist-Stellen (4 + Label):**
  - `backend/app/config.py:49` — `VALID_MODELS` um `"fable"` erweitern.
  - `backend/app/schemas/sessions.py:10-11` — `ModelName`-Literal + `CLAUDE_MODELS` um `fable`.
  - `backend/app/engine/manager.py:163` — Alias-Liste in `_model_alias()` um `fable`.
  - `nextjs_app/lib/types.ts` — `ModelName` um `"fable"`; `new-session-dialog.tsx:65,114`
    (Fallback-Modelliste) + `modelLabel()` in `nextjs_app/lib/status.ts:198` fürs Label.
- **Kein neuer Treiber-Code:** Fable läuft über die bestehende eingebaute `claude`-Engine.
- **Security:** unverändert (Single-User-MVP; `owner` serverseitig gestempelt); keine neuen
  Env-Vars, keine Secrets. Keine RLS-/Auth-Änderung.
- **Browser Support:** Chrome/Firefox/Safari (Next.js web).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-02 · **Stack:** Next.js 16 (App Router) + FastAPI (eingebaute `claude`-Engine) · **Branch:** dev

### Kern der Entscheidung
Fable 5 ist **kein neues Engine-Profil und kein neuer Treiber** — es ist ein weiteres Modell
der bereits existierenden, eingebauten `claude`-Engine. Jupiter reicht den Modell-Alias
(`haiku`/`sonnet`/`opus`) unverändert an die Claude-Code-CLI durch; die CLI kennt `fable`
schon offiziell. Das Feature besteht deshalb ausschließlich darin, `fable` durch **eine
kurze Allowlist-Kette** freizuschalten, die heute hart auf drei Modelle steht. Keine DB,
kein MinIO, keine neue API-Route, kein neuer Endpunkt.

### A) Betroffene Bausteine (statt Component-Tree)
```
Neue-Session-Dialog (Frontend)
└── Modell-Dropdown
    ├── zeigt jetzt 4 Optionen: Haiku · Sonnet · Opus · Fable 5 (temporär)
    └── Auswahl „fable" → geht als model-Feld an den Session-Start-Request

Session-Start (Backend, eingebaute claude-Engine)
├── Eingangs-Validierung  → akzeptiert „fable" (bisher: nur haiku/sonnet/opus)
├── Subprozess-Start      → claude --model fable   (unverändert durchgereicht)
└── Usage-/Token-Zuordnung → erkennt aufgelöste „claude-fable-…"-ID als Alias „fable"
```

### B) Datenmodell
Unverändert. `model` ist ein bereits existierendes Freitext-/Alias-Feld an der Session;
es kommt lediglich ein zulässiger Wert (`fable`) hinzu. Keine Migration, keine RLS-Änderung.

### C) API-Form
Keine neuen Endpunkte. Der bestehende Session-Start-Request trägt weiterhin ein `model`-Feld;
seine erlaubte Wertemenge wächst von `{haiku, sonnet, opus}` auf `{haiku, sonnet, opus, fable}`.

### D) Tech-Entscheidungen (Begründung)
- **Warum nur Allowlist statt Engine-Eintrag?** Die eingebaute `claude`-Engine ist reserviert
  und definiert ihre Modelle im Code (nicht in `engines.yaml`). Fable gehört genau dorthin —
  ein `engines.yaml`-Eintrag wäre der falsche Ort und würde einen zweiten Claude-Kanal erzeugen.
- **Warum kein aktives Ablauf-Handling?** Fable ist ~1 Woche verfügbar. Ein Auto-Deaktivieren
  bei Ablauf wäre unverhältnismäßiger Aufwand (Zeit-/Verfügbarkeits-Polling). Stattdessen:
  präventives **„temporär"-Label** + saubere Laufzeit-Fehlermeldung, falls die CLI `fable`
  nach Ablauf ablehnt. Bewusste Kosten-/Nutzen-Entscheidung.
- **Warum nicht als Default/Micro-App-Modell?** Ein flüchtiges Modell als fixer Default würde
  nach Ablauf reproduzierbar Sessions/Jobs brechen. Fable bleibt eine bewusste Ad-hoc-Wahl im
  Dialog (Scope A1).
- **Sonnet 5 = Nicht-Feature:** Der `sonnet`-Alias wird CLI-seitig automatisch auf Sonnet 5
  aufgelöst; die Substring-Rückabbildung (`_model_alias`, `modelLabel`) trägt „sonnet" weiterhin.
  Kein Code-Change — nur die CLI-Binary auf dem VPS aktuell halten (Regressions-/Doku-Punkt).

### E) Abhängigkeiten
Keine neuen Pakete (Frontend wie Backend). Voraussetzung ist allein eine Claude-Code-CLI, die
`fable` als `--model`-Alias kennt — auf dem VPS mit v2.1.190 **verifiziert vorhanden**.

### Verantwortliche Spezialisten
- **Backend-Developer** (`/abc-backend`): Allowlist an 3 Stellen — `config.py:49` (`VALID_MODELS`),
  `schemas/sessions.py:10-11` (`ModelName`/`CLAUDE_MODELS`), `manager.py:163` (`_model_alias`).
- **Frontend-Developer** (`/abc-frontend`): `lib/types.ts` (`ModelName`), `new-session-dialog.tsx`
  (Fallback-Listen Z. 65 & 114), `lib/status.ts:198` (`modelLabel` → „Fable 5 (temporär)").

## Implementation Notes — Backend (/abc-backend, 2026-07-02)
Reine Allowlist-Freischaltung, kein neuer Code-Pfad:
- `backend/app/config.py:49` — `VALID_MODELS` um `"fable"` erweitert (+ Kommentar zu Temporär-Charakter/Laufzeit-Ablehnung).
- `backend/app/schemas/sessions.py:10-11` — `ModelName`-Literal + `CLAUDE_MODELS` um `fable`.
- `backend/app/engine/manager.py:163` — `_model_alias()` mappt `claude-fable-…` → `fable` (Usage/Token-Zuordnung).
- Tests: `backend/tests/test_manager.py` — `test_fable_model_accepted` (Session mit `model="fable"` wird akzeptiert) + `test_model_alias_maps_fable` (Rückabbildung, keine Kollision mit sonnet).
- Verifikation: `test_manager.py` 12/12, `test_proj51_engine_settings` + `test_proj19_usage` 16/16 grün.

**Offen für Frontend (/abc-frontend):** `lib/types.ts` (`ModelName`), `new-session-dialog.tsx:65,114` (Fallback-Listen), `lib/status.ts:198` (`modelLabel` → „Fable 5 (temporär)").

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
