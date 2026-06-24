# PROJ-19: Effizienz-Ausbau — Pointer/RAG, Späher-Agenten, Prompt-Caching, Token-Dashboard

## Status: In Progress
**Created:** 2026-06-23
**Last Updated:** 2026-06-24
**Bausteine:** #23, #26, #27, #28

> **Hinweis Granularität:** Dieser Eintrag bündelt vier verwandte Effizienz-Mechanismen (PRD-Roadmap-Eintrag). Falls die Architektur-Phase einen davon als zu groß einstuft, kann er in eine eigene Spec ausgegliedert werden (z. B. Token-Dashboard als separate UI-Spec).

## Dependencies
- Requires: PROJ-1 (Engine) — Späher-Agenten + Caching greifen in den Treiber-/Modell-Pfad.
- Requires: PROJ-2 / PROJ-15 (Vault) — Pointer/RAG lädt Ausschnitte aus dem Vault.
- Verwandt: PROJ-5/#25 (Kontext-Budget) und #22 (Modell-Routing) — das Token-Dashboard schließt deren Regelkreis.

## Beschreibung
Vier Querschnitts-Mechanismen, die den Token-Verbrauch senken, ohne Informationsverlust:
- **#23 Pointer statt Volltext (Vault-RAG):** Agenten bekommen Links zu Vault-Dateien; nur relevante Ausschnitte werden geladen.
- **#26 Billige Späher-Agenten:** „Lies viele Dateien, gib nur das Fazit"-Aufgaben gehen an günstige Explorer (Haiku); die teure Hauptsession bleibt schlank.
- **#27 Prompt-Caching:** wiederkehrende Rollen-/Skill-Prompts + stabiler Projektkontext werden gecacht statt neu gesendet.
- **#28 Token-/Kosten-Dashboard:** Verbrauch heute/pro Projekt/pro Modell sichtbar; erkennt token-fressende Rollen/Tasks.

## User Stories
- Als Nutzer möchte ich, dass Agenten statt Volltext-Dumps nur relevante Vault-Ausschnitte geladen bekommen, um Kontext schlank zu halten.
- Als Nutzer möchte ich Such-/Lese-Schwerarbeit an billige Späher-Agenten delegieren, damit die teure Hauptsession nicht zumüllt.
- Als Nutzer möchte ich, dass stabile Rollen-/Skill-Prompts gecacht werden, um wiederkehrende Kosten zu senken.
- Als Nutzer möchte ich ein Dashboard mit Verbrauch pro Tag/Projekt/Modell, um Token-Fresser zu erkennen.

