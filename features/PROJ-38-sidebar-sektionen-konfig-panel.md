# PROJ-38: Sidebar-Sektionen + Konfigurations-Panel (Sichtbarkeit, Reihenfolge, RESET)

## Status: Approved
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

## Implementation Notes (Frontend)
**Umgesetzt:** 2026-06-25 · **Branch:** dev · Build + Lint + tsc grün.

**Neue Dateien:**
- `nextjs_app/lib/sidebar-config.ts` — zentrale Definition (`SIDEBAR_SECTIONS`, `SIDEBAR_ITEMS` mit `key/label/icon/href/section/defaultVisible/defaultOrder`). Einzige Andock-Stelle für PROJ-39/40. „Aktive Sessions" ist EIN Eintrag (`key: "sessions"`, ohne `href`).
- `nextjs_app/components/cockpit/sidebar-prefs-provider.tsx` — Context + `useSidebarPrefs`-Hook. Hält `{visible, order}` pro key, persistiert nach `localStorage["jupiter.sidebar.v1"]`. **Merge** beim Laden (Defaults für neue/unbekannte keys, Nutzerwunsch gewinnt). `mounted`-Flag via `requestAnimationFrame` (Repo-Muster, Hydration-sicher); Storage-Fehler → stiller Default-Fallback. API: `visibleItems/allItems(section)`, `toggleVisible`, `move(±1)`, `reorder(from,before)`, `reset`.
- `nextjs_app/components/cockpit/sidebar-config-panel.tsx` — `SidebarConfigButton` (Gear `Settings2Icon`) öffnet Popover. Pro Sektion gruppierte Liste; je Zeile Drag-Griff, ▲/▼ (Touch-Fallback), Auge (`Eye`/`EyeOff`). RESET „Auf Standard zurücksetzen". Hilfezeile „Ziehen zum Sortieren · Auge zum Ausblenden".
- `nextjs_app/components/ui/popover.tsx` — shadcn-/Base-UI-Wrapper (`@base-ui/react/popover`), analog `select.tsx`/`dialog.tsx`. (Switch/Tooltip nicht nötig: Auge = Icon-Toggle, Tooltip via `title`-Attribut.)

**Geändert:**
- `nextjs_app/components/cockpit/session-rail.tsx` — rendert „Workspace"-Überschrift (Stil wie „Aktive Sessions") mit Gear daneben; Workspace-Einträge aus `visibleItems("workspace")` (Reihenfolge inkl.); Sessions-Sektion nur wenn `sessions` sichtbar, sonst `flex-1`-Platzhalter (Footer bleibt unten). Mission Control unberührt (Header).
- `nextjs_app/app/(cockpit)/layout.tsx` — `SidebarPrefsProvider` umschließt `CockpitShell` (teilt State über Desktop-Rail + Mobile-Drawer).

**Abweichungen/Entscheidungen:** Kein neues DnD-Paket (natives HTML5-DnD, `reorder` on drop). Auge statt Switch (entspricht Spec-UX). Gear sitzt an der Workspace-Überschrift und ist nie ausblendbar → kein Aussperren (Edge-Case erfüllt).

**Offen für QA:** Touch-Drag real auf Mobile (▲/▼-Fallback vorhanden); Verhalten bei blockiertem localStorage; Merge nach simuliertem PROJ-39-Item.

## QA Test Results
**Getestet:** 2026-06-25 · **Branch:** dev · **Methode:** Vitest-Unit (Pure-Logik + Config-Invarianten) + statischer Code-Review gegen jedes Kriterium. Repo-Konvention: node-Env-Vitest (kein jsdom) → DOM-Interaktion per Code-Review verifiziert, Live-Browser/Touch als Rest-Check markiert.

**Tests:** `nextjs_app/lib/sidebar-config.test.ts` (5) + `nextjs_app/components/cockpit/sidebar-prefs-provider.test.ts` (15). Gesamte Suite **152/152 grün**, `next build` + `tsc` + ESLint grün.
- QA-Seam: Merge-/Reorder-/Toggle-Logik wurde behavior-preserving in exportierte pure Funktionen (`buildDefaults`, `mergeStored`, `togglePref`, `movePref`, `reorderPref`) gezogen, damit sie ohne DOM testbar ist. Keine Verhaltensänderung.

