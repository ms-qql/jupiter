# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #116)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint ac4acbc2 (Freshdesk #116) — "KI Funktion" | Übergreifendes Problem: KI-"Verbessern"-Funktion schreibt Texte grundsätzlich komplett um statt leicht zu editieren — gleicher Kunde/gleiche Ursache wie bereits dokumentiertes Ticket #84 (Anrede) | Mittel |

---

### Ticket: Peppermint-Ticket "KI Funktion" (Peppermint ac4acbc2-dac2-42e0-9bac-36ff2310d578, Freshdesk #116, Absender: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Firat Erol beschwert sich allgemein, dass die KI-Funktion im IMMo-CRM seine Texte
"einfach komplett umschreibt" und "einfach besser funktionieren" muss. Kein konkretes Fehlerbild,
keine Vorher/Nachher-Stelle im Ticket-Text selbst benannt — als Beleg liegt ein Word-Dokument
(`Mein geschriebener Text.docx`, Freshdesk-Attachment, nicht abgerufen) bei.

Dieses Ticket ist derselbe Kunde und dasselbe Feature wie das heute bereits dokumentierte Ticket
Freshdesk #84 ([Report](2026-07-08-immocrm-ki-schreibfunktion-anrede.md)), dort konkret an der
Anrede/Sie-Form festgemacht. Ticket #116 wirkt wie dieselbe Unzufriedenheit, jetzt allgemeiner
formuliert ("die KI muss besser funktionieren") — kein neuer Einzelfall, sondern eine zweite Meldung
zum selben Grundproblem.

**Eingrenzung:** Backend · Modul: KI-Schreibassistent (`immo-crm`, PROJ-14, Deployed)
Code-Grep in `backend/app/services/ai_service.py` (`rewrite_text`, Zeilen 139–183) bestätigt den
allgemeineren Verdacht hinter der Kundenbeschwerde:
- Jede Ton-Option in `tone_instructions` (Zeilen 160–167: `professional`, `friendly`, `shorter`,
  `longer`, `formal`, `casual`) ist als **"Schreibe den Text ... um"** formuliert — keine der
  Anweisungen enthält eine Vorgabe, den Originaltext möglichst zu erhalten oder nur gezielt zu
  editieren. Das Modell wird also bei jeder Nutzung der "Verbessern"-Funktion explizit zu einer
  Komplett-Neuformulierung angewiesen, nicht zu einer leichten Überarbeitung.
- Das deckt sich mit dem bereits für Ticket #84 gefundenen Root-Cause-Ansatz (dort: `tone`
  clientseitig hart auf `'professional'` verdrahtet) — hier zeigt sich zusätzlich, dass selbst bei
  anderen Tönen (`friendly`, `casual` etc.) grundsätzlich "umschreiben" statt "leicht anpassen"
  instruiert wird. Das betrifft strukturell jeden Nutzer der KI-Funktion, nicht nur diesen Kunden.

**Dringlichkeit:** Mittel
Kein Datenverlust-, DSGVO- oder Blocker-Fall (Kunde kann seinen Originaltext weiter unverändert
verwenden), aber es ist dieselbe Kernfunktion (KI-Schreibassistent, PROJ-14) wie bei Ticket #84,
und der Kunde meldet sich hier bereits zum zweiten Mal zum selben Grundproblem — das spricht für
spürbaren, wiederkehrenden Unmut, nicht für ein einmaliges Ärgernis. Freshdesk-Priorität "low"
erscheint dadurch etwas niedrig; Einstufung bleibt bei Mittel, da weiterhin kein Blocker und ein
klarer Fix-Ansatz vorliegt (Rewrite-Prompts um eine "möglichst nah am Original bleiben"-Vorgabe
ergänzen, ergänzend zur bereits für #84 vorgeschlagenen Ton-Auswahl im UI).

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Rückmeldung. Wir haben Ihr Feedback zur KI-Schreibfunktion registriert und
> bringen es mit Ihrer vorherigen Meldung zur Anrede-Umwandlung zusammen — beides hängt mit
> demselben Verhalten zusammen: Die Funktion schreibt Texte aktuell grundsätzlich vollständig um,
> statt sie nur leicht zu überarbeiten. Wir prüfen, wie wir die KI-Funktion so anpassen können, dass
> sie näher am von Ihnen geschriebenen Text bleibt, und melden uns, sobald wir mehr dazu wissen.

**Rückfragen-Guidance:** Für eine genauere Einordnung wäre hilfreich zu wissen, welchen Bereich der
App er konkret meint (E-Mail-Entwurf, Exposé-Text, interne Notiz?) und ob er ein konkretes
Vorher/Nachher-Beispiel direkt im Ticket-Text nennen kann — das beigefügte Word-Dokument wurde im
Rahmen dieser Ersteinschätzung nicht abgerufen.

---
