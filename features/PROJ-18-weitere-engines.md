# PROJ-18: Weitere Engines (Codex/Gemini/GLM/Ollama) + iFrame/Launch

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #13

## Dependencies
- Requires: PROJ-1 (Engine-Treiber-Modell) — das Treiber-Interface ist die Abstraktion, gegen die neue Engines gebaut werden.
- Verwandt: PROJ-22 (Modell-Routing) und P2 Cross-Agent-Review (#30), das Multi-Engine voraussetzt.

## Beschreibung
Das Integrations-Spektrum aus drei Tiefen — **Treiber → iFrame → Startknopf** — macht Integration zu keinem Alles-oder-nichts: ein generischer **CLI-Adapter** für weitere Engines (Codex/Gemini/GLM/Ollama), das **Einbetten** fremder Web-Apps als iFrame, und ein simpler **Launch-Button** für alles andere. Nach oben sehen alle Engines gleich aus (gleiche Session-Sicht).

## User Stories
- Als Nutzer möchte ich beim Session-Start neben Claude Max weitere Engines wählen können (sofern konfiguriert).
- Als Nutzer möchte ich eine fremde Engine über einen **generischen CLI-Adapter** einbinden, ohne Jupiters Kern zu ändern.
- Als Nutzer möchte ich eine fremde Web-App (z. B. ein Tool) als **iFrame** in Jupiter einbetten.
- Als Nutzer möchte ich für nicht integrierbare Tools einen einfachen **Startknopf** (öffnet/launcht extern).
- Als Nutzer möchte ich, dass eine Nicht-Claude-Session in Cockpit/Kanban genauso erscheint wie eine Claude-Session.

## Acceptance Criteria
- [ ] Ein **generischer CLI-Treiber** implementiert dasselbe Treiber-Interface wie der Claude-Treiber (start/lesen/steuern/stop) und kann per Konfiguration auf andere CLI-Engines gemappt werden.
- [ ] Mindestens eine zweite Engine ist exemplarisch lauffähig integriert (Treiber-Tiefe), als Nachweis der Abstraktion.
- [ ] **iFrame-Einbettung**: eine konfigurierte URL wird als eingebettete App angezeigt (mit DSGVO-/CSP-konformer Konfiguration).
- [ ] **Launch-Button**: konfigurierbarer Eintrag, der ein externes Tool öffnet/startet.
- [ ] Session-Sicht (Status/Ampel/Kanban) ist **engine-agnostisch**; engine-spezifische Felder degradieren sauber (z. B. kein Token-Füllstand bei Engines ohne Usage).
- [ ] Engine-Auswahl im Smart Launcher (PROJ-9); Claude Max bleibt Default.
- [ ] Fehlende/fehlkonfigurierte Engine → klare Meldung, kein Crash, Claude bleibt nutzbar.
- [ ] Alle Texte deutsch.

## Edge Cases
- **Engine liefert kein Stream-JSON** (anderes Protokoll) → Adapter normalisiert oder degradiert sichtbar (eingeschränkte Live-Sicht).
- **iFrame verweigert Einbettung** (X-Frame-Options) → klarer Hinweis + Fallback Launch-Button.
- **Engine ohne Modell-Routing/Usage** → betroffene Anzeigen als „n/v" statt 0/Fehler.
- **Auth/Key fehlt** für eine API-Engine → Setup-Hinweis, Engine ausgegraut.
- **Mehrere Engines gleichzeitig** → Limit-/Watchdog-Logik (PROJ-14/16) gilt engine-übergreifend.

## Technical Requirements (optional)
- Treiber-Interface aus PROJ-1 bleibt die einzige Kopplung; neue Engines als Plug-in/Adapter.
- iFrame/CSP DSGVO-konform (keine US-CDNs erzwingen); Secrets nie im Frontend.
- Konfiguration der Engines zentral (Settings), ohne Codeänderung pro Engine-Variante.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
