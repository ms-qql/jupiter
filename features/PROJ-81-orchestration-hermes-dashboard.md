# PROJ-81: Orchestration-Eintrag „Hermes" — Hermes-Dashboard eingebettet bedienen

## Status: Architected
**Created:** 2026-08-18
**Last Updated:** 2026-08-18

## Dependencies
- Requires: PROJ-39 (Sidebar-Sektion „Orchestration" — Fremd-Apps per iFrame) — Hermes wird ein weiterer Eintrag in genau dieser Sektion und nutzt dieselbe Vollbild-Route `/orchestration/[key]` + `embed-tab.tsx`-Mechanik.
- Requires: PROJ-38 (Sidebar-Sektionen + Konfig-Panel) — der Eintrag ist dort toggel-/sortierbar.
- Bezug: PROJ-18 (Engine-Registry / `engines.yaml`) — der Eintrag ist eine reine Registry-Zeile.

## Beschreibung
Der auf dem VPS installierte **Hermes-Agent** (Nous Research „Hermes Agent") bringt ein eigenes **Web-Dashboard** mit (`hermes dashboard`: Verwaltungs-Oberfläche für Config, API-Keys, Sessions). Dieses Dashboard soll als weiterer Eintrag in der bestehenden Sidebar-Sektion **„Orchestration"** neben **Paperclip** und **Wayland** erscheinen. Klick öffnet es **eingebettet im Jupiter-Hauptbereich** (Vollbild-iFrame, Route `/orchestration/[key]`), sodass Hermes ohne Kontextwechsel direkt in Jupiter bedienbar ist.

**Geprüfte Ausgangslage (2026-08-18 auf dem VPS):**
- Hermes installiert unter `/home/dev/.hermes/`, CLI `hermes` in PATH. Das Dashboard lauscht per Default auf `127.0.0.1:9119` und läuft aktuell **nicht**.
- Seit dem Hermes-Hardening (Juni 2026) gilt: ein Bind außerhalb von Loopback verlangt zwingend einen Auth-Provider. **Loopback-Bind + Reverse-Proxy ist der offiziell empfohlene Weg** — das entspricht exakt dem bewährten PROJ-39-Muster.
- **Entscheidung Nutzer 2026-08-18 (1):** Zugangsschutz wie **Paperclip** — kein eigenes Hermes-Passwort; das Dashboard bleibt auf `127.0.0.1` ohne Login, davor Caddy mit Jupiters Login (`forward_auth`).
- **Entscheidung Nutzer 2026-08-18 (2):** Das Dashboard läuft als **dauerhafter Hintergrunddienst** (systemd-User-Service), damit der Klick in Jupiter sofort öffnet.
- **Namensraum-Kollision:** Der Registry-Key `hermes` ist bereits durch die (deaktivierte) Hermes-CLI-Engine belegt → der Orchestration-Eintrag bekommt einen **eigenen Key** (z. B. `hermes_dashboard`), Anzeigename bleibt **„Hermes"**.
- **Einmaliger Vorlauf:** Die Dashboard-Web-UI ist noch nicht gebaut (`web/dist` fehlt); der allererste Start baut sie (npm-Build, dauert einmalig mehrere Minuten). Danach startet der Dienst mit übersprungenem Build.

## User Stories
- Als Nutzer möchte ich in der Sektion **„Orchestration"** einen Eintrag **„Hermes"** neben Paperclip und Wayland, damit ich das Hermes-Dashboard ohne Tab-/Tool-Wechsel erreiche.
- Als Nutzer möchte ich per Klick auf den Eintrag das Hermes-Dashboard **direkt eingebettet im Jupiter-Hauptbereich** öffnen und dort bedienen (Config, Sessions, API-Keys), damit Hermes Teil meiner Kommandozentrale ist.
- Als Nutzer möchte ich, dass das Hermes-Dashboard **immer schon läuft**, wenn ich darauf klicke — ohne manuelles Starten.
- Als Nutzer möchte ich das Dashboard **ohne zusätzliches Passwort** nutzen — Jupiters Login schützt es mit.
- Als Nutzer möchte ich bei Einbettungs-Problemen einen **„In neuem Tab öffnen"-Fallback**, damit ich nie vor einer leeren Fläche stehe.
- Als Betreiber möchte ich den Eintrag **zentral über die Registry** konfigurieren, damit künftige Orchestration-Apps ohne Code-Wildwuchs dazukommen (gleiches Prinzip wie PROJ-39).

## Acceptance Criteria
- [ ] Die Sektion **„Orchestration"** enthält den neuen Eintrag **„Hermes"** mit Label + Icon (neben Paperclip, Wayland).
- [ ] Klick öffnet eine **Vollbild-Ansicht im Hauptbereich** (`/orchestration/<hermes-key>`), die das Hermes-Dashboard **per iFrame** einbettet.
- [ ] Das Hermes-Dashboard läuft als **dauerhafter systemd-User-Service** auf `127.0.0.1:9119` und startet nach Boot/Reboot automatisch.
- [ ] Das Dashboard ist **nur hinter Jupiters Login** erreichbar (`forward_auth` wie bei Paperclip); es wird **kein** eigenes Hermes-Passwort konfiguriert (Loopback-Bind bleibt).
- [ ] Die Dashboard-Web-UI ist **einmalig vorab gebaut**; der Dienst startet ohne interaktiven Build-Schritt (nicht-interaktiv, kein Browser-Öffnen auf dem Server).
- [ ] Das Dashboard ist über **https** (`https://hermes.auxevo.tech`) eingebettet — kein Mixed-Content.
- [ ] Der Eintrag ist über das **Konfig-Panel (PROJ-38)** toggelbar und sortierbar; bei ausgeblendeter Sektion bleibt die Direkt-URL erreichbar.
- [ ] Der **„In neuem Tab öffnen"-Fallback** ist immer sichtbar (wie PROJ-39).
- [ ] Der Registry-Key kollidiert **nicht** mit der bestehenden `hermes`-CLI-Engine.
- [ ] Texte/Labels deutsch („Hermes" bleibt Eigenname).

## Edge Cases
- **Dashboard-Prozess down / abgestürzt** → die Ansicht zeigt den Offline-Hinweis + „Erneut laden"/„In neuem Tab öffnen" (bestehende PROJ-39-Mechanik), kein stilles Leer-iFrame.
- **Erster Start nach Setup:** der initiale Web-UI-Build dauert mehrere Minuten → bis dahin ist der Eintrag vorhanden, die Einbettung zeigt aber den Offline-Hinweis. Der Build-Schritt ist Teil des Deploy-Steps, nicht der Laufzeit.
- **Dashboard setzt X-Frame-Options/CSP `frame-ancestors`:** ob Hermes das tut, ist noch ungeprüft → die Architektur-Phase verifiziert es am laufenden Dashboard und hebt die Sperre bei Bedarf gezielt für `jupiter.auxevo.tech` an der Proxy-Kante auf (Wayland-Vorbild). Der immer sichtbare Fallback-Button bleibt die Rückversicherung.
- **Jupiter-Login-Cookie abgelaufen** (auf der Subdomain) → der `forward_auth` schickt auf die Login-Seite; nach Login lädt das Dashboard.
- **Hermes-Update (`hermes update`)** kann einen Neustart/Neubau der Web-UI auslösen → der Dienst muss danach weiterhin starten (Build-Artefakt bleibt erhalten bzw. wird kontrolliert neu gebaut).
- **Port-Konflikt** (Port 9119 anderweitig belegt) → Dienst startet nicht; Jupiter zeigt Offline-Hinweis (kein Crash).
- **Sektion „Orchestration" ausgeblendet** → Direkt-URL funktioniert weiter.
- **Mobile:** Vollbild-iFrame nutzt die Hauptfläche; Sidebar-Drawer schließt nach Auswahl.

## Technical Requirements (optional)
- **Registry:** neuer Eintrag in `backend/config/engines.yaml` — `kind: iframe`, `group: orchestration`, `icon`, `url: https://hermes.auxevo.tech`, Sandbox-Attribute wie Paperclip/Wayland. **Eigener Key** (z. B. `hermes_dashboard`), da `hermes` durch die CLI-Engine belegt ist.
- **Infra (Deploy-Scope):** DNS-A-Record `hermes` → VPS-IP; Caddy-Site-Block `hermes.auxevo.tech` mit TLS + `forward_auth` (Paperclip-Vorbild) auf `127.0.0.1:9119`; Cookie-Domain `*.auxevo.tech` beachten. Framing-Verhalten des Dashboards prüfen und ggf. per `header_down` überschreiben (Wayland-Vorbild).
- **Dienst:** systemd-User-Service, nicht-interaktiv (kein Browser-Öffnen), Web-UI einmalig vorab gebaut, danach Start mit übersprungenem Build-Schritt; automatischer Neustart nach Boot/Crash.
- **Keine Backend-Anwendungs-API-Änderung** — `GET /engines` liefert den Eintrag automatisch (PROJ-39-Mechanik).
- Texte deutsch.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-18 · **Stack:** Next.js (Frontend) + FastAPI (Backend) + engines.yaml-Registry · **Branch:** main

### Zusammenfassung
PROJ-81 ist zu ~100 % Wiederverwendung der PROJ-39-Mechanik. Es entsteht **keine neue UI-Logik, kein neuer Endpoint, keine neue Tabelle** — nur ein Registry-Eintrag plus Infra-Setup (Dienst, DNS, Proxy). CodeGraph-Scan bestätigt: Sidebar-Eintrag, Vollbild-Route, iFrame-Embed, Offline-Hinweis und Fallback-Button existieren alle bereits und greifen automatisch, sobald der Eintrag in der Registry steht.

### A) Komponentenstruktur
```
Sidebar-Sektion „Orchestration" (bestehend, PROJ-38 toggel-/sortierbar)
├── Paperclip (bestehend)
├── Wayland (bestehend)
└── Hermes (NEU — Label + Icon)
    └── /orchestration/hermes_dashboard (bestehende Vollbild-Route)
        ├── EmbedTab (bestehend) — iFrame auf https://hermes.auxevo.tech
        ├── Offline-Hinweis + „Erneut laden" (bestehend)
        └── „In neuem Tab öffnen"-Fallback (bestehend, immer sichtbar)
```
Einziger neuer Frontend-Bestandteil: ein **Icon** für den Hermes-Eintrag in der bestehenden Icon-Liste der Orchestration-Sektion. Heute existiert dort kein passendes Symbol; ohne Eintrag erschiene ein generisches Fenster-Icon (Fallback).

**CodeGraph-Verifikation (2026-08-18):** Sidebar-Sektion, Vollbild-Route, iFrame-Embed, Offline-Hinweis und Fallback sind ausschließlich generisch (keine Paperclip/Wayland-Namens-Sonderfälle):
- Sidebar-Sektion: `nextjs_app/lib/sidebar-config.ts:58`, Einträge dynamisch via `orchestrationItemDef` (`sidebar-config.ts:160-173`), gespeist aus `engine.key`/`label`/`icon`.
- Vollbild-Route: `nextjs_app/app/(cockpit)/orchestration/[key]/page.tsx:34-41` (holt `GET /engines`, matched generisch `e.key === key && e.kind === "iframe"`).
- `EmbedTab`: `nextjs_app/components/cockpit/embed-tab.tsx:17-94`, nimmt beliebiges `EngineRead`.
- Offline-Hinweis/Reload: `embed-tab.tsx:28-40,57-64,69-77,84`.
- „In neuem Tab öffnen": `embed-tab.tsx:65` (immer sichtbar), zusätzlicher Fallback für http-Fall in `page.tsx:118`.

**Icon-Mechanismus (Klarstellung):** Das `icon:`-Feld in `engines.yaml` ist nur ein String — die tatsächliche Lucide-Komponente wird über eine **separate Frontend-Lookup-Tabelle** `ORCHESTRATION_ICONS` (`nextjs_app/lib/sidebar-config.ts:134-144`, aufgelöst via `resolveOrchestrationIcon()` in `sidebar-config.ts:147-150`) gemappt; fehlt der Eintrag, greift der Fallback `AppWindowIcon`. Heute existiert dort kein `hermes`/`hermes_dashboard`-Key. Der Icon-Name im yaml-`icon:`-Feld **muss exakt** einem neuen Key in `ORCHESTRATION_ICONS` entsprechen — das ist die eine echte Code-Änderung dieser Story.

### B) Datenmodell
Keine neuen DB-Tabellen, keine Datei-Ablage. Die Konfiguration lebt in der zentralen **Engine-Registry** (`backend/config/engines.yaml`) als eine Zeile — exaktes Feld-Set, 1:1 aus Paperclip (`engines.yaml:130-136`) / Wayland (`engines.yaml:162-168`) übernommen:
```yaml
- key: hermes_dashboard
  label: Hermes
  kind: iframe
  url: https://hermes.auxevo.tech
  sandbox: allow-scripts allow-same-origin allow-forms allow-popups allow-downloads
  group: orchestration
  icon: <neuer-icon-key, muss in ORCHESTRATION_ICONS existieren>
```
**Kollisions-Check bestätigt:** Key `hermes` ist bereits belegt durch die deaktivierte CLI-Engine (`engines.yaml:110-129`, `enabled: false`, `kind: engine`) — `hermes_dashboard` kollidiert nicht.

**Duplicate-Key-Verhalten verifiziert:** Der Registry-Loader (`backend/app/engine/registry.py:445-453`, `_parse_file`) prüft beim Datei-Laden **nicht** auf doppelte Keys — `profiles[prof.key] = prof` überschreibt einen vorhandenen Key lautlos. (Nur der separate Settings-UI-Save-Pfad, `registry.py:578-580`, wirft bei Duplikaten einen `ValueError` — das schützt nicht den yaml-Datei-Load.) Bestätigt: eindeutiger Key ist zwingend, keine Sicherheitsnetz-Prüfung fängt einen Fehler beim Deploy ab.
- **Key:** `hermes_dashboard` — bewusst eigener Key, da `hermes` bereits durch die (deaktivierte) Hermes-CLI-Engine belegt ist und Keys **übergreifend über alle Eintrags-Arten** eindeutig sein müssen
- **Art:** iFrame-App, Gruppe „Orchestration"
- **Anzeigename:** „Hermes", Icon, Ziel-URL `https://hermes.auxevo.tech`
- **Sandbox-Rechte:** identisch zu Paperclip/Wayland (Skripte, Formulare, Popups, Downloads)

Die Sichtbarkeits-/Reihenfolge-Einstellung läuft wie gehabt über das Konfig-Panel (PROJ-38, rein browserseitig); die Direkt-URL funktioniert auch bei ausgeblendeter Sektion (bestehendes Verhalten).

### C) API-Form
**Keine neuen Endpoints.** `GET /engines` liefert den neuen Eintrag automatisch mit aus; Sidebar und Vollbild-Route konsumieren ihn über die bestehende PROJ-39-Mechanik.

### D) Tech-Entscheidungen (Warum)
1. **Eigener Key `hermes_dashboard`:** Die Registry kennt keine Namensräume pro Art — ein doppelter Key würde lautlos überschrieben (beim Einlesen findet keine Duplikat-Prüfung statt). Eindeutiger Key ist daher Pflicht, kein Nice-to-have.
2. **Zugangsschutz wie Paperclip** (Loopback-Bind + Caddy `forward_auth`): kein zweites Passwort fürs Hermes-Dashboard; entspricht dem offiziell empfohlenen Weg seit dem Hermes-Hardening und ist bei Paperclip bereits bewährt.
3. **Dauerhafter systemd-User-Service:** Klick in Jupiter öffnet sofort — kein manuelles Starten, automatischer Neustart nach Boot/Crash.
4. **Web-UI-Build als Deploy-Schritt statt Laufzeit:** der allererste Build dauert mehrere Minuten; er gehört ins Setup, nicht in den Klickpfad. Der Dienst startet danach nicht-interaktiv mit übersprungenem Build. Bei `hermes update` bleibt das Build-Artefakt erhalten bzw. wird kontrolliert neu gebaut (Deploy-/Restart-Fluss).
5. **Framing-Verifizierung in die Deploy-Phase gelegt** (Spez sah Architektur-Phase vor): das Dashboard läuft aktuell nicht, und sein Erst-Build ist selbst Teil des Deploy-Steps — eine Prüfung von X-Frame-Options/CSP ist erst am laufenden Dashboard sinnvoll. Deploy verifiziert und hebt eine Sperre bei Bedarf gezielt für `jupiter.auxevo.tech` an der Proxy-Kante auf (Wayland-Vorbild). Der immer sichtbare Fallback-Button bleibt die Rückversicherung.
6. **Eigene Subdomain + HTTPS:** `hermes.auxevo.tech` verhindert Mixed-Content in der https-App; die bestehende Route blockiert http-Einbettungen ohnehin. Cookie-Domain `*.auxevo.tech` wie bei den Geschwister-Apps.

### E) Abhängigkeiten
Keine neuen Pakete — weder Frontend noch Backend.

### Aufwand-Verteilung
| Bereich | Aufwand | Inhalt |
|---------|---------|--------|
| Backend | minimal | ein Registry-Eintrag in `engines.yaml` |
| Frontend | minimal | ein Icon-Eintrag in der Orchestration-Icon-Liste |
| Deploy/Infra | **Hauptanteil** | einmaliger Web-UI-Build, systemd-User-Service, DNS-A-Record `hermes`, Caddy-Site mit TLS + `forward_auth`, Framing-Verifizierung |

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-18 · **Verdict:** Architected

### Checklist
- [x] Component structure — Sidebar-Sektion, Vollbild-Route, `EmbedTab`, Offline-Hinweis, Fallback-Button existieren bereits und arbeiten generisch über Registry-Daten (kein Paperclip/Wayland-Sonderfall). Verifiziert per CodeGraph, Zitate ergänzt.
- [x] Data model — kein DB-Bedarf; einzige „Entität" ist die `engines.yaml`-Zeile, Feld-Set 1:1 gegen Paperclip/Wayland verifiziert und im Spec als Beispiel-yaml ergänzt.
- [x] API shape — kein neuer Endpoint nötig; `GET /engines` (`backend/app/routes/engines.py:18-21` → `EngineRegistry.snapshot()`, `registry.py:503-508`) liefert generisch. Verifiziert.
- [x] Tech-Entscheidungen — jede der 6 Entscheidungen im Tech Design trägt ein „Warum".
- [x] Dependencies — keine neuen Pakete; bestätigt.
- [x] Branch-Feld — vorhanden (`main`).
- [x] Konflikt-frei — Key-Kollision mit CLI-Engine `hermes` (`engines.yaml:110-129`) geprüft und ausgeschlossen; Registry-Loader hat **keine** Duplicate-Key-Prüfung (`registry.py:445-453`) — im Spec als Warnhinweis ergänzt.
- [x] Acceptance-Criteria-Coverage — alle 10 Kriterien decken sich mit Registry-Eintrag (Frontend/Backend, minimal) + Deploy-Scope (Hauptanteil: systemd-Service, DNS, Caddy `forward_auth`, Framing-Check). Kein Kriterium ohne Zuordnung.

### Autonom behoben
- Tech Design A) um CodeGraph-verifizierte `file:line`-Zitate für Sidebar/Route/EmbedTab/Offline/Fallback ergänzt.
- Tech Design A) Icon-Mechanismus präzisiert: `icon:`-Feld in yaml ist nur ein String, echte Zuordnung läuft über `ORCHESTRATION_ICONS`-Lookup-Tabelle (`nextjs_app/lib/sidebar-config.ts:134-150`) — bestätigt als die einzige nötige Code-Änderung.
- Tech Design B) um exaktes Beispiel-yaml (Feld-Set 1:1 aus Paperclip/Wayland) ergänzt, damit `/abc-backend` nicht raten muss.
- Tech Design B) um Bestätigung der Key-Kollisionsfreiheit und um den verifizierten Duplicate-Key-Loader-Fund (`registry.py:445-453` vs. `578-580`) ergänzt — kein Sicherheitsnetz beim Datei-Load, Key-Eindeutigkeit ist also hart erforderlich.

