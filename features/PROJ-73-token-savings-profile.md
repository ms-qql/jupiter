# PROJ-73: Token Savings — globales, engine-übergreifendes Optimierungsprofil

## Status: Planned
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
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
