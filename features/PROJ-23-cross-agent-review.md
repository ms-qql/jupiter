# PROJ-23: Cross-Agent-Review / Challenge (adversariell, engine-übergreifend)

## Status: Approved
**Created:** 2026-06-23
**Last Updated:** 2026-06-25
**Baustein:** #30
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-18 (Weitere Engines) — Cross-Agent-Review lebt von **Modell-Diversität**; ein zweiter Treiber (Codex/Gemini/GLM/Ollama) ist Voraussetzung, sonst reviewt nur Claude sich selbst.
- Requires: PROJ-22 (Dispatch-Schicht + Vertrag) — die Challenge startet eine **Reviewer-Session** über die Dispatch-Schicht; das Vertrags-/Architektur-Artefakt (#18) ist das Prüfobjekt.
- Requires: PROJ-4 (Decision Cards) — die Kritik des Reviewers kommt als **Review-Notiz / Decision Card** zurück.
- Requires: PROJ-2 (Vault-Anbindung) — geprüfte Artefakte (Architektur-Doku, ADR, Diff) und Review-Ergebnisse liegen im Vault.
- Verwandt: PROJ-1 (Engine, `--model`-Routing) — Reviewer bevorzugt eine **andere Engine/anderes Modell** als der Autor.

## Beschreibung
Selbst-Review eines einzelnen Modells übersieht systematische blinde Flecken. Dieses Feature lässt das **Ergebnis eines Agenten von einem anderen Agenten herausfordern** — bevorzugt mit **anderer Engine/anderem Modell**. Beispiel: eine via `/abc-architecture` von **Claude Opus** entworfene Architektur wird von **Codex** (oder Gemini/GLM) gechallengt.

Integration **nativ in den Flow**: Auf einem erzeugten Artefakt (Architektur-Doku, ADR, Diff/Code) gibt es eine **„Challenge"-Aktion**. Sie startet eine **Reviewer-Session** mit (möglichst) anderer Engine, die das Artefakt adversariell prüft. Das Review-Ergebnis (Schwachstellen, Risiken, Gegenvorschläge) kommt als **Review-Notiz bzw. Decision Card** (#4) zurück — der Mensch entscheidet, was übernommen wird.

**Grundhaltung:** Diversität der Modelle fängt Fehler, die ein einzelnes Modell nicht sieht. Der Challenger **bewertet und schlägt vor**, er ändert das Artefakt nicht selbst (analog zur QA-Rolle: finden + vorschlagen, nicht fixen).

## User Stories
- Als Nutzer möchte ich auf einem erzeugten Artefakt (Architektur-Doku, ADR, Diff) eine **„Challenge"-Aktion** auslösen, um eine unabhängige Zweitmeinung zu bekommen.
- Als Nutzer möchte ich, dass der Challenger **standardmäßig eine andere Engine/ein anderes Modell** als der Autor nutzt, um echte Diversität zu erhalten.
- Als Nutzer möchte ich die Kritik als **strukturierte Review-Notiz** (Schweregrad, Fundstelle, Gegenvorschlag) erhalten, nicht als langes Fließtext-Log.
- Als Nutzer möchte ich pro Befund entscheiden: **übernehmen / verwerfen / mit Kommentar zurück an den Autor** (gleiche Aktionen wie bei einer Decision Card).
- Als Nutzer möchte ich sehen, **welche Engine/welches Modell** den Review erstellt hat (Nachvollziehbarkeit der Diversität).
- Als Nutzer möchte ich die Challenge auch dann nutzen können, wenn nur Claude verfügbar ist — dann mit explizitem Hinweis „gleiche Engine, eingeschränkte Diversität".

## Acceptance Criteria
- [ ] Auf einem prüfbaren Artefakt (mind. Architektur-Doku/ADR + Diff/Code) gibt es eine **„Challenge"-Aktion** in der UI.
- [ ] Die Challenge startet eine **Reviewer-Session** über die Dispatch-Schicht (PROJ-22) mit dem Artefakt als **Pointer**-Prüfobjekt (kein Volltext-Duplikat).
- [ ] Der Reviewer nutzt **standardmäßig eine andere Engine/anderes Modell** als der Autor; ist keine andere verfügbar, läuft die Challenge mit Warnhinweis auf derselben Engine.
- [ ] Das Review-Ergebnis ist **strukturiert** (Liste aus: Befund + Schweregrad + Fundstelle/Bezug + Gegenvorschlag) und kommt als **Review-Notiz/Decision Card** (PROJ-4) zurück.
- [ ] Pro Befund kann der Nutzer **übernehmen / verwerfen / mit Kommentar zurück** wählen; „mit Kommentar zurück" reicht den Befund an die Autor-Session.
- [ ] Jeder Review nennt **Autor-Engine/-Modell** und **Reviewer-Engine/-Modell**.
- [ ] Der Reviewer **ändert das Artefakt nicht** — er liefert nur Befunde (Trennung Finden/Umsetzen).
- [ ] Review-Ergebnisse werden im **Vault** abgelegt (Audit-Spur, projektübergreifend auffindbar).
- [ ] Alle Texte deutsch.

## Edge Cases
- **Nur eine Engine installiert** → Challenge läuft mit deutlichem Hinweis „eingeschränkte Diversität (gleiche Engine)" statt blockiert zu sein.
- **Artefakt zu groß fürs Reviewer-Kontextfenster** → es wird der relevante Ausschnitt/Diff gechallengt (Pointer/RAG-Linie #23), nicht stumm abgeschnitten.
- **Reviewer findet nichts** → explizite „keine Befunde"-Notiz (nicht stilles Verschwinden), inkl. genutztem Modell.
- **Reviewer halluziniert Befunde** → Befunde sind Vorschläge; der Mensch entscheidet; „verwerfen" schließt sie ohne Artefakt-Änderung.
- **Challenge auf ein veraltetes Artefakt** (inzwischen geändert) → Review wird gegen die Version markiert, gegen die er lief; Warnung bei Versions-Drift.
- **Reviewer-Session stirbt/timeoutet** → Befund „Review unvollständig", Artefakt bleibt unverändert; Retry möglich.
- **Endlos-Challenge-Schleife** (Autor ↔ Reviewer streiten endlos) → Rundenlimit; danach Eskalation als Decision Card an den Menschen.

## Technical Requirements (optional)
- Setzt **mehrere Treiber** voraus (PROJ-18); Engine-Auswahl des Reviewers über das vorhandene Routing (`--model` / Treiber-Wahl).
- Nutzt die **Dispatch-Schicht** (PROJ-22) zum Starten/Verfolgen der Reviewer-Session und das **Vertrags-/Artefakt-Modell** als Prüfobjekt.
- Befunde als strukturierte Notiz an die bestehende Decision-Card-Mechanik (PROJ-4) angedockt — kein separater Review-Stack.
- Artefakt-Referenzen als **Pointer** in den Vault (konsistent mit #23), Review-Ergebnis als kuratiertes Wissen ablegbar (PROJ-15).
- Single-User-MVP-Linie: kein JWT/RLS hier; `owner` wird mitgeführt.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 Cockpit + FastAPI (in-memory SessionManager) + Vault (MD/Obsidian) · **Branch:** dev

### Grundidee in einem Satz
Eine **Challenge-Aktion** auf einem Artefakt (Architektur-Doku/ADR oder Diff/Code) startet eine kurze **Reviewer-Session** mit (möglichst) **anderer Engine**, die das Artefakt adversariell prüft; die Befunde kommen als **strukturierte Review-Karten** zurück und landen als Audit-Spur im Vault — der Mensch entscheidet pro Befund.

### Wiederverwendung statt Neubau (Befund der Codegraph-Exploration)
Die vier Abhängigkeiten liefern fast alles fertig — PROJ-23 ist primär **Verdrahtung + ein neuer Kartentyp**, kein neuer Stack:
- **Dispatch/Session (PROJ-22/PROJ-1):** `SessionManager.create()/start()` startet beliebige Sessions inkl. `role` + `initial_prompt`. Reviewer = normale Session mit `role="reviewer"`.
- **Engine-Routing (PROJ-18, deployed):** `EngineRegistry` kennt alle verfügbaren Engines; Reviewer-Engine = „nicht die Autor-Engine" aus der Registry.
- **Decision Cards (PROJ-4, deployed):** Karten haben bereits ein `card_type`-Feld (`normal | phase_transition | deny | knowledge_proposal | watchdog_pause | self_restart`). Wir **erweitern um `review_finding`** — kein eigener Review-Stack.
- **Vault (PROJ-2, deployed):** `VaultService.write()` + Pointer/RAG-Fenster (`_best_window`) sind vorhanden; Review wird als MD unter `Knowledge/reviews/` mit Pointer aufs geprüfte Artefakt abgelegt.

### A) Komponenten-Struktur (UI)
```
Artefakt-Ansicht (file-preview.tsx / doku/page.tsx / rag-preview-panel.tsx)
└── Toolbar
    └── Button „Challenge" (neben Kopieren/Bearbeiten)
        └── ChallengeDialog (shadcn Dialog)
            ├── Artefakt-Bezug (Pfad + Zeilenbereich, read-only Pointer)
            ├── Reviewer-Engine-Auswahl (Default: andere Engine; Badge bei „gleiche Engine")
            └── Fokus-Hinweis (optional: „Sicherheit / Skalierung / Konsistenz")

Cockpit Session-Detail / Kanban-Spalte „Review"
└── DecisionCard (card_type="review_finding")   ← bestehende Komponente, neue Variante
    ├── Kopf: Autor-Engine/-Modell  →  Reviewer-Engine/-Modell  + Artefakt-Version
    └── Befund-Liste, je Befund:
        ├── Schweregrad-Badge (hoch / mittel / niedrig)
        ├── Fundstelle (Pointer-Link ins Artefakt)
        ├── Gegenvorschlag (Text)
        └── Aktionen: Übernehmen · Verwerfen · Mit Kommentar zurück
```

### B) Datenmodell (Klartext, kein SQL — In-Memory + Vault wie der Rest von Jupiter)
```
Review (eine Challenge):
- review_id
- artifact_pointer   (Vault-Pfad + Zeilenbereich; KEIN Volltext-Duplikat)
- artifact_version   (Hash/Stand, gegen den geprüft wurde → Drift-Warnung)
- author_engine/-model   (wer das Artefakt erzeugt hat)
- reviewer_engine/-model (wer geprüft hat)  + same_engine: bool (Diversitäts-Hinweis)
- reviewer_session_id    (Rückverweis auf die laufende/erledigte Session)
- status: läuft / fertig / unvollständig (Timeout/Crash)
- owner  (Single-User-MVP, wie überall mitgeführt)

Befund (0..n je Review):
- befund_id
- schweregrad   (hoch | mittel | niedrig)   ← 3-stufig (Design-Entscheid 2026-06-25)
- fundstelle    (Pointer/Bezug ins Artefakt)
- beschreibung + gegenvorschlag
- entscheidung: offen | übernommen | verworfen | zurück-an-autor (+ kommentar)
```
Persistenz analog Jupiter-Linie: Laufzeitzustand in `SessionManager`/Decision-Card-Registry (in-memory), **Ergebnis als kuratiertes MD im Vault** (Audit-Spur, projektübergreifend auffindbar). Kein neues DB-Schema.

### C) API-Form (nur Endpunkte, kein Code)
```
- POST /sessions/{id}/challenge
    Startet eine Reviewer-Session auf einem Artefakt-Pointer.
    Eingabe: artifact_pointer, optional reviewer_engine + Fokus-Hinweis.
    Default-Engine-Wahl: andere als Autor-Engine; sonst gleiche Engine + Warnflag.
    (bewusst NICHT /challenge top-level — Kollision mit dem /abc-challenge-Skill vermeiden)

- GET  /sessions/{id}/reviews            → Reviews/Befunde zu einer Session
- POST /reviews/{review_id}/findings/{finding_id}
    → Entscheidung je Befund: übernehmen | verwerfen | zurück-an-autor (+ Kommentar).
      „zurück" reicht den Befund als Eingabe an die Autor-Session.

Befunde erscheinen zusätzlich über den bestehenden Decision-Card-Kanal
(GET /sessions liefert pending_decisions[] mit card_type="review_finding").
```
Single-User-MVP: kein JWT/RLS (konsistent mit Jupiter-Stack-Overrides); `owner` wird mitgeführt.

### D) Tech-Entscheidungen (Warum)
- **Reviewer ändert nie das Artefakt** — er liefert nur Befunde (Trennung Finden/Umsetzen, analog QA). „Übernehmen" erzeugt erst einen Vorschlag/Diff zur menschlichen Freigabe, keinen stillen Schreibvorgang.
- **Pointer statt Volltext** (konsistent mit PROJ-22/#23): Bei zu großem Artefakt wird der relevante Diff/Ausschnitt über das vorhandene RAG-Fenster gechallengt — nichts wird stumm abgeschnitten.
- **`card_type="review_finding"` statt eigenem Review-Stack:** nutzt die fertige Karten-/Kanban-/WebSocket-Mechanik; visuell abgesetzt (eigene Farbe) von Freigabe-Karten, damit „Review-Befund" nicht mit „Berechtigungs-Gate" verwechselt wird.
- **Diversität als Default, nicht als Pflicht:** ist nur eine Engine verfügbar, läuft die Challenge mit deutlichem Hinweis „eingeschränkte Diversität (gleiche Engine)" statt zu blockieren.
- **Versions-Anker:** Jeder Review merkt sich den Artefakt-Stand; ändert sich das Artefakt danach, warnt die UI vor Versions-Drift, statt veraltete Befunde als aktuell zu zeigen.
- **Rundenlimit gegen Endlos-Challenge:** Autor↔Reviewer-Pingpong ist auf **2 Runden** begrenzt; danach Eskalation als normale Decision Card an den Menschen.
- **„Übernehmen"-Semantik (Design-Entscheid):** „Übernehmen" erzeugt einen **Vorschlags-Diff** an die Autor-Session (menschliche Freigabe nötig) — kein stiller Schreibvorgang ins Artefakt.

### E) Abhängigkeiten / Pakete
- **Backend:** keine neuen Pakete — nutzt bestehende `engine/registry.py`, `engine/manager.py`, `engine/decisions.py`, `engine/vault.py`.
- **Frontend:** keine neuen Pakete — erweitert `decision-card.tsx` (neue Variante) + Toolbar-Button in `file-preview.tsx`/`doku`/`rag-preview-panel.tsx`; neue Typen in `lib/types.ts`.

### Neu zu bauen (Architekten-Übergabe → Spezialisten)
| # | Aufgabe | Spezialist |
|---|---------|-----------|
| 1 | `review_finding`-Kartentyp + Review/Befund-Modell + Endpunkte (`/sessions/{id}/challenge`, `/reviews/...`) | **Backend Developer** |
| 2 | Reviewer-Engine-Auswahl (andere-Engine-Logik über Registry) + adversarieller System-Prompt + Output→Befund-Strukturierung | **Backend Developer** |
| 3 | Vault-Konvention `Knowledge/reviews/PROJ-X-review-<stamp>.md` + Pointer aufs Artefakt | **Backend Developer** |
| 4 | Challenge-Button + ChallengeDialog (Engine-Wahl, Diversitäts-Badge) | **Frontend Developer** |
| 5 | `DecisionCard`-Variante `review_finding` (Befundliste, Schweregrad, Pointer-Link, 3 Aktionen) + `lib/types.ts` | **Frontend Developer** |
| 6 | Abnahme gegen Acceptance Criteria + Red-Team (Engine-Diversität, Drift, Timeout, „keine Befunde") | **QA Engineer** |

**Reihenfolge:** PROJ-22 (Dispatch) muss minimal stehen → Backend #1–3 → Frontend #4–5 → QA #6.

## Implementation Notes (Backend)
**Datum:** 2026-06-25 · **Branch:** dev

Backend implementiert in vier Dateien (kein neues DB-Schema — in-memory + Vault, konsistent mit PROJ-22):
- `backend/app/engine/challenge.py` — `ChallengeService` (+ `Review`/`Finding`-Dataclasses):
  - **Engine-Auswahl** `pick_reviewer_engine`: bevorzugt eine andere verfügbare Session-Engine als der Autor; gibt es keine → gleiche Engine mit `same_engine=True` (Warnhinweis statt Block).
  - **`start`**: lädt das Artefakt über den Vault-Pointer (großes Artefakt → RAG-Fenster via `_best_window`, kein stummes Abschneiden), berechnet einen Versions-Hash, baut einen adversariellen deutschen Prompt mit JSON-Schema-Konvention, startet eine Reviewer-`SessionRuntime` (`role="reviewer"`) über den bestehenden `SessionManager`. Rundenlimit **2** je Autor-Session → danach `RoundLimitError` (Eskalation an den Menschen).
  - **`collect`** (lazy, idempotent): parst den letzten ```json-Block aus dem Reviewer-Transkript → strukturierte Befunde (Schweregrad 3-stufig hoch/mittel/niedrig, ungültig → „mittel"), materialisiert sie als nicht-blockierende `card_type="review_finding"`-Cards auf der Reviewer-Session und schreibt eine Audit-Notiz in den Vault (`Knowledge/`, best-effort). Kein verwertbarer Output bei toter Session → `incomplete=True` (Retry möglich). Leere Liste → explizite „keine Befunde".
  - **`resolve_finding`**: übernehmen → Gegenvorschlag als Eingabe an die **Autor-Session** (Umsetzung läuft über deren eigenen Decision-Card-Flow → menschliche Freigabe); zurück → Befund + Kommentar an die Autor-Session; verwerfen → nur schließen (Artefakt unberührt).
  - **Versions-Drift** (`stale`): aktueller Artefakt-Hash vs. Review-Version.
- `backend/app/schemas/challenge.py` — `ChallengeRequest`, `ReviewRead`, `FindingRead`, `FindingDecision`.
- `backend/app/routes/challenge.py` — `POST /sessions/{id}/challenge`, `GET /sessions/{id}/reviews`, `GET /reviews/{id}`, `POST /reviews/{id}/findings/{finding_id}`.
- `backend/app/main.py` — `app.state.challenge = ChallengeService(...)` + Router registriert. `decisions.py`: `card_type`-Kommentar um `review_finding` ergänzt.

**Tests:** `backend/tests/test_proj23_challenge.py` (Parser, Engine-Auswahl inkl. Diversitäts-Fallback, Start/Attribution, Befund-Collection + Cards, übernehmen/verwerfen/zurück, Rundenlimit, keine Befunde, Versions-Drift).

**API-Vertrag (für Frontend):**
- `POST /sessions/{id}/challenge` `{artifact_pointer, reviewer_engine?, focus?}` → `ReviewRead` (201)
- `GET /sessions/{id}/reviews` → `ReviewRead[]` (Befunde werden beim Lesen eingesammelt)
- `POST /reviews/{review_id}/findings/{finding_id}` `{action: "übernehmen"|"verwerfen"|"zurück", comment?}` → `FindingRead`
- Befunde erscheinen zusätzlich als `pending_decisions` (`card_type="review_finding"`) auf der Reviewer-Session (WS-Stream + `GET /sessions`).

**Hinweis Diversität:** Aktuell ist (laut engines.yaml/Verfügbarkeit) i. d. R. nur Claude verfügbar → `same_engine=True`. Echte Cross-Engine-Diversität greift, sobald eine zweite Session-Engine (PROJ-18) verfügbar ist.

## Implementation Notes (Frontend)
**Datum:** 2026-06-25 · **Branch:** dev · **Stack:** Next.js (Cockpit)

- `lib/types.ts` — `Severity`, `FindingAction`, `FindingRead`, `ReviewRead`, `ChallengeRequest`; `card_type`-Union um `review_finding` erweitert; `PendingDecision.context` um die Review-Felder (Engine-Attribution, `review_id`, `severity`, `same_engine`).
- `lib/api.ts` — `startChallenge`, `listReviews`, `resolveFinding`.
- `components/cockpit/review-finding.tsx` — gemeinsame Bausteine: `SeverityBadge` (3-stufig, farbcodiert) + `FindingActions` (Übernehmen/Verwerfen/Mit-Kommentar-zurück → `resolveFinding`).
- `components/cockpit/decision-card.tsx` — neue `ReviewFindingCard`-Variante (indigo, klar abgesetzt) für `card_type="review_finding"` auf der Reviewer-Session: Schweregrad, Fundstelle, Gegenvorschlag, Reviewer→Autor-Engine-Attribution, Diversitäts-Warnung, 3 Aktionen.
- `components/cockpit/challenge-dialog.tsx` — „Challenge"-Button + Dialog: Artefakt-Pointer (vorbelegt mit `contract_pointer`), Reviewer-Engine-Select (Default „automatisch — andere Engine bevorzugt", nur verfügbare `kind=engine`), Fokus; Ergebnis nennt Reviewer-Engine/-Modell + `same_engine`-Hinweis + Link zur Reviewer-Session.
- `components/cockpit/reviews-panel.tsx` — Review-Übersicht auf der Autor-Session: Reviews + Befunde, Autor-/Reviewer-Engine-Attribution, Versions-Drift-Badge (`stale`), „keine Befunde"/„unvollständig"-Zustände, je Befund die 3 Aktionen.
- `app/(cockpit)/sessions/[id]/page.tsx` — `ChallengeDialog` in die Actions-Bar, ausklappbares „Cross-Agent-Reviews"-Panel; `reviewsKey` lädt die Übersicht nach jedem Challenge-Start neu.

**Verifikation:** `tsc --noEmit` fehlerfrei (einzige verbleibende Meldung ist die vorbestehende `lib/md-tree.test.ts`), `eslint` der geänderten/neuen Dateien fehlerfrei.

**Bekannte Einschränkung (UX):** Der Challenge-Einstieg sitzt auf der Session-Detailseite (die Challenge braucht eine Autor-Session-ID). Ein zusätzlicher Trigger direkt aus einer Artefakt-/Doku-Ansicht ist möglich, sobald dort die Autor-Session bekannt ist.

## QA Test Results
**Datum:** 2026-06-25 · **Tester:** QA Engineer · **Branch:** dev · **Entscheidung:** ✅ Production-ready (Approved)

### Testumfang
- Automatisiert: `backend/tests/test_proj23_challenge.py` — **23 passed** (Parser, Engine-Auswahl, Start/Attribution, Collection, 3 Aktionen, Rundenlimit, keine Befunde, Drift, + QA-Lückentests).
- Regression Backend: **736 passed** (`pytest backend/tests`, 22,6 s) — keine Regression.
- Regression Frontend: **vitest 169 passed** (19 Dateien) · `tsc --noEmit` fehlerfrei (Restmeldung = vorbestehende `lib/md-tree.test.ts`, nicht von PROJ-23) · `eslint` der geänderten Dateien fehlerfrei.

### Acceptance Criteria (pass/fail)
| # | Kriterium | Status | Beleg |
|---|-----------|:--:|-------|
| 1 | „Challenge"-Aktion in der UI auf prüfbarem Artefakt | ✅ | `ChallengeDialog` (Button in Session-Actions); Pointer wählbar |
| 2 | Challenge startet Reviewer-Session über Dispatch-Schicht mit Pointer (kein Volltext-Duplikat) | ✅ | `ChallengeService.start` → `manager.create(role="reviewer")`; `Review` speichert `artifact_pointer`, nicht den Volltext; `test_challenge_starts_reviewer_session` |
| 3 | Reviewer standardmäßig andere Engine; sonst gleiche + Warnung | ✅ | `pick_reviewer_engine`; `test_pick_reviewer_engine_prefers_other` / `_same_when_only_one`; `same_engine`-Flag in UI |
| 4 | Strukturiertes Ergebnis (Befund+Schweregrad+Fundstelle+Gegenvorschlag) als Review-Notiz/Decision Card | ✅ | `collect` → `review_finding`-Cards; `test_reviews_collect_structured_findings` |
| 5 | Pro Befund übernehmen/verwerfen/zurück; „zurück" an Autor-Session | ✅ | `resolve_finding`; `test_resolve_uebernehmen/verwerfen/zurueck` |
| 6 | Jeder Review nennt Autor- + Reviewer-Engine/-Modell | ✅ | `ReviewRead`-Felder; Attribution in Card + Panel; Test asserts |
| 7 | Reviewer ändert das Artefakt nicht | ✅ | Befunde sind nur Vorschläge; `test_resolve_verwerfen_does_not_touch_author` (author.sent leer) |
| 8 | Review-Ergebnisse im Vault (Audit-Spur) | ✅ | `_write_vault_note` → `Knowledge/`; `test_ac8_review_result_written_to_vault` + `_no_findings_also_written` |
| 9 | Alle Texte deutsch | ✅ | Prompts, UI, Vault-Notiz, Fehlermeldungen deutsch (Sichtprüfung) |

### Edge Cases
| Fall | Status | Beleg |
|------|:--:|-------|
| Nur eine Engine → Warnhinweis statt Block | ✅ | `same_engine=True`; `test_pick_reviewer_engine_same_when_only_one` |
| Artefakt zu groß → RAG-Fenster statt stummem Abschneiden | ✅ | `test_large_artifact_uses_rag_window_not_truncation` |
| Reviewer findet nichts → explizite „keine Befunde"-Notiz | ✅ | `test_no_findings_explicit_note` + Vault-Notiz |
| Halluzinierte Befunde → „verwerfen" schließt ohne Artefakt-Änderung | ✅ | `test_resolve_verwerfen_does_not_touch_author` |
| Veraltetes Artefakt → Versions-Drift markiert | ✅ | `test_version_and_stale_detection`; `stale`-Badge im Panel |
| Reviewer-Session stirbt/timeoutet → „Review unvollständig" | ✅ | `test_incomplete_when_reviewer_dies_without_output` |
| Endlos-Challenge → Rundenlimit (2) + Eskalation | ✅ | `test_round_limit_escalates` (409) |

### Security / Red-Team
- **Pfad-Traversal** über `artifact_pointer` (`../../../etc/passwd`): eingedämmt — `VaultService._resolve_read` wirft, der Inhalt gilt als „nicht lesbar" (kein Leak, `artifact_version=null`). `test_path_traversal_pointer_is_contained`. ✅
- **Ungültige/keine Session-Engine** als Reviewer → 400 (`test_invalid_reviewer_engine_400`). ✅
- **Fremd-Steuerung**: Befund-Auflösung gegen unbekanntes Review/Befund → 404 (`test_resolve_finding_unknown_review_404`, `test_resolve_finding_twice_404`). ✅
- **Autor-Session beschäftigt** beim Routing eines Befunds → 409 statt Verkeilung (gehandhabt in `_route_to_author`). ✅
- Single-User-MVP: kein JWT/RLS (bewusst, Stack-Override) → Tenant-Isolations-Red-Team N/A; `owner` wird serverseitig gestempelt. Echtes Auth kommt mit PROJ-25.

### Bugs / Beobachtungen
- **Keine Critical/High/Medium.**
- ~~**Low-1**~~ **✅ behoben (2026-06-25):** Befunde werden nicht mehr nur lazy beim Lesen eingesammelt. `ChallengeService.start` sammelt sofort ein (instant fertige Reviewer) und startet zusätzlich einen Watcher (`_watch_and_collect`), der auf das Turn-Ende der Reviewer-Session reagiert → die `review_finding`-Cards erscheinen automatisch, auch wenn man direkt zur Reviewer-Session navigiert. Lese-Collect bleibt als idempotenter Fallback. Test: `test_l1_findings_materialize_without_reviews_call`.
- ~~**Low-2**~~ **✅ behoben (2026-06-25):** `collect` behandelt `waiting` (Turn beendet, Review erwartet keine Folge-Eingabe) als sammelbar — liefert der Reviewer dann keinen parsebaren Block, wird der Review sofort als `incomplete` markiert statt dauerhaft „prüft noch …" anzuzeigen. Test: `test_l2_incomplete_when_waiting_without_json`.

### Production-Ready: **JA** — keine Critical/High-Bugs; die zwei Low-Beobachtungen wurden behoben. Status → Approved.

## Deployment
_To be added by /abc-deploy_
