# Frontdesk-Check — OpenCode-Chatstart ohne Initial-Prompt

**Datum:** 2026-07-10

**Quelle:** Nutzer-Screenshot der produktiven Jupiter-Session „Test OC2"

**Hinweis:** Interne Ersteinschätzung, kein vollständiges QA-Ergebnis.

### Ticket: Neue OpenCode-/MiniMax-Session endet sofort mit „You must provide a message or a command"

**Kurzbefund:** Übergreifendes Problem

**Eingrenzung:** Schicht: Backend · Modul: Session-Lifecycle / Generic-CLI-/tmux-Transport (PROJ-34, PROJ-57, PROJ-63)

Die produktive Session `b0f2427e-782c-4e45-b2d2-4f8f66133e49` („Test OC2") wurde mit `opencode-go/minimax-m3` und leerem Initial-Prompt gestartet. Im zugehörigen tmux-Ordner fehlt deshalb eine Prompt-Datei; der Oneshot-Prozess erhält `/dev/null` als stdin und OpenCode beendet sich vor dem ersten Turn. Die UI erlaubt dies im Chat-Modus ausdrücklich, während der Generic-CLI-Treiber trotzdem sofort einen Oneshot-Prozess startet. Codex akzeptiert laut Nutzer denselben Leerstart; der Fehler ist daher OpenCode-spezifisch, betrifft dort aber jede Session mit dieser Startkonstellation.

**Dringlichkeit:** Hoch

Der frisch deployte OpenCode-Hauptpfad ist für den vorgesehenen Chat-Start ohne Initial-Prompt vollständig blockiert. Es gibt keinen Datenverlust und einen einfachen Workaround, aber jeder Nutzer mit derselben Startkonstellation trifft denselben Fehler.

**Antwortentwurf an den Kunden:**
> Danke für den Screenshot. Ihre OpenCode-API und das MiniMax-Modell funktionieren; der Fehler entsteht beim Start einer Chat-Session ohne ersten Text. Bis zur Korrektur tragen Sie bitte bereits im Feld „Initial-Prompt" einen kurzen ersten Auftrag ein. Wir haben den übergreifenden Session-Startfehler eingegrenzt und prüfen die Korrektur separat.

**Rückfragen-Guidance:** Für die Einstufung fehlen keine wesentlichen Angaben. Für einen nachgelagerten Fix sollte nur bestätigt werden, ob der Start bewusst im Modus „Chat" und mit leerem Feld „Initial-Prompt" erfolgte; der Screenshot und die produktiven Session-Artefakte belegen den technischen Ablauf bereits ausreichend.
