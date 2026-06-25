# PROJ-34: Chat-Modus im Neue-Session-Dialog (freies Chatfenster ohne ABC-Bezug)

## Status: Deployed
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Deployment
- **Production URL:** https://jupiter.auxevo.tech
- **Deployed:** 2026-06-25 · **Version:** 0.12.0 · **Host:** Dev-VPS (host-native systemd + Caddy, GitHub-Webhook Auto-Deploy aus `main`)
- **Geliefert:** Modus-Umschalter „Workflow/ABC ↔ Chat" im Neue-Session-Dialog; Chat-Modus graut den ABC-Block aus und startet eine normale Session ohne abc-/Rollen-Verknüpfung. Reiner Frontend-Change.
- **Browser-Smoke (auf Prod zu verifizieren):** Dialog öffnen → „Chat" → ABC-Block ausgegraut, Rolle deaktiviert → „Session starten" erzeugt normale Session. Nach Frontend-Rebuild ggf. Hard-Refresh (Strg+Shift+R).

## QA Test Results
**Getestet:** 2026-06-25 · **Branch:** dev · **Tester:** QA Engineer · **Methode:** Code-Review je Kriterium + Regressions-Suite (`vitest`) + Production-Build (inkl. TypeScript). Reines Frontend, kein Backend/Auth/Tenancy → Tenant-Isolation-/JWT-Audit **N/A** (Jupiter-MVP ohne JWT/RLS).

### Automatisierte Gates
- `vitest run`: **121/121** grün (13 Dateien) — keine Regression.
- `npm run build`: **erfolgreich**, TypeScript-Schritt sauber (der einzelne `tsc --noEmit`-Fehler liegt in `lib/md-tree.test.ts` und ist baseline-bestätigt; Next-Build schließt Test-Dateien aus → grün).
- `eslint` auf der geänderten Datei: sauber.
- Hinweis: Das Feature ist reines State/JSX-Wiring; unter der Repo-Konvention (Vitest testet **reine Funktionen**, kein jsdom/Testing-Library installiert) gibt es keine extrahierbare reine Logik für einen sinnvollen Unit-Test. Empfehlung (optional, nicht blockierend): bei künftigem Refactoring die Payload-Regel `role = chatMode ? undefined : role` in eine exportierte Helper-Funktion ziehen und wie `describeBranch` (PROJ-13) testbar machen.

### Acceptance Criteria (8/8 PASS)
| # | Kriterium | Ergebnis | Beleg |
|---|-----------|----------|-------|
| 1 | Umschalter mit zwei Zuständen „Workflow/ABC" + „Chat" | ✅ | `Tabs`/`TabsList`/zwei `TabsTrigger` |
| 2 | Default „Workflow/ABC", bisheriges Verhalten unverändert | ✅ | `useState("workflow")` |
| 3 | „Chat" graut ABC-Block (Vorschlag, „Vorschlag starten", „Weitere offene Features") sichtbar aus + nicht klickbar | ✅ | Wrapper `opacity-50 pointer-events-none aria-disabled` + `disabled`-Prop deaktiviert innere Buttons/Chips |
| 4 | Im Chat-Modus keine Feature-ID/abc-Rolle; zuvor gewähltes Feature wird beim Wechsel verworfen | ✅ | `onModeChange("chat")` → `setSelectedId(null)` + `setRole("")` |
| 5 | Projekt, Pfad, Prompt, Engine, Modell, Berechtigung bleiben bedienbar | ✅ | nur `role`-Input ist im Chat-Modus `disabled` |
| 6 | „Session starten" im Chat-Modus → normale Session ohne abc-Verknüpfung | ✅ | Payload `role: chatMode ? undefined : …`; Feature-ID geht ohnehin nie ans Backend |
| 7 | Zurück nach „Workflow" reaktiviert Block + lädt Vorschlag (debounced) | ✅ | `chatMode` als `useEffect`-Dependency → Re-Fetch beim Zurückschalten |
| 8 | Alle Beschriftungen/Tooltips deutsch | ✅ | „Workflow/ABC", „Chat", Hinweis-/Platzhalter-Texte deutsch |