### Akzeptanzkriterien
| # | Kriterium | Ergebnis | Beleg |
|---|-----------|----------|-------|
| 1 | „Workspace"-Überschrift über Doku/Dateien, Stil uppercase/gedämpft | ✅ Pass | `session-rail.tsx` Heading-Klasse identisch zu „Aktive Sessions" |
| 2 | Mission Control bleibt im Header | ✅ Pass | Rail enthält kein Mission Control; unberührt |
| 3 | Einstellungs-Icon neben Überschrift, Tooltip „Sidebar anpassen" | ✅ Pass | `SidebarConfigButton` mit `title`+`aria-label` |
| 4 | Klick öffnet Konfig-Panel mit Liste aller Einträge | ✅ Pass | Popover rendert `allItems` je Sektion |
| 5 | Auge blendet sofort aus/ein | ✅ Pass | `togglePref` → Provider-State → Rerender; Test ✓ |
| 6 | Drag-Reorder spiegelt sofort in der Sidebar | ✅ Pass | `reorderPref` (HTML5-DnD) → State; Test ✓ |
| 7 | RESET stellt Default-Sichtbarkeit/-Reihenfolge her | ✅ Pass | `reset()=buildDefaults()`; Test ✓ |
| 8 | Sichtbarkeit+Reihenfolge in localStorage, Reload-fest | ✅ Pass | `jupiter.sidebar.v1`, `mergeStored`; Tests ✓ |
| 9 | Hilfezeile „Ziehen zum Sortieren · Auge zum Ausblenden" | ✅ Pass | Panel-Markup |
| 10 | Aktive-Sessions-Sektion funktioniert; Sessions nicht einzeln gelistet | ✅ Pass | Sessions = EIN togglebarer Eintrag; Liste/Archiv unverändert |
| 11 | Texte deutsch | ✅ Pass | gesamte UI |

### Edge Cases
| Fall | Ergebnis | Beleg |
|------|----------|-------|
| Alle Einträge ausgeblendet → Panel-Zugang bleibt | ✅ Pass | Überschrift+Gear immer gerendert (nicht togglebar) |
| Veralteter/unbekannter localStorage-Key | ✅ Pass | `mergeStored` ignoriert; Test ✓ |
| Neue Sektion trotz gespeicherter Konfig sichtbar (Merge) | ✅ Pass | Test „neue Sektion erscheint sichtbar an Default-Position" ✓ |
| Kaputter Storage-Inhalt (falsche Typen / null / Unsinn) | ✅ Pass | Default-Fallback, kein Crash; Tests ✓ |
| localStorage blockiert (Privatmodus) | ✅ Pass | try/catch → Defaults, Änderung nur für Session |
| Aktive-Sessions-Sektion ausgeblendet → Sessions über Board erreichbar | ✅ Pass | Footer „Zum Board" bleibt; `flex-1`-Platzhalter |
| Mobile-Drawer: Panel + Toggles + Sortieren | ⚠️ Logik ok, Live offen | ▲/▼-Touch-Fallback vorhanden; Popover z-50 > Drawer z-40 — **echtes Touch-Drag noch nicht im Browser geprüft** |

### Security (Red-Team)
- Reine Client-Präferenz, **kein Backend/Auth/Tenant** → kein Tenant-Leak/Auth-Bypass-Vektor.
- Kein XSS: Labels stammen aus statischer Definition, nicht aus Nutzereingaben; `JSON.parse` in try/catch.
- Keine Secrets/Netzwerk im Feature. → **Keine Findings.**

### Bugs
Keine Critical/High/Medium gefunden.
- **Low (offen, nicht blockierend):** Live-Browser-Smoke (Touch-Drag auf 375px, Reload-Persistenz visuell, Popover im Mobile-Drawer) steht aus — headless QA. Empfehlung: kurzer manueller Check vor/nach Deploy.

### Production-Ready: **JA** (keine Critical/High; 1 Low = manueller Browser-Smoke empfohlen)

## Deployment
_To be added by /deploy_
