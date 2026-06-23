# PROJ-12: MD-Editor (voll) — Obsidian-DNA

## Status: Deployed
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #16 (voller Ausbau; Reader = PROJ-7)

## Dependencies
- Requires: PROJ-7 (MD-Reader) — erweitert die read-only-Ansicht um Editieren; nutzt denselben Index, Wikilink-Parser, Frontmatter-Split.
- Verwandt: PROJ-2 (Vault) — Schreiben zurück in den Hal-Vault.

## Beschreibung
Der MD-Reader (PROJ-7) wird zum **leichten Editor mit Obsidian-DNA**: Markdown nicht nur lesen, sondern direkt **bearbeiten und speichern**, mit `[[Wikilinks]]` (inkl. Autovervollständigung) und **Backlinks**. Ziel: Doku lebendig bearbeitbar, kein Tool-Wechsel zu Obsidian.

## User Stories
- Als Nutzer möchte ich eine `.md`-Datei direkt im Jupiter-UI bearbeiten und speichern, ohne nach Obsidian zu wechseln.
- Als Nutzer möchte ich beim Tippen von `[[` eine Autovervollständigung existierender Notizen bekommen.
- Als Nutzer möchte ich die **Backlinks** einer Notiz sehen (welche Dateien verlinken hierher).
- Als Nutzer möchte ich zwischen **Edit- und Vorschau-Modus** wechseln (oder Split-View).
- Als Nutzer möchte ich, dass das Frontmatter (YAML) erhalten und valide bleibt.

## Acceptance Criteria
- [ ] Editor lädt Inhalt (Frontmatter + Body) und speichert zurück an denselben Pfad (`PUT`/Save), atomar (kein Teil-Schreiben).
- [ ] `[[`-Eingabe öffnet eine **Autovervollständigung** aus dem MD-Index (PROJ-7); Auswahl fügt einen gültigen Wikilink ein.
- [ ] Wikilinks im Vorschaumodus sind klickbar und navigieren zur Zieldatei (Auflösung wie PROJ-7).
- [ ] **Backlinks-Panel** zeigt alle Dateien, die auf die aktuelle Notiz verlinken.
- [ ] Umschalten **Edit ↔ Vorschau** (mind. eines von beidem; Split-View optional); Body-Markdown rendert mit Tabellen/Code/Headings.
- [ ] **Ungespeicherte Änderungen** werden erkannt; Warnung beim Verlassen/Navigieren.
- [ ] Schreibziel ist auf erlaubte Roots/Vault beschränkt; Pfad serverseitig geprüft.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Speicher-Zustände explizit.

## Edge Cases
- **Externe Änderung** der Datei seit dem Laden → Konflikt erkennen (z. B. mtime/Hash), nachfragen statt blind überschreiben.
- **Ungültiges Frontmatter** beim Speichern → Validierung, klare Fehlermeldung, kein Datenverlust.
- **Wikilink auf nicht existierende Notiz** → als „unaufgelöst" markieren (nicht klickbar), kein Crash.
- **Sehr große Datei** → performant laden/scrollen; ggf. Edit-Limit mit Hinweis.
- **Gleichzeitiges Editieren in zwei Tabs** → letzter Speichervorgang gewinnt, aber mit Konflikt-Warnung.

## Technical Requirements (optional)
- Baut auf den vorhandenen PROJ-7-Komponenten (`md-tree`, `remark-wikilink`, `markdown-view`) und dem `/md`-Backend auf.
- Speichern atomar (temp + rename); Schreibpfad serverseitig auf Vault/Roots beschränkt.
- Optimistic UI mit Rollback bei Speicherfehler.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Next.js 16 (App Router, TS) + FastAPI · **Branch:** dev

### Ausgangslage (was PROJ-7 schon liefert)
- **Backend `/md`** (`backend/app/routes/md.py`): `GET /md/sources`, `GET /md/index` (flache Liste aller `.md` → für `[[`-Autocomplete), `GET /md/file` (liefert `{path, frontmatter (geparst), body, content}`). **Kein Schreibpfad.** Pfad-Härtung via `_validate_md_file` (realpath + `allowed_roots`-Whitelist).
- **Frontmatter-Split** existiert (`vault.py::_parse_frontmatter`) und wird beim Lesen schon strukturiert geliefert.
- **Atomares Schreiben** existiert wiederverwendbar: `vault.py::_atomic_write` (temp-Datei + `os.replace`, POSIX-atomar). Schreibpfad-Validierung: `vault.py::_resolve_write`.
- **Wikilinks** (`remark-wikilink.ts` + `md-tree.ts`): Parser für `[[Ziel]]`, `[[Ziel|Alias]]`, `[[Ziel#Anker]]`; `buildWikilinkIndex()` + `resolveWikilink()` (basename/rel-path-Lookup), unaufgelöst = durchgestrichen. **Kein Backlink-Reverse-Index.**
- **Anzeige** (`markdown-view.tsx`): read-only react-markdown + remark-gfm, härtet gegen `<script>`/`javascript:` (kein rehype-raw), Truncate bei 400K Zeichen.

