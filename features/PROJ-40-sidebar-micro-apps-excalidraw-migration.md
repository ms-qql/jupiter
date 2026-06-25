# PROJ-40: Sidebar-Sektion „Micro-Apps" + Excalidraw-Migration aus „Werkzeuge"

## Status: Approved
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
„Micro-Apps" ist eine **Sammel-Sektion für kleine Einzel-Tools**. Anders als die Orchestration-Sektion (PROJ-39, ausschließlich iFrames fremder Apps) hat eine Micro-App **zwei mögliche Naturen**:
1. **Eingebettet (`kind: iframe`)** — eine externe App im iFrame, z. B. Excalidraw (`https://excalidraw.com`). Nutzt exakt die PROJ-39-/PROJ-18-Mechanik (Registry-Eintrag + `embed-tab.tsx` + Fallback).
2. **Nativ (`kind: native`)** — eine **direkt in Jupiter programmierte** App (Next.js/React-Komponente im Repo), die **ohne iFrame** im Hauptbereich gerendert wird. Beispiel-Kandidaten: Rechner, Notiz-Snippet, kleines internes Werkzeug. **Heute noch keine native App vorhanden** — das Modell wird aber von Anfang an mitgedacht, damit native Micro-Apps später ohne Architektur-Umbau dazukommen.

