# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #113)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint ba96ef4d (Freshdesk #113) — "Mail durcheinander" | Vermutlich übergreifendes Problem: im Kunden-Kommunikationsverlauf von "Frau Brendeke Gras" erscheint bei einem Nutzer eine Nachricht eines völlig anderen Kunden ("Herr Burghard"), während sie bei einer Kollegin am selben Kunden korrekt angezeigt wird — nicht live geprüft | Hoch |

---

### Ticket: Peppermint-Ticket "Mail durcheinander" (Peppermint ba96ef4d-83f6-45d5-a412-c1fb3e1432eb, Freshdesk #113, Absender: Firat Erol / Erol Immobilien GmbH, adressiert an Manfred)

**Kurzbefund:** Firat Erol berichtet (knapp, Tippfehler): Er wollte im Kunden-Kommunikationsverlauf
von "Beata Rutkowska ihrem" Kunden — gemeint ist vermutlich der von Beata betreute Kunde
"Frau Brendeke Gras" — eine Nachricht nachlesen. Auf Beatas eigenem Rechner steht dort die
korrekte Nachricht. Bei ihm (Firat) erscheint stattdessen unter demselben Kundendatensatz eine
Nachricht eines **anderen** Kunden, "Herr Burghard" (Screenshot als Anhang, hier nicht einsehbar).
Es geht also nicht um eine fehlende oder verzögerte Nachricht, sondern darum, dass am selben
Kunden-Datensatz zwei verschiedene Personen zwei verschiedene (und die eine davon eindeutig
falsche) Nachrichten sehen.

**Eingrenzung:** Vermutlich Frontend, ggf. Backend/Datenverknüpfung · Modul: Kommunikation /
Kunden-Mailverlauf (`immo-crm`, `lib/features/clients_mailview/application/kunden_neu_providers.dart`,
Backend-Endpoint `GET /messages/by-client/{client_id}` in `backend/app/routes/messaging.py:318`).

Code-Grep-Befund:
- Der Backend-Endpoint filtert die Nachrichten sauber über
  `WHERE c.client_id = %s AND c.tenant_id = %s` (messaging.py:357) — bei korrektem `client_id`
  im Request kann er serverseitig keine Nachricht eines anderen Kunden zurückgeben. Das spricht
  eher gegen einen reinen Backend-Query-Bug.
- Der Frontend-Cache in `kunden_neu_providers.dart` (`KundenNeuNotifier`) ist explizit pro
  `clientId` isoliert (`_cache[client.id]`, Zeile 149/192) und zusätzlich über einen
  identitätsgebundenen `cacheKey` (Tenant+User+Permissions) vom jeweiligen Notifier getrennt
  (AK14, PROJ-91) — ein simples Cache-Leck zwischen zwei Kunden im selben Notifier ist damit auf
  den ersten Blick nicht ersichtlich.
- Da exakt derselbe Kunde ("Frau Brendeke Gras") bei Beata korrekt, bei Firat aber mit dem Inhalt
  eines fremden Kunden ("Herr Burghard") angezeigt wird, deutet das eher auf einen
  **Client-seitigen Effekt bei Firat** (z. B. Browser-/HTTP-Cache einer älteren Antwort für eine
  andere Kunden-URL, oder ein Widget-/Tastenwechsel-Bug bei der Kundenauswahl, der den falschen
  `client_id` an den Request bindet) als auf einen serverseitig falsch verknüpften Datensatz — bei
  Letzterem müsste auch Beata die falsche Nachricht sehen, da der Query serverkanonisch ist.