### A) Komponenten-Struktur (Frontend)
```
MdEditorPanel  (erweitert die bestehende Reader-Ansicht)
├── EditorToolbar
│   ├── ModeToggle (Edit ⇄ Vorschau; Split optional)
│   ├── SaveButton (zeigt Dirty-State „● Ungespeichert" / „Gespeichert")
│   └── ConflictBadge (sichtbar nur bei externer Änderung)
├── EditorTextarea            ← Edit-Modus: rohes Markdown (Frontmatter + Body)
│   └── WikilinkAutocomplete  ← Popover bei „[["; Liste aus /md/index, Filter live
├── MarkdownView (PROJ-7)     ← Vorschau-Modus: gerendert, Wikilinks klickbar
├── BacklinksPanel            ← „Verlinkt von" – Liste referenzierender Notizen
└── States: Laden / Fehler / Leer / Gespeichert / Konflikt (alle explizit, deutsch)
```

### B) Datenmodell (kein DB-Eintrag — alles Dateisystem)
Eine bearbeitbare Notiz = genau eine `.md`-Datei innerhalb `allowed_roots` (Vault + optional Projekt). Kein neuer DB-State. Pro Lesevorgang liefert das Backend zusätzlich:
- `mtime` (Änderungszeit) **und** `hash_sha256` des Inhalts → Basis für Konflikterkennung.
Der Editor hält diese beiden Werte und schickt sie beim Speichern zurück („optimistic concurrency").

### C) API-Shape (nur Endpunkte, kein Code)
```
GET  /md/file?path=…        → ERWEITERN: zusätzlich mtime + hash_sha256 zurückgeben
POST /md/file               → NEU: Notiz speichern
     Body: { path, content, expected_mtime?, expected_hash?, force? }
       (content = voller Rohtext inkl. Frontmatter-Block, 1:1 — kein YAML-Re-Serialize)
     200 → { path, mtime, hash }
     409 → Konflikt (Datei extern geändert) — wenn expected_mtime/hash abweicht und force≠true
     400 → Pfad außerhalb der Roots / ungültiges Frontmatter (kein Schreibvorgang)
GET  /md/backlinks?path=…   → NEU: Liste der Notizen, die per [[…]] hierher verlinken
GET  /md/index  (bestehend) → bleibt Quelle der [[-Autocomplete (clientseitig gefiltert)
```
Alle Schreibvorgänge atomar (`_atomic_write`), Pfad serverseitig gegen `allowed_roots` geprüft (gleiche Härtung wie Lesen, jetzt auch für Schreiben).

### D) Tech-Entscheidungen (Warum)
- **Speichern auf `/md`, nicht `/vault`:** Editor-Scope ist Vault **+** Projekt-Roots (wie der Reader); `vault.py` schreibt nur in die enge Jupiter-Write-Root. Wir nutzen aber dessen `_atomic_write`/`_resolve_write`-Bausteine wieder, statt sie zu duplizieren.
- **Konflikt via mtime **und** Hash:** mtime erkennt „Datei wurde berührt", der Hash verhindert Fehlalarm bei mtime-Wechsel ohne Inhaltsänderung. Bei echtem Konflikt → 409 + Nachfrage im UI („Überschreiben / Verwerfen"), kein blindes Last-Write-Wins. Erfüllt Edge-Cases „externe Änderung" und „zwei Tabs".
- **Autocomplete clientseitig:** `/md/index` ist schon da und klein genug; kein neuer Such-Endpoint nötig. Tippt der Nutzer `[[`, filtert das Frontend die vorgeladene Index-Liste — sofort, ohne Roundtrip.
- **Backlinks serverseitig:** Reverse-Index braucht das Scannen aller `.md` nach `[[Notizname]]`; das gehört ins Backend (ein Request statt N Reads im Browser). MVP: on-demand berechnen; Caching (mtime-invalidiert) optional später.
- **Frontmatter-Validierung beim Speichern:** YAML wird vor dem Schreiben geparst; ungültig → 400 ohne Schreibvorgang → kein Datenverlust.
- **Rohtext-Edit (Textarea) statt WYSIWYG:** Obsidian-DNA = Markdown bleibt sichtbar; minimiert Komplexität, Frontmatter bleibt 1:1 erhalten. Vorschau rendert über die bestehende `markdown-view.tsx`.

