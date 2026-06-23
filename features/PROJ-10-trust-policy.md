# PROJ-10: Trust-Policy — abgestuftes, konfigurierbares Vertrauen

## Status: In Review
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #5

## Dependencies
- Requires: PROJ-4 (Decision Cards) — die Policy entscheidet, was eine Card erzeugt (erweitert die heutige fixe `engine/policy.py`); nutzt die Pause-+-Card-+-Resume-Maschinerie.
- Requires: PROJ-6 (Knappheits-Konstitution / Rollen) — Policy ist pro Rolle/Skill/Projekt konfigurierbar.
- Requires: PROJ-8 (Phasenerkennung) — liefert das Signal für das **Phasen-Übergangs-Gate** (`abc_phase`-Wechsel).
- Requires: PROJ-1 (Engine / `permission_mode`) — die **bypass-festen** Gates müssen auch bei `bypassPermissions` greifen.
- Verwandt: PROJ-16 (Watchdog) — nutzt dieselbe Policy + dasselbe „pausieren statt killen"-Prinzip als Reißleine.

## Beschreibung
Im MVP gibt es einen **fixen, konservativen** Freigabe-Trigger (jede schreibende Aktion → Card). Dieses Feature macht Vertrauen zu einer **konfigurierbaren Richtlinie pro Kontext**: Pro Rolle/Skill/Projekt wird festgelegt, was **autonom** läuft (Auto-Approve), was eine **Decision Card** erzeugt und was **hart verboten** ist. Default bleibt „möglichst autonom, aber sicher".

### Eine Entscheidungsstelle, zwei Sorten Gate (wichtig wegen Bypass)
Wichtige Korrektur zur Mechanik: Der PreToolUse-Hook (`request_decision`) feuert **immer** — auch im `bypassPermissions`-Modus (PROJ-1). Ob eine Aktion durchläuft oder eine Card erzeugt, entscheidet **Jupiter** in `request_decision`. Damit gibt es zwei Sorten Gate an **derselben** Stelle:
1. **Operative Gates:** `auto-allow` / `card` / `deny` pro Tool/Kontext. Im **Bypass** werden operative Aktionen (Bash & Co.) **auto-allowed** (seit PROJ-1-Fix) — daher laufen die kleinen Freigaben im Bypass durch.
2. **Harte Gates (bypass-fest):** werden in `request_decision` **vom Bypass-Auto-Allow ausgenommen** → sie erzeugen **auch im Bypass** eine Card und pausieren die Session bis zur Freigabe. Kein separater Pfad nötig — nur eine Ausnahme im selben Hook.

### Phasen-Übergangs-Gate (erstes bypass-festes Gate)
Beim Wechsel der **ABC-Phase** (z. B. Architecture → Frontend, erkannt über PROJ-8s `abc_phase`-Signal) wird **immer** — auch im Bypass — eine **Decision Card** erzeugt, bevor die nächste Phase startet. So bleibt der Mensch an den **Schaltstellen** in der Schleife, während die kleinteilige Arbeit innerhalb einer Phase (im Bypass) ungebremst läuft. Welche Übergänge gaten, ist konfigurierbar (Default: jeder Phasenwechsel).

## User Stories
- Als Nutzer möchte ich pro Rolle/Skill festlegen, welche Tool-Klassen autonom laufen dürfen, um vertraute Abläufe nicht ständig freigeben zu müssen.
- Als Nutzer möchte ich bestimmte Aktionen (z. B. `rm -rf`, force-push, Schreiben außerhalb des Projekts) **hart verbieten**, unabhängig vom Kontext.
- Als Nutzer möchte ich eine projektweite Default-Policy plus rollen-/skillspezifische Übersteuerungen pflegen.
- Als Nutzer möchte ich sehen, **welche Regel** eine konkrete Decision Card ausgelöst hat (Nachvollziehbarkeit).
- Als Nutzer möchte ich Policy-Änderungen ohne Backend-Neustart wirksam machen.
- Als Nutzer möchte ich, dass am **Phasenwechsel** (z. B. Architecture → Frontend) eine Freigabe kommt, damit ich an den Schaltstellen entscheide — **auch wenn die Session im Bypass-Modus läuft**.
- Als Nutzer möchte ich pro Projekt/Rolle festlegen können, **welche** Phasenübergänge eine Freigabe brauchen (oder alle).
- Als Nutzer möchte ich, dass solche „harten" Gates vom `bypassPermissions`-Modus **nicht** ausgehebelt werden.

