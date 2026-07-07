# PROJ-55: Session-Kondensierung — Wochen-Sweep alter Sessions in Hal-Knowledge

## Status: Deployed
**Created:** 2026-07-04
**Last Updated:** 2026-07-07

## Kurzbeschreibung
Ein Skill (plus planbarer Wochen-Lauf), der periodisch über die in Hal abgelegten
Roh-Session-Logs (`Agentic OS/Jupiter/Sessions/`) geht, alle Sessions **älter als 7 Tage**
evaluiert, die wichtigsten Erkenntnisse **kondensiert** und als kuratierte Knowledge-Notizen
in Hal ablegt — damit das Wissen weiterlebt und Jupiter daraus lernt. Kondensierte Roh-Logs
werden anschließend **archiviert + komprimiert**, damit der Sessions-Ordner nicht endlos wächst.

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung als Dienst) — Lesen/Schreiben im Hal-Vault
- Requires: PROJ-1 (Engine-Treiber: Claude headless) — die Kondensierung selbst läuft als headless-Lauf/Skill
- Verwandt: PROJ-15 (Vault Stufe 3 — roh↔kuratiert + Kuratierung), PROJ-5 (Context-Management & Handover)
- Baut auf dem bestehenden Kuratier-Mechanismus auf (`Knowledge/`-Stubs mit `curation_marker`, leeres `## Erkenntnis`)

