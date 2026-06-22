# 🪐 Brainstorming: Jupiter — KI-Agenten-Kommandozentrale

**Datum:** 2026-06-22
**Status:** Konzept (Divergenz + Konvergenz abgeschlossen, bereit für Requirements)
**Referenz-Messlatte:** [Wayland](https://github.com/FerroxLabs/wayland) (FerroxLabs) — lokales AI Agent Command Center

---

## 1. Session-Setup

| Feld | Inhalt |
|---|---|
| **Topic** | Jupiter — modulares Framework / Kommandozentrale für KI-Agenten-gestützte Entwicklung |
| **Goal** | Produktkonzept + priorisierte Feature-Landkarte |
| **Approach** | Progressive Flow (breit divergieren → fokussiert ordnen) |
| **Frontend** | **Next.js 16 (App Router) + React** — Web-GUI zuerst (Browser über Tailscale), Desktop-App später. **(entschieden)** |
| **Nutzer** | Erst solo, später teamfähig |
| **Ambition** | Großes, dauerhaftes Projekt — Kommandozentrale der gesamten Dev-Umgebung |
| **Herzstück** | Claude Max Subscription (nicht API-only); später Codex, Gemini, GLM, Ollama, OpenRouter |
| **Tech-Stack** | FastAPI-Backend + **Next.js/React-Frontend** + Postgres + Hal-Vault |
| **Architektur-Prinzip** | Maximal modular & erweiterbar |

---

## 2. Produktkonzept (der eine Satz)

> **Jupiter ist eine selbstgehostete Kommandozentrale, die deine KI-Agenten — allen voran Claude Max — als überwachbare, token-sparsame Flotte orchestriert, mit deinem Hal-Vault als gemeinsamem Gedächtnis und deinem abc-Workflow als nativem Betriebssystem.**

**Haltung (3 Grundprinzipien, die alles prägen):**
1. **Cockpit-first, nicht Chat-first** — du steuerst eine Flotte, du tippst nicht in ein leeres Eingabefeld.
2. **Autonom by default, du greifst nur an Schaltstellen ein** — Agenten laufen allein, du entscheidest das Wichtige.
3. **Token-Sparsamkeit by Design** — keine aufgeblähten Sessions, kein Geschnatter; das richtige Modell für die richtige Aufgabe.

---

## 3. Divergenz — die 28 Bausteine (nach Domäne)

### Domäne: Cockpit & Steuerung
**[#1] Mission-Control-Startbildschirm** — Erster Screen = kompaktes Lagebild: kleiner globaler Status + alle Agenten + alle laufenden Sessions auf einen Blick. *Cockpit statt Chatbot.*

**[#2] Session-Kachel mit Ampel-Signalen** — Jede Session zeigt ohne Reinklicken: Status (arbeitet / wartet auf dich / fertig / Fehler), aktive Rolle/Skill, Projekt, Laufzeit. *„Wartet auf dich" ist das Leitsignal.*

**[#3] Session-Kanban (Logik 1: nach Zustand)** — Karten wandern durch Spalten `Arbeitet → Wartet auf dich → Review/Approval → Fertig`. Bewegung teils automatisch (Agent wechselt Zustand). *Vertrautes Mentalmodell × Live-Agent-Zustände.*

**[#4] Karten-Detail = Entscheidungsansicht (Decision Card)** — Klick auf wartende Karte zeigt alles für eine 5-Sekunden-Entscheidung: Was will der Agent? + relevanter Ausschnitt (Diff/Befehl, nicht das ganze Log) + Warum + Kontext (Projekt/abc-Phase) + Aktionen (Freigeben / Ablehnen / Mit Kommentar zurück / In Session springen). *Optimiert auf den Entscheidungsmoment.*

### Domäne: Governance & Vertrauen
**[#5] Abgestuftes Vertrauen (Trust-Policy / „Konstitution")** — Pro Rolle/Skill/Projekt: was autonom (Auto-Approve), was erzeugt eine Decision Card, was ist hart verboten. Default = möglichst autonom. *Vertrauen ist Richtlinie pro Kontext, nicht global an/aus.*

**[#19] Amok-Schutz: Limits + Watchdog** — Token-/Zeit-/Aktions-Limits + Watchdog, der Endlosschleifen / wildes Schreiben erkennt und Sessions **pausiert** (nicht killt) → Decision Card. Nutzt dieselbe Trust-Policy. *Autonomie mit Reißleine.* **(kritischstes Failure-Szenario)**

**[#24] Knappheits-Konstitution (kein Geschnatter)** — Globaler System-Prompt erzwingt Disziplin: keine Vorreden, keine Wiederholungen, keine „Soll ich…?"-Schleifen. Pro Rolle anpassbar. *Output-Kultur zentral durchgesetzt.* **(MVP-Kern)**

### Domäne: Sessions & Engines (der Motor)
**[#6] Einheitliche Session über Treiber-Modell** — Session = projektbezogene Sicht auf ein Chat-Window. Darunter austauschbarer Treiber (CLI wie Claude Code, oder API/SDK). Nach oben sehen alle gleich aus. *Engine wechseln ohne Mentalmodell-Wechsel.*

**[#12] Mitdenkender Session-Start (Smart Launcher)** — „Neue Session" liest `features/INDEX.md`, schlägt nächste abc-Phase + passenden Skill/Rolle vor, Default-Engine Claude Max. *Start ist ein Vorschlag aus deinem eigenen Workflow.*

**[#13] Integrations-Spektrum: Treiber → iFrame → Startknopf** — Drei Tiefen je nach Aufwand: generischer CLI-Adapter / fremde App als iFrame / simpler Launch-Button. *Integration ist kein Alles-oder-nichts.* (z. B. Hermes, Paperclip)

**[#22] Modell-Routing nach Aufgabentyp** — Haiku für mechanisches (Netzwerk-/Shell-Befehle, Datei-Ops, Status), Sonnet als Standard, Opus nur für komplexe Architektur/Reasoning. Eskalation auch innerhalb einer Session. *Modell = Ressource pro Aufgabe.* **(MVP-Kern)**

### Domäne: Kontext & Gedächtnis
**[#7] Context-Management mit sauberem Handover** — Jupiter überwacht Kontextfenster-Füllung und resettet bewusst an Übergabepunkten mit gutem Handover. *Geplanter Staffelstab statt Notbremsen-Crash.*

**[#8] Handover automatisch + manuell, als MD im Vault** — Auto an Phasenübergängen + auf Knopfdruck. Inhalt: Wo stehen wir? / Was ist erledigt / Was offen / Fallstricke / Pointer statt Volltext. *Ein Artefakt = Kontext-Reset + Audit-Trail + Doku.*

**[#25] Kontext-Budget sichtbar pro Session** — Füllstandsanzeige des Kontextfensters + Token-Verbrauch auf der Karte; Schwellenwarnung → Handover-Vorschlag. *Macht Verschwendung sichtbar, bevor sie teuer wird.* **(MVP-Kern)**

**[#23] Pointer statt Volltext (Vault-RAG)** — Agenten bekommen Links zu Vault-Dateien statt Volltext; nur relevante Ausschnitte werden geladen. *Kontext schlank ohne Informationsverlust.*

**[#26] Billige Späher-Agenten für Suche** — „Lies viele Dateien, gib nur das Fazit"-Aufgaben gehen an günstige Explorer (Haiku); teure Hauptsession bleibt schlank. *Teure Modelle denken, billige holen.*

**[#27] Prompt-Caching für Rollen/Skills** — Wiederkehrende Rollen-/Skill-Prompts + stabiler Projektkontext werden gecacht statt neu gesendet. *Stabile Skills = dauerhaft billiger.*

### Domäne: Vault als Wahrheit
**[#9] Vault als lebendes Gehirn (Stufe 3)** — Agenten lesen aktiv aus dem Vault und schreiben strukturierte Spuren zurück; Wissen wird projektübergreifend durchsuchbar. Bleibt offenes MD, direkt lesbar/editierbar. *Kein Black-Box-Memory.*

**[#10] Zwei Schichten: rohe Logs ↔ kuratiertes Wissen** — Rohe Session-Mitschriften (vollständig, Audit) vs. destilliertes Wissen (Entscheidungen, Lösungen, Sackgassen, Muster). *Rohdaten bleiben, Kopf-Index bleibt sauber.*

**[#11] Kuratierung: Schwelle → Vorschlag → Freigabe** — Trigger (Bug gelöst, ADR gefallen, Sackgasse verworfen) lösen Wissens-Vorschlag aus; du gibst per Card frei/editierst. *Ereignisgetrieben, gleicher Freigabe-Flow.*

**[#14] Vault-Integration als geteilter Dienst** — Vault-Anbindung (lesen/schreiben/suchen) ist ein Dienst, den auch eingebettete Apps nutzen können. *Gemeinsame Datenschicht der ganzen Kommandozentrale.*

**[#20] Wiederherstellung über den Vault** — Nach VPS-Reboot rekonstruiert Jupiter Sessions aus dem Vault bis zum letzten Handover, mit „Hier ging's weiter"-Vorschlag. *Vault = Crash-Recovery-Journal.* **(kritischstes Failure-Szenario)**

### Domäne: Arbeitsraum (Dateien)
**[#15] Fileexplorer + Drag-and-Drop-Transport** — Vollständiger Fileexplorer (à la 1Panel) als neutrale Ebene; Dateien per DnD zwischen PC und VPS. Bewusst von Sessions entkoppelt. *Gleiche Shell, getrennte Mentalmodelle.*

**[#16] MD-Reader/-Editor mit Obsidian-DNA** — Markdown lesen *und* leicht editieren, mit `[[Wikilinks]]` + Backlinks. *Doku lebendig bearbeitbar, kein Tool-Wechsel.*

### Domäne: Multi-Agent-Orchestrierung
**[#17] Jupiter als Dispatch-Schicht (der fehlende Orchestrator)** — Koordinator-Modus, der Tickets aus `features/INDEX.md` an Spezialisten-Sessions verteilt und ihre Zusammenarbeit steuert. *Materialisiert die „Hauptsession"-Rolle, die dein Agent-Team-Design schon voraussetzt (du machst sie heute von Hand).*

**[#18] Vertrag-zuerst + Koordinator als Schiedsrichter** — Architect legt API-Vertrag als Vault-Artefakt fest (alle bauen dagegen); bei Konflikten vermittelt der Koordinator-Agent, eskaliert im Zweifel als Decision Card. *Dokument als objektiver Schiedsrichter + Agent als Vermittler.*

**[#30] Cross-Agent-Review / Challenge (adversariell, engine-übergreifend)** — Das Ergebnis eines Agenten wird von einem **anderen** Agenten (bevorzugt andere Engine/anderes Modell) geprüft und herausgefordert. Beispiel: eine via `/abc-architecture` von **Claude Opus** entwickelte Architektur wird von **Codex** (oder Gemini/GLM) gechallengt. Natürlich in Flow/UI eingebaut: **„Challenge"-Aktion auf einem erzeugten Artefakt** (Architektur-Doku, ADR, Diff/Code) startet eine Reviewer-Session mit anderer Engine; deren Kritik kommt als Review-Notiz / Decision Card (#4) zurück, Artefakt aus #18 ist das Prüfobjekt. *Diversität der Modelle fängt blinde Flecken, die Selbst-Review eines einzelnen Modells übersieht.* **(nicht MVP — Phase 2, baut auf Multi-Engine #13 + Dispatch #17/#18 auf)**

### Domäne: Eingabe & Interaktion
**[#29] Spracheingabe (Push-to-Talk), abo-frei** — Diktat statt Tippen fürs Auftrag-Feld im Smart Launcher (#12) und für Decision-Card-Antworten (#4). **Kein Monats-Abo (kein WhisperFlow).** Empfohlener Weg: **A) self-hosted Whisper auf dem VPS** (`faster-whisper`/`whisper.cpp`, open source, keine laufenden Kosten, Daten bleiben lokal) als Standard, **B) Groq Whisper (pay-per-use, Cent-Beträge)** als optionaler Schnell-Fallback — exakt das Muster des `watch`-Skills. **C) Browser Web Speech API verworfen** (sendet Audio an Google → kollidiert mit der DSGVO-Linie, gleiche Logik wie das Google-Fonts-Verbot). *Lokal-first & abo-frei statt bequem-aber-fremdgehostet.*

### Domäne: Token-Effizienz (Querschnitt)
**[#28] Token-/Kosten-Dashboard** — Verbrauch heute/pro Projekt/pro Modell; erkennt, welche Rollen/Tasks Token fressen. *Schließt den Regelkreis fürs Routing (#22).*

### Domäne: Team-Zukunft
**[#21] Identität von Tag 1 — aber schlank** — Jede Session/Handover/Wissensnotiz trägt ein `owner`-Feld (heute immer du). Kein volles Auth/RLS jetzt — nur das Feld wird nie weggelassen. *Vermeidet die teuerste spätere Migration für minimalen Aufwand.*

---

## 4. Konvergenz — Themen-Cluster (Module)

| Modul | Bausteine | Rolle im Produkt |
|---|---|---|
| **A. Cockpit** | #1, #2, #3, #4, #28 | Das Gesicht — Flottenübersicht, Kanban, Entscheidungen |
| **B. Governance** | #5, #19, #24 | Vertrauensregeln, Watchdog, Output-Disziplin |
| **C. Engine-Layer** | #6, #12, #13, #22 | Treiber-Abstraktion, Launcher, Integration, Routing |
| **D. Kontext-Engine** | #7, #8, #23, #25, #26, #27 | Handover, Budget, schlanker Kontext |
| **E. Vault (Gedächtnis)** | #9, #10, #11, #14, #20 | Einzige Wahrheit, Wissen, Recovery |
| **F. Arbeitsraum** | #15, #16 | Dateien & Doku |
| **I. Eingabe** | #29 | Spracheingabe (Push-to-Talk), abo-frei |
| **G. Multi-Agent** | #17, #18, #30 | Orchestrierung mehrerer Spezialisten + Cross-Agent-Review |
| **H. Team-Fundament** | #21 | Zukunftssichere Identität |

---

## 5. Priorisierte Feature-Landkarte (Phasen)

### 🟢 Phase 0 — MVP („der kleinste nutzbare Kern")
Ziel: Du steuerst **mehrere parallele Claude-Max-Sessions** in einer GUI, mit Vault-Anbindung und Token-Disziplin — und ersetzt damit dein heutiges Terminal-Setup.

- **Engine:** Claude Max via **Claude Code headless** (nur CLI-Treiber) — Treiber-Modell #6
- **Cockpit:** Mission Control #1 + Session-Kanban (Logik 1) #3 + Ampel-Kacheln #2
- **Entscheiden:** Decision Cards #4 + Trust-Policy Grundform #5
- **Starten:** Smart Launcher #12 (liest `features/INDEX.md`)
- **Kontext:** Handover auto + manuell #8 + #7
- **Vault:** Stufe 1–2 — Sessions/Handovers als MD reinschreiben + lesen (#8, #9 Ansatz)
- **Token-Kern:** Modell-Routing #22 · Knappheits-Konstitution #24 · Kontext-Budget-Anzeige #25
- **Doku:** MD-Reader (read-first) #16
- **Fundament:** Identitäts-Feld #21

### 🟡 Phase 1 — Ausbau (Komfort, Robustheit, Effizienz)
- **Arbeitsraum:** Fileexplorer + DnD #15 · MD-Editor mit Obsidian-Features #16 (voll)
- **Vault Stufe 3:** lebendes Gehirn #9 · roh↔kuratiert #10 · Kuratierung Schwelle→Freigabe #11
- **Resilienz:** Amok-Watchdog #19 · Recovery über Vault #20
- **Weitere Engines:** Codex / Gemini / GLM / Ollama als Treiber · iFrame + Launch-Button #13
- **Effizienz-Ausbau:** Pointer/RAG #23 · Späher-Agenten #26 · Prompt-Caching #27 · Token-Dashboard #28
- **Eingabe:** Spracheingabe / Push-to-Talk, abo-frei (self-hosted Whisper + Groq-Fallback) #29

### 🔵 Phase 2 — Skalierung (Orchestrierung & Team)
- **Multi-Agent:** Dispatch-Schicht #17 · Vertrag-zuerst + Koordinator #18 · Cross-Agent-Review/Challenge engine-übergreifend #30
- **Vault als geteilter Dienst** #14 (auch für eingebettete Apps)
- **Team-Fähigkeit:** echtes Auth (JWT) + Scope/RLS auf dem `owner`-Feld #21 aufbauen
- **Marktplatz/Registry** für Rollen / Skills / Agenten (teilbar)

---

## 6. Empfohlene Bau-Reihenfolge (warum diese Sequenz)

1. **Engine-Treiber zuerst (#6, Claude Code headless)** — ohne das läuft nichts. Erst *eine* Session sauber starten/lesen/steuern können.
2. **Dann Cockpit (#1–#4)** — sobald 1 Session läuft, mehrere sichtbar machen + Entscheidungen.
3. **Parallel Kontext-Engine (#7/#8/#25)** — Handover + Budget verhindern von Anfang an Bloat (dein Kernanliegen).
4. **Vault-Anbindung (#8→#9)** — macht Handover + Recovery erst nützlich und schaltet Stufe 3 frei.
5. **Token-Routing (#22) + Konstitution (#24)** — früh einziehen, prägt das Verhalten aller Sessions.
6. *Erst danach* Komfort (Files, Editor) und *zuletzt* Multi-Agent — das setzt einen stabilen Unterbau voraus.

> **Schlüssel-Erkenntnis der Session:** Die Architektur-Entscheidung **„Vault als einzige Wahrheit"** zahlt dreifach: Gedächtnis (#9) + Doku (#8) + Crash-Recovery (#20). Ein Konzept, drei Probleme gelöst.

---

## 7. Getroffene Entscheidungen & offene Punkte

### ✅ Getroffene Entscheidungen
- **Frontend-Framework: Next.js 16 (App Router) + React.** Begründung: Cockpit mit Kanban, **iFrame-Embedding fremder Apps (#13)** und ein **MD-Editor mit Obsidian-Features (#16)** sind im React/Next.js-Ökosystem mit fertigen Bausteinen am schnellsten umsetzbar (web-native). Stack damit: **FastAPI + Next.js/React + Postgres + Hal-Vault**, gemäß Default-Stack-Option B.

### ❓ Offene Punkte (vor dem Bauen klären)

1. **🔑 Claude-Max-Engine bestätigen (wichtigste Knacknuss).**
   Pragmatischer Weg: **Claude Code headless als Subprozess** (`claude -p` / Stream-JSON I/O), das nutzt die **Max-Subscription-Auth** (via `claude login`) — *kein* API-Key.
   **Architektonische Konsequenz:** Der Claude-Treiber ist *Claude Code*, **nicht** die rohe Anthropic-API. Modell-Routing (#22: Haiku/Sonnet/Opus) läuft über das `--model`-Flag der CLI. Cross-Provider (Codex/Gemini) = je eigener Treiber. → *Vor dem MVP technisch verifizieren.*

2. **🗄️ Live-Zustand vs. Wahrheit.**
   Wo lebt der *flüchtige* Live-Session-Zustand (welche Karte ist gerade wo)? Vorschlag: **Postgres als schneller Live-Index**, **Vault (MD) als persistente Wahrheit/Recovery-Quelle**. → Datenmodell in der Architektur-Phase.

3. **🧭 Vault-Struktur.** Ordner-/Namens-Konvention innerhalb des Hal-Vaults für: rohe Logs vs. kuratiertes Wissen vs. Handovers vs. abc-Doku. Muss zu deinem bestehenden Hal-Layout passen.

4. **🛑 Watchdog-Metriken (#19).** Was genau heißt „Amok"? Konkrete Schwellen definieren (Tokens/min, wiederholte identische Tool-Calls, Schreibrate, Zeit ohne Fortschritt).

---

## 8. Nächster Schritt

Konzept steht. Empfehlung: **`/abc-requirements`** starten, um aus Phase 0 (MVP) die erste Feature-Spec (`PROJ-1`) zu schneiden — sinnvoller Erststart: **„Engine-Treiber: eine Claude-Max-Session headless starten, lesen, steuern"** (offener Punkt #1 verifizieren), gefolgt vom Cockpit.