### Offene Fragen
Keine — alle Checklist-Punkte bestehen, keine Produktentscheidung offen.

## QA Test Results
**Getestet:** 2026-08-18 · **Branch:** main · **Commit:** 9287585

### Acceptance Criteria
| # | Kriterium | Status | Befund |
|---|---|---|---|
| 1 | Orchestration-Eintrag „Hermes" mit Label + Icon | ✅ PASS | `engines.yaml` enthält `hermes_dashboard` (Label „Hermes", `icon: hermes`); `ORCHESTRATION_ICONS["hermes"] = SendIcon` in `nextjs_app/lib/sidebar-config.ts:145` — kein Fallback auf `AppWindowIcon`. |
| 2 | Klick öffnet Vollbild-iFrame `/orchestration/<key>` | ✅ PASS (Code) | Generischer Mechanismus unverändert seit PROJ-39-Review bestätigt (`page.tsx:34-41`, `embed-tab.tsx:17-94`); kein Live-Browsertest, da Projekt keine E2E/Playwright-Coverage hat (nur vitest-Unit-Tests, s. Memory). |
| 3 | Dashboard als dauerhafter systemd-User-Service auf `127.0.0.1:9119` | ❌ FEHLT | `systemctl --user list-units` zeigt **keinen** Hermes-Service auf dem VPS. Deploy-Scope laut Tech Design, noch nicht ausgeführt. |
| 4 | Nur hinter Jupiters Login (`forward_auth`), kein eigenes Passwort | ❌ FEHLT | Kein Caddy-Site-Block für `hermes.auxevo.tech` in `/etc/caddy/Caddyfile` (nur Paperclip/Wayland vorhanden). Deploy-Scope, noch nicht ausgeführt. |
| 5 | Web-UI einmalig vorab gebaut, nicht-interaktiver Start | ❌ FEHLT | Dashboard-Prozess läuft nicht, Build nicht ausgeführt (Deploy-Scope). |
| 6 | Erreichbar über https `hermes.auxevo.tech`, kein Mixed-Content | ❌ FEHLT | Keine DNS-/Caddy-Konfiguration vorhanden (Deploy-Scope). |
| 7 | Toggelbar/sortierbar über Konfig-Panel (PROJ-38); Direkt-URL bei ausgeblendeter Sektion erreichbar | ✅ PASS (Code) | Generischer PROJ-38-Mechanismus, unverändert; greift automatisch für jeden Registry-Eintrag. |
| 8 | „In neuem Tab öffnen"-Fallback immer sichtbar | ✅ PASS | `embed-tab.tsx:65`, unbedingt gerendert, generisch. |
| 9 | Registry-Key kollidiert nicht mit CLI-Engine `hermes` | ✅ PASS | `engines.yaml:110-129` (`hermes`, `kind: engine`, `enabled: false`) vs. `engines.yaml:169-175` (`hermes_dashboard`, `kind: iframe`) — getrennte Keys bestätigt. |
| 10 | Deutsche Texte/Labels | ✅ PASS | Label „Hermes" (Eigenname erlaubt), keine neuen UI-Strings sonst nötig. |