## Acceptance Criteria
- [ ] Es gibt drei Vertrauensstufen pro Regel: **auto-allow**, **card** (Freigabe nötig), **deny** (hart verboten).
- [ ] Regeln können nach **Tool-Klasse** (Bash/Edit/Write/…) und **Kontext** (Rolle, Skill, Projekt) gematcht werden; spezifischere Regel schlägt allgemeinere.
- [ ] Eine **deny**-Regel verhindert die Aktion und erzeugt eine ablehnende Card-Notiz mit Begründung — die Aktion wird nie ausgeführt.
- [ ] Der Default (keine passende Regel) ist konservativ: schreibende/destruktive Tools → **card**, Lesezugriffe → **auto-allow** (= heutiges Verhalten).
- [ ] Jede erzeugte Card nennt die **auslösende Regel** (welche Stufe, welcher Match).
- [ ] Policy ist als Konfiguration editierbar (UI oder Settings) und wird **live** neu geladen, ohne Sessions zu unterbrechen.
- [ ] Bestehende PROJ-4-Cards funktionieren unverändert, wenn keine Policy gepflegt ist (Rückwärtskompatibilität).
- [ ] **Bypass-feste Gates:** Die Policy kennt Gates, die **unabhängig vom `permission_mode`** greifen — von Jupiter durchgesetzt (pausieren → Card → resume), nicht über den Claude-Permission-Hook.
- [ ] **Phasen-Übergangs-Gate:** Bei einem von PROJ-8 erkannten `abc_phase`-Wechsel wird **vor** dem Start der neuen Phase eine Decision Card erzeugt — **auch bei `bypassPermissions`** —; die Session pausiert bis zur Freigabe.
- [ ] Die zu gatenden Phasenübergänge sind **konfigurierbar** (Default: jeder Wechsel); Freigeben setzt die Session fort, Ablehnen/Mit-Kommentar wirkt wie bei PROJ-4.
- [ ] Im Bypass laufen die **operativen** Per-Tool-Freigaben (Bash etc.) weiterhin durch (nur die harten Gates feuern).
- [ ] **Phasen-Signal liegt im Bypass an:** Da der PreToolUse-Hook auch im Bypass feuert, ist die `_detect_abc`-Phasenerkennung (PROJ-8) auch dort aktiv → Gate + Gantt-Anzeige stocken im Bypass nicht.
- [ ] Alle Texte deutsch.

## Edge Cases
- **Widersprüchliche Regeln** (eine auto-allow, eine deny für denselben Match) → die restriktivere (deny) gewinnt; Konflikt wird geloggt.
- **Policy-Datei kaputt/ungültig** → Fallback auf konservativen Default, sichtbare Warnung, kein Crash.
- **Neue, unbekannte Tool-Klasse** → Default-Stufe (card), nie versehentlich auto-allow.
- **Auto-allow trotz Watchdog-Alarm** (PROJ-16) → Watchdog kann eine auto-allow-Aktion dennoch pausieren (Reißleine sticht Komfort).
- **Rolle ohne Policy** → projektweiter Default greift.
- **Phasenwechsel im Bypass** → Phasen-Gate feuert trotzdem (harter Gate = von der Bypass-Auto-Allow-Ausnahme ausgenommen, erzeugt weiterhin eine Card).
- **Nicht-linearer Phasensprung** (z. B. Frontend ↔ Backend hin und her) → Gate pro tatsächlich erkanntem Wechsel; kein Doppel-Feuern beim selben Übergang (Entprellung).
- **Phase nicht erkennbar** (Skill ohne klaren abc-Bezug) → kein Phasen-Gate, nur die operative Hook-Ebene greift.
- **Nutzer lehnt den Phasenübergang ab** → Session bleibt in der alten Phase pausiert; Kommentar reist (wie bei PROJ-4) als Begründung zurück.

