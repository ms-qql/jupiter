# PROJ-39: Sidebar-Sektion „Orchestration" — Fremd-Apps per iFrame (Paperclip, Wayland)

## Status: Planned
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-38 (Sidebar-Sektionen + Konfig-Panel) — „Orchestration" ist eine neue, konfigurierbare Sektion in diesem Gerüst.
- Requires: PROJ-3 (Cockpit-Shell / Routing) — die Sektion sitzt unter „Aktive Sessions"; Klick öffnet eine Vollbild-Ansicht im Hauptbereich.
- Bezug: PROJ-18 (Engine-Registry / `engines.yaml`, `kind: iframe`) — bestehende iFrame-Einbettungs-Mechanik (`embed-tab.tsx`) wird wiederverwendet.

## Beschreibung
Unter der Sektion „Aktive Sessions" entsteht eine neue Sidebar-Sektion **„Orchestration"**, in der **andere Agenten-Orchestrierungs-Apps** als Navigationspunkte erscheinen und im Hauptbereich **per iFrame** eingebettet werden. Die ersten beiden Einträge sind **Paperclip** und **Wayland**, beide bereits auf dem VPS installiert.

Abgrenzung (Klärung 2026-06-25): *Orchestration* = vollwertige Agenten-Orchestrierungs-Apps (Paperclip, Wayland). Kleine Einzel-Tools (z. B. Excalidraw) gehören in **Micro-Apps** (PROJ-40).

**Bekanntes Risiko (Mixed-Content):** Die Apps sind über `http://` auf Tailscale-IPs erreichbar (Wayland `http://100.80.219.113:3000/`, Paperclip `http://100.80.219.113:3100`). Jupiter läuft unter `https://jupiter.auxevo.tech`. Ein `http`-iFrame in einer `https`-Seite wird vom Browser als **Mixed Content hart blockiert** — noch vor jedem JS-`onError`-Fallback. Lösung (Architektur-Phase): beide Apps via **Caddy-Reverse-Proxy** unter `https://…` (eigener Host oder Subpfad) ausliefern und Jupiter auf die `https`-URL zeigen lassen. Ohne diese Lösung ist nur der „In neuem Tab öffnen"-Fallback nutzbar.

## User Stories
- Als Nutzer möchte ich in der Sidebar eine Sektion **„Orchestration"** mit meinen anderen Orchestrierungs-Apps, damit ich nicht zwischen Tabs/Tools springen muss.
- Als Nutzer möchte ich **Paperclip** und **Wayland** per Klick **direkt eingebettet** im Jupiter-Hauptbereich öffnen, damit ich sie ohne Kontextwechsel nutze.
- Als Nutzer möchte ich, dass eine App, die das Einbetten verweigert, mir einen **„In neuem Tab öffnen"-Fallback** zeigt statt einer leeren/kaputten Fläche.
- Als Nutzer möchte ich die Orchestration-Sektion und ihre Einträge über das Konfig-Panel (PROJ-38) **aus-/einblenden und sortieren**, damit ich nur sehe, was ich nutze.

## Acceptance Criteria
- [ ] Neue Sidebar-Sektion **„Orchestration"** erscheint **unter** „Aktive Sessions".
- [ ] Die Sektion enthält die Einträge **Paperclip** und **Wayland** mit Label + Icon.
- [ ] Klick auf einen Eintrag öffnet eine **Vollbild-Ansicht im Hauptbereich** (eigene Route, z. B. `/orchestration/[key]`), die die App **per iFrame** einbettet.
- [ ] Verweigert die App die Einbettung (X-Frame-Options/CSP) **und** wird sie über `https` ausgeliefert, zeigt die Ansicht den **„In neuem Tab öffnen"-Fallback** (wie `embed-tab.tsx`).
- [ ] Die Sektion + ihre Einträge sind über das **Konfig-Panel (PROJ-38)** toggelbar und sortierbar.
- [ ] Die App-Einträge sind **zentral konfiguriert** (Registry), sodass weitere Orchestration-Apps ohne Code-Wildwuchs ergänzt werden können.
- [ ] Texte/Labels deutsch (App-Eigennamen bleiben).

## Edge Cases
- **Mixed-Content (http-App in https-Jupiter):** Solange kein https-Proxy existiert, lädt der iFrame nicht; die Ansicht zeigt einen **klaren Hinweis** („Einbettung blockiert — über Reverse-Proxy bereitstellen oder in neuem Tab öffnen") + Fallback-Button, **kein** stiller Leer-Frame.
- **App nicht erreichbar / Port down** → Ansicht zeigt einen Fehler-/Offline-Hinweis + Retry/Neuer-Tab, kein Crash.
- **App setzt X-Frame-Options: DENY** → Fallback „In neuem Tab öffnen".
- **Tailscale nicht verbunden** (Client außerhalb des Tailnet) → App nicht erreichbar; gleicher Offline-Hinweis.
- **Sektion über Konfig-Panel ausgeblendet** → Routen bleiben per direkter URL erreichbar; kein verwaister Zustand.
- **Mobile:** Vollbild-iFrame nutzt die Hauptfläche; Sidebar-Drawer schließt nach Auswahl.

## Technical Requirements (optional)
- **Frontend** + **Infra**; **keine** Anwendungs-API-Änderung im Backend zwingend nötig.
- **Infra (Architektur/Deploy):** Caddy-Reverse-Proxy-Einträge, die Wayland (`:3000`) und Paperclip (`:3100`) unter `https://…auxevo.tech` ausliefern, damit Mixed-Content entfällt. URLs danach in der Registry/Config hinterlegen.
- **Registry:** Orchestration-Apps als Einträge mit `key`, `label`, `icon`, `url`, `sandbox` — bevorzugt Wiederverwendung des `engines.yaml`-Mechanismus mit einem **Gruppen-Feld** (`group: orchestration`), das Sidebar/Filter auswerten (gemeinsam mit PROJ-40 zu entscheiden).
- iFrame-Einbettung über die bestehende `embed-tab.tsx`-Logik (Sandbox + `onError`-Fallback) wiederverwenden.
- Sandbox-Attribute pro App konfigurierbar.
- Texte deutsch.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
