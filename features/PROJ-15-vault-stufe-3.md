# PROJ-15: Vault Stufe 3 — lebendes Gehirn + roh↔kuratiert + Kuratierung

## Status: Deployed
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Bausteine:** #9, #10, #11

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung als Dienst) — baut auf lesen/schreiben/suchen im Hal-Vault auf.
- Requires: PROJ-4 (Decision Cards) — die Kuratierung nutzt denselben Freigabe-Flow.
- Verwandt: PROJ-5 (Handover) — Handovers sind eine Quelle kuratierten Wissens; PROJ-17 (Recovery) liest aus denselben Schichten.

## Beschreibung
Der Vault wird vom passiven Log-Ablageort zum **lebenden Gehirn**: Agenten lesen aktiv aus dem Vault und schreiben strukturierte Spuren zurück, projektübergreifend durchsuchbar — und bleibt offenes, lesbares MD. Zwei Schichten werden klar getrennt: **rohe Logs** (vollständig, Audit) ↔ **kuratiertes Wissen** (Entscheidungen, Lösungen, Sackgassen, Muster). **Kuratierung** ist ereignisgetrieben: ein Trigger (Bug gelöst, ADR gefallen, Sackgasse verworfen) erzeugt einen **Wissens-Vorschlag**, den der Nutzer per Card freigibt/editiert.

## User Stories
- Als Nutzer möchte ich, dass Agenten relevantes Vault-Wissen aktiv lesen, damit Lösungen nicht doppelt erarbeitet werden.
- Als Nutzer möchte ich rohe Session-Logs und kuratiertes Wissen klar getrennt im Vault haben, damit der „Kopf-Index" sauber bleibt.
- Als Nutzer möchte ich, dass aus erkannten Ereignissen (Bug gelöst, ADR, Sackgasse) automatisch ein **Wissens-Vorschlag** entsteht.
- Als Nutzer möchte ich jeden Wissens-Vorschlag per Decision Card **freigeben, editieren oder verwerfen**, bevor er ins kuratierte Wissen wandert.
- Als Nutzer möchte ich projektübergreifend im kuratierten Wissen suchen können.

## Acceptance Criteria
- [ ] **Zwei Schichten** mit fester Vault-Struktur: rohe Logs (vollständig) vs. kuratiertes Wissen (destilliert); beide offenes MD, direkt les-/editierbar.
- [ ] Agenten können Vault-Inhalte **lesen und strukturierte Spuren zurückschreiben** (über den PROJ-2-Dienst), ohne Bestehendes zu überschreiben.
- [ ] **Kuratierungs-Trigger** (mind.: Bug gelöst, ADR/Entscheidung gefallen, Sackgasse verworfen) erzeugen einen Wissens-Vorschlag.
- [ ] Ein Vorschlag erscheint als **Decision Card** (PROJ-4-Flow) mit Aktionen Freigeben / Editieren / Verwerfen.
- [ ] Freigegebenes Wissen landet als kuratierte MD-Notiz an definierter Stelle; verworfenes wird nicht geschrieben (nur im Roh-Log dokumentiert).
- [ ] **Suche** über kuratiertes Wissen liefert projektübergreifende Treffer mit Pfad/Backlink.
- [ ] Vault-Schreibvorgänge sind nachvollziehbar (owner-Feld, Zeitstempel) und idempotent.
- [ ] Alle Texte deutsch.

