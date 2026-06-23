# PROJ-5: Context-Management & Handover

## Status: Approved
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

## Implementierung — Backend (2026-06-23)
**Branch:** dev · **Tests:** `backend/tests/test_proj5_handover.py` (21 neu) · gesamte Suite **180 grün**.

### Gebaut
- **Schwellen-Konfiguration + Klemmung** (`config.py`): `context_fill_threshold_pct` (global, Default **85 %**); `clamp_threshold()` klemmt jeden Wert auf `[THRESHOLD_MIN_PCT=50, THRESHOLD_MAX_PCT=98]` (Edge-Case 0/100/Unsinn).
- **Settings-API** (`routes/settings.py`, `schemas/settings.py`): `GET /settings/threshold` (Wert + min/max), `PATCH /settings/threshold` (klemmt, in-memory).
- **Pro-Session-Override**: `PATCH /sessions/{id}/threshold` (`threshold_pct` | `null` = global). State-Feld `context_threshold_override_pct`; `SessionState.effective_threshold_pct` löst Override→global→geklemmt auf.
- **Gauge-Daten + „unbekannt"** (`manager.py`/`events.py`): neues Feld `context_known` (erst nach erstem Usage-Event `True`) → Frontend zeigt „unbekannt" statt irreführend 0 %. `to_read()` liefert zusätzlich `context_known`, `context_fill_threshold_pct`, `threshold_warning`, `parent_session_id`.
- **Schwellen-Warnung + Auto-Vorschlag** (`manager.py`): `threshold_warning` (live abgeleitet, im `kind=state`-Snapshot) + einmaliger `{"kind":"notice","event":"threshold_reached"}`-Broadcast beim ERSTEN Überschreiten (`threshold_warned` one-shot). Einziger Auto-Trigger im MVP — Phasen-Trigger bleibt PROJ-8.
- **Hybrid-Handover-Generator** (`engine/handover.py`): `POST /sessions/{id}/handover/generate` → Vorschau `{title, body}` (schreibt NICHT). Mechanisches Gerüst aus Session-Zustand mit den Feldern **Wo stehen wir? / Erledigt / Offen / Fallstricke / Pointer** (Pointer statt Volltext, zahlt auf #23 ein). LLM-Anreicherung als optionaler `enrichment`-Seam (Default aus via `settings.handover_llm_enrich`); fällt sie aus, bleibt das Gerüst gültig.
- **Schreiben** unverändert über `POST /sessions/{id}/handover` → `vault.write(type="handover")` (PROJ-2). Generierter Body fließt direkt hinein.
- **Reset-Staffelstab** (`manager.reset` + `POST /sessions/{id}/reset`): archiviert die alte Session (`stop()` → DONE → Auto-Log in den Vault), startet eine **Kind-Session** mit dem Handover als `--append-system-prompt`-Seed (bewusst KEIN `--resume`), setzt `parent_session_id`. Body: `seed_context` (Pflicht), `initial_prompt` (optional, sonst Default-Auftakt).

### Bewusste Abweichungen / offene Punkte
- **„Automatisches Handover" = automatischer Vorschlag**, keine Auto-Schreibung — respektiert „Generieren≠Schreiben" (Nutzer prüft den Staffelstab) und den Edge-Case „nicht mitten im Tool-Call".
- **LLM-Anreicherung als Seam, Default aus** — das deterministische Gerüst ist der garantierte Pfad; die echte Treiber-Anreicherung kann später ohne Vertragsänderung zugeschaltet werden.
- **Schwelle in-memory** (kein DB im MVP, konsistent mit PROJ-1/2).
- **Frontend**: in dieser Iteration umgesetzt (siehe unten).

### API-Vertrag (für Frontend)
| Methode | Pfad | Body | Antwort |
|---|---|---|---|
| POST | `/sessions/{id}/handover/generate` | — | `{title, body}` (Vorschau) |
| POST | `/sessions/{id}/handover` | `{body, title?, on_exists?}` | `VaultWriteResult` (`path,type,created`) |
| POST | `/sessions/{id}/reset` | `{seed_context, initial_prompt?}` | `SessionRead` (Kind, inkl. `parent_session_id`) |
| PATCH | `/sessions/{id}/threshold` | `{threshold_pct \| null}` | `SessionRead` |
| GET/PATCH | `/settings/threshold` | `{threshold_pct}` | `{threshold_pct, min_pct, max_pct}` |
| WS | `/sessions/{id}/stream` | — | `kind=state` trägt `context_known/threshold_warning/...`; `kind=notice` `event=threshold_reached` |

## Implementierung — Frontend (2026-06-23)
**Stack:** Next.js 16 + Tailwind + shadcn/Base-UI · **Branch:** dev · **Gates:** `tsc --noEmit` ✓ · `eslint` ✓ · `vitest` **23 grün** · `next build` ✓.

### Neue Komponenten (`nextjs_app/components/cockpit/`)
- **`context-gauge.tsx`** — Füllstand-Balken; zeigt „unbekannt" (gestreift) statt 0 %, wenn `context_known=false`; Farbe rot ab Schwelle (amber davor), feine Schwellen-Markierung.
- **`threshold-badge.tsx`** — Warn-Chip („Schwelle X% erreicht"), compact-Variante für die Kachel.
- **`handover-dialog.tsx`** — Button → Dialog: ruft beim Öffnen `/handover/generate`, zeigt Titel + MD **editierbar**, schreibt via `/handover` in den Vault, zeigt den Datei-Pointer.
- **`reset-session-button.tsx`** — „Zurücksetzen": generiert den Seed (Handover), Edge-Case-Hinweis „wenig Kontext" bei `num_turns ≤ 1`, bestätigt → `/reset` → navigiert zur Kind-Session.
- **`threshold-control.tsx`** — `ThresholdControl` (global, `/settings/threshold`) + `SessionThresholdControl` (pro-Session `PATCH …/threshold`, „Global"-Reset = `null`).
- **`settings-dialog.tsx`** — Zahnrad im Mission-Control-Header → globaler Schwellen-Regler.

### Integration / geändert
- **`lib/types.ts`** — `Session` um `context_known`, `context_fill_threshold_pct`, `threshold_warning`, `parent_session_id` erweitert; `HandoverPreview`/`VaultWriteResult`/`ThresholdSetting`.
- **`lib/api.ts`** — `generateHandover`, `writeHandover`, `resetSession`, `setSessionThreshold`, `getThreshold`, `setThreshold`.
- **`lib/status.ts`** — `contextLabel()` (+ „unbekannt") und `gaugeColor()` (Schwellen-basiert); Unit-Tests ergänzt.
- **`hooks/use-session-stream.ts`** — verarbeitet `kind=notice`/`event=threshold_reached` via optionalem `onNotice`-Callback.
- **`session-tile.tsx`** — nutzt `ContextGauge`; zeigt `ThresholdBadge` bei `threshold_warning`.
- **Detailseite** (`app/(cockpit)/sessions/[id]/page.tsx`) — Header-Badge + Aktionsleiste (Handover, Zurücksetzen, „← Vorgänger-Session"); Schwellen-Override + Gauge; Toast bei Schwellen-Notice.
- **Cockpit-Header** (`app/(cockpit)/page.tsx`) — `SettingsDialog` (Zahnrad).

### Offen für QA
- Visuelle E2E-Verifikation gegen laufendes Backend + echte Claude-Session (`/abc-qa-e2e`) — Build/Typecheck/Unit sind grün, der Live-Flow (WS-Notice, Reset-Navigation, Vault-Write-Pointer) ist noch nicht im Browser gegen den Stack durchgeklickt.

## QA Test Results
**Getestet:** 2026-06-23 · **Branch:** dev · **Tester:** QA/Red-Team
**Automatisiert:** Backend `pytest` **183 grün** (24 PROJ-5, davon 3 neue Red-Team-Fälle) · Frontend `tsc --noEmit` ✓ · `eslint` ✓ · `vitest` **23 grün** · `next build` ✓.
**Methodik:** Akzeptanzkriterien gegen Code + automatisierte Tests + dynamische Red-Team-Probe (Manager/TestClient mit FakeDriver). **Nicht** abgedeckt: visuelle Browser-E2E gegen laufenden Stack + echte Claude-Session (→ `/abc-qa-e2e` empfohlen vor Deploy).

### Akzeptanzkriterien
| # | Kriterium | Ergebnis | Beleg |
|---|---|---|---|
| 1 | Füllstand % + Token-Verbrauch je Kachel (Gauge, #25) | ✅ PASS | `SessionRead.context_fill_pct/context_known/tokens_used`; `ContextGauge` in Tile + Detail; `test_context_known_true_after_usage` |
| 2 | Schwellenwarnung + Handover-Vorschlag bei konfigurierbarer Schwelle | ✅ PASS | `threshold_warning`-Flag im `kind=state`; `ThresholdBadge`; one-shot `kind=notice`; Toast; `test_threshold_warning_and_one_shot_notice` |
| 3 | Handover manuell (Button) + automatisch (Schwelle) | ✅ PASS¹ | `HandoverDialog` (manuell); Schwellen-Notice (auto-Vorschlag). Phasen-Trigger bewusst → PROJ-8 |
| 4 | Handover-MD-Felder Wo/Erledigt/Offen/Fallstricke/Pointer | ✅ PASS | `build_handover_md`; `test_generate_handover_has_all_sections` |
| 5 | Handover über PROJ-2 in den Vault | ✅ PASS | `/handover` → `vault.write(type="handover")`; `test_generate_then_write_handover` |
| 6 | Session zurücksetzen (Kind-Session + Seed + Archiv) | ✅ PASS | `/reset`; `test_reset_archives_old_and_seeds_child`, `…_links_parent` |

¹ „Automatisch" = automatischer **Vorschlag** beim Schwellenübergang (kein Auto-Write — bewusste Architektur-Entscheidung „Generieren≠Schreiben"). Deckt sich mit dem Tech-Design.

### Edge Cases
| Edge Case | Ergebnis | Beleg |
|---|---|---|
| Token-Daten fehlen → Gauge „unbekannt" statt 0 % | ✅ PASS | `context_known=false` → gestreifter Balken + `contextLabel`; `test_fresh_state_is_unknown`, `test_generate_handover_on_empty_transcript` |
| Handover ausgelöst, während Session arbeitet | ✅ PASS | `/handover/generate` ist rein lesend (Snapshot) — unterbricht keinen Tool-Call |
| Reset bei sehr kurzer Session → erlaubt + Hinweis | ✅ PASS | Frontend-Hinweis bei `num_turns ≤ 1` (`ResetSessionButton`) |
| Schwelle 0/100/Unsinn → geklemmt | ✅ PASS | `clamp_threshold` [50,98]; `test_clamp_threshold`, `test_patch_threshold_clamps`, `test_patch_session_threshold_override` |

### Security / Red-Team
- **Keine neue Auth/Tenant-Fläche.** Alle neuen Endpunkte sind Single-User-MVP (kein JWT), konsistent mit PROJ-1/2/4 — kein RLS/Mandanten-Modell im MVP (bekannte, dokumentierte Posture, kein Regress).
- **Pfad-Härtung beim Vault-Write** unverändert (slug + `safe_id_segment`); generierter/editierter Body ist erwarteter MD-Inhalt, Frontmatter via `json.dumps` escaped. Kein Injection-Vektor server-seitig.
- **Reset bei `awaiting_approval` hängt nicht** — blockierter Hook wird mit `deny` entsperrt (`test_reset_while_awaiting_approval_does_not_hang`).
- **Schwellen-Eingaben** (negativ/riesig/None) werden geklemmt bzw. als Override gelöscht — keine Dauerwarnung / kein „nie".

### Bugs
| ID | Sev | Beschreibung | Status |
|---|---|---|---|
| QA5-1 | **Low** | Doppelter `/reset` auf dieselbe (bereits archivierte) Session erzeugt eine zweite Kind-Session; die erste bleibt als **lebende Waise** in der Registry. Client-seitig durch den `resetting`-Guard + Navigation entschärft; serverseitig ungebremst. Empfehlung: Reset auf nicht-archivierte Sessions beschränken oder bei vorhandenem Kind ablehnen. | offen (nicht blockierend) |

### Produktionsreife
**READY (MVP)** — keine Critical/High-Bugs. 1× Low (QA5-1) dokumentiert, nicht blockierend.
**Empfehlung vor Deploy:** `/abc-qa-e2e` für den Live-Browser-Flow (WS-Notice-Toast, Reset-Navigation zur Kind-Session, Vault-Pointer nach dem Schreiben) gegen laufendes Backend + echte Claude-Session — diese Schicht wurde hier nicht visuell verifiziert.

## Deployment
_To be added by /deploy_
