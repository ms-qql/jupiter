# PROJ-42: VPS-Admin — Dashboard (native Micro-App)

## Status: Deployed
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-40 (Sidebar-Sektion „Micro-Apps" + `kind: native`) — VPS-Admin ist eine **native** Micro-App (`group: micro`, `kind: native`, Route `/apps/<key>`, Eintrag in `microapps-registry.ts`), wie PROJ-41.
- Requires: PROJ-3 (Cockpit-Shell / Sidebar / Routing) — Sidebar-Eintrag + Vollbild-Ansicht im Hauptbereich; **Erweiterung der Sidebar um ein Status-Farb-Icon** pro Micro-App-Eintrag.
- Bezug: PROJ-38 (Sidebar-Sektionen + Konfig-Panel) — Eintrag ist toggel-/sortierbar; Ampel-Icon stört das Konfig-Panel nicht.
- Verwandt: PROJ-43 (VPS-Admin — Terminal) — **gleiche Micro-App-Kachel**, Terminal ist ein eigener Bereich/Tab innerhalb von VPS-Admin; eigener Spec (Single Responsibility).
- Bezug: [[jupiter-deployment]] — Metrik-Quelle ist der **host-native Dev-VPS** (systemd: `backend`/`frontend`/`webhook` + Caddy); das Jupiter-Backend läuft auf demselben Host und liest die Werte lokal.

## Beschreibung
Eine native Micro-App **„VPS-Admin"** in der Sidebar-Sektion „Micro-Apps". Sie zeigt **auf einen Blick** den IT-Zustand des VPS: Auslastung der Kern-Ressourcen (CPU, RAM, Disk, Load), kurze Verlaufs-Trends, sowie den Gesundheitszustand der für Jupiter relevanten **systemd-Dienste**. Eine **Status-Bannerzeile** (Gut · Achtung · Kritisch) fasst den Gesamtzustand zusammen.

Zusätzlich signalisiert ein **kleines Farb-Icon direkt am Sidebar-Eintrag** (grün/gelb/rot) den aktuellen VPS-Gesamtstatus, ohne dass die App geöffnet sein muss.

Vorbild ist das 1Panel-Overview (Donut-Gauges für CPU/Memory/Load/Disk), **erweitert** um Verlaufs-Sparklines, Uptime, Netz-I/O, Swap, Top-Prozesse und Service-Health — damit nicht nur „wie ausgelastet", sondern auch „läuft alles" auf einen Blick sichtbar ist.

Das **Terminal** (Shell-Zugriff auf den VPS) ist bewusst als **eigenes Feature PROJ-43** ausgegliedert, teilt sich aber dieselbe Micro-App-Kachel.

### Geklärte Entscheidungen (2026-06-25)
- **Schnitt (A1):** Dashboard (dieser Spec) und Terminal (PROJ-43) sind getrennte, einzeln baubare Features unter einer gemeinsamen Micro-App.
- **Datenquelle:** Metriken werden **host-nativ** vom Jupiter-Backend gelesen (kein externer Agent, kein 1Panel). Genaue Bibliothek/Implementierung entscheidet `/abc-architecture`.
- **Umfang (D1):** Voller Umfang — Kern-Gauges **plus** Sparklines, Uptime, Netz-I/O, Swap, Top-Prozesse, systemd-Service-Health.
- **Ampel-Schwellen (C1):** **grün** < 75 %, **gelb** 75–90 %, **rot** > 90 % (CPU/RAM/Disk; Load relativ zur Core-Zahl). Gesamt-Ampel = **schlechtester** Einzelwert. Schwellen später konfigurierbar (Default fix im MVP).
- **Live-Aktualisierung:** Polling alle paar Sekunden (genaues Intervall in Architektur), explizite Loading-/Error-/Empty-/Success-Zustände.

## User Stories
- Als Nutzer möchte ich in der Micro-App **auf einen Blick** sehen, ob der VPS gesund ist (eine klare Gut/Achtung/Kritisch-Aussage), damit ich nicht erst Zahlen interpretieren muss.
- Als Nutzer möchte ich **CPU-, RAM-, Disk- und Load-Auslastung** als Gauges sehen (wie 1Panel), inkl. absoluter Werte (z. B. „5,1 / 31,3 GB", „0,2 / 8 Cores").
- Als Nutzer möchte ich einen **kurzen Verlauf** (Sparkline) je Kennzahl sehen, um zu erkennen, ob ein Wert gerade steigt.
- Als Nutzer möchte ich **Uptime, Netz-I/O, Swap und die Top-Prozesse** sehen, um Auffälligkeiten schnell einzuordnen.
- Als Nutzer möchte ich sehen, ob die **Jupiter-Dienste** (backend/frontend/webhook) und **Caddy** laufen (aktiv/inaktiv/fehlerhaft), damit ich Ausfälle sofort erkenne.
- Als Nutzer möchte ich am **Sidebar-Eintrag** ein **kleines Farb-Icon** (grün/gelb/rot), das den VPS-Gesamtstatus anzeigt, **ohne** die App zu öffnen.
- Als Nutzer möchte ich, dass die Anzeige sich **automatisch aktualisiert**, damit ich einen Live-Eindruck habe.

## Acceptance Criteria
- [ ] **VPS-Admin** erscheint als Eintrag in der Sidebar-Sektion „Micro-Apps" (`group: micro`, `kind: native`) mit Label + Icon und öffnet als **Vollbild** unter `/apps/<key>`.
- [ ] Die App ist als **native** Micro-App umgesetzt (React-Komponente im Repo, registriert in `microapps-registry.ts`) — **kein** iFrame für das Dashboard.
- [ ] Eine **Status-Bannerzeile** zeigt den Gesamtzustand **Gut · Achtung · Kritisch** (farbcodiert), abgeleitet aus dem schlechtesten Einzelwert.
- [ ] **Gauges** für **CPU, RAM, Disk, Load** mit Prozentwert **und** absoluten Werten (Cores; GB used/total; Disk used/total; Load-Einordnung).
- [ ] Je Kern-Kennzahl eine **Verlaufs-Sparkline** (kurzes rollierendes Zeitfenster).
- [ ] Zusatz-Kacheln: **Uptime**, **Netz-I/O** (rx/tx-Rate), **Swap-Auslastung**, **Top-Prozesse** (nach CPU und/oder RAM, Top N).
- [ ] **Service-Health**: Liste der relevanten systemd-Dienste (`backend`, `frontend`, `webhook`, Caddy) mit Status **aktiv · inaktiv · fehlerhaft** (farbcodiert).
- [ ] **Sidebar-Ampel:** der Sidebar-Eintrag „VPS-Admin" trägt ein **kleines Farb-Icon** (grün/gelb/rot) entsprechend dem VPS-Gesamtstatus; aktualisiert sich periodisch.
- [ ] **Schwellen:** grün < 75 %, gelb 75–90 %, rot > 90 % (CPU/RAM/Disk); Load relativ zur Core-Zahl; Gesamt = schlechtester Einzelwert.
- [ ] Die Werte werden **host-nativ** vom Backend gelesen und über eine **neue API** bereitgestellt; das Frontend **pollt** sie periodisch.
- [ ] Explizite **Loading-/Error-/Empty-Zustände** (z. B. wenn Metriken kurz nicht lesbar sind → Hinweis statt Crash).
- [ ] Alle Texte/Labels/Fehlermeldungen **deutsch** (App-Eigenname „VPS-Admin" bleibt; Einheiten wie GB/%/Cores bleiben).
- [ ] Sektion „Micro-Apps" im Konfig-Panel ausgeblendet → App per Direkt-URL `/apps/<key>` weiter erreichbar (kein verwaister Zustand, wie PROJ-40).

## Edge Cases
- **Metrik kurz nicht lesbar** (z. B. transienter Lesefehler) → betroffene Kachel zeigt „—"/Hinweis, restliche Werte bleiben sichtbar; kein Crash.
- **systemd-Dienst nicht vorhanden/umbenannt** → Dienst als „unbekannt" markieren statt Fehler; Liste der erwarteten Dienste ist konfigurierbar (Architektur).
- **Mehrere Disks / Mounts** → mindestens Root-`/` anzeigen; weitere Mounts optional (Architektur entscheidet Umfang).
- **Load auf Single-Core vs. Many-Core** → Bewertung immer **relativ zur Core-Zahl** (Load/Cores), nicht absolut, damit die Ampel stimmt.
- **VPS frisch gebootet** → Sparklines noch leer/kurz → sauberer Anfangszustand, kein „springender" Graph.
- **Polling während Tab im Hintergrund** → Intervall darf gedrosselt werden; beim Zurückkehren sofort frische Werte holen.
- **Sidebar-Ampel ohne geöffnete App** → Status-Abruf für das Icon läuft unabhängig von der geöffneten App (leichter Endpoint), darf das Backend nicht belasten.
- **Backend-Neustart** → nach Neustart liefert die API wieder Werte; Sparkline-Historie darf neu anfangen (kein Persistenz-Zwang für Verlauf im MVP).

## Technical Requirements (optional)
- **Native Micro-App-Muster (PROJ-40/PROJ-41):** Metadaten-Eintrag in `backend/config/engines.yaml` (`kind: native`, `group: micro`, Label, Icon); Code unter `nextjs_app/components/microapps/<key>/`, registriert in `nextjs_app/lib/microapps-registry.ts`; Render über die kind-Verzweigung in `app/(cockpit)/apps/[key]/page.tsx`.
- **Metrik-Erhebung:** Backend liest **host-native** System-Metriken (CPU/RAM/Disk/Load/Swap/Netz/Uptime/Prozesse) + systemd-Status. Bibliothek (`psutil` o.ä.) und systemd-Abfrage (`systemctl is-active …`) entscheidet `/abc-architecture`. **Read-only** — das Dashboard ändert nichts am System.
- **API:** neue FastAPI-Routen für (a) vollständigen Metrik-Snapshot (für die geöffnete App) und (b) einen **leichten Gesamtstatus** (grün/gelb/rot) für die Sidebar-Ampel. Schemas in `backend/app/schemas/`, Pydantic v2.
- **Sparkline-Historie:** kurzes rollierendes Fenster im Backend-Speicher (kein Postgres-Zwang im MVP); Frontend pollt.
- **Frontend:** React-Komponente (Tailwind + shadcn/ui), Gauges/Sparklines (Charts via Plotly.js gemäß Stack **oder** leichtgewichtige SVG-Gauges — Architektur entscheidet); Zustände Loading/Error/Empty/Success explizit.
- **Sidebar-Erweiterung:** der bestehende Micro-App-Sidebar-Eintrag wird um ein optionales **Status-Icon** erweitert (generisches Feld, damit weitere Apps später eine Ampel zeigen können).
- **Kein Auth/RLS im MVP** (Projekt-Entscheidung, single-user hinter Tailscale); `owner`-Feld nicht erforderlich für read-only Metriken.
- **Texte deutsch.**

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (native Micro-App) + FastAPI/asyncio-Metrik-Worker + **In-Memory-Verlauf** (kein Postgres/SQLite-Zwang im MVP) · **Branch:** dev

### Überblick / Grundhaltung
VPS-Admin ist eine **native** Micro-App nach dem PROJ-40/PROJ-41-Muster: React-Komponente im Repo, Metadaten in `engines.yaml` (`kind: native`, `group: micro`), gerendert über `/apps/vps_admin`. Das Backend liest die Metriken **host-nativ und read-only** und stellt sie über zwei Endpunkte bereit. Ein **asyncio-Hintergrund-Worker im Lifespan** (Vorbild `_liveness_loop` / `_video_summary_loop` in `main.py`) berechnet periodisch einen Metrik-Snapshot und hält einen **kurzen rollierenden Verlauf im Speicher** (für die Sparklines). Frontend + Sidebar **pollen** — alle Drossel-/Bewertungslogik liegt im Backend, das Frontend ist reine Ansicht.

**Grundsatz: read-only.** Das Dashboard verändert nichts am System; es liest CPU/RAM/Disk/Load/Swap/Netz/Uptime/Prozesse und den `systemctl`-Status der relevanten Dienste.

### A) Komponenten-Struktur (UI-Baum)
```
/apps/vps_admin  (native, Vollbild)
└── VpsAdminApp
    ├── StatusBanner           (Gut · Achtung · Kritisch — Farbe = schlechtester Einzelwert)
    ├── GaugeGrid
    │   ├── Gauge „CPU"   (% + „0,2 / 8 Cores")      + Sparkline
    │   ├── Gauge „RAM"   (% + „5,1 / 31,3 GB")      + Sparkline
    │   ├── Gauge „Disk /"(% + „31 / 386 GB")        + Sparkline
    │   └── Gauge „Load"  (Load/Cores + „Low/High")  + Sparkline
    ├── InfoKacheln           (Uptime · Netz-I/O rx/tx · Swap-Auslastung)
    ├── TopProzesseTabelle    (Top N nach CPU/RAM: Name · PID · CPU% · RAM%)
    ├── ServiceHealthListe    (backend · frontend · webhook · caddy → aktiv/inaktiv/fehlerhaft, je mit Ampel)
    └── Lade-/Fehler-/Empty-Zustand  (Polling des Metrik-Snapshots)
```
- Registry: `engines.yaml`-Eintrag `vps_admin` (`kind: native`, `group: micro`, `icon: server`) + `microapps-registry.ts` (`vps_admin → lazy(import …)`) + Komponente unter `components/microapps/vps_admin/`.
- Gerendert über den native-Zweig in [`app/(cockpit)/apps/[key]/page.tsx`](nextjs_app/app/(cockpit)/apps/[key]/page.tsx) (`NativeMicroAppHost`, Props = nur `appKey`).
- Die App **pollt** `GET /metrics/current` alle paar Sekunden; im Hintergrund-Tab darf das Intervall gedrosselt werden.

### B) Sidebar-Ampel (Farb-Icon am Eintrag)
- Wiederverwendung der **bestehenden** [`ampel.tsx`](nextjs_app/components/cockpit/ampel.tsx) (`<Ampel color="green|amber|red|gray" />`) — **kein** neues Statuslicht bauen.
- Der Micro-App-Sidebar-Eintrag (gerendert in [`session-rail.tsx`](nextjs_app/components/cockpit/session-rail.tsx#L159), Item-Def in [`sidebar-config.ts`](nextjs_app/lib/sidebar-config.ts#L143)) wird um ein **optionales Status-Feld** erweitert: ein generischer „Status-Provider je Micro-App-Key", damit künftige Apps ebenfalls eine Ampel zeigen können (nicht hart auf VPS-Admin verdrahten).
- Die Sidebar holt den VPS-Gesamtstatus über einen **leichten** Endpoint `GET /metrics/status` (nur `green|amber|red`), unabhängig davon, ob die App geöffnet ist. Niedrige Frequenz, damit das Backend nicht belastet wird; der Worker liefert den Wert ohnehin aus dem Cache (keine Neuberechnung pro Request).

### C) Datenmodell (Klartext — In-Memory, keine DB-Persistenz im MVP)
**Metrik-Snapshot** (jeweils der aktuelle Stand, vom Worker periodisch erzeugt):
- CPU: Auslastung %, Core-Zahl, belegte „Cores" (für „0,2 / 8")
- RAM: %, used/total (GB) · Swap: %, used/total
- Disk: je Mount (mindestens Root `/`): %, used/total (GB)
- Load: 1-/5-/15-min, dazu Load/Cores als Bewertungsgröße
- Netz: rx/tx-Rate (aus Delta zweier Messungen)
- Uptime (seit Boot), Zeitstempel
- Top-Prozesse: Liste (Name, PID, CPU%, RAM%), Top N
- Services: je Dienst (`backend`,`frontend`,`webhook`,`caddy`) → `active|inactive|failed|unknown`
- **Gesamtstatus** `green|amber|red` (abgeleitet, s. D)

**Rollierender Verlauf** für Sparklines: pro Kennzahl ein kurzes Zeitfenster (z. B. letzte ~60 Messpunkte) im Worker-Speicher. **Bewusst nicht persistiert** — nach Backend-Neustart beginnt der Verlauf neu (Akzeptanzkriterium erlaubt das). Kein Postgres/SQLite nötig, weil es flüchtige Live-Daten sind (passt zur PRD-Grenze „Live-Index vs. Wahrheit").

### D) Bewertung / Schwellen (Backend, nicht Client)
- **grün** < 75 %, **gelb** 75–90 %, **rot** > 90 % für CPU/RAM/Disk.
- **Load** wird **relativ zur Core-Zahl** bewertet (Load/Cores in dieselben Schwellen), nie absolut.
- **Service `failed`** = rot, `inactive` (eines erwarteten Diensts) = mindestens gelb.
- **Gesamtstatus = schlechtester Einzelwert** über alle bewerteten Größen. Schwellen im MVP fix im Backend hinterlegt, später konfigurierbar (an `settings.py`/`policy.py`-Muster anschließbar).

### E) API-Shape (neue Routen, kein Code)
Neuer Router `backend/app/routes/metrics.py` (+ Schemas in `schemas/metrics.py`), Stil wie [`usage.py`](backend/app/routes/usage.py) (dünne HTTP-Schicht, Logik im Service unter `app.state`):
```
GET /metrics/current   → vollständiger Snapshot inkl. Verlauf (für die geöffnete App; Polling)
GET /metrics/status    → leichtgewichtig: nur Gesamt-Ampel green|amber|red (für die Sidebar)
```
Read-only, kein Auth/RLS (MVP, single-user hinter Tailscale). Beide Endpunkte liefern den **gecachten** Worker-Stand, berechnen also nicht pro Request.

### F) Backend-Mechanik (Klartext)
- **Worker** `engine/metrics_worker.py` mit `tick()`: misst Snapshot, aktualisiert Verlauf + Gesamtstatus, legt beides im Speicher ab. Eingehängt als `_metrics_loop(app)` im Lifespan ([`main.py`](backend/app/main.py#L106), neben den bestehenden Loops), Intervall z. B. 5–10 s, Cleanup auf `CancelledError` wie die Vorbilder.
- **Metriken** via `psutil` (CPU/RAM/Disk/Swap/Netz/Prozesse) + stdlib (`os.getloadavg`, `/proc/uptime`).
- **Service-Health** via `subprocess` `systemctl is-active <unit>` (defensives Fehler-Handling + Timeout wie [`git_service.py`](backend/app/engine/git_service.py)); erwartete Unit-Namen konfigurierbar abgelegt. Nicht gefundener Dienst → `unknown`, kein Crash.
- **Netz-Rate** aus Delta zweier aufeinanderfolgender Ticks (Worker hält den letzten Zählerstand).

### G) Tech-Entscheidungen (WARUM)
- **In-Memory statt DB:** Metriken sind flüchtige Live-Daten; ein rollierendes Fenster im Worker spiegelt exakt die bestehende „Live-Index"-Haltung (Liveness/Usage laufen genauso) und vermeidet unnötige Schreiblast. Verlust nach Neustart ist akzeptabel und im AC erlaubt.
- **Worker + Cache statt Messung pro Request:** entkoppelt teure Messungen (Prozessliste, `systemctl`) von der Request-Latenz und macht den Sidebar-Status-Endpoint billig — wichtig, weil die Sidebar pollt, auch wenn die App zu ist.
- **Bewertung im Backend:** der Sidebar-Punkt und das Banner müssen denselben „schlechtester-Wert"-Status zeigen; eine einzige Quelle im Backend verhindert Drift zwischen Client und Server.
- **`Ampel`-Reuse:** Statuslicht existiert bereits — kein neues Widget, konsistente Farben mit dem restlichen Cockpit.
- **Leichte SVG-Gauges statt Plotly:** für vier kleine Live-Gauges + Sparklines ist Plotly.js schwergewichtig; einfache SVG-/CSS-Gauges + minimaler Sparkline-Pfad sind leichter und flüssiger. (Falls eine vorhandene Chart-Abhängigkeit bereits geladen ist, kann `/abc-frontend` sie nutzen — Default ist leichtgewichtig.)
- **`systemctl is-active` statt D-Bus:** kein Zusatz-Dependency (`dbus-python`), simples, robustes Parsing; deckt aktiv/inaktiv/fehlerhaft ab.

### H) Abhängigkeiten (Pakete)
- **Backend neu:** `psutil` (System-Metriken). Sonst stdlib (`os`, `subprocess`, `/proc`). `systemctl` ist auf dem host-nativen VPS vorhanden.
- **Frontend:** keine neuen Pakete zwingend — shadcn/ui-Karten/Badges + `lucide-react`-Icon (`server`/`hard-drive`) + bestehende `Ampel`. Sparklines/Gauges als kleine eigene SVG-Komponenten.

### I) Sicherheit / Betrieb
- Read-only Metriken, kein Schreibpfad → geringe Angriffsfläche. Kein Auth im MVP (single-user/Tailscale, Projekt-Entscheidung).
- `subprocess`-Aufrufe mit **festen Argumentlisten** (keine Shell-Interpolation), Timeout, Fehler abgefangen.
- Worker-Fehler dürfen das Backend nie kippen (try/except pro Tick wie die Vorbild-Loops).

### J) Bau-Reihenfolge / Hand-offs
1. **Backend** (`/abc-backend`): `psutil` ergänzen, `metrics_worker.py` + `_metrics_loop` im Lifespan, `routes/metrics.py` + `schemas/metrics.py` (`/current`, `/status`), Service-Health via `systemctl`.
2. **Frontend** (`/abc-frontend`): `engines.yaml`-Eintrag `vps_admin` + `microapps-registry.ts` + Komponente (`StatusBanner`, `GaugeGrid` mit Sparklines, Info-Kacheln, Top-Prozesse, Service-Liste, Polling); **Sidebar-Ampel** über generisches Status-Feld + `GET /metrics/status`.
3. **QA** (`/abc-qa`): Schwellen/Gesamtstatus (rot bei >90 % / failed-Dienst), Ampel = Banner, Polling-/Fehler-/Empty-Zustände, Direkt-URL bei ausgeblendeter Sektion, `subprocess`-Robustheit.
> Reihenfolge **Backend zuerst** (Metrik-API + Worker sind Fundament/Risiko), dann Frontend gegen die fertige API. PROJ-43 (Terminal) dockt anschließend an dieselbe Kachel an.

### K) Referenz-Dateien (Ist-Stand, CodeGraph-verifiziert)
- Native Micro-App: `nextjs_app/lib/microapps-registry.ts:34`, `nextjs_app/app/(cockpit)/apps/[key]/page.tsx:119` (native-Zweig, `MicroAppComponentProps` = nur `appKey`)
- Sidebar: `nextjs_app/components/cockpit/session-rail.tsx:159`, `nextjs_app/lib/sidebar-config.ts:143`; Ampel: `nextjs_app/components/cockpit/ampel.tsx`
- Worker-Vorbild: `backend/app/main.py:59` (`_liveness_loop`/`_video_summary_loop`), Lifespan `:106`
- Route/Schema-Vorbild: `backend/app/routes/usage.py`, `backend/app/schemas/usage.py`
- Subprocess-Vorbild (Timeout/Fehler): `backend/app/engine/git_service.py`
- Registry-Eintrag: `backend/config/engines.yaml:76` (Micro-Apps-Block, `whiteboard`/`video_summary` als Vorbild)

## Implementation Notes (Backend — /abc-backend, 2026-06-25)
**Branch:** dev · **Tests:** 15 PROJ-42-Tests grün, gesamte Suite 672 grün (keine Regression).

Umgesetzt nach Tech-Design Abschnitt F/E/J-1 — read-only, in-memory, Worker + Cache:

- **`backend/app/engine/metrics.py`** — `MetricsService`: `tick()` misst host-nativ via `psutil` (CPU/RAM/Swap/Disk `/`/Netz-Rate/Uptime/Top-Prozesse) + `os.getloadavg`, hält letzten Snapshot + rollierenden Verlauf (`deque(maxlen=metrics_history_points)`) je Gauge im Speicher. psutil-Messung läuft über `asyncio.to_thread` (blockiert den Event-Loop nicht); CPU-Messung wird im Konstruktor geprimt. Netz-Rate aus Delta zweier Ticks. `startup()` zieht sofort einen ersten Snapshot, damit `/current` direkt Daten liefert. Leer-Stand (`_empty()`) ist schema-konform → keine 500 vor dem 1. Tick.
- **Bewertung** (`_status_for`/`_worst`): Schwellen aus `config` — `< 75 %` grün, `75–90 %` gelb, `> 90 %` rot (CPU/RAM/Disk **und** `(Load1/Cores)·100`). `overall_status` = schlechtester Einzelwert über alle Gauges + Services. Service `failed` → rot, `inactive` → gelb, `unknown` → ampel-neutral (nicht vorhandener/umbenannter Dienst färbt nicht fälschlich rot).
- **Service-Health**: `systemctl is-active <unit>` via `asyncio.create_subprocess_exec` (feste Argumentliste, kein Shell-Interpolation), hartes Timeout, jeder Fehler → `unknown`. Übergangszustände (`activating`/`reloading` → active, `deactivating` → inactive). Erwartete Units konfigurierbar: `jupiter-backend`, `jupiter-frontend`, `jupiter-webhook`, `caddy`.
- **`backend/app/routes/metrics.py`** — Router `/metrics`: `GET /current` (voller Snapshot inkl. Verlauf, Polling), `GET /status` (nur Gesamt-Ampel für die Sidebar). Beide lesen nur den Worker-Cache, messen nicht pro Request. Kein JWT (MVP single-user, vgl. `usage.py`).
- **`backend/app/schemas/metrics.py`** — Pydantic-v2-Schemas (`MetricsSnapshot`, `MetricsStatus`, Gauge-/Service-Modelle). `Status = Literal["green","amber","red"]`, `ServiceStatus` inkl. `unknown`.
- **`backend/app/main.py`** — `MetricsService` an `app.state.metrics`, Router registriert, `_metrics_loop(app)` als Lifespan-Task (Intervall `metrics_poll_interval_seconds`, Default 5 s) neben den bestehenden Loops; defensiv (Tick-Fehler nur geloggt) + sauberes Cancel-Cleanup.
- **`backend/app/config.py`** — neue Settings: `metrics_poll_interval_seconds` (5.0), `metrics_history_points` (60 ≈ 5 min), `metrics_top_processes` (5), `metrics_services` (Liste), `metrics_systemctl_timeout_seconds` (5.0); Schwellen-Konstanten `METRIC_WARN_PCT=75`, `METRIC_CRIT_PCT=90`.
- **`backend/requirements.txt`** — `psutil>=5.9` (im `Dashboard`-Env vorhanden: 5.9.0).

**Bugfix während Build:** `schemas/metrics.py:20` hatte ein straight-`"` innerhalb eines `"..."`-Field-Descriptions-Strings (`„0,2 / 8"`) → `SyntaxError`. Auf typografisches Schlusszeichen `„…“` korrigiert.

**Abweichungen:** keine. Verlauf bewusst nicht persistiert (AC erlaubt Neustart-Reset). `unknown`-Services ampel-neutral statt gelb — bewusst, damit umbenannte/fehlende Units die Gesamt-Ampel nicht verfälschen (deckt Edge Case „systemd-Dienst nicht vorhanden“).

**API-Kontrakt fürs Frontend (/abc-frontend):**
- `GET /metrics/current` → `MetricsSnapshot` (`overall_status`, `cpu/memory/swap/disk/load`, `net`, `uptime_seconds`, `top_processes[]`, `services[]`; je Gauge `history: float[]` für Sparklines).
- `GET /metrics/status` → `{ "status": "green"|"amber"|"red" }` (leichtgewichtig, Sidebar-Ampel).

## Implementation Notes (Frontend — /abc-frontend, 2026-06-25)
**Branch:** dev · **Build:** `npm run build` grün (TypeScript ok), ESLint sauber. Stack: Next.js (native Micro-App nach PROJ-40/41-Muster), kein Plotly — leichte SVG-Gauges/Sparklines.

- **`components/microapps/vps_admin/vps-admin-app.tsx`** — Dashboard nach UI-Baum (Abschnitt A): **StatusBanner** (Gut/Achtung/Kritisch, Farbe + Punkt aus `overall_status`), **GaugeGrid** (CPU/RAM/Disk/Load — SVG-Donut, %-Wert + Sparkline + absolute Werte: „x / y Cores“, „x / y GB“, Load „Ø load1 · Niedrig/Erhöht/Hoch“), **Info-Kacheln** (Uptime „3 T 4 h 12 min“, Netz-I/O rx/tx mit Byte-Skalierung, Swap inkl. „Kein Swap“-Fall), **Top-Prozesse**-Tabelle (Name/PID/CPU%/RAM%), **Service-Health**-Liste (Badge aktiv/inaktiv/fehlerhaft/unbekannt, farbcodiert). Alle Texte deutsch, deutsche Dezimalkomma-Formatierung via `toLocaleString("de-DE")`.
- **Polling**: `GET /metrics/current` alle 5 s, stiller Refresh (kein Spinner-Flackern). Explizite Zustände: Initial-Loading, Error (letzter Stand bleibt sichtbar + „veraltet“-Hinweis im Banner statt Crash), Empty (z. B. keine Prozessdaten/keine Dienste). **Hintergrund-Tab gedrosselt** (`document.hidden` → Tick übersprungen), **`visibilitychange` → sofort frischer Wert** beim Zurückkehren (Edge Case erfüllt).
- **Sparklines**: feste 0..max(100, peak)-Skala → kein „springender“ Graph bei frisch gebootetem VPS / kurzer Historie; < 2 Punkte → leerer, ruhiger Anfangszustand.
- **Sidebar-Ampel** (generisch, nicht auf VPS-Admin verdrahtet):
  - `lib/microapp-status.ts` — Registry `appKey → Status-Fetcher` (Ampelfarbe). Einzige Zeile für VPS-Admin: `vps_admin → GET /metrics/status`. Künftige Apps melden hier eine Zeile an.
  - `components/cockpit/use-microapp-status.tsx` — Hook pollt nur Keys mit registriertem Fetcher (15 s, niederfrequent), unabhängig davon ob die App offen ist; nicht erreichbar → „grau“ (unbekannt) statt veraltet grün.
  - `session-rail.tsx` — rendert `<Ampel size="sm" />` (wiederverwendet, kein neues Widget) rechts am Micro-App-Eintrag, wenn ein Status vorliegt; `microAppEngineKey()` löst `micro:<key>` → `<key>` auf.
- **Registry/Metadaten**: `lib/microapps-registry.ts` (`vps_admin → lazy(...)`), `backend/config/engines.yaml` (`vps_admin`, `kind: native`, `group: micro`, `icon: server`), `server`-Icon in `sidebar-config.ts` ergänzt. Render über den bestehenden native-Zweig in `app/(cockpit)/apps/[key]/page.tsx` (`NativeMicroAppHost`) — Direkt-URL `/apps/vps_admin` funktioniert auch bei ausgeblendeter Sektion (kein verwaister Zustand).
- **Typen/Client**: `lib/types.ts` (`MetricsSnapshot`/`MetricsStatus` + Gauge-/Service-Typen, `MetricStatus ⊂ Ampel`), `lib/api.ts` (`getMetricsCurrent`/`getMetricsStatus`).

**Smoke verifiziert** (Backend-TestClient): `vps_admin` erscheint in `GET /engines`; `/metrics/current` → 200 mit den 4 erwarteten Diensten; `/metrics/status` → 200 Ampel.

**Abweichungen:** keine. Bewertung/Schwellen bleiben vollständig im Backend (eine Quelle der Wahrheit; Banner und Sidebar-Ampel können nicht driften).

## QA Test Results (/abc-qa, 2026-06-25)
**Branch:** dev · **Ergebnis: PRODUCTION-READY ✅** — 0 kritische/hohe/mittlere Bugs.
**Automatisiert:** Backend `pytest` **682 passed** (davon **25** PROJ-42, warnungsfrei) · Frontend `vitest` **169 passed** (167 Bestand + 2 neu) · `npm run build` + ESLint grün.
**Live verifiziert** (echter Host, nicht gemockt): Snapshot + `systemctl`-Service-Health end-to-end.

### Akzeptanzkriterien (14/14 bestanden)
| # | Kriterium | Status | Nachweis |
|---|-----------|--------|----------|
| 1 | Eintrag in Sektion „Micro-Apps" (group:micro, kind:native), Vollbild `/apps/vps_admin` | ✅ | Smoke: in `GET /engines`; native-Zweig `apps/[key]/page.tsx` |
| 2 | Native (kein iFrame fürs Dashboard) | ✅ | `microapps-registry.ts` lazy import, `NativeMicroAppHost` |
| 3 | Status-Banner Gut·Achtung·Kritisch (schlechtester Wert) | ✅ | `BANNER`-Map ↔ Backend `_worst`; Live overall=green |
| 4 | Gauges CPU/RAM/Disk/Load mit % **und** absolut | ✅ | Live: CPU 0,18/8 Cores · RAM 5,56/31,34 GB · Disk 31/386 GB · Load Ø 0,65 „Niedrig" |
| 5 | Verlaufs-Sparkline je Kern-Kennzahl | ✅ | `Sparkline`-SVG; `history`-Felder; Live hist-len wächst |
| 6 | Uptime · Netz-I/O · Swap · Top-Prozesse | ✅ | Live: uptime 448687s · rx/tx ~15 KB/s · swap 0% · top1 python |
| 7 | Service-Health (backend/frontend/webhook/caddy) aktiv·inaktiv·fehlerhaft | ✅ | Live: alle 4 `active`; Tests: failed/inactive/unknown |
| 8 | Sidebar-Ampel (grün/gelb/rot), periodisch | ✅ | generischer Provider `microapp-status.ts` + `useMicroAppStatuses` (15 s) + `<Ampel>` |
| 9 | Schwellen 75/90 %; Load rel. Core-Zahl; Gesamt = schlechtester | ✅ | `_status_for`/`_worst` + 6 Schwellen-Tests |
| 10 | Host-nativ gelesen, Frontend pollt | ✅ | `psutil`+`systemctl`; Worker-Cache; `/current` 5-s-Poll |
| 11 | Loading-/Error-/Empty-Zustände | ✅ | Initial-Loading, „veraltet"-Banner bei Fehler, Empty-Fälle (keine Prozesse/Dienste) |
| 12 | Texte deutsch (Eigenname „VPS-Admin" bleibt) | ✅ | UI + `de-DE`-Formatierung |
| 13 | Sektion ausgeblendet → Direkt-URL bleibt erreichbar | ✅ | `apps/[key]/page.tsx` lädt unabhängig von Sidebar-Prefs |
| 14 | Schwellen-Bewertung im Backend (eine Quelle) | ✅ | Banner + Sidebar lesen denselben `overall_status` → kein Drift |

### Edge Cases (alle abgedeckt)
- **Metrik transient nicht lesbar** → Tick-`try/except` im Lifespan-Loop; letzter Snapshot bleibt, Frontend zeigt „veraltet" statt Crash. ✅
- **systemd-Dienst fehlt/umbenannt** → `unknown`, ampel-neutral (kein falsches Rot). ✅ Test `…unknown_faerbt_ampel_nicht`.
- **`systemctl` hängt** → Timeout → `unknown`, Prozess gekillt; Tick blockiert nie. ✅ neuer Test `…timeout_degradiert_zu_unknown`.
- **Übergangszustände** (activating/reloading→active, deactivating→inactive). ✅ neuer parametrisierter Mapping-Test.
- **Load Single- vs. Many-Core** → Bewertung über `per_core`. ✅
- **Frisch gebootet / kurze Historie** → Sparkline < 2 Punkte = ruhiger Leerzustand, feste 0..max-Skala (kein Springen). ✅
- **Hintergrund-Tab** → Polling gedrosselt (`document.hidden`), sofortiger Refresh bei `visibilitychange`. ✅
- **Sidebar-Ampel ohne offene App** → eigener 15-s-Poll auf leichtem `/metrics/status` (gecacht). ✅
- **Backend-Neustart** → In-Memory-Verlauf beginnt neu (vom AC erlaubt). ✅

### Security-Audit (Red-Team)
- **Read-only**: keine Schreib-/Mutationspfade → minimale Angriffsfläche. ✅
- **Command-Injection**: `systemctl is-active <unit>` über `create_subprocess_exec` mit **fester Argumentliste**, keine Shell-Interpolation, Units serverseitig konfiguriert (kein Client-Einfluss). ✅
- **XSS**: Prozess-/Dienstnamen als React-Textknoten gerendert (auto-escaped), kein `dangerouslySetInnerHTML`. ✅
- **Kein SQL/keine DB** → keine SQLi/Tenant-Leaks im Scope. ✅
- **Kein Auth (MVP)**: bewusste Projekt-Entscheidung (single-user hinter Tailscale, [[jupiter-stack-overrides]]). `/metrics/*` legt Host-Infos + Prozessliste offen — akzeptabel im MVP-Scope, mit echtem Auth (PROJ-25) später abzusichern. **Informativ, kein Bug.**

### Beobachtungen (Low / informativ, nicht blockierend)
- **L1 (Low):** `_systemctl_is_active` killt einen hängenden Subprozess beim Timeout, ruft aber kein `await proc.wait()` — in der Praxis vom Event-Loop-Child-Watcher abgeräumt; bei Dauer-Timeouts theoretisch Zombie-Risiko. Kein Funktionsfehler.
- **L2 (Info):** Kein Auth auf `/metrics/*` — by design (siehe oben), Wiedervorlage mit PROJ-25.

### Regression
- Full Backend-Suite (682) + Frontend-Suite (169) grün. Geänderte geteilte Komponente `session-rail.tsx` (Ampel-Zusatz) ohne Bestands-Bruch; Build/Lint grün.

### Neue/erweiterte Tests
- `backend/tests/test_proj42_metrics.py`: +`inactive→mind. amber`, +`systemctl`-Mapping (8 Fälle inkl. Übergänge/leer), +Timeout→unknown (25 gesamt).
- `nextjs_app/lib/sidebar-config.test.ts`: +Round-Trip `microAppItemKey`↔`microAppEngineKey` (Sidebar-Ampel-Auflösung).

**Empfehlung:** Approve → bereit für `/abc-deploy`. **Deploy-Hinweis:** Live-`engines.yaml` (gitignored) trägt den `vps_admin`-Eintrag bereits; auf dem Prod-VPS muss er ebenfalls vorhanden sein (committed nur `engines.example.yaml`).

## Deployment
- **Production URL:** https://jupiter.auxevo.tech (Route `/apps/vps_admin`)
- **Deployed:** 2026-06-25 · **Version:** 0.15.0 · **Tag:** v0.15.0
- **Host:** Dev-VPS host-native (systemd `jupiter-backend`/`jupiter-frontend` + Caddy TLS), Auto-Deploy via GitHub-Webhook auf `main` ([[jupiter-deployment]]).
- **Geshippt:** native Micro-App VPS-Admin — Backend-Metrik-Worker (`/metrics/current` + `/metrics/status`, `psutil` + `systemctl`-Service-Health) + Frontend-Dashboard (Gauges/Sparklines/Top-Prozesse/Service-Health) + generische Sidebar-Ampel.
- **Hinweis:** Prod-`engines.yaml` (gitignored) trägt den `vps_admin`-Eintrag bereits (überlebt `git reset --hard`); `requirements.txt` führt `psutil>=5.9` (im Env vorhanden).
- **Browser-Smoke (nach SW-Hard-Refresh):** Kachel „VPS-Admin" in Sidebar-Sektion Micro-Apps, Gauges/Live-Werte, Sidebar-Ampel, Direkt-URL `/apps/vps_admin`.