### E) Abhängigkeiten
- **Backend:** keine neuen Packages (stdlib `hashlib`, `os`; PyYAML bereits via Frontmatter-Parser vorhanden).
- **Frontend:** keine neuen Packages — Textarea nativ, Autocomplete-Popover aus shadcn/ui (Command/Popover), Rendering + Wikilinks aus PROJ-7.

### Aufgaben-Routing
- **Backend:** `POST /md/file` (Save, atomar, Pfad-Check, 409-Konflikt), `/md/file`-Read um mtime+hash erweitern, `GET /md/backlinks` (Reverse-Scan). Schemas in `schemas/md.py`. Tests in `backend/tests/test_proj12_md_editor.py`.
- **Frontend:** `MdEditorPanel` (Edit/Vorschau-Toggle, Dirty-State + Verlassen-Warnung, `[[`-Autocomplete, Backlinks-Panel, 409-Konflikt-Dialog) auf Basis der PROJ-7-Komponenten.
- **QA:** Acceptance-Kriterien + Edge-Cases (externe Änderung, ungültiges Frontmatter, Pfad-Ausbruch, große Datei, zwei Tabs).

## Implementierung — Frontend (abc-frontend, 2026-06-23)
**Branch:** dev · **Status:** Frontend fertig, Backend ausstehend (`/abc-backend`).

Aufgesetzt auf der PROJ-7-Reader-UI (`app/(cockpit)/doku/page.tsx`), kein neuer Screen.

**Neu:**
- `components/cockpit/md-editor.tsx` — `MdEditorPanel`: Rohtext-Textarea (Frontmatter+Body 1:1) ⇄ Vorschau-Toggle; `[[`-Autocomplete (Dropdown mit Tastatur-Navigation ↑/↓/Enter/Tab/Esc, Auswahl fügt `[[Name]]` am Cursor ein); Dirty-Anzeige + `Speichern`-Button + `Strg/Cmd+S`; `beforeunload`-Warnung; 409-Konflikt-Dialog (Überschreiben/Neu laden). Vorschau rendert über die bestehende `MarkdownView` (Wikilinks klickbar).
- `components/cockpit/backlinks-panel.tsx` — „Verlinkt von"-Liste via `GET /md/backlinks`.
- `lib/md-tree.ts` — reine Helfer `splitFrontmatter()` (Live-Vorschau) + `searchNotes()` (Autocomplete-Ranking). Tests in `lib/md-tree.test.ts` (4+ neue Fälle, alle grün).
- `lib/api.ts` — `saveMdFile()` (POST `/md/file`), `getMdBacklinks()`.
- `lib/types.ts` — `MdFileRead` um optionales `mtime`/`hash` erweitert; `MdSaveResult`, `MdBacklinksResult`.

**Integration:** `doku/page.tsx` — „Bearbeiten"-Toggle pro Datei; Dirty-Navigations-Guard (`window.confirm` beim Datei-/Quellen-Wechsel); Autocomplete-Quelle = alle MD-Quellen gemerged (`allNotes`); nach Speichern `reloadFile()` für konsistente Leseansicht.

**Offen für Backend (`/abc-backend`):** `POST /md/file` (atomar via `vault._atomic_write`, Pfad-Check `allowed_roots`, 409 bei mtime/Hash-Abweichung, Frontmatter-Validierung → 400), `/md/file`-Read um `mtime`+`hash` erweitern, `GET /md/backlinks` (Reverse-Scan). Bis dahin sind Speichern/Backlinks im UI vorhanden, aber serverseitig noch nicht bedient.

**Qualität:** `tsc --noEmit` sauber (einziger Treffer = vorbestehender PROJ-7-Testfehler), ESLint sauber, Vitest 14/14 grün.

## Implementierung — Backend (abc-backend, 2026-06-23)
**Branch:** dev · **Stack:** FastAPI, dateisystembasiert (kein DB/RLS — Single-User-Override).

Erweitert den bestehenden `/md`-Router (PROJ-7), keine neue Domain.

