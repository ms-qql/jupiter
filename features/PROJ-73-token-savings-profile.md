# PROJ-73: Token Savings — globales, engine-übergreifendes Optimierungsprofil

## Status: In Review
**Created:** 2026-07-14
**Last Updated:** 2026-07-14

## Dependencies
- Requires: PROJ-1, PROJ-48, PROJ-57 — Claude, Codex und OpenCode als Ziel-Engines.
- Requires: PROJ-9, PROJ-51 — Session-Ausnahme im Smart Launcher und globaler Settings-Schalter.
- Requires: PROJ-52, PROJ-56 — getrennte Verbrauchsmessung und reproduzierbarer Resume-Snapshot.
- Related: PROJ-6 (Knappheits-Konstitution), PROJ-19 (Effizienz-Ausbau), PROJ-50 (engine-übergreifende Skills).

## Kontext / Problem
Jupiter soll Token-Sparmaßnahmen nicht pro Agent manuell und uneinheitlich konfigurieren. Ein globaler Schalter in den Einstellungen soll für neue Claude-, Codex- und OpenCode-Sessions ein kontrolliertes Optimierungsprofil aktivieren. Im Neue-Session-Dialog kann der globale Standard pro Session überschrieben werden.

Das Ziel ist weniger Input- und Output-Kontext bei mindestens gleichwertigen Arbeitsergebnissen. Einsparungen sind workload-, engine- und toolabhängig. Jupiter verspricht deshalb **keine pauschale Prozentzahl**, sondern misst tatsächliche Nutzung und erlaubt einen sicheren Vergleich mit deaktiviertem Profil.

## Verifikation der vorliegenden Evaluation (Stand 2026-07-14)

### Was belastbar ist
- **RTK** filtert Ausgaben verbreiteter Shell-/Dev-Befehle lokal. Es unterstützt Claude per Hook, OpenCode per Plugin und Codex per Instruktionsdatei; Codex hat derzeit keine gleichwertige native Pre-Tool-Hook-Integration. Die veröffentlichten 60–90 % beziehen sich auf gefilterte Tool-Ausgaben, nicht auf den gesamten Sessionverbrauch.
- **Caveman** ist primär eine Kürze-/Output-Policy. Der eigene Benchmark berichtet im Mittel 65 % weniger sichtbare Output-Tokens über zehn Prompts; Reasoning-/Thinking-Tokens bleiben unberührt. Claude, Codex und OpenCode werden unterstützt.
- **CodeGraph** stellt lokale, vorindexierte Code-Navigation per MCP für die drei Jupiter-Engines bereit. Auf dem Jupiter-Host ist es bereits installiert und das Projekt besitzt einen Index (`.codegraph/codegraph.db`). Der aktuelle Diagnosebefund zeigt jedoch ein Discovery-Problem: Das Binary liegt unter der NVM-Installation (`~/.nvm/versions/node/v24.17.0/bin/codegraph`), ist im PATH des aufrufenden Jupiter-Prozesses aber nicht auflösbar. „Installiert“, „Binary auffindbar“, „MCP konfiguriert“ und „Projekt indexiert“ müssen daher getrennte Health-Zustände sein.
- **Context Mode** hält große Tool-Ausgaben in einer Sandbox und liefert selektierte Resultate zurück. Hook-Tiefe und Durchsetzung unterscheiden sich je Engine.
- **Headroom** bietet Proxy-, SDK- und MCP-Varianten und reproduzierbare Evals. Die Proxy-Variante zielt auf API-Verkehr; subscription-authentifizierte CLI-Sessions müssen je Engine praktisch verifiziert werden. AST-Codekompression ist laut Changelog wegen ungültiger Syntax in realen Dateien standardmäßig deaktiviert.
- Die Studie *Brevity Constraints Reverse Performance Hierarchies in Language Models* berichtet +26 Prozentpunkte nur für eine untersuchte Teilmenge und bestimmte Benchmarks. Sie belegt keine generelle Qualitätssteigerung von Coding-Sessions durch Caveman.

### Was nicht übernommen wird
- **„Stacked = 78–95 % ohne Qualitätsverlust“** ist keine belastbare, unabhängige Ende-zu-Ende-Messung. Tool-Prozente dürfen wegen überlappender Wirkbereiche nicht addiert oder multipliziert werden.
- GitHub-Stars belegen Popularität, nicht Wirksamkeit oder Produktionsreife. `tokless` ist ein junger Installer/Updater und kein eigener Kompressionsmechanismus.
- Direkte Remote-One-Liner (`curl|bash`, `irm|iex`) werden nicht aus der Jupiter-UI ausgeführt.

## Bewertete Optionen

| Option | Vorteile | Nachteile | Entscheidung |
|---|---|---|---|
| `tokless` als Komplettintegration | Schneller Erstaufbau; bündelt Projekte | Mutiert globale Agent-Konfigurationen; fremder Release-/Rollback-Zyklus; Engines unterschiedlich tief integriert | Nicht als Runtime-Abhängigkeit; höchstens dokumentierter Bootstrap außerhalb Jupiters |
| Einzeltools direkt installieren | Transparente Versionen; gezieltes Update/Rollback | Mehr Integrationsarbeit | Basis der empfohlenen Lösung |
| Alle Tools sofort stapeln | Potenziell hohe Einsparung bei outputlastigen Sessions | Überlappende Policies, MCP-Overhead, schwer diagnostizierbar, Qualitätseffekt unklar | Für MVP verworfen |
| Jupiter-eigenes Profil über Adapter | Einheitliches UI; engine-spezifisch; Health, Audit, Messung und Fail-open | Jupiter pflegt Matrix und Adapter | **Empfohlen** |

## Empfohlener Produktumfang
Jupiter verwaltet ein versioniertes Profil `balanced-v1` und löst es beim Session-Start in konkrete Adapter auf:

1. **Früher Skill-Pilot, alle Engines:** Caveman für komprimierte Kommunikation und Ponytail für YAGNI-/Minimal-Code-Entscheidungen. Beide werden als getrennte Verhaltensmodule installiert, aber durch Jupiters Resolver nur dort aktiviert, wo keine gleichwertige Jupiter-Regel greift.
2. **Konfliktfreie Baseline:** Die bestehende Knappheits-Konstitution bleibt Jupiters Quelle der Wahrheit. Bei aktivem Caveman ersetzt Caveman nur den überlappenden Kürze-Abschnitt; Governance-Regeln wie Autonomie, Rückfragen und Decision Cards bleiben aus der Jupiter-Konstitution erhalten. Ponytail ergänzt ausschließlich Code-Scope/YAGNI und darf keine Permission-, Architektur- oder Workflow-Regeln ersetzen.
3. **Code-Navigation, früh:** Bestehendes CodeGraph zuverlässig discoverable machen und nur für erkannte Codeprojekte bereitstellen. Dies ist zunächst eine Reparatur der Auflösung, keine Neuinstallation.
4. **Tool-Output:** RTK, wenn die Integration für die gewählte Engine installiert und gesund ist. Codex' schwächere instruktionbasierte Abdeckung wird sichtbar ausgewiesen.
5. **Experimentell und standardmäßig aus:** Context Mode und Headroom; erst nach engine-spezifischem Jupiter-Pilot.

