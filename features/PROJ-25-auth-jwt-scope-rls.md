# PROJ-25: Echtes Auth (JWT) + Scope/RLS auf `owner`

## Status: In Progress
**Created:** 2026-06-23
**Last Updated:** 2026-06-25
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

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