**Geändert/neu:**
- `app/engine/md_reader.py`:
  - `read_file()` liefert jetzt zusätzlich `mtime` (float) + `hash` (SHA-256) → Konfliktbasis.
  - `save_file(path, content, expected_mtime?, expected_hash?, force?)` — Pfad-Härtung via neuem `_validate_md_write` (wie Lesen, aber Neuanlage erlaubt; `realpath`+`allowed_roots`), Frontmatter-Strukturprüfung (`_validate_frontmatter`: offener, ungeschlossener `---`-Block → `ValueError`), optimistische Konfliktprüfung (Hash bevorzugt, sonst mtime) → `MdConflictError`, atomares Schreiben über `VaultService._atomic_write` (temp+`os.replace`).
  - `backlinks(path)` — Reverse-Scan der Quell-Sammlung, die das Ziel enthält (`_source_root_for`: Vault bzw. Default-Projekt), Wikilink-Matching (`_WIKILINK_RE`, Basisname/rel/Alias/Anker, `_EXCLUDE_DIRS`, Größen-/Anzahl-Cap) — spiegelt die Frontend-Auflösung.
  - Neue Exception `MdConflictError`.
- `app/schemas/md.py`: `MdFileRead` um `mtime`/`hash` erweitert; neu `MdFileSave`, `MdSaveResult`, `MdBacklinksResult`.
- `app/routes/md.py`: `POST /md/file` (200 / 400 Pfad+Frontmatter / 409 Konflikt) · `GET /md/backlinks` (200 / 400 / 404). `GET /md/file` liefert mtime+hash automatisch.

**Tests:** `backend/tests/test_proj12_md_editor.py` — **16/16 grün** (Save-Roundtrip, Neuanlage, ungültiges Frontmatter ohne Datenverlust, Konflikt + force-Bypass + no-conflict, Pfad-Traversal blockiert, Backlinks plain/alias/anchor inkl. Ausschluss Selbst/none/node_modules, API 200/409/400/404). PROJ-7 + Vault-Regression: 41/41 grün.

**API-Contract (Frontend bereits angebunden):**
- `POST /md/file` Body `{ path, content, expected_mtime?, expected_hash?, force? }` → `{ path, mtime, hash }`
- `GET /md/backlinks?path=…` → `{ path, backlinks: [{path, rel, name}] }`

## QA Test Results
**Getestet:** 2026-06-23 · **Branch:** dev · **Tester:** abc-qa (Red-Team)
**Ergebnis:** ✅ **Production-ready** — 0 Critical, 0 High, 0 Medium offen.

### Testumfang / Automatisierung
- Backend: `backend/tests/test_proj12_md_editor.py` — **20/20 grün** (16 Funktion/API + 4 Red-Team).
- Backend-Gesamtsuite (Regression): **375/375 grün**.
- Frontend: Vitest **54/54 grün** (inkl. `splitFrontmatter`/`searchNotes`); ESLint sauber; `tsc --noEmit` ohne neue Fehler (einziger Treffer = vorbestehender PROJ-7-Test-Cast).

### Acceptance Criteria
| # | Kriterium | Status | Beleg |
|---|-----------|--------|-------|
| 1 | Laden (FM+Body) + atomares Speichern an denselben Pfad | ✅ | `save_file` via `_atomic_write`; `test_save_writes_content_and_returns_meta`, `test_api_save_roundtrip` |
| 2 | `[[`-Autocomplete aus MD-Index, Auswahl fügt gültigen Wikilink ein | ✅ | `searchNotes` (Vitest 4 Fälle) + `insertWikilink` (`[[Name]]` am Cursor) |
| 3 | Wikilinks in Vorschau klickbar, navigieren zur Zieldatei | ✅ | Wiederverwendung `MarkdownView`/`resolveWikilink` (PROJ-7), `onNavigate→selectPath` |
| 4 | Backlinks-Panel zeigt referenzierende Dateien | ✅ | `backlinks()` Reverse-Scan; `test_backlinks_finds_linking_notes`, `test_api_backlinks_200` |
| 5 | Umschalten Edit ↔ Vorschau, Body rendert (Tabellen/Code/Headings) | ✅ | `MdEditorPanel` ModeToggle + `MarkdownView`(remark-gfm) |
| 6 | Ungespeicherte Änderungen erkannt + Verlassen-Warnung | ✅ | Dirty-State, `beforeunload`, Navigations-`confirm` im Page-Guard |
| 7 | Schreibziel auf Roots beschränkt, serverseitig geprüft | ✅ | `_validate_md_write` (realpath+allowed_roots); `test_save_traversal_blocked`, `…_dotdot_…`, `…_symlink_…`, `…_non_md_…` |
| 8 | Alle Texte deutsch; Lade-/Fehler-/Speicher-Zustände explizit | ✅ | Toolbar/Toasts/Dialog/Backlinks deutsch; Loading/Fehler/Leer/Gespeichert/Konflikt |