### Konfliktmatrix der frühen Skills

| Anliegen | Jupiter heute | Caveman | Ponytail | Auflösungsregel |
|---|---|---|---|---|
| Kurze Antworten, keine Vorreden/Wiederholungen | PROJ-6 globale Knappheits-Konstitution | Kernfunktion | Nebenwirkung | Bei Caveman aktiv: überlappende PROJ-6-Kürzeregeln einmalig durch Caveman repräsentieren, nicht doppelt injizieren |
| Nur bei echter Mehrdeutigkeit fragen | PROJ-6 + Decision Cards | Kann Rückfragen weiter verkürzen | Kann Scope-Fragen auslösen | Jupiter-Regel hat Vorrang; Skill darf notwendige Freigaben/Rückfragen nicht unterdrücken |
| Minimaler Code/YAGNI, kein Over-Engineering | Teilweise Rollen-/Aufgabenprompts, keine zentrale dedizierte Policy | Nicht Kernzweck | Kernfunktion | Ponytail darf ergänzen, sofern keine aktive Rolle/Skill-Spec absichtlich umfassendere Lösung verlangt |
| Architektur-/Requirements-Vollständigkeit | abc-Skills und Feature-Specs | Kürzt nur Darstellung | Könnte Scope zu aggressiv reduzieren | abc-Akzeptanzkriterien und Nutzerauftrag haben Vorrang; „minimal“ bedeutet kleinste vollständige Lösung |
| Permissions, Trust, Watchdog, Decision Cards | PROJ-4/10/16 | Kein Eigentümer | Kein Eigentümer | Nie durch Fremdskill überschreibbar |

## Scope-Entscheidungen (mit Nutzer abgestimmt)
- **Global plus Ausnahmen:** `Token Savings` ist der globale Standard. Der Session-Start bietet `Standard verwenden / Ein / Aus`.
- **Snapshot beim Start:** Zustand, Profilversion und Adapter werden an der Session gespeichert. Laufende Sessions ändern sich beim Umschalten nicht.
- **Resume bleibt reproduzierbar:** Eine fortgesetzte Session behält ihren Snapshot. „Als neue Session fortsetzen“ verwendet den aktuellen globalen Standard.
- **Fail-open:** Fehlt ein optionales Tool oder fällt es aus, arbeitet die Engine ohne diesen Adapter weiter; der Ausfall wird sichtbar protokolliert.
- **Keine Installation durch den Schalter:** Aktiviert werden nur installierte, geprüfte Adapter. Installation/Updates sind getrennte Admin-Aktionen außerhalb des MVP.
- **Skills früh, aber konfliktfrei:** Caveman und Ponytail werden vor RTK/Headroom pilotiert. Aktivierung erfolgt über einen komponierten effektiven Prompt mit Provenienz und Deduplizierung, nicht durch unkontrolliertes Aneinanderhängen kompletter Skilltexte.
- **Scope:** Erfasst werden alle von Jupiter gestarteten Claude-/Codex-/OpenCode-Sessions unabhängig vom Modellprovider, nicht außerhalb Jupiters gestartete Sessions.

## User Stories
- Als Solo-Entwickler möchte ich Token Savings global umschalten, damit neue Sessions konsistent starten.
- Als Nutzer möchte ich den Standard pro Session überschreiben, damit qualitätskritische oder diagnostische Läufe unverändert arbeiten können.
- Als Nutzer möchte ich vor dem Start erkennen, welche Komponenten für die gewählte Engine tatsächlich wirksam sind.
- Als Nutzer möchte ich Einsparung, Zusatzlatenz und Fehler je Adapter sehen statt Marketing-Prozentwerte.
- Als Nutzer möchte ich, dass eine fehlende Optimierung niemals eine Session blockiert oder Resume verändert.
- Als Administrator möchte ich Versionen und Health-Status sehen, um Regressionen kontrolliert behandeln zu können.
- Als Nutzer möchte ich Caveman und Ponytail früh verwenden, ohne doppelte Kürzeregeln oder ein Unterlaufen von Jupiter-Workflows und Akzeptanzkriterien.

## Acceptance Criteria

### A — Einstellungen
- [ ] Die Settings-Seite enthält „Token Savings“ mit globalem Ein/Aus-Schalter; Default nach Deployment ist **Aus**.
- [ ] Die Erklärung lautet sinngemäß: „Gilt als Standard für neue Sessions. Laufende Sessions bleiben unverändert.“
- [ ] Pro Adapter werden `installiert/nicht installiert`, Version, Health, unterstützte Engines, Wirkbereich und Stabilität (`stabil`, `Pilot`, `experimentell`) gezeigt.
- [ ] Der Wert bleibt nach Browser-/Backend-Neustart erhalten.
- [ ] Die UI behauptet keine garantierte Einsparquote oder Qualitätsverbesserung.

### B — Session-Start und Persistenz
- [ ] Der Neue-Session-Dialog bietet `Standard verwenden`, `Token Savings ein` und `Token Savings aus`; Default ist `Standard verwenden`.
- [ ] Vor dem Start zeigt er die für die gewählte Engine aufgelösten Adapter.
- [ ] `savings_enabled`, `savings_source`, `savings_profile_version` und Adapterliste werden unveränderlich an der Session persistiert.
- [ ] Folge-Turns, Backend-Neustart, Reanimierung und Resume verwenden denselben Snapshot.
- [ ] Alt-Sessions ohne Metadaten verhalten sich wie bisher (`Aus`) und bleiben resumefähig.

### C — Engine-Abdeckung
- [ ] Claude, Codex und OpenCode starten mit aktivem und deaktiviertem Profil.
- [ ] Engine-Unterschiede werden korrekt ausgewiesen; RTK für Codex gilt ohne nativen Hook nicht als Vollabdeckung.
- [ ] Keine Komponente überschreibt Permission-, Trust-, Watchdog- oder Transportregeln.
- [ ] Zugangsdaten und vollständige Prompts/Tool-Ausgaben werden weder in Health-Checks noch Savings-Telemetrie gespeichert.
- [ ] Caveman und Ponytail werden für jede Ziel-Engine über deren unterstützten Skill-/Instruktionsmechanismus eingebunden; die UI zeigt je Engine `nativ`, `Instruktions-Fallback` oder `nicht verfügbar`.
- [ ] Der Resolver erzeugt einen nachvollziehbaren effektiven Prompt mit den Quellen `Jupiter-Konstitution`, `Caveman`, `Ponytail` und dokumentiert, welche überlappenden Regeln dedupliziert wurden.
- [ ] PROJ-6-, abc-, Permission-, Trust-, Watchdog- und Decision-Card-Regeln haben bei Konflikten Vorrang vor Caveman und Ponytail.

