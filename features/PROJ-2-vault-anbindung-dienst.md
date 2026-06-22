# PROJ-2: Vault-Anbindung als Dienst

## Status: Approved
**Created:** 2026-06-22
**Last Updated:** 2026-06-22 (QA bestanden — READY)

## Dependencies
- None — kann parallel zu PROJ-1 gebaut werden (eigenständiger Backend-Dienst).

## Beschreibung
Ein Backend-Dienst, der den **Hal-Vault** (`/home/dev/tools/Hal`, Obsidian, PARA-Struktur) als Daten-/Wissensschicht anbindet: MD lesen, schreiben, auflisten, durchsuchen. Schreibt Session-Logs und Handover-Dokumente als offenes MD zurück. Grundlage für Gedächtnis (#9), Doku (#8) und spätere Recovery (#20) sowie für den geteilten Dienst (#14). Jedes Artefakt trägt ein `owner`-Feld (#21).

## User Stories
- Als Nutzer möchte ich, dass Session-Transkripte automatisch als MD in meinem Hal-Vault landen, um sie in Obsidian wiederzufinden.
- Als Nutzer möchte ich Handover-Dokumente im Vault speichern und lesen, damit Kontext über Resets hinweg erhalten bleibt.
- Als Nutzer möchte ich, dass jedes Artefakt ein `owner`-Feld trägt, um später ohne Migration teamfähig zu werden.
- Als System möchte ich Vault-MD durchsuchen können, um später Pointer statt Volltext zu liefern (Grundlage RAG #23).

## Acceptance Criteria
- [ ] Dienst kann MD-Dateien im Hal-Vault lesen, schreiben und auflisten.
- [ ] Jupiter-Artefakte landen unter einem dedizierten Vault-Unterordner (z. B. `02 Projects/Jupiter/…` bzw. `Agentic OS/…`; exakte Konvention = Architektur-Entscheidung), **ohne** die bestehende PARA-Struktur zu verändern.
- [ ] Geschriebene Dateien sind valides Obsidian-MD mit YAML-Frontmatter (mind. `owner`, `session_id`, `created`, `type`).
- [ ] Rohe Session-Logs und Handover-/kuratierte Dokumente liegen in getrennten Bereichen (Vorbereitung Stufe 3 / #10).
- [ ] Textsuche über Vault-MD liefert Treffer mit Dateipfad + Ausschnitt.
- [ ] Schreibzugriffe sind atomar (kein halb geschriebenes MD bei Absturz).

## Edge Cases
- Datei existiert bereits → konfigurierbar: anhängen vs. neue versionierte Datei (**kein** stilles Überschreiben).
- Vault-Pfad nicht erreichbar / Permission denied → klarer Fehler, keine Datenkorruption.
- Sehr großes Log → Streaming-Write statt alles im RAM.
- Umlaute/Sonderzeichen in Titeln → saubere Slug-Bildung für Dateinamen.
- Gleichzeitige Schreibzugriffe zweier Sessions → kein Datenverlust (getrennte Dateien / Locking).

## Technical Requirements (optional)
- **Vault-Struktur-Konvention** (Brainstorm offener Punkt #3) in der Architektur-Phase festlegen, passend zum bestehenden PARA-Layout (`00 Context` … `08 To-Dos`, `Agentic OS/`).
- Live-Zustand bleibt in Postgres; der Vault ist die persistente **Wahrheit** (Datenmodell-Grenze in Architektur klären).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-22 · **Stack:** FastAPI + Filesystem-MD (Hal-Vault, kein DB/RLS im MVP) · **Branch:** dev

> Jupiter-MVP weicht bewusst von den globalen Defaults ab: **kein JWT/RLS/Neon**. Der Vault (Obsidian-MD im Dateisystem) ist die **persistente Wahrheit**; der Live-Zustand der Sessions bleibt vorerst in-memory (`SessionState`). Der Vault-Dienst ist reine Datei-I/O — kein neuer DB-Layer.

### A) Komponenten-Struktur (Backend; eigene UI später via Cockpit #3 / MD-Reader #16)
```
Vault-Dienst (Engine-Layer)
├── VaultService (engine/vault.py — neuer Dienst, Muster wie engine/constitution.py)
│   ├── read(pfad)            → MD-Inhalt eines Vault-Files
│   ├── list(unterordner)     → Dateien unter dem Jupiter-Bereich auflisten
│   ├── search(query)         → Volltext über den GANZEN Vault (read-only) → Treffer (Pfad + Ausschnitt)
│   ├── write(...)            → atomar (temp + rename); Default-Kollision = append (mit Lock)
│   └── slug()/frontmatter()  → saubere Dateinamen + valides YAML-Frontmatter
├── Vault-Layout (im Hal-Vault, OHNE die PARA-Struktur zu verändern)
│   └── Agentic OS/Jupiter/
│       ├── Sessions/         ← ROHE Session-Logs (1 Datei je Session, immutable Snapshots)
│       └── Handovers/        ← KURATIERTE Handover-/Übergabe-Dokumente (getrennt → AC erfüllt)
├── Session-Hook (engine/manager.py)
│   └── beim Übergang Session→DONE (closed-Event) wird das Roh-Log nach Sessions/ geschrieben
└── API → routes/vault.py (neuer Router, registriert in main.py — kein Namens-Konflikt)
```

### B) Datenmodell (Klartext)
**Kein DB-Schema** — der Vault-Dienst arbeitet ausschließlich auf MD-Dateien.

**Jede geschriebene Datei** ist valides Obsidian-MD mit YAML-Frontmatter (mind. die AC-Pflichtfelder):
```
owner        – wer das Artefakt besitzt (serverseitig gestempelt, MVP: "dev")  [#21]
session_id   – zu welcher Session es gehört
created      – Erstell-Zeitpunkt (ISO)
type         – "session_log" | "handover" (Roh vs. kuratiert)
```
Darunter folgt der eigentliche MD-Body (Transkript bzw. Handover-Prosa).

**Zwei getrennte Bereiche** (AC „roh vs. kuratiert"):
- `Agentic OS/Jupiter/Sessions/` — automatisch erzeugte Roh-Transkripte, 1 Datei pro Session.
- `Agentic OS/Jupiter/Handovers/` — bewusst kuratierte Übergaben (Grundlage Kontext-Mgmt PROJ-5, Recovery #20).

**Datei-Benennung:** `<datum>--<slug>-<kurz-id>.md` — Umlaute/Sonderzeichen werden zu einem sauberen ASCII-Slug normalisiert (Edge-Case Spec).

### C) API-Form (nur Endpunkte, kein Code)
```
GET  /vault/files?dir=<unterordner>      → listet MD-Dateien im Jupiter-Bereich (Pfad + Meta)
GET  /vault/file?path=<pfad>             → liest eine MD-Datei (Frontmatter + Body)
GET  /vault/search?q=<query>             → Volltextsuche über den GANZEN Vault → [Pfad, Ausschnitt]
POST /vault/files                        → schreibt MD (type, body, optional session_id);
                                           on_exists = append (Default) | version | error
POST /sessions/{id}/handover             → schreibt ein kuratiertes Handover-Doc nach Handovers/
```
- **Schreiben** ist **immer** auf `Agentic OS/Jupiter/**` beschränkt (Pfad-Validierung, s.u.).
- **Lesen/Suchen** darf den **ganzen** Vault sehen (read-only) → Grundlage für späteres RAG (#23).
- Roh-Logs entstehen zusätzlich **automatisch** über den Session-Hook (kein API-Aufruf nötig).

### D) Tech-Entscheidungen (warum)
- **Dienst als `engine/vault.py`, gleiches Muster wie `engine/constitution.py`.** Es gibt keinen `services/`-Ordner; Business-Logik lebt im `engine/`-Layer. Single Responsibility, schlanke Routes, die den Dienst über `app.state` aufrufen — konsistent mit PROJ-1/PROJ-6.
- **Vault-Ort `Agentic OS/Jupiter/`** (nicht `02 Projects/`): Session-Logs/Handover sind **maschinen-erzeugte Laufzeit-Artefakte** und gehören neben Jarvis/Memories/Pipeline, nicht in die handgepflegten PARA-Projektdocs. Die bestehende PARA-Struktur bleibt unangetastet (AC).
- **Schreiben gekapselt auf den Jupiter-Unterbaum, Lesen/Suchen vault-weit.** Asymmetrie bewusst: Jupiter soll vorhandenes Wissen finden (RAG-Grundlage #23), aber niemals fremde Vault-Bereiche verändern. Durchgesetzt per Pfad-Normalisierung (`realpath` + erlaubter Wurzel-Check) — dasselbe Härtungs-Muster wie `validate_project_path` in `manager.py` und die Rollen-Regex in `constitution.py` (Pfad-Traversal-Schutz).
- **Atomare Writes über temp-Datei + `rename`** (POSIX-atomar) → kein halb geschriebenes MD bei Absturz (AC). **Default-Kollision = append**, abgesichert durch einen **Datei-Lock**, damit zwei gleichzeitig schreibende Sessions sich nicht überschreiben (Edge-Case). Roh-Logs nutzen ohnehin **eine Datei je Session** → echte Parallel-Appends sind die Ausnahme.
- **`owner`-Feld von Anfang an im Frontmatter** (#21), serverseitig gestempelt (MVP `"dev"`) — macht das Format später ohne Migration teamfähig.
- **Suche im MVP = Dateisystem-Scan + Substring/Regex** (kein Index). Genügt für die Vault-Größe; liefert Pfad + Ausschnitt (AC). Ein echter Index/Embeddings ist explizit RAG (#23, P1) und hier Non-Goal.
- **Streaming-Write für sehr große Logs** (Edge-Case): Transkript wird beim Schreiben gestreamt statt komplett im RAM gehalten.
- **Klarer Fehler statt Korruption** bei nicht erreichbarem Pfad / Permission denied (Edge-Case) → sauberer HTTP-Fehler, kein Teil-Write.

### E) Abhängigkeiten
- **Keine neuen Pakete zwingend nötig** — reine Datei-I/O + vorhandenes FastAPI/Pydantic. YAML-Frontmatter lässt sich mit der Standardbibliothek schreiben.
- **Optional** `python-frontmatter` (nur falls robustes Parsen bestehender Frontmatter beim Append gewünscht ist) — Entscheidung dem Backend-Developer überlassen; nicht zwingend.
- Neue Config-Settings (Muster wie `constitution_dir`): `vault_root` (Default `/home/dev/tools/Hal`, env `JUPITER_VAULT_ROOT`) und der abgeleitete Jupiter-Schreib-Unterbaum `Agentic OS/Jupiter`.

### Hinweis für /abc-backend
- Neuen Router `routes/vault.py` in `main.py` registrieren (Muster: `sessions.py` / `constitution.py`).
- Schreib-Pfad-Validierung gegen den Jupiter-Unterbaum nach dem Vorbild `validate_project_path` (`engine/manager.py`) implementieren; Lese-/Such-Validierung gegen `vault_root`.
- Session-Hook beim `closed`-Event in `manager.py` (Übergang → DONE) ergänzen, der das Roh-Log nach `Sessions/` schreibt.
- Atomare Writes (temp + `os.rename`) + Datei-Lock für Append; Slug-/Frontmatter-Helfer als reine Funktionen (testbar wie `constitution.py`).

### Implementation Notes (Backend Developer)
**Datum:** 2026-06-22 · **Branch:** dev · **Stand:** Backend fertig, QA ausstehend · **Tests:** `pytest` → **99 grün** (26 neue für PROJ-2).

**Gebaute Teile:**
- **`engine/vault.py` — `VaultService`** (reine Datei-I/O, Muster wie `constitution.py`): `read_file`, `list_files`, `search`, `write`, `write_session_log` + Helfer `slugify`, `_build/_parse_frontmatter`. Lesen/Suchen vault-weit, Schreiben nur im Jupiter-Unterbaum.
- **Vault-Layout:** geschrieben wird nach `<vault_root>/Agentic OS/Jupiter/Sessions/` (roh) bzw. `…/Handovers/` (kuratiert) — getrennt (AC). Dateiname `YYYY-MM-DD--<slug>-<kurz-id>.md`, ASCII-Slug (Umlaut-Mapping).
- **Frontmatter:** jede Datei valides Obsidian-MD mit YAML-Frontmatter (`owner`, `session_id`, `created`, `type`, optional `title`) — `owner` serverseitig gestempelt (#21).
- **Atomare Writes:** temp-Datei + `os.replace`; Default-Kollision **append** mit `fcntl`-Lock (kein zweites Frontmatter beim Anhängen); `version` (→ `-2.md`) und `error` (→ 409) wählbar.
- **Suche:** case-insensitive Substring über den GANZEN Vault → Pfad + Zeile + Ausschnitt; Limits (max 100 Hits, 2 MB/Datei) als DoS-Schutz.
- **API (`routes/vault.py`):** `GET /vault/files?dir=`, `GET /vault/file?path=`, `GET /vault/search?q=&limit=`, `POST /vault/files`. Plus `POST /sessions/{id}/handover` (kuratiertes Doc, Default `version`).
- **Auto-Log:** `SessionManager` bekommt optional einen `VaultService`; bei Übergang **Session → DONE** schreibt ein `on_done`-Hook das Roh-Transkript automatisch nach `Sessions/` (Fehler werden geschluckt → kein Session-Abbruch).
- **Config:** `vault_root` (`JUPITER_VAULT_ROOT`, Default `/home/dev/tools/Hal`), `vault_jupiter_subdir` (`Agentic OS/Jupiter`), `vault_autolog` (Default an).

**Sicherheit/Edge-Cases (getestet):** Pfad-Traversal beim Lesen/Schreiben (`..`, absolute Pfade, `/etc/passwd`) → `ValueError`/400; Suche sieht fremde PARA-Dateien (read-only), Schreiben bleibt im Jupiter-Baum; fehlender Vault-Pfad → klarer Fehler statt Korruption; keine `.tmp`-Reste; unbekannter `type` → 400/422.

**Test-Isolation:** neue `tests/conftest.py` (autouse) biegt `settings.vault_root` pro Test auf ein tmp-Verzeichnis → **kein** Test schreibt je in den echten Hal-Vault (verifiziert: kein `Agentic OS/Jupiter`-Ordner entsteht).

**Offen / Hinweis für QA:**
- `--append-system-prompt`-/JWT-/RLS-Themen sind hier N/A (MVP-Abweichung, reine Datei-I/O).
- `python-frontmatter` bewusst NICHT eingeführt — der tolerante Eigen-Parser genügt fürs MVP.
- Streaming-Write für sehr große Logs ist noch nicht umgesetzt (aktuell ganzer Body im RAM) — für MVP-Loggrößen unkritisch, später nachrüstbar (Repository-Seam offen).

## QA Test Results
**Getestet:** 2026-06-22 · **Branch:** dev · **Tester:** QA Engineer · **Suite:** `backend/tests/` → **119 grün** (`pytest`, +20 in `test_proj2_qa.py`).

### Akzeptanzkriterien (6/6 bestanden)
| # | Kriterium | Ergebnis | Nachweis |
|---|-----------|----------|----------|
| 1 | MD lesen, schreiben, auflisten | ✅ PASS | `test_ac1_read_write_list`, API `test_api_write_read_list_search` |
| 2 | Artefakte unter `Agentic OS/Jupiter/…`, PARA unangetastet | ✅ PASS | `test_ac2_dedicated_subfolder_para_untouched` |
| 3 | Valides Obsidian-MD mit YAML-Frontmatter (`owner`, `session_id`, `created`, `type`) | ✅ PASS | `test_ac3_valid_frontmatter_required_fields` (echter `yaml.safe_load`) |
| 4 | Rohe Logs (`Sessions/`) vs. kuratierte Docs (`Handovers/`) getrennt | ✅ PASS | `test_ac4_raw_and_curated_separated`, `test_autolog_writes_session_log_on_stop` |
| 5 | Textsuche → Pfad + Ausschnitt | ✅ PASS | `test_ac5_search_returns_path_and_excerpt` |
| 6 | Schreibzugriffe atomar (kein halb geschriebenes MD) | ✅ PASS | `test_ac6_atomic_write_no_partial` (temp+`os.replace`, keine `.tmp`-Reste) |

### Edge-Cases (alle abgedeckt)
- ✅ Datei existiert → **append** (Default, kein stilles Überschreiben), `version` (→ `-2.md`), `error` (→ 409) wählbar.
- ✅ Vault-Pfad nicht beschreibbar → klarer `PermissionError`/503, keine halbe Datei (`test_edge_vault_unreachable_clear_error_no_corruption`).
- ✅ Umlaute/Sonderzeichen → sauberer ASCII-Slug (`test_edge_umlaut_slug`).
- ✅ Gleichzeitige Sessions → getrennte Dateien je `session_id` + `fcntl`-Lock beim Append (`test_edge_concurrent_sessions_separate_files`).
- ⚠️ Sehr großes Log → **Streaming-Write noch nicht umgesetzt** (ganzer Body im RAM). Für MVP-Loggrößen unkritisch → siehe QA-2.2.

### Security-Audit (Red-Team)
- ✅ **Pfad-Traversal Lesen** (`..`, `/etc/passwd`, `a/../../b`) → `ValueError`/400 (`test_sec_read_traversal_blocked`, API `test_api_read_traversal_400`).
- ✅ **Symlink-Escape**: Symlink im Vault, der nach außen zeigt → `realpath`-Guard verweigert das Lesen (`test_sec_symlink_escape_blocked`). Starker Schutz gegen Daten-Exfiltration.
- ✅ **Schreib-Eingrenzung**: client-gelieferte `session_id` mit `../` bricht NICHT aus dem Jupiter-Baum aus — finaler `_resolve_write`-Guard hält (`test_sec_client_session_id_cannot_escape_jupiter`).
- ✅ **Frontmatter-Injection**: Title mit YAML-Breakout-Versuch wird via `json.dumps` escaped → kein neuer Top-Level-Key, genau 5 erwartete Keys (`test_sec_frontmatter_injection_safe`, echter YAML-Parser).
- ✅ **Lese-/Schreib-Asymmetrie**: Suche/Lesen vault-weit, Schreiben nur im Jupiter-Baum (`test_sec_search_write_asymmetry`).
- ✅ **DoS-Schutz Suche**: max 100 Hits, Dateien > 2 MB übersprungen; `dir`-Traversal in `/vault/files` → 400.
- N/A: JWT/RLS/Mandant/MinIO, Flutter/Responsive (MVP-Abweichung bzw. UI später in #3/#16).

### Findings (alle Low → nicht deploy-blockierend)
| ID | Sev | Befund | Empfehlung |
|----|-----|--------|------------|
| QA-2.1 | Low | Client-`session_id` mit `/` (z. B. `a/b/c`) erzeugt **verschachtelte Ordner** im Jupiter-Baum (`Sessions/…-a/b/c.md`). **Kein** Sicherheits-Ausbruch (Guard verifiziert), aber unsaubere Dateinamen. | `session_id`-Segment vor dem Dateinamen ebenfalls `slugify`-en bzw. per Regex `^[A-Za-z0-9_-]{1,64}$` validieren (wie Rollenname in PROJ-6). |
| QA-2.2 | Low | **Streaming-Write** für sehr große Logs noch nicht umgesetzt (Body komplett im RAM). | Für MVP akzeptiert; später Streaming/Chunked-Write nachrüsten (Repository-Seam offen). |
| QA-2.3 | Low | Fehlt der Vault-Root komplett, schlägt erst der Schreibversuch fehl (kein früher Health-Hinweis). | Optional: beim Start prüfen, ob `vault_root` existiert, und warnen (analog QA-6.2). |

### Produktionsreife-Entscheidung
**READY / Approved** — alle 6 AC bestanden, alle Edge-Cases abgedeckt, keine Critical/High/Medium-Bugs, 119 Tests grün. QA-2.1–2.3 sind optionale Härtungen (kein Blocker).

## Deployment
_To be added by /deploy_