### Edge Cases (5/5 PASS)
- **Wechsel mit gewähltem Feature:** Auswahl wird verworfen; Zurückschalten lädt frisch den Empfehlungs-Vorschlag (kein „Geister"-Feature der vorherigen Hand-Auswahl). ✅
- **Projekt ohne abc-Struktur:** Chat-Modus überspringt den Launcher komplett → freier Start funktioniert. ✅
- **Leerer Initial-Prompt:** `valid` verlangt weiterhin `prompt.trim() > 0` — Pflichtfeld unverändert. ✅
- **Pfadwechsel im Chat-Modus:** `useEffect` bricht bei `chatMode` früh ab → kein Launcher-Request; Block bleibt ausgegraut. ✅
- **Schmaler Viewport (375 px):** `TabsList` `w-full` mit zwei `flex-1`-Triggern → kein Layout-Bruch (Code-Verifikation; visuelle Bestätigung empfohlen). ✅

### Bugs
Keine (Critical 0 · High 0 · Medium 0 · Low 0).

### Regression
Verwandte Features (PROJ-3 Cockpit, PROJ-9 Smart Launcher, PROJ-18 Engines, PROJ-20 Push-to-Talk) unverändert: Workflow-Modus ist Default und nutzt denselben Code-Pfad wie vorher; Suite grün.

### Production-Ready
**JA** — keine Critical/High-Bugs. Einzige offene Empfehlung ist die optionale visuelle 375px-Sichtprüfung im Browser (nicht blockierend).

## Implementation Notes (Frontend)
**Datum:** 2026-06-25 · **Branch:** dev · **Datei:** `nextjs_app/components/cockpit/new-session-dialog.tsx` (einzige Änderung, kein Backend).

- Neuer lokaler State `workflowMode: 'workflow' | 'chat'` (Default `'workflow'`), abgeleitetes `chatMode`. Kein Backend-Flag, kein neues Schema.
- **Umschalter** als shadcn `Tabs`/`TabsList`/`TabsTrigger` (Segmented-Look, volle Breite) direkt unter dem Dialog-Header. Bei „Chat" zusätzlich ein deutscher Hinweistext.
- **Moduswechsel** (`onModeChange`): Wechsel nach „Chat" verwirft `selectedId` + `role` (kein „Geister"-Feature). `resetForm` setzt `workflowMode` wieder auf `'workflow'`.
- **Launcher-Fetch** (`useEffect`) bricht im Chat-Modus früh ab (`if (!open || chatMode) return`) + `chatMode` als Dependency → kein störender Request bei Pfadwechsel.
- **ABC-Block** im Chat-Modus sichtbar, aber ausgegraut: Wrapper mit `pointer-events-none select-none opacity-50` + `aria-disabled`; `SuggestionCard` bekam ein `disabled`-Prop (deaktiviert die inneren Buttons/Chips). Ohne geladenen Vorschlag zeigt ein ausgegrauter Platzhalter, dass der Block bewusst deaktiviert ist.
- **Rolle-Feld** im Chat-Modus `disabled` (zeigt leer + Platzhalter „Im Chat-Modus deaktiviert").
- **Submit:** `role` wird im Chat-Modus als `undefined` gesendet → normale Session ohne abc-Verknüpfung (`POST /sessions`, sonst identischer Payload). Projekt/Pfad/Prompt/Engine/Modell/Berechtigung bleiben voll bedienbar; Pflichtfeld (Prompt) unverändert.
- Verifikation: `eslint` sauber; `tsc --noEmit` ohne neuen Fehler (1 vorbestehender Fehler in `lib/md-tree.test.ts`, baseline-bestätigt).

## Dependencies
- Requires: PROJ-3 (Cockpit / Neue-Session-Dialog) — der Modus-Umschalter und die ausgegraute Vorauswahl leben im `NewSessionDialog`.
- Requires: PROJ-9 (Smart Launcher) — der „Vorschlag aus dem Workflow" / „Weitere offene Features"-Block ist das, was im Chat-Modus ausgegraut wird.
- Requires: PROJ-1 (Engine-Treiber) — eine Chat-Session ist eine ganz normale Engine-Session (gleicher `POST /sessions`).

## Beschreibung
Im **Neue-Session-Dialog** wird man heute immer in die **ABC-Projekt-/Feature-Vorauswahl** geführt (Smart-Launcher-Vorschlag + „Weitere offene Features"). Es fehlt die Möglichkeit, im **gleichen Projektordner** einfach **ein reines Chatfenster** zu öffnen, um andere Dinge zu besprechen, ohne ein Feature/eine abc-Phase zu verknüpfen.

Gewünscht: ein **kleiner Umschalter** (z. B. Knopf/Segment „Chat" neben dem Default „Workflow/ABC"). Bei Auswahl **„Chat"** wird die **ABC-/Feature-Vorauswahl ausgegraut** (deaktiviert, nicht entfernt) und es wird **keine Feature-/Rollen-Verknüpfung** gesetzt. Es wird trotzdem eine **ganz normale Session** gestartet — gleicher Request, Engine/Modell/Berechtigung weiterhin wählbar, gleicher Projektpfad. Nur eben ohne abc-Bezug (laut Klärung 2026-06-25: kein eigenes Backend-Flag, kein Sonder-Lifecycle).

## User Stories
- Als Nutzer möchte ich im Neue-Session-Dialog zwischen **„Workflow/ABC"** und **„Chat"** umschalten können, um im selben Projektordner auch mal frei reden zu können, ohne ein Feature zu starten.
- Als Nutzer möchte ich, dass im **Chat-Modus** die ABC-/Feature-Vorauswahl **sichtbar, aber ausgegraut** ist, damit klar ist, dass sie bewusst deaktiviert wurde (statt zu verschwinden).
- Als Nutzer möchte ich im Chat-Modus weiterhin **Engine, Modell und Berechtigung** wählen können, weil ich auch im freien Chat das richtige Modell brauche.
- Als Nutzer möchte ich, dass eine im Chat-Modus gestartete Session **als normale Session** im Cockpit/in der Sidebar auftaucht, damit ich sie wie jede andere weiterführen kann.

## Acceptance Criteria
- [ ] Der Neue-Session-Dialog hat einen **Umschalter mit zwei Zuständen**: „Workflow/ABC" (Default, heutiges Verhalten) und „Chat".
- [ ] Default beim Öffnen ist **„Workflow/ABC"** — das bestehende Verhalten bleibt unverändert.
- [ ] Bei Auswahl **„Chat"** wird der gesamte ABC-Block (Smart-Launcher-Vorschlag „VORSCHLAG AUS DEM WORKFLOW", „Vorschlag starten", „Weitere offene Features") **sichtbar ausgegraut und nicht klickbar**.
- [ ] Im Chat-Modus ist **keine Feature-ID** und **keine abc-Rolle** vorausgewählt; ein zuvor (im Workflow-Modus) gewähltes Feature wird beim Wechsel nach „Chat" **entworfen/zurückgesetzt**.
- [ ] Im Chat-Modus bleiben **Projekt(-Titel), Projekt-Pfad, Initial-Prompt, Engine, Modell, Berechtigung** voll bedienbar.
- [ ] „Session starten" im Chat-Modus erzeugt eine **normale Session** (`POST /sessions`) **ohne** Feature-/abc-Verknüpfung im Payload; die Session erscheint danach wie üblich in der Sidebar und im Cockpit.
- [ ] Wechsel **zurück nach „Workflow/ABC"** reaktiviert den ABC-Block und lädt den Smart-Launcher-Vorschlag wie bisher (debounced beim Pfadwechsel).
- [ ] Alle Beschriftungen/Tooltips sind **deutsch**.

## Edge Cases
- **Wechsel mit bereits gewähltem Feature:** Nutzer wählt im Workflow-Modus ein Feature und schaltet dann auf „Chat" → Feature-Auswahl wird verworfen; schaltet er zurück, ist nichts vorausgewählt (kein „Geister"-Feature).
- **Projekt ohne abc-Struktur:** Im Workflow-Modus liefert der Launcher „kein abc erkannt"; der Chat-Modus muss auch hier sauber funktionieren (gleicher freier Start).
- **Leerer Initial-Prompt:** Pflichtfeld-Verhalten bleibt wie im Workflow-Modus (Start nur mit Prompt) — der Chat-Modus hebt keine bestehenden Pflichtfelder auf.
- **Pfadwechsel im Chat-Modus:** Ein Pfadwechsel soll im Chat-Modus **keinen** störenden Launcher-Request auslösen bzw. dessen Ergebnis nicht sichtbar einblenden (Block bleibt ausgegraut).
- **Schmaler Viewport:** Der Umschalter darf das Dialog-Layout auf 375 px nicht sprengen.