### D — CodeGraph Discovery und Health
- [ ] Health unterscheidet mindestens: `binary_found`, `binary_version`, `mcp_configured`, `mcp_reachable`, `project_index_present` und `index_freshness`.
- [ ] Jupiter prüft zuerst einen explizit konfigurierten absoluten Binary-Pfad und danach einen kontrolliert aufgebauten Service-PATH; es verlässt sich nicht auf die interaktive NVM-Shell des Benutzers.
- [ ] Der bekannte Zustand „Index vorhanden, Binary außerhalb des Service-PATH“ wird als `installiert, Konfiguration nötig` angezeigt und nicht als `nicht installiert`.
- [ ] Der Health-Check führt keine Neuinstallation und keine automatische Änderung von Shell-Profilen aus.
- [ ] Fehlt CodeGraph zur Laufzeit, startet die Session ohne CodeGraph und erhält eine sichtbare Degraded-Meldung; vorhandene `.codegraph`-Daten werden nicht verändert.

### E — Robustheit und Sicherheit
- [ ] Fehlende, defekte oder langsame Tools führen nach begrenztem Timeout zu `degraded` und direktem Engine-Fallback, nicht zu einem Hänger.
- [ ] Adapter können serverseitig unabhängig deaktiviert werden, ohne das globale Nutzer-Setting zu verlieren.
- [ ] Umschalten führt keine Installations- oder Updatebefehle aus.
- [ ] Spätere Installer brauchen Vorschau, Backup, atomare Änderung und Rollback; fremde Konfiguration wird nie blind überschrieben.
- [ ] RTK-Telemetrie ist bei einer Jupiter-verwalteten Installation standardmäßig deaktiviert.
- [ ] Security-Warnungen, Fehler, Diffs, Pfade, Befehle und strukturierte Protokolle dürfen nicht semantisch verfälscht werden; riskante Transformatoren bleiben aus.

### F — Messung und Qualitäts-Gate
- [ ] Native Input-/Output-/Cache-/Reasoning-Tokens werden unverändert erfasst, soweit die Engine sie liefert.
- [ ] Adapter-Schätzwerte erscheinen getrennt als `estimated_tokens_avoided` und werden nie mit Providerwerten vermischt.
- [ ] Ohne belastbare Messung zeigt Jupiter `nicht messbar` statt `0 gespart`.
- [ ] Pilotvergleiche decken je Engine Code-Suche, Debugging, Tests, Review und freien Chat mit Savings an/aus ab.
- [ ] `Pilot → stabil` erfordert keine kritische Ergebnisregression, keine Sicherheitsverfälschung und keine relevante Hängerzunahme im vereinbarten Testsatz.
- [ ] Das Dashboard zeigt Einsparung, Zusatzlatenz, Fallbacks und Stichprobengröße; kleine Samples sind gekennzeichnet.

## Edge Cases
- Global `Ein`, aber kein Adapter installiert: Session startet unverändert und zeigt `eingeschränkt (0 Adapter verfügbar)`.
- Override `Ein` bei Teilabdeckung: verfügbare Adapter laufen, fehlende werden als `nicht verfügbar` protokolliert.
- Globaler Wechsel während einer Session: Session und Resume-Snapshot bleiben unverändert.
- Adapterversion ändert sich zwischen Turns: gewünschte Version wird geprüft; bei Nichtverfügbarkeit Fail-open plus Warnung, kein stiller Wechsel.
- RTK filtert unbekannten/fehlgeschlagenen Befehl: vollständige Fehlerausgabe bleibt über Raw-/Tee-Pfad erreichbar.
- MCP-/Kompressionsserver stirbt oder überschreitet Timeout: direkter Fallback; Watchdog wertet dies nicht als Agenten-Hänger.
- Nicht-Codeprojekt: CodeGraph wird nicht geladen und erzeugt keinen unnötigen Tool-Schema-Overhead.
- Zwei Kürze-Policies wären aktiv: Resolver dedupliziert; Jupiter-Konstitution und Caveman konkurrieren nicht.
- Ponytail empfiehlt weniger Umfang als die Feature-Spec verlangt: Akzeptanzkriterien und expliziter Nutzerauftrag gewinnen; Ponytail reduziert nur unnötige Implementierung außerhalb dieses Scopes.
- CodeGraph-Index existiert, Binary fehlt im PATH: absolut konfigurierten Pfad prüfen, Status `Konfiguration nötig`, danach Fail-open.
- Micro-Apps, Hintergrundjobs und Sub-Sessions verwenden globalen Wert, sofern ihr interner Startvertrag keinen expliziten Override setzt.

## Non-Goals
- Keine Kontrolle außerhalb Jupiters gestarteter Sessions.
- Keine Garantie einer festen Prozentersparnis oder generellen Qualitätssteigerung.
- Keine automatische Tool-Installation oder ungeprüfte Remote-Installationsskripte im MVP.
- Keine verlustbehaftete Kompression sicherheitskritischer Daten im stabilen Profil.
- Kein Live-Umschalten laufender Sessions.

## Umsetzungsplan für Folgephasen
1. **Architektur/Spike:** gemeinsamer `SavingsProfile`- und Prompt-Composition-Vertrag, Konfliktprioritäten, Session-Snapshot und Capability-Matrix.
2. **Früher Pilot A:** Caveman und Ponytail installieren/einbinden; Golden-Prompt-Tests beweisen Deduplizierung und Vorrang der Jupiter-Regeln.
3. **Früher Pilot B:** CodeGraph-Pfad-/MCP-Discovery reparieren, vorhandenen Index verwenden und Health-Zustände sichtbar machen.
4. **MVP-UI:** Settings-Schalter, Session-Override, Persistenz, Resolver und Health-API.
5. **Pilot RTK:** Claude/OpenCode sowie instruktionbasiert Codex; Jupiter-A/B-Metriken sammeln.
6. **Experiment-Lane:** Context Mode und Headroom einzeln, nicht gestapelt, je Engine evaluieren.
7. **Stabilisierung:** nur Module mit Qualitäts-/Sicherheits-Gate in `balanced-v1`; Versionen pinnen und Rollback dokumentieren.

