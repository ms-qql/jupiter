# PROJ-40: Sidebar-Sektion „Micro-Apps" + Excalidraw-Migration aus „Werkzeuge"

## Status: Architected
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
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (App Router) Frontend + FastAPI/`engines.yaml`-Registry · **Branch:** dev

### Überblick / Grundhaltung
„Micro-Apps" ist **kein neuer Mechanismus**, sondern die **zweite Anwendung desselben Musters** wie PROJ-39 (Orchestration) — nur mit `group: micro` statt `group: orchestration`. Wiederverwendet werden exakt dieselben drei Bausteine:
1. **iFrame-Einbettung** (`embed-tab.tsx` — iframe + Sandbox + immer sichtbarer „In neuem Tab öffnen"-Fallback),
2. **zentrale Registry** `engines.yaml`, erweitert um das (mit PROJ-39 gemeinsame) `group`-Feld,
3. **Sidebar-Sektions-Gerüst** PROJ-38 (`sidebar-config.ts` + Konfig-Panel für Sichtbarkeit/Reihenfolge/RESET).

**Entscheidender Unterschied zu PROJ-39:** Die erste Micro-App, **Excalidraw**, liegt bereits unter `https://excalidraw.com` und **erlaubt das Framing** (kein `X-Frame-Options`/Mixed-Content). → **Keine Caddy-/DNS-/Infra-Arbeit nötig.** Reine **Frontend + Config**-Änderung. Der einzige neue Bau ist die Vollbild-Route + die zweite Sidebar-Sektion; beides erbt PROJ-40 von der PROJ-39-Mechanik.

### A) Komponenten-Struktur (UI-Baum)
```
SessionRail (session-rail.tsx, PROJ-38-Sektionsgerüst)
├── Workspace-Sektion (Doku · Dateien)         ← PROJ-38
├── Aktive Sessions                             ← PROJ-3
├── Orchestration                               ← PROJ-39 (group=orchestration)
└── Micro-Apps  ◄── NEU (Sektion UNTER „Orchestration")
    └── Excalidraw  (Label + Icon → Link /apps/whiteboard)
        └── (Einträge aus Registry gefiltert auf group=micro;
             Sichtbarkeit/Reihenfolge über PROJ-38-Konfig-Panel)

Hauptbereich-Route  /apps/[key]   ◄── NEU (Vollbild)
└── MicroAppView
    ├── Kopfzeile: App-Label + „In neuem Tab öffnen" (immer sichtbar)
    ├── iframe (Vollhöhe, Sandbox aus Registry)   ← wiederverwendete embed-Logik
    └── Fallback-/Hinweis-Fläche
        ├── Einbettung verweigert → Fallback-Button (bei Excalidraw nicht zu erwarten)
        └── App nicht erreichbar → Offline-Hinweis + Retry/Neuer Tab
```
> **Routen-Angleichung mit PROJ-39:** PROJ-39 nutzt `/orchestration/[key]`. PROJ-40 nutzt analog `/apps/[key]` (Spec-Vorgabe). Beide rendern dieselbe vollhöhen-`EmbedTab`-Variante — die Route ist nur ein dünner Wrapper, der den Registry-Eintrag per `key` lädt und einbettet. Empfehlung: die in PROJ-39 entstehende Vollbild-View als gemeinsame Komponente (`<EmbeddedAppView engine={…} />`) nutzen, damit `/apps/[key]` und `/orchestration/[key]` sich denselben Renderer teilen (kein Duplikat).

### B) Datenmodell (Klartext — kein DB-Schema)
Kein Backend-DB-Schema. Eine Micro-App ist ein **Registry-Eintrag** in `backend/config/engines.yaml` — der **bestehende `whiteboard`-Eintrag** (`kind: iframe`, `url: https://excalidraw.com`, `sandbox: …`) erhält **nur ein neues Feld**:
```
whiteboard (bestehend):
- key      "whiteboard"          → Routen-Parameter /apps/whiteboard
- label    "Excalidraw"          (App-Eigenname bleibt)
- kind     "iframe"              (unverändert)
- group    "micro"   ◄── NEU: verschiebt den Eintrag aus „Werkzeuge" in die Micro-Apps-Sektion
- icon     lucide-Name (optional, z. B. "PenTool"/"Pencil"; sonst Default)
- url      "https://excalidraw.com"  (unverändert)
- sandbox  (unverändert)
```
Registry wird weiterhin live (mtime-geprüft) geladen — weitere Micro-Apps kommen als reine Datenzeile dazu (Akzeptanzkriterium „zentral konfiguriert, kein Wildwuchs").

> **`group`-Wert mit PROJ-39 abstimmen:** Beide Features führen dasselbe Feld ein. Verbindlich: `group: "orchestration" | "micro" | null` (`null`/fehlt = klassisches Werkzeug). Wer zuerst implementiert, legt das Feld an; der zweite nutzt es nur. Genau **eine** Quelle/`group` entscheidet die Platzierung → keine Doppelregistrierung (Edge Case).

### C) API-Shape (kein neuer Endpunkt)
- `GET /engines` (bestehend) liefert künftig `group` + `icon` je Eintrag (dieselbe Schema-Erweiterung wie PROJ-39 — **nur einmal** nötig: `backend/app/schemas/engines.py` `EngineRead`, Frontend-Typ `nextjs_app/lib/types.ts`).
- **Keine** weitere Backend-API. Das Frontend filtert clientseitig:
  - **Micro-Apps-Sektion:** `group === "micro"`.
  - **Werkzeuge-Tab (`tools-panel.tsx`):** bisheriger iFrame-Filter **plus** `group !== "micro"` (und `!== "orchestration"`) → Excalidraw verschwindet aus „Werkzeuge". Genau hier liegt die „Migration".

### D) „Werkzeuge"-Tab nach Migration (Edge Case entschieden)
Der Werkzeuge-Tab zeigt heute Effizienz-Tools, Launches **und** iFrames. Nach Herausfiltern von Excalidraw bleiben die übrigen Engines/Launches/Tools erhalten → **Tab bleibt funktionsfähig, nicht leer**. Entscheidung: **Tab NICHT ausblenden**; falls die iFrame-Untersektion dadurch leer wird, deren Überschrift einfach weglassen (bestehendes Render-Muster: leere Filter-Arrays erzeugen keine Sektion). Kein Sonder-Leerzustand nötig, solange andere Tools existieren.

### E) Tech-Entscheidungen (WARUM)
- **Gemeinsames `group`-Feld statt zweiter Registry:** ein Mechanismus, zwei Sektionen — Sidebar + Filter werten nur das Feld aus. Mit PROJ-39 abgestimmt.
- **Excalidraw nur „verschieben", nicht neu anlegen:** der Eintrag existiert (`whiteboard`); wir ändern **eine Zeile** (`group: micro`). Verhindert Doppelregistrierung by design.
- **Eigene Vollbild-Route `/apps/[key]` statt Tab:** teilbare URL, saubere History; Sektion bleibt per Direkt-URL erreichbar, auch wenn im Konfig-Panel ausgeblendet (Edge Case „kein verwaister Zustand").
- **iFrame-Logik wiederverwenden:** `embed-tab.tsx` kapselt Sandbox + Fallback schon; die Route nutzt die vollhöhen-Variante aus PROJ-39 statt eigener iframe-Logik.
- **„In neuem Tab öffnen" immer sichtbar:** Garantie gegen die „leere Fläche", falls je eine künftige Micro-App das Framing verweigert (`onError` feuert bei `X-Frame-Options` unzuverlässig). Bei Excalidraw selbst nicht relevant, aber Teil des wiederverwendeten Bausteins.
- **Keine Infra:** Excalidraw ist https + framing-offen → der Caddy-/DNS-Block aus PROJ-39 entfällt hier vollständig.

### F) Abhängigkeiten (Pakete)
- **Keine neuen Pakete.** Icon aus bestehendem `lucide-react` (z. B. `PenTool`/`Pencil`). Sidebar-Sektion + Konfig-Panel liefert PROJ-38; Vollbild-View + `group`-Feld liefert/teilt PROJ-39.

### G) Bau-Reihenfolge / Hand-offs
1. **Voraussetzung:** PROJ-38 (Sektionsgerüst + Konfig-Panel) steht. **Reihenfolge mit PROJ-39 koordinieren:** das `group`+`icon`-Schemafeld und die gemeinsame Vollbild-View nur **einmal** bauen. Idealerweise PROJ-39 zuerst (legt Feld + `<EmbeddedAppView>` an), PROJ-40 hängt sich dran. Falls PROJ-40 zuerst läuft: dann legt PROJ-40 beides an.
2. **Backend (winzig):** `group` + `icon` in `EngineRead`-Schema (falls nicht schon durch PROJ-39); `whiteboard`-Eintrag in `engines.yaml` um `group: micro` (+ optional `icon`) ergänzen.
3. **Frontend:**
   - `EngineRead`-Typ um `group`/`icon` erweitern (falls nicht schon durch PROJ-39).
   - `sidebar-config.ts`: `SIDEBAR_SECTIONS` um `micro` (Label „Micro-Apps", Order **unter** `orchestration`) ergänzen; Sidebar-Eintrag rendert die `getEngines()`-Liste gefiltert auf `group === "micro"` als Links auf `/apps/[key]`.
   - `tools-panel.tsx`: iFrame-Filter um `&& e.group !== "micro"` (+ `!== "orchestration"`) ergänzen.
   - Route `app/(cockpit)/apps/[key]/page.tsx`: lädt Engine per `key`, rendert die vollhöhen-`EmbeddedAppView`.
4. **QA:** Micro-Apps-Sektion erscheint unter Orchestration; Excalidraw lädt im Vollbild unter `/apps/whiteboard`; Excalidraw **nicht mehr** im Werkzeuge-Tab, Tab sonst intakt; Toggle/Sort via Konfig-Panel; Direkt-URL bei ausgeblendeter Sektion; „In neuem Tab"-Fallback vorhanden.

**Zuständigkeit:** Registry/Schema → Backend Developer (klein) · Sektion + Route + Filter → Frontend Developer · Prüfung → QA Engineer. **Keine** Infra/Deploy-Sonderarbeit (anders als PROJ-39).

### H) Referenz-Dateien (Ist-Stand, CodeGraph-verifiziert)
- Sidebar-Registry: `nextjs_app/lib/sidebar-config.ts` (`SIDEBAR_SECTIONS`, `SIDEBAR_ITEMS`)
- Konfig-Panel/Prefs: `nextjs_app/components/cockpit/sidebar-config-panel.tsx`, `…/sidebar-prefs-provider.tsx` (localStorage `jupiter.sidebar.v1`), `…/session-rail.tsx`
- Registry/iFrame: `backend/config/engines.yaml` (Eintrag `whiteboard`), `nextjs_app/components/cockpit/tools-panel.tsx` (Filter `kind === "iframe"`), `…/embed-tab.tsx` (Sandbox + Fallback)
- Schema/Typ: `backend/app/schemas/engines.py` (`EngineRead`), `nextjs_app/lib/types.ts`

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
