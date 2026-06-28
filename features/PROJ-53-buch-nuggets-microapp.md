# PROJ-53: Buch-Nuggets (native Micro-App)

## Status: Planned
**Created:** 2026-06-28
**Last Updated:** 2026-06-28

## Dependencies
- Requires: PROJ-40 (Sidebar-Sektion „Micro-Apps" + `kind: native`) — Buch-Nuggets ist eine **native Micro-App** (`group: micro`, `kind: native`, Route `/apps/<key>`, Eintrag in `microapps-registry.ts`), gleiches Muster wie PROJ-41.
- Requires: PROJ-1 (Engine-Treiber: Claude-Max-Session headless) — jede Buch-Umwandlung läuft als **headless Claude-Code-Session**.
- Requires: PROJ-2 / PROJ-24 (Vault-Anbindung) — die erzeugten Nuggets (md + Abbildungen + PDF) landen im Hal-Vault unter `04 Resources/Buch_Nuggets/`.
- Requires: PROJ-11 (Fileexplorer + Drag-and-Drop) — Vorbild/Bausteine für den Datei-Upload per Drag&Drop.
- Bezug: PROJ-51 (Engine-/Modellverwaltung) — die Modell-Auswahl speist sich aus der bestehenden Engine-/Modell-Registry.
- Bezug: PROJ-14/PROJ-16 (Session-Limits/Watchdog) — die Verarbeitungs-Sessions unterliegen denselben Limits wie reguläre Sessions.
- Vorbild (kein harter Dependency): PROJ-41/PROJ-44 (Video Summary) — UX-, Queue-, Worker- und Persistenz-Muster werden gespiegelt.

## Beschreibung
Eine native Micro-App **„Buch-Nuggets"** in der Sidebar-Sektion „Micro-Apps". Der Nutzer übergibt ein Buch — per **direkter Datei-URL**, **Upload** oder **Drag&Drop** (MVP-Formate: **pdf, epub, txt, docx**; `mobi` = Fast-Follow/Phase 2, s. Tech-Design G) — und die App erzeugt daraus eine strukturierte **Kurzform („Nugget")**: eine **Markdown-Notiz**, die **wichtigen extrahierten Abbildungen** und eine **konsolidierte PDF-Version**. Alles wird im **Hal Second Brain** unter `04 Resources/Buch_Nuggets/` gespeichert.

Die App ist GUI + Orchestrierungs-Schicht analog zur Video Summary: pro Buch startet das Backend eine **headless Claude-Code-Session**, die das Buch parst, in die unten definierten Blöcke konsolidiert, das **Contra-Kapitel** recherchegestützt erzeugt und die Artefakte rendert + ablegt. Bücher werden — wegen Größe und Kosten — **sequenziell** (eine Session zur Zeit) verarbeitet; eine **Warteschlange** nimmt mehrere Bücher auf.

### Nugget-Datenmodell (Inhalt der erzeugten Markdown-Notiz)
Schwerpunkt: **Technik- und Finanzbücher.** Jede Notiz besteht aus:
1. **1-Satz-Kernaussage** — was will der Autor beweisen?
2. **Executive Summary** — 5–10 Bullet Points, ohne Ausschmückung.
3. **Core Concepts** — Begriffe, Definitionen, Prinzipien.
4. **Tools/Frameworks** — Methoden, Entscheidungslogiken, Checklisten, Modelle.
5. **Numbers/Evidence** — Statistiken, Benchmarks, Formeln, Studien, Annahmen — **mit Seitenzitat verankert** (Seite X) gegen Halluzination.
6. **Examples/Case Studies** — konkrete Anwendung oder Gegenbeispiele.
7. **Actionable Takeaways** — was kann der Leser morgen anwenden?
8. **Assumptions** — auf welchen (oft unausgesprochenen) Annahmen ruht das Buch?
9. **Critique** — interne Schwächen/Lücken des Buches.
10. **Contra-Kapitel** *(Differenzierer)* — geht **über den Buchinhalt hinaus**: mögliche **Gegenbeweise**, warum die Aussagen falsch oder lückenhaft sein könnten. **Recherchegestützt** — pro Kernthese 1–2 belegte Gegenpositionen **mit Quelle** (kein freies Meinen).
11. **Action Items** — umsetzbare Schritte.

### Geklärte Entscheidungen (Brainstorm 2026-06-28, D1–D11)
- **D1 — Eingabe-„Link":** Ein Link = **direkte URL zu einer Buchdatei** (pdf/epub/…). Metadaten-Links (Goodreads/Amazon o. Ä.) liefern keinen Volltext → daraus werden **keine** Nuggets erzeugt (deutsche Fehlermeldung, Volltext anfordern). Zusätzlich **Upload** und **Drag&Drop**.
- **D2 — Verarbeitungsmodell:** **Async-Job mit sichtbarem Fortschritt** (Hochladen → Parsen → Analyse → Abbildungen → Contra-Recherche → PDF-Bau → in Hal abgelegt). Kein Browser-Blocking.
- **D3 — Parsing/Chunking:** **Map-Reduce** — Format zuerst zu Text+Bildern vereinheitlichen, kapitel-/abschnittsweise Zwischen-Extrakte, dann Konsolidierung in die 11 Blöcke.
- **D4 — Abbildungs-Auswahl:** Alle Figuren extrahieren → die Session **wählt per Bildunterschrift + Umgebungstext** die relevanten aus und referenziert sie an der passenden Stelle im md (wie `hal-video-summary` Frames einbettet).
- **D5 — Contra-Engine:** **Web-recherchegestützt** (deep-research-Pattern light), belegte Gegenpositionen mit Quelle.
- **D6 — Zahlen-Grounding:** „Numbers/Evidence" mit **Seitenzitat** verankert.
- **D7 — Modell-Auswahl (Kosten):** **Dropdown** aus der Engine-/Modell-Registry (PROJ-51). **Default: Stufen-Logik** (günstiges Modell für Chunk-Extrakte, starkes Modell für Konsolidierung + Contra) mit **Umschalter „global ein Modell für alles"**. **Kostenschätzung vor dem Start** (aus Seitenzahl/Tokens) + optionales **Seitenlimit**.
- **D8 — Hal-Ablage:** Zielordner `04 Resources/Buch_Nuggets/`. Pro Buch: `…/<Autor>-<Titel>/<Autor>-<Titel>.md` + Unterordner `figures/` + konsolidierte PDF.
- **D9 — Re-Run/Duplikate:** Erkennung über Titel/Hash → fragen **„überschreiben oder neue Version?"**.
- **D10 — MVP-Grenze:** Quiz, Karteikarten, Mehr-Buch-Vergleich, „apply to my business" = **Phase 2**, nicht MVP.
- **D11 — Sprache:** Nuggets **deutsch**; Fachbegriffe/Zitate im Original.

## User Stories
- Als Nutzer möchte ich ein Buch per **Datei-URL, Upload oder Drag&Drop** (pdf/epub/mobi/txt/docx) übergeben, um daraus eine strukturierte Kurzform erzeugen zu lassen.
- Als Nutzer möchte ich vor dem Start das **KI-Modell wählen** (und zwischen Stufen-Logik und „ein Modell für alles" umschalten), damit die Verarbeitung nicht zu teuer wird.
- Als Nutzer möchte ich **vor dem Start eine Kostenschätzung** (basierend auf Seitenzahl/Tokens) sehen und optional ein **Seitenlimit** setzen.
- Als Nutzer möchte ich den **Fortschritt** pro Buch sehen (Wartend · Parsen · Analyse · Contra-Recherche · PDF · Fertig · Fehler).
- Als Nutzer möchte ich, dass die fertige Notiz die **11 Blöcke inkl. Contra-Kapitel**, die **wichtigen Abbildungen** und eine **konsolidierte PDF** enthält und unter `04 Resources/Buch_Nuggets/` im Vault liegt.
- Als Nutzer möchte ich bei „Fertig" die erzeugte **Notiz/PDF im Vault öffnen** können.
- Als Nutzer möchte ich bei einem **bereits verarbeiteten Buch** wählen können, ob ich **überschreibe oder eine neue Version** anlege.
- Als Nutzer möchte ich einen **fehlgeschlagenen** Eintrag **erneut versuchen** oder einen Eintrag aus der Warteschlange **entfernen** können.

## Acceptance Criteria
- [ ] **Buch-Nuggets** erscheint als Eintrag in der Sidebar-Sektion „Micro-Apps" (`group: micro`, `kind: native`) mit Label + Icon und öffnet als Vollbild unter `/apps/<key>`.
- [ ] Die App ist als **native** Micro-App umgesetzt (React-Komponente im Repo, registriert in `microapps-registry.ts`) — **kein** iFrame.
- [ ] Eingabe akzeptiert **(a) eine direkte Datei-URL, (b) Datei-Upload, (c) Drag&Drop**. Akzeptierte Formate: **pdf, epub, mobi, txt, docx**; andere Formate werden mit deutscher Fehlermeldung abgewiesen.
- [ ] Ein **Metadaten-Link** (z. B. Goodreads/Amazon-Produktseite) ohne abrufbaren Volltext wird **abgewiesen** mit deutscher Erklärung (Volltext/Datei anfordern) — es wird **kein** Nugget aus reinen Metadaten erzeugt.
- [ ] Vor dem Start zeigt die App eine **Kostenschätzung** (aus Seitenzahl/geschätzten Tokens) und erlaubt ein optionales **Seitenlimit**.
- [ ] Ein **Modell-Dropdown** (gespeist aus der Engine-/Modell-Registry) erlaubt die Modellwahl; ein **Umschalter** wählt zwischen **Stufen-Logik** (günstig für Extrakte, stark für Konsolidierung + Contra) und **„ein Modell für alles"**.
- [ ] Eine **Warteschlangen-/Verlaufsliste** zeigt alle Bücher mit Status **Wartend · Läuft · Fertig · Fehler** (bei „Läuft" zusätzlich die aktuelle Phase: Parsen/Analyse/Contra/PDF).
- [ ] Bücher werden **sequenziell** verarbeitet (eine Verarbeitungs-Session gleichzeitig).
- [ ] Jede Verarbeitung erzeugt im Vault unter `04 Resources/Buch_Nuggets/<Autor>-<Titel>/`: **(a)** eine **Markdown-Notiz** mit allen **11 Blöcken inkl. Contra-Kapitel**, **(b)** die **relevanten Abbildungen** (in `figures/`, im md referenziert), **(c)** eine **konsolidierte PDF**.
- [ ] Der Block **„Numbers/Evidence"** verankert Zahlen/Formeln mit **Seitenzitat** (Seite X).
- [ ] Das **Contra-Kapitel** enthält **recherchegestützte** Gegenpositionen **mit Quellenangabe** (keine quellenlosen Behauptungen).
- [ ] Bei **bereits verarbeitetem Buch** (Titel/Hash erkannt) fragt die App **„überschreiben oder neue Version?"** und handelt entsprechend (kein stilles Überschreiben).
- [ ] Bei Status **„Fertig"** zeigt der Eintrag **Links** auf Notiz und PDF im Vault.
- [ ] Bei Status **„Fehler"** wird eine knappe Ursache angezeigt und **„Erneut versuchen"** angeboten; die übrigen Einträge bleiben unberührt.
- [ ] Einzelne Einträge lassen sich **entfernen**.
- [ ] Warteschlange + App-Einstellungen (Modellwahl, Stufen-Logik, Seitenlimit) **überleben Reload/Neustart** (persistiert, serverseitig).
- [ ] Die Verarbeitung läuft **serverseitig weiter**, auch wenn der Tab geschlossen / gewechselt wird; der Status wird beim Wiederöffnen korrekt angezeigt.
- [ ] Alle Nugget-Inhalte sind **deutsch** (Fachbegriffe/Zitate im Original); alle UI-Texte/Fehlermeldungen **deutsch** (App-Eigenname „Buch-Nuggets" bleibt).

## Edge Cases
- **DRM-geschützte Datei** (häufig bei Kindle-`mobi`/Adobe-`epub`) → Parsen schlägt fehl → Status „Fehler" mit deutscher Ursache („DRM-geschützt, nicht lesbar"); kein Teil-Nugget.
- **Format vorhanden, aber `mobi` auf dem Host nicht konvertierbar** (Toolchain fehlt) → klare Fehlermeldung statt stillem Hängen (siehe Open Point — Konvertierungs-Toolchain).
- **Sehr großes Buch** (z. B. 800+ Seiten) → Kostenschätzung warnt; optionales Seitenlimit greift; Map-Reduce verhindert Kontext-Überlauf.
- **Buch ohne Abbildungen** (reiner Text / txt) → md wird ohne `figures/` erzeugt; Hinweis „keine Abbildungen gefunden", kein Fehler.
- **Gescanntes PDF ohne Textebene** (nur Bilder) → entweder OCR (falls vorgesehen) oder Status „Fehler/eingeschränkt" mit deutscher Erklärung; keine halluzinierte Zusammenfassung.
- **Ungültige / nicht erreichbare Datei-URL** → Eintrag „Fehler" mit Ursache; blockiert die Queue nicht.
- **Duplikat-Buch** (Titel/Hash schon vorhanden) → D9-Dialog „überschreiben oder neue Version?"; kein stiller Doppel-Eintrag.
- **Contra-Recherche findet keine belastbaren Quellen** → Contra-Kapitel weist das transparent aus („keine belastbaren Gegenquellen gefunden") statt etwas zu erfinden.
- **Autor/Titel nicht sicher erkennbar** (fehlende Metadaten) → Fallback-Dateiname (z. B. aus Originaldateinamen) + Hinweis; keine Ablage-Kollision.
- **App geschlossen / Backend-Neustart mitten in der Verarbeitung** → serverseitiger Worker setzt fort bzw. `running`→`pending` beim Start (kein Verlust der Warteschlange).
- **Sektion „Micro-Apps" im Konfig-Panel ausgeblendet** → App per Direkt-URL `/apps/<key>` weiter erreichbar (wie PROJ-40/41).
- **Kostenschätzung deutlich überschritten** (reale Tokens > Schätzung) → Verarbeitung läuft im Rahmen der normalen Session-Limits (PROJ-14/16) weiter; kein hartes Abbrechen erforderlich, aber Schätzung ist „best effort" zu kennzeichnen.

## Technical Requirements (optional)
- **Native Micro-App-Muster (PROJ-40/41):** Metadaten-Eintrag in `backend/config/engines.yaml` (`kind: native`, `group: micro`, Label, Icon); Code unter `nextjs_app/components/microapps/<key>/`, registriert in `nextjs_app/lib/microapps-registry.ts`; Render über die kind-Verzweigung in `app/(cockpit)/apps/[key]/page.tsx`.
- **Upload/Drag&Drop:** Datei-Upload-Endpunkt (Größenlimit beachten) + Drag&Drop im Frontend (Vorbild PROJ-11). Hochgeladene Datei wird serverseitig zwischengespeichert, an die Verarbeitungs-Session übergeben und nach Abschluss aufgeräumt. Object-Storage (MinIO) **nicht** erforderlich — Artefakte liegen im Hal-Vault (Dateisystem), wie bei Video Summary.
- **Verarbeitungs-Mechanik:** Backend-Worker startet pro Buch eine **headless Claude-Code-Session** (PROJ-1), die das Buch parst (Map-Reduce), die 11 Blöcke konsolidiert, das Contra-Kapitel recherchiert, Abbildungen wählt und md+figures+PDF rendert + im Vault ablegt. **Sequenziell** (eine Session zur Zeit). `permission_mode=bypassPermissions` (headless, kein interaktives Decision-Card-Gate) — dokumentierte Architektur-Entscheidung wie PROJ-41.
- **Processing-Skill/Prompt:** Es existiert **noch kein** `hal-book-nuggets`-Skill (analog `hal-video-summary`). `/abc-architecture` entscheidet, ob ein **neuer Skill** angelegt oder der Ablauf als **strukturierter Prompt** umgesetzt wird; er nutzt das **`pdf`-Skill-Muster** (Markdown→PDF mit Bild-Embedding) und das **`deep-research`-Pattern** (Contra-Quellen).
- **Format-Konvertierung:** Vereinheitlichung zu Text+Bildern. `pandoc` ist auf dem Host vorhanden (docx/epub/txt/html). **`mobi`** benötigt zusätzliche Toolchain (z. B. `calibre`/`ebook-convert`) — **derzeit nicht installiert** (siehe Open Point); ggf. Host-Setup nötig.
- **Modell-Auswahl/Stufen-Logik:** Modell-Optionen aus der Engine-/Modell-Registry (PROJ-51). Stufen-Logik bzw. „ein Modell für alles" pro Lauf wählbar und persistiert.
- **Persistenz:** Warteschlange/Verlauf (Quelle, Titel/Hash, gewähltes Modell, Status+Phase, Ergebnis-Pfade, Kostenschätzung, Zeitstempel, owner) + App-Einstellungen. Konsistent mit dem bestehenden Jupiter-Muster (**SQLite** + asyncio-Worker im Lifespan, Vorbild `db/session_index.py` + `video_summary_queue.py`) — kein neues Infra-Teil. `owner`-Feld (single-user-MVP).
- **API:** neue FastAPI-Routen für Upload, Queue-CRUD, Trigger, Kostenschätzung und Einstellungen (`backend/app/routes/`), Schemas in `backend/app/schemas/`.
- **Frontend:** React-Komponente (Tailwind + shadcn/ui), Zustände Loading/Error/Empty/Success explizit; Polling/Refresh des Status.
- **Texte deutsch.** Kein Auth/RLS im MVP (Projekt-Entscheidung), `owner`-Feld vorbereitet.

### Open Points (für /abc-architecture zu entscheiden)
1. **`mobi`-Konvertierung:** `calibre`/`ebook-convert` auf dem Host installieren — oder `mobi` im MVP als „nicht unterstützt" markieren? (pandoc deckt docx/epub/txt/html ab.)
2. **Gescanntes PDF / OCR:** OCR im MVP vorsehen oder als „eingeschränkt/Fehler" behandeln?
3. **Kostenschätzungs-Formel:** Tokens/Seite + Preis pro Engine kalibrieren (Quelle: Engine-/Modell-Registry).
4. **Web-Recherche-Budget** fürs Contra-Kapitel begrenzen (Anzahl Suchen/Thesen) — Kosten + Laufzeit.
5. **Versionierungs-Schema** bei „neue Version" (D9) — Suffix/Timestamp im Dateinamen.
6. **Neuer Skill vs. Inline-Prompt** für die Verarbeitung (s. o.).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-28 · **Stack:** Next.js 16 (native Micro-App) + FastAPI/asyncio-Worker + **SQLite** (kein Postgres/RLS im MVP) + **neuer Skill `hal-book-nuggets`** · **Branch:** dev

### Grundhaltung
Buch-Nuggets ist **Video Summary (PROJ-41) für Bücher** — dasselbe bewährte Muster wird geklont und nur dort verändert, wo Bücher anders sind als Videos. Wir erfinden **keine** neue Infrastruktur: SQLite-Queue + asyncio-Worker im Lifespan + native React-Micro-App, exakt wie PROJ-41 (`video_summary_queue.py`, `engine/video_summary.py`, `routes/video_summary.py`, Registry-Wiring). **Alle** schwere Verarbeitung (Parsen, Map-Reduce, Abbildungen, Contra-Recherche, PDF-Bau, Vault-Ablage) steckt in **einem neuen Skill `hal-book-nuggets`** — das Backend ist nur GUI + Orchestrierung + Drossel, identisch zur Video-Summary-Philosophie.

**Drei Unterschiede zu Video Summary** (und wie wir sie lösen):
1. **Quelle ist eine Datei, nicht eine URL** → zusätzlich Upload/Drag&Drop (bestehender `/files/upload`-Endpunkt wird wiederverwendet).
2. **Modellwahl mit Stufen-Logik + Kostenschätzung** (D7) → zwei Modell-Felder + ein Schätz-Endpunkt; Stufen-Logik wird **im Skill** über Claude-Code-Sub-Agenten mit Modell-Override realisiert.
3. **Es gibt noch keinen Verarbeitungs-Skill** → wir legen `hal-book-nuggets` neu an (Video Summary konnte `hal-video-summary` wiederverwenden).

### A) Komponenten-Struktur (UI-Baum)
```
/apps/book_nuggets  (native, Vollbild)
└── BuchNuggetsApp
    ├── EingabeKarte
    │   ├── Dropzone (Drag&Drop) + Datei-Upload-Button  (pdf/epub/txt/docx)
    │   ├── ODER Textfeld „Direkte Datei-URL"
    │   ├── Modell-Steuerung:
    │   │     • Umschalter „Stufen-Logik | Ein Modell für alles"
    │   │     • Dropdown „Extrakt-Modell" (günstig)  + Dropdown „Konsolidierungs-/Contra-Modell" (stark)
    │   │       (bei „Ein Modell": nur ein Dropdown)
    │   ├── optionales Seitenlimit
    │   ├── Kostenschätzung (erscheint nach Auswahl der Quelle) + Button „Zur Warteschlange hinzufügen"
    │   └── Inline-Validierung (deutsch)
    ├── SteuerLeiste
    │   ├── Button „Jetzt ausführen"
    │   ├── Status-Badge: Leerlauf · Läuft (mit Phase) · Fehler
    │   └── Button „Einstellungen"  → Dialog (Default-Modellmodus, Default-Seitenlimit)
    ├── WarteschlangenListe
    │   └── BuchZeile (Titel/Dateiname · Status-Badge Wartend/Läuft/Fertig/Fehler ·
    │        bei Läuft: aktuelle Phase Parsen/Analyse/Contra/PDF ·
    │        bei Fertig: Links „Notiz öffnen"/„PDF" · bei Fehler: Ursache + „Erneut versuchen" · „Entfernen")
    ├── Bibliotheks-Tab (read-only Liste erzeugter Nuggets, wie PROJ-44)
    ├── Duplikat-Dialog (D9): „Buch bereits vorhanden — Überschreiben oder Neue Version?"
    ├── EmptyState („Noch keine Bücher in der Warteschlange")
    └── Lade-/Fehlerzustand (Polling alle ~5 s)
```
Registry-Wiring wie PROJ-41: `engines.yaml`-Eintrag (`key: book_nuggets`, `kind: native`, `group: micro`, `icon: book`) + `microapps-registry.ts` (`book_nuggets → lazy(import …)`) + Render über den native-Zweig in `app/(cockpit)/apps/[key]/page.tsx`. Direkt-URL `/apps/book_nuggets` bleibt auch bei ausgeblendeter Sektion erreichbar.

### B) Datenmodell (Klartext — SQLite, kein Postgres/RLS)
**Tabelle `book_nuggets_queue`** (eine Zeile pro Buch):
- `id`, `owner` (single-user-MVP)
- `source_type` (`url` | `upload`), `source_ref` (die URL **oder** der Pfad der hochgeladenen Datei)
- `title`, `author`, `book_hash` (für Duplikaterkennung D9 — Hash der Quelldatei + erkannter Titel)
- `model_mode` (`staged` | `single`), `model_extract`, `model_consolidate` (bei `single` beide gleich)
- `page_limit` (optional), `cost_estimate` (best-effort, beim Einreihen berechnet)
- `status` (`pending` · `running` · `done` · `error`), `phase` (frei: `parsing` · `analysis` · `contra` · `pdf` — nur Anzeige bei `running`)
- `result_dir`, `result_note_path`, `result_pdf_path` (gefüllt bei `done`)
- `error_message`, `session_id`, `created_at`, `started_at`, `finished_at`

**Tabelle `book_nuggets_settings`** (1 Zeile): `default_model_mode`, `default_model_extract`, `default_model_consolidate`, `default_page_limit`, `output_subdir`. Modell-Whitelist serverseitig (wie PROJ-41 `VALID_MODELS`, Schutz vor Slug-Falle PROJ-18).

Persistenz wie `session_index.py`/`video_summary_queue.py`: `CREATE TABLE IF NOT EXISTS` + idempotente Migrationen, Zugriff via `asyncio.to_thread`, WAL. **Queue + Einstellungen überleben Neustart**; beim Start `running`→`pending` (verwaiste Sessions), Laufzeit-Zustand (draining) nur im Speicher.

### C) Verarbeitungs-Ablauf (Worker + Skill)
**Worker** (Klon von `VideoSummaryWorker`, asyncio-Tick im Lifespan, **sequenziell — eine Session zur Zeit**):
1. Nächsten `pending`-Eintrag nehmen (nur wenn keine Session läuft).
2. Headless Claude-Session starten: `SessionManager.create(project_path=<Vault-Root>, initial_prompt=…, model=<Konsolidierungs-Modell>, permission_mode="bypassPermissions")`. Bei Upload wird die Datei vorher in einen vault-skopierten Arbeitsordner gelegt; der Prompt nennt Dateipfad, Output-Subdir, Modellmodus, Seitenlimit.
3. Session-Transcript überwachen, am Ende Ergebnis-Pfade aus einem `JUPITER_BOOK_RESULT`-Block parsen (`note:`/`pdf:`/`dir:`), Eintrag auf `done`, Session stoppen (Slot freigeben, PROJ-14). Fehler → `error` + Ursache. Phase-Updates best-effort aus Transcript-Markern.

**Drossel:** Bücher blocken nicht wie YouTube → **kein** Cooldown nötig; die Sequenzialität (eine Session) + die bestehenden Session-Limits (PROJ-14/16) genügen. **Kein Zeitplan im MVP** (Bücher werden ad-hoc hochgeladen, nicht als wiederkehrende Queue) — „Jetzt ausführen" + automatischer Drain reichen.

**Neuer Skill `hal-book-nuggets`** (Host-seitig, analog `hal-video-summary`) — kapselt:
- **Parsen/Vereinheitlichen** zu Text+Bildern: `pandoc` (epub/docx/txt/html, auf dem Host vorhanden) bzw. PDF-Textextraktion; Abbildungen + Bildunterschriften extrahieren.
- **Map-Reduce** (D3): pro Kapitel/Chunk Zwischen-Extrakte → Konsolidierung in die **11 Blöcke**.
- **Stufen-Logik (D7):** Die Session läuft auf dem **starken** Modell (Konsolidierung + Contra); die **günstigen Chunk-Extrakte** werden als **Claude-Code-Sub-Agenten mit Modell-Override** ausgeführt. Bei `model_mode=single` entfällt der Override → ein Modell für alles. (So ist „zwei Modelle in einem Lauf" sauber umsetzbar — eine headless `claude`-Session hat genau ein Haupt-Modell, Sub-Agenten dürfen ein anderes nutzen.)
- **Abbildungs-Auswahl (D4):** relevante Figuren wählen + im md referenzieren.
- **Contra-Kapitel (D5):** Web-Recherche-Pattern (light), **gedeckelt** (z. B. max. 3 Kernthesen × 1–2 Suchen), belegte Gegenpositionen mit Quelle.
- **Zahlen-Grounding (D6):** „Numbers/Evidence" mit Seitenzitat.
- **Rendern + Ablage (D8):** md + `figures/` + konsolidierte PDF (über das bestehende **`pdf`-Skill-Muster**) nach `04 Resources/Buch_Nuggets/<Autor>-<Titel>/`; am Ende `JUPITER_BOOK_RESULT`-Block mit den Pfaden ausgeben.

### D) API-Shape (neue Routen, kein Code) — Router `backend/app/routes/book_nuggets.py`
```
GET    /book-nuggets/queue              → Warteschlange + Worker-State (Polling)
POST   /book-nuggets/upload             → Datei-Upload (Wiederverwendung der /files-Mechanik/Scope-Guard) → liefert staged Pfad
POST   /book-nuggets/estimate           → Body {source_type, source_ref, model_mode, modelle} → {pages?, est_tokens, est_cost} (best-effort, vor dem Einreihen)
POST   /book-nuggets/queue              → Buch einreihen (Body: Quelle + Modellmodus/Modelle + Seitenlimit + on_duplicate?: overwrite|new_version) → 409 bei Duplikat ohne on_duplicate (D9)
DELETE /book-nuggets/queue/{id}         → Eintrag entfernen
POST   /book-nuggets/queue/{id}/retry   → fehlgeschlagenen Eintrag erneut einreihen
POST   /book-nuggets/run-now            → Drain sofort starten
GET    /book-nuggets/library            → erzeugte Nuggets (Scan des Output-Subdir, read-only)
GET    /book-nuggets/settings           → Defaults lesen
PATCH  /book-nuggets/settings           → Defaults ändern
```
Kein Auth/RLS (MVP-Entscheidung); `owner` gestempelt, nicht gefiltert. Upload + URL serverseitig auf erlaubte Formate + `allowed_roots`-Scope geprüft.

### E) Tech-Entscheidungen (WARUM)
- **Klon statt Neubau:** Jupiter ist SQLite + In-Memory + Lifespan-Tasks. Wir spiegeln `video_summary_*` 1:1 — kleinster, konsistentester Eingriff, kein Postgres/Celery/Broker.
- **Schwere Arbeit im Skill, nicht im Backend:** Genau wie Video Summary. Das Backend kennt keine PDF/EPUB-Parser, keine PDF-Erzeugung, keine Web-Recherche — und soll sie nicht kennen. Der Skill ist der austauschbare, testbare Verarbeitungskern.
- **Stufen-Logik via Sub-Agenten-Modell-Override:** ehrliche Umsetzung von „günstig für Extrakte, stark für Konsolidierung" innerhalb **einer** headless Session (eine `claude`-Session = ein Haupt-Modell; Sub-Agenten dürfen abweichen).
- **Upload wiederverwenden:** `/files/upload` existiert inkl. Scope-Guard (`allowed_roots`) und Größenlimit — kein zweiter Upload-Pfad.
- **Kostenschätzung „best-effort":** Seitenzahl × Tokens/Seite × Preis pro Modell; bewusst Schätzung (kein hartes Abbrechen) — reale Limits regeln weiterhin PROJ-14/16.
- **Kein Zeitplan/Cooldown im MVP:** Bücher sind Einzel-Uploads ohne Block-Risiko → Sequenzialität genügt; spart Komplexität.
- **bypassPermissions:** headless kann kein Decision-Card-Gate bedienen (dokumentierte Architektur-Entscheidung wie PROJ-41); cwd ist vault-skopiert, Prompt fest auf `/hal-book-nuggets`.
- **Kein MinIO:** Artefakte liegen im Hal-Vault (Dateisystem).

### F) Abhängigkeiten
- **Backend:** keine neuen Pakete (SQLite/asyncio stdlib, `SessionManager`/`/files` vorhanden, `lucide-react`-Icon `book`, shadcn/ui vorhanden).
- **Host (Skill-seitig):** `pandoc` (vorhanden). PDF-Textextraktion + Abbildungs-Extraktion (z. B. `PyMuPDF`/`pdfplumber`) + `pdf`-Skill (vorhanden) — werden beim Skill-Setup eingerichtet, nicht im Jupiter-Repo.
- **Upload-Whitelist:** `epub` (und ggf. `mobi`) in `upload_allowed_extensions` (`config.py`) ergänzen — `pdf/txt/docx` sind bereits drin.

### G) Offene Punkte — ENTSCHIEDEN (User-Freigabe 2026-06-28)
1. **`mobi`:** ✅ **MVP ohne `mobi`** (pdf/epub/txt/docx). `mobi` wird mit klarer deutscher Meldung als „nicht unterstützt" abgewiesen (calibre nicht installiert, nur `pandoc`); Calibre-Host-Setup als Fast-Follow/Phase 2.
2. **Gescanntes PDF / OCR:** ✅ **kein OCR im MVP.** Kein Text-Layer → „Fehler: kein extrahierbarer Text" statt halluzinierter Zusammenfassung.
3. **Verarbeitungs-Skill:** ✅ **neuer Skill `hal-book-nuggets`** (Pipeline zu komplex für einen Inline-Prompt; testbar, wartbar, spiegelt `hal-video-summary`).
4. **Versionierung bei „neue Version" (D9):** ✅ **Zeitstempel-Suffix** im Ordnernamen (`<Autor>-<Titel>--vYYYYMMDD-HHMM`).
5. **Contra-Recherche-Budget:** ✅ **max. 3 Kernthesen × 1–2 Suchen**, im Skill fest gedeckelt (Kosten/Laufzeit).

### H) Bau-Reihenfolge / Hand-offs
1. **Skill** `hal-book-nuggets` anlegen + Host-Tools (Backend-Dev/Setup, vor dem Worker testbar machen).
2. **Backend** (`/abc-backend`): SQLite-Tabellen + Repo, Worker im Lifespan, Routen + Schemas, Upload-Anbindung, `config.py`-Defaults (`book_nuggets_*`), Estimate-Endpunkt, Duplikat-Logik.
3. **Frontend** (`/abc-frontend`): `engines.yaml`/Registry-Eintrag + Komponente (Dropzone/URL, Modell-Steuerung, Kostenschätzung, Queue-Liste mit Polling, Bibliotheks-Tab, Duplikat-Dialog, Einstellungen).
4. **QA** (`/abc-qa`): ACs + Upload/Format-Validierung + Stufen-Logik-Beleg + Duplikat-Dialog + Persistenz über Neustart + Direkt-URL.
> Reihenfolge **Skill → Backend → Frontend**: der Skill ist der Verarbeitungskern und das Risiko; Backend orchestriert ihn, Frontend bedient die fertige API.

### I) Referenz-Dateien (Ist-Stand, CodeGraph-verifiziert)
- Queue/Worker/Routen-Vorbild: `backend/app/db/video_summary_queue.py`, `backend/app/engine/video_summary.py`, `backend/app/routes/video_summary.py`, `backend/app/schemas/video_summary.py`
- Lifespan-Wiring: `backend/app/main.py` (`_video_summary_loop`, `app.state.video_summary`, startup running→pending)
- Headless-Session: `backend/app/engine/manager.py` (`SessionManager.create`, `validate_project_path`)
- Upload/Scope: `backend/app/routes/files.py` (`POST /files/upload`, `GET /files/download`), `backend/app/engine/files.py`
- Native Micro-App: `backend/config/engines.yaml` (Eintrag `video_summary`), `nextjs_app/lib/microapps-registry.ts`, `nextjs_app/app/(cockpit)/apps/[key]/page.tsx`
- Modell-Quelle: `backend/app/routes/engines.py` (`GET /engines`, `models`/`default_model`)
- Config-Defaults: `backend/app/config.py` (`video_summary_*`-Block, `vault_root`, `upload_allowed_extensions`)

## Implementation Notes (Backend + Skill — /abc-backend, 2026-06-28)

**Branch:** `dev`. Backend + Verarbeitungs-Skill vollständig; Frontend (native Komponente + `engines.yaml`/Registry-Eintrag) ist der nächste Hand-off. **Volle Suite: 966 passed, keine Regression** (27 neue PROJ-53-Tests).

### Neue/geänderte Dateien (Backend)
- `backend/app/db/book_nuggets_queue.py` — SQLite-Repo (Vorbild `video_summary_queue.py`): Tabellen `book_nuggets_queue` (eine Zeile/Buch) + `book_nuggets_settings` (1-Zeile: Default-Modellmodus/-Modelle/-Seitenlimit). Off-thread via `asyncio.to_thread`, WAL, Spalten-Whitelist bei insert/update, `reset_running()`.
- `backend/app/engine/book_nuggets.py` — `BookNuggetsWorker` (sequenziell, **eine** Session zur Zeit, **Auto-Drain** bei Add — kein Cooldown/Zeitplan) + reine Helfer `validate_source`, `compute_book_hash_sync`, `estimate_cost`, `build_prompt`, `parse_result_paths`, `parse_phase` + `DuplicateError`.
- `backend/app/schemas/book_nuggets.py` — Pydantic v2 (QueueItem/WorkerState/Queue, QueueAdd Req/Result, Estimate Req/Result, DuplicateConflict, Settings Read/Patch, Library).
- `backend/app/routes/book_nuggets.py` — Router (API unten).
- `backend/app/config.py` — `book_nuggets_*`-Defaults (db_path, poll 5s, model `opus`, permission `bypassPermissions`, project_path=Vault, output_subdir `04 Resources/Buch_Nuggets`); **`epub` in `upload_allowed_extensions`** ergänzt (pdf/txt/docx waren schon drin; **mobi bewusst nicht**).
- `backend/app/main.py` — `bn_repo` gebaut, `app.state.book_nuggets` (Worker), `_book_nuggets_loop` als Lifespan-Task, `startup()` (Schema + running→pending), Router registriert, `bn_repo.close()` beim Shutdown.
- `backend/app/db/__init__.py` — Exporte. `backend/tests/conftest.py` — Test-Isolation (eigene DB in tmp, Poll-Intervall aus).
- `backend/tests/test_proj53_book_nuggets.py` — 27 Tests (Helper + Worker + Duplikat + Persistenz + API).

### Neuer Skill (Host-seitig, kein Repo)
- `/home/dev/.claude/skills/hal-book-nuggets/SKILL.md` — Orchestrator: 11-Block-Nugget inkl. recherchegestütztem Contra-Kapitel, STAGED-Stufenlogik (günstige Chunk-Extrakte via Sub-Agenten mit Modell-Override), seitenzitierte Zahlen, md+figures+PDF nach `04 Resources/Buch_Nuggets/<Autor>-<Titel>/`, Abschluss-Block `JUPITER_BOOK_RESULT`.
- `scripts/extract_book.py` — Buch → `text.md` (PDF seitengemappt via pdfplumber, Bilder via pypdf; epub/docx/txt via `pandoc --extract-media`). **Abbruch bei DRM/Scan ohne Textebene** (kein Halluzinieren). `mobi` abgewiesen.
- `scripts/check_embeds.py` — Embed-Konsistenz-Gate vor dem PDF-Bau.

### Worker-Verhalten (umgesetzt)
- **Sequenziell + Auto-Drain:** genau eine headless Session gleichzeitig; ein eingereihtes Buch wird ohne weiteren Klick verarbeitet; `run-now` bleibt (idempotent). **Kein Cooldown/Zeitplan** (Bücher blocken nicht).
- **Stufen-Logik (D7):** Session läuft auf dem **Konsolidierungs-Modell** (`model=model_consolidate`); der Prompt weist im STAGED-Modus an, Chunk-Extrakte über Sub-Agenten mit dem günstigen `model_extract` zu fahren. SINGLE kollabiert beide Modelle.
- **Kostenschätzung (D7):** `POST /estimate` best-effort aus Dateigröße (Upload); URL ohne Download → `null` (ehrlich). `cost_estimate` wird am Eintrag gespeichert.
- **Duplikat (D9):** Identität = SHA-256 (Upload) bzw. URL. Gleiche Identität pending/running/done → **409** mit `existing_id`/`existing_status`; `on_duplicate=overwrite|new_version` hebt auf (vault-seitige Versionierung erledigt der Skill).
- **Phasen-Anzeige:** Worker liest `JUPITER_BOOK_PHASE:`-Marker aus dem Transcript → `phase` am Eintrag (parsing/analysis/contra/pdf).
- **Persistenz:** Queue + Einstellungen in SQLite (überleben Neustart); `running`→`pending` beim Start.
- **Fehler/Retry:** Start-/Skill-Fehler → `error` + Ursache, Queue läuft weiter; `retry` setzt `error`→`pending` + Drain. `SessionLimitError` → bleibt `pending`.

### API-Vertrag (für Frontend)
```
GET    /book-nuggets/queue              → {items:[QueueItem], state:{status:idle|running, draining, current_id}}
POST   /book-nuggets/estimate           → {source_type, source_ref, model_mode, model_extract, model_consolidate, page_limit?} → {pages?, est_tokens?, est_cost?}
POST   /book-nuggets/queue              → {source_type:url|upload, source_ref, model_mode:staged|single, model_extract, model_consolidate, page_limit?, on_duplicate?} → {item, queue}; Duplikat → 409 {detail, existing_id, existing_status}; ungültig → 400
DELETE /book-nuggets/queue/{id}         → 204 (404 unbekannt)
POST   /book-nuggets/queue/{id}/retry   → QueueRead (404 unbekannt, 409 wenn nicht error)
POST   /book-nuggets/run-now            → QueueRead (Drain sofort, idempotent)
GET    /book-nuggets/library            → [{title, md_path, pdf_path?, mtime?}] (Vault-Scan)
GET    /book-nuggets/settings           → {default_model_mode, default_model_extract, default_model_consolidate, default_page_limit?}
PATCH  /book-nuggets/settings           → Teil-Update derselben Felder
```
QueueItem: `{id, owner, source_type, source_ref, title, author, model_mode, model_extract, model_consolidate, page_limit, cost_estimate, status, phase, result_dir, result_note_path, result_pdf_path, error_message, session_id, created_at, started_at, finished_at}`.
Modelle: `haiku|sonnet|opus`. Modi: `staged|single`.

### Offener Hand-off (Frontend, /abc-frontend)
- `engines.yaml`/`engines.example.yaml`-Eintrag `book_nuggets` (`kind: native`, `group: micro`, Label „Buch-Nuggets", Icon z. B. `book`/`book-open`).
- `nextjs_app/lib/microapps-registry.ts` (`book_nuggets → lazy(import …)`) + Komponente `components/microapps/book_nuggets/`: **Dropzone/Upload** (→ `POST /files/upload`, dann `source_type=upload` + Pfad) **ODER URL-Feld**, Modell-Steuerung (Umschalter staged/single + 1–2 Modell-Dropdowns), Kostenschätzung (`POST /estimate` vor dem Hinzufügen), Queue-Liste mit Polling (`GET /queue`, Phase-Anzeige), Bibliotheks-Tab (`GET /library`), Duplikat-Dialog (409 → overwrite/new_version), Einstellungs-Dialog.
- **Upload-Fluss:** Datei via bestehendes `/files/upload` ablegen → den zurückgegebenen Pfad als `source_ref` mit `source_type=upload` an `POST /book-nuggets/queue` schicken (kein zweiter Upload-Endpunkt).

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