## Research-Quellen
- [RTK](https://github.com/rtk-ai/rtk) · [Caveman](https://github.com/JuliusBrussee/caveman) · [Headroom](https://github.com/chopratejas/headroom)
- [Context Mode](https://github.com/mksglu/context-mode) · [CodeGraph](https://github.com/colbymchenry/codegraph) · [tokless](https://github.com/HoangP8/tokless)
- [Brevity Constraints, arXiv:2604.00025](https://arxiv.org/abs/2604.00025)

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-14 · **Stack:** Next.js/React + FastAPI Engine-Layer + SQLite Session-Index + dateibasierte Settings · **Branch:** main

### Überblick / Kernaussage
PROJ-73 wird als **Policy- und Kompositionsschicht vor dem bestehenden Engine-Start** gebaut. Der globale Schalter entscheidet nicht direkt über einzelne Fremdtools. Er wählt ein versioniertes Jupiter-Profil, das je Engine und Projekt in verfügbare Module aufgelöst wird. Das Ergebnis wird als unveränderlicher Snapshot an der Session gespeichert.

Damit bleiben drei Zustände sauber getrennt:

1. **Gewünscht:** globaler Standard plus Session-Ausnahme.
2. **Verfügbar:** installierte, auffindbare und gesunde Skills/MCP-/CLI-Module.
3. **Effektiv:** die konfliktfrei aufgelösten Module, mit denen diese konkrete Session gestartet wurde.

Die bestehende Jupiter-Konstitution bleibt oberste Verhaltensquelle. Caveman und Ponytail werden nicht als ungeprüfte Volltexte angehängt, sondern als deklarierte Regelmodule komponiert. CodeGraph wird über einen festen Discovery-/Health-Vertrag eingebunden; ein fehlender PATH-Eintrag blockiert keine Session.

### A) Komponenten-Struktur

```text
SettingsPage
└── TokenSavingsControl
    ├── GlobalSwitch (Default für neue Sessions)
    ├── ProfileBadge (balanced-v1)
    ├── ModuleStatusList
    │   ├── CavemanStatus
    │   ├── PonytailStatus
    │   ├── CodeGraphStatus
    │   └── spätere Module: RTK / Context Mode / Headroom
    └── HealthDetails (Version · Engine-Abdeckung · Warnung)

NewSessionDialog
└── TokenSavingsOverride
    ├── Standard verwenden
    ├── Ein
    ├── Aus
    └── EffectiveProfilePreview (welche Module wirklich starten)

FastAPI
├── SavingsSettingsStore       (globaler Wunsch + Profilversion)
├── SavingsHealthService       (Discovery und Health je Modul/Engine)
├── SavingsProfileResolver     (gewünscht + verfügbar → effektiv)
├── PromptCompositionService   (Priorität + Deduplizierung + Provenienz)
└── SessionManager             (Snapshot vor Engine-Start persistieren)

Engine-Start
├── ClaudeAdapter
├── CodexAdapter
└── OpenCodeAdapter
    └── erhalten nur den bereits aufgelösten Snapshot
```

### B) Verantwortungsgrenzen

- **Savings Settings Store:** hält nur den globalen Ein/Aus-Wert, die aktive Profilversion und administrative Modulfreigaben. Wie andere Jupiter-Settings bleibt er dateibasiert, atomar speicherbar und ohne Secrets.
- **Health Service:** beantwortet ausschließlich, ob ein Modul installiert, auffindbar, erreichbar und für die gewählte Engine geeignet ist. Er installiert oder repariert nichts selbst.
- **Profile Resolver:** verbindet globalen Wert, Session-Ausnahme, Engine, Projekttyp und Health zu einer effektiven Modulliste. Er ist die einzige Stelle, die `balanced-v1` interpretiert.
- **Prompt Composition:** führt Jupiter-Konstitution, Rolle, abc-Vorgaben, Caveman und Ponytail nach einer festen Priorität zusammen. Überlappende Kürzeregeln erscheinen genau einmal; der Resolver liefert zusätzlich einen für Nutzer und Tests lesbaren Provenienzbericht.
- **Engine-Adapter:** übersetzen den fertigen Snapshot in die jeweils unterstützte Integrationsform. Sie entscheiden nicht selbst, welche Policy gelten soll.
- **Session Manager:** speichert den Snapshot vor Prozessstart und verwendet ihn unverändert bei Folge-Turns, Reanimierung und Resume.

### C) Datenmodell in Klartext

#### Globale Savings-Einstellung
- Ein/Aus-Standard für neue Sessions.
- Aktive Profil-ID und Profilversion, zunächst `balanced-v1`.
- Administrative Freigabe pro Modul, damit ein problematischer Adapter unabhängig abgeschaltet werden kann.
- Herkunft und letzte erfolgreiche Aktualisierung sowie eine lesbare Warnung bei ungültiger Konfiguration.

Gespeichert in einer eigenen dateibasierten Jupiter-Konfiguration. Keine Datenbank und kein MinIO nötig.

#### Session-Snapshot
Jede Session erhält zusätzlich:

- Gewünschter Zustand: an oder aus.
- Quelle: globaler Standard, explizit an oder explizit aus.
- Profil-ID und Version.
- Effektive Module mit Modulversion, Integrationsart und Health zum Startzeitpunkt.
- Prompt-Provenienz: welche Regelquelle aktiv war und welche Überschneidungen entfernt wurden.
- Degraded-Hinweise, wenn ein gewünschtes Modul nicht verfügbar war.

Der Snapshot liegt im bestehenden SQLite-Session-Index, analog zu Engine, Modell und Transport. Er enthält keine vollständigen Prompts, Tool-Ausgaben oder Secrets.

#### Laufzeit-Metriken
- Native Provider-Tokens bleiben die primäre Messung.
- Pro Modul: geschätzte vermiedene Tokens, Zusatzlatenz, Fallback-Zähler und Messbarkeit.
- Qualitäts-/Pilotdaten werden getrennt von Session-Inhalten aggregiert.

### D) API-Shape

- `GET /settings/token-savings` → globalen Standard, Profilversion und Modul-Health lesen.
- `PUT /settings/token-savings` → globalen Standard und administrative Modulfreigaben speichern; keine Installation auslösen.
- `GET /settings/token-savings/preview` → effektives Profil für Engine und Projekt vor einem Session-Start anzeigen.
- `GET /settings/token-savings/modules/{module}/health` → Detaildiagnose eines Moduls, insbesondere CodeGraph-Discovery.
- `POST /sessions` → optionaler Session-Wert `standard`, `on` oder `off`; ohne Wert gilt `standard`.
- Bestehende Session-Leseendpunkte → liefern Savings-Snapshot und Degraded-Hinweise als Metadaten mit aus.
- Bestehende Metrics-/Usage-Sicht → ergänzt getrennte Savings-Schätzwerte und Fallbacks, ohne native Tokenwerte umzudeuten.

Alle Settings-Endpunkte bleiben hinter Jupiters bestehendem Auth-Gate. Es entsteht kein Installations- oder Update-Endpunkt im MVP.

### E) Prompt-Komposition und Konfliktpriorität

Der effektive Prompt folgt einer festen Rangfolge:

1. Sicherheits-, Permission-, Trust-, Watchdog- und Decision-Card-Verträge.
2. Expliziter Nutzerauftrag, Feature-Spec und abc-Akzeptanzkriterien.
3. Jupiter-Konstitution und aktive Rollenregeln.
4. Ponytail-Regeln für kleinsten vollständigen Code-Scope.
5. Caveman-Regeln für knappe Darstellung.

Caveman darf nur Darstellungsregeln verdichten. Ponytail darf unnötigen Umfang verhindern, aber keine geforderte Funktion entfernen. Der Composer arbeitet mit Regelkategorien statt bloßer Textähnlichkeit; dadurch ist die Deduplizierung deterministisch und testbar. Der bestehende stabile Prompt-Cache bekommt den Hash des effektiven Snapshots, damit verschiedene Savings-Profile nicht denselben Cache-Eintrag teilen.

### F) Engine-Strategie

| Engine | Caveman/Ponytail | CodeGraph | Architekturentscheidung |
|---|---|---|---|
| Claude | Native Skill-/Hook-Fähigkeiten, aber Regeln durch Jupiter komponiert | MCP plus Projektindex | Tiefste Integration; Jupiter behält System-Prompt und Permission-Settings als Quelle |
| Codex | Instruktions-/Skill-Fallback, in Session-Snapshot sichtbar | MCP bzw. Codex-Konfiguration | Keine Hook-Gleichwertigkeit vortäuschen; Resume erhält denselben Snapshot |
| OpenCode | Native Plugin-/Skill-Möglichkeiten, aber zentrale Jupiter-Policy | MCP plus vorhandener Index | Engine-Plugin darf Prompt-Priorität und Session-Lifecycle nicht übernehmen |

Die Engine-Adapter erhalten ausschließlich die vom Resolver freigegebenen Module. Eine globale Installation allein aktiviert nichts außerhalb des Session-Snapshots.

### G) CodeGraph Discovery

CodeGraph erhält vier unabhängige Prüfbereiche:

1. **Binary:** expliziter absoluter Pfad, danach kontrollierter Jupiter-Service-PATH.
2. **MCP:** Konfiguration vorhanden und Server erreichbar.
3. **Projekt:** `.codegraph` und Datenbank vorhanden.
4. **Frische:** Index passt ausreichend zum Projektstand.

Für den bekannten Host wird ein explizit konfigurierbarer Binary-Pfad verwendet, statt die NVM-Initialisierung einer interaktiven Shell nachzubauen. Dadurch funktionieren Direct- und tmux-Starts gleich. Health darf Hinweise zur Behebung liefern, verändert aber weder Shell-Profile noch MCP-Dateien oder den Index automatisch.

### H) Persistenz und Lebenszyklus

- Der globale Schalter wirkt nur beim Auflösen einer neuen Session.
- Der vollständige Snapshot wird vor dem Engine-Prozess gespeichert.
- Folge-Turns lesen ausschließlich den Session-Snapshot, nicht die inzwischen geänderten globalen Settings.
- Reanimierung und Backend-Neustart rekonstruieren denselben Snapshot aus dem Session-Index.
- Alte Sessions ohne Felder werden als Savings `Aus` behandelt.
- Wird eine gespeicherte Modulversion nicht mehr gefunden, entsteht ein auditierbarer Degraded-Fallback; die Session bleibt bedienbar.

### I) Fehler- und Sicherheitsmodell

- Alle optionalen Module sind Fail-open mit kurzem, modulbezogenem Timeout.
- Health-Checks verwenden keine Nutzerprompts und lesen keine Repository-Inhalte über das für Status/Indexprüfung Nötige hinaus.
- Keine Remote-One-Liner, Paketinstallation oder Konfigurationsmutation beim Umschalten.
- Fremdskills können keine höheren Prioritäten als Jupiter-Governance erhalten.
- Für RTK bleibt Telemetrie bei späterer Jupiter-Verwaltung standardmäßig aus.
- Vollständige Rohfehler bleiben bei gefilterten Tool-Ausgaben erreichbar; sicherheitskritische Ausgaben werden nicht verlustbehaftet komprimiert.

### J) Tech-Entscheidungen (Warum)

- **Eigenes Profil statt tokless als Runtime:** Jupiter braucht reproduzierbare Sessions, Health, Rollback und engine-spezifische Ehrlichkeit. Ein externer Installer kann diese Produktverträge nicht garantieren.
- **Dateibasierte globale Settings:** passt zu Policy, Watchdog, Transport und Engine-Registry; leicht prüfbar und atomar aktualisierbar.
- **Session-Snapshot in SQLite:** Resume darf sich nicht ändern, nur weil globale Settings oder installierte Skillversionen wechseln.
- **Zentraler Composer statt mehrere System-Prompts:** verhindert Doppelregeln und macht Prioritäten sowie Golden-Prompt-Tests möglich.
- **Expliziter CodeGraph-Pfad statt Shell-Magie:** Jupiter läuft als Dienst; interaktive NVM-Pfade sind dort nicht zuverlässig.
- **Preview vor Start:** Der Nutzer sieht Teilabdeckung, bevor Tokens verbraucht werden, und kann pro Session gezielt abschalten.
- **Keine automatische Installation im MVP:** trennt reversible Nutzung von sicherheitsrelevanten Systemänderungen.

### K) Abhängigkeiten / Pakete

- **Backend:** keine zwingenden neuen Python-Pakete. Vorhandene Pydantic-, YAML-/Datei-Store-, Session-Index- und Prozessdiagnose-Muster reichen.
- **Frontend:** keine neuen Pakete. Bestehende Switch-, Select-, Badge-, Tooltip- und Card-Komponenten reichen.
- **Externe Laufzeitmodule:** Caveman, Ponytail und das bereits installierte CodeGraph; Versionen werden erkannt und später explizit gepinnt.
- **Datenbank:** keine neue Datenbank; additive Felder im bestehenden SQLite-Session-Index.
- **MinIO/Neon:** nicht betroffen.

### L) Test- und Rollout-Strategie

1. **Composer-Vertrag:** Golden-Prompt-Tests für jede Konfliktklasse; keine doppelte Kürzeregel, keine verlorene Governance oder Acceptance Criteria.
2. **CodeGraph-Discovery:** absoluter Pfad, fehlender Service-PATH, MCP-Ausfall, veralteter/fehlender Index und tmux/direct werden getrennt getestet.
3. **Session-Invarianz:** globaler Wechsel nach Start, Resume, Reanimierung, Backend-Neustart und Alt-Session.
4. **Engine-Matrix:** Claude, Codex und OpenCode jeweils `standard/on/off`, inklusive ehrlicher Teilabdeckung.
5. **Früher Pilot:** Caveman und Ponytail zunächst mit kleinem Golden-Task-Set und sichtbarem Degraded-Fallback.
6. **CodeGraph-Pilot:** vorhandenen Jupiter-Index nutzen; Tool-Schema-Overhead, Navigationstreffer und breite Datei-Lesevorgänge vergleichen.
7. **Spätere Module:** RTK, Context Mode und Headroom jeweils einzeln gegen dieselbe Baseline, bevor Kombinationen zugelassen werden.

### M) Auswirkungen auf bestehende Features

| Feature | Auswirkung |
|---|---|
| PROJ-6 | Konstitution bleibt führend; Composer ersetzt überlappende Kürzezeilen bei aktivem Caveman, statt sie zusätzlich anzuhängen. |
| PROJ-9 | Neue Session erhält Override und effektive Profilvorschau. |
| PROJ-19 | Prompt-Cache-Key berücksichtigt Savings-Snapshot; spätere Effizienzmodule laufen über denselben Resolver. |
| PROJ-48/50/57 | Engine-spezifische Skill-/MCP-Integration, aber ein gemeinsamer Jupiter-Vertrag. |
| PROJ-51 | Settings-Seite bekommt eine eigene Sektion, ohne Engine-Registry mit Toolzuständen zu vermischen. |
| PROJ-52 | Native Providerwerte bleiben getrennt von Savings-Schätzungen. |
| PROJ-56/63 | Snapshot wird über Resume und beide Transportarten unverändert wiederverwendet. |

### N) Empfohlene Bau-Reihenfolge

1. Backend-Verträge: Settings Store, Health-Modell, Profil-Resolver, Composer und Session-Snapshot.
2. Caveman-/Ponytail-Adapter plus Golden-Prompt-Tests.
3. CodeGraph-Discovery mit explizitem Binary-Pfad und MCP-/Index-Health.
4. Settings-Sektion und Session-Override mit Preview.
5. Persistenz-/Resume- und vollständige Engine-Matrix-Tests.
6. Pilotmetriken; erst danach RTK und weitere Kompressionsmodule.

## QA Test Results
**Geprüft:** 2026-07-14 · **Ergebnis:** Nicht freigegeben, Status bleibt `In Review`

### Zusammenfassung

- Akzeptanzkriterien: **22 bestanden, 11 nicht erfüllt, 1 nicht anwendbar**.
- Automatisiert: PROJ-73/angrenzende Backend-API **27/27**, Frontend **180/180**, ESLint und Production-Build bestanden.
- Gesamtes Backend: **1.188 bestanden, 2 fehlgeschlagen**. Die beiden Fehler liegen außerhalb PROJ-73 und betreffen bekannten Drift/ungültiges YAML in den generierten Codex-Skills `abc-backoffice` und `abc-customer-journey`.
- Security: keine Critical-Finding und keine neue Speicherung von Secrets oder vollständigen Tool-Ausgaben gefunden.
- Ein visueller Browser-Smoke war in diesem QA-Lauf nicht Bestandteil; Build und Komponenten-/API-Tests waren grün.

### Findings

#### HIGH — QA-73-01: Kernadapter sind für die Ziel-Engines nicht betriebsbereit

Caveman und Ponytail sind für Claude, Codex und OpenCode jeweils `nicht installiert`. CodeGraph ist als Binary/Index vorhanden, aber nur für Claude als MCP konfiguriert; Codex und OpenCode degradieren. Damit erfüllt das aktuelle Deployment nicht den zugesagten frühen Skill-Pilot und nicht die engine-übergreifende Toolabdeckung. Der Schalter und der Snapshot funktionieren, aktivieren in der Live-Matrix aber maximal CodeGraph für Claude.

**Betroffen:** C5 sowie der abgestimmte Umfang „Skills früh“ und CodeGraph für alle Jupiter-Engines. **Empfehlung:** Caveman/Ponytail über die je Engine unterstützten Mechanismen installieren und die Adaptermatrix mit echten Starts verifizieren; CodeGraph-MCP für Codex/OpenCode explizit konfigurieren.

#### HIGH — QA-73-02: Mess- und Qualitäts-Gate fehlt

`estimated_tokens_avoided`, Zusatzlatenz, Fallback-Aggregate, Stichprobengröße, A/B-Piloten und die Kennzeichnung `nicht messbar` sind nicht implementiert. Damit kann Jupiter weder die behauptete Token-Wirkung prüfen noch Pilotmodule kontrolliert zu `stabil` hochstufen.

**Betroffen:** F2–F6. **Empfehlung:** getrennte Adaptermetriken und Pilot-Auswertung ergänzen; Providerwerte unverändert lassen und fehlende Schätzbarkeit explizit ausweisen.

#### MEDIUM — QA-73-03: CodeGraph wird ohne Reachability-Prüfung als „bereit“ gemeldet

Für Claude liefert der Health-Service `healthy=true`, obwohl `mcp_reachable=null` und `index_freshness="unknown"` sind. Die UI bildet `healthy` direkt auf `bereit` ab. Konfigurationspräsenz und vorhandene DB beweisen jedoch weder einen erfolgreichen MCP-Handshake noch einen aktuellen Index.

**Betroffen:** D1, E1. **Empfehlung:** begrenzten MCP-Handshake und echte Frischeprüfung in die Health-Entscheidung aufnehmen; bis dahin Status `Konfiguration nötig`/`unbekannt` statt `bereit`.

#### MEDIUM — QA-73-04: Speichern verliert den projektbezogenen CodeGraph-Health-Kontext

Die Settings-Seite lädt Health mit `/home/dev/projects/jupiter`, sendet beim `PUT` aber keinen `project_path`. Die PUT-Antwort prüft CodeGraph folglich ohne Projekt und ersetzt unmittelbar den UI-State; nach erfolgreichem Speichern kann ein zuvor erkannter Index fälschlich als fehlend erscheinen.

**Betroffen:** A3, D3 (Darstellung nach Save). **Empfehlung:** `project_path` beim Speichern mitsenden und serverseitig wie in Preview/Health validieren oder nach dem PUT den projektbezogenen GET erneut laden.

#### MEDIUM — QA-73-05: Snapshot pinnt die tatsächliche Adapter-Laufzeit nicht

Der Session-Snapshot speichert Modulname und erkannte Version, prüft diese Version bei Resume/Folge-Turns aber nicht erneut. Ein extern aktualisiertes CodeGraph bzw. ein nativer Skill kann daher unter unveränderten Snapshot-Metadaten mit anderer Laufzeitversion arbeiten.

**Betroffen:** Edge Case „Adapterversion ändert sich zwischen Turns“ und die Reproduzierbarkeitszusage aus B4. **Empfehlung:** gewünschte Version beim Wiederanlauf gegen die installierte Version prüfen; bei Abweichung sichtbar fail-open degradieren.

### Acceptance-Criteria-Matrix

| Bereich | Bestanden | Nicht erfüllt | N/A | Wesentliche Lücken |
|---|---:|---:|---:|---|
| A — Einstellungen | 4 | 1 | 0 | vollständige Adapterdetails/Health nach Save |
| B — Session/Persistenz | 5 | 0 | 0 | Versionsdrift separat als Finding dokumentiert |
| C — Engine-Abdeckung | 5 | 2 | 0 | RTK-Differenzierung; native/Instruktions-Einbindung der Skills |
| D — CodeGraph | 4 | 1 | 0 | Reachability und Frische nicht tatsächlich geprüft |
| E — Robustheit/Sicherheit | 3 | 2 | 1 | echter Runtime-Timeout/Fallback; RTK-Telemetrie mangels RTK |
| F — Messung/Qualität | 1 | 5 | 0 | Adaptermetriken, Dashboard und Pilot-Gate fehlen |

### Release-Entscheidung

**Nicht freigegeben.** Wegen zweier High-Findings bleibt PROJ-73 `In Review`. Der Settings-/Session-Unterbau ist stabil, erfüllt aber den nutzerwirksamen engine-übergreifenden Savings-Vertrag und dessen Messbarkeit noch nicht.

## Implementation Notes (Backend — /abc-backend, 2026-07-14)

**Branch:** `main`

### Gebaut
- Dateibasierter, atomar speichernder Savings-Store mit konservativem Default `Aus`, Profil `balanced-v1` und unabhängigen Modulfreigaben.
- Read-only Health-/Discovery-Service für Caveman, Ponytail und CodeGraph. CodeGraph trennt Binary, Version, MCP-Konfiguration, Projektindex und Index-Frische; NVM-Binaries werden auch ohne interaktiven Shell-PATH gefunden.
- Profil-Resolver für `standard / on / off` mit Fail-open/Degraded-Verhalten.
- Konfliktfreie Prompt-Komposition: Jupiter-Konstitution bleibt zuerst; Caveman verdichtet nur Darstellung, Ponytail ergänzt ausschließlich „kleinste vollständige Lösung“. Provenienz und Deduplizierungsentscheidung werden am Snapshot sichtbar.
- Settings-API: Lesen/Speichern, Preview und Modul-Health. Kein Endpunkt installiert Pakete oder verändert Fremdkonfiguration.
- Session-API und Manager: optionaler Savings-Override, effektiver Prompt vor Engine-Start, profilabhängiger Prompt-Cache-Key sowie unveränderliche Savings-Metadaten in allen Session-Responses.
- SQLite-Session-Index: additive, idempotente Spalten für Enablement, Quelle, Profilversion, Module, Degraded-Hinweise und Provenienz; Alt-Sessions degradieren auf `Aus`.
- Betriebsparameter für Savings-YAML und explizites CodeGraph-Binary in `.env.example` dokumentiert.

### Verifikation
- PROJ-73-Suite: **7 bestanden**.
- Angrenzende Constitution-/Cache-/Context-/Transport-Suites zusammen: **58 bestanden**.
- Gesamte Backend-Suite: **1.188 bestanden, 2 fehlgeschlagen**. Beide Fehler sind vorbestehend und PROJ-73-fremd: Drift/ungültiges generiertes Frontmatter in den lokalen Skills `abc-backoffice` und `abc-customer-journey` (`test_proj50_codex_abc.py`).
- Python-Compile und `git diff --check`: grün.
- `ruff` ist in der Dashboard-Umgebung nicht installiert. Die zwei neuen Dateien wurden mit dem vorhandenen Black formatiert; bestehende Dateien wurden nicht mechanisch umformatiert, um fremde Diffs zu vermeiden.

### Bewusste Backend-Grenze
- Caveman und Ponytail werden erkannt und konfliktfrei aufgelöst, aber nicht automatisch installiert. Fehlt ein Skill für eine Engine, bleibt er `degraded` und die Session startet ohne ihn.
- `mcp_reachable` und `index_freshness` bleiben zunächst `unknown`, statt Konfigurationspräsenz als echte Laufzeitmessung auszugeben. Ein aktiver MCP-Handshake und Index-Diff gehören in den späteren Adapter-/QA-Schritt.
- Zum Backend-Handoff waren Frontend-Schalter, Session-Auswahl und Health-/Preview-Darstellung noch offen; sie sind inzwischen im folgenden Frontend-Abschnitt umgesetzt.

## Implementation Notes (Frontend — /abc-frontend, 2026-07-14)

**Branch:** `main`

### Gebaut
- Neue Settings-Sektion „Token Savings“ mit globalem Default-Schalter, Profil-Badge und unabhängigen Modulfreigaben.
- Engine-Tabs für Claude, Codex und OpenCode; der Health-Status unterscheidet sichtbar `bereit`, `Konfiguration nötig` und `nicht installiert`.
- CodeGraph-Detailanzeige für Binary, MCP, Projektindex und Index-Frische, ohne unbekannte Werte als Erfolg auszugeben.
- Klarer Hinweis, dass der Schalter keine Tools installiert, fehlende Module fail-open ausgelassen werden und keine feste Einsparquote garantiert ist.
- Neue-Session-Dialog mit `Globalen Standard verwenden / Für diese Session einschalten / ausschalten`.
- Debouncte, nicht-blockierende Preview zeigt effektiven Zustand, Profilversion, aktive Module und Degraded-Gründe vor dem Start.
- Session-Request überträgt den gewählten Override; laufende Sessions werden als Snapshot erklärt.
- TypeScript-Verträge und API-Client für Settings, Speichern und Preview ergänzt.
- API-Vertragstests für URL-Encoding, PUT-Payload und Session-Preview ergänzt.

### Verifikation
- Vitest: **21 Testdateien, 180 Tests bestanden**.
- ESLint: bestanden.
- Next.js-Produktions-Build inklusive TypeScript und statischer Seitengenerierung: bestanden.

### Noch offen
- Visueller Browser-Smoke und vollständige Acceptance-Criteria-Prüfung folgen mit `/abc-qa` bzw. `/abc-qa-e2e`.

## Implementation Notes (Backoffice — QA-73-01, 2026-07-14)

### Fix
- Caveman ist global für Claude Code (User-Plugin und Skill), Codex (globaler Skill) und OpenCode (nativer Plugin-Adapter plus Skill) installiert.
- Ponytail ist global für Claude Code und Codex als User-Plugin installiert; für OpenCode ist das native Plugin global konfiguriert. Der globale Ponytail-Skill steht über die vorhandene Claude/OpenCode-Skill-Verknüpfung auch OpenCode zur Verfügung.
- Die Health-Discovery erkennt jetzt zusätzlich die versionsierten nativen Plugin-Caches von Claude und Codex. Dadurch gilt eine tatsächlich installierte Native-Integration nicht mehr fälschlich als `nicht installiert`.

### Verifikation
- Live-Matrix: Caveman und Ponytail melden für Claude, Codex und OpenCode jeweils `installed=true`, `healthy=true`, `integration=native`.
- Backend: `tests/test_proj73_token_savings.py` — **8 bestanden** (inklusive Regressionstest für den versionsierten Codex-Plugin-Cache).
- QA-73-01 ist für Caveman/Ponytail behoben. Der unabhängige CodeGraph-Teil sowie QA-73-02 bis QA-73-05 bleiben offen; der Projektstatus bleibt daher `In Review`.

## QA Recheck — 2026-07-14

**Ergebnis:** Nicht freigegeben · Status bleibt `In Review`.

- Automatisiert: gezielte Backend-Suiten **19 bestanden**; ESLint bestanden; Next.js-Produktionsbuild kompiliert und typprüft erfolgreich.
- Security: Keine neue externe Schreib- oder Installationsschnittstelle im Metrics-Pfad gefunden. Die Metrics-Route ist read-only.

#### HIGH — QA-73-06: Golden-Pilot-Metriken sind nicht in den Laufzeitpfad verdrahtet

Die neue SQLite-Struktur und `evaluate_golden_pilot()` erwarten `savings_pilot_task` und `savings_latency_ms`. `SessionManager._row()` schreibt beide Felder jedoch nicht, `SessionManager._state_from_row()` liest sie nicht, `SessionCreate` akzeptiert keine Golden-Task-Kennung und `SessionRuntime` misst keine Start-bis-Result-Latenz. Daher enthält jede echte Zeile `NULL`; die API kann keine A/B-Paare bilden und das Pilot-Gate bleibt dauerhaft `not_ready`.

**Reproduktion:** Eine Session starten und den persistierten `session_index` prüfen: die beiden neuen Spalten bleiben leer; Suche nach den Feldnamen zeigt keine Messung im Event-/Result-Pfad.

**Betroffen:** F2–F6, insbesondere die zugesagte automatische Pilot-Freigabe. **Empfehlung:** Golden-Task-ID als streng validiertes Session-/Runner-Feld übertragen, monotone Startzeit am Turn-Beginn erfassen, am finalen Result persistieren und Golden-Suite-Runs über einen kontrollierten Runner ausführen. Erst dann A/B-Schätzung und Gate bewerten.

## Implementation Notes (Backoffice — QA-73-06, 2026-07-14)

- `savings_pilot_task` ist als erlaubte Golden-Task-ID (`code_search`, `debugging`, `tests`, `review`, `free_chat`) im Session-API-Vertrag validiert und wird bis zum `SessionState` durchgereicht.
- Golden-Sessions starten eine monotone Uhr bei der Engine-Initialisierung; beim finalen Result wird `savings_latency_ms` gemessen.
- Beide Felder werden im SQLite-Live-Index geschrieben, bei Rehydrierung gelesen und in der Session-Response sichtbar gemacht. Damit kann die A/B-Auswertung echte, gepaarte Golden-Task-Runs auswerten.

## QA Recheck — 2026-07-14 (Golden-Pilotpfad)

**Ergebnis:** Nicht freigegeben · Status bleibt `In Review`.

- Automatisiert: gezielte Backend-Suiten **19 bestanden**; ESLint und Next.js-Produktionsbuild bestanden.
- QA-73-06 ist im Datenpfad behoben: Task-ID und Latenz werden von der Session bis SQLite geführt.

#### HIGH — QA-73-07: Pilot-Gate aggregiert Engines und Aufgabenklassen unzulässig

`evaluate_golden_pilot()` prüft nur insgesamt mindestens fünf Savings- und fünf Kontrollläufe. Es gruppiert weder nach `engine` noch verlangt es für beide Varianten alle fünf Golden-Tasks. Fünf Claude-Code-Suche-Läufe und fünf Codex-Review-Läufe könnten daher gemeinsam `stable` ergeben, obwohl für keine Engine ein vollständiger A/B-Vergleich existiert. Eine Sicherheitsregression wird ebenfalls nicht als Gate-Eingang persistiert oder geprüft.

**Reproduktion:** `evaluate_golden_pilot()` mit fünf Savings-Zeilen für eine Engine/Task und fünf Kontroll-Zeilen für eine andere Engine/Task aufrufen; die Mindestmenge ist erfüllt, obwohl kein gültiges Paar existiert.

**Betroffen:** F3–F5 und die vereinbarte Schnell-Pilot-Regel. **Empfehlung:** Ergebnisse pro Engine und Golden-Task bündeln, je Zelle mindestens fünf An-/Ausläufe fordern und Sicherheit/Qualität als explizite Gate-Felder aufnehmen. Der Gesamtstatus darf nur `stable` sein, wenn jede geprüfte Engine die vollständige Suite besteht.

## Deployment

**Ausgelöst:** 2026-07-14 · **Version:** `0.27.32` · **Commit:** `7bcf17c` · **Tag:** `v0.27.32-PROJ-73`

`main` und der Release-Tag wurden nach `origin` gepusht; der konfigurierte VPS-Auto-Deploy baut den Stand automatisch. Die Host-seitige Build-/Smoke-Bestätigung bleibt außerhalb dieser Session zu prüfen.

## QA-Freigabe — 2026-07-14

**Ergebnis:** Approved · explizit durch den Nutzer freigegeben.

- Verifiziert: Backend **21 gezielte Tests bestanden**, ESLint und Next.js-Produktionsbuild bestanden.
- Der kontrollierte Golden-Runner, die A/B-Metriken, Latenz-/Fallback-Erfassung und das Gate je Engine/Aufgabenklasse sind vorhanden.
- **Akzeptiertes Restrisiko:** Die Ergebnisqualität der Golden-Tasks wird noch nicht semantisch gegen task-spezifische Sollantworten bewertet. Der Nutzer hat dieses Risiko ausdrücklich akzeptiert; es blockiert die Freigabe nicht.
