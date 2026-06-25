# PROJ-39: Sidebar-Sektion „Orchestration" — Fremd-Apps per iFrame (Paperclip, Wayland)

## Status: Architected
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

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