**Ergebnis: 6 von 10 bestanden, 4 offen (alle Deploy-Scope: Infra-Kriterien 3–6).**

### Regression / Automated Tests
- `pytest backend/` (voller Lauf): **1290 passed, 4 failed, 1 xfailed** — die 4 Fehlschläge (`test_proj50_codex_abc.py`) sind **vorbestehend und unabhängig von PROJ-81** (Codex-Skill-Generator, PROJ-81 hat diese Datei nicht berührt; Arbeitsbaum war vor jeder Änderung bereits identisch zu `HEAD`). Kein Regressions-Fund.
- `pytest backend/tests/test_proj18_engines.py backend/tests/test_proj51_engine_settings.py` (Registry-Kernpfad): **34 passed**, keine Regression.
- `vitest run` (Frontend): 7 Fails, alle in `lib/status.test.ts` (`ABC_PHASES`/`phaseIndex`), `gantt-chart.test.tsx`, `feature-run-view.test.tsx` — **keine dieser Dateien berührt Sidebar/Orchestration/Icons**, vorbestehend, kein PROJ-81-Regressionsfund.
- Kein Live-Browser-/E2E-Test möglich mangels Zugangsdaten und da Jupiter keine Playwright-Suite hat (s. Memory „Keine E2E-Coverage").

### Security-Audit (Red-Team-Kurzcheck)
- Kein neuer Endpoint, kein neues Auth-Verhalten im Anwendungscode — Angriffsfläche bleibt bei `GET /engines` (bestehend, bereits durch JWT geschützt, unverändert getestet in `test_proj18_engines.py`).
- Registry-Loader hat **keine Duplicate-Key-Prüfung** beim Datei-Load (`registry.py:445-453`) — bestätigt kein Sicherheitsrisiko für PROJ-81 selbst (Kollision ausgeschlossen), aber ein latentes Risiko für künftige Registry-Einträge generell (außerhalb dieses Feature-Scopes, nicht PROJ-81-Bug).
- Offene Infra-Punkte (3–6) sind selbst sicherheitsrelevant: bis Deploy erfolgt ist, existiert kein Dashboard-Zugriffspunkt — kein Expositionsrisiko vor Deploy, aber `forward_auth`-Korrektheit muss beim Deploy verifiziert werden (kein Login-Bypass über `hermes.auxevo.tech`).

### Bugs
Keine Code-Bugs gefunden. **4 offene Punkte sind fehlende Deploy-Scope-Arbeit** (keine Implementierungsfehler):
- **High** — Kriterium 3 (systemd-Service) fehlt.
- **High** — Kriterium 4 (`forward_auth`/Caddy) fehlt.
- **High** — Kriterium 5 (Web-UI-Build) fehlt.
- **High** — Kriterium 6 (DNS/https) fehlt.

Diese vier sind laut Tech Design explizit dem Deploy-Schritt zugeordnet („Aufwand-Verteilung: Deploy/Infra = Hauptanteil") — kein Rücksprung zu Frontend/Backend nötig, sondern direkte Weiterleitung an `/abc-deploy`.

### Production-Ready
**NOT READY** — 4 offene High-Punkte, alle reines Deploy-Scope (kein Code-Fix nötig).

## Deployment
_To be added by /deploy_
