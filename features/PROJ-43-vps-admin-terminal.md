# PROJ-43: VPS-Admin — Terminal (Shell-Zugriff)

## Status: Architected
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-42 (VPS-Admin — Dashboard) — das Terminal lebt **innerhalb derselben Micro-App-Kachel** „VPS-Admin" als eigener Bereich/Tab.
- Requires: PROJ-40 (Micro-Apps-Sektion / `kind: native`) + PROJ-3 (Cockpit-Shell / Routing) — Vollbild-Ansicht im Hauptbereich.
- Bezug: PROJ-39 (Orchestration — Fremd-Apps per iFrame) — teilt das **iFrame-Einbettungs-Muster** (`embed-tab.tsx`, Sandbox + Fallback), falls Terminal-Variante B1 (ttyd im iFrame) gewählt bleibt.
- Bezug: [[jupiter-deployment]] — Shell zielt auf den **host-nativen Dev-VPS**; Terminal-Dienst läuft als zusätzlicher systemd-Dienst auf demselben Host.

## Beschreibung
Ein **Terminal-Fenster** innerhalb der Micro-App „VPS-Admin", über das der Nutzer eine **Shell auf dem VPS** erhält und **Konfigurationsbefehle** eingeben kann. Damit lässt sich der VPS direkt aus Jupiter heraus verwalten, ohne separates SSH/Terminal.

### Geklärte Entscheidungen (2026-06-25)
- **Technik (B1):** **`ttyd`** als systemd-Dienst auf dem VPS (winziges Binary, serviert eine Shell über WebSocket) wird per **iFrame** in den Terminal-Bereich der VPS-Admin-Micro-App eingebettet. Begründung: robust, minimaler eigener Code, nutzt das vorhandene iFrame-Muster (PROJ-39). Die **native** Alternative (xterm.js + Backend-PTY) ist als spätere Option dokumentiert, aber **nicht** MVP.
- **Sicherheit:** Shell-Zugriff = **Vollzugriff** auf den VPS. Akzeptabel, weil Jupiter **single-user hinter Tailscale** läuft (kein Auth im MVP, Projekt-Entscheidung). Der ttyd-Dienst wird **nicht** öffentlich exponiert — nur lokal/Tailscale-intern erreichbar und ausschließlich über Jupiter eingebettet.

## User Stories
- Als Nutzer möchte ich in der VPS-Admin-App ein **Terminal** öffnen, um direkt auf dem VPS Befehle einzugeben.
- Als Nutzer möchte ich **Konfigurationsbefehle** (z. B. Dienste neu starten, Logs prüfen) ausführen, ohne ein separates SSH-Programm zu öffnen.
- Als Nutzer möchte ich zwischen **Dashboard** und **Terminal** innerhalb derselben Micro-App wechseln, damit beides an einem Ort liegt.
- Als Nutzer möchte ich, dass eine laufende Befehlsausgabe **nicht abbricht**, wenn ich kurz wegklicke und zurückkomme (Session-Persistenz, soweit ttyd das hergibt).
- Als Nutzer möchte ich einen klaren **Hinweis**, falls das Terminal gerade **nicht erreichbar** ist (Dienst aus), statt einer leeren/kaputten Fläche.

## Acceptance Criteria
- [ ] Innerhalb der Micro-App **VPS-Admin** gibt es einen **Terminal-Bereich** (z. B. Tab „Terminal" neben „Dashboard").
- [ ] Das Terminal liefert eine **funktionierende interaktive Shell** auf dem VPS (Eingabe + Ausgabe, inkl. laufender Programme wie `htop`/`tail -f`).
- [ ] **Konfigurationsbefehle** lassen sich ausführen (kein read-only); Rechte entsprechen dem Benutzer, unter dem der Terminal-Dienst läuft.
- [ ] Terminal-Variante **B1**: `ttyd` läuft als **systemd-Dienst** und wird per **iFrame** eingebettet; der Dienst ist **nicht öffentlich** exponiert (lokal/Tailscale-intern).
- [ ] Verweigert die Einbettung (CSP/X-Frame-Options) → **„In neuem Tab öffnen"-Fallback** (wie `embed-tab.tsx`).
- [ ] **Terminal-Dienst nicht erreichbar** (Dienst gestoppt) → sauberer Hinweis + Retry, kein Crash/leere Fläche.
- [ ] Das Terminal nutzt die **Vollbild-Hauptfläche**; Wechsel Dashboard ↔ Terminal ohne Reload der ganzen Seite.
- [ ] UI-Texte/Hinweise **deutsch** (Terminal-Inhalt = Shell-Ausgabe bleibt unverändert).