## Technical Requirements (optional)
- Erweitert `backend/app/engine/policy.py` (heute fixe `AUTO_ALLOW_TOOLS`) um die Stufen-Logik (Hook-Ebene).
- **Harte Gates** sitzen in **`request_decision`** (derselbe Hook): Sie werden von der Bypass-Auto-Allow-Ausnahme **ausgenommen** und nutzen die vorhandene Pause-+-Card-+-Resume-Mechanik (PROJ-4 Futures). Da der Hook auch im Bypass feuert (verifiziert in Prod 2026-06-23), ist **kein** separater Engine-Pfad nötig.
- **Phasen-Signal:** Das Phasen-Gate triggert auf einen `abc_phase`-Wechsel, der schon im selben Hook erkannt wird (`_detect_abc`, PROJ-8). Da der Hook im Bypass feuert, liegt das Signal auch dort an — keine Entkopplung nötig.
- Konfig versioniert/serverseitig; Secrets/Pfade nie aus Client-Payload.
- Auswertung pro Tool-Call < 5 ms (im Permission-Hook-Pfad).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Next.js (Settings-UI) + FastAPI (Engine/Hook) + dateibasierte Config (kein DB, in-memory wie PROJ-1/2/5) · **Branch:** dev

### Leitidee
Die heutige **eine** Trigger-Funktion (`policy.requires_card()`, binär: Lese-Tool → durch, sonst → Card) wird durch einen **gestuften Policy-Evaluator** ersetzt — **1:1 am selben Aufrufpunkt**, der Rest des Codes ändert sich nicht. Es entstehen **zwei Sorten Gate an derselben Stelle** (`request_decision` in `manager.py`): weiche **operative** Gates (im Bypass durchlässig) und **harte, bypass-feste** Gates (feuern auch im Bypass). Das erste harte Gate ist das **Phasen-Übergangs-Gate**.

### A) Komponenten (was gebaut wird)

```
Policy-Engine (Backend, erweitert engine/policy.py)
├── PolicyStore        → lädt config/policy.yaml (live, mtime-basiert; Fallback bei Defekt)
├── Evaluator          → evaluate(tool, kontext) → {level: auto-allow|card|deny, rule}
│   └── Matcher        → Spezifität: tool+rolle+skill+projekt > tool+rolle > tool > default
└── PhaseGate          → erkennt abc_phase-Wechsel (PROJ-8) → hartes Gate

request_decision (engine/manager.py, bestehender Hook — erweitert)
├── Phasen-Wechsel?  → JA → harte Card (auch im Bypass), pausieren
├── Evaluator-Level  → deny → ablehnende Card-Notiz (nie ausführen)
│                      card → operative Card (im Bypass: auto-allow)
│                      auto-allow → durch
└── Pause→Card→Resume (vorhandene PROJ-4-Futures, unverändert)

Settings-Tab „Trust-Policy" (Next.js)
├── Regel-Liste (Tool-Klasse × Kontext × Stufe), bearbeitbar
├── Phasen-Gate-Schalter (welche Übergänge gaten; Default: alle)
└── „Live übernommen"-Hinweis (kein Neustart)
```

### B) Datenmodell (Klartext, keine DB)

**Policy-Config** — eine versionierte Datei `config/policy.yaml` neben der Konstitution (gleiches Muster wie `global.md`/`roles/<rolle>.md`):
- Eine Liste von **Regeln**. Jede Regel: *Match* (Tool-Klasse + optional Rolle/Skill/Projekt) → *Stufe* (`auto-allow` | `card` | `deny`) + optionaler Klartext-Grund.
- Ein **Phasen-Gate-Block**: an/aus + Liste der zu gatenden Übergänge (leer = alle).
- Fehlt die Datei oder ist sie kaputt → **konservativer eingebauter Default** (heutiges Verhalten: Lese-Tools auto-allow, Rest card) + sichtbare Warnung, kein Crash.

**Decision Card** (erweitert `PendingDecision`, in-memory):
- neu: `triggering_rule` (welche Regel/Stufe hat ausgelöst — Nachvollziehbarkeit, AC).
- neu: `card_type` (`normal` | `phase_transition` | `deny`) — Frontend rendert Phasen-Gate & Ablehnung anders.
- **Bugfix:** `context.phase` trägt künftig den echten `abc_phase` (heute fälschlich `constitution_source`) und die echte `role`.

