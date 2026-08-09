# PROJ-77: masterskill-creator — agenten-unabhängige Master-Skills in Hal + minimale Pointer-Stubs je CLI

## Status: In Review
**Created:** 2026-08-09
**Last Updated:** 2026-08-09

## Dependencies
- Requires: PROJ-50 (abc-Workflow für die Codex-Engine) — löst dessen Copy-Generator (`scripts/gen_codex_skills.py`) als Quelle der Wahrheit ab
- Requires: PROJ-2 (Vault-Anbindung) — Hal-Vault unter `/home/dev/tools/Hal` ist der Speicherort der Master-Skills

## Problem
Skills liegen heute doppelt vor: `~/.claude/skills/` (Original) und `~/.codex/skills/` (generierte Kopien aus PROJ-50).
Die Kopien sind bereits gedriftet — z. B. fehlt `abc-requirements/template.md` auf der Codex-Seite, und die
`SKILL.md` beider Seiten unterscheiden sich. OpenCode zieht per Symlink
(`~/.config/opencode/skills -> ~/.claude/skills`) die Claude-Skills direkt, hat also kein eigenes Verzeichnis.
Mit jedem weiteren CLI (z. B. Kimi) vervielfacht sich die Pflege.

## Ziel
Ein Skill `masterskill-creator`, der (a) neue Skills so anlegt, dass der **einzige inhaltliche Master** im
Hal-Vault liegt, und (b) bestehende Skills **einzeln auf Zuruf** in dieses Format überführt. Je Agent entsteht
nur ein **Pointer-Stub**, der auf den Master verweist. Neue CLIs werden über eine Registry-Datei ergänzt,
ohne den Skill zu editieren.

## Zielbild (Struktur)

```
/home/dev/tools/Hal/09_Skills/
  agents.yaml                     # Agenten-Registry
  <skill-name>/
    SKILL.md                      # Master, agenten-neutral
    template.md, scripts/, …      # Assets bleiben beim Master

~/.claude/skills/<skill-name>/SKILL.md    # Pointer-Stub (Claude-Frontmatter)
~/.codex/skills/<skill-name>/SKILL.md     # Pointer-Stub (Codex-Frontmatter + Übersetzungs-Hinweis)
~/.config/opencode/skills                 # Symlink auf ~/.claude/skills → kein eigener Stub
```

## User Stories
- Als Skill-Autor möchte ich einen neuen Skill **einmal** schreiben, damit er ohne Zusatzarbeit in Claude, Codex und OpenCode verfügbar ist.
- Als Skill-Autor möchte ich einen bestehenden Skill mit einem Kommando ins Master-Format überführen, damit ich nicht alle 55 Skills auf einmal anfassen muss.
- Als Nutzer eines weiteren CLI (z. B. Kimi) möchte ich einen Registry-Eintrag ergänzen und danach alle Master-Skills dort verfügbar haben, ohne Skill-Code zu ändern.
- Als Pfleger der Skills möchte ich Inhalte nur an **einer** Stelle ändern, damit Drift zwischen Agenten technisch unmöglich wird.
- Als Nutzer möchte ich vor einer Migration sehen, was verschoben, ersetzt und archiviert wird, damit ich nichts unbeabsichtigt verliere.

## Funktionsumfang

### Modus A — Neuer Skill (`masterskill-creator <name>` / „neuen Masterskill anlegen")
1. Skill-Inhalt agenten-neutral im Hal-Master anlegen (`09_Skills/<name>/SKILL.md` + Assets).
2. `agents.yaml` lesen; für jeden aktiven Agenten einen Pointer-Stub schreiben.
3. Agenten mit `shares_with:` (OpenCode → claude) werden übersprungen und im Report als „geteilt" ausgewiesen.

### Modus B — Migration bestehender Skill (`masterskill-creator migriere <name>`)
1. Quelle bestimmen (Standard: `~/.claude/skills/<name>/`).
2. Drift-Report: Unterschiede zwischen Claude-Original und vorhandener Codex-Kopie anzeigen; Nutzer entscheidet, welche Fassung Master wird.
3. Master nach `09_Skills/<name>/` kopieren, agentenspezifische Passagen (z. B. der PROJ-50-Codex-Hinweisblock, `GENERIERT von …`-Marker) aus dem Master entfernen.
4. Verifizieren (Master vorhanden, Assets vollständig, keine kaputten relativen Links).
5. Erst danach Originale durch Pointer-Stubs ersetzen; verdrängte Alt-Fassungen nach `/home/dev/tools/Hal/06 Archive/09_Skills/<name>/<datum>/` sichern statt löschen.

