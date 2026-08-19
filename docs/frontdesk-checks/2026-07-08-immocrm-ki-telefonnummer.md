# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #96)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint de718d71 (Freshdesk #96) — "Eingegebene Telefonnummer wird nicht von KI übernommen wenn wir eine Mail schreiben" | Kein Bug: KI-Textüberarbeitung entfernt Telefonnummern bewusst vor dem KI-Aufruf (DSGVO-PII-Scrubbing) und ersetzt sie durch einen Platzhalter, der so im Ergebnis stehen bleibt — strukturell reproduzierbar für jeden Nutzer der Funktion | Mittel |

---

### Ticket: Peppermint-Ticket "Eingegebene Telefonnummer wird nicht von KI übernommen wenn wir eine Mail schreiben" (Peppermint de718d71-4eb7-469d-8937-b147cbece3ea, Freshdesk #96, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, adressiert an Manfred)

**Kurzbefund:** Kein klassischer Fehlerbericht, aber ein reproduzierbares, unerwünschtes Verhalten:
Wird in einem E-Mail-Entwurf eine Telefonnummer eingetippt und der Text danach über die
KI-Umschreiben-Funktion überarbeitet, verschwindet die Nummer und wird durch "(Telefonnummer)"
ersetzt — die Nutzerin muss sie danach von Hand wieder eintragen.

**Eingrenzung:** Backend · Modul: KI-Schreibassistent / E-Mail-Composer
(`immo-crm`, `backend/app/services/ai_service.py`).

Code-Grep-Befund:
- `rewrite_text()` (Zeile 119–163) ist die Funktion hinter "Text über KI umschreiben". Bevor der
  Text an DeepSeek geschickt wird, läuft er durch `_scrub_pii(text)` (Zeile 152).
- `_scrub_pii()` (Zeile 20–27) ersetzt E-Mail-Adressen, IBANs und **Telefonnummern** per Regex
  durch die Platzhalter `[EMAIL]`, `[IBAN]`, `[TELEFON]` — bewusst als DSGVO-Schutz, damit keine
  personenbezogenen Daten an die externe KI-API (DeepSeek) übertragen werden.
- Die KI bekommt also nie die echte Nummer zu sehen, sondern nur den Platzhalter, und gibt ihn
  (leicht anders formatiert, "(Telefonnummer)") im umgeschriebenen Text zurück. Es gibt keinen
  Mechanismus, der den Original-Wert nach dem KI-Aufruf wieder einsetzt.
- Das ist **by design** (Datenschutzmaßnahme), keine Fehlfunktion — betrifft aber strukturell
  **jeden** Nutzer, der eine Telefonnummer in den Text schreibt und danach die KI-Umschreiben-
  Funktion auf denselben Text anwendet. Kein Einzelfall, sondern eine Eigenschaft der Funktion
  selbst.

**Dringlichkeit:** Mittel
Kein Datenverlust, keine Blockade (Workaround: Nummer nach dem Umschreiben manuell wieder
eintragen) und kein DSGVO-Risiko — im Gegenteil, das Verhalten *ist* die DSGVO-Schutzmaßnahme.
"Mittel" statt "Niedrig", weil es jeden Nutzer der KI-Funktion mit Telefonnummern im Text trifft
(Kernfunktion E-Mail-Kommunikation) und für den Kunden wie ein Datenverlust-Bug wirkt, obwohl es
keiner ist — das kostet wiederkehrend Zeit und Vertrauen in die KI-Funktion.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für den Hinweis. Das ist tatsächlich kein Fehler, sondern eine bewusste
> Datenschutz-Maßnahme: Bevor ein Text an unsere KI zur Überarbeitung geschickt wird, entfernen
> wir automatisch personenbezogene Daten wie Telefonnummern, E-Mail-Adressen und IBANs, damit
> diese nicht an den externen KI-Dienst übertragen werden. Deshalb erscheint an der Stelle der
> Nummer der Platzhalter "(Telefonnummer)", und Sie müssen die Nummer nach dem Umschreiben noch
> einmal von Hand eintragen. Wir nehmen den Wunsch auf, das komfortabler zu gestalten (z. B. die
> Nummer nach dem Umschreiben automatisch wieder einzusetzen), können aber noch keinen Zeitpunkt
> dafür nennen.

**Rückfragen-Guidance:** Keine — die Ursache ist über den Code eindeutig geklärt, keine weiteren
Informationen vom Kunden nötig für die Einstufung. Für eine mögliche Umsetzung (automatisches
Wiedereinsetzen der Original-Werte nach dem KI-Aufruf, per Platzhalter-Mapping) wäre der nächste
Schritt `/abc-requirements` im `immo-crm`-Projekt, nicht Teil dieser Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine
Verbesserung ("Original-PII nach KI-Umschreiben automatisch wieder einsetzen") — kein klassischer
Bug-Fix, sondern ein UX-Feature auf einer bewussten Datenschutz-Maßnahme.