Wiederverwendet werden trotzdem dieselben Bausteine wie bei PROJ-39:
1. **zentrale Registry** `engines.yaml`, erweitert um das (mit PROJ-39 gemeinsame) `group`-Feld — listet alle Micro-Apps als Metadaten,
2. **Sidebar-Sektions-Gerüst** PROJ-38 (`sidebar-config.ts` + Konfig-Panel für Sichtbarkeit/Reihenfolge/RESET) — identisch für beide Naturen,
3. für eingebettete Apps zusätzlich die **iFrame-Einbettung** (`embed-tab.tsx` + „In neuem Tab öffnen"-Fallback).

**Entscheidender Unterschied zu PROJ-39:** Die erste Micro-App, **Excalidraw**, ist eingebettet, liegt bereits unter `https` und **erlaubt das Framing** → **keine Caddy-/DNS-/Infra-Arbeit nötig.** Reine **Frontend + Config**-Änderung. Neuer Bau: die Vollbild-Route + die zweite Sidebar-Sektion + die **native Render-Verzweigung** (siehe D).

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
└── MicroAppView  (verzweigt nach kind)
    ├── kind == "iframe":
    │   ├── Kopfzeile: App-Label + „In neuem Tab öffnen" (immer sichtbar)
    │   ├── iframe (Vollhöhe, Sandbox aus Registry)   ← wiederverwendete embed-Logik
    │   └── Fallback-/Hinweis-Fläche (verweigert / offline → Retry/Neuer Tab)
    └── kind == "native":
        └── <NativeMicroApp/>  ← React-Komponente aus Frontend-Komponenten-Registry
            (kein iFrame, kein Fallback-Button, lädt Jupiter-intern)
```
> **Routen-Angleichung mit PROJ-39:** PROJ-39 nutzt `/orchestration/[key]`. PROJ-40 nutzt analog `/apps/[key]` (Spec-Vorgabe). Beide rendern dieselbe vollhöhen-`EmbedTab`-Variante — die Route ist nur ein dünner Wrapper, der den Registry-Eintrag per `key` lädt und einbettet. Empfehlung: die in PROJ-39 entstehende Vollbild-View als gemeinsame Komponente (`<EmbeddedAppView engine={…} />`) nutzen, damit `/apps/[key]` und `/orchestration/[key]` sich denselben Renderer teilen (kein Duplikat).

### B) Datenmodell (Klartext — kein DB-Schema)
Kein Backend-DB-Schema. Jede Micro-App ist ein **Metadaten-Eintrag** in `backend/config/engines.yaml` (Label, Icon, Sichtbarkeit, Platzierung) — egal ob eingebettet oder nativ. Der **Code** einer nativen App liegt im Repo, **nicht** in der YAML (siehe D).

**Eingebettet** — der **bestehende `whiteboard`-Eintrag** erhält **nur ein neues Feld**:
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

**Nativ** — künftige in Jupiter programmierte App, Beispiel-Form:
```
rechner (Beispiel, noch nicht gebaut):
- key      "rechner"             → Routen-Parameter /apps/rechner
- label    "Rechner"
- kind     "native"   ◄── NEU: kein iFrame; Render über Frontend-Komponenten-Registry
- group    "micro"
- icon     lucide-Name (optional)
- (kein url, kein sandbox — der Code lebt im Repo, verknüpft per key)
```
Registry wird weiterhin live (mtime-geprüft) geladen — weitere Micro-Apps kommen als reine Metadaten-Zeile dazu (Akzeptanzkriterium „zentral konfiguriert, kein Wildwuchs").

> **`group`-Wert mit PROJ-39 abstimmen:** Beide Features führen dasselbe Feld ein. Verbindlich: `group: "orchestration" | "micro" | null` (`null`/fehlt = klassisches Werkzeug). `kind` wird um `"native"` erweitert (bisher `engine | iframe | launch`). Wer zuerst implementiert, legt `group` an; PROJ-40 ergänzt `kind: native`. Genau **eine** Quelle/`group` entscheidet die Platzierung → keine Doppelregistrierung (Edge Case).

### C) API-Shape (kein neuer Endpunkt)
- `GET /engines` (bestehend) liefert künftig `group` + `icon` je Eintrag (dieselbe Schema-Erweiterung wie PROJ-39 — **nur einmal** nötig: `backend/app/schemas/engines.py` `EngineRead`, Frontend-Typ `nextjs_app/lib/types.ts`).
- **Keine** weitere Backend-API. Das Frontend filtert clientseitig:
  - **Micro-Apps-Sektion:** `group === "micro"`.
  - **Werkzeuge-Tab (`tools-panel.tsx`):** bisheriger iFrame-Filter **plus** `group !== "micro"` (und `!== "orchestration"`) → Excalidraw verschwindet aus „Werkzeuge". Genau hier liegt die „Migration".

### D) Native Micro-Apps — Render-Verzweigung & Komponenten-Registry
Eine native App ist **Code im Repo**, nicht aus YAML ladbar. Darum gibt es zwei Quellen, die das Frontend zu **einer** Micro-App-Liste zusammenführt:
- **Metadaten** (Label, Icon, `group`, `kind`, Reihenfolge) kommen aus `engines.yaml` über `GET /engines` — einheitlich für `iframe` **und** `native`.
- **Der Code** einer nativen App liegt unter `nextjs_app/components/microapps/<key>/` und wird in einer **Frontend-Komponenten-Registry** registriert: `nextjs_app/lib/microapps-registry.ts` als Map `key → React.LazyExoticComponent` (Lazy-Import → kein Bundle-Aufblähen, App lädt erst beim Öffnen).

**Render-Verzweigung in `/apps/[key]`:** Die Route holt den Registry-Eintrag per `key` und schaltet auf `kind`:
- `kind === "iframe"` → vollhöhen-`EmbeddedAppView` (Sandbox + Fallback, wie PROJ-39).
- `kind === "native"` → schlägt `key` in `microapps-registry.ts` nach und rendert die Lazy-Komponente vollflächig (in `<Suspense>` mit Lade-/Fehlerzustand). Fehlt der `key` in der Registry → sauberer „App nicht verfügbar"-Hinweis, kein Crash.

So bleibt die **Sidebar-Sektion + das Konfig-Panel (PROJ-38) identisch** für beide Naturen — sie sehen nur Metadaten; erst die Route entscheidet iFrame vs. native.

### E) „Werkzeuge"-Tab nach Migration (Edge Case entschieden)
Der Werkzeuge-Tab zeigt heute Effizienz-Tools, Launches **und** iFrames. Nach Herausfiltern von Excalidraw bleiben die übrigen Engines/Launches/Tools erhalten → **Tab bleibt funktionsfähig, nicht leer**. Entscheidung: **Tab NICHT ausblenden**; falls die iFrame-Untersektion dadurch leer wird, deren Überschrift einfach weglassen (bestehendes Render-Muster: leere Filter-Arrays erzeugen keine Sektion). Kein Sonder-Leerzustand nötig, solange andere Tools existieren.

### F) Tech-Entscheidungen (WARUM)
- **Micro-App = `iframe` ODER `native`:** Micro-Apps sind nicht auf Einbettung beschränkt — kleine, direkt in Jupiter programmierte Tools sind ausdrücklich vorgesehen. Eine native App rendert ohne iFrame (kein Sandbox-Overhead, voller App-Kontext, kein Mixed-Content/Framing-Thema).
- **Metadaten in YAML, Code im Repo, verknüpft per `key`:** YAML kann keinen Code tragen. Die Frontend-Komponenten-Registry (`microapps-registry.ts`, Lazy-Import) hält den Code; `engines.yaml` nur Label/Icon/Reihenfolge. So bleibt die zentrale Konfig + das Konfig-Panel für beide Naturen gleich, ohne Code in Daten zu pressen.
- **Gemeinsames `group`-Feld statt zweiter Registry:** ein Mechanismus, zwei Sektionen — Sidebar + Filter werten nur das Feld aus. Mit PROJ-39 abgestimmt.
- **Excalidraw nur „verschieben", nicht neu anlegen:** der Eintrag existiert (`whiteboard`); wir ändern **eine Zeile** (`group: micro`). Verhindert Doppelregistrierung by design.
- **Eigene Vollbild-Route `/apps/[key]` statt Tab:** teilbare URL, saubere History; Sektion bleibt per Direkt-URL erreichbar, auch wenn im Konfig-Panel ausgeblendet (Edge Case „kein verwaister Zustand").
- **iFrame-Logik wiederverwenden:** `embed-tab.tsx` kapselt Sandbox + Fallback schon; die Route nutzt die vollhöhen-Variante aus PROJ-39 statt eigener iframe-Logik.
- **„In neuem Tab öffnen" immer sichtbar:** Garantie gegen die „leere Fläche", falls je eine künftige Micro-App das Framing verweigert (`onError` feuert bei `X-Frame-Options` unzuverlässig). Bei Excalidraw selbst nicht relevant, aber Teil des wiederverwendeten Bausteins.
- **Keine Infra:** Excalidraw ist https + framing-offen → der Caddy-/DNS-Block aus PROJ-39 entfällt hier vollständig. (Eine künftige native App ist ohnehin Jupiter-intern und braucht keine Infra.)

### G) Abhängigkeiten (Pakete)
- **Keine neuen Pakete.** Icon aus bestehendem `lucide-react` (z. B. `PenTool`/`Pencil`). Sidebar-Sektion + Konfig-Panel liefert PROJ-38; Vollbild-View + `group`-Feld liefert/teilt PROJ-39.

### H) Bau-Reihenfolge / Hand-offs
1. **Voraussetzung:** PROJ-38 (Sektionsgerüst + Konfig-Panel) steht. **Reihenfolge mit PROJ-39 koordinieren:** das `group`+`icon`-Schemafeld und die gemeinsame Vollbild-View nur **einmal** bauen. Idealerweise PROJ-39 zuerst (legt Feld + `<EmbeddedAppView>` an), PROJ-40 hängt sich dran. Falls PROJ-40 zuerst läuft: dann legt PROJ-40 beides an.
2. **Backend (winzig):** `group` + `icon` in `EngineRead`-Schema (falls nicht schon durch PROJ-39); `whiteboard`-Eintrag in `engines.yaml` um `group: micro` (+ optional `icon`) ergänzen.
3. **Frontend:**
   - `EngineRead`-Typ um `group`/`icon` erweitern (falls nicht schon durch PROJ-39).
   - `sidebar-config.ts`: `SIDEBAR_SECTIONS` um `micro` (Label „Micro-Apps", Order **unter** `orchestration`) ergänzen; Sidebar-Eintrag rendert die `getEngines()`-Liste gefiltert auf `group === "micro"` als Links auf `/apps/[key]`.
   - `tools-panel.tsx`: iFrame-Filter um `&& e.group !== "micro"` (+ `!== "orchestration"`) ergänzen.
   - Route `app/(cockpit)/apps/[key]/page.tsx`: lädt Engine per `key`, **verzweigt nach `kind`** — `iframe` → vollhöhen-`EmbeddedAppView`; `native` → Lazy-Komponente aus `microapps-registry.ts` in `<Suspense>`.
   - `nextjs_app/lib/microapps-registry.ts` anlegen (Map `key → lazy component`) — vorerst leer/nur Gerüst, da noch keine native App existiert; Ordner-Konvention `components/microapps/<key>/` dokumentieren.
4. **QA:** Micro-Apps-Sektion erscheint unter Orchestration; Excalidraw (iframe) lädt im Vollbild unter `/apps/whiteboard`; Excalidraw **nicht mehr** im Werkzeuge-Tab, Tab sonst intakt; Toggle/Sort via Konfig-Panel; Direkt-URL bei ausgeblendeter Sektion; „In neuem Tab"-Fallback vorhanden; **`kind: native`-Pfad** mit einer Dummy-Komponente verifizierbar (rendert ohne iFrame; unbekannter `key` → sauberer Hinweis).

**Zuständigkeit:** Registry/Schema → Backend Developer (klein) · Sektion + Route + Filter → Frontend Developer · Prüfung → QA Engineer. **Keine** Infra/Deploy-Sonderarbeit (anders als PROJ-39).

### I) Referenz-Dateien (Ist-Stand, CodeGraph-verifiziert)
- Sidebar-Registry: `nextjs_app/lib/sidebar-config.ts` (`SIDEBAR_SECTIONS`, `SIDEBAR_ITEMS`)
- Konfig-Panel/Prefs: `nextjs_app/components/cockpit/sidebar-config-panel.tsx`, `…/sidebar-prefs-provider.tsx` (localStorage `jupiter.sidebar.v1`), `…/session-rail.tsx`
- Registry/iFrame: `backend/config/engines.yaml` (Eintrag `whiteboard`), `nextjs_app/components/cockpit/tools-panel.tsx` (Filter `kind === "iframe"`), `…/embed-tab.tsx` (Sandbox + Fallback)
- Schema/Typ: `backend/app/schemas/engines.py` (`EngineRead`), `nextjs_app/lib/types.ts`
- **NEU (native):** `nextjs_app/lib/microapps-registry.ts` (key → lazy component), `nextjs_app/components/microapps/<key>/` (App-Code), Route `nextjs_app/app/(cockpit)/apps/[key]/page.tsx` (kind-Verzweigung)

## Implementation Notes (Frontend, 2026-06-25)
Umgesetzt auf Branch `dev` (Next.js, kein Flutter). Spiegelt das bereits gebaute
PROJ-39-Muster für `group: micro` und ergänzt den `native`-Pfad.

**Stack-Realität:** Die PROJ-39-Foundation existierte schon im Code (group/icon in
`EngineRead`, dynamische Sidebar-Items, `embed-tab` mit `fullHeight`, Route
`/orchestration/[key]`). PROJ-40 hängt sich daran an — kein Schema-/EmbedTab-Neubau.

**Geänderte/neue Dateien:**
- `backend/config/engines.yaml`: `whiteboard` → `group: micro` + `icon: pentool`
  (= die Migration; verschiebt Excalidraw aus „Werkzeuge" in die Micro-Apps-Sektion).
- `backend/app/engine/registry.py`: neues `kind: native` (in `VALID_KINDS`, eigener
  Parse-Zweig ohne url/target-Pflicht, `availability → (True, None)`).
  `EngineRead`-Schema hatte `group`/`icon` bereits (PROJ-39) — keine Schema-Änderung.
- `lib/types.ts`: `EngineKind` um `"native"` erweitert.
- `lib/sidebar-config.ts`: Sektion `micro` („Micro-Apps", unter „Orchestration") +
  `microAppItemKey`/`microAppItemDef` (href `/apps/[key]`), `pentool`-Icon ergänzt.
- `lib/microapps-registry.ts` **(neu)**: Frontend-Komponenten-Registry `key → lazy
  component` für native Apps; vorerst leer (Excalidraw ist iframe). `resolveMicroApp`.
- `components/cockpit/use-microapps.tsx` **(neu)**: lädt `group=micro` (kind iframe
  **und** native) aus GET /engines, meldet sie als dynamische Sidebar-Items an.
- `components/cockpit/sidebar-prefs-provider.tsx`: `registerDynamicItems` ist jetzt
  **namespaced** (`(namespace, items)`), dynamische Items pro Namespace gespeichert —
  sonst hätten sich Orchestration und Micro gegenseitig überschrieben.
  Caller `use-orchestration-apps.tsx` mitangepasst.
- `components/cockpit/session-rail.tsx`: `useMicroApps()` gemountet + Micro-Apps-
  Sektion unter Orchestration gerendert.
- `components/cockpit/tools-panel.tsx`: iFrame-Filter um `&& e.group !== "micro"` →
  Excalidraw erscheint nicht mehr im Werkzeuge-Tab (Orchestration bleibt dort, wie
  in PROJ-39 entschieden).
- `app/(cockpit)/apps/[key]/page.tsx` **(neu)**: Vollbild-Route, verzweigt nach
  `kind` — iframe ⇒ `EmbedTab fullHeight` (+ Mixed-Content-Guard); native ⇒
  `NativeMicroAppHost` (Modul-Scope-Komponente, `resolveMicroApp` + `<Suspense>`,
  unbekannter key → sauberer Hinweis). Lint-konform (abgeleiteter Loading-State,
  `createElement` statt JSX für die call-abgeleitete native Komponente).

**Verifikation:** `tsc --noEmit` sauber (nur vorbestehender md-tree.test-Fehler),
ESLint 0 Errors, Vitest 23/23 grün (sidebar-prefs/-config, tools-panel, embed-tab),
Backend `pytest -k "registr or engine"` 29/29 grün. Smoke: `whiteboard` lädt als
`iframe/micro/pentool/available`; `kind: native` parst (session=False, available).

**Offen für QA:** Klick-Flow im Browser (Sektion erscheint, /apps/whiteboard lädt
Excalidraw vollbild, Werkzeuge-Tab ohne Excalidraw intakt), Konfig-Panel-Toggle/Sort,
Direkt-URL bei ausgeblendeter Sektion, native-Pfad mit Dummy-Komponente.

## QA Test Results
**Getestet:** 2026-06-25 · **Branch:** dev · **Verfahren:** automatisierte Tests
(Vitest/pytest) + Production-Build + Code-Verifikation. Kein headless-Browser mit
Login verfügbar → die rein visuellen Klick-Flows sind als „manuell offen" markiert.

### Automatisierte Suiten
- **Frontend (Vitest):** 167/167 grün (19 Dateien), davon **6 neu** in
  `lib/microapps.test.ts` (Micro-Sektion/-Helfer + native Registry).
- **Backend (pytest, Engine-Suiten):** 34/34 grün, davon **7 neu** in
  `backend/tests/test_proj40_microapps.py` (kind=native, group/icon, native-Session-
  Reject, Migrations-Guard via engines.example.yaml).
- **`next build`:** erfolgreich; Route `ƒ /apps/[key]` registriert (kompiliert prod-seitig).
- **tsc/ESLint:** sauber (0 Errors).

### Akzeptanzkriterien
| # | Kriterium | Status | Beleg |
|---|-----------|--------|-------|
| 1 | Sektion „Micro-Apps" unter Orchestration | ✅ Pass | `microapps.test`: micro-Sektion existiert, Index > orchestration; `session-rail.tsx` rendert Block darunter |
| 2 | Excalidraw mit Label + Icon | ✅ Pass | engines.yaml `group: micro`/`icon: pentool`; example-Guard-Test; `use-microapps` filtert group=micro |
| 3 | Klick öffnet Vollbild `/apps/[key]` (iFrame) | ✅ Pass* | `microAppItemDef.href=/apps/whiteboard`; Route kompiliert; EmbedTab `fullHeight`. *visueller Klick manuell offen |
| 4 | Excalidraw NICHT mehr im Werkzeuge-Tab, Tab intakt | ✅ Pass | `tools-panel.tsx` Filter `group !== "micro"`; tools-panel-Tests weiter grün; Leerzustand vorhanden |
| 5 | Fallback „In neuem Tab öffnen" bei verweigerter Einbettung | ✅ Pass | EmbedTab zeigt LaunchButton immer; `embed-tab.test` deckt ab |
| 6 | Sektion + Einträge über Konfig-Panel (PROJ-38) toggel-/sortierbar | ✅ Pass* | dynamische Items via namespaced `registerDynamicItems("micro", …)`; Panel iteriert `SIDEBAR_SECTIONS` (inkl. micro). *Panel-Interaktion manuell offen |
| 7 | Micro-Apps zentral konfiguriert (Registry-Gruppe) | ✅ Pass | `group: micro` in Registry (Backend akzeptiert; example.yaml). **Abweichung:** Wert ist `micro` (nicht `microapp` wie im AC-Text illustriert) — bewusst, analog `orchestration`. |
| 8 | Texte/Labels deutsch | ✅ Pass | Sektionslabel „Micro-Apps", alle Hinweise/Fehlertexte deutsch |

### Edge Cases
| Fall | Status | Beleg |
|------|--------|-------|
| Werkzeuge-Tab nach Migration leer? | ✅ | übrige Engines/Launches bleiben; tools-panel hat Leer-/Hinweiszustand; Tab nicht ausgeblendet |
| App verweigert Einbettung (CSP/XFO) | ✅ | EmbedTab-Fallback (immer sichtbarer Launch-Button) |
| App nicht erreichbar | ✅ | Route: `error`/`notfound`-Zustand; iFrame-`onError` → Fallback; kein Crash |
| Doppelregistrierung | ✅ | genau ein `group`-Wert entscheidet; tools-panel filtert micro heraus → keine Doppelanzeige |
| Sektion ausgeblendet → Direkt-URL | ✅ | Route lädt unabhängig von der Sidebar-Sichtbarkeit (Lookup per key aus GET /engines) |
| Mobile: Drawer schließt nach Auswahl | ✅ | `onItemClick` an die Micro-Links durchgereicht (wie Orchestration) |
| **native-Pfad** (kind=native) | ✅ | Backend parst native ohne url; Route verzweigt auf Komponenten-Registry; unbekannter key → sauberer Hinweis (`resolveMicroApp`→null getestet) |

### Security-Audit (Red-Team)
- Kein Auth/RLS im MVP (Projekt-Entscheidung) — Feature fügt **keine** neuen Endpunkte hinzu; nutzt das bestehende, secret-freie `GET /engines`.
- **iFrame-Sandbox:** Excalidraw mit `allow-scripts allow-same-origin allow-forms allow-popups allow-downloads`. `same-origin` gilt der **eingebetteten** Origin (excalidraw.com), nicht Jupiter — kein Zugriff auf Jupiters Origin. Vertretbar für ein vertrauenswürdiges Tool.
- **Injection:** `key` wird gegen die Registry gematcht (kein SQL, keine Eval); Labels werden als Text gerendert (JSX-Autoescape) → kein XSS-Vektor.
- **Mixed-Content-Guard** für künftige http-Micro-Apps vorhanden.
- Keine Secrets in Responses/Build. **Keine Findings.**

### Regression
- Werkzeuge-Tab, Sidebar (PROJ-38), Orchestration (PROJ-39): alle Tests grün; `registerDynamicItems` auf Namespace umgestellt + PROJ-39-Caller mitangepasst → Orchestration koexistiert mit Micro (Pure-Logic-Parität; volle Provider-Koexistenz mangels jsdom manuell verifiziert).

### Bugs
Keine Critical/High/Medium. **Low/Notiz (kein Blocker):**
- **L1 (Doku):** AC-Text nennt `group: microapp`, Implementierung nutzt `group: micro` — bewusste, dokumentierte Angleichung an `orchestration`. Keine Code-Änderung nötig.
- **Deploy-Hinweis (kein Bug):** `engines.yaml` ist gitignored → die `group: micro`-Migration muss `/abc-deploy` auf dem Host setzen (Vorlage: getracktes `engines.example.yaml`). Auf dem Dev-Host bereits gesetzt.

### Offen (manuell, nicht-blockierend)
Visueller Klick-Flow im eingeloggten Browser: Sektion sichtbar · `/apps/whiteboard` lädt Excalidraw vollbild · Konfig-Panel Toggle/Sort · Mobile-Drawer. Empfohlen als Smoke vor/nach Deploy.

### Production-Ready-Entscheidung: **READY** ✅
Keine Critical/High-Bugs. Alle automatisierbaren ACs bestanden; rein visuelle Punkte als Deploy-Smoke notiert.

## Deployment
_To be added by /deploy_