- Kein exakter Treffer für "falscher Kunde im selben Verlauf angezeigt" in `features/INDEX.md`;
  der nächstliegende bekannte Cluster ist **PROJ-38** ("E-Mail-Verlauf — Anzeige &
  Cross-User-Sichtbarkeit", On Hold), der aber **fehlende/unvollständige** Sichtbarkeit zwischen
  Nutzern behandelt (Anhänge/Mails fehlen), nicht das Anzeigen der Nachricht eines **anderen
  Kunden**. Diese Ticket-Symptomatik ist also vermutlich ein neuer, eigenständiger Fund und nicht
  automatisch Teil des bestehenden Clusters.
- Ohne Live-Zugriff (kein Screenshot einsehbar, keine Kunden-/Konversations-ID bekannt) lässt sich
  nicht zwischen Frontend-Anzeigefehler und einer falsch verknüpften Konversation in der DB
  unterscheiden — Reproduktionsversuch bleibt daher auf Code-Analyse beschränkt.
- Die auslösende Vorbedingung (zwei Makler betreuen gemeinsam Kunden, mehrere Kundenakten werden
  im selben Zeitraum durchgesehen) ist im Maklerarbeitsalltag alltäglich und nicht an eine
  Sonderkonstellation gebunden → sollte sich der Mechanismus bestätigen, wäre er strukturell und
  würde jeden Nutzer/jede Kundenkombination treffen können. Daher vorläufig als **übergreifendes
  Problem** eingestuft, auch wenn bislang nur ein Ticket vorliegt.

**Dringlichkeit:** Hoch
Freshdesk hat "low" gesetzt, das wird hier bewusst überschrieben: Es geht um die Kernfunktion
Kommunikationsverlauf, mit einem konkreten Verdacht auf **Vermischung personenbezogener Daten
zweier verschiedener Kunden** (Nachricht von "Herrn Burghard" erscheint im Verlauf von "Frau
Brendeke Gras") — ein potenzielles DSGVO-relevantes Vertraulichkeitsproblem, nicht nur ein
Anzeige-Komfortthema. Kein bestätigter Fall bisher, aber das Risiko (falsche Zuordnung
sensibler Kundenkommunikation) rechtfertigt zügige Prüfung statt Einordnung als Kleinigkeit.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis, das nehmen wir ernst. Damit wir das gezielt nachvollziehen können:
> Könnten Sie uns den Screenshot noch einmal beschreiben bzw. bestätigen, welcher Kunde im
> Verlauf ausgewählt war (Name/Kundennummer) und welcher Kunde in der angezeigten Nachricht als
> Absender/Betreff erschien? Auf welchem Gerät/Browser ist Ihnen das aufgefallen, und war es
> reproduzierbar (z. B. beim erneuten Öffnen desselben Kunden)? Wir prüfen das umgehend.

**Rückfragen-Guidance:**
- Genaue Kunden-ID/-Name, dessen Verlauf geöffnet war ("Frau Brendeke Gras" — Bestätigung, ob das
  korrekt ist), und Kunden-ID/-Name der fälschlich angezeigten Nachricht ("Herr Burghard").
- Browser/Gerät, auf dem der Fehler auftrat (Firat), zum Vergleich mit Beatas Gerät.
- War der Fehler reproduzierbar (nochmal denselben Kunden geöffnet, gleiches Ergebnis)?
- Uhrzeit des Vorfalls, und ob kurz zuvor ein anderer Kundendatensatz (ggf. der eines
  "Herrn Burghard") angesehen wurde.
- Der im Ticket erwähnte Screenshot (Freshdesk-Anhang) — direkter Zugriff für die Analyse wäre
  hilfreich, war hier nicht einsehbar.

---

Nächster Schritt bei Bedarf: `/abc-qa` im `immo-crm`-Projekt für einen gezielten Test des
Kunden-Wechsel-Pfads in `clients_mailview` (schnelles Wechseln zwischen zwei Kunden, insbesondere
mit vorherigem Browser-Cache) sowie Prüfung, ob die betroffene Konversation serverseitig korrekt
`client_id` von "Frau Brendeke Gras" trägt. Bezug zu PROJ-38 nur als Nachbar-Cluster, nicht als
identisches Symptom.
