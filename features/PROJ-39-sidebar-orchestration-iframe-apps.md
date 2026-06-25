# PROJ-39: Sidebar-Sektion „Orchestration" — Fremd-Apps per iFrame (Paperclip, Wayland)

## Status: Deployed
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
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (App Router) Frontend + FastAPI/`engines.yaml`-Registry + Caddy-Reverse-Proxy (Infra) · **Branch:** dev

### Überblick / Grundhaltung
„Orchestration" ist **kein neuer Mechanismus**, sondern die Komposition aus drei bereits existierenden Bausteinen:
1. die **iFrame-Einbettung** aus PROJ-18 (`embed-tab.tsx` — iframe + Sandbox + „In neuem Tab öffnen"-Fallback),
2. die **zentrale Registry** `engines.yaml` (PROJ-18), erweitert um ein Gruppen-Feld,
3. das **Sidebar-Sektions-Gerüst** aus PROJ-38 (benannte, konfigurierbare Sektionen mit Sichtbarkeit/Reihenfolge/RESET).

Der einzige echte Neubau ist eine **Vollbild-Route** im Hauptbereich und die **Caddy-Infra**, die die http-only-Apps unter `https` verfügbar macht (sonst greift Mixed-Content und nichts lädt).

### A) Komponenten-Struktur (UI-Baum)
```
SessionRail (session-rail.tsx, PROJ-38-Sektionsgerüst)
├── Workspace-Sektion (Doku · Dateien)          ← PROJ-38
├── Aktive Sessions                              ← PROJ-3 (bestehend)
└── Orchestration  ◄── NEU (Sektion unter „Aktive Sessions")
    ├── Paperclip   (Label + Icon → Link /orchestration/paperclip)
    └── Wayland     (Label + Icon → Link /orchestration/wayland)
        └── (Einträge aus Registry gefiltert auf group=orchestration;
             Sichtbarkeit/Reihenfolge über PROJ-38-Konfig-Panel)

Hauptbereich-Route  /orchestration/[key]   ◄── NEU (Vollbild)
└── OrchestrationView
    ├── Kopfzeile: App-Label + „In neuem Tab öffnen"
    ├── iframe (Vollhöhe, Sandbox aus Registry)   ← wiederverwendete embed-Logik
    └── Fallback-/Hinweis-Fläche
        ├── Einbettung verweigert (X-Frame-Options/CSP) → Fallback-Button
        ├── Mixed-Content/http-App → „über Reverse-Proxy bereitstellen"-Hinweis
        └── App offline / Tailscale getrennt → Offline-Hinweis + Retry/Neuer Tab
```

### B) Datenmodell (Klartext — kein neues DB-Schema)
Kein Backend-DB-Schema. Eine Orchestration-App ist ein **Registry-Eintrag** in `backend/config/engines.yaml`, identisch zum bestehenden `whiteboard`-iFrame, plus zwei neue Felder:
```
Jeder Orchestration-Eintrag hat:
- key      eindeutig (z. B. „paperclip", „wayland")  → Routen-Parameter
- label    Anzeigename (App-Eigenname bleibt)
- kind     "iframe"
- group    "orchestration"   ◄── NEU: trennt Orchestration (PROJ-39) von Micro-Apps (PROJ-40)
- icon     lucide-Icon-Name   ◄── NEU (optional): Sidebar-Icon, sonst Default
- url      https-Adresse (über Caddy-Proxy, NICHT die http-Tailscale-IP)
- sandbox  pro App konfigurierbare iframe-Sandbox-Attribute
```
Die Registry wird weiterhin live (mtime-geprüft) geladen — neue Apps ohne Backend-Neustart, ohne Code.

### C) API-Shape (Endpunkte — kein neuer Endpunkt)
- `GET /engines` (bestehend) liefert künftig auch `group` + `icon` je Eintrag.
  → Schema `backend/app/schemas/engines.py` (`EngineRead`) und Frontend-Typ `nextjs_app/lib/types.ts` (`EngineRead`) um `group` und `icon` ergänzen.
- **Keine** weitere Backend-Anwendungs-API. Das Frontend filtert die Engine-Liste clientseitig auf `group === "orchestration"` für die Sidebar-Sektion.

### D) Infra — Caddy-Reverse-Proxy (PFLICHT, sonst lädt nichts)
**Verifizierter Ist-Zustand (2026-06-25 auf dem VPS geprüft):**
- **Jupiter:** `https://jupiter.auxevo.tech` (Caddy, Auto-TLS, öffentliche IP `187.124.182.215`). Dahinter Next.js `127.0.0.1:3001`, FastAPI `127.0.0.1:8000`. Caddy schützt **alles** per `forward_auth` (Cookie-Login, Port `9100`).
- **Wayland:** systemd-User-Service, lauscht `0.0.0.0:3000`. Sendet **`X-Frame-Options: DENY`** + CSP `default-src 'self'` (ohne `frame-ancestors`). Hat **eigenen** Admin-Login.
- **Paperclip:** systemd-User-Service, lauscht **nur** auf Tailscale-IP `100.80.219.113:3100`. **Keine** Framing-Sperre, **kein** eigener Login.

**Zwei Blocker, beide infra-seitig zu lösen:**
1. **Mixed-Content:** `http://IP:port`-iFrame lädt in der `https`-Seite gar nicht (greift vor jedem JS-`onError`). → Beide Apps müssen über `https` ausgeliefert werden.
2. **Framing-Sperre (nur Wayland):** `X-Frame-Options: DENY` verbietet Einbettung selbst über https. → Header an der Proxy-Kante gezielt überschreiben. Paperclip ist framing-offen.

**Lösung — je App eine eigene Subdomain hinter Caddy mit TLS:**
```
# Paperclip — HINTER Jupiters Login (Nutzerwunsch 2026-06-25):
paperclip.auxevo.tech {
    forward_auth 127.0.0.1:9100 { ... }      # derselbe Cookie-Login-Block wie jupiter.auxevo.tech
    reverse_proxy 100.80.219.113:3100         # Paperclip hat keinen eigenen Login → Schutz durch forward_auth
}

# Wayland — eigener Login, Framing-Sperre gezielt für Jupiter aufheben:
wayland.auxevo.tech {
    reverse_proxy 127.0.0.1:3000 {
        header_down -X-Frame-Options
        header_down +Content-Security-Policy "frame-ancestors https://jupiter.auxevo.tech"
    }
}
```
- **DNS:** zwei A-Records (`paperclip`, `wayland`) → `187.124.182.215` (manuell beim DNS-Provider; **ohne** sie kein Let's-Encrypt-Zertifikat).
- **Registry:** danach `url: https://paperclip.auxevo.tech` bzw. `url: https://wayland.auxevo.tech`.
- **Subdomain statt Subpfad:** beide Apps nutzen absolute Asset-/WS-Pfade ab `/`, die unter einem Unterpfad (`/wayland/`) brechen — eigene Hosts vermeiden das.

Diese Caddy-/DNS-Einträge legt `/abc-deploy` (Infra, host-nativ, kein Dokploy) an; bis dahin greift ausschließlich der „In neuem Tab öffnen"-Fallback. **Aufwand gering, keine Code-Änderung an Jupiter:** Caddyfile (2 Blöcke) + `caddy reload` + 2 DNS-Records + 2 `engines.yaml`-Einträge.

**Sicherheits-Entscheidungen (dokumentiert):**
- **Paperclip hinter Jupiters `forward_auth` (Port 9100):** Paperclip bringt keinen eigenen Login mit; über eine öffentliche Subdomain wäre es sonst ungeschützt erreichbar. Der `forward_auth`-Block schließt diese Lücke — Paperclip ist nur nach Jupiter-Login nutzbar, im iFrame trägt der Browser denselben Cookie automatisch mit (gleiche Eltern-Domain `auxevo.tech`). **Cookie-Domain prüfen:** Login-Cookie muss für `*.auxevo.tech` gültig sein (nicht host-only auf `jupiter.`), sonst greift `forward_auth` auf der Subdomain nicht.
- **Wayland-Clickjacking:** `X-Frame-Options: DENY` ist von Wayland bewusst gesetzt; das Aufheben (Framing **nur** für `jupiter.auxevo.tech` via `frame-ancestors`) ist eine bewusste, eng begrenzte Abschwächung — für Single-User-Self-Host vertretbar. Wayland behält seinen eigenen Login.

### E) Tech-Entscheidungen (WARUM)
- **Registry statt Hardcoding:** Apps liegen als Datenzeilen in `engines.yaml` — weitere Orchestration-Apps kommen ohne Code-Änderung dazu (Akzeptanzkriterium „zentral konfiguriert, kein Wildwuchs").
- **`group`-Feld statt getrennter Registry:** ein gemeinsamer Mechanismus für PROJ-39 (`orchestration`) und PROJ-40 (`micro`); Sidebar/Filter werten nur das Feld aus. Mit PROJ-40 abgestimmt.
- **Eigene Vollbild-Route `/orchestration/[key]` statt Tab:** teilbare URL, saubere Browser-History, kein Tab-Wechsel beim Laden; die Sektion bleibt per Direkt-URL erreichbar, auch wenn im Konfig-Panel ausgeblendet (Edge Case).
- **iFrame-Logik wiederverwenden statt neu bauen:** `embed-tab.tsx` kapselt Sandbox + Fallback bereits. Für die Route genügt eine **vollhöhen-Variante** (Höhe `h-[60vh]` → Vollfläche). Empfehlung: `embed-tab.tsx` um einen Höhen-/Vollbild-Schalter erweitern und in der Route wiederverwenden, statt die iframe-Logik zu duplizieren.
- **Caddy-Proxy statt iFrame-Tricks:** Mixed-Content lässt sich clientseitig nicht umgehen; die einzige robuste Lösung ist https-Auslieferung an der Quelle.
- **Bekannte Grenze des `onError`-Fallbacks:** Bei `X-Frame-Options: DENY` feuert `iframe.onError` in vielen Browsern **nicht** zuverlässig. Deshalb ist der **„In neuem Tab öffnen"-Button immer sichtbar** (nicht nur im Fehlerfall) — das ist die eigentliche Garantie gegen die „leere Fläche", der `onError`-Pfad ist nur die Kür.

### F) Abhängigkeiten (Pakete)
- **Keine neuen Pakete.** Icons aus bestehendem `lucide-react` (z. B. `PaperclipIcon`; für Wayland z. B. `Waves`/`Radio`). Sidebar-Sektion + Konfig-Panel liefert PROJ-38.
- Infra: vorhandener Caddy (host-nativ auf Dev-VPS, siehe Deployment-Memory) — nur zwei neue Site-Blöcke + DNS-A-Records für die Subdomains.

### G) Bau-Reihenfolge / Hand-offs
1. **Voraussetzung:** PROJ-38 (Sektionsgerüst + Konfig-Panel) muss zuerst stehen — PROJ-39 registriert nur seine Einträge dort. *(PROJ-38 ist inzwischen „In Progress".)*
2. **Infra zuerst (`/abc-deploy`):** 2 DNS-A-Records (`paperclip`, `wayland` → `187.124.182.215`); Caddyfile um beide Blöcke ergänzen — **Paperclip mit `forward_auth 127.0.0.1:9100`** (hinter Jupiter-Login), **Wayland mit `header_down`-Overrides**; `caddy reload`. Erst danach ist die Einbettung real testbar.
3. **Backend (klein):** `group` + `icon` in `EngineRead`-Schema; Paperclip/Wayland als `kind: iframe` in `engines.yaml` mit `url: https://…auxevo.tech` + Sandbox `allow-scripts allow-same-origin allow-forms allow-popups allow-downloads`.
4. **Frontend:** `EngineRead`-Typ erweitern, Orchestration-Sektion in `session-rail.tsx` (group-Filter), Route `app/(cockpit)/orchestration/[key]/page.tsx` mit vollhöhen-`EmbedTab`.
5. **QA:** Einbettung lädt (nach Proxy), Wayland-Framing nach Header-Override, **Paperclip nur nach Jupiter-Login erreichbar** (Cookie auf `*.auxevo.tech` gültig → im iFrame mitgesendet, da gleiche Registrable-Domain → SameSite=Lax greift), Offline-Hinweis bei Port-down/Tailscale getrennt, Toggle/Sort via Konfig-Panel, Direkt-URL bei ausgeblendeter Sektion.

**Zuständigkeit:** Infra/Caddy/DNS → `/abc-deploy` · Registry/Schema → Backend Developer · Sektion + Route → Frontend Developer · Prüfung → QA Engineer.

### H) Generalisierung (Folge-Kandidat, nicht in PROJ-39)
Das Muster „eingebettete self-hosted App" = **Caddy-Subdomain + optionale `header_down`-Overrides + optional `forward_auth` + `engines.yaml`-Eintrag (`kind: iframe`, `group`)** wird hier zum zweiten Mal angewandt (nach Excalidraw). Lohnt sich als wiederverwendbarer Architektur-Baustein für künftige Tools — als eigenes Folge-Ticket festhalten, sobald eine dritte App ansteht (YAGNI bis dahin).

## Implementierungs-Notizen (Frontend + Registry) — 2026-06-25

**Umgesetzt (Code, Branch `dev`):**
- **Registry/Schema (Backend, klein):**
  - `EngineProfile` (`backend/app/engine/registry.py`) um `group` + `icon` erweitert; `_coerce_profile` parst beide kind-unabhängig, `to_read()` gibt sie aus.
  - `EngineRead` (`backend/app/schemas/engines.py`) um `group` + `icon` ergänzt.
  - `backend/config/engines.yaml`: Einträge **paperclip** (`icon: paperclip`) und **wayland** (`icon: waves`) als `kind: iframe`, `group: orchestration`, `url: https://…auxevo.tech` (Caddy-Proxy-Zieladressen), Sandbox `allow-scripts allow-same-origin allow-forms allow-popups allow-downloads`.
- **Frontend:**
  - `lib/types.ts` `EngineRead` um `group`/`icon` erweitert.
  - `lib/sidebar-config.ts`: neue Sektion **„Orchestration"** (unter „Aktive Sessions"); Icon-Auflösung (`resolveOrchestrationIcon`) + `orchestrationItemDef()`/`orchestrationItemKey()` (Namensraum `orch:`). *(Hinweis: dieselbe Datei trägt jetzt auch PROJ-40-Micro-Apps — koexistiert konfliktfrei.)*
  - `sidebar-prefs-provider.tsx`: PROJ-38-Prefs um **dynamische, registry-getriebene Einträge** erweitert — `registerDynamicItems(namespace, items)`; pure Helfer abwärtskompatibel um optionalen `defs`-Parameter ergänzt (bestehende PROJ-38-Tests unverändert grün). Persistierte Sichtbarkeit/Reihenfolge wird aus dem Roh-Storage nach-gemerged, sobald die dynamischen Einträge bekannt sind.
  - `use-orchestration-apps.tsx`: lädt `GET /engines`, filtert `kind=iframe & group=orchestration`, meldet sie als dynamische Items an (Namespace `orchestration`).
  - `session-rail.tsx`: rendert die Orchestration-Sektion (Klick → Route); Hook unbedingt eingebunden, damit die Einträge auch bei ausgeblendeter Sektion im Konfig-Panel wieder einblendbar bleiben.
  - `embed-tab.tsx`: `fullHeight`-Variante (Vollfläche statt 60vh) — wiederverwendet in der Route; „In neuem Tab öffnen" bleibt **immer** sichtbar.
  - Route `app/(cockpit)/orchestration/[key]/page.tsx`: Vollbild-Ansicht; lädt den Eintrag, behandelt **Lädt / unbekannte App / Registry-Fehler / Mixed-Content (http)** explizit (kein stiller Leer-Frame); direkt per URL erreichbar, unabhängig von der Sektions-Sichtbarkeit.

**Tests:** Frontend `vitest run` 152 grün (inkl. PROJ-38-Prefs + EmbedTab); Backend `test_proj18_engines.py` 27 grün; `eslint`/`tsc` für PROJ-39-Dateien sauber.

**OFFEN (nicht im Frontend-Scope, blockiert die reale Einbettung) → `/abc-deploy`:**
- **Caddy-Reverse-Proxy + DNS** für `paperclip.auxevo.tech` (mit `forward_auth 127.0.0.1:9100`, da Paperclip keinen eigenen Login hat) und `wayland.auxevo.tech` (mit `header_down -X-Frame-Options` + `+Content-Security-Policy "frame-ancestors https://jupiter.auxevo.tech"`), 2 A-Records → `187.124.182.215`, `caddy reload`.
- **Bis dahin** lädt nur der „In neuem Tab öffnen"-Fallback (die `https://…auxevo.tech`-Hosts existieren noch nicht). Die Registry-URLs sind bereits auf diese Zieladressen gesetzt.
- Cookie-Domain prüfen: Jupiter-Login-Cookie muss für `*.auxevo.tech` gelten (nicht host-only), damit `forward_auth` auf der Paperclip-Subdomain greift.

## QA Test Results — 2026-06-25 (Branch `dev`)

**Testart:** Statisches Code-Review gegen Akzeptanzkriterien + automatisierte Tests (vitest/pytest/eslint/tsc). **Live-Browser-Test** der eingebetteten Apps war NICHT möglich — die https-Zielhosts (`paperclip/wayland.auxevo.tech`) existieren erst nach dem Caddy/DNS-Schritt (`/abc-deploy`). Dynamische UI-Pfade (echtes iFrame-Laden, Mobile-Drawer, Responsive) sind per Code-Review verifiziert, der visuelle Live-Smoke steht nach Deploy aus.

### Automatisierte Tests
- **Frontend `vitest run`: 167 grün** (19 Dateien) — inkl. neuer Suiten:
  - `lib/orchestration-config.test.ts` (Sektion existiert unter „Aktive Sessions", Icon-Auflösung inkl. Fallback/Case, `orchestrationItemDef`/`-Key`-Namensraum).
  - `components/cockpit/embed-tab.test.tsx` erweitert (`fullHeight`-Variante: iFrame `flex-1` statt `h-[60vh]`, Fallback-Button bleibt; Default-60vh unverändert).
  - PROJ-38-Prefs-Suite (23) trotz Signatur-/Defs-Erweiterung unverändert grün → keine Regression.
- **Backend `pytest backend/tests/`: 634 grün** — inkl. neuer `test_proj39_orchestration.py` (4): `group`/`icon` parsen + via `to_read` ausliefern; Default `None` ohne Felder; iFrame immer `available`; echte `engines.yaml` trägt Paperclip+Wayland als `group=orchestration` mit **https**-URLs.
- **eslint:** 0 Errors in PROJ-39-Dateien (1 Warning gehört zu PROJ-40 `microapps-registry.ts`). **tsc:** PROJ-39 sauber.

### Akzeptanzkriterien
| # | Kriterium | Status | Beleg |
|---|-----------|--------|-------|
| 1 | Sektion „Orchestration" unter „Aktive Sessions" | ✅ Pass | `session-rail.tsx` rendert Block nach dem Sessions-Block; `SIDEBAR_SECTIONS`-Index > sessions (Test). |
| 2 | Einträge Paperclip + Wayland mit Label + Icon | ✅ Pass | `engines.yaml` (group=orchestration, icon=paperclip/waves) → `useOrchestrationApps` → `orchestrationItemDef` (Icon-Auflösung getestet). |
| 3 | Klick → Vollbild-Route `/orchestration/[key]` mit iFrame | ✅ Pass | `app/(cockpit)/orchestration/[key]/page.tsx` + `EmbedTab fullHeight`. |
| 4 | Bei Einbettungs-Verweigerung (https) „In neuem Tab öffnen"-Fallback | ✅ Pass | Button in `EmbedTab` **immer** sichtbar (nicht nur im onError-Fall) — getestet. |
| 5 | Sektion + Einträge über Konfig-Panel (PROJ-38) toggel-/sortierbar | ✅ Pass (Code-Review) | Dynamische Items im `SidebarPrefsProvider` (Namespace `orchestration`); Konfig-Panel iteriert `SIDEBAR_SECTIONS` inkl. orchestration. Live-Klicktest nach Deploy empfohlen. |
| 6 | Apps zentral konfiguriert (Registry), kein Code-Wildwuchs | ✅ Pass | Reine `engines.yaml`-Zeilen; weitere Apps ohne Code. |
| 7 | Texte/Labels deutsch (App-Eigennamen bleiben) | ✅ Pass | Sektionslabel + Route-Hinweise deutsch; „Paperclip"/„Wayland" als Eigennamen. |

### Edge Cases
| Edge Case | Status | Anmerkung |
|-----------|--------|-----------|
| Mixed-Content (http-App in https-Jupiter) | ✅ Pass | Route erkennt `http://` → expliziter Hinweis „Einbettung blockiert … über Reverse-Proxy bereitstellen" + Fallback-Button, **kein** Leer-Frame. |
| App nicht erreichbar / Port down | ⚠️ Teilweise (Low #3) | Kein Crash, Fallback-Button bleibt. Aber **kein expliziter Offline-Hinweis + Retry** wie im Edge-Case genannt — nur der generische `EmbedTab`-Hinweis. |
| X-Frame-Options: DENY (Wayland) | ✅ Pass | Immer sichtbarer Fallback-Button ist die Garantie (onError unzuverlässig — bewusst dokumentiert). |
| Tailscale getrennt | ⚠️ Teilweise (Low #3) | Wie „Port down": kein expliziter Retry. |
| Sektion ausgeblendet → Direkt-URL erreichbar | ✅ Pass | Route prüft keine Sichtbarkeit; lädt Engine eigenständig aus `GET /engines`. |
| Mobile: Drawer schließt nach Auswahl | ✅ Pass (Code-Review) | Orchestration-Links rufen `onItemClick` (Drawer-Close), wie Workspace-Items. |

### Security-Audit (Red-Team)
- **iFrame-Sandbox:** `allow-scripts allow-same-origin allow-forms allow-popups allow-downloads` — **kein** `allow-top-navigation`/`allow-top-navigation-by-user-activation` → eine eingebettete App kann das Eltern-Cockpit nicht wegnavigieren. ✅
- **`allow-same-origin` + `allow-scripts`:** unkritisch, da die gerahmten Apps eine **andere Origin** (eigene Subdomain) als Jupiter haben → kein Sandbox-Self-Escape auf Jupiters Origin. ✅
- **XSS:** `label` wird als Text gerendert (React-Escaping); `url` nur in `iframe src`/Anchor `href`. Quelle ist die operator-kontrollierte `engines.yaml` (Vertrauensgrenze = Betreiber), keine Nutzer-Eingabe. `LaunchButton` rendert nur `http(s)`-Ziele als Link (sonst „Befehl kopieren") → kein `javascript:`-Anchor. ✅
- **Secrets:** `to_read()`/`GET /engines` bleibt secret-frei (kein `auth_env`/argv) — durch PROJ-18-Test `test_to_read_is_secret_free` weiter abgedeckt. ✅
- **Architektur-Hinweis (an `/abc-deploy`, nicht Code):** Paperclip hat **keinen** eigenen Login → MUSS hinter `forward_auth 127.0.0.1:9100`; Login-Cookie muss für `*.auxevo.tech` gelten (sonst greift forward_auth auf der Subdomain nicht). Wayland-XFO-Override eng auf `frame-ancestors https://jupiter.auxevo.tech` begrenzen. **Ohne diese Schritte ist Paperclip über die öffentliche Subdomain ungeschützt** → vor Deploy zwingend prüfen.
- Auth/RLS/Tenant/SQL-Injection: **n/a** — rein clientseitiges Feature + read-only Registry, keine DB/kein Mandantenpfad.

### Gefundene Bugs
| # | Sev | Beschreibung | Status |
|---|-----|--------------|--------|
| 1 | **Low** | `EmbedTab` setzt seinen `failed`-State beim Engine-Wechsel nicht zurück; die Route gab der `EmbedTab` keinen `key` → potenziell übernommene „verweigert"-Meldung. | ✅ **Behoben** — Route rendert `<EmbedTab key={engine.key} …>` → frischer Mount, `failed` automatisch zurückgesetzt. |
| 2 | **Low** | Doppelte Kopfzeile in der Route (Route-Header + `EmbedTab`-Header zeigten beide das Label). | ✅ **Behoben** — neuer `headerLeading`-Slot in `EmbedTab`; Route reicht „← Cockpit" rein, separater Route-Header entfällt → **eine** Kopfzeile. |
| 3 | **Low** | Edge-Case „App offline/Tailscale getrennt": kein Retry-Knopf, kein expliziter Offline-Text. | ✅ **Behoben** — „Erneut laden"-Button (iFrame-Remount via `reloadKey`) immer sichtbar; Fußzeilen-Hinweis nennt jetzt Offline/Tailscale. |

**Keine Critical/High-Bugs.** Alle 3 Low-Findings wurden im Anschluss an die QA **behoben** (Commit-fähig); Re-Test: `vitest`/`pytest`/`eslint`/`tsc` grün.

### Produktionsreife
**READY (Code/Registry-Oberfläche)** — keine Critical/High-Bugs; automatisierte Tests grün; Sicherheits-Review ohne Code-Befund.

⚠️ **Deploy-Gate:** Die *reale* Einbettung von Paperclip/Wayland ist erst nach dem Infra-Schritt (`/abc-deploy`: 2 DNS-A-Records + Caddy-Blöcke mit `forward_auth` (Paperclip) bzw. `header_down`-Overrides (Wayland) + `caddy reload`) testbar. Bis dahin greift nur der „In neuem Tab öffnen"-Fallback. Der Live-Browser-Smoke (Einbettung lädt, Wayland-Framing nach Header-Override, Paperclip nur nach Jupiter-Login, Toggle/Sort im Panel, Mobile-Drawer) ist **nach** Deploy nachzuholen.

## Deployment
- **Production-URL:** https://jupiter.auxevo.tech (Sidebar → „Orchestration")
- **Deployed:** 2026-06-25 · **Version:** 0.14.0 · **Tag:** v0.14.0
- **Host:** Dev-VPS host-nativ (systemd `jupiter-backend`/`jupiter-frontend`) + Caddy-TLS; GitHub-Webhook deployt `main` (`deploy.sh`: `reset --hard origin/main` → `npm ci && npm run build` → Service-Restart).
- **Mit ausgeliefert:** Orchestration-Sidebar-Sektion + Vollbild-Route `/orchestration/[key]`; Registry-Einträge Paperclip/Wayland (`group: orchestration`).
- **Infra (manuell, vor diesem Deploy erledigt):** DNS-A-Records `paperclip`/`wayland` → `187.124.182.215`; Caddy-Blöcke (Paperclip hinter eigener Forward-Auth-Instanz `jupiter-auth-paperclip` Port 9101, eigenes Cookie `paperclip_session`; Wayland `-X-Frame-Options` + `frame-ancestors https://jupiter.auxevo.tech`).
- **Smoke-Test (Browser, nach Deploy):**
  - [ ] Einloggen auf jupiter.auxevo.tech → Sidebar zeigt „Orchestration" mit Paperclip + Wayland
  - [ ] Paperclip öffnen → eigener Login im iFrame (gleiche Credentials), danach eingebettet
  - [ ] Wayland öffnen → eigener Wayland-Login, eingebettet (Framing-Override greift)
  - [ ] Toggle/Sort der Einträge im Konfig-Panel; Direkt-URL bei ausgeblendeter Sektion