## Technical Requirements (optional)
- Reiner **Frontend-Fix** im `NewSessionDialog` (`nextjs_app/components/cockpit/new-session-dialog.tsx`); **keine** neue Backend-/DB-/Schema-Änderung (Chat = normale Session ohne abc-Felder im Payload).
- Der „Chat"-Zustand ist **lokaler Dialog-State**; beim Start wird der bestehende `createSession`-Payload nur **ohne** Feature-/Rollen-Verknüpfung gebaut.
- Ausgegraut = `disabled`/reduzierte Opazität, **nicht** entfernen (Erkennbarkeit, dass es bewusst deaktiviert ist).
- Texte/Tooltips deutsch; shadcn/ui-Primitive (z. B. Toggle/SegmentedControl) statt handgerollter Button-Logik.

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (App Router) + shadcn/ui — reiner Frontend-Fix, kein Backend · **Branch:** dev

### Einordnung (CodeGraph-Befund)
Alles spielt sich in **einer Datei** ab: `nextjs_app/components/cockpit/new-session-dialog.tsx`. Kein Backend, keine DB, kein neues Schema. Die Erkundung hat drei für das Design entscheidende Fakten bestätigt:
- Es existiert bereits ein lokales `mode`-Feld — das ist aber die **Berechtigung** (`default`/`acceptEdits`/`bypassPermissions`). Der neue Umschalter braucht deshalb einen **eigenen Namen** (`workflowMode`), sonst Namenskollision.
- Die ABC-Verknüpfung einer Session hängt am **`role`-Feld** im Erstell-Payload. Die Feature-ID selbst wird heute **nie** ans Backend geschickt — sie befüllt nur lokal Prompt/Modell. Chat-Modus = Session **ohne `role`** starten.
- Der Smart-Launcher-Block wird über die `SuggestionCard`-Komponente gerendert und per **debounced Fetch (300 ms)** bei Pfadwechsel geladen.