### Edge Cases
| Fall | Status | Beleg |
|------|--------|-------|
| Externe Änderung seit Laden → Konflikt erkennen, nachfragen | ✅ | mtime/Hash → `MdConflictError`/409 + Dialog; `test_save_conflict_when_changed_externally`, `test_api_save_conflict_409` |
| Ungültiges Frontmatter → Validierung, kein Datenverlust | ✅ | `_validate_frontmatter`→400, Datei unverändert; `test_save_invalid_frontmatter_rejected` |
| Wikilink auf nicht existierende Notiz → unaufgelöst markiert | ✅ | `MarkdownView` (durchgestrichen, kein Crash; PROJ-7-Security-Test) |
| Gleichzeitiges Editieren in zwei Tabs → last-write-wins **mit** Warnung | ✅ | Hash-Konflikt → 409 → Dialog „Überschreiben/Neu laden"; `force`-Bypass `test_save_force_overwrites_conflict` |
| Sehr große Datei | ✅ (mit Hinweis) | Vorschau kürzt bei 400K (PROJ-7); Textarea scrollt. Siehe Obs-1 |

### Security-Audit (Red-Team)
- **Pfad-Ausbruch (Write/Read/Backlinks):** absolute Fremdpfade, `../`-Eskalation und `.md`-**Symlinks**, die aus den Roots zeigen, werden über `realpath`+`allowed_roots` blockiert — Ziel außerhalb bleibt unangetastet. ✅
- **Nicht-.md-Überschreiben** (z. B. `config.yaml`) abgelehnt. ✅
- **Datenverlust:** ungültiges Frontmatter schreibt nicht (Datei unverändert). ✅
- **XSS/Injection in Vorschau:** erbt PROJ-7-Härtung (kein `rehype-raw`, `<script>` escaped, `javascript:`-Links neutralisiert). ✅
- **Multi-Tenancy/JWT/RLS:** entfällt (Single-User-Tool, bewusster Stack-Override) — Sicherheitsgrenze ist ausschließlich `allowed_roots`.

### Beobachtungen (keine Bugs)
- **Obs-1 (Low):** Kein explizites Edit-Limit/Hinweis für sehr große Dateien im Editor (Spec: „ggf." optional). Vorschau kürzt; Bearbeitung funktioniert.
- **Obs-2 (by-design):** Backlinks scannen nur die Quell-Sammlung des Ziels (Vault **oder** Default-Projekt) — keine quellenübergreifenden Backlinks. Bewusste MVP-Grenze (Obsidian-typisch vault-scoped).
- **Obs-3 (by-design):** Schreib-Scope = gesamte `allowed_roots` (wie der Lese-Scope, nicht nur der Vault). Für das Single-User-Dev-Tool gewollt.

### Regression-Hinweis (behoben)
- `test_proj7_qa.py::test_ac5_read_only_no_write_route` prüfte die PROJ-7-Invariante „kein Schreib-Endpoint" (`POST /md/file` → 405). PROJ-12 fügt diesen Endpoint **bewusst** hinzu → Test aktualisiert: `/md/index` bleibt schreibmethodenlos (405), `/md/file`-POST liefert bei leerem Body 422. Kein Produktfehler.

### Empfehlung
**READY** — keine Critical/High/Medium-Bugs. Freigabe für `/abc-deploy` empfohlen.

## Deployment
**Deployed:** 2026-06-23 · **Version:** 0.4.0 · **URL:** https://jupiter.auxevo.tech (Doku-Tab → Datei → „Bearbeiten")
**Host:** Dev-VPS host-native (systemd `jupiter-backend`/`jupiter-frontend` + Caddy), Promotion `dev → main` → GitHub-Webhook-Rebuild.

Gemeinsam mit PROJ-9 + PROJ-10 als Sammel-Deploy (Bump 0.3.1 → 0.4.0). Pre-Deploy-Gates grün: Backend 375/375, Next.js-Prod-Build (inkl. TypeScript), Secret-Scan sauber.

**Browser-Smoke (auf Prod zu verifizieren, hinter Basic-Auth):** Datei im Doku-Tab öffnen → „Bearbeiten" → Text ändern (Dirty-Anzeige) → `[[`-Autocomplete → Speichern (Toast) → Vorschau (Wikilinks klickbar) → Backlinks-Panel; zweiter Tab/externe Änderung → 409-Dialog.