## Edge Cases
- **ttyd-Dienst gestoppt/abgestürzt** → Terminal-Bereich zeigt „Terminal nicht erreichbar" + Retry; Dashboard (PROJ-42) bleibt nutzbar.
- **WebSocket bricht ab** (Netz/Tailscale-Reconnect) → klarer Reconnect-Hinweis; idealerweise automatischer Reconnect.
- **Mehrere Tabs/Fenster gleichzeitig** → Verhalten definiert (ttyd erlaubt je nach Konfig mehrere Clients; ggf. eigene Session je Verbindung) — in Architektur festlegen.
- **Lange Ausgabe / `tail -f`** → Terminal bleibt responsiv; Scrollback funktioniert.
- **Browser-Reload während laufendem Befehl** → ttyd-Verhalten dokumentieren; Erwartung dem Nutzer kommunizieren (Session ggf. neu).
- **Sektion „Micro-Apps" ausgeblendet** → VPS-Admin (inkl. Terminal) per Direkt-URL erreichbar.
- **Sicherheit:** Terminal-Dienst darf **nicht** auf einer öffentlichen Adresse lauschen; Bind auf localhost/Tailscale-Interface, sonst offener Shell-Zugang. In QA explizit prüfen.

## Technical Requirements (optional)
- **Terminal-Dienst (B1):** `ttyd` als systemd-Dienst auf dem VPS, gebunden an localhost/Tailscale (nicht öffentlich), startet die Login-Shell des Service-Users. Reverse-Proxy/Pfad über Caddy (passend zu [[jupiter-deployment]]) oder direkte interne Adresse — entscheidet `/abc-architecture` + `/abc-deploy`.
- **Einbettung:** iFrame im native VPS-Admin-Component (Tab „Terminal"), Wiederverwendung der `embed-tab.tsx`-Logik (Sandbox + `onError`-Fallback „In neuem Tab öffnen").
- **Registry/Routing:** kein neuer Sidebar-Eintrag — Terminal ist ein **Unterbereich** der VPS-Admin-Micro-App (PROJ-42), kein eigener `engines.yaml`-Eintrag.
- **Alternative (nicht MVP):** native Variante xterm.js (Frontend) + FastAPI-PTY über WebSocket — dokumentiert für späteren Ausbau, falls tiefere Integration/Theming gewünscht.
- **Sicherheit:** kein Auth/RLS im MVP (single-user/Tailscale), aber **Bind nur intern** ist Pflicht; in `/abc-qa` als Sicherheits-Check verankern (Port nicht öffentlich erreichbar).
- **Texte deutsch.**

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (Terminal-Tab in der nativen VPS-Admin-Micro-App, iFrame) + `ttyd` als systemd-Dienst + dünner FastAPI-Erreichbarkeits-Endpoint + Caddy-Reverse-Proxy · **Branch:** dev

### Überblick / Grundhaltung
Das Terminal ist **kein neuer Sidebar-Eintrag**, sondern ein **Tab innerhalb der bestehenden VPS-Admin-Micro-App** (PROJ-42). Die native Komponente `VpsAdminApp` bekommt eine **Tab-Leiste „Dashboard · Terminal"**; der Terminal-Tab bettet die von `ttyd` servierte Shell per **iFrame** ein und nutzt dafür das **vorhandene Einbettungs-Muster** (Sandbox + „In neuem Tab öffnen"-Fallback aus [`embed-tab.tsx`](nextjs_app/components/cockpit/embed-tab.tsx)).

