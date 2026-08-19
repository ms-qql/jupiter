# Frontdesk-Triage — 2026-07-10

Quelle: Nutzer-Screenshot `/home/dev/projects/clipboard/image-73.png` und lokale Jupiter-/tmux-Logs.
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| GPT 5.6 Sol-Session bricht sofort mit "Prozess endete mit Code 1" ab | Übergreifendes Problem: installierte Codex-CLI ist für `gpt-5.6-sol` zu alt; Jupiter zeigt nur den generischen Exit-Code | Hoch |

---

### Ticket: GPT 5.6 Sol-Session lässt sich nicht zurück/starten und endet sofort mit Code 1

**Kurzbefund:** Übergreifendes Problem

**Eingrenzung:** Schicht: Backend/CLI-Harness · Modul: Engine-Layer `generic_cli` / Codex-tmux-Transport.
Der betroffene Session-Eintrag ist `57fef0f2-b69c-4ef3-b4db-775e68f1fc39` (`engine=codex`, `model=gpt-5.6-sol`, `transport=tmux`, Projektpfad `/home/dev/projects/jupiter`). Die tmux-Ausgabe enthält die eigentliche Ursache:

```text
Model metadata for `gpt-5.6-sol` not found. Defaulting to fallback metadata; this can degrade performance and cause issues.
The 'gpt-5.6-sol' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.
```

Installiert ist aktuell `/home/dev/.local/bin/codex -> /home/dev/.codex/packages/standalone/current/bin/codex` mit `codex-cli 0.142.5`. Der Prozess beendet sich daraufhin mit Exit-Code 1, bevor ein verwertbarer Assistant-Turn oder Token-Usage entsteht (`tokens_used=0`, `session_transcript=[]`).

Zusatzbefund: Die UI-Überschrift zeigt "OpenCode", weil `project_name` dieses Session-Eintrags "OpenCode" ist. Technisch war es aber kein OpenCode/OpenRouter-Lauf, sondern eine Codex-Session (`engine=codex`) mit Modell `gpt-5.6-sol`. OpenCode selbst ist separat installiert (`opencode 1.17.18`) und ist hier nicht die auslösende CLI.

Jupiter-Oberflächenproblem: `backend/app/engine/adapters.py::codex_parse_line` ignoriert Codex-Events vom Typ `error` und `turn.failed`; `backend/app/engine/generic_cli_driver.py` setzt bei Exit-Code 1 dann nur stderr bzw. den generischen Fallback `Prozess endete mit Code 1.`. Deshalb sieht der Nutzer die eigentliche Provider-/CLI-Fehlermeldung nicht im Cockpit, obwohl sie in `out.log` vorhanden ist.

**Dringlichkeit:** Hoch
GPT-5.6-Sol-Sessions sind aktuell auf diesem System mit der installierten Codex-CLI nicht nutzbar. Das blockiert einen Kern-Workflow für alle Nutzer/Sessions mit diesem Modell. Kein Datenverlust, keine DSGVO-Relevanz, aber unmittelbare Arbeitsblockade und irreführende Fehlermeldung.

**Antwortentwurf an den Kunden:**
> Die Session ist nicht wegen Ihres Prompts oder wegen OpenCode selbst abgebrochen. Der Lauf wurde technisch als Codex-Session mit Modell `gpt-5.6-sol` gestartet, und die installierte Codex-CLI (`0.142.5`) ist für dieses Modell zu alt. Codex liefert intern die Meldung: `gpt-5.6-sol requires a newer version of Codex`. Jupiter zeigt im Cockpit aktuell nur den generischen Exit-Code 1 an; das ist ein Anzeige-/Fehlerweitergabeproblem im Engine-Layer. Kurzfristig hilft ein Update der Codex-CLI oder die Auswahl eines Modells, das mit der installierten CLI-Version noch unterstützt wird.

**Rückfragen-Guidance:** Keine Rückfrage nötig für die Ursache. Für die Behebung sollte entschieden werden, ob zuerst nur die Codex-CLI aktualisiert wird oder zusätzlich Jupiter angepasst wird, damit `error`/`turn.failed`-Events aus Codex sichtbar im Transkript bzw. `state.error` landen.
