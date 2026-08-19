# Frontdesk-Check — 2026-08-13

Quelle: Nutzer direkt (interne Meldung im Chat). Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Download-Button in Dateien reagiert nicht / wirft dann viele Downloads gleichzeitig | Übergreifendes Problem | Mittel |

---

### Ticket: Ordner im Fileexplorer auswählen + „herunterladen" drücken — mal passiert nichts, mal starten viele Downloads auf einmal

**Kurzbefund:** Übergreifendes Problem — der Mechanismus trifft jeden Nutzer, der einen größeren Ordner herunterlädt, nicht nur einen Einzelfall.

**Eingrenzung:** Schicht: Frontend (Hauptursache) · Modul: Fileexplorer / Dateien (PROJ-11), `nextjs_app/components/cockpit/file-explorer.tsx`

Code-Grep-Fund: `handleDownloadSelected` (Zeile ~245) und der Pro-Zeile-Download-Button (`IconBtn`, Zeile ~628) haben **keinen Lade-/Disabled-Zustand**. Der Button bleibt nach dem Klick klickbar, es gibt kein Spinner-Feedback. Backend-seitig baut `build_zip`/`_stream_zip` (`backend/app/engine/files.py:366-433`) das ZIP synchron per `os.walk` über den kompletten Ordnerinhalt, bevor der Download im Browser startet — bei einem größeren Ordner kann das spürbar dauern. In dieser Zeit wirkt der Button "tot", der Nutzer klickt vermutlich mehrfach nach. Jeder Klick löst eine eigene `downloadZip`-Anfrage aus; kommen mehrere Antworten kurz hintereinander zurück, feuert der Browser mehrere Downloads gleichzeitig — das erklärt beide geschilderten Symptome (scheinbar nichts passiert, dann mehrere Downloads auf einmal).

**Dringlichkeit:** Mittel — Kernfunktion (Datei-Download) ist betroffen und für jeden Nutzer reproduzierbar, aber kein Daten-/DSGVO-Risiko, kein Datenverlust; Workaround (warten statt mehrfach klicken) vorhanden, sobald bekannt.

**Antwortentwurf an den Kunden:**
> Danke für den Hinweis. Beim Herunterladen größerer Ordner fehlt aktuell eine Rückmeldung, dass die Anfrage läuft — dadurch wirkt der Button kurz "tot" und ein erneuter Klick löst einen zweiten Download aus. Wir schauen uns das im Fileexplorer an. Bis dahin am besten nach dem Klick auf „herunterladen" kurz warten, statt mehrfach zu klicken.

**Rückfragen-Guidance:** Für eine genauere Eingrenzung wäre hilfreich: ungefähre Ordnergröße/Dateianzahl der betroffenen Ordner, ob es auch bei kleinen Ordnern (wenige Dateien) auftritt oder nur bei großen, und ob "nichts passiert" nach Sekunden oder erst nach Minuten doch noch etwas kommt. Nicht live nachgestellt (kein konkreter Ordner/Repro-Fall genannt) — Einschätzung basiert auf Code-Analyse.
