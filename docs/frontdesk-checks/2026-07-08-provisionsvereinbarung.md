# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #90)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint ed0fd119 (Freshdesk #90) — "Provisionsvereinbarung" | Kein klassisches Bug-Ticket — vager Wunsch/Reminder zu einer Provisions-Bestätigungssperre; betroffener Mechanismus existiert für den Exposé-Kanal bereits, für andere Anfrage-Kanäle unklar | Niedrig |

---

### Ticket: Peppermint-Ticket "Provisionsvereinbarung" (Peppermint ed0fd119-6c8f-4a76-9e75-53235985a2c8, Freshdesk #90, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht im eigentlichen Sinn. Die Absenderin formuliert eine
Verhaltensanforderung: "Wenn der Kunde die Provision nicht bestätigt, soll die Anfrage nicht
durchgehen und der Kunde soll eine automatische Rückmeldung erhalten, dass er der Provision
zustimmen soll." Es wird kein konkretes Fehlverhalten beschrieben (kein Datum, kein betroffener
Kunde/Datensatz, keine Angabe, über welchen Kanal die "Anfrage" hereinkam) — das Ticket liest sich
wie ein Reminder/Anforderungswunsch, nicht wie eine Reproduktion eines beobachteten Fehlers.

**Eingrenzung:** Backend · Modul: Provisionsvereinbarung/Exposé-Consent
(`immo-crm`, `backend/app/routes/expose.py::provision_submit`,
`backend/app/services/email_service.py` Phase-24-05-Autoset).

Code-Grep-Befund:
- Für den **Exposé-Anfrage-Kanal** (Kunde fordert über die Web-Exposé-Seite das vollständige
  Exposé/Dokumente an) existiert die gewünschte Sperre bereits: `provision_submit` validiert
  serverseitig `if has_courtage and provision_consent != "on": errors.append(...)` und lässt die
  Anfrage bei fehlender Zustimmung **nicht** durch (Formular wird mit Fehlermeldung erneut
  angezeigt, kein Consent-Datensatz wird angelegt). Bei erfolgreicher Zustimmung verschickt
  `_send_provision_confirmation` eine Bestätigungs-Mail an den Kunden.
- Für **E-Mail-Anfragen von Immobilienportalen** (`email_service.py`, "Phase 24-05") wird
  `provision_consent` für Absender von `@immobilienscout24.de`/`@immoscout24.de` dagegen
  **automatisch auf 'Ja' gesetzt**, ohne dass der Kunde tatsächlich zustimmt — das ist inhaltlich
  das Gegenteil einer Bestätigungssperre für diesen Kanal.
- Das Ticket nennt nicht, welchen Kanal die Absenderin meint. Da bereits zwei frühere,
  verwandte Vorfälle im selben Themenfeld dokumentiert sind — `PROJ-84` (Security-Hotfix:
  Dokument-Download ohne gültigen Consent möglich) und `PROJ-100` (Hotfix: Provision-Consent ging
  beim Anlegen des Kundendatensatzes verloren, Fund aus einem früheren Frontdesk-Check) — ist
  Provisions-Consent ein Bereich mit wiederkehrenden Lücken; das allein macht dieses Ticket aber
  noch nicht zu einem bestätigten neuen Bug.

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; kein konkret beschriebener Vorfall, kein blockierter Kunde,
keine neue Rechts-/Datenrisiko-Angabe über die bereits bekannten (und bereits gefixten) Fälle
PROJ-84/PROJ-100 hinaus. Einzige Auffälligkeit, die für eine genauere Prüfung spricht: die
wiederholte Häufung von Provisions-Consent-Themen in diesem Modul — daher eher "genau hinschauen"
als "ignorieren", aber ohne akuten Handlungsdruck.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für Ihre Nachricht. Für Anfragen über die Exposé-Seite gibt es bereits eine
> Bestätigungspflicht: Ohne Zustimmung zur Provisionsvereinbarung wird die Anfrage nicht
> abgeschickt, der Kunde erhält eine entsprechende Fehlermeldung im Formular.
>
> Damit wir prüfen können, ob es noch eine Lücke gibt, wäre hilfreich zu wissen: Über welchen Weg
> kam die Anfrage herein, bei der Ihnen aufgefallen ist, dass die Provision nicht bestätigt wurde
> (z. B. Exposé-Formular auf der Website, E-Mail-Anfrage über ein Immobilienportal, direkte
> Kunden-Mail)? Gerne auch mit Datum bzw. Kundenname, damit wir den konkreten Fall nachvollziehen
> können.

**Rückfragen-Guidance:** Es fehlt die Angabe, über welchen Anfrage-Kanal die Provision nicht
bestätigt wurde (Exposé-Web-Formular vs. E-Mail-Anfrage über ein Portal vs. direkte Anfrage), ob
es sich um einen konkret beobachteten Vorfall (mit Kunde/Datum) oder eine allgemeine
Prozessanforderung handelt, und ob die Absenderin die bereits bestehende Sperre im
Exposé-Formular kennt bzw. warum diese aus ihrer Sicht nicht ausreicht.

---

Nächster Schritt bei Bedarf: Rückfrage an Beata Rutkowska nach dem konkreten Anfrage-Kanal; falls
E-Mail-Anfragen über Portale gemeint sind, den Autoset-Mechanismus in `email_service.py`
(Phase 24-05) im Lichte dieses Wunsches über `/abc-requirements` im `immo-crm`-Projekt neu
bewerten. Kein akuter Fix ohne weitere Information sinnvoll.