**SessionState** (erweitert): `abc_phase_previous` — um einen **Wechsel** beim Tool-Call zu erkennen und **Doppel-Feuern** desselben Übergangs zu entprellen.

### C) Wo es greift (Verhalten, keine neuen Endpunkte für den Hook)

Der PreToolUse-Hook `request_decision` bleibt der einzige Entscheidungspunkt. Neue Reihenfolge:
1. **Phasen-Wechsel erkannt** (`abc_phase` ≠ `abc_phase_previous`, Übergang ist gegated) → **harte Card** (`phase_transition`), Session pausiert — **auch bei `bypassPermissions`** (von der Bypass-Auto-Allow-Ausnahme ausgenommen).
2. Sonst Evaluator-Stufe:
   - **deny** → Aktion wird **nie** ausgeführt; ablehnende Card-Notiz mit Grund (`behavior="deny"`).
   - **card** → operative Card; **im Bypass** läuft sie weiterhin durch (auto-allow, PROJ-1-Verhalten).
   - **auto-allow** → durch.
3. Pause/Card/Resume nutzt die vorhandene PROJ-4-Future-Mechanik unverändert.

### D) Neue/erweiterte HTTP-Endpunkte (Settings-UI, keine DB)

```
GET   /settings/policy        → aktuelle Policy + Phasen-Gate-Config + Quelle/Warnung
PUT   /settings/policy        → Policy ersetzen (validiert; schreibt config/policy.yaml; live aktiv)
GET   /settings/policy/preview?tool=Bash&role=…  → welche Stufe/Regel würde greifen (Nachvollziehbarkeit/Test)
```
Live-Reload: der Evaluator prüft die Datei-mtime pro Call (Auswertung < 5 ms, in-process) — Schreiben über das UI wirkt sofort, ohne Sessions zu unterbrechen. Single-User-MVP: kein JWT (konsistent mit PROJ-1/2/5); Pfade/Secrets nie aus Client-Payload.

### E) Tech-Entscheidungen (Warum)
- **Ein Gate-Punkt, zwei Sorten** statt zweiter Engine-Pfad: Der Hook feuert auch im Bypass (Prod-verifiziert 2026-06-23) → harte Gates brauchen nur eine **Ausnahme** von der Bypass-Auto-Allow, keinen Parallelpfad. Weniger Code, eine Quelle der Wahrheit.
- **YAML-Datei statt DB-Tabelle**: deckt sich mit Jupiters No-DB-/In-memory-Ansatz und dem Konstitutions-Muster (Datei + Live-Reload). Editierbar per UI **oder** direkt im Dateisystem.
- **Spezifischer schlägt allgemeiner; deny schlägt alles**: deterministisch und vorhersehbar; Konflikte werden geloggt. Unbekanntes Tool → `card` (nie versehentlich auto-allow).
- **`triggering_rule` in der Card**: erfüllt die Nachvollziehbarkeits-AC ohne separates Audit-Log.
- **Entprellung über `abc_phase_previous`**: verhindert Doppel-Cards bei nicht-linearen Sprüngen (Frontend ↔ Backend).

### F) Abhängigkeiten
- Backend: `PyYAML` (Policy-Datei lesen/schreiben) — neu, falls noch nicht vorhanden; sonst keine.
- Frontend: bestehende shadcn/ui-Komponenten (Table, Switch, Select, Badge) — nichts Neues.

### G) Abdeckung der Acceptance Criteria
| AC | Umsetzung |
|---|---|
| 3 Stufen auto-allow/card/deny | Evaluator-`level` |
| Match nach Tool-Klasse + Kontext, spezifisch > allgemein | Matcher-Spezifität |
| deny verhindert + ablehnende Card | `behavior="deny"`, nie ausgeführt |
| konservativer Default | eingebauter Default-Layer (= heute) |
| Card nennt auslösende Regel | `triggering_rule` |
| live editierbar, kein Neustart | mtime-Reload + PUT-Endpunkt |
| Rückwärtskompatibel ohne Policy | fehlende Datei → Default |
| bypass-feste Gates | Ausnahme von Bypass-Auto-Allow |
| Phasen-Gate vor neuer Phase, auch im Bypass | PhaseGate in `request_decision` |
| gatebare Übergänge konfigurierbar | Phasen-Gate-Block in Config |
| operative Per-Tool-Freigaben im Bypass durchlässig | unveränderte PROJ-1-Logik |
| Phasen-Signal liegt im Bypass an | `_detect_abc` läuft schon im Hook |
| alles deutsch | UI + Card-Texte |

