# PROJ-9: Smart Launcher — mitdenkender Session-Start

## Status: Approved
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #12

## Dependencies
- Requires: PROJ-3 (Cockpit / `NewSessionDialog`) — der Launcher ersetzt/erweitert den heutigen „Neue Session"-Dialog.
- Requires: PROJ-1 (Engine-Treiber) — startet die Session mit gewähltem Skill/Modell.
- Verwandt: PROJ-6 (Konstitution/Rollen) — Rollen-Vorschlag korreliert mit der abc-Phase. PROJ-8 (Gantt) — nutzt dieselbe Phasen-/Feature-Logik.

## Beschreibung
Der „Neue Session"-Start ist kein leeres Formular mehr, sondern ein **Vorschlag aus dem eigenen Workflow**: Jupiter liest die `features/INDEX.md` des gewählten Projekts, erkennt das nächste sinnvolle Feature + die nächste ABC-Phase und schlägt **Skill, Rolle und Modell** vor. Default-Engine bleibt Claude Max. Der Nutzer bestätigt oder überschreibt.

## User Stories
- Als Nutzer möchte ich beim Session-Start einen konkreten Vorschlag (Feature + nächste abc-Phase + Skill) sehen, damit ich nicht selbst in der INDEX.md nachschlagen muss.
- Als Nutzer möchte ich den vorgeschlagenen Skill/Rolle/Modell mit einem Klick übernehmen oder einzeln überschreiben.
- Als Nutzer möchte ich, dass das passende Modell (Haiku/Sonnet/Opus) zur Phase vorgeschlagen wird (z. B. Opus für Architektur, Haiku für mechanische Phasen).
- Als Nutzer möchte ich für Ad-hoc-Arbeit den Vorschlag ignorieren und frei einen Prompt eingeben können.
- Als Nutzer möchte ich, dass Projekte ohne `features/INDEX.md` trotzdem startbar sind (Freitext-Modus).

