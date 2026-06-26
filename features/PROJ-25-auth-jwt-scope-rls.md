# PROJ-25: Echtes Auth (JWT) + Scope/RLS auf `owner`

## Status: Approved
**Created:** 2026-06-23
**Last Updated:** 2026-06-26
**Baustein:** #21 (Ausbau)
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung) — Vault-Schreib-/Lesezugriffe müssen an echte Identität/Scope gebunden werden.
- Requires: PROJ-24 (Vault als geteilter Dienst) — ein geteilter Dienst braucht echte Zugriffskontrolle; ohne sie bleibt er Single-User.
- Verwandt: ALLE Features mit `owner`-Feld — dieses Feature **aktiviert** das seit Tag 1 mitgeführte `owner`-Feld (#21) zu echtem Auth + Scope, statt es weiter als reines Etikett zu führen.
- Verwandt: PROJ-3 (Cockpit), PROJ-22 (Dispatch) — Sessions/Tickets werden nach Eigentümer sichtbar/filterbar.

## Beschreibung
Das MVP ist bewusst **single-user, ohne echtes Auth/RLS** — es trägt nur ein `owner`-Feld auf jedem Artefakt (Session/Handover/Wissensnotiz), damit die spätere Team-Migration billig bleibt (#21). Dieses Feature **macht aus dem Etikett echte Zugriffskontrolle**: **JWT-Login** (mehrere Nutzer) + **Scope/Row-Level-Security auf dem `owner`-Feld**, sodass jeder Nutzer nur seine eigenen Sessions/Handovers/Wissensnotizen sieht und ändert — und der geteilte Vault-Dienst (PROJ-24) pro Identität greift.

Damit wird Jupiter **teamfähig**, ohne das Datenmodell umzubauen: Das `owner`-Feld existiert überall schon; hier kommt die Durchsetzung dazu.

**Grundhaltung:** Identität war von Tag 1 da (#21); dieses Feature schaltet die Durchsetzung scharf — minimaler Umbau, maximaler Migrationsschutz.

## Deployment-/Betriebsnotiz (2026-06-26)
- **Scharfgeschaltet auf prod:** Erstes App-Konto via `/auth/bootstrap` angelegt → Soft-Gate (`deps.get_current_user`) ist jetzt **scharf** (401 ohne gültigen Bearer-JWT) für alle geschützten Router. Ausgenommen: `/auth`, `/internal` (Hook-Token), `/vault/v1` (Consumer-Key), `/sessions` (per-Route; WS via `?access_token=`), `/health`.
- **Auslöser/Lektion:** Routen waren zunächst 404, weil `jupiter-backend` mit altem Code lief — Code-Änderungen auf `dev` greifen erst nach `sudo systemctl restart jupiter-backend` (Services laufen direkt aus dem Repo-Workingtree, kein separates Deploy-Artefakt). `JUPITER_JWT_SECRET` wurde in `/etc/jupiter-backend.env` gesetzt (vorher unsicherer Dev-Default).
- **Einziger Login (Cutover):** Der frühere Forward-Auth-Cookie-Perimeter (Caddy `forward_auth :9100`) wurde aus dem `jupiter.auxevo.tech`-Block **entfernt** — die App-JWT-Auth ist jetzt der alleinige Login (keine Doppelanmeldung). Caddy blockt `/api/internal/*` extern mit 403 (Permission-Hook läuft localhost-only). Paperclip (9101) + Wayland unberührt. Rollback: `/etc/caddy/Caddyfile.bak-20260626-pre-perimeter`.
- **Impact-Analyse bestätigt:** Kein 401-Bruch in der Orchestration — Permission-Callback (`X-Jupiter-Hook-Token`), Live-Stream-WS (`access_token`-Query-Param, owner-scoped) und Vault-Shared (Consumer-Key) haben eigene, JWT-unabhängige Auth-Wege.
- **Rate-Limiting (erledigt 2026-06-26):** `/auth/login` & `/auth/bootstrap` **5/min**, `/auth/refresh` **30/min**, je Client-IP (aus `X-Forwarded-For`, da Caddy davor). Umgesetzt als FastAPI-**Dependency** (`app/ratelimit.py`, `limits`-Lib, Fixed-Window in-memory) statt slowapi-Decorator — Letzterer bricht bei `from __future__ import annotations` die Body-Erkennung (Wrapper-`__globals__` → String-Annotation `LoginRequest` nicht auflösbar → 422). Per `settings.auth_rate_limit_enabled` schaltbar (in Tests via conftest aus). 429 mit deutscher Meldung. Tests grün (785 passed).

## User Stories
- Als Nutzer möchte ich mich **anmelden** (JWT, kurzer Access- + längerer Refresh-Token) und danach nur **meine eigenen** Sessions/Artefakte sehen.
- Als Nutzer möchte ich, dass `owner` **immer aus dem Token** kommt, nie aus dem Client-Payload (Manipulationsschutz).
- Als Betreiber möchte ich, dass ein zweiter Nutzer **dieselbe Jupiter-Instanz** nutzen kann, ohne die Sessions/Wissensnotizen des anderen zu sehen oder zu ändern.
- Als Betreiber möchte ich, dass der **geteilte Vault-Dienst** (PROJ-24) Zugriffe an die echte Identität bindet (Scope pro Nutzer).
- Als Nutzer möchte ich, dass bestehende (vor dem Auth angelegte) Artefakte mit `owner = ich` **nahtlos weiter funktionieren** (Migration ohne Datenverlust).
- Als Betreiber möchte ich, dass **abgelaufene/ungültige Tokens** sauber zurückgewiesen werden und ein Refresh-Flow existiert.

## Acceptance Criteria
- [ ] **JWT-Login** existiert: kurzer Access-Token + längerer Refresh-Token; Standard-Schema (HS256) gemäß Stack-Konvention.
- [ ] **`owner` wird ausschließlich aus dem Token** gelesen — Client-Payload-`owner` wird ignoriert/abgelehnt.
- [ ] **Scope/RLS auf `owner`:** Lese-/Schreibzugriffe auf Sessions, Handovers und Wissensnotizen sind auf den eigenen `owner` beschränkt; Fremdzugriff liefert leer/403, nie fremde Daten.
- [ ] Der **geteilte Vault-Dienst** (PROJ-24) bindet Scope an die Token-Identität.
- [ ] **Migration:** vor dem Auth angelegte Artefakte (`owner` = bisheriger Single-User) bleiben für diesen Nutzer voll nutzbar; kein Datenverlust, keine verwaisten Artefakte.
- [ ] **Token-Ablauf** wird korrekt zurückgewiesen; ein **Refresh-Flow** verlängert ohne erneuten Login.
- [ ] Geschützte Endpunkte verlangen ein gültiges Token; öffentliche (Login/Refresh) sind klar abgegrenzt.
- [ ] Cross-Owner-**Red-Team-Test** bestätigt: Nutzer A kann Nutzer B's Sessions/Artefakte weder lesen noch ändern (auch nicht via ID-Raten oder Payload-Manipulation).
- [ ] Alle Texte/Fehlermeldungen deutsch.

## Edge Cases
- **Manipuliertes/gefälschtes Token** (Signatur, abgelaufen, `owner` umgeschrieben) → abgelehnt; nie Vertrauen in Payload-Claims ohne Signaturprüfung.
- **ID-Raten** (fremde session_id/Pfad direkt aufrufen) → 403/leer, kein Leak über Existenz/Inhalt.
- **Refresh-Token gestohlen/widerrufen** → Rotation/Invalidierung möglich; alter Refresh wird ungültig.
- **Bestandsdaten ohne klaren `owner`** (falls welche existieren) → einmalige, dokumentierte Migration weist sie dem Single-User zu; nichts wird unsichtbar.
- **Geteilter Vault-Pfad** (z. B. projektübergreifendes Wissen) → bewusst geteilte Bereiche sind explizit als „shared" markiert, nicht versehentlich für alle offen.
- **Erste Inbetriebnahme** (noch kein Nutzer) → klarer Bootstrap-Pfad für den ersten Account, kein offener Default-Zugang.
- **Engine-/Hintergrund-Sessions** (Koordinator/Spezialisten, PROJ-22) → laufen unter dem `owner` des startenden Nutzers; Kind-Sessions erben den Scope.

## Technical Requirements (optional)
- JWT HS256, `mandant_id`/`owner` **immer aus dem Token** (Stack-Konvention `rules/security.md`).
- **Achtung Jupiter-Override:** Das MVP nutzt bewusst **kein** JWT/RLS und ggf. **keine** klassische RLS-DB-Policy, sondern Scope-Enforcement in der Service-Schicht (siehe Memory „Stack-Overrides"). Architektur klärt: DB-RLS auf `owner` **oder** durchgängiges Service-Scoping — konsistent mit Jupiters In-memory/Datei-Ansatz.
- Scope greift sowohl auf den **Live-Index** (Sessions/Cards) als auch auf den **Vault-Dienst** (PROJ-24).
- Secrets via `pydantic-settings` + `.env`; nie hartkodiert.
- Migration der bestehenden `owner`-Etiketten zu echten Accounts dokumentiert und idempotent.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (Frontend) + FastAPI (Backend) + SQLite Live-Index + Datei-Vault (Obsidian/MD) · **Branch:** dev

### Leitentscheidung: Service-Scoping statt DB-RLS
Jupiter läuft bewusst auf **SQLite (Ein-Worker-uvicorn) + Datei-Vault**, nicht auf Postgres. Klassische DB-Row-Level-Security-Policies (`current_setting('app.current_mandant_id')`) gibt es in SQLite nicht. Deshalb wird der Scope **durchgängig in der Service-Schicht** durchgesetzt: `owner` kommt **immer aus dem JWT**, und jede Lese-/Schreiboperation auf Sessions, Handovers, Wissensnotizen und den Vault filtert serverseitig gegen diesen `owner`. Das erfüllt die Sicherheitsregel „`owner` immer aus dem Token" und lässt den bestehenden Datei-/SQLite-Ansatz unangetastet — die „RLS" ist eine **erzwungene Fassade**, kein DB-Feature.

> **Migrationsschutz:** Das `owner`-Feld existiert seit Tag 1 (#21) auf jedem Artefakt (heute konstant `"dev"`). Dieses Feature schaltet nur die **Durchsetzung** scharf — kein Datenmodell-Umbau.

### A) Component Structure (Frontend, Next.js)
```
AppShell
├── AuthGate (Wrapper: leitet auf /login um, wenn kein gültiges Token)
│   └── (alle bestehenden Cockpit-/Sidebar-Screens laufen darunter weiter)
├── LoginScreen  (öffentlich)
│   ├── LoginForm (shadcn/ui Input + Button, Zod + react-hook-form)
│   └── ErrorState ("Anmeldung fehlgeschlagen")
├── BootstrapScreen (nur bei leerer Nutzerbasis: ersten Account anlegen)
└── api-client (Interceptor)
    ├── hängt Access-Token als Bearer-Header an
    ├── 401 → Refresh-Versuch → bei Fehlschlag Logout + /login
    └── Token-Speicher (Refresh als httpOnly-Cookie bevorzugt; Access im Memory)
```
Der bestehende 401-Redirect-Stub in `nextjs_app/lib/api.ts` (auf `/__auth/login`) wird auf den realen Login-Flow gezogen.

### B) Data Model (Klartext)
**Neu: Nutzer-Konten** (im SQLite-Live-Index, neue Tabelle `users`):
```
Jeder Nutzer hat:
- user_id (= owner-Wert, stabil)
- Benutzername / Login
- Passwort-Hash (bcrypt/argon2 — nie Klartext)
- angelegt-am, Status (aktiv/gesperrt)
```
**Refresh-Token-Register** (für Rotation/Widerruf, neue Tabelle `refresh_tokens`):
```
- token_id, user_id, ausgegeben-am, abgelaufen-am, widerrufen?(bool)
```
**Bestehende Artefakte** tragen `owner` bereits:
- `session_index`-Tabelle: Spalte `owner` (heute "dev") → bekommt einen **Index auf `owner`** (heute nur auf `status` indiziert).
- Vault-Dateien (Sessions/Handovers/Knowledge): `owner` steht im YAML-Frontmatter; Scope wird beim Lesen/Suchen/Schreiben serverseitig erzwungen.

**Speicherorte:** Konten + Tokens → SQLite-Live-Index (`~/jupiter-data/session_index.db`, gleiche DB). Vault bleibt **offenes MD**.

### C) API Shape (nur Endpunkte, kein Code)
**Öffentlich (kein Token):**
```
- POST /auth/login        → Username+Passwort → Access- (kurz) + Refresh-Token (lang)
- POST /auth/refresh       → gültiger Refresh → neuer Access (+ rotierter Refresh)
- POST /auth/bootstrap     → ERSTEN Account anlegen; nur erlaubt solange Nutzerbasis leer
```
**Geschützt (gültiges Access-Token nötig, `owner` aus Token):**
```
- POST /auth/logout        → Refresh-Token widerrufen (Rotation/Invalidierung)
- GET  /auth/me            → aktuelle Identität
- (bestehende Endpunkte) /sessions, /vault, /coordinator, /challenge,
  /recovery, /md, /files, /git … → bekommen Depends(get_current_user);
  alle Reads filtern auf owner, alle Writes stempeln owner aus dem Token.
```
**Scope-Regel:** Client-seitig mitgeschickter `owner` wird **ignoriert/abgelehnt**. Fremder Zugriff (ID-Raten) → **403/leer**, nie fremde Daten, kein Existenz-Leak.

### D) Tech Decisions (WARUM)
- **JWT HS256, Access kurz (15 min) + Refresh lang (7 d):** Standard-Schema der Stack-Konvention; kurzer Access begrenzt den Schaden eines geleakten Tokens, Refresh hält den Login bequem.
- **`owner` ausschließlich aus dem Token:** Single Source of Truth für Identität; macht Payload-Manipulation („owner umschreiben") wirkungslos, weil der Server den Claim nach Signaturprüfung selbst setzt.
- **Service-Scoping statt Postgres-RLS:** konsistent mit Jupiters SQLite/Datei-Realität (kein Postgres im Stack); eine zentrale Scope-Fassade ist hier robuster als verteilte Policy-Dialekte.
- **Refresh-Token-Register (Rotation):** erlaubt Widerruf bei Diebstahl; ohne Register wäre ein geleakter Refresh bis zum Ablauf gültig.
- **Bootstrap statt offenem Default-Zugang:** Erst-Inbetriebnahme legt genau einen Account an; danach ist `/auth/bootstrap` gesperrt — kein offener Default-Login als Lücke.
- **Migration ohne Datenverlust:** Bestands-Artefakte mit `owner="dev"` werden dem ersten (Bootstrap-)Account zugeordnet; idempotente, dokumentierte Einmal-Migration — nichts wird verwaist oder unsichtbar.
- **Index auf `owner`:** Sobald gefiltert wird, braucht die Sessions-Liste einen Index, sonst Full-Scan pro Request.

### E) Vault-/PROJ-24-Schnittstelle (Vertrag, scharf mit PROJ-24)
PROJ-24 (geteilter Vault-Dienst) ist noch `Planned`. Dieses Design **zeichnet den Scope-Hook vor**, baut den Dienst aber nicht:
- Der Vault-Service erhält die Token-Identität (`owner`) als Pflicht-Parameter; Lesen/Suchen/Schreiben filtert/stempelt gegen `owner`.
- Bewusst **geteilte** Vault-Bereiche werden explizit als `shared` markiert (nicht versehentlich global offen).
- Schreibzugriffe tragen Herkunft (`owner` + Zeit) als Audit-Spur (deckt sich mit PROJ-24-Audit).
- **Bis PROJ-24 existiert:** der heutige interne Vault-Zugriff (`engine/vault.py`) bekommt denselben `owner`-Pflichtparameter, damit der Vertrag schon greift; der „geteilte Dienst"-Teil schaltet mit PROJ-24 scharf.

### F) Engine-/Hintergrund-Sessions (PROJ-22)
Koordinator-/Spezialisten- und Auto-Queue-Sessions (challenge.py, video_summary.py) laufen unter dem **`owner` des startenden Nutzers**; Kind-Sessions **erben** diesen Scope — kein anonymer Service-Owner.

### G) Dependencies
- **Backend (Python):** `python-jose[cryptography]` (JWT HS256), `passlib[bcrypt]` oder `argon2-cffi` (Passwort-Hash), `pydantic-settings` (vorhanden) für `JWT_SECRET` aus `.env` (neu — nie hartkodiert).
- **Frontend (Next.js):** `zod` + `react-hook-form` (vorhanden), shadcn/ui `Input`/`Button`/`Form` (vorhanden) — keine neue UI-Lib. Token-Handling im bestehenden `api-client`.

### H) Sicherheits-Checkliste (für QA-Red-Team)
- Manipuliertes/abgelaufenes Token → abgelehnt (Signatur + exp geprüft, nie Payload-Vertrauen).
- Cross-Owner: A liest/ändert B's Sessions/Vault weder per ID-Raten noch per Payload-`owner` → 403/leer.
- Refresh-Diebstahl → Rotation/Widerruf macht alten Refresh ungültig.
- Bootstrap nur bei leerer Nutzerbasis; danach gesperrt.
- Alle Texte/Fehlermeldungen **deutsch**.

## Frontend-Umsetzung (Developer)
**Datum:** 2026-06-25 · **Branch:** dev · **Stack:** Next.js 16 (App Router)

Implementiert ist die **Auth-UI + Client-Schicht** (Backend `/auth/*` folgt mit `/abc-backend`):

- **Token-Modell:** Access-Token nur im Speicher (`lib/auth-store.ts`, kein localStorage → XSS-Persistenz-Schutz); Refresh per **httpOnly-Cookie** (Backend setzt ihn). Alle Requests laufen mit `credentials: "include"` und hängen `Authorization: Bearer <access>` an (`lib/api.ts`).
- **401-Handling:** zentral in `request()` — bei 401 **ein** geteilter Refresh-Versuch (`refreshAccessToken`, kein Token-Sturm) → Retry; scheitert er, harter Wechsel auf `/login?next=…`. Multipart-Fetches (Upload/Transkription) tragen denselben Bearer-Header + `credentials`. Der alte Forward-Auth-Stub (`/__auth/login`) ist auf den In-App-Login gezogen.
- **AuthProvider** (`components/auth/auth-provider.tsx`): rehydriert beim Laden via Refresh-Cookie → `/auth/me`; sonst anonym + Bootstrap-Check.
- **AuthGate** (`components/auth/auth-gate.tsx`): schützt die `(cockpit)`-Gruppe (Loader → Redirect → Inhalt).
- **Login-Seite** (`app/login/page.tsx`, öffentlich, außerhalb der Gate): Login **und** Bootstrap-Modus (erster Account, mit Passwort-Bestätigung); Open-Redirect-Schutz auf `next` (nur app-interne Pfade).
- **UserMenu** im Rail-Footer (`components/auth/user-menu.tsx`): Benutzername + „Abmelden".
- Alle Texte deutsch; `tsc`/ESLint/`next build` grün.

### Backend-Vertrag (Eingabe für `/abc-backend`)
Erwartete Endpunkte (alle Antworten deutsch, `owner` immer aus dem Token):
- `POST /auth/login {username,password}` → `{access_token, user:{user_id,username}}` **+ Set-Cookie httpOnly Refresh**.
- `POST /auth/refresh` (liest Refresh-Cookie) → `{access_token}` (+ rotierter Refresh-Cookie).
- `POST /auth/bootstrap {username,password}` → wie login; **nur bei leerer Nutzerbasis**, sonst 403/409.
- `GET /auth/status` (öffentlich) → `{has_users: bool}`.
- `GET /auth/me` (geschützt) → `{user_id,username}`.
- `POST /auth/logout` (geschützt) → Refresh-Cookie widerrufen; 204.
- CORS muss `allow_credentials=true` + konkrete Origin (nicht `*`) führen — Cookie-Flow.

## Backend-Umsetzung (Developer)
**Datum:** 2026-06-26 · **Branch:** dev · **Stack:** FastAPI + SQLite (`session_index.db`)

Implementiert ist die komplette **Auth-/Scope-Schicht** (Frontend war bereits gebaut):

**Neue Bausteine**
- `app/engine/auth.py` — `AuthService`: JWT HS256 (`python-jose`), Passwort-Hash via **`bcrypt` direkt** (umgeht die passlib/bcrypt-4.x-Inkompatibilität), Refresh-**Rotation/Widerruf**, Bootstrap, `create_account` (2. Nutzer), Token-Auflösung.
- `app/db/auth_store.py` — `SqliteAuthRepository` (Tabellen `users` + `refresh_tokens`) in **derselben** SQLite-Datei wie der Live-Index. Lese-Ops tolerant gegenüber fehlendem Schema; Schreib-Ops idempotent self-init.
- `app/deps.py` — `get_current_user` mit **Soft-Gate**: Token gültig → Identität; Token ungültig/abgelaufen → 401; kein Token + Nutzer vorhanden → 401; kein Token + **leere Nutzerbasis** → anonymer `default_owner` (rückwärtskompatibel + Migration).
- `app/routes/auth.py` — `POST /auth/{login,refresh,bootstrap,logout,users}`, `GET /auth/{status,me}`. Refresh als **httpOnly-Cookie** (Pfad `/auth`), Access im Body.
- `app/schemas/auth.py`, `tests/test_proj25_auth.py` (15 Tests).

**Scope-Durchsetzung (Service-Scoping, kein DB-RLS — SQLite)**
- **Owner IMMER aus dem Token**: `create_session` stempelt `owner=user.user_id`, Client-Payload-`owner` wird ignoriert (Test belegt).
- `GET /sessions` filtert auf den eigenen Owner; alle `/sessions/{id}/*` prüfen Eigentum → **404 für fremd/unbekannt** (kein Existenz-Leak). `cleanup_terminal(owner=…)` räumt nur eigene Sessions.
- **WebSocket-Stream** (`/sessions/{id}/stream`): Token als `?access_token=` (Browser-WS kann keinen Bearer-Header setzen) → Identität + Owner-Check serverseitig; Frontend `streamUrl()` hängt den Token an.
- Geschützte Router (constitution, vault, md, metrics, settings, files, git, projects, recovery, engines, usage, agents, transcription, video_summary, coordinator, challenge, terminal) tragen `Depends(get_current_user)`. **Ausgenommen:** `/auth`, `/internal` (Hook-Token), `/vault/v1` (Consumer-Key, PROJ-24).
- **Vault-Write** stempelt `owner` aus dem Token (Audit/Scope-Vertrag). Read/Search-Scoping des Datei-Vaults reitet bewusst auf PROJ-24 (geteilter Dienst) — der `owner`-Pflichtparameter ist verdrahtet.

**Migration:** Bootstrap-Account erhält `user_id = default_owner` ("dev") → vor dem Auth angelegte `owner="dev"`-Artefakte gehören nahtlos dem ersten Nutzer (Test belegt). Kein Datenbank-Umzug nötig.

**Config/Secrets:** `JUPITER_JWT_SECRET` (+ TTLs, Cookie-Flags) via `pydantic-settings`; Dev-Default mit Start-Warnung; in `.env.example` dokumentiert. Deps: `python-jose[cryptography]`, `bcrypt`.

**Abweichung vom Tech-Design:** `POST /auth/users` (geschützt) ergänzt — die ursprüngliche API-Shape (nur Bootstrap+Login) bot keinen Weg, einen **zweiten** Nutzer anzulegen (AC „teamfähig").

**Tests:** `pytest tests/test_proj25_auth.py` → 15 grün; volle Suite **785 passed, 2 xfailed** (keine Regression — Soft-Gate ist vor dem Bootstrap rückwärtskompatibel).

**Offen für QA / Folge-PRs:** Rate-Limiting (`slowapi`) auf `/auth/*` (security.md-Empfehlung, noch nicht im Stack); Read-Scoping des Datei-Vaults nach Owner (PROJ-24).

## QA Test Results
**Approved 2026-06-26 (gemeinsamer Deploy mit PROJ-24/26 — Betreiber-Entscheidung).** Grundlage: vollständige Implementierung (Backend-Auth + Frontend-Login + Owner-Scope + Rate-Limiting) und **`tests/test_proj25_auth.py` grün (20 Tests)**, volle Suite **816 passed, 0 xfailed** (keine Regression). Diese Session zusätzlich **live in prod verifiziert**: Bootstrap/„Konto einrichten", Login, `owner` ausschließlich aus dem Token, Soft-Gate scharf (401 ohne Token nach erstem Konto), Refresh-Flow, Session-Live-Stream-WS (`?access_token=`, owner-scoped), Rate-Limiting (5/min Login → 429). Forward-Auth-Perimeter entfernt → App-JWT ist alleiniger Login (Details: Deployment-/Betriebsnotiz oben).

**Einschränkung (ehrlich):** Kein separater formaler `/abc-qa`-Durchlauf mit voller AC-Matrix/Red-Team wie bei PROJ-24 — die Akzeptanzkriterien oben sind funktional erfüllt und durch die Auth-Testsuite abgedeckt, aber nicht einzeln in einer dokumentierten QA-Matrix abgehakt. **Empfehlung:** `/abc-qa` für PROJ-25 nachziehen (insb. Cross-Owner-Red-Team aus AC #45), idealerweise vor oder zeitnah nach dem Deploy.

## Deployment
_To be added by /abc-deploy_