`ttyd` läuft als eigener **systemd-Dienst** auf demselben host-nativen Dev-VPS ([[jupiter-deployment]]), gebunden **ausschließlich an `127.0.0.1`** (nicht öffentlich, nicht 0.0.0.0). Erreichbar gemacht wird es über **Caddy als Reverse-Proxy unter derselben Origin** wie Jupiter (`https://jupiter.auxevo.tech/<pfad>`). Das löst zwei Probleme auf einmal: kein **Mixed-Content** (die Einbettung läuft über `https`, nicht über eine `http`-Tailscale-IP — vgl. den Schutz in [`app/(cockpit)/apps/[key]/page.tsx:134`](nextjs_app/app/(cockpit)/apps/[key]/page.tsx#L134)) und keine **cross-origin `frame-ancestors`**-Reibung (gleiche Origin ⇒ Einbettung erlaubt). Das Backend steuert nur eine **leichte Erreichbarkeits-/URL-Auskunft** bei, damit „Dienst aus" sauber von „Einbettung verweigert" unterschieden werden kann.

### A) Komponenten-Struktur (UI-Baum)
```
/apps/vps_admin  (native, Vollbild — PROJ-42)
└── VpsAdminApp
    ├── TabBar  „Dashboard · Terminal"   (interner Zustand, KEIN Seiten-Reload)
    ├── Tab „Dashboard"  → PROJ-42-Inhalt (StatusBanner, Gauges, …)   ← unverändert
    └── Tab „Terminal"   → TerminalTab
        ├── Lade-Zustand      („Terminal wird geprüft …")
        ├── Deaktiviert       (Dienst nicht konfiguriert → Hinweis, kein iFrame)
        ├── Nicht erreichbar  („Terminal nicht erreichbar" + „Erneut versuchen")
        └── Bereit            → iFrame auf die ttyd-Shell (Sandbox + Fallback)
```
- **Kein** `microapps-registry.ts`-Eintrag und **kein** neuer `engines.yaml`-Eintrag (Terminal ist Unterbereich von `vps_admin`, nicht eigenständige App — entspricht der Spec).
- Tab-Wechsel ist reiner React-State in `VpsAdminApp`; die ganze Seite lädt **nicht** neu (AC „ohne Reload der ganzen Seite").
- **iFrame bleibt beim Tab-Wechsel montiert** (per CSS aus-/eingeblendet statt unmounten), damit die laufende WebSocket-Verbindung beim kurzen Wechsel zu „Dashboard" und zurück **nicht** abreißt (User-Story „nicht abbrechen, wenn ich kurz wegklicke").

### B) `ttyd`-Dienst (Betrieb, Detail in `/abc-deploy`)
- **systemd-Dienst** `ttyd` (User `dev`), Kommando ≈ `ttyd --interface 127.0.0.1 --port 7681 --writable tmux new -A -s jupiter`.
  - `--interface 127.0.0.1` → **nur localhost**, niemals öffentlich (Sicherheits-Pflicht der Spec; in QA prüfen).
  - `--writable` → Eingabe erlaubt (kein read-only; Konfigurationsbefehle möglich).
  - `tmux new -A -s jupiter` → **Session-Persistenz**: jeder Client (Reload, kurz weg & zurück, zweites Fenster) **attached an dieselbe tmux-Session** ⇒ laufende Programme (`htop`, `tail -f`) überleben Browser-Reload und Reconnect. Genau das adressiert die User-Stories zu „nicht abbrechen" + Edge-Case „Browser-Reload während laufendem Befehl".
- **Caddy** proxyt eine **gleich-origin Route** unter `jupiter.auxevo.tech` (z. B. `/vps-terminal/*` inkl. WebSocket-Upgrade) auf `127.0.0.1:7681`. Gleiche Origin ⇒ kein Mixed-Content, kein cross-origin Framing. (Alternative: Subdomain `terminal.auxevo.tech` mit explizitem `frame-ancestors jupiter.auxevo.tech` — wie der Wayland-Block in `engines.yaml`; gleich-origin ist aber einfacher und wird empfohlen.)

### C) Datenmodell (Klartext)
Kein Persistenz-Bedarf, keine DB. Einzige „Daten" sind drei Konfig-/Laufzeit-Felder, die das Backend dem Frontend mitteilt:
- `enabled` (bool) — ist ein Terminal-Dienst überhaupt konfiguriert (URL gesetzt)?
- `url` (string) — die einzubettende `https`-Adresse (gleiche Origin, aus Backend-Config; nie vom Client gesetzt).
- `reachable` (bool) — antwortet der `ttyd`-Port gerade (kurzer TCP-Connect-Probe auf `127.0.0.1:7681`)?

### D) API-Shape (neue Route, kein Code)
Dünner neuer Router `backend/app/routes/terminal.py` (Schema in `backend/app/schemas/terminal.py`, Pydantic v2), Stil wie die bestehenden dünnen Read-Routen:
```
GET /terminal/info → { enabled: bool, url: string|null, reachable: bool }
```
- **Erreichbarkeits-Probe:** kurzer TCP-Connect (kleiner Timeout) auf den lokalen ttyd-Port. Schlägt er fehl → `reachable=false` ⇒ Frontend zeigt „Terminal nicht erreichbar" + Retry, **statt** einer leeren/kaputten iFrame-Fläche. Antwortet er → `reachable=true` ⇒ iFrame; verweigert die Einbettung doch noch (CSP/X-Frame), greift der iFrame-`onError`-Fallback aus dem embed-tab-Muster.
- Read-only, kein Auth/RLS (MVP, single-user hinter Tailscale). Keine clientseitig gesetzte URL — die kommt **nur** aus der Backend-Config.

### E) Backend-Mechanik & Config
- Neue Felder in [`config.py`](backend/app/config.py) (Prefix `JUPITER_`):
  - `terminal_url: str = ""` — leer ⇒ `enabled=false` (Feature aus, sauberer Hinweis statt Crash; erlaubt Aktivierung erst nach `/abc-deploy`).
  - `terminal_probe_host: str = "127.0.0.1"`, `terminal_probe_port: int = 7681`, `terminal_probe_timeout_seconds: float = 1.5`.
- Die Probe ist ein **nicht-blockierender, kurz getimeouteter** Socket-Connect (kein `subprocess`, keine Shell). Fehlerfälle (Connection refused / Timeout) ⇒ `reachable=false`, nie eine Exception nach außen.
- Router in `main.py` via `include_router` registrieren (wie die übrigen Routen).

### F) Frontend-Mechanik
- `TerminalTab` ruft beim Öffnen `GET /terminal/info` (AbortController-Muster wie die apps-Route) und verzweigt in die vier Zustände aus (A). „Erneut versuchen" = erneuter `/terminal/info`-Abruf **und** iFrame-Remount (`reloadKey++`, exakt wie `embed-tab.tsx`).
- **iFrame-Einbettung über Wiederverwendung von `EmbedTab`:** dem `EmbedTab` wird ein minimales engine-förmiges Objekt `{ key: "vps_terminal", label: "Terminal", url, sandbox }` mit `fullHeight` übergeben — so erbt der Terminal-Tab Sandbox, „Erneut laden", „In neuem Tab öffnen"-Fallback und die X-Frame-Hinweiszeile **ohne** Duplizierung. Der **Erreichbarkeits-Gate** (loading/disabled/unreachable) liegt davor in `TerminalTab` (das ist terminal-spezifisch und gehört nicht in das generische `EmbedTab`).
- **Sandbox** für ttyd: `allow-scripts allow-same-origin allow-clipboard-read allow-clipboard-write` (Scripts für xterm.js; same-origin für WebSocket + lokale Einstellungen; Clipboard für Copy/Paste im Terminal). Da wir ttyd selbst betreiben, ist `allow-same-origin` unbedenklich.
- Texte/Hinweise **deutsch**; der **Terminal-Inhalt** (Shell-Ausgabe) bleibt unverändert.

### G) Tech-Entscheidungen (WARUM)
- **iFrame statt nativem xterm.js+PTY (B1):** robust, minimaler Eigencode, wiederverwendetes Einbettungs-Muster (PROJ-39/embed-tab). Die native Variante (xterm.js + FastAPI-WebSocket-PTY) ist in der Spec als spätere Option dokumentiert, aber bewusst **nicht** MVP.
- **`tmux new -A -s jupiter` als ttyd-Kommando:** liefert echte **Session-Persistenz** über ttyd-Bordmittel hinaus — laufende Befehle überleben Reload/Reconnect/zweites Fenster. Direkt auf die User-Stories + Edge-Cases gemünzt, ohne eigenen Persistenz-Code.
- **Gleiche Origin via Caddy statt Subdomain:** vermeidet zugleich Mixed-Content **und** cross-origin `frame-ancestors` — die zwei Stolpersteine, die in diesem Projekt schon bei Orchestration/Wayland auftraten.
- **Backend-Erreichbarkeits-Probe statt nur iFrame-`onError`:** `iframe onError` feuert bei „Connection refused" unzuverlässig — ein aktiver TCP-Probe unterscheidet verlässlich „Dienst aus" (Hinweis+Retry) von „Einbettung verweigert" (embed-Fallback). Erfüllt den Edge-Case „kein Crash/leere Fläche".
- **`terminal_url` leer = Feature aus:** das Frontend ist mergebar/lauffähig, **bevor** der ttyd-Dienst + Caddy via `/abc-deploy` stehen — sauberer „nicht konfiguriert"-Hinweis statt kaputter Fläche.
- **Kein neuer Registry-/engines.yaml-Eintrag:** Terminal ist Unterbereich von `vps_admin`, kein eigenständiges Tool — hält die Sidebar sauber (Spec-Vorgabe).

### H) Abhängigkeiten (Pakete)
- **Backend:** keine neuen Python-Pakete (TCP-Probe via stdlib `socket`/`asyncio`). `ttyd` + `tmux` sind **System-Binaries**, die `/abc-deploy` auf dem VPS installiert/als systemd-Dienst einrichtet — keine Repo-Dependency.
- **Frontend:** keine neuen Pakete — `EmbedTab`, `LaunchButton`, shadcn/ui-Tabs/Card + `lucide-react` (`terminal`-Icon) sind vorhanden.

### I) Sicherheit / Betrieb
- **Shell = Vollzugriff.** Akzeptabel nur, weil Jupiter single-user hinter Tailscale läuft (Projekt-Entscheidung, [[jupiter-stack-overrides]]).
- **Pflicht:** ttyd bindet **nur** an `127.0.0.1` — niemals `0.0.0.0`/Tailscale-IP direkt. Öffentlicher Zugang ausschließlich über die Caddy-Route auf der bereits Tailscale-geschützten Jupiter-Origin. In `/abc-qa` explizit prüfen: Port von außen **nicht** erreichbar.
- TCP-Probe mit festem Host/Port aus der Config (keine Client-Eingabe, keine Shell-Interpolation), kurzer Timeout, Fehler abgefangen.

### J) Bau-Reihenfolge / Hand-offs
1. **Voraussetzung:** PROJ-42-Frontend stellt `VpsAdminApp` bereit; PROJ-43 fügt dort die **Tab-Leiste** + `TerminalTab` hinzu. (Wird PROJ-43 vor dem PROJ-42-Frontend gebaut, legt PROJ-43 die Tab-Hülle an und PROJ-42 hängt den Dashboard-Tab ein.)
2. **Backend** (`/abc-backend`): `config.py`-Felder, `routes/terminal.py` + `schemas/terminal.py` (`GET /terminal/info` mit TCP-Probe), Router registrieren.
3. **Frontend** (`/abc-frontend`): Tab-Leiste in `VpsAdminApp`, `TerminalTab` (vier Zustände, `/terminal/info`-Abruf, `EmbedTab`-Reuse, montiert-bleibender iFrame).
4. **Deploy** (`/abc-deploy`): `ttyd`+`tmux` installieren, systemd-Dienst `ttyd` (Bind `127.0.0.1`, `tmux new -A`), Caddy-Route (gleich-origin, WebSocket-Upgrade), `JUPITER_TERMINAL_URL` setzen.
5. **QA** (`/abc-qa`): interaktive Shell (Eingabe/Ausgabe, `htop`/`tail -f`), Persistenz über Reload, „Dienst gestoppt → Hinweis+Retry", Einbettungs-Fallback, Direkt-URL bei ausgeblendeter Sektion, **Sicherheits-Check: ttyd-Port nicht öffentlich**.

### K) Referenz-Dateien (Ist-Stand, verifiziert)
- Einbettungs-Muster (Sandbox + Fallback + Retry): [`embed-tab.tsx`](nextjs_app/components/cockpit/embed-tab.tsx)
- Native Micro-App-Host / Mixed-Content-Schutz: [`app/(cockpit)/apps/[key]/page.tsx:119`](nextjs_app/app/(cockpit)/apps/[key]/page.tsx#L119), Mixed-Content `:134`
- Registry (kein neuer Eintrag nötig): [`microapps-registry.ts`](nextjs_app/lib/microapps-registry.ts)
- Config-Muster (Prefix `JUPITER_`): [`config.py`](backend/app/config.py)
- Caddy-Framing-Vorbild (cross-origin Alternative): `engines.yaml` Wayland-/Orchestration-Block
- VPS-Admin-Host-Komponente: PROJ-42 `components/microapps/vps_admin/` (Tab-Träger)

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