## Acceptance Criteria
- [x] Beim Öffnen des Dialogs nach Projektwahl wird die `features/INDEX.md` des Projekts gelesen und das **nächste empfohlene Feature** ermittelt. Auswahl = **„Fortsetzen-First"** (BUG-1, Produktentscheidung 2026-06-23): unter allen offenen (≠ Deployed) Features der **reifste Dev-Stand zuerst** — In Review → In Progress → Architected → Planned; **Approved** wird ans Ende gestellt (nur noch human-gated Deploy offen). Tie-Break: höhere Prio, dann Dokument-Reihenfolge.
- [ ] Aus dem Feature-Status wird die **nächste abc-Phase** abgeleitet (z. B. Status „Architected" → nächste Phase „Frontend/Backend") und der zugehörige `abc-*`-Skill vorgeschlagen.
- [ ] Es wird ein **Modell-Vorschlag** je Phase angezeigt (mappingbasiert, überschreibbar).
- [ ] Der Vorschlag ist mit **einem Klick übernehmbar** („Vorschlag starten") und füllt Skill, Rolle, Modell, Initial-Prompt vor.
- [ ] Jedes Feld bleibt **manuell überschreibbar** (Phase, Skill, Modell, Prompt).
- [ ] Projekt ohne `features/INDEX.md` → Hinweis „Kein abc-Workflow erkannt" + Fallback auf den heutigen Freitext-Dialog, ohne Fehler.
- [ ] Der gewählte Skill + sein Argument werden so an die Session übergeben, dass PROJ-8 daraus `abc_phase`/`abc_feature` lesen kann.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Leer-Zustände explizit.

## Edge Cases
- **INDEX.md leer / nur Deployed-Features** → Vorschlag „Alle Features deployed — neues Feature mit `/abc-requirements`?".
- **Mehrere Features in Arbeit** → „Fortsetzen-First": reifsten offenen Dev-Stand zuerst (Approved ans Ende), Tie-Break höhere Prio; restliche als Auswahlliste anbieten.
- **Status nicht parsebar** (manuell editierte INDEX) → robust degradieren auf Freitext, kein Crash.
- **Projektpfad außerhalb erlaubter Roots** → gleiche Scope-Prüfung wie heute (`validate_project_path`), klare Fehlermeldung.
- **Skill ohne klaren Phasenbezug** (z. B. refactor) → kein Phasen-Vorschlag, nur Modell/Prompt.

## Technical Requirements (optional)
- Datenquelle: Datei-Read der `features/INDEX.md` im Projekt (kein neuer DB-State).
- Phasen-/Modell-Mapping aus derselben zentralen Konstante wie PROJ-8 (`abc_phases`).
- Antwortzeit des Vorschlags < 300 ms (reiner File-Parse).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Next.js 16 (App Router) + FastAPI + Datei-Read (kein neuer DB-State) · **Branch:** dev

### Leitidee
Der Vorschlag ist **reine Ableitung aus der `features/INDEX.md`** des gewählten Projekts. Es entsteht **kein neuer DB-State**. Die gesamte Vorschlags-Logik lebt im **Backend** (eine Quelle der Wahrheit, teilt das `abc_phases`-Mapping mit PROJ-8); das Frontend zeigt den Vorschlag nur an und lässt jedes Feld überschreiben.

### A) Komponenten-Struktur (Frontend)
Erweiterung des bestehenden Dialogs ([new-session-dialog.tsx](../nextjs_app/components/cockpit/new-session-dialog.tsx)) — kein neuer Dialog:
```
NewSessionDialog
├── ProjektAuswahl (bestehend: project_path)
│   └── onChange → ruft Vorschlag ab (GET /projects/suggestion)
├── VorschlagsCard (NEU) — erscheint nach Projektwahl
│   ├── "Nächstes Feature: PROJ-X — <Titel> (Status)"
│   ├── "Nächste Phase: <Phase> → Skill <abc-…>"
│   ├── Modell-Vorschlag (Badge, z. B. Opus)
│   ├── Button "Vorschlag starten" (füllt alle Felder vor)
│   └── Mehr-Optionen: Auswahlliste, falls mehrere Features in Arbeit
├── Skill-Feld (NEU, vorbelegt, überschreibbar)
├── Modell-Select (bestehend, vom Vorschlag vorbelegt)
├── Rolle / extra_system_prompt (bestehend im Schema, im Dialog ergänzen)
├── Prompt-Feld (bestehend, vom Vorschlag vorbelegt)
└── HinweisBanner (NEU) "Kein abc-Workflow erkannt — Freitext-Modus"
```

### B) Datenmodell (Klartext)
Kein persistenter Zustand. Zur Laufzeit berechnet aus der INDEX.md:
```
Vorschlag (flüchtig, pro Dialog-Öffnung):
- projekt_pfad
- nächstes_feature: { id (PROJ-X), titel, status, prio }
- nächste_phase: eine der abc-Phasen (oder leer)
- skill: abc-<phase>  (oder leer bei nicht-Phasen-Arbeit)
- modell: haiku | sonnet | opus  (aus Phasen→Modell-Mapping)
- initial_prompt: vorgeschlagener Startsatz inkl. Feature-Nummer
- alternativen: Liste weiterer offener Features (für Auswahl)
- abc_erkannt: true/false  (false → Freitext-Fallback)
```
Quelle: Datei-Read der `features/INDEX.md` (Parsing der Status-Tabelle). Pfad-Scope wie heute über `validate_project_path` ([manager.py:85](../backend/app/engine/manager.py#L85)).

### C) API-Form (nur Endpoints, kein Code)
```
GET /projects/suggestion?project_path=<pfad>
    → liest features/INDEX.md, gibt das oben beschriebene Vorschlag-Objekt zurück.
    → 200 mit abc_erkannt=false, wenn keine/leere INDEX.md (kein Fehler).
    → 400 bei Pfad außerhalb der erlaubten Roots (validate_project_path).
```
- **Kein neuer Start-Endpoint:** Session-Start bleibt `POST /sessions` ([sessions.py:32](../backend/app/routes/sessions.py#L32)). Das vorhandene `SessionCreate`-Schema deckt `model`, `role`, `extra_system_prompt`, `initial_prompt` bereits ab.
- **Skill-Übergabe an die Session:** Der Vorschlag formuliert den `initial_prompt` so, dass er mit dem Skill-Aufruf beginnt (z. B. `/abc-architecture 9`). Damit greift der bestehende `detect_phase_signal`-Hook ([abc_phases.py:95](../backend/app/engine/abc_phases.py#L95)) und PROJ-8 liest `abc_phase`/`abc_feature` ohne Schemaänderung.

### D) Status → nächste Phase → Skill → Modell (zentrale Ableitung)
Lebt neben `abc_phases.py` (eine Quelle der Wahrheit, von PROJ-8 mitgenutzt):

| INDEX-Status | nächste abc-Phase | vorgeschlagener Skill | Modell-Default |
|---|---|---|---|
| (keine/leere INDEX) | requirements | `abc-requirements` | Opus |
| Planned | architecture | `abc-architecture` | Opus |
| Architected | frontend | `abc-frontend` | Sonnet |
| In Progress | backend | `abc-backend` | Sonnet |
| In Review | qa | `abc-qa` | Sonnet |
| Approved | deploy | `abc-deploy` | Haiku |
| Deployed | — (Hinweis: neues Feature) | — | — |

- **„Nächstes Feature"** = erste Tabellenzeile, deren Status ≠ „Deployed". Bei mehreren offenen Features: das mit dem geringsten Reifegrad (kleinster Phasen-Index), bei Gleichstand höhere Prio; restliche als `alternativen`.
- **Modell-Mapping** ist überschreibbar und wird als überschreibbare Konstante geführt (Denk-/Design-Phasen → Opus, Bau/QA → Sonnet, mechanische Phasen → Haiku).
- **Robust degradieren:** nicht parsebare Status-Zeile → `abc_erkannt=false`, Freitext-Fallback statt Crash.

### E) Tech-Entscheidungen (Begründung)
- **Logik im Backend, nicht im Frontend:** Das Phasen-/Skill-/Modell-Mapping existiert bereits im Backend (`abc_phases.py`, geteilt mit PROJ-8/Gantt). Doppelte Pflege im Frontend würde auseinanderlaufen. Frontend bleibt „dumm" (anzeigen + überschreiben).
- **Kein neuer DB-State / kein neues Schema:** Der Vorschlag ist eine reine Funktion der Projektdateien. Das hält die <300 ms-Anforderung (reiner File-Parse) und vermeidet Migrationsaufwand.
- **INDEX.md statt einzelner Spec-Files lesen:** Die INDEX-Tabelle hat Status + Prio aller Features kompakt an einer Stelle — ein Read genügt, keine Verzeichnis-Scans.
- **Wiederverwendung des `POST /sessions`-Pfads:** Der Skill wird über den `initial_prompt` transportiert; der bestehende Detektor verknüpft Session ↔ Phase/Feature automatisch. Kein neuer Start-Weg, keine Sonderbehandlung.
- **Scope-Sicherheit:** derselbe `validate_project_path`-Guard wie heute — der Launcher öffnet keinen neuen Angriffsweg auf das Dateisystem.

### F) Abhängigkeiten (Pakete)
- Keine neuen Pakete. Backend: Datei-Read + Regex-Parse (stdlib) wiederverwendet die Muster aus `abc_phases.py` / `md_reader.py`. Frontend: bestehender API-Client + shadcn/ui-Komponenten (Card, Badge, Button, Select).

### Neu zu bauen (Zusammenfassung für Frontend/Backend)
- **Backend:** `GET /projects/suggestion` (Route + Pydantic-Response-Schema), INDEX.md-Parser, Status→Phase/Skill/Modell-Mapping neben `abc_phases.py`.
- **Frontend:** VorschlagsCard + Skill-/Rolle-Felder im `NewSessionDialog`, Abruf nach Projektwahl, „Vorschlag starten"-Vorbelegung, Freitext-Fallback-Banner, Lade-/Fehler-/Leer-Zustände.

## Backend-Implementierung (Backend Developer)
**Datum:** 2026-06-23 · **Branch:** dev

### Gebaut
- **Mapping (Quelle der Wahrheit, geteilt mit PROJ-8)** in [`backend/app/engine/abc_phases.py`](../backend/app/engine/abc_phases.py): `PHASE_TO_SKILL`, `PHASE_TO_MODEL`, `STATUS_TO_NEXT_PHASE`, `STATUS_ORDER` + Helfer (`normalize_status`, `status_maturity`, `next_phase_for_status`, `skill_for_phase`, `model_for_phase`). Status-/Phasen-Logik liegt damit an EINER Stelle (kein Frontend-Duplikat).
- **LauncherService** in [`backend/app/engine/launcher.py`](../backend/app/engine/launcher.py): header-basierter INDEX.md-Parser (robust gegen Spaltenreihenfolge, strippt Markdown-Links in der Titel-Spalte, ignoriert Roadmap-Listen), Auswahl des nächsten Features (geringster Reifegrad → höhere Prio → Dokument-Reihenfolge), Sonderfälle. Pfad-Scope via bestehendem `validate_project_path`.
- **Schema** [`backend/app/schemas/projects.py`](../backend/app/schemas/projects.py): `FeatureRef`, `LaunchSuggestion`.
- **Route** [`backend/app/routes/projects.py`](../backend/app/routes/projects.py): `GET /projects/suggestion?project_path=…` (registriert in `main.py`, `app.state.launcher`).

### API-Vertrag (für Frontend)
`GET /projects/suggestion?project_path=<pfad>` → `200` `LaunchSuggestion`:
```
{
  project_path, abc_erkannt: bool, hinweis: str|null,
  naechstes_feature: { id, number, title, status, prio } | null,
  naechste_phase: str|null, skill: str|null,
  modell: "haiku"|"sonnet"|"opus"|null, initial_prompt: str|null,
  alternativen: FeatureRef[]
}
```
- `400` bei Pfad außerhalb der erlaubten Roots.
- Session-Start unverändert über `POST /sessions`; der Vorschlags-`initial_prompt` beginnt mit dem Skill-Aufruf (z. B. `/abc-architecture 9`) → bestehender `detect_phase_signal`-Hook verknüpft Phase/Feature automatisch (PROJ-8). Kein Schema-Change an `SessionCreate`.

### Verhalten / Edge Cases (alle getestet)
- Keine `features/INDEX.md` → `abc_erkannt=false`, Freitext-Hinweis (kein Fehler).
- Nur/alle Deployed → `abc_erkannt=true`, Vorschlag `abc-requirements` (Opus), kein Feature.
- Nicht parsebare Status → degradiert auf Freitext (`abc_erkannt=false`), kein Crash.
- Reordered Spalten / verlinkte Titel → robust geparst.

### Tests
[`backend/tests/test_proj9_smart_launcher.py`](../backend/tests/test_proj9_smart_launcher.py) — 20 Tests (Mapping, Parser, Auswahl, Sonderfälle, REST + 400). **Volle Suite: 345 passed, 2 xfailed.**

### Offen für Frontend (`/abc-frontend`)
VorschlagsCard + Skill-/Rolle-Felder im `NewSessionDialog`, Abruf nach Projektwahl, „Vorschlag starten"-Vorbelegung, Freitext-Fallback-Banner, Lade-/Fehler-/Leer-Zustände.

> **Vertrags-Anpassung während `/abc-frontend`:** Jede Feature-Option (Empfehlung + Alternativen) trägt jetzt ihre EIGENEN abgeleiteten Felder (`phase`/`skill`/`modell`/`initial_prompt`) als `FeatureSuggestion`. So muss das Frontend beim Umschalten auf eine Alternative keine Mapping-Logik duplizieren — Single Source of Truth bleibt das Backend. Response-Felder: `empfehlung: FeatureSuggestion|null`, `alternativen: FeatureSuggestion[]`, plus Top-Level-Default (`skill`/`modell`/`naechste_phase`/`initial_prompt`) für „Übernehmen" bzw. den /abc-requirements-Sonderfall.

## Frontend-Implementierung (Frontend Developer)
**Datum:** 2026-06-23 · **Stack:** Next.js 16 + shadcn/ui · **Branch:** dev

### Gebaut
- **Typen** in [`nextjs_app/lib/types.ts`](../nextjs_app/lib/types.ts): `FeatureSuggestion`, `LaunchSuggestion` (spiegeln die Backend-Schemas).
- **API-Client** in [`nextjs_app/lib/api.ts`](../nextjs_app/lib/api.ts): `getLaunchSuggestion(projectPath, signal)` → `GET /projects/suggestion`.
- **Dialog** [`nextjs_app/components/cockpit/new-session-dialog.tsx`](../nextjs_app/components/cockpit/new-session-dialog.tsx) erweitert (kein neuer Dialog):
  - Debounced (300 ms, abbrechbar via `AbortController`) Abruf des Vorschlags nach Projektpfad-Eingabe, solange der Dialog offen ist.
  - `SuggestionCard` mit allen Zuständen: **Laden** (Skeleton), **Fehler** (nicht-blockierend, Freitext bleibt), **kein abc-Workflow** (Hinweis-Banner), **alle deployed** (`/abc-requirements`-Übernehmen), **Erfolg** (Feature + Status→Phase + Skill-Badge + Modell-Badge).
  - „Vorschlag starten" belegt Prompt + Modell vor; **Alternativen** als klickbare Chips (jede mit eigenen Feldern).
  - Neues **Rolle (optional)**-Feld (→ `role` in `SessionCreate`).
  - Skill reist im editierbaren `initial_prompt` (`/abc-architecture 9`) — Hinweistext erklärt das; PROJ-8 liest Phase/Feature automatisch.
- Jedes Feld (Prompt, Modell, Rolle, Berechtigung) bleibt manuell überschreibbar.

### Verifikation
- `npm run lint` ✅ · `tsc --noEmit` ✅ (keine Fehler in den PROJ-9-Dateien; ein vorbestehender `tsc`-Fehler in `lib/md-tree.test.ts` ist nicht Teil dieses Features).
- `npx vitest run` → 47 Tests grün.
- Backend-Vollsuite nach Vertragsänderung: **348 passed**.

> Hinweis: visuelle Browser-Abnahme (`/abc-qa-e2e`) steht noch aus.

## QA Test Results
**Getestet:** 2026-06-23 · **Branch:** dev · **Tester:** QA Engineer

### Zusammenfassung
- Akzeptanzkriterien: **8 bestanden** (AC1 nach BUG-1-Fix grün).
- Automatisierte Tests: **27 PROJ-9-Tests grün**; Backend-Vollsuite **355 passed**; Frontend `lint`/`tsc`/`vitest 47` grün.
- Security (Red-Team Pfad-Härtung): **keine Lücke gefunden**.
- **Production-Ready: JA** — BUG-1 (High) behoben; verbleibende Findings sind Low/Info. Status **Approved**.

> **Re-QA 2026-06-23 (nach BUG-1-Fix):** Sortierung auf „Fortsetzen-First" umgestellt (Produktentscheidung des Users). Verifiziert gegen die echte INDEX.md → Empfehlung jetzt **PROJ-9** (In Review → `/abc-qa 9`) statt eines frischen Planned-Features. AC1 ✅.

> Kontext: Jupiter ist ein Single-User-Tool ohne Mandanten/JWT/RLS/MinIO — die üblichen Tenant-Isolations-/Auth-Audits entfallen. Einzige Angriffsfläche von PROJ-9 ist der `project_path`-Query-Parameter (Datei-Scope).

### Akzeptanzkriterien
| # | Kriterium | Ergebnis |
|---|-----------|----------|
| 1 | Nächstes empfohlenes Feature (offen, ≠ Deployed) | ✅ — nach BUG-1-Fix: „Fortsetzen-First" (reifster offener Stand zuerst). AC-Text unten präzisiert |
| 2 | Nächste abc-Phase aus Status abgeleitet + Skill vorgeschlagen | ✅ |
| 3 | Modell-Vorschlag je Phase (mappingbasiert, überschreibbar) | ✅ |
| 4 | Vorschlag mit einem Klick übernehmbar (Skill/Rolle/Modell/Prompt) | ⚠️ teils — Skill (via Prompt)/Modell/Prompt ✅; **Rolle** ohne Datenquelle (FINDING-2) |
| 5 | Jedes Feld manuell überschreibbar | ✅ |
| 6 | Kein features/INDEX.md → Hinweis + Freitext-Fallback, kein Fehler | ✅ |
| 7 | Skill+Arg so übergeben, dass PROJ-8 `abc_phase`/`abc_feature` lesen kann | ✅ (via `initial_prompt` `/abc-<phase> <n>` → `detect_phase_signal`) |
| 8 | Alle Texte deutsch; Lade-/Fehler-/Leer-Zustände explizit | ✅ |

### Edge Cases
| Fall | Ergebnis |
|------|----------|
| INDEX.md leer / nur Deployed | ✅ Hinweis „Alle Features deployed … /abc-requirements" |
| Mehrere Features in Arbeit | ✅ Auswahlliste + Primär-Pick „Fortsetzen-First" (nach BUG-1-Fix) |
| Status nicht parsebar | ✅ degradiert auf Freitext (`abc_erkannt=false`) |
| Projektpfad außerhalb der Roots | ✅ `400` (validate_project_path) |
| Skill ohne Phasenbezug (refactor) | ✅ N/A — Vorschlag leitet nur aus Status ab (kein freier Skill-Pfad) |

### Bugs / Findings
**BUG-1 (High) — ✅ BEHOBEN (2026-06-23).** Fix: Sortierschlüssel von „geringster Reifegrad" auf **„Fortsetzen-First"** umgestellt (`abc_phases.selection_rank` + `launcher.py`). Reihenfolge: In Review → In Progress → Architected → Planned; **Approved ans Ende** (dessen einzige offene Stufe ist der human-gated Deploy — bleibt als Alternative wählbar, drängt aber nicht als Top-Vorschlag). Verifiziert + Regressionstests (`test_suggest_continue_first_*`). Ursprüngliche Beschreibung:

**Feature-Auswahl widerspricht AC1 und ist kontraintuitiv.**
- *Repro:* `GET /projects/suggestion?project_path=/home/dev/projects/jupiter` (echte INDEX.md).
- *Erwartet (AC1):* erste offene Zeile = **PROJ-9** (In Progress).
- *Tatsächlich:* **PROJ-12** (frisch *Planned*). Die Implementierung sortiert offene Features rein nach **Reifegrad** (`status_maturity`), wodurch ein neues *Planned*-Feature aktiv begonnene Arbeit (*In Progress* PROJ-9, *In Review* PROJ-10) ans Listenende drängt.
- *Wirkung:* Der „mitdenkende" Launcher empfiehlt, **neue** Architektur-Arbeit zu starten, statt angefangene Features fortzuführen — entwertet den Kernnutzen.
- *Ursache:* AC1 („erste offene Zeile") und die Edge-Case-Regel („geringster Reifegrad") **widersprechen sich**; der Code folgt nur Letzterer.
- *Empfehlung (Produktentscheidung nötig, Fix durch Backend):* Sortierschlüssel ändern. Sinnvolle Optionen:
  - **(a) Fortsetzen-First:** offene Features nach *größtem* Reifegrad < deployed (In Review → In Progress → Architected → Planned), Doku-Reihenfolge als Tie-Break → empfiehlt PROJ-10/PROJ-9. *(empfohlen — „weitermachen statt neu anfangen")*
  - **(b) Dokument-Reihenfolge** (wörtliche AC1): erste offene Zeile → PROJ-9.
  - **(c) Status quo** (geringster Reifegrad) + AC1 entsprechend anpassen.

**FINDING-2 (Low) — AC4 „Rolle vorbelegen" ohne Datenquelle.** Der Vorschlag enthält keinen Rollen-Vorschlag (Backend leitet keine Rolle aus der Phase ab). Das Rolle-Feld bleibt leer/manuell. Klären, ob ein Phase→Rolle-Mapping (vgl. PROJ-6 Rollen) gewünscht ist; sonst AC4 um „Rolle" bereinigen.

**FINDING-3 (Low) — Alternativen-Liste lang.** Bei jupiter erscheinen 14 offene Features als Chips (inkl. *Approved*, deren nächste Phase korrekt „deploy" ist). Funktional ok, aber potenziell unübersichtlich — ggf. begrenzen/gruppieren (z. B. „in Arbeit" vs. „neu").

**FINDING-4 (Info, kein Fix) — Symlink-Read.** `features/INDEX.md` wird nach `validate_project_path` ohne erneute Symlink-Prüfung geöffnet. Da nur **geparste Metadaten** (keine Rohinhalte) zurückgegeben werden und es ein Single-User-Tool mit eigenen Roots ist, besteht kein praktischer Leak. Dokumentiert.

**FINDING-5 (Info) — Toter Zweig.** Der `"Arbeite an PROJ-X"`-Prompt-Zweig in `_feature_suggestion` ist unerreichbar (nur erkannte Status erreichen die Funktion, alle mappen auf eine Phase). Harmlos.

### Security-Audit (Red-Team, Pfad-Scope)
Alle als Regressionstests fixiert (`test_proj9_smart_launcher.py`):
- Absoluter Traversal (`/etc`) → `400` ✅
- Relativer Traversal (`…/../../etc`) → `400` ✅
- Null-Byte-Injection (`…\x00/etc/passwd`) → `400` ✅
- Nicht-existentes Verzeichnis innerhalb Root → `400` ✅
- Keine Rohinhalte in der Response (nur Feature-Metadaten) ✅

### Regression
Backend-Vollsuite **348 passed** (inkl. PROJ-8-Gantt, das dieselbe `abc_phases`-Konstante teilt — kein Bruch durch die neuen Mappings). Frontend `vitest` 47/47, `lint`/`tsc` (PROJ-9-Dateien) sauber.

### Neue/erweiterte Tests
- [`backend/tests/test_proj9_smart_launcher.py`](../backend/tests/test_proj9_smart_launcher.py) — 27 Tests (Mapping, Parser, „Fortsetzen-First"-Reihenfolge, Sonderfälle, REST, Red-Team Pfad-Härtung, Approved-als-offen).

### Re-QA Runde 2 — Live-Verifikation (2026-06-23)
Bisher nur TestClient/Unit; diese Runde gegen einen **laufenden uvicorn** + Production-Build:
- **Next.js `npm run build`** ✅ (TypeScript kompiliert, alle Seiten generiert) — stärker als nur `tsc`/`lint`.
- **Backend-Vollsuite** erneut **355 passed**.
- **Live-HTTP** (`uvicorn` auf Testport):
  - Happy `?project_path=/home/dev/projects/jupiter` → `200`, `abc_erkannt=true`, valide Empfehlung + Default-Prompt + Alternativen.
  - Traversal `/etc` → `400` · Null-Byte → `400` · fehlender Pflichtparameter → `422` · Projekt ohne `features/INDEX.md` → `200` mit Freitext-Hinweis · CORS-Preflight vom Frontend-Origin → `200`.
- Beobachtung (kein Bug): Die Live-Empfehlung folgt der aktuellen INDEX.md; bei parallelen Sessions ändert sich der Top-Vorschlag entsprechend — „Fortsetzen-First" wählt stets den reifsten offenen Dev-Stand.
- Hinweis: rein visuelle Browser-Interaktion (Klick „Vorschlag starten", State-Rendering) bleibt `abc-qa-e2e` vorbehalten; der Dialog-Code ist über Build + `vitest`/`lint`/`tsc` abgesichert.

**Production-Ready (Runde 2): JA** — Status bleibt **Approved**.

## Deployment
_To be added by /abc-deploy_