## Frontend-Implementierung (2026-06-23)
Stack: **Next.js** (nicht Flutter — Jupiter-Override). Branch `dev`. UI gegen den geplanten
API-Kontrakt gebaut; Backend (Evaluator + Phasen-Gate + `/settings/policy`) folgt via `/abc-backend`.

**Neu/geändert:**
- `lib/types.ts` — `PolicyLevel`, `PolicyRuleMatch`, `PolicyRule`, `PhaseGateConfig`, `TrustPolicy`, `PolicyPreview`; `PendingDecision` um `triggering_rule` + `card_type` (`normal`/`phase_transition`/`deny`) erweitert.
- `lib/api.ts` — `getPolicy` (GET), `setPolicy` (PUT, live), `previewPolicy` (GET Trockenlauf).
- `components/cockpit/policy-control.tsx` (neu) — Regel-Editor (Tool-Klasse × Rolle/Skill/Projekt × Stufe + Grund), bypass-festes Phasen-Gate (an/aus + Ziel-Phasen, leer = alle), Defekt-/Quelle-Banner, Regel-Test (Preview). „Speichern (live)".
- `components/cockpit/settings-dialog.tsx` — auf Tabs umgestellt: „Allgemein" (Schwelle) + „Trust-Policy".
- `components/cockpit/decision-card.tsx` — zeigt auslösende Regel; eigenes Styling/Badge für `phase_transition` (violett, „Phase freigeben") und `deny` (rot, nur „Zur Kenntnis", da nie ausgeführt).

