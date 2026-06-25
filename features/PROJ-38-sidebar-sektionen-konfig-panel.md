# PROJ-38: Sidebar-Sektionen + Konfigurations-Panel (Sichtbarkeit, Reihenfolge, RESET)

## Status: Architected
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
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (App Router) + Tailwind + shadcn/ui — **Frontend-only**, kein Backend · **Branch:** dev

### Grundsatz
Reine UI-Präferenz, exakt wie das Theme: ein client-seitiger Provider hält Sichtbarkeit + Reihenfolge, spiegelt sie nach `localStorage` und füttert die Sidebar. Kein API-, kein DB-Anteil. Das Feature liefert das **Gerüst**, auf das PROJ-39/40 nur noch ihre Einträge in die zentrale Definition eintragen.

### A) Component Structure (Visual Tree)
```
SidebarPrefsProvider               (neu · Context, wraps Cockpit-Layout — analog ThemeProvider)
└── SessionRail                    (umgebaut: rendert Sektionen aus zentraler Definition)
    ├── Header: 🛰️ Jupiter + „+ Neu"        (unverändert; Mission Control bleibt im Header)
    ├── Sektion „WORKSPACE"                  (neue Überschrift, Stil wie „Aktive Sessions")
    │   ├── SettingsIcon-Button  → öffnet Konfig-Panel   (Tooltip „Sidebar anpassen")
    │   ├── Doku-Eintrag      (togglebar / sortierbar)
    │   └── Dateien-Eintrag   (togglebar / sortierbar)
    ├── Sektion „AKTIVE SESSIONS"            (als Ganzes togglebar; Sessions NICHT einzeln gelistet)
    │   └── Session-Liste + Archiv           (PROJ-3 unverändert)
    └── Footer: „Zum Board →"                (unverändert)

SidebarConfigPanel                 (neu · sidebar-config-panel.tsx, im Popover/Sheet)
├── Hilfezeile „Ziehen zum Sortieren · Auge zum Ausblenden"
├── Liste konfigurierbarer Einträge
│   └── ConfigRow: [Drag-Griff] Label  [▲/▼ Mobile-Fallback]  [👁 Auge-Toggle]
└── RESET-Button
```

### B) Daten- / Konfig-Modell (plain language, kein Code)
Zwei Bausteine, beide rein im Frontend:

**1. Zentrale Definition** (`lib/sidebar-config.ts`) — die „Wahrheit", was es überhaupt gibt:
```
Jeder Sidebar-Eintrag hat:
- key            (stabile ID, z. B. "doku", "dateien", "sessions")
- label          (Anzeigename, deutsch)
- icon           (lucide-Icon)
- section        ("workspace" | "sessions" | später "orchestration"/"micro-apps")
- defaultVisible (true/false)
- defaultOrder   (Default-Position)
```
PROJ-39/40 fügen hier künftig nur Zeilen hinzu — sonst nichts.

**2. Nutzer-Präferenz** (im `SidebarPrefsProvider`, persistiert):
```
Pro key:  { visible: bool, order: zahl }
Gespeichert in localStorage unter dem versionierten Key  "jupiter.sidebar.v1"
```
**Merge-Regel (wichtig):** Beim Laden wird die gespeicherte Prefs-Map über die Definition *gemerged*, nicht ersetzt:
- key in Def **und** Prefs → Pref gewinnt (Nutzerwunsch bleibt).
- key nur in Def (neu per Update, z. B. PROJ-39) → erscheint sichtbar an `defaultOrder`.
- key nur in Prefs (veraltet/entfernt) → ignoriert.
So gehen weder bestehende Einstellungen verloren noch sperrt eine alte Konfig neue Features aus.

### C) API Shape
**Keine.** Frontend-only, kein Endpoint, keine Schema-/DB-Änderung.

### D) Tech Decisions (WHY)
- **localStorage statt Backend:** Es ist eine persönliche Ansichts-Präferenz ohne Mehrtenant-/Sicherheitsrelevanz — genau wie das Theme, das bereits über `next-themes` in `localStorage` lebt. Ein Server-Roundtrip wäre Overkill.
- **Versionierter Key `jupiter.sidebar.v1`:** erlaubt spätere strukturelle Migrationen, ohne alte Daten „erben" zu müssen.
- **Definition getrennt von Prefs:** Die Trennung „was existiert" (Code) vs. „wie der Nutzer es will" (Storage) ist die Voraussetzung dafür, dass PROJ-39/40 ohne Storage-Bruch andocken (siehe Merge-Regel).
- **Settings-Icon an der „Workspace"-Überschrift statt globalem Menü:** Anpassung sitzt dort, wo sie wirkt (Spec-Wunsch, Bild 8/9). Der Panel-Zugang ist **nie ausblendbar** → kein Aussperren.
- **Drag ohne schweres Paket:** Reorder per **nativer HTML5-Drag-and-Drop** (dasselbe Mittel, das PROJ-11 Fileexplorer schon nutzt) — kein `@dnd-kit`/`react-dnd` nötig. Für Touch/Mobile zusätzlich **▲/▼-Buttons** je Zeile als gleichwertiger, immer funktionierender Fallback (Spec-Edge-Case Mobile).
- **Hydration-sicher:** Der Prefs-Hook übernimmt das `mounted`-Flag-Muster des bestehenden `theme-toggle`, damit Server- und Client-Render nicht divergieren; bei blockiertem localStorage (Privatmodus) → stiller Fallback auf Defaults, kein Crash (Edge-Case).
- **Auge = Sichtbarkeit sofort:** Toggle schreibt in den Provider-State → Sidebar re-rendert unmittelbar; Persistenz passiert nebenher.

### E) Dependencies (Pakete)
Bestehende shadcn/ui-Bausteine vorhanden: Button, ScrollArea, Dialog, Separator, Label. **Neu via `shadcn add` zu generieren** (copy-paste-Komponenten, keine schwere Lib): **Popover** (Desktop-Panel), **Switch** (Auge/Sichtbarkeit), **Tooltip** (Icon-Hinweis); für Mobile-Drawer optional **Sheet**. **Keine** neue Drag-Bibliothek (native HTML5 DnD). **Keine** Backend-Pakete.

### Betroffene Dateien (Orientierung, kein Auftrag an Code)
- umbauen: `nextjs_app/components/cockpit/session-rail.tsx` (Sektions-Rendering aus Definition, Workspace-Überschrift + Settings-Icon)
- neu: `nextjs_app/lib/sidebar-config.ts` (zentrale Item-Definition)
- neu: `nextjs_app/components/cockpit/sidebar-prefs-provider.tsx` (Context + `useSidebarPrefs`-Hook + localStorage-Merge/Reset) — eingehängt im Cockpit-Layout neben `SessionsProvider`
- neu: `nextjs_app/components/cockpit/sidebar-config-panel.tsx` (Panel-UI: Auge, Reorder, RESET, Hilfezeile)
- ggf. neu: `nextjs_app/components/ui/{popover,switch,tooltip,sheet}.tsx` (shadcn-generiert)

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
