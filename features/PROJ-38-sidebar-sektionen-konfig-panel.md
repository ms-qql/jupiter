# PROJ-38: Sidebar-Sektionen + Konfigurations-Panel (Sichtbarkeit, Reihenfolge, RESET)

## Status: Planned
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-3 (Cockpit / Session-Rail) — die linke Sidebar (`session-rail.tsx`), die hier strukturiert und konfigurierbar wird.

## Beschreibung
Die linke Sidebar wird in **benannte Sektionen** gegliedert und um ein **Konfigurations-Panel** erweitert. Heute hängen Doku und Dateien als lose Schnelllinks über der Session-Liste; künftig stehen sie unter einer eigenen Überschrift **„Workspace"** (Klärung 2026-06-25; Mission Control bleibt im Header). Neben der Überschrift sitzt ein kleines **Einstellungs-Icon** (vgl. Bild 8), das ein Panel öffnet (vgl. Bild 9), in dem der Nutzer pro Sektionseintrag die **Sichtbarkeit** umschaltet (Auge), die **Reihenfolge** per Drag verändert und alles per **RESET** auf Default zurücksetzt. Die Präferenzen werden **client-seitig (localStorage)** gespeichert — reine UI-Präferenz, kein Backend, analog zum Theme.

Dieses Feature liefert das **strukturelle Gerüst** (benannte, konfigurierbare Sektionen), auf das PROJ-39 (Orchestration) und PROJ-40 (Micro-Apps) als weitere Sektionen aufsetzen.

## User Stories
- Als Nutzer möchte ich, dass Doku und Dateien unter einer klaren Überschrift **„Workspace"** gruppiert sind, damit die Sidebar strukturiert wirkt statt loser Links.
- Als Nutzer möchte ich neben der Überschrift ein **Einstellungs-Icon**, über das ich die Sidebar konfiguriere, damit die Anpassung dort sitzt, wo sie wirkt.
- Als Nutzer möchte ich im Konfig-Panel einzelne Einträge **ausblenden/einblenden** (Auge), damit ich nur sehe, was ich nutze.
- Als Nutzer möchte ich Einträge per **Drag-and-Drop umsortieren**, damit meine wichtigsten oben stehen.
- Als Nutzer möchte ich einen **RESET-Knopf**, der die Standard-Sichtbarkeit und -Reihenfolge wiederherstellt, damit ich Fehlkonfigurationen rückgängig mache.
- Als Nutzer möchte ich, dass meine Einstellungen **nach Reload erhalten** bleiben, damit ich nicht jedes Mal neu konfiguriere.

## Acceptance Criteria
- [ ] Die Sidebar zeigt eine Sektions-Überschrift **„Workspace"** über den Einträgen Doku und Dateien (Stil wie bestehende „Aktive Sessions"-Überschrift: uppercase, gedämpft).
- [ ] Mission Control bleibt im **Header** (nicht in die Workspace-Sektion verschoben).
- [ ] Neben der Workspace-Überschrift erscheint ein **kleines Einstellungs-Icon** (Tooltip „Sidebar anpassen").
- [ ] Klick auf das Icon öffnet ein **Konfig-Panel** (Popover/Sheet) mit der Liste aller konfigurierbaren Sidebar-Einträge.
- [ ] Jeder Eintrag im Panel hat ein **Auge-Icon**: Klick blendet den Eintrag in der Sidebar aus bzw. wieder ein (sofort sichtbar).
- [ ] Einträge im Panel sind per **Drag** umsortierbar; die neue Reihenfolge spiegelt sich sofort in der Sidebar.
- [ ] Ein **RESET**-Knopf stellt Default-Sichtbarkeit und -Reihenfolge wieder her.
- [ ] Sichtbarkeit + Reihenfolge werden in **localStorage** gespeichert und nach Reload korrekt wiederhergestellt.
- [ ] Das Panel führt eine kurze Hilfezeile („Ziehen zum Sortieren · Auge zum Ausblenden") analog Bild 9.
- [ ] Die **„Aktive Sessions"**-Sektion und die Session-Liste (PROJ-3) bleiben funktionsfähig; Sessions selbst werden im Panel **nicht** als einzelne Einträge gelistet (nur die Sektion als Ganzes ist togglebar — siehe Edge Cases).
- [ ] Texte deutsch.

## Edge Cases
- **Alle Einträge ausgeblendet** → die Sidebar bleibt nutzbar; das Einstellungs-Icon bzw. der Zugang zum Panel ist **immer** erreichbar (nicht ausblendbar), damit man sich nicht aussperrt.
- **Unbekannter/veralteter localStorage-Eintrag** (z. B. eine Sektion existiert nicht mehr) → wird ignoriert; neue Default-Einträge erscheinen sichtbar an Default-Position.
- **Neue Sektion kommt per Update dazu** (z. B. PROJ-39/40) → erscheint per Default **sichtbar** an definierter Position, auch wenn schon eine gespeicherte Konfig existiert (Merge, kein Verlust bestehender Prefs).
- **Mobile (Drawer):** Panel + Toggles funktionieren auch im Mobile-Sidebar-Drawer (PROJ-3); Drag muss touch-tauglich sein oder auf Mobile ein Pfeil-hoch/runter-Fallback bieten.
- **localStorage nicht verfügbar** (Privatmodus/blockiert) → App fällt auf Defaults zurück, kein Crash; Änderungen gelten dann nur für die Session.
- **„Aktive Sessions"-Sektion ausgeblendet** → die Sessions sind weiter über das Board erreichbar; kein verwaister Zustand.

## Technical Requirements (optional)
- **Frontend-only**; betrifft `nextjs_app/components/cockpit/session-rail.tsx` (Sektions-Rendering + Workspace-Überschrift + Icon) und eine **neue** Konfig-Panel-Komponente (z. B. `sidebar-config-panel.tsx`) sowie einen kleinen Prefs-Hook/Provider (localStorage).
- **Keine** Backend-/API-Änderung.
- Konfigurierbare Einträge als **zentrale Definition** (Array von Sidebar-Items mit `key`, `label`, `icon`, `section`, `defaultVisible`, `defaultOrder`) — Voraussetzung dafür, dass PROJ-39/40 ihre Einträge dort registrieren.
- Drag-and-Drop bevorzugt mit bereits vorhandenen Mitteln / leichtem dnd; **keine** schweren neuen Pakete ohne Not.
- shadcn/ui-Bausteine (Popover/Sheet, Button, Toggle/Switch) wiederverwenden.
- localStorage-Key versioniert (z. B. `jupiter.sidebar.v1`) für spätere Migrationen.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