## Edge Cases
- **Doppelter Wissens-Vorschlag** (gleiches Thema) → Duplikat erkennen, an bestehende Notiz anhängen statt neu anlegen.
- **Trigger feuert zu oft** (Geschwätzigkeit) → Entprellung/Schwelle, damit keine Card-Flut entsteht.
- **Nutzer editiert Vorschlag** → editierte Fassung wird geschrieben, Original-Roh-Log bleibt unverändert.
- **Konflikt mit manuell editierter Notiz** → nicht blind überschreiben; anhängen/nachfragen.
- **Vault temporär nicht schreibbar** → Vorschlag in Warteschlange, sichtbarer Hinweis, kein Verlust.
- **Sehr großes Roh-Log** → Pointer/Ausschnitt statt Volltext im kuratierten Wissen (zahlt auf PROJ-19/#23 ein).

## Technical Requirements (optional)
- Nutzt den PROJ-2-Vault-Dienst (lesen/schreiben/suchen); Struktur passt ins bestehende Hal-PARA-Layout.
- Kuratierung ereignisgetrieben über erkannte Marker im Session-Stream; Entprellung serverseitig.
- Suche: einfacher Index über kuratierte Notizen (Volltext/Frontmatter), erweiterbar Richtung RAG (PROJ-19).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** FastAPI + Filesystem-MD (Hal-Vault, kein DB/RLS im MVP) · Next.js 16 Cockpit (bestehend) · **Branch:** dev

> Jupiter-Overrides gelten weiter: Next.js statt Flutter, kein JWT/RLS im MVP (single-user, `owner` serverseitig gestempelt). PROJ-15 ist **rein additiv** auf zwei vorhandenen Seams: dem **Vault-Dienst** (PROJ-2, `engine/vault.py` — Schreiben gekapselt auf `Agentic OS/Jupiter/**`, Lesen/Suchen vault-weit) und dem **Decision-Card-Flow** (PROJ-4, `engine/decisions.py` + `manager.py` + `routes/sessions.py`). Beide existieren bereits und müssen nur erweitert werden — kein neuer Daemon, kein neues Paket.

### Kernidee in zwei Sätzen
Eine **dritte Vault-Schicht `Knowledge/`** (kuratiert) tritt neben die vorhandenen `Sessions/` (roh) und `Handovers/`. Während eine Session läuft, scannt der Engine-Layer den Assistenten-/Denk-Strom auf **Kuratierungs-Marker** (Bug gelöst, ADR/Entscheidung, Sackgasse); ein Treffer erzeugt — entprellt — eine **nicht-blockierende Wissens-Vorschlags-Card** (PROJ-4-UI), die der Nutzer **freigeben / editieren / verwerfen** kann; bei Freigabe wird eine kuratierte MD-Notiz nach `Knowledge/` geschrieben, projektübergreifend durchsuchbar.

### A) Komponenten-Struktur

**Backend (additiv im bestehenden Engine-Layer):**
```
Vault-Schicht (PROJ-2, erweitert)
├── engine/vault.py
│   ├── _TYPE_DIRS += {"curated": "Knowledge"}        ← dritte Schicht, neben Sessions/ + Handovers/
│   ├── write_curated_note(...)                        ← Convenience wie write_session_log(); type="curated"
│   │     · Dedup: gleicher slug/Thema existiert → on_exists="append" (nie blind überschreiben)
│   └── search(query, subdir="Knowledge", limit)       ← bestehende Suche, optional auf Knowledge/ gefiltert
│
Kuratierung (NEU, ereignisgetrieben)
├── engine/curation.py (neu, reine Funktionen — testbar wie policy.py)
│   ├── detect_marker(text|thinking) -> Marker|None    ← erkennt "bug gelöst" / "ADR/Entscheidung" / "Sackgasse"
│   ├── build_proposal(marker, source) -> (title, body)← destilliert Vorschlag (Pointer/Ausschnitt statt Volltext)
│   └── proposal_slug(marker) -> str                   ← Dedup-Schlüssel (Themen-Slug)
├── engine/manager.py
│   ├── handle_event(): nach extract_text/extract_thinking → detect_marker()
│   │     · Entprellung: self._seen_markers:set + Mindest-Schwelle → keine Card-Flut
│   │     · Treffer → request_knowledge_card()          ← NICHT-blockierend (keine asyncio.Future)
│   └── resolve_decision(): dispatch auf card_type=="knowledge_proposal"
│         · approve            → vault.write_curated_note(title, body, source_session_id)
│         · approve + edits    → editierte Fassung schreiben (Roh-Log unberührt)
│         · deny (verwerfen)   → nichts in Knowledge/ (nur im Roh-Log dokumentiert)
│         · Vault nicht schreibbar → Card bleibt offen + Fehlerhinweis (kein Verlust)
└── engine/decisions.py
    └── card_type += "knowledge_proposal"; Felder proposal_title, proposal_body (editierbar)
│
API → routes/sessions.py
└── POST /sessions/{id}/decisions/{decision_id}  (bestehend, erweitert):
      body zusätzlich { edited_title?, edited_body? } für die Editier-Aktion
└── GET  /vault/search?q=&scope=curated          (routes/vault.py, erweitert um scope)
```

**Frontend (Erweiterung des bestehenden Cockpits, kein neues Paket):**
```
components/cockpit/decision-card.tsx (PROJ-4, erweitert)
└── card_type "knowledge_proposal" Variante:
    ├── Badge „Wissens-Vorschlag" (eigene Farbe, NICHT orange/Freigabe-blockierend)
    ├── Vorschau: Titel + kuratierter Body (MD)
    └── Aktionen [Freigeben] [Editieren] [Verwerfen]
        └── Editieren → Textarea (Titel + Body) → approve mit edited_*
components/cockpit/  (Suche über kuratiertes Wissen — projektübergreifend)
└── Treffer mit Pfad + Backlink in den Vault (nutzt bestehende MD-Reader-Route)
```

### B) Datenmodell (Klartext)
**Kein DB-Schema** — wie PROJ-2 reine MD-Dateien.

**Kuratierte Notiz** (`Agentic OS/Jupiter/Knowledge/<datum>--<themen-slug>.md`), valides Obsidian-MD mit Frontmatter:
```
owner             – serverseitig gestempelt (MVP "dev")           [#21, Nachvollziehbarkeit]
type              – "curated"
created           – ISO-Zeitstempel
source_session_id – aus welcher Session der Vorschlag stammt       (Nachvollziehbarkeit)
curation_marker   – "bug_geloest" | "adr" | "sackgasse"
title             – Themen-Titel (Dedup-Basis)
```
Body = destillierter Vorschlag: **Pointer/Ausschnitt** auf das Roh-Log (`Sessions/…`), **nicht** der Volltext (Edge-Case „sehr großes Roh-Log"; zahlt auf PROJ-19 ein).

**Wissens-Vorschlags-Card** (nur im Speicher, wie PendingDecision): `card_type="knowledge_proposal"`, **ohne** `asyncio.Future` → blockiert die Session nicht (die Session läuft weiter, die Card wartet sichtbar). Trägt `proposal_title` + `proposal_body` (editierbar vor Freigabe).

### C) API-Form (nur Endpunkte, kein Code)
```
POST /sessions/{id}/decisions/{decision_id}   (bestehend)
        body = { decision: "approve" | "deny", edited_title?, edited_body? }
        approve            → kuratierte Notiz nach Knowledge/ geschrieben
        approve + edited_* → editierte Fassung geschrieben (Roh-Log unberührt)
        deny               → verworfen, nichts in Knowledge/
GET  /vault/search?q=<query>&scope=curated|all   (erweitert)
        scope=curated → nur Knowledge/ (projektübergreifend) → [Pfad, Ausschnitt, Backlink]
GET  /sessions  +  WS /sessions/{id}/stream      (bestehend)
        liefern Wissens-Vorschlags-Cards via pending_decisions (kein Extra-Request)
```
- Roh-Logs entstehen weiterhin automatisch (PROJ-2-Hook); kuratierte Notizen **nur** nach Nutzer-Freigabe.
- Schreiben bleibt auf `Agentic OS/Jupiter/**` gekapselt (Pfad-Guard aus PROJ-2 gilt unverändert).

### D) Tech-Entscheidungen (warum)
- **`Knowledge/` als dritte Schicht statt neuer Mechanik.** `engine/vault.py` ist bereits polymorph über `type` (`_TYPE_DIRS`); eine kuratierte Schicht ist ein Eintrag + eine Convenience-Methode. Roh↔kuratiert ist damit eine **Dateisystem-Grenze** (Sessions/ vs. Knowledge/), beide offenes, in Obsidian les-/editierbares MD — erfüllt das AC „zwei Schichten" sauber, ohne den Kopf-Index zu verschmutzen.
- **Nicht-blockierende Card statt neuer UI.** Der PROJ-4-Flow kennt bereits **futurelose** Cards (die Deny-Notiz-Cards). Ein Wissens-Vorschlag ist genau diese Klasse: sichtbar, einzeln auflösbar, **ohne** die Session anzuhalten (Kuratierung darf nie blockieren). Wir erben Rendering, Polling/WS-Surfacing und den `resolve`-Endpunkt — minimaler Neubau, klare Trennung von Freigabe-blockierenden Cards (orange) durch eine eigene Card-Farbe.
- **Marker-Erkennung im vorhandenen Event-Strom.** `manager.handle_event` extrahiert bereits Assistenten-Text **und** Denk-Block (`extract_text`/`extract_thinking`). Die Marker-Erkennung hängt sich dort an — keine zweite Pipeline. Erkennung als **reine Funktionen** in `engine/curation.py` (testbar wie `policy.py`), nicht in den Manager verdrahtet.
- **Entprellung serverseitig.** Ein `_seen_markers`-Set (Themen-Slug) + Mindestschwelle verhindert die Card-Flut (Edge-Case „Trigger feuert zu oft"). Marker-Heuristik bleibt im MVP einfach/konservativ (Schlüsselwort-/Phrasen-basiert); ein LLM-Klassifikator ist explizit RAG-Ausbau (PROJ-19), hier Non-Goal.
- **Dedup = anhängen, nie überschreiben.** Existiert eine Knowledge-Notiz gleichen Themen-Slugs, schreibt `write_curated_note` mit `on_exists="append"` (PROJ-2-Lock-Mechanik) — deckt „doppelter Vorschlag" und „Konflikt mit manuell editierter Notiz" ab. Der atomare temp+`rename`-Write von PROJ-2 garantiert Idempotenz/keine Korruption.
- **Pointer statt Volltext.** Die kuratierte Notiz verweist per Backlink auf das Roh-Log statt es zu kopieren (Token-Disziplin PROJ-6, Edge-Case großes Log, Vorbereitung RAG PROJ-19).
- **Aktives Lesen nutzt die bestehende PROJ-2-Leseschicht.** Agenten lesen/suchen den Vault bereits vault-weit (read-only) über den PROJ-2-Dienst; PROJ-15 fügt die **strukturierte Rückschreib-Schicht** (Knowledge/) + die **kuratierte, projektübergreifende Suche** (`scope=curated`) hinzu. Das Einspeisen relevanten Wissens beim Session-Start bleibt dem Smart Launcher (PROJ-9) überlassen — kein Doppelbau.
- **Vault temporär nicht schreibbar → Card bleibt offen.** Schlägt der Write fehl, wird die Card **nicht** aufgelöst, sondern zeigt einen Fehlerhinweis (analog PROJ-4 „Fehler beim Zurückspielen") — der Vorschlag geht nicht verloren (Edge-Case Warteschlange).

### E) Abhängigkeiten
- **Keine neuen Pakete.** Reine Datei-I/O (PROJ-2) + bestehende Card-/Event-Infrastruktur (PROJ-4). Frontend: bestehende shadcn-Primitives (Card, Badge, Button, Textarea).
- Optionale Config (Muster wie PROJ-2/PROJ-4): `enable_curation` (Default an), `curation_markers` (Phrasen-Liste, überschreibbar), `curation_debounce` (Mindestschwelle).

### Mapping AC → Bausteine
| AC | Umsetzung |
|----|-----------|
| Zwei Schichten roh↔kuratiert, beide offenes MD | `Sessions/` (PROJ-2) + neue `Knowledge/`-Schicht (`_TYPE_DIRS`) |
| Agenten lesen + strukturierte Spuren zurück, ohne zu überschreiben | PROJ-2-Leseschicht + `write_curated_note` mit `on_exists="append"` |
| Kuratierungs-Trigger (Bug/ADR/Sackgasse) → Vorschlag | `engine/curation.py:detect_marker` im `handle_event` |
| Vorschlag als Decision Card mit Freigeben/Editieren/Verwerfen | `card_type="knowledge_proposal"` (futurelos) im PROJ-4-Flow |
| Freigegeben → MD an definierter Stelle; verworfen → nicht geschrieben | `resolve_decision`-Dispatch → `write_curated_note` bzw. no-op |
| Suche kuratiert, projektübergreifend, Pfad/Backlink | `GET /vault/search?scope=curated` |
| Nachvollziehbar (owner/Zeitstempel) + idempotent | Frontmatter `owner`/`created`/`source_session_id` + atomarer Write/append |
| Alle Texte deutsch | UI + Notiz-Templates deutsch |

### Handoff
1. **Backend (`/abc-backend`):** `engine/curation.py` (Marker-Erkennung, Vorschlags-Destillation, Slug); `vault.write_curated_note` + `_TYPE_DIRS["curated"]`; `vault.search(scope)`; `manager.handle_event` Marker-Hook + Entprellung; `card_type="knowledge_proposal"` (futurelos) + `resolve_decision`-Dispatch; `decisions.py`-Felder; `routes/sessions.py` Decision-Body um `edited_*`; `routes/vault.py` `scope`-Param. Tests wie `test_proj4_*`/`test_proj2_*`.
2. **Frontend (`/abc-frontend`):** `decision-card.tsx` Variante „Wissens-Vorschlag" (eigene Farbe, Editieren-Textarea, Freigeben/Editieren/Verwerfen); kuratierte Suche (Treffer + Backlink) im Cockpit; `lib/api.ts` Decision-Call um `edited_*`.
3. **QA (`/abc-qa`):** AC + Edge-Cases (Doppelvorschlag→append, Geschwätzigkeit→Entprellung, Editieren→Roh-Log unberührt, Konflikt→nie überschreiben, Vault nicht schreibbar→Card bleibt, großes Log→Pointer); Red-Team: kuratierte Suche leakt keine fremden Schreibbereiche, Card-Approve schreibt nur in `Knowledge/`.

## Implementation Notes (Backend Developer)
**Datum:** 2026-06-24 · **Branch:** dev · **Env:** conda `Dashboard` · **Stand:** Backend fertig, QA ausstehend · **Tests:** `pytest` → **407 grün** (16 neue in `test_proj15_curation.py`, keine Regression — inkl. paralleler PROJ-16/PROJ-21-Suiten).

### Gebaute Teile (rein additiv auf PROJ-2-Vault + PROJ-4-Card-Flow)
- **`engine/vault.py`** — dritte Schicht `curated` → `_TYPE_DIRS["curated"] = "Knowledge"`. `write()` um `extra_meta` (zusätzliche Frontmatter-Felder) + `dated` (themen-stabiler Dateiname ohne Datums-/ID-Präfix) erweitert. Neu: **`write_curated_note(...)`** (schreibt nach `Knowledge/`, `dated=False` → gleicher Titel = gleiche Datei = **Append-Dedup**, nie blindes Überschreiben; Frontmatter `type=curated`, `source_session_id`, `curation_marker`) und **`search_curated()`** (Suche auf `Knowledge/` eingegrenzt; `search()` nimmt jetzt optional `subdir`).
- **`engine/curation.py` (NEU)** — reine Funktionen: `detect_marker` (Bug gelöst / ADR / Sackgasse, konservative Phrasen-Heuristik), `build_proposal` (Titel = Themen-Slug pro Marker+Projekt → Dedup-Basis; Body = gekappter Auszug + Quell-Pointer aufs Roh-Log, **kein Volltext**), `proposal_title`.
- **`engine/decisions.py`** — `card_type` erweitert um `knowledge_proposal`; neue editierbare Felder `proposal_title`/`proposal_body` (+ `to_read`).
- **`engine/manager.py`** —
  - `SessionRuntime._maybe_propose_knowledge()` hängt sich an den bestehenden Assistenten-/Denk-Strom in `handle_event` (kein zweiter Parser); **Entprellung** über `_seen_markers` (je Marker-Art max. 1 Vorschlag/Session).
  - **Nicht-blockierende Card:** der Vorschlag wird wie eine futurelose Notiz in `pending` gehängt — **kein** `asyncio.Future`, **kein** `awaiting_approval`; die Session läuft weiter.
  - `SessionRuntime.resolve_knowledge()` (Freigeben/Editieren/Verwerfen): bei Freigabe schreibt der Vault-Writer **vor** dem Auflösen — schlägt er fehl, **bleibt die Card offen** (kein Verlust). `SessionManager.resolve_decision()` dispatcht knowledge-Cards dorthin; `_write_curated_note()` persistiert (owner/Quelle/Marker gestempelt).
  - `send_input`-Guard verfeinert: nicht-blockierende `knowledge_proposal`-Cards sperren die Eingabe **nicht** (nur echte Freigabe-Cards tun das weiterhin).
- **`config.py`** — `enable_curation` (Default an).
- **API:** `routes/sessions.py` — Decision-Body um `edited_title`/`edited_body`; Vault-Schreibfehler → **503** (Card bleibt offen). `routes/vault.py` — `GET /vault/search?scope=all|curated`. Schemas: `PendingDecisionRead` (+`proposal_*`), `DecisionResolve` (+`edited_*`), `VaultType` (+`curated`).

### AC-Abdeckung (Tests)
Zwei Schichten roh↔kuratiert ✓ · Lesen/Rückschreiben ohne Überschreiben (Append-Dedup) ✓ · Trigger Bug/ADR/Sackgasse ✓ · Decision-Card Freigeben/Editieren/Verwerfen ✓ · freigegeben→`Knowledge/`, verworfen→nichts ✓ · projektübergreifende kuratierte Suche mit Pfad/Backlink ✓ · Nachvollziehbarkeit (owner/created/source_session_id) + idempotent (atomarer Write/Append) ✓ · deutsch ✓.
Edge-Cases getestet: Doppelvorschlag→Append, Geschwätzigkeit→Entprellung, Editieren, Vault nicht schreibbar→Card bleibt offen (503), Eingabe nie gesperrt.

### Offen / Hinweise für QA & Deploy
- **Kein Git-Commit gesetzt (bewusst):** `manager.py`, `config.py`, `schemas/sessions.py` tragen im geteilten `dev`-Working-Tree gleichzeitig **PROJ-16-Watchdog** (Parallel-Agent). Ein sauberer feature-isolierter Commit war ohne Mit-Einsacken der Fremdarbeit nicht möglich → Code liegt getestet im Working Tree; Promotion koordiniert `abc-deploy`/Nutzer.
- **Marker-Heuristik bewusst einfach** (Phrasen). Semantischer Klassifikator = RAG-Ausbau PROJ-19 (Non-Goal hier).
- **Cross-Day-Dedup:** Themen-Datei ist datumslos → echte Dedup über Tage hinweg; sehr großer Body wird als Auszug+Pointer kuratiert (kein Volltext).
- **Session-Tod mit offenem Vorschlag** → Card wird wie andere via `abandon_decisions` obsolet (Roh-Log behält den Marker-Kontext).

→ Bereit für `/abc-frontend` (Card-Variante „Wissens-Vorschlag" + kuratierte Suche) und danach `/abc-qa`.

## Implementation Notes (Frontend Developer)
**Datum:** 2026-06-24 · **Branch:** dev · **Stack:** Next.js 16 + shadcn/ui (Cockpit) — rein additiv, kein neues Paket. **Verifikation:** `npm run lint` grün · `next build` + TypeScript grün · `vitest` → **57 grün**.

### Gebaut
- **`components/cockpit/decision-card.tsx`** — neue **`KnowledgeProposalCard`** (eigene **smaragdgrüne** Farbe, klar abgesetzt von der orangenen Freigabe-Card; Badge „💡 Wissens-Vorschlag"). Zeigt Titel + kuratierten Body (scrollbar). Aktionen **Freigeben** / **Editieren** (klappt Titel-`Input` + Body-`Textarea` auf → „Editiert freigeben") / **Verwerfen**. Obsolet-Zustand + „In Session springen". `DecisionCard`-Router dispatcht `card_type === "knowledge_proposal"` dorthin (vor AskUserQuestion/ApproveDeny).
- **`components/cockpit/knowledge-search.tsx` (NEU)** — projektübergreifende Suche über kuratiertes Wissen: Eingabe + `searchVault(q, "curated")`, Trefferliste (Titel + Ausschnitt), Klick öffnet die Notiz im MD-Reader.
- **`app/(cockpit)/doku/page.tsx`** — `KnowledgeSearch` oben in der Sidebar eingehängt; `onSelect` mappt den vault-relativen Treffer-Pfad auf den absoluten Vault-Pfad und öffnet ihn via `selectPath` (Quelle wechselt automatisch auf „Vault").
- **`lib/types.ts`** — `PendingDecision.card_type` um `knowledge_proposal`; `proposal_title`/`proposal_body`; `context.curation_marker`; neue `VaultSearchHit`/`VaultSearchResult`.
- **`lib/api.ts`** — `resolveDecision(..., edited?)` (sendet `edited_title`/`edited_body`); neue `searchVault(q, scope, limit)`.

### Surfacing
- Wissens-Vorschläge erscheinen **inline auf der Session-Detailseite** (rendert alle `pending_decisions`) — nicht-blockierend, die Session läuft weiter. Sie setzen **nicht** `awaiting_approval`, daher kein Eintrag in der Kanban-„Review/Approval"-Spalte und keine Verfälschung des „Freigabe nötig"-Zählers (der greift nur bei `awaiting_approval`).

### Hinweis
- Frontend ist **sauber committet** (PROJ-16-Frontend war bereits in `18b3622`); nur das verschränkte **Backend** (`manager.py`/`config.py`/`schemas/sessions.py`) bleibt für den koordinierten Commit mit PROJ-16 offen.

→ Bereit für `/abc-qa`.

## QA Test Results
**Getestet:** 2026-06-24 · **Branch:** dev · **Tester:** QA Engineer (Red-Team) · **Methode:** `pytest` (**433 grün**, davon 22 PROJ-15 in `test_proj15_curation.py`) + `vitest` (**57 grün**) + `next build`/TypeScript + ESLint grün + adversariale Code-Review der neuen Flächen (kuratierter Write, scoped Suche, nicht-blockierende Card).

### Akzeptanzkriterien (8/8 bestanden)
| # | Kriterium | Ergebnis | Nachweis |
|---|-----------|----------|----------|
| 1 | Zwei Schichten roh↔kuratiert, beide offenes MD | ✅ PASS | `_TYPE_DIRS["curated"]=Knowledge`; `test_curated_note_lands_in_knowledge`, `test_search_curated_is_scoped_to_knowledge` |
| 2 | Agenten lesen + strukturierte Spuren zurück, ohne Überschreiben | ✅ PASS | PROJ-2-Leseschicht + `write_curated_note` mit `append`; `test_curated_dedup_appends_same_topic` (beide Erkenntnisse erhalten) |
| 3 | Trigger Bug/ADR/Sackgasse → Vorschlag | ✅ PASS | `test_detect_marker_kinds`, `test_marker_creates_nonblocking_proposal` |
| 4 | Vorschlag als Card mit Freigeben/Editieren/Verwerfen | ✅ PASS | `KnowledgeProposalCard` (Build/Vitest) + `test_api_proposal_approve_and_curated_search` |
| 5 | Freigegeben→`Knowledge/`, verworfen→nichts | ✅ PASS | `test_approve_writes_curated_note_edited`, `test_deny_writes_nothing` |
| 6 | Kuratierte Suche projektübergreifend + Pfad/Backlink | ✅ PASS | `search_curated`; `test_api_search_all_vs_curated_scope`; Frontend öffnet Treffer im MD-Reader |
| 7 | Nachvollziehbar (owner/Zeitstempel) + idempotent | ✅ PASS | `test_qa_curated_frontmatter_has_owner_and_created`; atomarer Write/Append (PROJ-2) |
| 8 | Alle Texte deutsch | ✅ PASS | Card/Such-UI + Notiz-Templates deutsch |

### Edge-Cases (alle abgedeckt)
- ✅ Doppelvorschlag (gleiches Thema) → **Append** statt neu (`test_curated_dedup_appends_same_topic`).
- ✅ Trigger zu oft → **Entprellung** je Marker-Art (`test_debounce_one_proposal_per_marker_kind`).
- ✅ Editieren → editierte Fassung geschrieben (`test_approve_writes_curated_note_edited`); Roh-Log unberührt (wird erst bei DONE geschrieben).
- ✅ Konflikt mit manuell editierter Notiz → nie blind überschreiben (Default `append`).
- ✅ **Vault nicht schreibbar → Card bleibt offen** (kein Verlust) → `test_qa`/`test_vault_failure_keeps_card_open` (OSError propagiert, Route 503).
- ✅ Sehr großes Roh-Log → Pointer/Auszug statt Volltext (`test_build_proposal_is_pointer_not_fulltext`).
- ✅ Kuratierung deaktivierbar (`test_qa_curation_toggle_off_suppresses_proposals`).

### Security-Audit (Red-Team)
**Kontext:** Single-User-MVP, kein JWT/RLS (bewusst, #21) → klassische Tenant-Audits N/A. Neue Flächen = kuratierter Write + scoped Suche.
- ✅ **Pfad-Traversal** über kuratierten Titel (`../../etc/passwd`) → `slugify` neutralisiert, Datei bleibt im `Knowledge/`-Baum (`test_qa_curated_title_traversal_stays_in_knowledge`). Erbt zusätzlich den PROJ-2-`_resolve_write`-Guard.
- ✅ **Frontmatter/YAML-Injection** über Titel → via `json.dumps` escaped, kein überschriebenes Feld (`test_qa_curated_title_yaml_injection_safe`).
- ✅ **Such-Scope dicht:** `scope=curated` sieht NUR `Knowledge/` (kein Leak roher Logs/fremder PARA-Bereiche); ungültiger `scope` → 422.
- ✅ **Schreib-Eingrenzung:** Approve schreibt ausschließlich nach `Knowledge/` (Jupiter-Unterbaum), nie vault-weit.
- ✅ **XSS:** `proposal_body`/`excerpt` als React-Textknoten (`<pre>`); im Reader geöffnet greift die bestehende MarkdownView-Sanitisierung (PROJ-7).
- ✅ **Kein Wedge:** nicht-blockierende Vorschlags-Card sperrt die Eingabe NICHT; echte Freigabe-Cards blockieren weiterhin (`test_qa_blocking_card_still_blocks_input_regression`).

### Findings
| ID | Sev | Befund | Empfehlung |
|----|-----|--------|------------|
| QA15-1 | Low | Cross-Day-Dedup: gleiche Themen-Datei ist datumslos → echte Dedup über Tage. Sehr alte Notiz wächst durch Append monoton. | Akzeptiert (lebende Notiz); spätere Archiv-Rotation optional. |
| QA15-2 | Low (UX) | Hat eine Session gleichzeitig eine blockierende Card **und** einen Wissens-Vorschlag, zählt die Kachel im `awaiting_approval`-Zweig beide als „Freigabe nötig" (+1 zu viel). | Beim Härten Vorschläge aus dem `pendingCount` filtern. |
| QA15-3 | Low | Marker-Heuristik ist phrasenbasiert → seltene false positives/negatives möglich. | Bewusst MVP; semantischer Klassifikator = RAG-Ausbau PROJ-19. |

Keine Critical/High/Medium. Keine Regression (433 Backend- + 57 Frontend-Tests grün).

### Produktionsreife-Entscheidung
**READY / Approved** (innerhalb des MVP-Scopes) — alle 8 AC + alle Edge-Cases bestanden, keine Critical/High-Bugs. QA15-1..3 sind Low-Härtungen (kein Blocker).

> **Deploy-Hinweis:** Der verschränkte PROJ-15-Backend-Teil (`manager.py`/`config.py`/`schemas/sessions.py`/`routes/sessions.py`) + `tests/test_proj15_curation.py` sind im Working Tree (getestet), aber noch nicht committet (gemeinsam mit der laufenden PROJ-16-Watchdog-Arbeit in denselben Dateien) → `/abc-deploy` muss sie koordiniert mit-promoten.

## Deployment
**Deployed:** 2026-06-24 · **URL:** https://jupiter.auxevo.tech · **Version:** 0.5.0 · **Tag:** v0.5.0 · **Branch-Promotion:** `dev → main`.

Gemeinsam mit PROJ-16 (Amok-Watchdog) und PROJ-21 (Session-Löschen) promotet (die PROJ-15-/PROJ-16-Backend-Verdrahtung lag verschränkt in `manager.py`/`config.py`/`schemas/sessions.py` und wurde mit Commit `feat(PROJ-15): Backend-Verdrahtung Kuratierung` gemeinsam aufgelöst). Host-native VPS-Deploy: Push auf `main` → GitHub-Webhook → `deploy.sh` (`git reset --hard origin/main` + `npm run build` + `systemctl restart`). Verifikation: 433 Backend- + 57 Frontend-Tests grün, `next build`/TS grün.
