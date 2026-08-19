# Frontdesk-Triage — 2026-08-03

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #135)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 67e94040 (Freshdesk #135) — "Kunden: Kontaktdaten verschwunden" | Übergreifendes Problem — DSGVO-Retention-Autopurge löscht Kontakte der Kategorie „Versorger" (fehlt in der Ausnahmeliste) | Hoch |

---

### Ticket: Peppermint "Kontaktdaten verschwunden" (Peppermint 67e94040-26c3-4289-9c28-eb346d233fce, Freshdesk #135, Nutzer f.erol@erolimmobilien.de, Erol Immobilien GmbH, Mandant 00000000-0000-0000-0000-000000000001)

**Kurzbefund:** Kunde meldet, sein Versicherungsmakler sei komplett aus dem Kundenmodul
verschwunden ("unter Kunden und Kommunikation alles versucht — einfach weg"), während die
zugehörigen Mails in Outlook noch sichtbar sind. Erwartung des Kunden: Kontakte bleiben
gespeichert, bis er sie selbst löscht.

**Eingrenzung:** Backend · Modul: Kundenverwaltung / DSGVO-Aufbewahrungsfrist
(`immo-crm`, `backend/app/main.py:2763` Hintergrund-Thread „daily cleanup of clients with expired
retain_until", ruft `_purge_client()` (Zeile ~735) auf, das den Client + alle Konversationen,
Nachrichten, Anhänge und Dokumente hart löscht — kein Soft-Delete, keine Papierkorb-Funktion).

Code-Grep-Befund: `_compute_retain_until()` (`backend/app/main.py:728`) setzt für jeden Kunden
automatisch ein Ablaufdatum (`retain_until`, Standard 12 Monate bzw. Tenant-Policy), NACH dessen
Ablauf der tägliche Hintergrund-Job den Datensatz automatisch und unwiderruflich löscht. Von dieser
Auto-Löschung ausgenommen sind laut Code nur die drei Kategorien `"Partner"`, `"Dienstleister"`,
`"Mitarbeiter"` (`retain_until` bleibt für sie `NULL`). Das Frontend bietet aber daneben noch eine
vierte, eigenständige Kategorie **„Versorger"** an (`lib/features/clients/client_list_screen.dart:232`),
die in der Ausnahmeliste **fehlt**. Ein Versicherungsmakler-Kontakt gehört inhaltlich klar in dieselbe
Klasse wie Partner/Dienstleister (dauerhafte Geschäftsbeziehung, kein zeitlich befristeter
Interessent) — landet er aber unter „Versorger" (oder wird versehentlich falsch kategorisiert),
bekommt er trotzdem ein Ablaufdatum und wird nach Fristablauf lautlos und endgültig gelöscht, ohne
Benachrichtigung außer einem Audit-Log-Eintrag (`reason: "consent_expired"`).

Das ist kein Einzelfall dieses einen Datensatzes: der Mechanismus (fehlende Kategorie in der
Ausnahmeliste) würde bei jedem Mandanten, der Versicherungsmakler, Handwerker, Notare o. Ä. unter
„Versorger" pflegt, nach Ablauf der Retention-Frist identisch zuschlagen.

**Dringlichkeit:** Hoch
Kernfunktion (Kundendatenverwaltung) betroffen, echter und endgültiger Datenverlust (kein
Soft-Delete/Papierkorb, `_purge_client` löscht hart inkl. Konversationen/Dokumente), strukturell
wiederkehrend bei jedem Mandanten mit „Versorger"-Kontakten, DSGVO-Bezug (die Funktion, die
eigentlich DSGVO-konform sein soll, produziert hier ungewollten Datenverlust). Nicht „Dringend",
da kein akuter Blocker für die Tagesarbeit des Kunden und die Löschung bereits geschehen ist (kein
laufender Schaden, der sich in Minuten verschlimmert) — aber zeitnahe Bearbeitung nötig, bevor
weitere Kontakte denselben Fristablauf erreichen.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für die Meldung — das tut uns leid. Wir haben einen wahrscheinlichen technischen
> Grund gefunden: Kontakte mit bestimmten Kategorien erhalten automatisch ein
> Aufbewahrungs-Ablaufdatum (DSGVO-Fristen) und werden danach automatisch gelöscht. Ihr
> Versicherungsmakler-Kontakt dürfte davon betroffen gewesen sein. Wir prüfen das genau und melden
> uns zeitnah mit einer Lösung sowie dazu, ob und wie sich der Kontakt wiederherstellen lässt.
>
> Damit wir das für Sie einordnen können: Wissen Sie noch ungefähr, wann der Kontakt ursprünglich
> angelegt wurde, und unter welcher Kategorie (z. B. „Versorger", „Dienstleister")?

**Rückfragen-Guidance:**
- Ungefähres Anlagedatum des Versicherungsmakler-Kontakts (hilft, das `retain_until`/Purge-Datum
  im Audit-Log zu finden).
- Unter welcher Kategorie war der Kontakt geführt (Versorger/Dienstleister/Sonstiges)?
- Name/E-Mail des Kontakts, um im Audit-Log gezielt nach dem Purge-Eintrag zu suchen.

---

Nächster Schritt: `/abc-backoffice` bzw. direkte Backend-Fix-Session — „Versorger" (und ggf. weitere
Nicht-Interessenten-Kategorien) in die Ausnahmeliste in `_compute_retain_until()`
(`backend/app/main.py:735`) und `get_retention_months()` (`backend/app/services/email_service.py:158`)
aufnehmen; zusätzlich empfehlenswert: Soft-Delete/Papierkorb statt Hard-Delete für
`_purge_client()`, sowie Prüfung, ob sich der bereits gelöschte Kontakt dieses Kunden aus dem
Audit-Log wiederherstellen lässt.