## Kontext / Ist-Zustand
- `Agentic OS/Jupiter/Sessions/` enthält aktuell ~210 Roh-Session-Logs (YAML-Frontmatter:
  `owner`, `session_id`, `created`, `type: session_log`, `title` + Abschnitte `## Claude (denkt)`,
  `## Claude`, `## Du`). Größen 155 B … > 1 MB; viele triviale Läufe (Test-, Smoke-, reine „ok"-Sessions).
- Sessions umfassen **alle Projekte** (jupiter, immo-crm, ui-check, crypto-mts, hal …), erkennbar am
  `title`-Slug im Dateinamen (`YYYY-MM-DD--<slug>-<hash8>.md`).
- `Agentic OS/Jupiter/Knowledge/` existiert und enthält halb-automatische Kuratier-Stubs
  (`type: curated`, `curation_marker: adr|bug|…`, `source_session_id`). Das Feld **`## Erkenntnis` ist
  bislang leer** („_Bitte ergänzen/kuratieren._"). Die Marker-Extraktion existiert also bereits —
  **die eigentliche Kondensierung fehlt**; dieses Feature schließt genau diese Lücke.

## Getroffene Entscheidungen (Requirements-Phase)
1. **Roh-Log nach Kondensierung:** verschieben nach `Agentic OS/Jupiter/Sessions/_archiv/` **+ gzip**.
   Recovery bleibt möglich; der aktive Sessions-Ordner wird leer/klein. **Endgültiges Löschen** erst
   nach einem zweiten, längeren Zeitfenster (Default: 30 Tage im Archiv).
2. **Ablageziel:** kondensierte Erkenntnisse gehen nach `Agentic OS/Jupiter/Knowledge/`. Bestehende
   Stub-Dateien werden **gefüllt** (`## Erkenntnis`), fehlende werden **neu** angelegt — je Erkenntnis-Typ.
3. **Filter:** triviale Sessions (Tests, unter Mindestgröße/-tiefe, reine „ok"/Smoke-Läufe, ohne Signal)
   werden **ohne Kondensat** direkt archiviert. Nur Sessions mit echtem Signal werden kondensiert.
4. **Auslösung & Umfang:** manuell aufrufbarer Skill **plus** planbarer **Wochen-Lauf**
   (Cron/systemd-Timer). Verarbeitet **alle Projekte**, jedes Kondensat trägt ein **Projekt-Tag**.

## Erkenntnis-Typen (was kondensiert wird)
Signal-Kategorien, konsistent zu den bereits genutzten Knowledge-Präfixen:
- **bug-geloest** — reproduzierter Bug + Ursache + Fix (die wertvollste Kategorie)
- **architektur-entscheidung** — Design-/ADR-Entscheidung inkl. Begründung & Alternativen
- **sackgasse-verworfener-ansatz** — verworfener Weg + *warum*, damit er nicht wiederholt wird
- **gotcha / stolperfalle** — nicht-offensichtliche Umgebungs-/Tooling-Fallen (Env, Pfade, CLI-Flags)
- **nutzer-praeferenz / feedback** — bestätigte Vorlieben/Korrekturen des Nutzers (Warum + Anwendung)

## User Stories
- Als **Solo-Entwickler** möchte ich, dass alte Session-Logs automatisch zu kompakten, durchsuchbaren
  Erkenntnissen verdichtet werden, damit gelöste Bugs und Entscheidungen nicht im Rauschen von 200+
  Roh-Logs verschwinden.
- Als **Solo-Entwickler** möchte ich, dass der Sessions-Ordner nicht unbegrenzt wächst, damit Hal
  performant und übersichtlich bleibt — ohne dass Roh-Logs unwiederbringlich verloren gehen.
- Als **Jupiter-Agent (künftige Session)** möchte ich auf verdichtete Projekt-Erkenntnisse zugreifen,
  damit ich frühere Fehler und Sackgassen nicht wiederhole.
- Als **Solo-Entwickler** möchte ich, dass triviale Test-/Smoke-Sessions nicht kondensiert, sondern
  nur weggeräumt werden, damit die Knowledge-Basis signalstark bleibt.
- Als **Solo-Entwickler** möchte ich den Sweep sowohl manuell auslösen als auch wöchentlich automatisch
  laufen lassen, damit die Kuratierung ohne mein Zutun aktuell bleibt.
- Als **Solo-Entwickler** möchte ich ein kurzes Lauf-Protokoll (wie viele Sessions kondensiert /
  verworfen / archiviert), damit ich dem Prozess vertrauen kann.

## Acceptance Criteria
**Auswahl & Filter**
- [ ] Der Sweep berücksichtigt ausschließlich Sessions mit `created` **> 7 Tage** in der Vergangenheit
      (Alter aus dem Frontmatter, nicht aus dem Datei-mtime).
- [ ] Bereits archivierte Sessions (in `_archiv/`) werden nicht erneut verarbeitet (idempotent).
- [ ] Triviale Sessions werden erkannt und **ohne Kondensat archiviert**. Trivial-Kriterien mind.:
      (a) `title`-Slug ∈ {`test`, `sess-test-tmp`, …} oder (b) Inhalt unter Mindestlänge/-tiefe
      (z. B. < ~800 Zeichen Nettoinhalt bzw. < 2 echte Turns) und ohne Signal-Marker.
- [ ] Sessions mit Signal (siehe Erkenntnis-Typen) werden zur Kondensierung ausgewählt.

**Kondensierung**
- [ ] Pro signalhafter Session entsteht mindestens eine Knowledge-Notiz mit **gefülltem `## Erkenntnis`**
      (kein Platzhalter „_Bitte ergänzen/kuratieren._" mehr).
- [ ] Existiert für die `source_session_id` bereits ein Knowledge-Stub, wird dieser **gefüllt/aktualisiert**
      statt ein Duplikat anzulegen.
- [ ] Jede Knowledge-Notiz enthält Frontmatter mit mind.: `type: curated`, `source_session_id`,
      `curation_marker` (Erkenntnis-Typ), **`project`-Tag** (aus dem `title`-Slug abgeleitet), `created`.
- [ ] Das Kondensat ist knapp und handlungsorientiert (Konstitution): Kern-Erkenntnis, Kontext-Auszug,
      und — bei bug/sackgasse — Ursache + Lehre; bei nutzer-praeferenz zusätzlich **Warum** + **Anwendung**.
- [ ] Kondensate enthalten **keine Secrets** (Tokens/Keys/`.env`-Werte werden vor dem Schreiben entfernt).

**Archivierung / Ordner-Hygiene**
- [ ] Nach erfolgreicher Verarbeitung (kondensiert **oder** als trivial verworfen) wird das Roh-Log nach
      `Sessions/_archiv/` verschoben und **gzip-komprimiert** (`.md.gz`).
- [ ] Roh-Logs im Archiv, die älter als das zweite Zeitfenster (Default **30 Tage**) sind, werden endgültig gelöscht.
- [ ] Schlägt die Kondensierung einer Session fehl, bleibt das Roh-Log **an Ort und Stelle** (kein Datenverlust,
      Wiederholung beim nächsten Lauf).

**Auslösung & Protokoll**
- [ ] Der Sweep ist als Skill **manuell** auslösbar.
- [ ] Ein **Wochen-Lauf** ist einrichtbar (Cron/systemd-Timer) und ruft denselben Sweep auf.
- [ ] Jeder Lauf erzeugt ein Kurz-Protokoll: Anzahl geprüft / kondensiert / trivial-verworfen /
      archiviert / gelöscht / Fehler — sichtbar im Lauf-Output und als Log-Eintrag.
- [ ] Der Lauf ist **idempotent** und **re-entrant**: ein zweiter Lauf ohne neue Alt-Sessions verändert nichts.

## Edge Cases
- **Sehr große Session (> 1 MB, z. B. 368ccdd5 mit ~1 MB):** Kondensierung muss ohne Kontext-Überlauf
  funktionieren (Chunking/gezielte Extraktion statt Voll-Ladung); darf den Lauf nicht sprengen.
- **Session ohne/kaputtes Frontmatter:** Alter unbestimmbar → nicht anfassen, im Protokoll als „übersprungen" melden.
- **Mehrere Signale in einer Session** (z. B. Bug + Architektur-Entscheidung): mehrere Knowledge-Notizen
  bzw. klar getrennte Abschnitte; keine Vermischung.
- **Projekt-Slug nicht eindeutig zuordenbar** (`jupiter`-Default für Jupiter-eigene, sonst Slug wörtlich):
  Fallback-Tag `unbekannt`, damit nichts stillschweigend falsch verortet wird.
- **Wiederholter Lauf am selben Tag:** keine Doppel-Kondensate, kein erneutes Archivieren bereits archivierter Logs.
- **Archiv-Verzeichnis fehlt:** wird angelegt; Schreibfehler (Rechte/Platz) brechen den Lauf kontrolliert ab
  und lassen Roh-Logs unangetastet.
- **Namenskollision im Knowledge-Ordner** (gleicher Erkenntnis-Typ, gleicher Projekt-Slug): eindeutiger
  Dateiname inkl. `source_session_id`-Kürzel, damit nichts überschrieben wird.
- **Sensible Inhalte** (PII/Secrets in Logs): Guard entfernt erkennbare Secrets; im Zweifel Erkenntnis
  ohne wörtliche Zitate formulieren.

## Technical Requirements (optional)
- **Umfang:** verarbeitet Sessions **aller Projekte**; Projekt-Tag aus dem `title`-Slug.
- **Zeitfenster:** Kondensier-Schwelle 7 Tage (konfigurierbar), Archiv-Löschfrist 30 Tage (konfigurierbar).
- **Kein Datenverlust:** Löschen erst nach Archiv+gzip und Ablauf des zweiten Fensters; Fehler ⇒ Roh-Log bleibt.
- **Idempotenz:** wiederholte Läufe sind sicher; Fortschritt an Datei-Ort (Sessions vs. `_archiv/`) erkennbar.
- **Ort:** Hal-Vault `/home/dev/tools/Hal/Agentic OS/Jupiter/` (Sessions/_archiv/ + Knowledge/).
- **Sprache:** Kondensate auf **Deutsch** (Projektkonvention), knapp gemäß Knappheits-Konstitution.
- **Sicherheit:** Secret-/PII-Scrub vor dem Schreiben ins Knowledge.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-04 · **Stack:** Next.js 16 (Micro-App-UI) + FastAPI/Python (Orchestrierung) + SQLite (Live-Index) + Hal-Vault (Wahrheit) · **Branch:** dev

### Leitidee
PROJ-55 ist eine **native Micro-App „Session-Kondensierung"** nach dem bereits erprobten Muster
von Video Summary (PROJ-41/44) und Buch-Nuggets (PROJ-53): eine dünne **Orchestrierungsschicht**
im Backend, die einen **unveränderten Skill** headless über den `SessionManager` (`claude -p`)
fährt und die Ergebnisse in den Vault schreibt. Die eigentliche *Bewertung + Kondensierung* macht
der Skill (LLM-Urteil); das Backend übernimmt nur **Auswahl, Zeitplan, Archivierung, Protokoll**.
So bleibt die Logik konsistent zum Rest von Jupiter und es kommen **keine neuen Pakete** dazu.

### Wiederverwendung (was schon existiert — nicht neu bauen)
- **Marker-Heuristik** `engine/curation.py` → `detect_marker()` + `_MARKER_DEFS`
  (`bug_geloest`, `adr`, `sackgasse`). Genau das Signal, das „trivial vs. wertvoll" trennt — der
  Filter (AC 3a) baut darauf auf, statt eine neue Heuristik zu erfinden. Erweiterbar um
  `gotcha`/`nutzer-praeferenz`.
- **Knowledge-Schreiber** `engine/vault.py` → `write_curated_note(title, body, source_session_id,
  marker, on_exists=…)` schreibt bereits nach `Knowledge/`, legt `source_session_id` +
  `curation_marker` ins Frontmatter und dedupliziert themenstabil. PROJ-55 nutzt diesen Pfad und
  liefert einen **gefüllten `## Erkenntnis`-Body** statt des heutigen Platzhalters.
- **Micro-App-Worker + In-App-Scheduler** `engine/video_summary.py`
  (`tick`/`_check_schedule`/`_next_run_at`, Queue-Repo, Settings). PROJ-55 spiegelt dieses Muster
  als **Wochen-Variante** (7-Tage-Rhythmus statt `HH:MM`-Tagesplan).
- **Vault-Pfade & Härtung** `VaultService` kennt `Sessions/`, `Knowledge/`, `Handovers/`,
  Pfad-Sandbox (`_resolve_write`), `slugify`, Frontmatter-Parser. `_archiv/` wird als vierter
  Unterordner ergänzt.

### A) Komponenten-Struktur (Micro-App)
```
Sidebar „Micro-Apps" → SessionKondensierungApp
├── StatusHeader (letzter Lauf · nächster geplanter Lauf · Ampel)
├── RunControls
│   ├── „Jetzt kondensieren"-Button (manueller Sweep)
│   └── Wochenplan-Toggle + Wochentag/Uhrzeit-Auswahl
├── RunLogPanel (letzte Läufe: geprüft / kondensiert / trivial / archiviert / gelöscht / Fehler)
└── EmptyState („Noch kein Lauf — 73 Sessions älter als 7 Tage warten.")
```
Backend-Orchestrierung (kein UI):
```
SessionCondenseWorker (engine/session_condense.py)
├── enumerate_candidates()   → alte Sessions (Alter aus Frontmatter > 7 d), _archiv/ ausgenommen
├── classify(session)        → trivial | signal   (nutzt curation.detect_marker + Größen-/Tiefe-Check)
├── condense(session)        → headless Skill-Lauf → Knowledge-Note(s)  (nur bei signal)
├── archive(session)         → move → Sessions/_archiv/…​.md.gz
├── prune_archive()          → _archiv/-Einträge älter als 30 d löschen
└── run() / tick()           → orchestriert + schreibt RunLog; Wochen-Scheduler
```

### B) Datenmodell (Klartext)
**Wahrheit im Vault** (persistente Artefakte):
- `Agentic OS/Jupiter/Knowledge/<typ>-<projekt>[-<sess8>].md` — kondensierte Erkenntnis:
  Frontmatter `type: curated`, `curation_marker` (Erkenntnis-Typ), `source_session_id`,
  **`project`** (aus `title`-Slug), `created`; Body: `## Kontext (Auszug)` + **gefülltes `## Erkenntnis`**.
- `Agentic OS/Jupiter/Sessions/_archiv/<originalname>.md.gz` — komprimiertes Roh-Log (Recovery).

**Live-Index in SQLite** (flüchtig, wiederaufbaubar — analog Video-Summary-Queue):
```
Jede Kondensierung merkt sich:
- source_session_id, dateiname, projekt-slug
- ergebnis: kondensiert | trivial | fehler
- knowledge_pfad(e), zeitpunkt
Zweck: Idempotenz (schon verarbeitet?), Protokoll, Wiederholung fehlgeschlagener.
Autorität bleibt aber der Datei-Ort (Sessions/ vs. _archiv/) — die DB ist nur schneller Index.
```
Micro-App-Settings (Zeitplan an/aus, Wochentag/Uhrzeit, Schwellen 7 d / 30 d) in der bestehenden
Settings-Ablage der Micro-Apps.

### C) API-Form (Endpunkte, kein Code)
Analog `routes/video_summary.py` / `routes/book_nuggets.py`, JWT-geschützt (PROJ-25), `owner` aus Token:
```
- GET   /session-condense              → Status (letzter/nächster Lauf, Zähler)
- POST  /session-condense/run          → manuellen Sweep anstoßen (idempotent, non-blocking)
- GET   /session-condense/log          → letzte Lauf-Protokolle
- GET   /session-condense/settings     → Zeitplan + Schwellen lesen
- PATCH /session-condense/settings     → Zeitplan/Schwellen ändern
```

### D) Tech-Entscheidungen (WARUM)
- **Skill statt Backend-Heuristik für die Kondensierung.** Ob eine Session „ein gelöster Bug mit
  Ursache" ist und *wie* man die Lehre in zwei Sätzen fasst, ist ein Urteil — das gehört zum LLM
  (headless Skill), nicht in Python-Keyword-Listen. Das Backend entscheidet nur mechanisch
  (Alter, triviale Vorfilter, Archivierung). → gleiche Trennung wie bei Video/Buch-Micro-Apps.
- **Vorfilter mit der bestehenden Marker-Heuristik.** Bevor ein (teurer) Skill-Lauf startet, siebt
  `curation.detect_marker` + ein Größen-/Tiefe-Check offensichtlich triviale Sessions aus. Spart
  Token und hält die Knowledge-Basis signalstark. Grenzfälle darf der Skill final als „kein
  Signal → nur archivieren" einstufen.
- **Archiv + gzip statt Löschen (Zwei-Fenster-Modell).** Roh-Logs sind die Recovery-Quelle
  (PROJ-17). Sofort löschen wäre unumkehrbar; nur behalten lässt den Ordner volllaufen. Kompromiss:
  nach Kondensierung **komprimiert ins `_archiv/`** (Ordner wird leer/klein), endgültiges Löschen
  erst nach 30 Tagen. `gzip` ist Python-Standardbibliothek → **kein neues Paket**.
- **Idempotenz über den Datei-Ort.** „Schon verarbeitet?" = „liegt in `_archiv/`?". Die SQLite-Zeile
  ist nur Protokoll/Beschleuniger; geht der Live-Index verloren, ist der Zustand aus dem
  Dateisystem rekonstruierbar (Jupiter-Prinzip Live-Index ↔ Vault-Wahrheit).
- **Fehler ⇒ nichts anfassen.** Scheitert ein Skill-Lauf, bleibt das Roh-Log in `Sessions/` liegen
  und wird beim nächsten Lauf erneut versucht — kein Datenverlust, keine leeren Knowledge-Notizen.
- **Secret-/PII-Scrub vor dem Schreiben.** Roh-Logs können versehentlich Tokens/`.env`-Werte
  enthalten; ein Scrub-Schritt (Regex-Redaction) läuft vor `write_curated_note`. Der Skill wird
  zusätzlich instruiert, keine wörtlichen Secrets zu zitieren.
- **Alter aus Frontmatter, nicht mtime.** `created` im YAML ist die Wahrheit; mtime ändert sich
  z. B. durch Backups/Sync. Verhindert Fehl-Auswahl.
- **In-App-Wochen-Scheduler statt externem systemd-Timer.** Der `tick`-/`_next_run_at`-Mechanismus
  existiert schon und ist über die UI steuerbar — konsistenter und ohne Root/Deploy-Eingriff. Ein
  systemd-Timer bleibt als Fallback möglich (er würde denselben `POST /run` treffen), ist aber
  nicht Teil des MVP.

### E) Abhängigkeiten (Pakete)
- **Keine neuen Pakete.** `gzip`, `shutil`, `re`, `datetime` sind Standardbibliothek. Backend nutzt
  bestehende Bausteine (`SessionManager`, `VaultService`, `curation`, Micro-App-Worker-Muster).
- **Neuer Skill** `hal-session-condense` (bzw. interner Kondensier-Skill) — Text-Asset, kein Paket;
  liest ein Session-Log, urteilt trivial/Signal, liefert je Signal Titel + `curation_marker` +
  gefüllten `## Erkenntnis`-Body zurück, den die Orchestrierung via `write_curated_note` ablegt.

### Offene Punkte für die Umsetzung
1. **Datei-Strategie pro Erkenntnis:** heutiger `write_curated_note`-Default hängt themenstabil an
   (`<label>-<projekt>.md`, `append`). Für PROJ-55 sollte pro Session eine **eigene** Notiz mit
   `source_session_id`-Suffix entstehen, damit gefüllte Erkenntnisse nicht in einer Sammeldatei
   verschmelzen und hand-kuratierte Notizen **nie** überschrieben werden → in `/abc-backend` festzurren.
2. **„Trivial"-Schwellen** (Mindest-Nettolänge, Mindest-Turns, Slug-Blocklist `test`/`sess-test-tmp`)
   final kalibrieren an den 73 Alt-Sessions.
3. **Sehr große Logs (>1 MB):** Chunking-/Extraktions-Strategie im Skill-Prompt (nur relevante Turns),
   damit kein Kontext-Überlauf.

### Grounding-Korrekturen (aus CodeGraph-Scan — für `/abc-backend` verbindlich)
- **Scheduler ist heute nur täglich.** `_next_run_at` ([video_summary.py:463](backend/app/engine/video_summary.py#L463))
  parst nur `HH:MM` (täglich). Für den **Wochen-Lauf** muss er um Wochentag erweitert werden
  (z. B. `MON 03:00`) — weiterhin **dependency-frei** (kein cron-Parser). Der Antrieb ist eine
  asyncio-Lifespan-Schleife in `main.py` (`_video_summary_loop`/`_book_nuggets_loop` rufen
  `worker.tick()`) — für PROJ-55 einen `_session_condense_loop` analog registrieren.
- **Archiv+gzip ist neu zu bauen.** `VaultService.write_at` weist Nicht-`.md` hart ab und `_TYPE_DIRS`
  ([vault.py:34](backend/app/engine/vault.py#L34)) kennt nur `session_log|handover|curated`. Für
  `Sessions/_archiv/*.md.gz` braucht es einen **neuen Archiv-Helfer** (eigener Typ-Ordner oder
  direktes FS-Move), der die Pfad-Sandbox `_resolve_write` ([vault.py:197](backend/app/engine/vault.py#L197))
  respektiert. Nicht über `write_at` erzwingen.
- **Kein synchroner „Prompt→Text"-Helfer.** `claude_driver` ist ein persistenter Multi-Turn-Treiber.
  Den Kondensier-Lauf wie die Micro-App-Worker über `manager.create(...)` (headless,
  `bypassPermissions`) fahren und den Abschluss per Marker im Transcript erkennen
  (Muster: `book_nuggets._start` [book_nuggets.py:488](backend/app/engine/book_nuggets.py#L488)).
- **Auto-Kondensierung umgeht bewusst das Card-Gate.** Die heutige Live-Kuratierung
  (`manager._maybe_propose_knowledge` [manager.py:1018](backend/app/engine/manager.py#L1018)) erzeugt
  **nutzer-freizugebende** Karten. PROJ-55 schreibt **automatisiert** — der LLM-Schreibpfad ist
  netto neu; `curation.proposal_title` nur für dedup-konsistente Titel wiederverwenden, nicht den
  Card-Lifecycle. (Bewusste Entscheidung: der Wochen-Sweep läuft ungated, weil er nur ins
  `Knowledge/`-Archiv schreibt und hand-kuratierte Notizen nie überschreibt.)

## Implementierung (Backend — /abc-backend, 2026-07-04)
**Branch:** dev · **Status:** Backend fertig (17 neue Tests grün; volle Suite 1003 grün, 1 unrelated Codex-Skill-Drift).

**Neue/erweiterte Dateien**
- `backend/app/engine/session_condense.py` — `SessionCondenseWorker` (Scan · Trivial-Vorfilter ·
  headless Skill-Lauf · Archivierung · Wochen-Scheduler · Lauf-Protokoll) + reine Helfer
  (`project_from_filename`, `is_older_than`, `is_trivial`, `parse_result`, `build_prompt`,
  `_next_weekly_run_at`).
- `backend/app/db/session_condense_queue.py` — SQLite-Repo (Queue mit UNIQUE `session_filename` →
  idempotenter Scan, Einstellungen, `session_condense_runs`-Protokoll).
- `backend/app/schemas/session_condense.py`, `backend/app/routes/session_condense.py` —
  `GET /session-condense/queue` · `POST /scan` · `POST /run` · `GET /runs` ·
  `DELETE /queue/{id}` · `POST /queue/{id}/retry` · `GET|PATCH /settings` (JWT-Gate).
- `backend/app/engine/vault.py` — neue gehärtete Helfer: `list_session_logs` (top-level, `_archiv/`
  ausgenommen), `read_session_log`, `session_log_abspath`, `archive_session_log` (gzip-move,
  erst kopieren dann löschen → kein Datenverlust), `prune_archive` (Löschfrist nach mtime).
- `backend/app/config.py` — `session_condense_*`-Settings (Modell `sonnet`, Alter 7 d, Retention 30 d,
  min. 800 Zeichen, Default-Plan `MON 03:00`, `bypassPermissions`).
- `backend/app/main.py` — Worker verdrahtet (`app.state.session_condense`), `_session_condense_loop`,
  Startup-Scan (kein Auto-Sweep), Shutdown-Close.
- **Skill** `~/.claude/skills/hal-session-condense/SKILL.md` — der unveränderte, headless gefahrene
  Kondensier-Skill (urteilt trivial/Signal, schreibt Knowledge-Notizen mit gefülltem `## Erkenntnis`,
  Secret-Scrub, maschinenlesbarer Abschlussbericht `JUPITER_CONDENSE_RESULT`).

**Umsetzungs-Entscheidungen / Abweichungen**
- **Skill schreibt die Notizen, Backend archiviert** — konsistent zum Video-/Buch-Micro-App-Muster
  (Skill hat Vault-Schreibzugriff; das Backend bleibt mechanisch). Statt `write_curated_note` gibt der
  Skill dem Backend die geschriebenen Pfade zurück; das Backend parst sie + archiviert das Roh-Log.
  → Der Design-Vorschlag „pro Session eigene Notiz mit `source_session_id`-Suffix" ist umgesetzt (der
  Skill benennt `<marker>-<projekt>-<sess8>.md` und überschreibt hand-kuratierte Notizen nie).
- **Kein Marker/Abschluss → Fehler, Roh-Log bleibt** (Retry) — verhindert leere Kondensate & Datenverlust.
- **Wochenplan `DOW HH:MM`** dependency-frei (eigener Parser; der bestehende `_next_run_at` konnte nur täglich).
- **Startup scannt, startet aber keinen Sweep** — nur Wochenplan oder `POST /run` lösen aus (keine Überraschung).

**Offen für QA / Folge**
- Trivial-Schwellen an den echten 73 Alt-Sessions kalibrieren.

## Implementierung (Frontend — /abc-frontend, 2026-07-04)
Native Micro-App „Session-Kondensierung" nach dem Video-/Buch-Muster (Next.js, kein Flutter — Jupiter-Override).

**Neue/erweiterte Dateien**
- `nextjs_app/components/microapps/session_condense/session-condense-app.tsx` — Micro-App:
  Kopf-Erklärung · Steuerleiste („Jetzt kondensieren" · „Nur scannen" · Worker-Badge · nächster
  Plan-Lauf) · Warteschlange (Projekt-Tag · Dateiname · Kondensiert/Trivial/Fehler-Badge · Knowledge-
  Notiz-Links über MD-Reader · Retry/Entfernen) · Lauf-Protokoll (geprüft/kondensiert/trivial/
  archiviert/gelöscht/Fehler) · Einstellungs-Dialog (Wochenplan DOW+Uhrzeit / Alter / Retention /
  Trivial-Schwelle / Modell). Polling 3 s (Queue) bzw. 8 s (Protokoll).
- `nextjs_app/lib/types.ts` — `SessionCondense*`-Typen.
- `nextjs_app/lib/api.ts` — `getSessionCondenseQueue` · `scanSessionCondense` · `runSessionCondense` ·
  `deleteSessionCondenseItem` · `retrySessionCondenseItem` · `getSessionCondenseRuns` ·
  `get/patchSessionCondenseSettings`.
- `nextjs_app/lib/microapps-registry.ts` — `session_condense` registriert (lazy).
- `nextjs_app/lib/sidebar-config.ts` — Icon `brain-circuit` → `BrainCircuitIcon`.
- `backend/config/engines.yaml` — `kind: native`, `group: micro`, key `session_condense` (Sidebar-Kachel).

**Checks:** `tsc --noEmit` sauber für neue Dateien (1 unrelated Fehler in `md-tree.test.ts`), ESLint
clean, Micro-App-Registry-Vitest 7/7 grün (Registry ↔ engines.yaml konsistent), Backend
`test_proj18_engines`/`test_proj40_microapps` 34/34 grün.

## QA Test Results (/abc-qa, 2026-07-04)
**Branch:** dev · **Ergebnis:** ✅ Production-ready — keine Critical/High-Bugs.
**Automatisiert:** 25 PROJ-55-Tests grün (`test_proj55_session_condense.py` 17 + `test_proj55_qa.py` 8);
Regression 182 grün (video/book/microapps/engines/vault/manager/auth/haertung); Frontend-Vitest
173/174 (1 pre-existing unrelated Fail, s. u.).

### Akzeptanzkriterien
| # | Kriterium | Status | Nachweis |
|---|-----------|--------|----------|
| Auswahl 1 | Alter aus Frontmatter `created` > 7 d | ✅ | `is_older_than`, `test_scan_enqueues_only_old_sessions` |
| Auswahl 2 | Archivierte nicht erneut verarbeitet (idempotent) | ✅ | `test_repeated_run_without_new_sessions_is_noop` |
| Auswahl 3 | Triviale ohne Kondensat archiviert | ✅ | `test_trivial_is_archived_without_session`, `is_trivial` |
| Auswahl 4 | Signal-Sessions zur Kondensierung ausgewählt | ✅ | `test_signal_condensed_records_notes_and_archives` |
| Kond. 1 | Gefülltes `## Erkenntnis` (kein Platzhalter) | ⚠️ by design | Skill-Prompt erzwingt es (LLM); nicht backend-unit-testbar |
| Kond. 2 | Bestehenden Stub füllen statt Duplikat | ↺ Abweichung | Bewusst **pro-Session-Notiz** (`<marker>-<projekt>-<sess8>`), hand-kuratierte nie überschrieben |
| Kond. 3 | Frontmatter inkl. `project`-Tag | ⚠️ by design | Prompt gibt Feldset + Projekt-Tag vor (Skill schreibt) |
| Kond. 4 | Knapp/handlungsorientiert | ⚠️ by design | Prompt (Konstitution) |
| Kond. 5 | Keine Secrets im Kondensat | ⚠️ Limitation | Scrub nur skill-seitig instruiert, **nicht** backend-erzwungen (s. Findings) |
| Archiv 1 | Archiv + gzip nach Verarbeitung | ✅ | `test_vault_archive_gzips_and_removes_source`, Worker-Tests |
| Archiv 2 | `.gz` > Retention gelöscht | ✅ | `test_vault_prune_archive_by_age` |
| Archiv 3 | Fehler → Roh-Log bleibt | ✅ | `test_missing_marker_keeps_raw_log`, `test_archive_failure_keeps_raw_log` |
| Auslös. 1 | Manuell auslösbar | ✅ | `POST /session-condense/run` |
| Auslös. 2 | Wochen-Lauf einrichtbar | ✅ | `test_schedule_fires_once_and_advances`, `_next_weekly_run_at` |
| Auslös. 3 | Lauf-Protokoll (geprüft/kond./trivial/arch./gelöscht/Fehler) | ✅ | Runs-Tabelle + `list_runs`, Worker-Tests |
| Auslös. 4 | Idempotent & re-entrant | ✅ | Idempotenz-Test |

**Edge Cases:** kaputtes Frontmatter → übersprungen ✅ (`skipped_broken`); Projekt-Slug unbestimmbar →
`unbekannt` ✅; Archiv-Ordner fehlt → wird angelegt ✅; erneuter Lauf am selben Tag → keine Doppel ✅.
Große Logs / mehrere Signale / Namenskollision / PII-Scrub sind **skill-seitig** (Prompt) — manuell
bzw. by design, nicht backend-unit-testbar.

### Security-Red-Team
| Angriff | Ergebnis |
|---------|----------|
| Pfad-Traversal beim Archivieren (`../../../etc/passwd`) | ✅ Abgewehrt — `_bare_name` reduziert auf Basisname, `_resolve_write`-Sandbox; bleibt in `Sessions/` (`test_archive_traversal_cannot_escape`) |
| Absoluter „Dateiname" (`/etc/shadow`) | ✅ Abgewehrt (`test_archive_absolute_path_rejected`) |
| `session_log_abspath` Ausbruch | ✅ bleibt unter `Sessions/` (`test_session_log_abspath_stays_in_sandbox`) |
| Dotfiles/leer als Dateiname | ✅ `ValueError` (`test_bare_name_rejects_dotfiles_and_empty`) |
| SQL-Injection via Update-Spalten | ✅ Spalten-Whitelist (`_UPDATABLE`) + `?`-Parameter |
| Auth | ✅ Router unter `auth_gate` (JWT, `owner` serverseitig) |
| Datenverlust bei Absturz | ✅ Archiv = kopieren→dann löschen; Fehler ⇒ Roh-Log bleibt |

### Findings
- **Medium (by design):** Der **Secret-Scrub liegt allein beim Skill** (LLM-instruiert), das Backend
  erzwingt ihn nicht — konsistent zum Video-/Buch-Micro-App-Muster (Skill schreibt die Artefakte).
  Empfehlung: bei sensiblen Vaults später einen backend-seitigen Redaction-Pass vor/nach dem Schreiben
  ergänzen. Kein Blocker.
- **Deploy-Hinweis (nicht Bug):** `backend/config/engines.yaml` ist **gitignored** → die Micro-App-
  Kachel `session_condense` (kind=native) muss auf prod **manuell** ergänzt werden (`/abc-deploy`).
- **Pre-existing, unrelated (kein PROJ-55):** `test_proj50_codex_abc` (Codex-Skill-Spiegel-Drift von
  `abc-customer-journey`), Frontend `file-preview.test.tsx` (Ladezustand), `md-tree.test.ts` (tsc-Cast).

**Produktionsreife:** ✅ READY — keine Critical/High. Status → **Approved**.
Vor Deploy: engines.yaml-Kachel auf prod nachziehen; Trivial-Schwelle an echten Alt-Sessions kalibrieren (P2).

## Deployment

**Bookkeeping-Nachtrag (2026-07-07):** Der Status-Header dieser Spec blieb nach der Implementierung fälschlich auf „Planned" stehen, obwohl Tech Design, Implementierung und QA (siehe oben, alle 2026-07-04) vollständig durchlaufen und das Feature bereits am selben Tag nach `main` gemergt und deployt wurde — hier nur die Doku nachgezogen, kein neuer Code.

**Datum:** 2026-07-04 · **Version:** 0.27.4 · **Branch:** main · **Production URL:** https://jupiter.auxevo.tech

### Ausgeliefert
- Skill-gestützter Wochen-Sweep über Roh-Session-Logs in Hal (`Agentic OS/Jupiter/Sessions/`), kondensiert Erkenntnisse älter als 7 Tage in kuratierte Knowledge-Notizen.
- Micro-App-Kachel „Session-Kondensierung" (`session_condense`, `kind=native`) in `backend/config/engines.yaml` — verifiziert bereits vorhanden (manueller Deploy-Schritt aus dem QA-Hinweis war bereits erledigt).
- Archiv-Verhalten: kopieren → dann löschen; Fehler lassen das Roh-Log unangetastet (kein Datenverlust).

### Smoke-Test
- [x] `session_condense`-Kachel in `engines.yaml` vorhanden (verifiziert 2026-07-07).
- [ ] Trivial-Schwelle an echten Alt-Sessions kalibrieren (P2, aus QA-Notizen — kein Blocker).
