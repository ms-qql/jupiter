# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #114)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 6ac2f14c (Freshdesk #114) — "Mail durcheinander" | Übergreifendes Problem (strukturell, aber bewusste Scope-Entscheidung aus PROJ-91): Der Live-Screen "Kommunikation" (`clients_mailview`) aktualisiert eine bereits geöffnete Kunden-Mailansicht nur beim erneuten Öffnen des Kunden, nicht per Hintergrund-Polling — neue Mails erscheinen daher erst nach F5/Reselect, nicht automatisch | Mittel |

---

### Ticket: Peppermint-Ticket "Mail durcheinander" (Peppermint 6ac2f14c-6bfa-4c39-a177-924dad18cad7, Freshdesk #114, Absender: Firat Erol / Erol Immobilien GmbH, adressiert an Manfred)

**Kurzbefund:** Firat Erol berichtet knapp (Tippfehler, kein Bug-Report-Format): Erst nach einem
Browser-Refresh (F5) war "die" (vermutlich eine erwartete Mail/Nachricht im Kunden-Mailverlauf)
sichtbar. Er merkt an, dass der Nutzer nicht "immer" mit F5 arbeiten sollte — deutet auf ein
wiederkehrendes, nicht einmaliges Verhalten hin. Betreff "Mail durcheinander" und fehlender
konkreter Kunden-/Datensatzbezug lassen offen, welche Mail/welcher Kunde genau gemeint war.

**Eingrenzung:** Frontend · Modul: Kommunikation / Kunden-Mailverlauf
(`immo-crm`, `lib/features/clients_mailview/application/kunden_neu_providers.dart`,
Route `/kunden-neu`, Feature PROJ-61/PROJ-91).

Code-Grep-Befund:
- Der Live-„Kommunikation"-Screen (`clients_mailview`/`KundenNeuNotifier`) ist bereits reaktiv
  (Riverpod `StateNotifier`) und cached Mails pro Kunde (AK7, PROJ-91). Beim (erneuten) Öffnen
  eines Kunden zeigt er sofort den Cache und gleicht **still im Hintergrund** einmal ab
  (`_load(clientId, silent: true)`, `kunden_neu_providers.dart:161`).
- Es gibt in dieser Datei **keinen** `Timer.periodic`/Polling-Mechanismus, der eine bereits
  geöffnete Kunden-Mailansicht automatisch aktualisiert, solange der Nutzer auf ihr verweilt. Der
  Abgleich läuft ausschließlich bei `selectClient()` (Kundenwechsel) bzw. `retry()`.
- Das ist laut PROJ-91-Spec (Re-Scope 2026-06-30) eine **bewusste** Scope-Entscheidung: kontinuierliches
  Live-Polling/WebSocket für diesen Screen wurde explizit ausgeschlossen ("kein WebSocket in diesem
  Ticket"); nur das alte, tote `messages_screen.dart` hatte ein 30-s-Voll-Polling, ist aber nicht der
  live genutzte Screen.
- Konsequenz: Trifft eine neue Mail ein, während ein Makler den Kunden-Mailverlauf bereits geöffnet
  hat, erscheint sie **nicht automatisch** — erst ein erneutes Öffnen des Kunden (weg/zurück-Klick)
  oder ein Seiten-Reload (F5) triggert den (stillen) Reload. Das passt zur Beschreibung "nach F5
  war die wieder zu sehen" und zur Beobachtung, dass es kein Einzelfall, sondern ein wiederkehrendes
  Muster ist.
- Diese Vorbedingung (neue Mail kommt an, während der Verlauf gerade offen ist) ist im
  Maklerarbeitsalltag alltäglich und nicht an eine spezielle Kundenkonstellation gebunden →
  strukturell, würde jeden Nutzer/jeden Kunden gleichermaßen treffen. Daher **Übergreifendes
  Problem**, auch wenn bisher nur ein Ticket vorliegt.
- Nicht live geprüft (kein Zugriff auf Produktivdaten/Session); Einschätzung beruht auf
  Code-Analyse + der PROJ-91-Spec-Historie.

**Dringlichkeit:** Mittel
Betrifft die Kernfunktion Kommunikationsverlauf, aber kein Datenverlust (Mail ist im System
vorhanden, nur die Ansicht ist nicht live) und ein einfacher, dem Nutzer bereits bekannter Workaround
(F5) existiert. Da es sich um eine bewusste, dokumentierte Scope-Grenze aus PROJ-91 handelt und
nicht um eine neu eingeschleppte Regression, wird auf Mittel statt Hoch eingestuft — mit Empfehlung,
bei gehäuften weiteren Meldungen ein eigenes Ticket für Live-Aktualisierung (Polling/WebSocket) auf
`clients_mailview` zu erwägen.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis. Kurze Rückfrage, damit wir das gezielt einordnen können: Ging es um
> eine neue E-Mail, die im Kundenverlauf erst nach einem Neuladen der Seite (F5) sichtbar wurde,
> während der Verlauf des jeweiligen Kunden bereits geöffnet war? Um welchen Kunden bzw. welche
> Mail es sich handelte, wäre für uns hilfreich. Wir prüfen die technische Ursache und melden uns
> mit dem Ergebnis.

**Rückfragen-Guidance:**
- Um welchen Kunden/welche Mail es konkret ging (Name/Kunden-ID, ungefähre Uhrzeit).
- Ob der Kunden-Mailverlauf zu diesem Zeitpunkt bereits offen war (also die neue Mail "live"
  fehlte) oder ob er den Kunden neu geöffnet hatte und sie dennoch fehlte (unterscheidet
  "kein Live-Refresh" von einem echten Anzeigefehler).
- Ob das Verhalten reproduzierbar ist (z. B. bei der nächsten eingehenden Mail erneut beobachtet).

---

Nächster Schritt bei Bedarf: bei Bestätigung/Häufung ein Ticket für Live-Aktualisierung
(Hintergrund-Polling oder WebSocket) auf `clients_mailview` anlegen, mit Bezug zu PROJ-91
(bewusst nicht umgesetztes AK "Eingehende Nachricht während geöffneter Konversation").