### A) Komponenten-Struktur (was sich ändert)
```
NewSessionDialog
├── ModusUmschalter  ← NEU (shadcn Tabs/ToggleGroup: „Workflow/ABC" · „Chat")
├── SuggestionCard (ABC-Block: Vorschlag + „Weitere offene Features")
│   └── im Chat-Modus: sichtbar, aber disabled + reduzierte Opazität
├── Projekt-Titel · Projekt-Pfad · Initial-Prompt   (immer aktiv)
└── Engine · Modell · Berechtigung                  (immer aktiv)
```

### B) Daten / State (Klartext)
- Neues lokales Dialog-State-Feld **`workflowMode: 'workflow' | 'chat'`**, Default `'workflow'`.
- Steuert zweierlei: (1) ob `SuggestionCard` als `disabled` gerendert wird, (2) ob beim Wechsel nach „Chat" die abc-Auswahl (`selectedId` + `role`) **zurückgesetzt** wird.
- Im Chat-Modus unterbleibt der Launcher-Fetch bei Pfadwechsel (bzw. dessen Ergebnis bleibt ausgegraut/unsichtbar) — kein störender Request.
- Keine Persistenz nötig: rein lokaler State, lebt nur solange der Dialog offen ist.

### C) API / Payload (kein neuer Endpoint)
- Unverändert `POST /sessions` über `createSession`.
- **Workflow-Modus:** Payload wie heute (inkl. `role`, falls gesetzt).
- **Chat-Modus:** identischer Payload (`project_path`, `initial_prompt`, `model`, `engine`) **ohne `role`** — fertig. Backend merkt davon nichts (kein Flag, kein Sonder-Lifecycle).

### D) Tech-Entscheidungen (warum so)
- **Kein Backend-Flag:** Eine Chat-Session ist technisch eine ganz normale Session ohne abc-Rolle. Ein extra „is_chat"-Feld würde Lifecycle, Recovery und Cockpit unnötig verzweigen — laut Klärung 2026-06-25 bewusst vermieden.
- **Ausgrauen statt Ausblenden:** Der ABC-Block bleibt sichtbar (`disabled`), damit erkennbar ist, dass er bewusst deaktiviert wurde — kein „verschwundenes" UI.
- **Eigenes State-Feld statt `mode` wiederverwenden:** `mode` ist die Berechtigung; Mischen würde zwei Bedeutungen in eine Variable pressen.
- **shadcn-Primitive (Tabs/ToggleGroup):** vorhandenes `tabs.tsx` nutzen statt handgerollter Button-Toggle-Logik (Konvention „shadcn first", Fokus/A11y gratis).

### E) Abhängigkeiten (Packages)
Keine neuen Packages. Nur ein bereits vorhandenes shadcn-Primitiv (`tabs` / ggf. `toggle-group` neu per shadcn-CLI kopieren, falls Segmented-Look gewünscht).
