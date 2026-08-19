# Frontdesk-Triage — 2026-07-10

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #122, Peppermint-ID 4643d1e8-ce14-41a5-b94b-d52e609c4d78)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 4643d1e8 (Freshdesk #122) — "Fehlermeldung bei Kunden wenn wir manuell die DSGVO Bestätigen" | Übergreifendes Problem: manuelles Setzen von AGB-/DSGVO-Zustimmung schlägt bei bestimmten Kundendatensätzen fehl (vermutlich fehlende/doppelt vergebene E-Mail-Adresse) | Hoch |
| Peppermint e3f06ae1 (Freshdesk #126) — "Immo-crm Fehlermeldung DSGVO" | Vermutliches Duplikat/Folge-Notification desselben Falls (Familie Herbst) — identische Ursachen-Hypothese | Hoch |

---

### Ticket: "Fehlermeldung bei Kunden wenn wir manuell die DSGVO Bestätigen" (Peppermint 4643d1e8-ce14-41a5-b94b-d52e609c4d78, Freshdesk #122, Absender: Firat Erol / Erol Immobilien GmbH, adressiert an "Manfred")

**Kernfakten aus dem Ticket:**
- Melder: Firat Erol (Inhaber/GF Erol Immobilien GmbH), meldet für sich selbst als Nutzer des CRM.
- Betroffener Datensatz: Kunde "Familie Herbst" (älteres Ehepaar, hat Makleraufrag erteilt).
- Aktion: AGB und DSGVO im Kundendatensatz manuell auf "akzeptiert" stellen und speichern (Zustimmung wurde nicht online, sondern mündlich/schriftlich gegeben und soll nachträglich im System erfasst werden).
- Beobachtung: Beim Speichern erscheint eine Fehlermeldung (Wortlaut nicht mitgeteilt).
- Kein Datum/Uhrzeit, kein Screenshot, kein exakter Fehlertext im Ticket enthalten.

**Kurzbefund:** Übergreifendes Problem — die auslösende Vorbedingung (älterer Bestandskunde ohne hinterlegte E-Mail-Adresse, bzw. Ehepaar/mehrere Kontaktpersonen an einem Kundendatensatz) ist keine Anomalie, sondern ein strukturell wiederkehrender Fall bei diesem Kundentyp. Ein zweiter vergleichbarer Kunde (älteres Ehepaar, Bestandskunde ohne E-Mail) würde mit hoher Wahrscheinlichkeit dasselbe Symptom auslösen.

**Eingrenzung:** Schicht: Frontend-Validierung + Backend-Datenmodell · Modul: Kundenverwaltung / Consent (`immo-crm`-Repo, `/home/dev/projects/immo-crm`).

Code-Grep-Befund (Recherche im tatsächlichen Produkt-Repo `immo-crm`, nicht im Jupiter-Repo selbst — Jupiter enthält kein CRM):
- UI: `lib/features/clients/models/client_form_config.dart:138-171` definiert die Consent-Dropdowns (`gdprConsent`, `agbConsent`, u.a.); bearbeitet über den 6-Schritte-Assistenten in `lib/features/clients/client_form_screen.dart` (Speichern: `_saveClient()`, Zeile 1238-1289). Anzeige im Kundendetail: `client_detail_screen.dart:666-724`.
- Backend: `PUT /api/clients/{client_id}` → `update_client()` in `backend/app/main.py:6233-6322`. Consent-Felder sind einfache `TEXT`-Spalten (Default `'Nein'`), kein Zeitstempel/Nachweis-Feld für manuell nachgetragene Zustimmungen — Speichern läuft als vollständiges Form-Resubmit, nicht als gezieltes Consent-Update.
- **Kandidat A (wahrscheinlichste Ursache):** `email` ist im Formular als Pflichtfeld markiert (`client_form_config.dart:84-88`). Fehlt bei einem älteren Bestandskunden wie "Familie Herbst" eine hinterlegte E-Mail-Adresse, schlägt die Schritt-Validierung fehl → das komplette Speichern (inkl. der Consent-Änderung) wird blockiert, unabhängig davon, dass nur AGB/DSGVO geändert werden sollten.
- **Kandidat B:** E-Mail-Eindeutigkeits-Constraint (`main.py:6330-6346`, `6562-6620`) — wenn dieselbe E-Mail bereits einem anderen Kundendatensatz zugeordnet ist (z. B. weil für die Eheleute zwei separate Datensätze mit identischer Adresse angelegt wurden), schlägt das Speichern mit einer Konflikt-Fehlermeldung fehl. Das System kennt laut `features/PROJ-42-multi-email-per-client.md` bisher kein Konzept für zwei Kontaktpersonen an einem Kundendatensatz — passt zur Ehepaar-Konstellation im Ticket.
- Bekannter Cluster: `features/PROJ-42-multi-email-per-client.md` (E-Mail-Eindeutigkeit als strukturelle Ursache für Kandidat B) und `features/PROJ-100-provision-consent-reconciliation-hotfix.md` (bereits behobener, verwandter Consent-Bug beim automatischen Übernehmen aus dem Web-Exposé-Formular — zeigt, dass der Consent-Bereich schon einmal Nacharbeit brauchte).
- Anleitung vorhanden, aber lückenhaft: `docs/customer-journeys/PROJ-100-zustimmungen-nachtragen.md` beschreibt den vom Mitarbeiter gegangenen Weg (Bearbeiten → Dropdowns → Speichern), enthält aber keinen Hinweis auf diese Fehlerfälle.

**Dringlichkeit:** Hoch
Begründung: DSGVO-Zustimmungen sind rechtlich relevant (Nachweispflicht bei Einwilligungen) — wenn das Nachtragen der Zustimmung strukturell blockiert ist, kann der Kunde diese Pflichtdokumentation für betroffene Bestandskunden gar nicht erfassen. Der Mitarbeiter ist bei einer Kernfunktion (Kundenstammdaten/Consent) aktuell blockiert, nicht nur gestört, und die Vorbedingung (ältere Bestandskunden ohne E-Mail bzw. Ehepaar-Konstellation) dürfte bei mehreren Kunden vorkommen, nicht nur bei "Familie Herbst". Freshdesk hatte "low" gesetzt — das passt eher zum unaufgeregten Tonfall des Tickets als zum tatsächlichen Compliance-/Blockade-Risiko.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für die Rückmeldung. Wir prüfen aktuell, woran es liegt, dass beim manuellen Bestätigen der AGB-/DSGVO-Zustimmung bei Familie Herbst eine Fehlermeldung erscheint. Eine mögliche Ursache ist, dass für diesen Kundendatensatz keine E-Mail-Adresse hinterlegt ist oder dieselbe E-Mail-Adresse bereits einem anderen Kundendatensatz zugeordnet ist — beides kann bei älteren Bestandskunden bzw. bei Ehepaaren mit zwei Ansprechpartnern vorkommen. Wir melden uns, sobald wir die genaue Ursache bestätigt haben.
>
> Könnten Sie uns bis dahin kurz mitteilen, ob für Familie Herbst bereits eine E-Mail-Adresse im System hinterlegt ist, und uns den genauen Wortlaut der Fehlermeldung schicken (z. B. als Screenshot)? Das hilft uns bei der weiteren Eingrenzung.
>
> Viele Grüße

**Rückfragen-Guidance:** Genauer Wortlaut/Screenshot der Fehlermeldung; ob für "Familie Herbst" eine E-Mail-Adresse hinterlegt ist; ob evtl. zwei getrennte Kundendatensätze für die Eheleute existieren (z. B. je ein Datensatz pro Person mit gleicher E-Mail); genaue Uhrzeit des Versuchs; ob der Fehler reproduzierbar ist (nochmal versucht?).

---

**Nächster Schritt:** Da es sich um ein strukturelles, vermutlich wiederkehrendes Problem mit DSGVO-Bezug handelt, empfiehlt sich ein vollständiger `/abc-qa`-Lauf im `immo-crm`-Repo (Reproduktion mit Testkunde ohne E-Mail bzw. Ehepaar-Konstellation, Abgleich mit PROJ-42) statt einer reinen Vor-Triage-Einschätzung.

---

### Ticket: "Immo-crm Fehlermeldung DSGVO" (Peppermint e3f06ae1-bb5f-44c2-b68b-51d86abe5f8c, Freshdesk #126, Absender: Auxevo Support / Freshdesk-Weiterleitung, "needs_support", Priorität lt. Freshdesk: low)

**Kernfakten aus dem Ticket:**
- Betroffener Datensatz: Kunde "Familie Herbst" (älteres Ehepaar, hat Makleraufrag erteilt) — identisch zum oben dokumentierten Fall.
- Aktion: AGB und DSGVO im Kundendatensatz manuell auf "akzeptiert" stellen und speichern, weil die Zustimmung mündlich erteilt und manuell nacherfasst werden soll — wortgleich zur Beschreibung in Freshdesk #122.
- Beobachtung: Fehlermeldung beim Speichern (Wortlaut wieder nicht mitgeteilt).
- Kein Datum/Uhrzeit, kein Screenshot, kein exakter Fehlertext.

**Kurzbefund:** Sehr wahrscheinlich dasselbe zugrunde liegende Problem wie Freshdesk #122 (oben) — andere Freshdesk-Ticketnummer (#126 statt #122) und andere Peppermint-ID, aber identischer Kunde, identisches Symptom, nahezu identischer Text. Denkbare Erklärungen: (a) Freshdesk hat eine neue Ticketnummer beim erneuten Versuch/Antwortenden erzeugt, (b) der Mitarbeiter hat es ein zweites Mal probiert und erneut dieselbe Fehlermeldung erhalten (würde die Übergreifend-Einstufung zusätzlich stützen, da nicht einmalig), oder (c) ein Weiterleitungs-/Notification-Duplikat. Ohne Zugriff auf das Peppermint-/Freshdesk-Threading lässt sich das nicht abschließend klären — für die technische Einschätzung ändert das aber nichts an der bereits dokumentierten Analyse (Kandidat A: Pflichtfeld E-Mail blockiert kompletten Save inkl. Consent-Änderung; Kandidat B: E-Mail-Eindeutigkeits-Konflikt bei zwei Kontaktpersonen/Ehepaar).

**Eingrenzung:** identisch zu oben — Frontend-Validierung + Backend-Datenmodell · Modul: Kundenverwaltung/Consent (`immo-crm`-Repo). Codefundstellen: `lib/features/clients/models/client_form_config.dart:84-88` (E-Mail als Pflichtfeld `required: true`) und `:138-171` (Consent-Dropdowns), `lib/features/clients/client_form_screen.dart:1238-1292` (`_saveClient`), `backend/app/main.py:6216-6322` (`update_client`, inkl. E-Mail-Alias-Konfliktprüfung).

**Dringlichkeit:** Hoch
Begründung: siehe Ticket #122 oben (DSGVO-Nachweispflicht blockiert, Kernfunktion betroffen). Dass derselbe Fall offenbar ein zweites Mal als Ticket hereinkommt, ist ein zusätzliches Indiz, dass der Mitarbeiter weiterhin blockiert ist bzw. die erste Rückmeldung ihn noch nicht erreicht/gelöst hat.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Nachricht — das betrifft denselben Fall (Familie Herbst, AGB-/DSGVO-Zustimmung manuell nachtragen), den Sie uns bereits gemeldet hatten. Wir sind aktuell dabei, die genaue Ursache zu prüfen und melden uns mit einer Lösung, sobald wir sie bestätigt haben. Falls Sie es zwischenzeitlich erneut versucht haben: Ist die Fehlermeldung weiterhin dieselbe, oder hat sich etwas geändert? Ein Screenshot der genauen Meldung würde uns sehr helfen.
>
> Viele Grüße

**Rückfragen-Guidance:** Ist dies dieselbe Meldung wie Freshdesk #122 oder ein neuer/wiederholter Versuch? Genauer Wortlaut/Screenshot der Fehlermeldung; ob für "Familie Herbst" eine E-Mail-Adresse hinterlegt ist; ob zwei getrennte Kundendatensätze für die Eheleute existieren.

---

**Gesamteinschätzung beider Tickets:** Beide Meldungen sollten im Support-System als ein Fall zusammengeführt werden (Duplikat-Verdacht), bevor eine Antwort verschickt wird — doppelte, leicht unterschiedliche Antworten an denselben Kunden wirken unprofessionell.

---

## Update 2026-07-10 (zu Peppermint e3f06ae1-bb5f-44c2-b68b-51d86abe5f8c, Freshdesk #126): Ursache bestätigt & Fix implementiert

Statt eines vollen `/abc-qa`-Laufs wurde die Ursache direkt im `immo-crm`-Repo (`/home/dev/projects/immo-crm`) am Code verifiziert (kein Testkunde in echter DB nötig — Bug reproduzierbar durch Codelesen + Unit-Test).

**Bestätigte Ursache (Kandidat A, präzisiert):** Nicht das Pflichtfeld `email` im Frontend blockiert, sondern eine **Asymmetrie im Backend** zwischen Create und Update:
- `POST /api/clients/submit` (Neuanlage) fängt ein Formatproblem der E-Mail beim Alias-Sync tolerant ab (`except HTTPException: new_email_validated = None`, `backend/app/main.py` ~Zeile 5805-5809) und speichert den Kunden trotzdem.
- `PUT /api/clients/{client_id}` (`update_client`, Bearbeiten bestehender Kunden — genau der Pfad, den der Mitarbeiter für "Familie Herbst" nutzt) hatte diese Toleranz **nicht**: `_validate_alias_email_42()` warf bei jedem nicht strikt validen Einzel-Adress-Format (Legacy-Platzhaltertext, zwei E-Mail-Adressen für ein Ehepaar in einem Feld, o.ä.) einen HTTP 422 „E-Mail-Adresse ist ungültig.", der ungefangen den **kompletten Save blockierte** — inklusive der eigentlich beabsichtigten, komplett unabhängigen AGB-/DSGVO-Änderung.

**Fix:** `backend/app/main.py:6313-6376` (`update_client`) — die `_validate_alias_email_42`-Validierung wurde in ein eigenes `try/except HTTPException` gewrappt, analog zum Create-Pfad. Bei Formatfehlern wird nur die Alias-Synchronisation übersprungen, der restliche Kundendatensatz (inkl. Consent-Felder) wird normal gespeichert. Echte 409-Konflikte (E-Mail bereits einem anderen Kunden zugeordnet) bleiben weiterhin hart, da das ein echtes Datenintegritätsproblem ist.

**Verifikation:**
- Neuer Regressionstest `backend/tests/unit/test_update_client_invalid_email_consent.py` — per Stash/Revert bestätigt: Test ist ohne den Fix rot, mit Fix grün.
- Gesamte Unit-Suite (`backend/tests/unit/`): 1234 passed, 1 skipped, 1 xfailed — keine Regression.
- Implementation-Notes im Feature-Spec `features/PROJ-42-multi-email-per-client.md` (Abschnitt „Hotfix (2026-07-10)") ergänzt.

**Status: Deployed (2026-07-10, mit User-Freigabe).**

- Fix erarbeitet auf `dev` (Commit `b772bd7`), da `dev` ~20 Commits hinter `main` lag (kein aktiv bespielter Dev-Host mehr) per Cherry-Pick nach `main` gebracht (`bbb83cc`), Version-Bump v0.8.5 → v0.8.6 (`2944ce1`), Deployment-Vermerk in der Feature-Spec (`8be4e48`).
- Gepusht nach `origin/main` → Dokploy Auto-Deploy-Webhook ausgelöst. Tag `v0.8.6-PROJ-42-hotfix` gesetzt und gepusht.
- Backend-Health-Check nach Push: `https://crm.erol.msce.info/health` → `{"status":"ok"}`, HTTP 200.
- **Noch offen (nicht headless prüfbar):** Bestätigung, dass der neue Build tatsächlich live ist (Dokploy-Deployments-Log grün) + funktionaler Browser-Test — bei "Familie Herbst" (oder einem Testkunden mit ähnlich unsauberem E-Mail-Feld) AGB/DSGVO manuell setzen und speichern, jetzt ohne Fehlermeldung.
- Feature-Spec `features/PROJ-42-multi-email-per-client.md` im `immo-crm`-Repo enthält vollständige Fix- + Deployment-Dokumentation.

**Nächster konkreter Schritt:** Funktionalen Smoke-Test im Browser gegen `crm.erol.msce.info` durchführen (Familie Herbst, AGB/DSGVO setzen + speichern). Danach Support-Antwort an Herrn Erol: „Ursache gefunden und behoben, bitte erneut versuchen" statt des bisherigen Platzhalter-Antwortentwurfs.