**Verifikation:** `tsc --noEmit` + `eslint` ohne Befunde in den PROJ-10-Dateien (vorbestehender `md-tree.test.ts`-Fehler unberührt). Backend-Endpunkte fehlen noch → Controls fangen Offline/404 ab (Banner „Backend offline?").

**Offene Designwahl (für Backend):** Config-Format **YAML** angenommen (PyYAML); Match-Spezifität tool+rolle+skill+projekt > … > default, deny gewinnt; `transitions` = Ziel-Phasen, leer = jeder Wechsel.

## Backend-Implementierung (2026-06-23)
Stack: FastAPI + **dateibasierte Policy** (YAML, kein DB). Branch `dev`. In-memory/Datei-Ansatz wie PROJ-6.

**Neu/geändert:**
- `engine/policy.py` — gestufter Evaluator: `PolicyStore` (YAML, **mtime-Live-Reload**, Fallback bei Defekt), `evaluate(tool, role, skill, project) → PolicyDecision(level, rule, reason)`. Stufen `auto-allow`/`card`/`deny`; Spezifität tool+rolle+skill+projekt > … > Default; bei Gleichstand deny>card>auto (Konflikt geloggt). `project` matcht per Teilstring. Default ohne Datei/Regel = konservativ (Lesen auto, Rest card; unbekanntes Tool → card). `snapshot()`/`save()` für die API. Modul-Singleton `policy_store`.
- `engine/manager.py` — `request_decision` neu: **(1)** hartes, bypass-festes **Phasen-Gate** (`_should_gate_phase`, Entprellung via old≠new, nur echte Übergänge old≠None), **(2)** Evaluator (auto/deny/card). `deny` blockiert die Session **nicht** (Aktion nie ausgeführt, Claude erhält Grund inline + transiente `deny`-Notiz). `card` im Bypass durchlässig. Neuer `_open_card`-Helfer. `SessionState.current_skill` (Skill-Kontext), `_detect_abc` führt ihn mit. **Bugfix:** Card-`context.phase` trägt jetzt `abc_phase` statt `constitution_source`.
- `engine/decisions.py` — `PendingDecision` um `triggering_rule` + `card_type` (`normal`/`phase_transition`/`deny`).
- `schemas/sessions.py` — `PendingDecisionRead` um dieselben Felder.
- `schemas/settings.py` + `routes/settings.py` — `GET /settings/policy`, `PUT /settings/policy` (validiert Stufen + Phasen-Namen → 400/422, schreibt YAML, live), `GET /settings/policy/preview`.
- `config.py` — `policy_config_path` (Default `backend/config/policy.yaml`, muss nicht existieren).
- `config/policy.example.yaml` (dokumentierte Vorlage, nicht geladen); Laufzeit-`policy.yaml` in `.gitignore`.

**Tests:** `tests/test_proj10_trust_policy.py` — 18 Tests (Stufen/Spezifität/Konflikt/Default/Defekt-Fallback/Live-Reload, Phasen-Gate feuert im Bypass, operative Card im Bypass durchlässig, deny ohne Pending-Card, Card trägt Regel+echte Phase, REST GET/PUT/preview inkl. 400/422). **Gesamtsuite: 322 passed.**

## QA Test Results (2026-06-23)
**Tester:** QA/Red-Team · **Branch:** dev · **Stand:** Backend 325 passed + 2 xfail; Frontend 47 passed; TS/Lint sauber.
**Hinweis Jupiter-Override:** kein JWT/RLS/MinIO/Multi-Tenancy → Tenant-Isolations-Audit entfällt; geprüft wurden Bypass-Festigkeit, deny-Enforcement, Injection/Traversal über Policy-Felder, Config-Robustheit.

### Acceptance Criteria
| # | Kriterium | Ergebnis |
|---|-----------|----------|
| 1 | 3 Stufen auto-allow/card/deny | ✅ PASS |
| 2 | Match Tool+Kontext, spezifisch > allgemein | ✅ PASS |
| 3 | deny verhindert Aktion **+ ablehnende Card-Notiz** | ⚠️ TEILWEISE — Aktion wird nie ausgeführt ✅, aber die Notiz ist **im UI nicht sichtbar** (→ Bug A) |
| 4 | Konservativer Default | ✅ PASS |
| 5 | Card nennt auslösende Regel | ✅ PASS (`triggering_rule`, Frontend rendert sie) |
| 6 | Live editierbar, kein Neustart | ✅ PASS (mtime-Reload + PUT) |
| 7 | Rückwärtskompatibel ohne Policy | ✅ PASS |
| 8 | Bypass-feste Gates | ✅ PASS |
| 9 | Phasen-Gate vor neuer Phase, auch im Bypass | ✅ PASS (feuert); **Ablehnungs-Edge → Bug B** |
| 10 | Gatebare Übergänge konfigurierbar | ✅ PASS |
| 11 | Operative Per-Tool-Freigaben im Bypass durchlässig | ✅ PASS |
| 12 | Phasen-Signal liegt im Bypass an | ✅ PASS |
| 13 | Alles deutsch | ✅ PASS |

### Edge Cases
| Edge Case | Ergebnis |
|-----------|----------|
| Widersprüchliche Regeln → deny gewinnt + Konflikt geloggt | ✅ PASS |
| Policy-Datei kaputt → Fallback + Warnung, kein Crash | ✅ PASS |
| Unbekannte Tool-Klasse → card | ✅ PASS |
| Rolle ohne Policy → Default | ✅ PASS |
| Phasenwechsel im Bypass → Gate feuert | ✅ PASS |
| Nicht-linearer Sprung (frontend↔backend) → Gate je Wechsel, Entprellung | ✅ PASS |
| Phase nicht erkennbar / None→erste Phase → kein Gate | ✅ PASS |
| Auto-allow trotz Watchdog (PROJ-16) | ⏭️ N/A (PROJ-16 nicht gebaut) |
| **Nutzer lehnt Phasenübergang ab → bleibt in alter Phase** | ❌ FAIL (→ Bug B) |

### Bugs — beide BEHOBEN (Backend-Fix 2026-06-23)
- **Bug A — deny-Notiz im UI unsichtbar (Medium) → BEHOBEN.** `deny` legt jetzt eine **nicht-blockierende, bereits aufgelöste** Notiz-Card in `pending_decisions` (kein Future, kein `awaiting_approval`). Sie erscheint im Cockpit (Polling) **und** auf der Detailseite (State-Snapshot) und wird mit „Zur Kenntnis" quittiert (`resolve_decision` entfernt future-lose Notizen). Das Frontend-Deny-Rendering ist damit aktiv. (`manager._register_deny_notice` + `resolve_decision`-Zweig.)
- **Bug B — Phase rückt bei abgelehntem Phasen-Gate vor (Medium) → BEHOBEN.** Die Phase wird jetzt **seiteneffektfrei** vorausberechnet (`abc_phases.detect_phase_signal`) und erst **nach Freigabe** übernommen (`manager._apply_phase`). Bei Ablehnung bleibt die alte Phase; bei Freigabe springt sie. (`request_decision` deferred-apply.)

Regression abgesichert in `tests/test_proj10_qa.py`: `test_denied_phase_gate_keeps_old_phase`, `test_approved_phase_gate_advances_phase`, `test_deny_surfaces_a_dismissable_notice`.

### Re-QA (2026-06-23) — NEUER Befund aus Fix A
- **Bug C — Status friert auf `awaiting_approval` ein (Medium, Regression aus Fix A).** Die nicht-blockierende deny-Notiz liegt in `self.pending`. Wird danach eine **echte** blockierende Card freigegeben, prüft `resolve_decision` `if not self.pending …` → die liegengebliebene Notiz hält `pending` nicht-leer → der Status kehrt **nicht** nach `RUNNING` zurück, sondern bleibt `awaiting_approval` (Cockpit/Kanban zeigen die Session fälschlich als „wartet auf Freigabe", obwohl der Treiber weiterläuft). *Repro:* deny-Regel (Bash) + card-Regel (Write) → Bash (deny-Notiz) → Write-Card freigeben → Status bleibt `awaiting_approval`. *Fix-Richtung:* Die „leer?"-Prüfung darf nur **blockierende** Cards zählen → `self._futures` statt `self.pending` verwenden (Notizen haben kein Future). Alternativ Notizen aus `pending` heraushalten und über eine separate `notices`-Liste in `to_read()` ausliefern.
- Festgehalten als `xfail(strict=True)`: `test_lingering_deny_notice_does_not_freeze_status` (flippt auf PASS nach dem Fix).

**Re-QA-Verdict:** Bug A + B bestätigt behoben. **Ein neuer Medium-Bug (C)** durch Fix A → **Status bleibt In Review**, Bug C vor Deploy fixen. Suite: 348 passed + 1 xfail (Bug C).

### Security / Red-Team
- ✅ **Bypass kann das harte Phasen-Gate nicht aushebeln** — die Gate-Prüfung steht **vor** dem Bypass-Auto-Allow.
- ✅ **Kein Code-/Injection-Risiko über die Policy:** `yaml.safe_load` (kein Exec); PUT validiert Stufen (Pydantic-`Literal` → 422) und Phasen-Namen (→ 400). Match-Felder werden nur für Gleichheit/Teilstring genutzt (kein SQL/eval/Pfad).
- ✅ **Kein Path-Traversal:** `save()` schreibt auf den fixen Serverpfad (`settings.policy_config_path`), nie aus Client-Payload.
- ⚠️ **Betriebs-Caveat (kein Bug):** eine Catch-all-`deny`-Regel (leeres `tool`) sperrt auch Lese-Tools und kann eine Session lahmlegen — bewusste Konfig-Macht; in der UI/Doku als Warnung sinnvoll.

### Tests hinzugefügt
- `tests/test_proj10_trust_policy.py` (18) + `tests/test_proj10_qa.py` (3 Edge-Cases + 2 xfail-Bugs).

### Verdict
Erst-QA fand zwei **Medium**-Bugs (A: deny unsichtbar; B: Phase rückt bei Ablehnung vor). **Beide sind jetzt backend-seitig behoben** und per Regressionstest abgesichert; AC #3 und der Ablehnungs-Edge-Case von #9/#10 sind damit erfüllt. Keine offenen Critical/High/Medium. Gesamtsuite **348 passed**. → **Bereit für erneute QA-Abnahme** (`/abc-qa 10`), danach `/abc-deploy`.

## Deployment
_To be added by /abc-deploy_
