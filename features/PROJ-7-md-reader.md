# PROJ-7: MD-Reader

## Status: In Progress
**Created:** 2026-06-22
**Last Updated:** 2026-06-23

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung) — liefert die MD-Dateien + Suche/Index

## Beschreibung
Doku ohne Tool-Wechsel: Vault-MD im Browser lesen, mit Obsidian-DNA (#16, **read-first**). `[[Wikilinks]]` werden klickbar gerendert; Handovers/Doku zu einer Session sind direkt aufrufbar. Der volle Editor (#16 voll) ist P1.

## User Stories
- Als Nutzer möchte ich Vault-MD-Dateien im Browser lesen, ohne das Tool zu wechseln.
- Als Nutzer möchte ich `[[Wikilinks]]` anklicken, um zwischen Doku-Dateien zu navigieren.
- Als Nutzer möchte ich Handovers/Doku zu einer Session direkt aufrufen.

## Acceptance Criteria
- [ ] MD-Dateien aus dem Vault (über PROJ-2) werden gerendert dargestellt (Headings, Listen, Code, Tabellen).
- [ ] `[[Wikilinks]]` werden als klickbare Links gerendert und navigieren zur Zieldatei (falls vorhanden).
- [ ] Datei-Navigation/Baum, um Vault-MD zu durchstöbern.
- [ ] YAML-Frontmatter wird sauber dargestellt (nicht als roher Text).
- [ ] **Read-only** (Editor = P1).

## Edge Cases
- Wikilink auf nicht-existente Datei → als „fehlend" markiert, kein Crash.
- Sehr große MD-Datei → lädt performant (Lazy/Virtualisierung).
- Nicht-MD-Datei angeklickt → Hinweis statt Fehlversuch.
- Bild-Embeds (`![[bild.png]]`) → Platzhalter (Anzeige = nice-to-have).

## Technical Requirements (optional)
- Markdown-Rendering React-seitig; Wikilink-Auflösung gegen den Vault-Index aus PROJ-2.
- Keine Schreibpfade im MVP (read-only); Architektur hält Editor (#16 voll, P1) offen.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-23 · **Stack:** Next.js 16 (App Router, shadcn/ui) + FastAPI (read-only Datei-I/O, kein DB/RLS im MVP) · **Branch:** dev

> Jupiter-MVP-Abweichung (wie PROJ-2/5): **kein JWT/RLS/Neon**. Der MD-Reader ist **rein lesend**. Er liest Markdown aus den bereits konfigurierten **`allowed_roots`** (`/home/dev/projects`, `/home/dev/tools`) und deckt damit **zwei Quellen** in einem Modell ab: den **Hal-Vault** und die **Projekt-Repos** (Feature-Specs unter `features/`, Doku unter `docs/`). Wiederverwendet wird der vorhandene `realpath`-gegen-`allowed_roots`-Guard aus `validate_project_path` (`engine/manager.py:68`) sowie der Frontmatter-Parser aus PROJ-2 (`engine/vault.py`).

### Browse-Scope (User-Entscheidung 2026-06-23)
Der Baum zeigt **beide Quellen**:
- **Vault** — der ganze Hal-Vault read-only (konsistent mit dem vault-weiten Lese-/Such-Scope aus PROJ-2).
- **Projekt** — das ausgewählte Projekt unter `/home/dev/projects/<name>` (z. B. `jupiter`), mit dem **`features/`-Ordner default aufgeklappt**, weil die Feature-Specs am häufigsten gelesen werden.

### A) Komponenten-Struktur (Frontend, Next.js App Router)
```
DocReaderPage  (app/(cockpit)/doku/page.tsx — Client Component, liest ?source & ?path aus der URL → deep-linkbar)
├── SourceSwitcher        (shadcn Tabs: „Vault" | „Projekt")
├── FileTree (links)      (ScrollArea; aus dem flachen Index gebaut; Vault → „Agentic OS/Jupiter/" & Projekt → „features/" default expanded)
│   ├── TreeFolder        (aufklappbar)
│   └── TreeFile          (.md-Dateien; Klick → setzt ?path=…)
├── MarkdownViewer (Haupt)
│   ├── FrontmatterPanel  (shadcn Card: YAML als saubere Key/Value-Tabelle — NICHT als Rohtext)
│   ├── MarkdownBody      (react-markdown + remark-gfm + Wikilink-Plugin)
│   │   ├── WikiLink      ([[Ziel]] → klickbarer Link auf ?path=<aufgelöst>; fehlend → grau/„fehlend"-Stil, kein Crash)
│   │   └── ImageEmbed    (![[bild.png]] → Platzhalter im MVP)
│   └── States            (Loading / Error / Empty / „keine MD-Datei"-Hinweis — reuse components/cockpit/states.tsx)
└── (optional) SearchBar  (nutzt bestehendes GET /vault/search)
```
**Navigations-Einstieg:** „Doku"-Link im Kopf der `SessionRail` (`components/cockpit/session-rail.tsx`). Zusätzlich **Deep-Link aus der Session-Detail-Seite**: das in PROJ-5 geschriebene Handover liefert einen Pfad-Pointer (`VaultWriteResult.path`) → Link auf `/doku?source=vault&path=<pfad>` erfüllt „Handover/Doku zu einer Session direkt aufrufen".

### B) Datenmodell (Klartext)
**Kein DB-Schema** — reine Datei-Lese-Operationen. Zwei logische Lese-Quellen, beide innerhalb der `allowed_roots`:

| Quelle | Wurzel | Default-Fokus | Schreibzugriff |
|--------|--------|---------------|----------------|
| **Vault** | `/home/dev/tools/Hal` (`vault_root`) | `Agentic OS/Jupiter/` (Sessions/, Handovers/) | nein (read-only) |
| **Projekt** | `/home/dev/projects/<projekt>` | `features/` (Feature-Specs) | nein (read-only) |

Pro gelesener Datei liefert der Dienst (wie PROJ-2 schon) **getrennt**: `frontmatter` (geparstes YAML als Objekt) + `body` (Markdown). Das Frontend rendert das Frontmatter als Metadaten-Panel, den Body als Markdown.

### C) API-Form (nur Endpunkte, kein Code)
Neuer **read-only**-Router `routes/md.py` (MD-Reader), getrennt von PROJ-2s schreibendem `vault.py`, damit dessen Schreib-/Vault-Semantik unangetastet bleibt:
```
GET /md/sources                              → verfügbare Quellen [{id:"vault"|"project", label, root}]
GET /md/index?source=vault                   → flache Liste aller .md im Vault  [{path, name}]  → Baum + Wikilink-Index
GET /md/index?source=project&project=<pfad>  → flache Liste aller .md im Projekt [{path, name}]
GET /md/file?path=<pfad>                      → liest EINE .md → {path, frontmatter, body, content}
```
- Lesen/Index sind **immer** gegen `allowed_roots` validiert (realpath-Guard, exakt wie `validate_project_path`). Pfad außerhalb → 400, nicht-`.md` → klarer Hinweis statt Fehlversuch.
- **Suche** bleibt im MVP das bestehende vault-weite `GET /vault/search` (PROJ-2). Suche über Projekt-Repos ist Non-Goal/P1.
- Der Frontend baut **Baum** (Gruppierung der flachen Pfadliste nach Ordner) **und** **Wikilink-Index** (Basename → Pfad) aus derselben `/md/index`-Antwort — eine Quelle, kein zweiter Endpunkt nötig.

### D) Tech-Entscheidungen (warum)
- **`allowed_roots` als gemeinsamer Lese-Scope.** Vault **und** Projekt-Specs liegen beide schon in den erlaubten Roots — der Reader braucht keinen neuen Sicherheits-Scope, sondern wiederverwendet `validate_project_path`. Das ist die kleinste sichere Erweiterung und konsistent mit PROJ-1/PROJ-2.
- **Eigener `md.py`-Router statt Aufbohren von `vault.py`.** PROJ-2s `vault.py` mischt Lesen **und** Schreiben (Schreiben streng auf den Jupiter-Unterbaum begrenzt). Ein dedizierter **read-only** Reader-Router hält diese Schreib-Härtung sauber getrennt und macht den Reader trivially sicher (kein Schreibpfad existiert). Die Frontmatter-Parser-/Slug-Helfer aus `engine/vault.py` werden als reine Funktionen wiederverwendet (kein Duplikat).
- **Ein flacher Index statt Lazy-Tree-Endpoint.** Bei einem persönlichen Vault/Repo (hunderte, nicht Millionen `.md`) genügt eine flache Pfadliste; Frontend baut Baum **und** Basename→Pfad-Wikilink-Map daraus. Spart einen zweiten Endpoint und macht Wikilink-Auflösung sofort lokal/synchron.
- **Markdown-Rendering client-seitig mit `react-markdown` + `remark-gfm`** (Headings, Listen, Code, **Tabellen**, Task-Lists — deckt das AC ab). **Kein Roh-HTML** → standardmäßig kein `dangerouslySetInnerHTML`, damit XSS aus fremden Vault-Dateien ausgeschlossen ist (Sicherheits-Entscheidung; falls je Roh-HTML gewünscht, dann nur mit `rehype-sanitize`).
- **Wikilinks via kleines remark-Plugin** (oder `remark-wiki-link`): `[[Ziel]]` → Lookup im Basename-Index. Treffer → klickbarer Link auf `?path=…` (gleiche Quelle zuerst, dann Cross-Source-Fallback). Kein Treffer → als „fehlend" markiert, **kein Crash** (Edge-Case).
- **Frontmatter als Panel, nicht als Rohtext** (AC): das Backend liefert es bereits geparst getrennt vom Body — das Frontend rendert nur eine Key/Value-Tabelle.
- **Deep-linkbare URL (`?source=&path=`).** Macht Wikilink-Navigation, Browser-Back und das „Handover zu Session aufrufen" (Deep-Link aus PROJ-5) ohne globalen State möglich.
- **Edge-Cases:** sehr große Datei → Viewer lädt **nur die eine** Datei; react-markdown rendert den ganzen Body (für MVP-Größen ok, Windowing/Virtualisierung als späterer Seam notiert). Bild-Embeds → Platzhalter (Anzeige = nice-to-have). Nicht-`.md` → Hinweis. Read-only erzwungen (kein Schreibpfad im Router).

### E) Abhängigkeiten
- **Frontend (neu):** `react-markdown` (MD-Rendering), `remark-gfm` (Tabellen/Task-Lists/Autolinks), Wikilink-Handling (`remark-wiki-link` **oder** ein ~30-Zeilen-Eigen-Plugin für volle Kontrolle über „fehlend"-Stil + Navigation). **Optional:** `rehype-highlight` oder `shiki` für Code-Syntax-Highlighting (nice-to-have).
- **Backend:** **keine neuen Pakete** — reine Datei-I/O, wiederverwendet `validate_project_path` + den Frontmatter-Parser aus PROJ-2.
- **Config:** keine zwingende neue Setting. Optional `reader_default_project` (Default = Jupiter-Repo) bzw. die „Projekt"-Quelle leitet sich aus dem `project_path` der aktiven Session ab (`schemas/sessions.py`).

### Hinweis für /abc-frontend & /abc-backend
- **Backend zuerst** (Reader braucht den Index): neuer Router `routes/md.py` + Schemas `schemas/md.py` (`MdSource`, `MdIndexEntry`, `MdFileRead` — letzteres kann `VaultFileRead` spiegeln). In `main.py` registrieren (Muster: `vault.py`). Lese-/Index-Validierung gegen `allowed_roots` via `validate_project_path`-Muster; Frontmatter-Helfer aus `engine/vault.py` importieren statt duplizieren.
- **Frontend** danach: Route `app/(cockpit)/doku/page.tsx`, API-Methoden in `lib/api.ts` (`listMdSources`, `getMdIndex`, `readMdFile`), Typen in `lib/types.ts`. „Doku"-Link in `session-rail.tsx`; Deep-Link aus `sessions/[id]/page.tsx` auf das Handover-Pfad-Pointer.

### Implementation Notes (Backend Developer)
**Datum:** 2026-06-23 · **Branch:** dev · **Stand:** Backend fertig, Frontend + QA ausstehend · **Tests:** `pytest` → **205 grün** (15 neue für PROJ-7, keine Regression).

**Gebaute Teile (rein lesend, kein Schreibpfad):**
- **`engine/md_reader.py` — `MdReaderService`**: `sources()`, `resolve_source_root()`, `index()`, `read_file()`. Liest MD über die `allowed_roots`; deckt Vault + Projekt in einem Modell ab. Frontmatter via wiederverwendetem `_parse_frontmatter` aus `engine/vault.py` (kein Duplikat).
- **Pfad-Härtung**: `_validate_dir` / `_validate_md_file` spiegeln das `realpath`-+-erlaubte-Wurzel-Muster aus `validate_project_path` (`manager.py`). Lesen nur innerhalb `allowed_roots`, nur `.md`, nur reguläre Dateien.
- **Pfad-Schema = absolut**: `/md/index` liefert je Datei `{path (absolut), rel (relativ zur Wurzel, für Baum), name (Basisname, für Wikilinks)}`. `/md/file?path=<absolut>` validiert erneut gegen `allowed_roots`. Der Frontend baut Baum **und** Wikilink-Index (Basename→Pfad) aus einer einzigen `/md/index`-Antwort.
- **API (`routes/md.py`)**: `GET /md/sources`, `GET /md/index?source=vault|project[&project=<pfad>]`, `GET /md/file?path=<pfad>`. In `main.py` als `app.state.md_reader` + Router registriert (Muster `vault.py`).
- **Schemas (`schemas/md.py`)**: `MdSource`, `MdIndexEntry`, `MdIndexResult`, `MdFileRead` (spiegelt `VaultFileRead`).
- **Config**: `reader_default_project` (`JUPITER_READER_DEFAULT_PROJECT`, Default `/home/dev/projects/jupiter`) — pro Request via `?project=` überschreibbar.

**Sicherheit/Edge-Cases (getestet):** Pfad außerhalb `allowed_roots` (`/etc/passwd`, `/etc/hosts`) → `ValueError`/400; **Symlink-Escape** im Index → übersprungen (realpath-Guard, Exfiltration-Schutz); Nicht-`.md` → 400; fehlende Datei → 404; unbekannte Quelle → 400. Index überspringt `node_modules`/`.git`/`.next`/`__pycache__` u. a. + cappt bei 10 000 Dateien (DoS-Schutz).

**Offen / Hinweis für QA & Frontend:**
- **Suche** über Projekt-Repos ist Non-Goal (MVP nutzt das vault-weite `GET /vault/search`).
- **Wikilink-Auflösung, Rendering (react-markdown), Frontmatter-Panel, „fehlend"-Stil, Bild-Platzhalter** sind Frontend-Themen (PROJ-7-Frontend) — Backend liefert nur Index + Roh-MD + getrenntes Frontmatter.
- **Streaming/Windowing** für sehr große MD nicht umgesetzt (ganze Datei im RAM); für MVP-Größen unkritisch, Seam offen (analog QA-2.2 PROJ-2).

### Implementation Notes (Frontend Developer)
**Datum:** 2026-06-23 · **Branch:** dev · **Stand:** Frontend fertig, QA ausstehend · **Stack:** Next.js 16 (App Router) · **Checks:** `vitest` → **30 grün** (8 neue), `eslint` sauber, `next build` grün, Live-Smoke gegen Backend ok.

**Gebaute Teile:**
- **Route `app/(cockpit)/doku/page.tsx`** (Client, in `<Suspense>` wegen `useSearchParams`): Quellen-Umschalter (shadcn `Tabs`), Datei-Baum links, Viewer rechts. Deep-linkbar via `?source=&path=` sowie `?source=vault&rel=…` (vault-relativer Handover-Pointer aus PROJ-5). Lädt beide Quell-Indizes einmal → Cross-Source-Wikilinks.
- **`lib/md-tree.ts`** (rein, getestet): `buildTree` (flacher Index → Ordnerbaum, Ordner vor Dateien, alphabetisch), `buildWikilinkIndex` + `resolveWikilink` (Basename **und** rel-Pfad, case-insensitiv, `#anchor` ignoriert).
- **`lib/remark-wikilink.ts`**: kleines remark-Plugin (ohne Zusatz-Dep) — `[[Ziel|Alias]]` → `wikilink:`-Link, `![[bild]]` → `wikiembed:`-Link. Fasst Code-/Inline-Code nie an, erzeugt keine verschachtelten Links.
- **`components/cockpit/markdown-view.tsx`**: `react-markdown` + `remark-gfm`; Link-Renderer löst `wikilink:` gegen den Index auf → Navigation oder durchgestrichener „fehlend"-Stil; `wikiembed:`/`<img>` → Platzhalter-Badge. **Kein Roh-HTML** (XSS-Schutz, react-markdown-Default).
- **`components/cockpit/frontmatter-panel.tsx`**: YAML-Frontmatter als Key/Value-`<dl>` (kein Rohtext).
- **`components/cockpit/file-tree.tsx`**: ausklappbarer Baum; Default-Expand `features/` (Projekt) bzw. `Agentic OS/Jupiter/(Handovers)` (Vault).
- **API/Typen**: `listMdSources`/`getMdIndex`/`readMdFile` in `lib/api.ts`, `MdSource`/`MdIndexEntry`/`MdIndexResult`/`MdFileRead` in `lib/types.ts`.
- **Navigation**: „📄 Doku"-Link in der `SessionRail`; HandoverDialog verlinkt den gespeicherten Pfad mit „Im Reader öffnen →".
- **Styling**: `.md-body`-Block in `globals.css` (Headings/Listen/Code/**Tabellen**/Blockquote/HR), da kein `@tailwindcss/typography` vorhanden.
- **Deps (neu):** `react-markdown`, `remark-gfm`.

**AC-Abdeckung:** Rendering inkl. Tabellen ✓ · klickbare Wikilinks + „fehlend"-Markierung ✓ · Datei-Baum ✓ · Frontmatter-Panel ✓ · read-only ✓ · Bild-Embeds → Platzhalter ✓ · Nicht-MD → erscheint nicht im Baum / Backend 400.

**Offen für QA:** Code-Syntax-Highlighting (Plain-`<pre>`, kein Shiki — nice-to-have); Windowing für sehr große Dateien (Seam offen); Suche-UI nicht eingebaut (Backend `/vault/search` vorhanden, P1).

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