## Acceptance Criteria
- [ ] **Pointer/RAG:** Ein Mechanismus liefert statt Volltext eine Auswahl relevanter Ausschnitte aus dem Vault (Pfad + Snippet); messbar geringerer Kontextverbrauch gegenüber Volltext.
- [ ] **Späher-Agenten:** „Fazit-Aufgaben" können an eine günstige Engine/Modell (Haiku) delegiert werden; die Hauptsession erhält nur das verdichtete Ergebnis.
- [ ] **Prompt-Caching:** wiederkehrende, stabile Prompt-Bestandteile werden über Aufrufe hinweg wiederverwendet; Cache-Treffer sind messbar/sichtbar.
- [ ] **Token-Dashboard:** zeigt Verbrauch und Kosten **heute / pro Projekt / pro Modell** mit Drilldown auf Rollen/Tasks.
- [ ] Alle vier Mechanismen sind **einzeln abschaltbar** und brechen bei Fehlern auf das heutige Verhalten zurück (kein Hard-Fail).
- [ ] Das Dashboard nutzt vorhandene Usage-Daten (aus PROJ-5/#25) ohne Extra-Erhebungslast.
- [ ] Alle Texte deutsch; Lade-/Fehler-/Leer-Zustände explizit.

## Edge Cases
- **RAG verfehlt relevanten Ausschnitt** → Fallback auf größeren Ausschnitt/Volltext mit sichtbarem Hinweis.
- **Späher-Ergebnis unbrauchbar** → Hauptsession kann eskalieren (teureres Modell), nachvollziehbar.
- **Cache veraltet** (Rolle/Skill geändert) → Invalidierung; kein Servieren veralteter Prompts.
- **Engine ohne Usage-Daten** (PROJ-18) → Dashboard zeigt „n/v" statt falscher Nullen.
- **Kosten-Schätzung vs. Ist** → klar als Schätzung kennzeichnen, wenn keine echten Kosten vorliegen (Subscription-Auth).

## Technical Requirements (optional)
- RAG: einfacher Ausschnitts-Index über Vault-Notizen (erweiterbar); Späher nutzt das Treiber-/Routing-Modell (#22).
- Caching nutzt die Caching-Fähigkeiten der jeweiligen Engine (z. B. Prompt-Caching der Claude-CLI), wo verfügbar.
- Dashboard aggregiert die bereits erfassten Token/Kosten pro Session; performant für viele Sessions.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js (Cockpit) + FastAPI (raw SQL) + SQLite-Live-Index (heute) / Vault-Files · **Branch:** dev

### Granularität (entschieden)
Ein gemeinsames Design für alle vier Mechanismen (Option A), gebaut in vier Bau-Sub-Phasen in dieser Reihenfolge — vom reifsten zum aufwändigsten, jede einzeln deploybar und einzeln abschaltbar:

**Sub-Phase 1 — Token-Dashboard (#28)** · **2 — Pointer/RAG (#23)** · **3 — Prompt-Caching (#27)** · **4 — Späher-Agenten (#26)**

Querschnitts-Prinzip aus den Acceptance Criteria: **jeder Mechanismus hat einen Feature-Schalter (Settings) und fällt bei Fehler still auf das heutige Verhalten zurück (kein Hard-Fail).**

---

### Sub-Phase 1 — Token-/Kosten-Dashboard (#28)

#### A) Component Structure (Cockpit)
```
UsageDashboardPage  (neuer Tab "Verbrauch" im Cockpit)
├── ZeitraumFilter        (shadcn Select: Heute · 7 Tage · 30 Tage)
├── KennzahlenLeiste       (3 Cards: Tokens · geschätzte Kosten · Sessions)
├── VerbrauchProModell     (Recharts BarChart — Tokens je Modell)
├── VerbrauchProProjekt    (Recharts BarChart — Tokens/Kosten je project_path)
├── DrilldownTabelle       (Sessions → Rolle/abc_phase, sortierbar)
├── LeerZustand            ("Noch keine Verbrauchsdaten")
└── SchätzungHinweis-Badge (wenn Kosten nur geschätzt, s. Edge Case Subscription)
```

#### B) Daten (keine neue Erhebung)
Nutzt die **bereits erfassten** Felder im Live-Index: `tokens_used`, `total_cost_usd`, `model`, `project_path`, `abc_phase`, `abc_feature`, `created_at`, `owner`. Keine neue Spalte, keine Extra-Erhebungslast (erfüllt AC „nutzt vorhandene Usage-Daten").

#### C) API Shape (neue Route `usage.py`)
```
- GET /usage/summary?range=today|7d|30d   → Aggregat: Tokens + Kosten gesamt, je Modell, je Projekt
- GET /usage/drilldown?range&group_by      → Sessions-Liste (Rolle/abc_phase/Modell) für Tabelle
```
Aggregation per `run_query_m` mit `GROUP BY model / project_path / abc_phase` über den Index.

#### D) Tech-Entscheidungen
- **Recharts** statt Plotly fürs Cockpit-Frontend — leichtgewichtig, React-nativ, passt zum bestehenden DOM-Rendering (gantt-chart.tsx); kein Plotly.js-Bundle nötig (Plotly bleibt für Python-Reports, nicht für dieses interaktive UI).
- **Kosten als Schätzung kennzeichnen:** Subscription-Engines (Claude-Max) liefern keine echten Kosten → `total_cost_usd` kann 0/None sein. Dashboard zeigt dann „geschätzt" (Token×Tarif) bzw. „n/v" statt falscher Nullen (Edge Case erfüllt).
- **Engine ohne Usage** (manche PROJ-18-Engines): Zeile zeigt „n/v".

---

### Sub-Phase 2 — Pointer/RAG über den Vault (#23)

#### A) Ablauf (plain)
```
Agent fragt Kontext an
 → RAG-Layer sucht im Vault (vorhandene Suche, _MAX_SEARCH_HITS/_EXCERPT_CHARS)
 → liefert Top-N { pfad, snippet } statt Volltext
 → bei zu wenig/keinem Treffer: Fallback größerer Ausschnitt → Volltext (mit sichtbarem Hinweis)
```

#### B) Was gebaut wird
- Dünne **Prompt-Konstruktions-Schicht** auf der vorhandenen `vault.search`-Funktion (Suche + Excerpts sind schon da, ~50% fertig): wählt Top-N Snippets, fügt Pfad-Pointer bei.
- **Messung:** geladene Kontext-Zeichen RAG vs. Volltext werden geloggt → erfüllt AC „messbar geringerer Kontextverbrauch".

#### C) API/Service
```
- (intern) vault.relevant_snippets(query, top_n) → [{path, snippet, score}]
- GET /vault/rag/preview?query=…   → Debug/Sichtbarkeit der gewählten Ausschnitte (optional UI)
```

#### D) Entscheidung
- **Kein Embedding-Store im MVP** — lexikalische Snippet-Suche reicht für den Vault-Umfang und vermeidet eine neue Vektor-DB-Abhängigkeit. Schnittstelle (`relevant_snippets`) ist so geschnitten, dass später ein Embedding-Index dahinter austauschbar ist.
- **Fallback** ist Pflicht: RAG verfehlt → größerer Ausschnitt/Volltext + Hinweis (Edge Case).

---

### Sub-Phase 3 — Prompt-Caching (#27)

#### A) Was gebaut wird
- Neuer **`cache_manager`**: bildet stabile, wiederkehrende Prompt-Bestandteile (Rollen-/Skill-Prompts, stabiler Projektkontext) auf Cache-Marker ab.
- **Claude-CLI / API:** Cache-Control-Marker werden in den Treiber-Aufbau injiziert (`claude_driver.build_argv` / API-Header), wo die Engine Prompt-Caching unterstützt.
- **Sichtbarkeit:** `cache_read_input_tokens` / `cache_creation_input_tokens` aus `UsageSnapshot` sind bereits erfasst → Cache-Treffer werden im Dashboard (Sub-Phase 1) als eigene Kennzahl sichtbar (erfüllt AC „Cache-Treffer messbar/sichtbar").

#### B) Entscheidungen
- **Engine-bedingt:** nur dort aktiv, wo die Engine Caching kann; sonst No-op (kein Fehler). Erfüllt „einzeln abschaltbar / kein Hard-Fail".
- **Invalidierung:** Cache-Key enthält einen Hash des Rollen-/Skill-Prompts → Änderung der Rolle/Skill invalidiert automatisch; keine veralteten Prompts (Edge Case).

---

### Sub-Phase 4 — Billige Späher-Agenten (#26)

#### A) Ablauf
```
Hauptsession delegiert "Fazit-Aufgabe" (viel lesen/suchen, wenig zurück)
 → POST /agents/scout (Modell = Haiku via engines.yaml-Routing)
 → Späher liest/sucht, gibt NUR das verdichtete Fazit zurück
 → Hauptsession erhält Fazit (nicht die Rohdaten)
 → Späher-Ergebnis unbrauchbar → Eskalation auf teureres Modell, nachvollziehbar
```

#### B) Was gebaut wird
- Neue Route **`agents.py`**: `POST /agents/scout { task, paths|query }` → kurzlebiger Sub-Agent über den vorhandenen Treiber-/Routing-Pfad (`SessionManager`/`registry`), fest auf das günstige Modell geroutet.
- Späher nutzt **Sub-Phase 2 (RAG)** zum Einlesen → doppelte Token-Ersparnis.
- Späher-Sessions erscheinen mit eigener `abc_phase`/Rolle im Dashboard (Drilldown zeigt Späher vs. Hauptsession).

#### C) Entscheidung
- Späher ist ein **kurzlebiger, nicht-steuerbarer** Lauf (kein interaktives Steering nötig) — leichter als eine volle PROJ-22-Dispatch-Schicht; PROJ-22 kann ihn später als Spezialfall aufnehmen.
- **Eskalation** (teureres Modell) ist explizit und wird geloggt (Edge Case + AC).

---

### E) Dependencies (Pakete)
- **Backend (Python):** keine neuen Pflicht-Pakete — Aggregation via vorhandenes `run_query_m`; Caching nutzt Engine-Fähigkeiten; Späher nutzt vorhandenen Treiber. (Optional später: ein Embedding-Paket, falls RAG aufgerüstet wird — bewusst aus dem MVP herausgehalten.)
- **Frontend (Next.js):** `recharts` (neu, Charts im Cockpit), sonst bestehendes shadcn/ui + Tabs.

### F) Einfügepunkte (aus Code-Scan)
- Usage-Aggregation → neue Route `backend/app/routes/usage.py` (GROUP BY über `session_index`).
- RAG → `backend/app/engine/vault.py` (`relevant_snippets` auf vorhandener Suche).
- Caching → neues `backend/app/engine/cache_manager.py` + Marker in `claude_driver.build_argv`.
- Späher → neue Route `backend/app/routes/agents.py` über `SessionManager`/`registry`.
- Frontend → neuer Tab `nextjs_app/app/(cockpit)/usage-dashboard/page.tsx` + Recharts-Komponenten; speist sich aus dem bestehenden `Session`-Typ/Provider.

### Risiken / offene Punkte
- **Kosten-Genauigkeit** bei Subscription-Auth: nur Schätzung möglich — klar im UI kennzeichnen.
- **Caching-Reichweite** hängt an der jeweiligen Engine — bei Fremd-Engines ggf. No-op.
- **Späher-Qualität:** Haiku-Fazit kann zu dünn sein → Eskalationspfad ist Pflicht, nicht optional.

## Implementierungs-Notizen (Frontend)

### Sub-Phase 1 — Token-/Kosten-Dashboard (#28) — ✅ Frontend fertig (Branch `dev`)
- **Neuer Cockpit-Tab „Verbrauch"** (`app/(cockpit)/page.tsx`) neben Kacheln/Kanban/Werkzeuge.
- **`components/cockpit/usage-dashboard.tsx`** — Zeitraum-Filter (Heute · 7 Tage · 30 Tage · Gesamt), Kennzahlen-Leiste (Tokens · geschätzte Kosten · Sessions), Verteilungen je Modell/Projekt (Balken), Drilldown-Tabelle (Projekt · Rolle/Phase · Modell · Tokens · Kosten), expliziter Leer-Zustand.
- **`lib/usage.ts`** — reine, getestete Aggregations-Logik (`aggregateUsage`/`filterByRange`/`rangeStartMs` + Formatter). Speist sich aus der **bereits gepollten** Session-Liste (sessions-provider) → kein Extra-Request, keine neue Erhebung (erfüllt AC „nutzt vorhandene Usage-Daten").
- **Kosten-Degradation:** Subscription/Fremd-Engine ohne echte Kosten → `costStatus` `none`/`partial`, UI zeigt „n/v" bzw. „~$…" + Hinweis statt falscher Nullen (erfüllt Edge Cases „Engine ohne Usage" / „Schätzung vs. Ist"). Nutzt die vorhandene `engineShowsCost`-Konvention (PROJ-18).
- **`lib/status.ts`** — kleiner Helper `phaseLabel()` ergänzt (ABC_PHASES bleibt Single Source of Truth).
- **Tests:** `lib/usage.test.ts` (9 Fälle: Range-Grenzen, Filter, Gruppierung Modell/Projekt, Kosten-Lagen, Formatierung) — grün. Lint sauber, Typecheck der neuen Dateien fehlerfrei.

**Abweichung vom Tech-Design:** Charts als **reine DOM-/Tailwind-Balken** statt `recharts` — konsistent mit dem bestehenden `gantt-chart.tsx`, kein neues Bundle/keine neue Abhängigkeit. `recharts` damit vorerst **nicht** nötig.

**Hinweis Daten-Reichweite:** Das Dashboard aggregiert die aktuell im Live-Index geführten Sessions (das, was der Provider liefert). Eine echte historische „heute/7d/30d"-Summe über bereits archivierte/gelöschte Sessions liefert später die geplante Backend-Route `GET /usage/summary` (Sub-Phase 1 Backend, noch offen) — die Frontend-Aggregation ist so geschnitten, dass sie dann nur die Datenquelle wechselt.

### Sub-Phase 1 — Backend (`/usage`) — ✅ fertig (Branch `dev`)
- **`backend/app/routes/usage.py`** — read-only, kein JWT (MVP single-user, vgl. sessions.py):
  - `GET /usage/summary?range=today|7d|30d|all` → `UsageSummary` (Tokens + Kosten gesamt, `cost_status`, `by_model[]`, `by_project[]`).
  - `GET /usage/drilldown?range=…&model=…&project=…` → `UsageDrilldown` (Session-Zeilen, nach Tokens absteigend; optionale Filter Modell-Label/Projektpfad).
- **`backend/app/engine/usage.py`** — `UsageService` + seiteneffektfreie Aggregat-Funktionen (`aggregate_summary`/`aggregate_drilldown`/`filter_by_range`/`range_start`). Quelle = **persistenter Live-Index** (`SessionIndexRepository.list_all()`) → überlebt Neustart, enthält auch beendete Sessions; keine neue Erhebung (AC erfüllt). Zeitfenster in UTC (`today` = ab UTC-Mitternacht).
- **`backend/app/schemas/usage.py`** — Pydantic-v2 (`UsageSummary` / `UsageGroup` / `UsageDrilldown` / `UsageDrilldownRow`); `cost_status ∈ {complete, partial, none}`.
- **Kosten-Degradation** identisch zum Frontend: `engine_shows_cost(engine) == (engine == "claude")`. Subscription/Fremd-Engine → `none`/`partial` (kein falscher Null-Betrag).
- **Schema-Ergänzung (additiv):** `engine`-Spalte in `session_index` (`COLUMNS` + `SCHEMA_SQL` + `_MIGRATIONS`, Default `'claude'`). Der Manager emittierte `engine` bereits in der Index-Row, es wurde aber nie persistiert → bei Rehydrierung ging die echte Engine verloren (Default „claude"). Jetzt persistiert — fixt nebenbei diesen latenten Bug und liefert die Engine fürs Kosten-Aggregat. `_state_from_row` las `engine` bereits.
- **Registrierung:** `app.state.usage = UsageService(repo)` + `app.include_router(usage.router)` in `main.py`.
- **Tests:** `backend/tests/test_proj19_usage.py` (9 Fälle: Logik + beide Endpunkte via TestClient/Fake-Repo) grün; volle Suite **559 passed**, keine Regression (Index/Rehydrierung inkl.).

**Frontend-Anbindung (offen, bewusst):** Das Dashboard aggregiert weiterhin client-seitig aus dem sessions-provider (steht bereits, kein Extra-Request). Die `/usage`-Endpunkte sind die kanonische, getestete Quelle für die echte historische Summe; das Umstellen des Dashboards (mit Fallback auf die Client-Aggregation = „kein Hard-Fail") ist ein sauberer Folgeschritt, nicht Teil dieses Backend-Commits, um die per-Feature-Stagung nicht zu vermischen.

### Sub-Phase 2 — Pointer/RAG (#23) — ✅ Backend fertig (Branch `dev`)
- **`VaultService.relevant_snippets(query, top_n, snippet_chars, subdir)`** (`backend/app/engine/vault.py`) — gerankte, mehr-termige Auswahl statt First-Hit-Substring (`search`): je Datei das **dichteste** Fenster (`_best_window`, Sliding-Window über Term-Positionen), über Dateien sortiert nach getroffenen Begriffen (`terms_matched ×1000 + Gesamthäufigkeit`). Liefert `{path, line, snippet, score, terms_matched, full_chars}`. Term-Zerlegung `_rag_terms` (lowercase, ≥2 Zeichen, DE/EN-Stoppwörter raus).
- **`VaultService.rag_preview(query, top_n, *, curated)`** — Mess-/Fallback-Hülle: `context_chars` (Snippets) vs. `fulltext_chars` (Volltext der Top-N) + `reduction_pct` → macht die Kontext-Ersparnis **messbar** (AC). `fallback=True` + `reason`, wenn kein Treffer → Caller fällt auf größeren Ausschnitt/Volltext zurück (Edge Case). `curated=True` grenzt auf `Knowledge/` ein (analog `search_curated`).
- **Route `GET /vault/rag/preview?q=&top_n=&scope=all|curated`** (`routes/vault.py`) → `VaultRagPreview`. Read-only, kein JWT (vgl. übrige Vault-Routen). Reine Datei-I/O, keine neue Erhebung.
- **Schemas:** `VaultRagSnippet` + `VaultRagPreview` (`schemas/vault.py`).
- **Wiederverwendung:** baut auf der vorhandenen Vault-Such-Infrastruktur auf (Walk, `_MAX_FILE_BYTES`-Cap, `_resolve_read`-Pfadhärtung) — keine neue Vektor-DB (Schnittstelle aber austauschbar, s. Tech-Design).
- **Tests:** `backend/tests/test_proj19_rag.py` (7 Fälle: Terme, dichtestes Fenster, Ranking, Leer-Treffer, Ersparnis-Messung, Fallback, Endpunkt) grün; volle Suite **566 passed**, keine Regression.

### Sub-Phase 3 — Prompt-Caching (#27) — ✅ Backend fertig (Branch `dev`)
- **`backend/app/engine/cache_manager.py`** — `CacheManager.plan(stable_prefix, variable_suffix)` → `CachePlan{enabled, cache_key, prompt, stable_chars}`. Stabile Konstitution/Rolle bildet das **cache-freundliche Präfix** (zuerst), variabler Seed-Kontext zuletzt — Assemblierung **identisch** zu `combine_with_extra` (per Test abgesichert → Verhalten unverändert). `cache_key` = SHA-256 des stabilen Präfixes → Änderung an Rolle/Skill/Konstitution invalidiert automatisch (Edge Case). Feature-Flag `settings.prompt_cache_enabled` (Default an); aus → identischer Prompt ohne Key (No-op-Fallback, kein Hard-Fail).
- **Manager-Integration:** `SessionManager` hält einen `CacheManager`; `create()` nutzt `plan()` statt `combine_with_extra` und legt `cache_key` auf den `SessionState`. Einziger Assemblier-Punkt (Resume/Recovery nutzen das bereits assemblierte `effective_constitution`).
- **Cache-Treffer sichtbar (AC):** `_apply_usage` akkumuliert nun `cache_read_tokens` + `cache_creation_tokens` (waren erfasst, aber nicht kumuliert) auf result-Events. Exponiert über `SessionState.to_read()` → `SessionRead` (+ TS-`Session`-Typ), persistiert im Live-Index (neue Spalten + `_MIGRATIONS`, additiv/idempotent), und aggregiert in `GET /usage/summary` als `cache_read_tokens` / `cache_creation_tokens` / `cache_hit_ratio` (read / (read+creation)).
- **Engine-bedingt:** funktioniert dort, wo die Engine cacht (Claude Code CLI cacht das System-Prompt-Präfix automatisch); Fremd-Engines ohne Cache-Tokens → Quote 0 / keine Treffer (kein Fehler).
- **Tests:** `backend/tests/test_proj19_cache.py` (7 Fälle: Assemblierung==combine_with_extra, Hash-Invalidierung, No-op-Fallback, leeres Präfix, Cache-Quote im Aggregat, Manager-Akkumulation) grün; volle Suite **573 passed**, keine Regression; Index-Round-Trip der neuen Spalten + Aggregat manuell verifiziert. Frontend-Typecheck sauber.

### Offen (nächste Sub-Phasen)
- Sub-Phase 1 **Frontend↔Backend-Anbindung** (optional) · Sub-Phase 2 **Frontend** RAG-Vorschau (optional) · Sub-Phase 3 **Frontend** Cache-Quote/-Tokens im Dashboard anzeigen (optional — Daten liegen in `SessionRead` + `/usage/summary`).
- Sub-Phase 4 **Späher-Agenten (#26)** — laut Tech-Design (größter Brocken).

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
