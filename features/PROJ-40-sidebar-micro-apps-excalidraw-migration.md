# PROJ-40: Sidebar-Sektion „Micro-Apps" + Excalidraw-Migration aus „Werkzeuge"

## Status: Planned
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-38 (Sidebar-Sektionen + Konfig-Panel) — „Micro-Apps" ist eine neue, konfigurierbare Sektion im Gerüst.
- Requires: PROJ-3 (Cockpit-Shell / Routing) — Klick öffnet eine Vollbild-Ansicht im Hauptbereich.
- Bezug: PROJ-18 (Engine-Registry / `engines.yaml`, Eintrag `whiteboard`) — Excalidraw ist heute dort als `kind: iframe` definiert und erscheint im „Werkzeuge"-Tab.
- Verwandt: PROJ-39 (Orchestration) — teilt die iFrame-Einbettungs- und Registry-Mechanik; das `group`-Feld unterscheidet beide Sektionen.

## Beschreibung
Unter der Sektion „Orchestration" (PROJ-39) entsteht eine weitere Sidebar-Sektion **„Micro-Apps"**, in der **kleine Einzel-Programme** als Navigationspunkte erscheinen, per iFrame im Hauptbereich eingebettet und so direkt **gelauncht** werden. Als erstes Beispiel wird **Excalidraw (Whiteboard)** aus dem **„Werkzeuge"-Tab herausgenommen** und in die Micro-Apps-Sektion verschoben.

Abgrenzung (Klärung 2026-06-25): *Micro-Apps* = kleine Einzel-Tools (Excalidraw). Vollwertige Agenten-Orchestrierungs-Apps gehören in **Orchestration** (PROJ-39).

## User Stories
- Als Nutzer möchte ich eine Sidebar-Sektion **„Micro-Apps"**, in der ich kleine Programme sammle und direkt starte, damit Tools nicht im „Werkzeuge"-Tab versteckt sind.
- Als Nutzer möchte ich **Excalidraw** aus der Micro-Apps-Sektion per Klick im Hauptbereich öffnen, damit ich schnell skizzieren kann.
- Als Nutzer möchte ich, dass Excalidraw **nicht mehr** im „Werkzeuge"-Tab auftaucht, damit es nur an einer Stelle lebt.
- Als Nutzer möchte ich künftig **weitere Micro-Apps** ohne großen Aufwand ergänzen können, damit die Sektion mit mir wächst.
- Als Nutzer möchte ich die Micro-Apps-Sektion über das Konfig-Panel (PROJ-38) **aus-/einblenden und sortieren**.

## Acceptance Criteria
- [ ] Neue Sidebar-Sektion **„Micro-Apps"** erscheint **unter** der Orchestration-Sektion.
- [ ] Die Sektion enthält **Excalidraw (Whiteboard)** mit Label + Icon.
- [ ] Klick auf Excalidraw öffnet eine **Vollbild-Ansicht im Hauptbereich** (eigene Route, z. B. `/apps/[key]`) mit dem eingebetteten iFrame.
- [ ] Excalidraw erscheint **nicht mehr** im „Werkzeuge"-Tab (`tools-panel.tsx`); der Werkzeuge-Tab bleibt für die übrigen Engines/Tools funktionsfähig (kein leerer/kaputter Tab).
- [ ] Verweigert eine Micro-App das Einbetten, greift der **„In neuem Tab öffnen"-Fallback** (wie `embed-tab.tsx`).
- [ ] Die Sektion + ihre Einträge sind über das **Konfig-Panel (PROJ-38)** toggelbar und sortierbar.
- [ ] Micro-Apps sind **zentral konfiguriert** (Registry mit `group: microapp`), sodass weitere Apps ohne Code-Wildwuchs ergänzt werden können.
- [ ] Texte/Labels deutsch (App-Eigennamen bleiben).

## Edge Cases
- **Werkzeuge-Tab nach Migration leer?** → Falls nach Entfernen von Excalidraw keine iFrame-/Launch-Engines mehr übrig sind, zeigt der Tab einen sauberen Leer-/Hinweiszustand statt einer kaputten Fläche (oder Tab entsprechend ausblenden — in Architektur zu entscheiden).
- **App verweigert Einbettung (CSP/X-Frame-Options)** → Fallback „In neuem Tab öffnen".
- **App nicht erreichbar** → Fehler-/Retry-Hinweis, kein Crash.
- **Doppelregistrierung** (Excalidraw versehentlich in Werkzeuge **und** Micro-Apps) → vermeiden: genau eine Quelle/`group` entscheidet die Platzierung.
- **Sektion über Konfig-Panel ausgeblendet** → Route per direkter URL erreichbar; kein verwaister Zustand.
- **Mobile:** Vollbild-iFrame nutzt die Hauptfläche; Sidebar-Drawer schließt nach Auswahl.

## Technical Requirements (optional)
- **Frontend** + **Config**; voraussichtlich **keine** Anwendungs-API-Änderung.
- **Registry/`engines.yaml`:** Excalidraw-Eintrag (`whiteboard`) erhält die Gruppen-Zuordnung `group: microapp`; `tools-panel.tsx` filtert Micro-Apps **heraus** (zeigt nur noch verbleibende Tools), die Sidebar-Sektion zeigt die `group: microapp`-Einträge an.
- iFrame-Einbettung über die bestehende `embed-tab.tsx`-Logik (Sandbox + `onError`-Fallback) wiederverwenden.
- Gemeinsamer Registry-/Routing-Ansatz mit PROJ-39 (nur anderes `group`-Feld → andere Sektion + Route-Präfix).
- Texte deutsch.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
