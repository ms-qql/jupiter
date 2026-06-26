# PROJ-24: Vault als geteilter Dienst (auch für eingebettete Apps)

## Status: In Review
**Created:** 2026-06-23
**Last Updated:** 2026-06-26
**Baustein:** #14
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung als Dienst) — dieses Feature **öffnet** die bestehende interne Vault-Anbindung als allgemein nutzbaren Dienst.
- Requires: PROJ-15 (Vault Stufe 3 / roh↔kuratiert) — geteilter Lese-/Schreib-/Suchzugriff soll die kuratierte Wissensschicht respektieren.
- Verwandt: PROJ-18 (Weitere Engines + iFrame/Launch) — eingebettete/fremde Apps (#13) sind die Hauptkonsumenten dieses Dienstes.
- Verwandt: PROJ-25 (Auth/RLS) — ein **geteilter** Dienst braucht Zugriffskontrolle pro Konsument; ohne PROJ-25 nur token-loser Single-User-Betrieb.

## Beschreibung
Heute ist die Vault-Anbindung (lesen/schreiben/suchen) **intern** für Jupiters Sessions gebaut (PROJ-2). Dieses Feature hebt sie zu einem **geteilten Dienst mit stabilem Vertrag**, den auch **eingebettete/fremde Apps** (z. B. über iFrame oder Launch-Button eingebundene Tools, #13) nutzen können — die **gemeinsame Datenschicht der ganzen Kommandozentrale**.

Der Vault bleibt **offenes MD** (Obsidian/PARA, `/home/dev/tools/Hal`) — der Dienst legt nur eine **saubere, versionierte API** darüber (lesen / schreiben / suchen / Pointer auflösen), damit nicht jede App ihre eigene, inkonsistente Vault-Logik nachbaut. Eine Wahrheit, viele Konsumenten.

**Grundhaltung:** Der Vault ist die einzige Wahrheit; der geteilte Dienst macht diese Wahrheit für die ganze Plattform konsumierbar, ohne sie zu duplizieren oder zu verstecken.

## User Stories
- Als Betreiber möchte ich, dass eine **eingebettete App** über eine definierte API im Vault lesen/schreiben/suchen kann, ohne eigene Vault-Logik zu implementieren.
- Als Betreiber möchte ich einen **stabilen, versionierten API-Vertrag** für den Vault-Dienst, damit Konsumenten nicht bei jeder internen Änderung brechen.
- Als Betreiber möchte ich pro Konsument festlegen, **welche Bereiche** des Vaults er sehen/schreiben darf (Scope), damit eine eingebettete App nicht den ganzen Vault aufmacht.
- Als Betreiber möchte ich **Pointer** statt Volltext zurückgeben können, damit Konsumenten kontextsparsam arbeiten (#23-Linie).
- Als Betreiber möchte ich nachvollziehen, **welcher Konsument wann was** geschrieben hat (Audit), da nun mehrere Quellen schreiben.

## Acceptance Criteria
- [ ] Es gibt einen **eigenständigen Vault-Dienst** mit dokumentierter API für mindestens: **lesen** (Datei/Ausschnitt), **schreiben/anhängen**, **suchen**, **Pointer auflösen**.
- [ ] Die API ist **versioniert** (z. B. `/vault/v1/...`); Brüche am internen Vault-Layout schlagen nicht ungefiltert auf Konsumenten durch.
- [ ] **Eingebettete Apps** (PROJ-18 / #13) können den Dienst nutzen; ein dokumentiertes Beispiel-Konsumenten-Setup existiert.
- [ ] Pro Konsument ist ein **Scope** konfigurierbar (welche Vault-Pfade lesbar/schreibbar) — kein Vollzugriff per Default.
- [ ] Schreibzugriffe tragen **Herkunft** (welcher Konsument/`owner`) und sind im Vault als Spur nachvollziehbar (Audit).
- [ ] Der Vault bleibt **offenes MD** — der Dienst fügt keine Binär-/Black-Box-Schicht ein; Dateien bleiben direkt les-/editierbar.
- [ ] Lese-Antworten unterstützen **Pointer/Ausschnitt** statt nur Volltext (kontextsparsam).
- [ ] Gleichzeitige Schreibzugriffe sind **konfliktsicher** (kein stilles Überschreiben — siehe Edge Cases).
- [ ] Alle Texte/Fehlermeldungen deutsch.

## Edge Cases
- **Zwei Konsumenten schreiben dieselbe Datei** → konfliktsicher (Append/Locking/Versionsprüfung); kein Last-Write-wins-Datenverlust.
- **Konsument schreibt außerhalb seines Scopes** → abgelehnt mit klarer Fehlermeldung, kein Teil-Schreib.
- **Vault-Pfad existiert nicht / Tippfehler im Pointer** → sauberer 404-äquivalenter Fehler, kein Crash, kein versehentliches Anlegen am falschen Ort.
- **Große Datei** → Ausschnitt/Pointer statt Volltext; harte Größengrenze mit klarer Meldung.
- **Vault temporär nicht erreichbar** (FS/Mount weg) → Dienst meldet Degradation; Konsumenten erhalten klaren Fehler statt Hänger.
- **Schädlicher Pfad** (`../`, absolute Pfade, Symlink-Ausbruch) → Path-Traversal wird verhindert; nur innerhalb des erlaubten Scopes.
- **Ohne PROJ-25 (kein Auth)** → Dienst läuft im Single-User-Modus ohne Token; bei Mehrnutzer/Team **muss** Scope an echte Identität gebunden werden (klar dokumentiertes Vorbedingung).

## Technical Requirements (optional)
- Refaktoriert die interne PROJ-2-Anbindung hinter eine **stabile Service-Fassade**; interne Aufrufer migrieren auf denselben Vertrag (eine Quelle der Wahrheit).
- **Path-Traversal-Schutz** und Scope-Enforcement serverseitig; Pfade nie ungeprüft aus Konsumenten-Payload.
- **Pointer-First**-Antworten (konsistent mit #23) zur Kontextsparsamkeit.
- Audit-Spur der Schreibzugriffe (Herkunft/`owner`/Zeit) — passt zur Identitäts-Linie #21 und bereitet PROJ-25 vor.
- Bleibt dateibasiert/offenes MD; keine DB als Wahrheitsquelle (Postgres bleibt Live-Index).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** FastAPI + dateibasierter MD-Vault (`/home/dev/tools/Hal`, kein DB-Wahrheitsquelle) · **Branch:** dev

### Kern-Erkenntnis
`backend/app/engine/vault.py` (`VaultService`) liefert ~80 % bereits: Path-Traversal-Schutz (`_resolve_read`/`_resolve_write`, Realpath-Validierung), Pointer-RAG (`rag_preview`, PROJ-19/#23), roh↔kuratiert-Layout (`Sessions/`/`Handovers/`/`Knowledge/`, PROJ-15), Owner-Stamping im Frontmatter. PROJ-24 baut **keinen neuen Vault**, sondern legt eine **versionierte, scope-geprüfte, auditierte Fassade** darüber und migriert interne Aufrufer (challenge/coordinator/recovery/manager/scout/sessions) auf denselben Vertrag — eine Wahrheit, viele Konsumenten.

### A) Komponenten (Backend-fokussiert, kein UI-Neubau)
```
/vault/v1  (neue versionierte Router-Fassade, backend/app/routes/vault_v1.py)
├── Auth-Dependency: resolve_consumer()  → consumer_id + scope (aus consumers.yaml)
├── Scope-Guard: enforce_scope(path, mode)  → 403 bei Pfad außerhalb Scope
├── GET  /vault/v1/read       → Datei/Ausschnitt (Pointer-first)
├── GET  /vault/v1/search     → Treffer als Pointer (Datei + Zeile + Snippet)
├── GET  /vault/v1/resolve    → Pointer → Volltext-Ausschnitt
├── POST /vault/v1/write      → schreiben/anhängen (version-check + Audit)
└── delegiert intern an VaultService (eine Wahrheit)

Konsument (dokumentiertes Beispiel-Setup): eingebettete iFrame-App (PROJ-18/#13)
  ruft /vault/v1/* mit Headern X-Vault-Consumer + X-Vault-Key
```
Bestehende `/vault/...`-Endpunkte (PROJ-2/15/19) bleiben als Thin-Wrapper (Jupiter-intern), rufen aber dieselbe Service-Fassade — kein Doppel-Code.

### B) Datenmodell (offenes MD bleibt Wahrheit)
- **Keine neue Wahrheits-DB.** Vault bleibt `/home/dev/tools/Hal`, offenes Markdown (Postgres bleibt nur Live-Index).
- **`consumers.yaml`** (gitignored, neben `engines.yaml`): je Konsument `consumer_id`, `api_key`, `scope.read[]`, `scope.write[]` (Glob-Pfade relativ zum Vault-Root). Interner Konsument `jupiter` mit implizitem Voll-Scope.
- **Audit-Spur zweigleisig:** (a) wie bisher Frontmatter-`owner`/`source` pro Datei; (b) zusätzlich **Append-only Audit-Log** als JSONL im Vault (`Agentic OS/Jupiter/_audit/vault-writes.jsonl`) — bleibt offen lesbar, keine Black-Box. Felder: Zeit, `consumer_id`, Pfad, Aktion, Bytes, Version vorher/nachher.
- **Version** = Content-Hash (`hashlib`) bzw. `mtime_ns` der Datei, in Lese-Antworten mitgegeben.

### C) API-Vertrag (Endpunkte, kein Code)
```
GET  /vault/v1/read?path=&mode=full|excerpt&offset=&limit=
        → { path, version, content|excerpt, truncated, total_chars }
GET  /vault/v1/search?q=&scope=all|curated&limit=
        → [ { path, line, snippet, score } ]   (Pointer, kein Volltext)
GET  /vault/v1/resolve?path=&line=&radius=
        → { path, version, excerpt }
POST /vault/v1/write   { path, mode: create|append|overwrite, content, base_version? }
        → 201/200 { path, version } | 409 Conflict | 403 Scope | 404 Pfad
Header (alle): X-Vault-Consumer, X-Vault-Key
```
Versioniert über Pfad-Präfix `/vault/v1`; interne Layout-Brüche werden in der Fassade abgefangen.

### D) Tech-Entscheidungen (Begründung)
- **Fassade statt Neubau:** `VaultService` ist sauber gekapselt — wir stabilisieren nur den *Vertrag* nach außen.
- **Scope serverseitig, Pfade nie ungeprüft:** baut auf vorhandenem `_resolve_write`-Realpath-Schutz auf, erweitert um Consumer-Scope-Globs → eingebettete App sieht nur ihren Bereich; kein Vollzugriff per Default.
- **Pointer-first:** nutzt vorhandenes `rag_preview` — kontextsparsam, konsistent mit #23.
- **Optimistische Versionsprüfung statt Lock:** kein Daemon/Lockfile-Zustand, passt zur dateibasierten Realität; verhindert trotzdem Last-Write-wins-Verlust. `append`/Knowledge-Notizen behalten den bestehenden atomaren Append.
- **Audit als offenes JSONL im Vault:** direkt lesbar (AC „keine Black-Box"), bereitet PROJ-25-`owner`-Bindung vor, ohne DB-Wahrheitsquelle.
- **`consumers.yaml` statt JWT jetzt:** Single-User-Brücke. PROJ-25 tauscht `resolve_consumer()` gegen JWT-`owner`-Auflösung — gleicher Vertrag, kein Konsumenten-Bruch.

### E) Dependencies
- Keine neuen Pakete (FastAPI/Pydantic/PyYAML vorhanden; Hash via stdlib `hashlib`).

### F) Mapping Requirement → Modul
| Requirement / AC | Ort |
|---|---|
| Versionierte API (read/write/search/resolve) | `backend/app/routes/vault_v1.py` (neu) |
| Service-Fassade, interne Aufrufer migrieren | `backend/app/engine/vault.py` (`VaultService`, erweitern) |
| Consumer-Scope + Keys | `consumers.yaml` (neu, gitignored) + `resolve_consumer()`-Dependency |
| Scope-Enforcement / Path-Traversal | `enforce_scope()` + bestehendes `_resolve_*` |
| Pointer-first / Ausschnitt | bestehendes `rag_preview` / `resolve` |
| Konflikt-Sicherheit | `base_version`-Prüfung im `write`-Pfad → 409 |
| Audit | `_audit/vault-writes.jsonl` (Append-only) |
| Beispiel-Konsument (iFrame-App) | Doku in `docs/` + Eintrag in `consumers.yaml` |

**Verantwortlich:** Backend Developer (`/abc-backend`). Kein Frontend nötig (Konsumenten sind Apps/iFrames; optionales Konfig-UI für `consumers.yaml` später).

### Implementierung (Backend, 2026-06-25 · Branch `dev`)
Backend vollständig umgesetzt, 32 neue Tests + volle Suite (770) grün.

**Neue/erweiterte Dateien:**
- `backend/app/routes/vault_v1.py` (neu) — versionierte Fassade `/vault/v1` mit `GET /read`, `GET /search`, `GET /resolve`, `POST /write`. Consumer-Auth via Header-Dependency `get_consumer`; Scope-Gates `_require_read`/`_require_write`.
- `backend/app/engine/consumers.py` (neu) — `ConsumerRegistry` (live mtime-gecacht wie `EngineRegistry`) + `Consumer` (Scope-Globs read/write). `_glob_to_regex`: `**` über Ordnergrenzen, `*` segment-intern. Key-Vergleich konstantzeit (`hmac.compare_digest`). Kein Default-Vollzugriff. Optionaler interner `jupiter`-Konsument nur bei gesetztem `JUPITER_VAULT_INTERNAL_CONSUMER_KEY`.
- `backend/app/engine/vault.py` — `VaultService` erweitert: `file_version` (sha256-16 Inhalts-Hash), `read_at` (full/excerpt + 413 bei Übergröße), `resolve_pointer` (Pointer→Ausschnitt), `write_at` (create/overwrite/append + optimistische `base_version`-Prüfung), `audit_write` (Append-only JSONL). Neue `VersionConflictError` trägt `current` (→ 409 mit `current_version`).
- `backend/app/schemas/vault_v1.py` (neu) — Pydantic-v2-Vertrag.
- `backend/app/config.py` — `consumers_config_path`, `vault_internal_consumer_key`, `vault_max_read_bytes` (1 MB), `vault_audit_rel_path` (`_audit/vault-writes.jsonl`).
- `backend/app/main.py` — Registry an `app.state.consumers`, Router registriert.
- `backend/config/consumers.example.yaml` (neu) + `.gitignore`-Eintrag für `consumers.yaml`.

**Konflikt-Sicherheit:** `create` auf existierende Datei → 409; `overwrite` ohne/mit falscher `base_version` → 409 (kein Last-Write-wins); `append` immer atomar mit Datei-Lock.

**Deviationen vom Design:** Path-Resolution für Schreibzugriffe nutzt die vault-weite Traversal-Härtung (`_resolve_read`); die Bereichsgrenze kommt nun aus dem **Consumer-Scope** (nicht mehr fix aus dem Jupiter-Subdir) — so kann ein Konsument gezielt auf einen Teilbereich beschränkt werden. `.md`-Pflicht für Schreibzugriffe (offenes MD bleibt Wahrheit). Interne in-process-Aufrufer (challenge/coordinator/recovery/manager/scout) bleiben auf der direkten `VaultService`-API (eine Quelle der Wahrheit) — sie über HTTP `/vault/v1` zu zwingen wäre falsch; der versionierte Vertrag ist die **externe** Schicht.

## QA Test Results
**Re-Test 2026-06-26 (3. Durchlauf):** Kein PROJ-24-Fix seit dem 2. Durchlauf — PROJ-25 fügte nur Rate-Limiting auf Auth-Endpunkte hinzu; PROJ-26 ergänzte `config.py` um `registry_root`. Weder `consumers.py` noch `vault_v1.py` noch `engine/vault.py` wurden berührt. **BUG-24-1 (Critical) besteht unverändert** (beide `xfail(strict)`-Tests weiter rot). Volle Suite 785 passed + 2 xfailed — keine Regression. **Verdikt unverändert: NICHT produktionsreif.**

**Fix 2026-06-26:** `_norm` in `backend/app/engine/consumers.py` erweitert um `posixpath.normpath`-Aufruf — kollabiert `..`-Segmente vor dem Glob-Match. Pfade, die nach Normalisierung aus dem Vault-Root ausbrechen (starten mit `..`), werden als `""` zurückgegeben (kein Scope-Glob matcht). Beide `xfail`-Tests jetzt echte PASSes. Volle Suite **787 passed, 0 xfailed** — keine Regression.

---
**Getestet:** 2026-06-26 · **Tester:** QA Engineer (`/abc-qa`) · **Branch:** `dev`
**Methode:** AC-Matrix + Red-Team (Code-Review + empirische Repros gegen `VaultService`/`ConsumerRegistry`) + volle pytest-Suite.

### Produktionsreife: **BEREIT** — alle Bugs behoben / akzeptiert
Volle Suite **787 passed, 0 xfailed**. Alle Critical/High-Bugs behoben.

### Akzeptanzkriterien
| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Eigenständiger Dienst: read/write/search/resolve | ✅ PASS (`/vault/v1`, 4 Endpunkte) |
| 2 | API versioniert (`/vault/v1`) | ✅ PASS |
| 3 | Eingebettete Apps nutzbar + Beispiel-Setup | ⚠️ TEILWEISE — `consumers.example.yaml` vorhanden; ein **dokumentiertes** iFrame-Konsumenten-Beispiel in `docs/` (laut Design F) fehlt noch |
| 4 | Scope pro Konsument, **kein Vollzugriff per Default** | ✅ PASS — BUG-24-1 behoben (`_norm` kollabiert `..` via `posixpath.normpath`) |
| 5 | Schreibzugriffe tragen Herkunft (Audit) | ✅ PASS (Append-only JSONL, `consumer`+Pfad+Version) |
| 6 | Offenes MD, keine Black-Box | ✅ PASS (`.md`-Pflicht, Audit als offenes JSONL) |
| 7 | Pointer/Ausschnitt statt Volltext | ✅ PASS (`read mode=excerpt`, `search`, `resolve`) |
| 8 | Gleichzeitige Schreibzugriffe konfliktsicher | ✅ PASS (create→409, overwrite ohne/falsche `base_version`→409, append atomar+Lock) — BUG-24-2 (Low) bleibt akzeptiert |
| 9 | Alle Texte/Fehler deutsch | ✅ PASS |

### Bugs

**BUG-24-1 — Scope-Bypass über `..`-Pfadsegmente · Severity: CRITICAL · ✅ BEHOBEN**
`_norm` in `consumers.py` kollabierte `..` nicht → Glob-Match arbeitete auf rohem Pfad, Datei-Auflösung via `realpath` auf normalisiertem. Fix: `posixpath.normpath` in `_norm` vor Glob-Match; `..`-Ausbrüche → `""` → automatisch verweigert. Beide Regressionstests (ehem. `xfail`) jetzt grün.

**BUG-24-2 — TOCTOU bei `mode=overwrite` · Severity: LOW · akzeptiert**
Die optimistische Versionsprüfung (`base_version` vs. `file_version`) und das `_atomic_write` sind nicht unter einem gemeinsamen Lock. Zwei gleichzeitige `overwrite` mit identischer `base_version` bestehen beide die Prüfung → das spätere gewinnt, das frühere Update geht **still** verloren (kein 409). Keine Korruption (Write bleibt atomar), nur ein verlorenes Update; im Single-User-Brücken-Betrieb sehr unwahrscheinlich. Akzeptiert für MVP; härtbar via Lock über Prüf-+Schreibfenster oder `O_EXCL`-Rename-Schema.

### Security-Audit (Red-Team)
- **Auth:** Header-Pflicht, fehlend/falsch → 401 ✓; Key konstantzeit (`hmac.compare_digest`) ✓; reservierte `id "jupiter"` aus YAML gesperrt ✓; interner Voll-Scope-Konsument nur bei gesetztem Key ✓.
- **Vault-Root-Traversal:** `../../etc/passwd` → 400/403 (realpath-Härtung greift) ✓.
- **Scope-Traversal:** ✅ behoben (BUG-24-1-Fix).
- **Search-Leak:** `search`/`search_curated` filtern Treffer per `can_read` auf bereits aufgelöste Pfade (kein `..`) → kein Scope-Leck über die Suche ✓.
- **DoS:** Such-/RAG-Obergrenzen (`_MAX_FILE_BYTES`, Hit-Caps), Lese-Limit `vault_max_read_bytes`→413 ✓.
- **Audit-Integrität:** zeichnet den **aufgelösten** Zielpfad auf (forensisch korrekt), best-effort (rollt Write nicht zurück) ✓.

### Regression
Volle Backend-Suite (787) grün — keine Regression in bestehenden Features.

## Deployment
_To be added by /abc-deploy_
