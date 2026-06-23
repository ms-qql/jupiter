# PROJ-5: Context-Management & Handover

## Status: Architected
**Created:** 2026-06-22
**Last Updated:** 2026-06-23

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — Token-/Kontext-Daten je Session
- Requires: PROJ-2 (Vault-Anbindung) — Handover-MD in den Vault schreiben
- Requires: PROJ-3 (Cockpit) — Budget-Gauge auf der Kachel anzeigen

## Beschreibung
Der Token-Disziplin-Kern: Jupiter überwacht den Kontextfenster-Füllstand je Session (#25), warnt an einer Schwelle und schlägt ein **Handover** vor. Handover (#8) wird manuell (Button) und automatisch (abc-Phasenübergang, #7) erzeugt, als MD in den Vault geschrieben und kann eine Session frisch neu starten. Geplanter Staffelstab statt Notbremsen-Crash.

## User Stories
- Als Nutzer möchte ich pro Session den Kontext-Füllstand + Token-Verbrauch sehen, um Bloat früh zu erkennen.
- Als Nutzer möchte ich bei Erreichen einer Schwelle einen Handover-Vorschlag bekommen.
- Als Nutzer möchte ich auf Knopfdruck (und automatisch an Phasenübergängen) ein Handover-MD erzeugen lassen.
- Als Nutzer möchte ich eine Session mit dem Handover als Startkontext frisch neu starten (Reset).

## Acceptance Criteria
- [ ] Pro Session werden Kontextfenster-Füllstand (%) + kumulierter Token-Verbrauch angezeigt (Gauge auf der Kachel, #25; Daten aus PROJ-1).
- [ ] Bei Überschreiten einer **konfigurierbaren Schwelle** erscheint eine Schwellenwarnung + Handover-Vorschlag.
- [ ] Handover ist **manuell** (Button) und **automatisch** (abc-Phasenübergang) auslösbar.
- [ ] Handover-MD enthält: Wo stehen wir? / Erledigt / Offen / Fallstricke / **Pointer** (statt Volltext).
- [ ] Handover wird über PROJ-2 in den Vault geschrieben.
- [ ] „Session zurücksetzen": neue Session startet mit Handover-MD als Startkontext; alte Session wird als abgeschlossen archiviert.

## Edge Cases
- Token-Daten vom Treiber fehlen/verzögert → Gauge zeigt „unbekannt" statt irreführend 0.
- Handover ausgelöst, während Session arbeitet → erst nach dem aktuellen Schritt, nicht mitten im Tool-Call.
- Reset bei sehr kurzer Session → erlaubt, aber Hinweis „wenig Kontext".
- Schwelle 0/100 % oder unsinnig konfiguriert → auf sinnvolle Grenzen geklemmt.

## Technical Requirements (optional)
- Schwellenwert konfigurierbar (pro Session / global).
- abc-Phasenübergang aus dem Workflow ableitbar (Skill-/Statuswechsel) als Auto-Trigger.
- Pointer-statt-Volltext im Handover zahlt auf #23 (RAG, P1) ein.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Next.js 16 (Cockpit) + FastAPI (Engine) + Hal-Vault (Datei-MD, kein DB/RLS/JWT im MVP) · **Branch:** dev

### Ausgangslage (was schon existiert)
Eine CodeGraph-Erkundung zeigt: der Großteil der Infrastruktur ist bereits da. Wir bauen **auf** PROJ-1/2/3 auf, statt neu anzufangen.

| Baustein | Status | Fundstelle |
|---|---|---|
| Token-Verbrauch + Kontext-Füllstand (%) je Session | ✅ vorhanden | `SessionState` / `_apply_usage()` `backend/app/engine/manager.py`; `UsageSnapshot.context_fill_pct` `backend/app/engine/events.py` |
| Felder im API-Schema (`tokens_used`, `context_fill_pct`, `total_cost_usd`) | ✅ vorhanden | `SessionRead` `backend/app/schemas/sessions.py:45` |
| Gauge auf der Kachel (grün/amber/rot) | ✅ vorhanden | `nextjs_app/components/cockpit/session-tile.tsx` |
| Live-Updates per WebSocket (`kind=state`) | ✅ vorhanden | `nextjs_app/hooks/use-session-stream.ts` |
| Handover-MD in den Vault schreiben | ✅ Endpoint scaffolded | `POST /sessions/{id}/handover` `backend/app/routes/sessions.py:105`; `vault.write(type="handover", …)` |
| Session archivieren | ✅ vorhanden | PROJ-3 (Archiv-Sektion im Cockpit) |
| Session fortsetzen (`claude --resume`) | ✅ vorhanden | `SessionManager.resume()` `backend/app/engine/manager.py` |

**Lücken, die PROJ-5 schließt:** Schwellen-Konfiguration + Warnung, **Handover-Inhalt erzeugen** (heute muss der Client den Text liefern), **Reset-mit-Seed**-Flow, sowie etwas Frontend (Warn-Badge, Handover-Dialog, Reset-Button).

### Entscheidungen dieser Iteration
- **Handover-Inhalt: Hybrid.** Ein mechanisches Gerüst (Metadaten, Status, Datei-Pointer) wird serverseitig befüllt; die Prosa-Felder (*Offen / Fallstricke / Pointer*) werden optional durch eine kurze LLM-Selbstzusammenfassung der laufenden Session angereichert. Fällt die LLM-Anreicherung aus (Session tot/Fehler), bleibt das mechanische Gerüst als gültiger Handover bestehen.
- **Auto-Trigger: nur Schwelle im MVP.** Automatisches Handover ausschließlich beim Überschreiten der Kontext-Schwelle. Der phasen-basierte Auto-Trigger (abc-Phasenübergang) wird auf **PROJ-8** verschoben, wo die Phasen-Erkennung ohnehin gebaut wird — heute existiert keine Phasen-Maschine im Engine.
- **Reset-Semantik: Staffelstab.** „Session zurücksetzen" archiviert die alte Session und startet eine **neue Kind-Session** mit dem Handover-MD als Seed-Kontext (`parent_session_id`-Verweis zurück). Keine zwei lebenden Sessions zum selben Strang.

### A) Komponenten-Struktur (Frontend, Cockpit)
```
SessionTile (vorhanden)
├── ContextGauge (vorhanden)            → grün/amber/rot Füllstand-Balken
├── ThresholdBadge (NEU)                → Warn-Icon, sobald Füllstand ≥ Schwelle
│   └── "Handover vorschlagen" (Aktion) → öffnet HandoverDialog
SessionDetailPage (vorhanden)
├── HandoverDialog (NEU)                → vorbefüllter Handover (Gerüst+Anreicherung),
│   ├── Vorschau (Wo/Erledigt/Offen/…)    editierbar, "In Vault schreiben"
│   └── HandoverPointer (Link zum MD im Vault nach dem Schreiben)
└── ResetSessionButton (NEU)            → "Mit Handover frisch neu starten"
        └── Bestätigungs-Dialog          → archiviert alt, startet Kind-Session
GlobalSettings / SessionSettings
└── ThresholdControl (NEU)              → Schwelle in % (global + pro Session überschreibbar)
```

### B) Datenmodell (Klartext, kein DB im MVP)
- **Schwellenwert:** neue Einstellung `context_fill_threshold_pct` (global, Default **85 %**) in `backend/app/config.py`; pro Session optional überschreibbar (im Session-State gehalten). Server klemmt Werte auf einen sinnvollen Bereich (z. B. 50–98 %), damit 0/100/Unsinn nicht zu Dauerwarnung oder „nie" führt.
- **Session-State-Ergänzungen (in-memory, kein Persistenz-DB):**
  - `parent_session_id` — verweist von einer Reset-Kind-Session auf ihren Vorgänger.
  - `threshold_warned` — Merker, damit die Schwellenwarnung nicht in jeder Turn neu feuert.
- **Handover-MD (im Vault):** geschrieben über PROJ-2 nach `Agentic OS/Jupiter/…`, mit Frontmatter (Session-ID, Owner, Zeit, Phase/Modell). Struktur: **Wo stehen wir? / Erledigt / Offen / Fallstricke / Pointer** (Datei- & Vault-Zeiger statt Volltext — zahlt auf #23/RAG ein).
- **Edge-Case „Daten fehlen":** liefert der Treiber (noch) keine Token-/Kontext-Daten, zeigt die Gauge **„unbekannt"** statt irreführend 0 %, und die Schwellenlogik bleibt still.

### C) API-Form (Endpunkte, kein Code)
```
- POST  /sessions/{id}/handover/generate   → erzeugt den Handover-INHALT (Hybrid: Gerüst
                                              + optionale LLM-Anreicherung), gibt MD-Vorschau
                                              zurück (schreibt noch NICHT). NEU.
- POST  /sessions/{id}/handover            → schreibt (ggf. editierten) Handover in den Vault.
                                              VORHANDEN — Body kommt jetzt aus /generate.
- POST  /sessions/{id}/reset               → archiviert alte Session, startet Kind-Session
                                              mit Handover-MD als Seed (extra_system_prompt),
                                              setzt parent_session_id. NEU.
- GET   /settings/threshold  /  PATCH …    → globalen Schwellenwert lesen/setzen. NEU
                                              (pro-Session-Override über Session-Patch).
- (Bestehender WebSocket kind=state)       → transportiert zusätzlich ein "threshold_warning"-
                                              Flag, wenn Füllstand ≥ Schwelle. KEIN neuer Kanal.
```
Alle Endpunkte sind Single-User-MVP (Owner serverseitig gestempelt, kein JWT — konsistent mit PROJ-1/2).

### D) Tech-Entscheidungen (WARUM, für PM)
- **Wir nutzen die vorhandene Token-/Kontext-Pipeline statt neuer Messung** — der Engine zählt schon pro Turn mit; PROJ-5 hängt nur Schwelle + Warnung daran.
- **Generieren und Schreiben sind zwei Schritte** (`/generate` → Vorschau → `/handover`), damit der Nutzer den Handover vor dem Festschreiben prüfen/editieren kann — ein Handover ist ein Staffelstab, kein Wegwerf-Log.
- **Pointer statt Volltext** im Handover hält das Dokument klein und macht den Reset-Kontext günstig — direkte Vorarbeit für späteres RAG (#23).
- **Reset = neue Kind-Session, nicht `--resume`** — Resume schleppt den vollen alten Kontext mit (genau das Problem). Reset startet bewusst frisch und seedet nur die verdichtete Übergabe.
- **Phasen-Auto-Trigger bewusst vertagt** — Phasen-Erkennung gehört zu PROJ-8 (ABC-Gantt); doppelt bauen würde Scope überlappen. MVP liefert den nutzbaren Schwellen-Pfad sofort.
- **Schwelle wird geklemmt** — schützt vor Fehlkonfiguration (Edge Case 4) ohne den Nutzer zu gängeln.

### E) Abhängigkeiten (Pakete)
- **Backend:** keine neuen Pakete — alles über vorhandenen Engine + Vault-Dienst. (LLM-Anreicherung läuft über den bestehenden Claude-Treiber, kein neuer SDK-Client.)
- **Frontend:** keine neuen Pakete — `ThresholdBadge`/`HandoverDialog`/`ResetSessionButton` sind Kompositionen vorhandener shadcn/ui-Primitive (`Dialog`, `Button`, `Badge`, `Textarea`).

### Mapping Anforderung → Modul → Spezialist
| Acceptance Criterion | Modul/Endpoint/Screen | Spezialist |
|---|---|---|
| Füllstand % + Token-Verbrauch je Kachel | `session-tile.tsx` (Gauge vorhanden) | Frontend (Verifikation) |
| Schwellenwarnung + Handover-Vorschlag | `config.py` + `manager.py` (Schwellen-Flag) · `ThresholdBadge` | Backend → Frontend |
| Handover manuell (Button) | `HandoverDialog` + `/handover/generate` + `/handover` | Frontend → Backend |
| Handover automatisch (Schwelle; Phase→PROJ-8) | `manager.py` (Auto-Trigger bei Schwelle) | Backend |
| Handover-MD-Felder (Wo/Erledigt/Offen/Fallstricke/Pointer) | Handover-Generator (Hybrid) | Backend |
| Handover in Vault | `/handover` → `vault.write` (vorhanden) | Backend (Verifikation) |
| Session zurücksetzen (Kind-Session + Archiv) | `/sessions/{id}/reset` + `ResetSessionButton` | Backend → Frontend |
| Schwelle konfigurierbar (global/Session) | `/settings/threshold` + `ThresholdControl` | Backend → Frontend |

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