### Registry `agents.yaml`
Je Agent mindestens: `id`, `skills_dir`, `frontmatter_fields` (welche Felder der Stub trägt, z. B. Claude:
`name/description/argument-hint/user-invocable`; Codex: `name/description/metadata.short-description`),
`translation_note` (optionaler Textblock, z. B. Codex „kein AskUserQuestion-Tool → Klartext-Rückfrage"),
`enabled`, optional `shares_with`.

### Pointer-Stub
Klein (Richtwert ≤ 15 Zeilen): Frontmatter im Agent-Format + Anweisung, den Master unter absolutem Pfad zu
lesen und zu befolgen + optionaler `translation_note` des Agenten. Kein inhaltlicher Text aus dem Master.

## Acceptance Criteria
- [ ] `masterskill-creator` liegt selbst im neuen Format vor: Master in `09_Skills/masterskill-creator/`, Stubs in Claude- und Codex-Verzeichnis.
- [ ] Modus A erzeugt aus einer Skill-Beschreibung: genau **einen** Master in `09_Skills/<name>/SKILL.md` und je aktivem Agenten (ohne `shares_with`) genau einen Stub.
- [ ] Ein erzeugter Stub enthält den absoluten Master-Pfad, ist ≤ 15 Zeilen und enthält keinen kopierten Master-Inhalt (prüfbar: kein Satz > 10 Wörter aus dem Master).
- [ ] Der Claude-Stub wird von Claude Code als Skill erkannt (erscheint in der Skill-Liste mit korrekter `description`), der Codex-Stub von Codex.
- [ ] OpenCode wird korrekt als `shares_with: claude` erkannt: kein eigener Stub erzeugt, Symlink unverändert, Report weist „geteilt über Claude" aus.
- [ ] Modus B migriert einen genannten Skill (Testfall: `abc-requirements`, hat Asset `template.md`) vollständig: Master inkl. `template.md` in Hal, Claude- und Codex-Verzeichnis nur noch Stub, Alt-Fassungen im Archiv.
- [ ] Modus B zeigt vor dem Schreiben einen Report (was wird Master, was ersetzt, was archiviert) und wartet auf Freigabe.
- [ ] Modus B fasst ausschließlich den genannten Skill an; alle anderen Skill-Verzeichnisse bleiben byte-identisch.
- [ ] Nach Migration liefert der Skill inhaltlich dasselbe Ergebnis wie vorher (Nachweis: ein migrierter Skill wird in Claude **und** Codex ausgeführt und arbeitet den Master ab).
- [ ] Ein neuer Agent (Testfall: Kimi-Dummy mit eigenem `skills_dir`) wird allein durch einen `agents.yaml`-Eintrag unterstützt: erneuter Lauf erzeugt Stubs für alle bereits migrierten Skills, ohne dass der Skill-Text geändert wird.
- [ ] Alle Nutzer-Ausgaben (Reports, Rückfragen, Fehler) sind auf Deutsch.
- [ ] `scripts/gen_codex_skills.py` (PROJ-50) ist im Zielbild nicht mehr die Quelle der Wahrheit; sein Status (deaktiviert/entfernt/nur noch für Nicht-migrierte) ist dokumentiert.

## Edge Cases
- **Asset-Pfade:** Master enthält relative Verweise (`[template.md](template.md)`, `scripts/x.py`). Assets bleiben beim Master; relative Pfade müssen sich auf das Hal-Master-Verzeichnis beziehen. Migration prüft und meldet nicht auflösbare Links.
- **Gedriftete Codex-Kopie:** Claude- und Codex-Fassung unterscheiden sich (heute der Regelfall). Kein stilles Gewinnen — Diff zeigen, Nutzer wählt Master.
- **Skill existiert nur in Codex** (z. B. `clone-website`, `web-deploy-mockup`, `design-build-design`): Migration akzeptiert Codex als Quelle und erzeugt danach auch einen Claude-Stub.
- **Codex-System-Skills** (`~/.codex/skills/.system/`, mit Marker-Datei): niemals anfassen.
- **Symlink-Skills in Claude** (`code-review`, `codebase-design`, `claude-handoff` → `../../.agents/skills/…`): Migration verweigert oder verlangt ausdrückliche Bestätigung; Symlink-Ziel darf nicht überschrieben werden.
- **Name-Kollision:** `09_Skills/<name>/` existiert bereits → abbrechen mit Diff, kein stilles Überschreiben.
- **Agenten-Verzeichnis fehlt / `enabled: false`:** Agent überspringen, im Report vermerken, Lauf nicht abbrechen.
- **Hal ist ein Obsidian-Vault:** `09_Skills` liegt im Vault; Master-Dateien dürfen den Vault-Betrieb nicht stören (keine erzwungenen Frontmatter-Felder, die Obsidian-Ansichten kaputt machen). Pfad enthält keine Leerzeichen — der Archiv-Pfad `06 Archive` schon, also überall quoten.
- **Abbruch mitten in der Migration:** Reihenfolge Kopieren → Verifizieren → Ersetzen; bricht es vor dem Ersetzen ab, ist das Original unverändert.
- **Wiederholter Lauf (idempotent):** Zweiter Lauf auf einen bereits migrierten Skill schreibt Stubs neu, verändert den Master nicht und legt kein zweites Archiv an.
- **Master fehlt zur Laufzeit** (Vault nicht gemountet/verschoben): Stub führt zu totem Verweis. Stub muss in dem Fall einen klaren deutschen Fehlerhinweis samt erwartetem Pfad tragen.

## Technical Requirements
- Speicherort Master: `/home/dev/tools/Hal/09_Skills/<name>/`
- Registry: `/home/dev/tools/Hal/09_Skills/agents.yaml`
- Agenten initial: `claude` (`~/.claude/skills`), `codex` (`~/.codex/skills`), `opencode` (`shares_with: claude`)
- Keine Kopie des Master-Inhalts in Agent-Verzeichnisse — Drift ist konstruktiv ausgeschlossen
- Migration ist nicht destruktiv: verdrängte Fassungen ins Hal-Archiv
- Deutsche Nutzer-Ausgaben

## Non-Goals
- Kein Massen-Rollout aller ~55 Skills in einem Lauf (bewusst „einzeln auf Zuruf").
- Keine automatische Übersetzung von Skill-Inhalten in agentenspezifische Werkzeug-Aufrufe über den `translation_note`-Block hinaus.
- Keine Änderung an der OpenCode-Symlink-Konfiguration.
- Kein Sync von Hal auf andere Maschinen.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-09 · **Stack:** Markdown/YAML-Artefakte + ein Python-Helfer (conda `Dashboard`), kein Frontend/Backend/DB · **Branch:** dev

> Hinweis: Dieses Feature berührt **keinen** App-Code (kein FastAPI, kein Next.js, kein Postgres/MinIO).
> Es erzeugt und verschiebt Dateien in `~/.claude/skills`, `~/.codex/skills` und im Hal-Vault.
> Einzige Berührung mit Jupiter-Code: `scripts/gen_codex_skills.py` (PROJ-50) bekommt einen Guard.

### A) Struktur (was entsteht)

```
/home/dev/tools/Hal/09_Skills/
├── agents.yaml                        # Agenten-Registry (Quelle für Stub-Erzeugung)
├── masterskill-creator/
│   ├── SKILL.md                       # Master des Skills selbst (Ablauf, Rückfragen, Reports)
│   └── scripts/masterskill.py         # deterministischer Helfer (Stubs, Migration, Prüfung)
└── <skill-name>/
    ├── SKILL.md                       # Master eines migrierten/neuen Skills
    └── template.md · scripts/ · …     # Assets bleiben beim Master

~/.claude/skills/<skill-name>/SKILL.md   # Pointer-Stub
~/.codex/skills/<skill-name>/SKILL.md    # Pointer-Stub (+ Übersetzungs-Hinweis)
~/.config/opencode/skills                # unverändert: Symlink auf ~/.claude/skills
/home/dev/tools/Hal/06 Archive/09_Skills/<skill-name>/<datum>/   # verdrängte Alt-Fassungen
```

**Gestalt eines Stubs** (Richtwert; Frontmatter je nach Agent):

```
---
name: abc-qa
description: <aus dem Master übernommen — der Agent baut seine Skill-Liste daraus>
argument-hint: …            (nur Claude)
user-invocable: true        (nur Claude)
---
<!-- Pointer-Stub, erzeugt von masterskill-creator. Nicht editieren — Inhalt steht im Master. -->

Lies **/home/dev/tools/Hal/09_Skills/abc-qa/SKILL.md** und befolge sie vollständig.
Alle relativen Pfade darin beziehen sich auf **/home/dev/tools/Hal/09_Skills/abc-qa/**.
Master nicht lesbar? → Abbrechen und dem Nutzer genau diesen Pfad nennen.

<agentenspezifischer translation_note aus agents.yaml>
```

### B) Arbeitsteilung Skill (LLM) ↔ Helfer (deterministisch)

| Aufgabe | Wer |
|---|---|
| Skill-Inhalt agenten-neutral formulieren / Claude-Ismen aus dem Master entfernen | Skill (LLM) |
| Drift Claude ↔ Codex bewerten, Rückfrage „welche Fassung wird Master?" | Skill (LLM) |
| Stubs erzeugen, Registry lesen, Dateien verschieben/archivieren, verifizieren, Report | Helfer-Skript |

Grund für die Trennung: alles Wiederholbare bleibt reproduzierbar und idempotent (auch per Cron/CI aufrufbar); nur die inhaltlichen Urteile brauchen ein Modell.

### C) Kommando-Oberfläche (Helfer)

```
masterskill.py stubs <name> [--agents a,b]   → Stubs aus dem Master erzeugen/aktualisieren
masterskill.py migrate <name> --dry-run       → Report: Quelle, Drift, was verschoben/archiviert wird
masterskill.py migrate <name> --apply         → Migration ausführen (nach Freigabe)
masterskill.py check [<name>]                 → Prüfen: Master existiert, Stubs aktuell, Assets vollständig
masterskill.py agents                         → Registry anzeigen (inkl. übersprungener shares_with-Agenten)
```

Reihenfolge bei `--apply`: **kopieren → verifizieren → Alt-Fassung archivieren → Original durch Stub ersetzen.**
Bricht es vor dem letzten Schritt ab, ist der Ausgangszustand unverändert.

### D) Datenmodell (Registry, Klartext)

`agents.yaml` — je Agent:
- **id** — z. B. `claude`, `codex`, `opencode`, später `kimi`
- **skills_dir** — absolutes Verzeichnis, in das Stubs geschrieben werden
- **frontmatter** — welche Felder der Stub trägt und wie sie befüllt werden (Claude: `name`, `description`, `argument-hint`, `user-invocable`; Codex: `name`, `description`, `metadata.short-description` mit 80-Zeichen-Kürzung wie heute in PROJ-50)
- **translation_note** — optionaler Textblock, der an jeden Stub dieses Agenten angehängt wird (Codex: kein `AskUserQuestion`, keine Sub-Agenten, kein CodeGraph-MCP → Shell/`rg`)
- **shares_with** — verweist auf einen anderen Agenten, dessen Verzeichnis geteilt wird (OpenCode → claude); dann wird **kein** Stub geschrieben
- **enabled** — aus/an, ohne den Eintrag zu löschen

Ein weiteres CLI (Kimi) = ein Block in dieser Datei. Danach `masterskill.py stubs` je migriertem Skill — kein Skill-Text wird angefasst.

### E) Tech-Entscheidungen (Begründung)

1. **Pointer statt Kopie.** Der Inhalt existiert genau einmal, also kann er nicht auseinanderlaufen — genau das Problem, das PROJ-50 heute hat (Codex-`abc-requirements` unterscheidet sich vom Claude-Original und hat `template.md` gar nicht). Preis: der Agent liest pro Skill-Nutzung eine Datei mehr. Das ist gegenüber dem Skill-Body selbst vernachlässigbar.
2. **Die `description` wird bewusst dupliziert.** Alle drei CLIs bauen ihre Skill-Auswahlliste aus dem Frontmatter — ein Stub ohne eigene `description` wäre nie auffindbar. Diese eine Zeile ist *generiert*, nicht handgepflegt; `check` meldet, wenn sie vom Master abweicht.
3. **Helfer liegt beim Master in Hal, nicht in `jupiter/scripts/`.** Codex, OpenCode oder Kimi laufen auch außerhalb des Jupiter-Checkouts. Der gemeinsame Ort ist Hal — sonst hängt agentenübergreifende Infrastruktur an einem einzelnen Repo.
4. **OpenCode bekommt keinen eigenen Stub.** `~/.config/opencode/skills` ist ein Symlink auf `~/.claude/skills`; ein zweiter Stub-Satz wäre reine Doppelung. Die Registry macht das explizit statt implizit (`shares_with: claude`).
5. **PROJ-50-Generator bleibt — mit Guard.** `gen_codex_skills.py` erfasst per Glob alle `abc-*` und würde einen migrierten Claude-Stub in eine Codex-Kopie *eines Stubs* verwandeln. Er bekommt daher eine Abbruchbedingung: Quelle enthält die Pointer-Stub-Markierung → überspringen. So bleiben migrierte und noch nicht migrierte Skills nebeneinander funktionsfähig, solange die Migration einzeln läuft.
6. **Migration ist nicht destruktiv.** Verdrängte Fassungen gehen ins Hal-Archiv statt in den Papierkorb — bei einer gedrifteten Codex-Kopie ist nicht immer sofort klar, ob sie nur veraltet ist oder eine bewusste Anpassung enthält.
7. **Keine neuen Abhängigkeiten.** PyYAML ist im Env `Dashboard` bereits in Gebrauch (PROJ-50); der Rest ist Standardbibliothek.
8. **Assets wandern mit dem Master, nicht in die Stubs.** `template.md`, `scripts/`, `references/` gehören inhaltlich zum Skill; der Stub nennt nur das Master-Verzeichnis als Basis für relative Pfade.

### F) Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Hal wird verschoben/nicht gemountet → alle Stubs zeigen ins Leere | Master-Wurzel steht als **ein** Wert in `agents.yaml`; `check` erkennt tote Verweise; Stub-Text enthält den erwarteten Pfad als Fehlerhinweis |
| Master enthält weiterhin Claude-Ismen (`AskUserQuestion`, Explore-Agenten) → Codex läuft ins Leere | Migration räumt sie im Master auf; der agentenspezifische Rest kommt über `translation_note` in den Stub |
| Zwei CLIs bearbeiten denselben Master gleichzeitig | Nur ein Master, letzter Schreiber gewinnt — bewusst akzeptiert (Einzelnutzer-VPS); Hal-Archiv erlaubt Rückgriff |
| `09_Skills` liegt in einem Obsidian-Vault → Skill-Dateien tauchen als Notizen auf | Akzeptiert; bei Störung `09_Skills` in den Obsidian-Ausschlussfiltern eintragen |
| Agent lädt Skills gecacht (Codex braucht Neustart) | Report weist nach jedem Schreiblauf auf den nötigen Agent-Neustart hin (wie heute PROJ-50) |

### G) Abhängigkeiten
- Python 3.11 im conda-Env `Dashboard`, PyYAML (bereits vorhanden)
- Keine neuen Pakete, keine Dienste, kein Deploy (läuft rein lokal auf dem VPS)

## Implementation Notes (Backend/Helfer)
**Erstellt:** 2026-08-09

Umgesetzt exakt nach Tech Design, kein FastAPI/DB-Code (Feature berührt keinen App-Code):
- `/home/dev/tools/Hal/09_Skills/agents.yaml` — Registry mit `claude`, `codex`, `opencode` (`shares_with: claude`).
- `/home/dev/tools/Hal/09_Skills/masterskill-creator/SKILL.md` + `scripts/masterskill.py` — Helfer mit
  `stubs`, `migrate --dry-run/--apply`, `check`, `agents`.
- `masterskill-creator` selbst im neuen Format: Master in Hal, Stubs unter `~/.claude/skills/masterskill-creator/`
  und `~/.codex/skills/masterskill-creator/` erzeugt und verifiziert (`check` → OK).
- Modus-B-Testfall `abc-requirements` durchlaufen: `--dry-run` zeigte Drift (Codex-Kopie fehlte `template.md`
  und trug den PROJ-50-Präambel-Block) + Asset-Liste; `--apply --source claude` kopierte Master + `template.md`
  nach Hal, archivierte beide Alt-Fassungen nach `06 Archive/09_Skills/abc-requirements/2026-08-09/{.claude,.codex}`
  und ersetzte beide Originale durch Pointer-Stubs (11/13 Zeilen). Wiederholter `stubs`-Lauf ist idempotent
  (kein zweites Archiv, Master unverändert).
- `scripts/gen_codex_skills.py` (PROJ-50) bekam den Guard aus Tech-Design E.5: Quellen mit dem
  Pointer-Stub-Marker werden übersprungen (verifiziert: `abc-requirements` wird jetzt übersprungen,
  alle anderen `abc-*`-Skills unverändert generiert). PROJ-50 bleibt damit aktiv für alle noch nicht
  migrierten `abc-*`-Skills; sein Status ist "aktiv, aber je migriertem Skill selbst-deaktivierend".

**Offen für /abc-qa:**
- AC „neuer Agent (Kimi-Dummy) via Registry-Eintrag" noch nicht durchgespielt — Mechanik (`stubs` je
  migriertem Skill erneut aufrufen) ist vorhanden und in `check masterskill-creator`/`check abc-requirements`
  verifiziert, aber kein eigener Testlauf mit einem dritten Agenten-Block.
- Symlink-Guard (`code-review`, `codebase-design`, `claude-handoff`) ist im Code vorhanden, aber nicht an
  einem echten Symlink-Skill durchgetestet.
- Rest der ~55 Skills bleibt bewusst unmigriert (Non-Goal: kein Massen-Rollout).

## QA Test Results

**Tested:** 2026-08-09  
**Environment:** lokaler Python-Helfer im Conda-Environment `Dashboard`; kein FastAPI-, Frontend- oder DB-Anteil  
**Tester:** QA Engineer (AI)

### Acceptance Criteria Status

1. **PASS** — `masterskill-creator` liegt als Hal-Master und als Claude-/Codex-Pointer-Stub vor; `check masterskill-creator` meldet `OK`.
2. **PASS** — Modus A erzeugt isoliert genau einen Stub je aktivem, nicht geteiltem Agenten; der Master bleibt unverändert.
3. **PASS** — reale Stubs enthalten absolute Master-Pfade, keinen Master-Body und haben 11 Zeilen (Claude) bzw. 13 Zeilen (Codex).
4. **PASS** — Claude Code 2.1.222 und Codex CLI 0.145.0 erkennen `abc-requirements`; beide lieferten `MASTER_OK /home/dev/tools/Hal/09_Skills/abc-requirements/SKILL.md`.
5. **PASS** — OpenCode ist `shares_with: claude`; `/home/dev/.config/opencode/skills` blieb Symlink auf `/home/dev/.claude/skills`, es wird kein eigener Stub geschrieben.
6. **PASS** — `abc-requirements` liegt mit `template.md` im Master, beide Alt-Fassungen liegen im datierten Archiv, beide Agentenverzeichnisse enthalten nur Pointer-Stubs. Asset-Prüfsummen stimmen überein.
7. **PASS** — `migrate --dry-run` berichtet Quelle, Drift/Assets und schreibt vor `--apply` nichts.
8. **PASS** — isolierter Migrationstest lässt ein anderes Skill-Verzeichnis byte-identisch.
9. **PASS** — der migrierte Skill wird von Claude und Codex über den Pointer aufgelöst.
10. **PASS** — ein Kimi-Dummy wird allein per Registry-Eintrag unterstützt; erneuter Stub-Lauf verändert den Master nicht.
11. **FAIL** — argparse-Fehlertexte sind Englisch (`error: the following arguments are required`). Siehe BUG-9.
12. **PASS** — der PROJ-50-Generator überspringt Pointer-Stubs; der isolierte Guard-Test ist grün und der Mischbetrieb ist dokumentiert.

### Edge Cases Status

- **PASS:** Relative Asset-Links werden vor dem Archivieren geprüft; ein kaputter Link entfernt den unvollständigen Master und lässt die Quelle bestehen.
- **PASS:** Claude/Codex-Drift wird im Dry-run angezeigt.
- **PASS:** Ein nur in Codex vorhandener Skill kann migriert werden und erhält danach beide Stubs.
- **PASS:** Claude-Symlink-Skills werden ohne `--force-symlink` verweigert.
- **PASS:** Bestehender Master bricht standardmäßig ab; `stubs` ist idempotent und legt kein weiteres Archiv an.
- **FAIL:** Codex-System-Skills mit Marker werden nicht geschützt. Siehe BUG-2.
- **FAIL:** Fehlende Agenten-Verzeichnisse werden angelegt statt übersprungen. Siehe BUG-8.
- **FAIL:** Abbruch nach dem Archivieren, aber vor erfolgreicher Stub-Erzeugung, stellt den Ausgangszustand nicht wieder her. Siehe BUG-3.
- **PASS:** Ein fehlender Master ist im Stub mit Pfad und deutschem Abbruchhinweis beschrieben.

### Security Audit Results

- **FAIL:** Skill-Namen werden nicht validiert; `../` verlässt Master- und Agenten-Wurzeln. Siehe BUG-1.
- **FAIL:** `.codex/skills/.system` kann trotz Marker als normaler Skill migriert werden. Siehe BUG-2.
- **PASS:** Symlink-Quellen werden standardmäßig abgelehnt.
- **PASS:** Relative tote Links stoppen die Migration vor dem Archivieren.
- **N/A:** JWT/Auth, Tenant-Isolation/RLS, SQL-Injection, Rate-Limits, MinIO, XSS und Secrets im Browser — PROJ-77 besitzt keine HTTP-, UI-, DB- oder Objekt-Storage-Schnittstelle.

### Bugs Found

#### BUG-1: Skill-Name erlaubt Pfad-Traversal
- **Severity:** High
- **Reproduktion:** `cmd_stubs` mit `name="../escape"` und einem Master oberhalb von `09_Skills` ausführen.
- **Expected:** Ungültigen Namen auf `[a-z0-9-]+` begrenzen und mit deutschem Fehler abbrechen.
- **Actual:** Master und Stub werden über `../` außerhalb der verwalteten Skill-Wurzeln gelesen/geschrieben (`masterskill.py:104-130`).
- **Priority:** Fix before deployment.

#### BUG-2: Codex-System-Skills sind migrierbar
- **Severity:** High
- **Reproduktion:** Codex-only-Quelle `.codex/skills/.system` mit `.codex-system-skills.marker` per Dry-run prüfen.
- **Expected:** Unbedingte Verweigerung; System-Skills niemals anfassen.
- **Actual:** `.system` wird als normale Quelle samt Marker-Asset akzeptiert (`masterskill.py:153-195`). Mit `--apply` könnte das Systemverzeichnis archiviert und ersetzt werden.
- **Priority:** Fix before deployment.

#### BUG-3: Migration ist bei Stub-Fehler nicht atomar
- **Severity:** High
- **Reproduktion:** Stub-Erzeugung nach erfolgreichem Kopieren/Verifizieren fehlschlagen lassen.
- **Expected:** Claude- und Codex-Originale bleiben an ihren Ausgangspfaden.
- **Actual:** Beide Originale wurden bereits ins Archiv verschoben; an den Agentenpfaden fehlt der Skill (`masterskill.py:221-233`).
- **Priority:** Fix before deployment.

#### BUG-4: Stub-Frontmatter wird bei Doppelpunkt ungültig
- **Severity:** High
- **Reproduktion:** Stub mit Beschreibung `Test-Skill: Beschreibung mit Doppelpunkt` rendern und per `yaml.safe_load` lesen.
- **Expected:** Gültiges YAML mit unveränderter Beschreibung.
- **Actual:** Unquotiertes `description:` erzeugt `yaml.scanner.ScannerError` (`masterskill.py:76-89`).
- **Priority:** Fix before deployment.

#### BUG-5: PROJ-50-Generator erzeugt ungültige `short-description`
- **Severity:** High
- **Reproduktion:** `test_generator_short_description_nonempty_all_skills` ausführen.
- **Expected:** Alle generierten Frontmatter sind gültiges YAML.
- **Actual:** Eine gekürzte Beschreibung mit Doppelpunkt wird unquotiert ausgegeben; YAML-Parsing bricht ab (`gen_codex_skills.py:185-190`).
- **Priority:** Fix before deployment.

#### BUG-6: PROJ-50-Generator-Drift in zwei Skills
- **Severity:** High
- **Reproduktion:** `python scripts/gen_codex_skills.py --check`.
- **Expected:** Exit 0 ohne Drift.
- **Actual:** Drift für `abc-backoffice` und `abc-customer-journey`; bestehender PROJ-50-Test schlägt fehl.
- **Priority:** Fix before deployment.

#### BUG-7: `check` meldet manipulierten Stub fälschlich als OK
- **Severity:** Medium
- **Reproduktion:** Im Pointer-Stub den absoluten Master-Pfad auf `/nicht/vorhanden` ändern und `check` ausführen.
- **Expected:** Fehler und Exit 1.
- **Actual:** Marker und Beschreibung genügen; falscher Pfad und Stub-Inhalt werden nicht verglichen (`masterskill.py:237-266`).
- **Priority:** Fix before deployment.

#### BUG-8: Fehlendes Agenten-Verzeichnis wird unerwartet angelegt
- **Severity:** Medium
- **Reproduktion:** Aktivierten Registry-Agenten mit nicht vorhandenem `skills_dir` konfigurieren und `stubs` ausführen.
- **Expected:** Agent überspringen und im Report nennen.
- **Actual:** `mkdir(parents=True)` legt das gesamte Verzeichnis an (`masterskill.py:127-130`).
- **Priority:** Fix before deployment.

#### BUG-9: CLI-Validierungsfehler sind Englisch
- **Severity:** Low
- **Reproduktion:** `python masterskill.py stubs` ohne Namen ausführen.
- **Expected:** Alle Nutzer-Ausgaben auf Deutsch.
- **Actual:** argparse meldet `error: the following arguments are required: name`.
- **Priority:** Fix before deployment because it violates an acceptance criterion.

### Automated Test Results

- Gesamtsuite vor Ergänzung der PROJ-77-Tests: **1155 passed, 79 skipped, 2 failed**; beide Fehler in `test_proj50_codex_abc.py`.
- Neue PROJ-77-Suite: **8 passed, 7 failed**.
- Kombinierter Zieltest PROJ-50 + PROJ-77: **26 passed, 9 failed**.
- Neue permanente Tests: `backend/tests/test_proj77_masterskill_creator.py`.
- Flutter-/Browsertests: **N/A**, laut Tech Design kein Frontend.

### Summary

- **Acceptance Criteria:** 11/12 passed
- **Bugs Found:** 9 total (0 Critical, 6 High, 2 Medium, 1 Low)
- **Security:** Issues found (Pfad-Traversal, fehlender System-Skill-Schutz, nicht atomarer Abbruch)
- **Production Ready:** **NO**
- **Recommendation:** High-Bugs zuerst beheben; Status bleibt **In Review**, danach `/abc-qa` erneut ausführen.

### User Review / Priorisierung

**Reviewed:** 2026-08-09
**Entscheidung:** Zuerst BUG-1 bis BUG-3 beheben: Pfad-Traversal schließen, Codex-System-Skills schützen und Migration bei Fehlern atomar halten. Danach erneut `/abc-qa` ausführen.

### Backoffice-Fix (2026-08-09)

**Modus:** Produkt-Bug (Helfer-Skript, kein App-Code) · Ausgangspunkt: PROJ-77-QA-Report oben.

- **BUG-1 (Pfad-Traversal):** `validate_skill_name()` in `masterskill.py` lehnt Namen mit `..`-
  Segmenten/absoluten Pfaden ab; aufgerufen am Anfang von `cmd_stubs` und `cmd_migrate`.
- **BUG-2 (Codex-System-Skills migrierbar):** `cmd_migrate` bricht sofort ab, sobald `claude_dir`
  oder `codex_dir` die Marker-Datei `.codex-system-skills.marker` enthält — vor allen anderen
  Prüfungen, auch im `--dry-run`.
- **BUG-3 (Migration nicht atomar):** Stub-Erzeugung (Schritt 4) läuft in `try/except`; schlägt sie
  fehl, werden alle in Schritt 3 archivierten Verzeichnisse zurück an ihren Ursprungspfad
  verschoben, bevor der Fehler weitergereicht wird.
- **Reproduktion/Verifikation:** `backend/tests/test_proj77_masterskill_creator.py` —
  `test_codex_system_skills_are_never_migrated`, `test_skill_name_cannot_escape_managed_directories`,
  `test_stub_failure_keeps_originals_in_place` liefen vor dem Fix rot, danach grün
  (`11 passed, 4 failed` statt `8 passed, 7 failed`). Verbleibende 4 Fehler sind BUG-4/7/8/9,
  bewusst außerhalb dieses Fix-Scopes. `test_proj50_codex_abc.py` unverändert (2 vorbestehende
  Fehler = BUG-5/6, ebenfalls außerhalb des Scopes).
- **Knowledge:** `bug-geloest-jupiter-proj77-migrate-traversal-atomicity.md` im Hal-Vault.
- **Rest-Risiko:** BUG-4 (YAML-Doppelpunkt in Description), BUG-5/6 (PROJ-50-Generator-Drift),
  BUG-7 (`check` erkennt manipulierten Master-Pfad im Stub nicht), BUG-8 (fehlendes
  Agenten-Verzeichnis wird angelegt statt übersprungen), BUG-9 (englische argparse-Fehler) bleiben
  offen. Status bleibt **In Review** bis erneutes `/abc-qa`.

### Backoffice-Fix Runde 2 (2026-08-09) — BUG-4/5/6/7/9

- **BUG-4 (YAML-Doppelpunkt im Stub bricht):** `masterskill.py` bekam `yaml_scalar()` — jeder
  Frontmatter-Wert (`name`, `description`, `short-description`, `argument-hint`) wird über
  `yaml.safe_dump` korrekt gequotet statt roh interpoliert.
- **BUG-5 (gleicher Fehler im PROJ-50-Generator):** `scripts/gen_codex_skills.py` –
  `transform_frontmatter()` quotet `short-description` jetzt genauso über `yaml.safe_dump`
  statt rohem String-Concat.
- **BUG-6 (PROJ-50-Generator-Drift):** `python scripts/gen_codex_skills.py` (Schreibmodus)
  ausgeführt — `abc-backoffice` und `abc-customer-journey` neu generiert, `--check` danach grün
  (`OK: alle 17 Codex-Skills aktuell.`, `abc-requirements` bewusst übersprungen als migrierter
  Pointer-Stub).
- **BUG-7 (`check` übersieht manipulierten Master-Pfad):** `cmd_check` vergleicht jetzt zusätzlich,
  ob der erwartete Master-Verweis (`<master_dir>/SKILL.md`) im Stub-Text vorkommt, nicht nur die
  Description.
- **BUG-9 (englische CLI-Fehler):** `GermanArgumentParser` (Subklasse von `argparse.ArgumentParser`)
  übersetzt die gängigen argparse-Fehlermeldungen (u. a. „the following arguments are required")
  ins Deutsche; gilt automatisch für alle Subparser.
- **Verifikation:** `backend/tests/test_proj77_masterskill_creator.py` + `test_proj50_codex_abc.py`
  zusammen: **34 passed, 1 failed** (nur noch der BUG-8-Test, siehe unten). Vorher (nach Runde 1):
  11+2 von 19 rot.
- **Knowledge:** Ergänzung in `bug-geloest-jupiter-proj77-migrate-traversal-atomicity.md`
  (Datei-Historie zeigt beide Runden; Erkenntnis-Abschnitt um BUG-4/5/6/7/9 erweitert — siehe Vault).

### Backoffice-Fix Runde 3 (2026-08-09) — BUG-8 (Produktentscheidung: Option A)

BUG-8 war kein Implementierungsfehler, sondern ein Zielkonflikt: „neuer Agent (Kimi), `skills_dir`
existiert noch nicht → anlegen" (AC10) und „Agent offline, `skills_dir` existiert nicht →
überspringen" (BUG-8) sind ohne zusätzliches Signal in der Registry dieselbe Vorbedingung. Nutzer
hat sich für **Option A** entschieden: explizites `bootstrap`-Feld je Agent in `agents.yaml`.

- **`bootstrap: false`** (etablierte Agenten, `claude` + `codex` in der realen Registry): fehlt
  `skills_dir`, gilt der Agent als offline → `cmd_stubs` überspringt ihn und vermerkt das im Report,
  statt einen leeren Verzeichnisbaum anzulegen.
- **`bootstrap: true`/Feld weglassen** (Default — neuer Agent, z. B. Kimi): fehlt `skills_dir` noch,
  wird es beim ersten `stubs`-Lauf angelegt (`mkdir(parents=True)`), wie bisher.
- Umsetzung: `cmd_stubs` in `masterskill.py` prüft jetzt `not agent_root.is_dir() and not
  agent.get("bootstrap", True)` vor dem `mkdir`. `agents.yaml` trägt `bootstrap: false` bei
  `claude`/`codex`. `SKILL.md` („Neuen Agenten anschließen") dokumentiert die Regel.
- **Test-Anpassung:** `test_missing_agent_directory_is_reported_and_skipped` erwartet jetzt
  `bootstrap: false` beim offline-Agenten (semantisch korrekt statt implizit). Neuer Test
  `test_new_agent_without_bootstrap_flag_still_creates_directory` deckt den Default-Fall
  (Kimi-artiger Neuzugang ohne explizites `bootstrap`) separat ab.
- **Verifikation:** `test_proj77_masterskill_creator.py` + `test_proj50_codex_abc.py` zusammen:
  **36 passed, 0 failed**. `masterskill.py check` gegen die echte Registry weiterhin `OK`
  (claude/codex-Verzeichnisse existieren real, `bootstrap: false` ändert dort nichts).
- **Knowledge:** Vault-Notiz um die Auflösung ergänzt (Option A, kein offener Konflikt mehr).

### Re-QA nach Backoffice-Fixes (2026-08-09)

Die Fix-Berichte oben wurden unabhängig erneut geprüft. Der dort genannte Stand „36 passed,
0 failed" deckte zwei reale Rollback-Abbrucharten sowie zwei `check`-Pflichten nicht ab.

#### Verifiziert behoben

- **BUG-1:** `../`-Pfad-Traversal wird vor jedem Schreibzugriff abgelehnt.
- **BUG-2:** `.codex-system-skills.marker` stoppt auch den Dry-run vor einer Migration.
- **BUG-4/5:** Stub- und Generator-Frontmatter bleiben bei Beschreibungen mit Doppelpunkt gültiges YAML.
- **BUG-6:** `gen_codex_skills.py --check` ist grün; migriertes `abc-requirements` wird übersprungen.
- **BUG-7 (ursprünglicher Fall):** `check` erkennt einen manipulierten Master-Pfad im Stub.
- **AC10/BUG-8-Schreibpfad:** `bootstrap: false` überspringt einen offline Agenten; Default/`true`
  legt das Verzeichnis eines neuen Agenten weiterhin an.

#### Weiter offene Bugs

##### BUG-3: Rollback ist weiterhin nicht atomar
- **Severity:** High
- **Fall A:** `cmd_stubs` kann nach dem Archivieren `SystemExit` auslösen, z. B. wenn das kopierte
  Master-Frontmatter keine `description` hat. `except Exception` fängt `SystemExit` nicht; das
  Original bleibt ausschließlich im Archiv und fehlt am Agentenpfad.
- **Fall B:** Wird der erste Stub geschrieben und der zweite schlägt fehl, existiert der
  Agenten-Zielpfad bereits. `shutil.move(Archiv, Zielpfad)` verschachtelt dann das Original unter
  dem neuen Stub-Verzeichnis statt den Ausgangszustand wiederherzustellen.
- **Tests:** `test_stub_system_exit_keeps_original_in_place`,
  `test_partial_stub_write_rolls_back_cleanly`.
- **Priority:** Fix before deployment.

##### BUG-8: `check` berücksichtigt offline Agenten nicht
- **Severity:** Medium
- **Reproduktion:** Aktivierten Agenten mit `bootstrap: false` und fehlendem `skills_dir`
  konfigurieren; `cmd_stubs` überspringt ihn korrekt, `cmd_check` meldet dennoch `FEHLT Stub`.
- **Test:** `test_check_skips_offline_non_bootstrap_agent`.

##### BUG-9: Fehlerausgabe ist nur teilweise Deutsch
- **Severity:** Low
- **Reproduktion:** `python masterskill.py stubs` ohne Namen.
- **Actual:** Der Fehlertext ist Deutsch, die vorangestellte Zeile beginnt weiterhin mit
  `usage:` statt einer deutschen Ausgabe.
- **Test:** `test_cli_errors_are_in_german`.

##### BUG-10: `check` prüft Master-Assets nicht
- **Severity:** Medium
- **Reproduktion:** Nach der Stub-Erzeugung ein im Master relativ verlinktes Asset löschen und
  `check` ausführen.
- **Expected:** Fehler und Exit 1.
- **Actual:** `check` meldet `OK`, obwohl der Master einen toten relativen Link enthält.
- **Test:** `test_check_detects_missing_master_asset`.

#### Re-QA-Teststand

- Vollständige Suite vor Ergänzung der neuen Negativtests: **1173 passed, 79 skipped, 0 failed**.
- Erweiterte PROJ-77-Suite: **15 passed, 5 failed**.
- Kombiniert PROJ-50 + PROJ-77: **35 passed, 5 failed**.
- **Acceptance Criteria:** 11/12 passed (AC11 weiterhin nicht vollständig erfüllt).
- **Offene Bugs:** 4 (0 Critical, 1 High, 2 Medium, 1 Low).
- **Security:** Pfad-Traversal und System-Skill-Schutz bestanden; atomarer Daten-/Rollback-Schutz
  weiterhin fehlgeschlagen.
- **Production Ready:** **NO** — Status bleibt **In Review**.

#### User Review / Priorisierung der Re-QA

**Reviewed:** 2026-08-09
**Entscheidung:** Zuerst BUG-3 vollständig beheben: Rollback muss sowohl `SystemExit` als auch
teilweise erzeugte Stub-Verzeichnisse abfangen und die Originale exakt an ihre Ausgangspfade
zurückbringen. Danach erneut `/abc-qa` ausführen.

## Deployment
_To be added by /abc-deploy_
