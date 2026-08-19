# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #140,
Peppermint-ID c0d0dc8a-c7a6-499e-8154-9ec63a7da802)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint c0d0dc8a-c7a6-499e-8154-9ec63a7da802 (Freshdesk #140) — "Lange Überschriften" | Übergreifendes Problem (Text-Overflow im PDF-Deckblatt) | Mittel |

---

### Ticket: "ImmoCheck - Lange Überschriften" (Peppermint c0d0dc8a-c7a6-499e-8154-9ec63a7da802, Freshdesk #140)

**Kernaussage des Kunden:** "Lange Überschriften im Exposé gehen verdecken das Logo und gehen
über die Seite hinaus, so dass man die Überschrift am Ende nicht weiter lesen kann." Kein Datum,
kein konkretes Objekt/Exposé genannt, kein Screenshot.

**Kurzbefund:** Vermutlich echter Anzeigefehler, keine Fehlbedienung. Code-Grep im Projekt
`immo-check` (nicht `jupiter` — Exposé-Code liegt dort) zeigt eine plausible technische Ursache.

**Eingrenzung:** Frontend · Modul: Expose-PDF-Export, Deckblatt (`immo-check`).
Code-Grep-Befund:
- `flutter_app/lib/features/expose/data/expose_pdf_builder.dart:172-175` — `variante.titel` wird
  als `pw.Text` mit `fontSize: 26, fontWeight: bold` direkt in die Deckblatt-`pw.Column` gerendert,
  ohne `maxLines`/`overflow`-Begrenzung.
- Zeile 166-170 direkt darüber: der Mandantenname (bzw. Textlogo `'ImmoCheck'`, falls kein
  Mandant hinterlegt) steht in derselben `pw.Column`, nur durch `pw.SizedBox(height: 24)` getrennt
  — kein tatsächliches Bild-Logo im Code gefunden (`grep -i logo` liefert nur diesen einen
  Kommentar), das Kunden-"Logo" ist also aktuell der Textblock mit dem Mandantennamen.
- Das `pdf`-Package (`pw.Text`) bricht Zeilen nur an Wortgrenzen um; ein einzelnes sehr langes Wort
  (z. B. ein langer deutscher Kompositum-Titel ohne Leerzeichen) wird nicht getrennt und kann über
  die Container-/Seitenbreite hinauslaufen — das erklärt exakt "geht über die Seite hinaus, am
  Ende nicht mehr lesbar". Läuft der Titel durch den Overflow zusätzlich in der Höhe/Breite in den
  Bereich des Mandantennamens, erklärt das die "verdeckt das Logo"-Beobachtung.
- Nicht live geprüft (kein PDF mit Testdaten gerendert) — Einschätzung basiert auf Code-Analyse.

**Warum übergreifend statt Einzelfall:** Die auslösende Vorbedingung ("Exposé-Titel ist länger als
die verfügbare Deckblattbreite bzw. enthält ein langes zusammenhängendes Wort") ist rein
layoutbedingt und unabhängig vom konkreten Mandanten/Objekt — jeder Nutzer mit einem längeren Titel
würde denselben Effekt bekommen.

**Bekanntes Cluster:** Kein bestehender Feature-/Bug-Eintrag zu diesem Overflow gefunden (weder in
`immo-check/features/INDEX.md`, `PROJ-31-expose-titel-werteinschaetzung.md`,
`PROJ-32-expose-layout-deckblatt-und-schluss.md`, noch in bisherigen Frontdesk-Checks).

**Dringlichkeit:** Mittel
Begründung: Kernfunktion (Exposé, das Kernprodukt) betroffen, übergreifend (jeder mit langem Titel
trifft es), kein Datenverlust-/Integritätsrisiko, keine DSGVO-Relevanz, Kunde nicht blockiert (PDF
weiterhin nutzbar, aber Titel teils unlesbar/unprofessionell) — daher über "Niedrig" (rein
kosmetisch bei generischem Layout), aber unter "Hoch" (kein Blocker). Freshdesk-Priorität "low"
wirkt hier etwas zu niedrig angesetzt, da es die Kernfunktion sichtbar/dauerhaft betrifft.

**Antwortentwurf an den Kunden:**
> Vielen Dank für den Hinweis. Wir haben uns das Deckblatt im Exposé angesehen: Bei sehr langen
> Überschriften kann der Text aktuell über den vorgesehenen Bereich hinauslaufen, statt korrekt
> umzubrechen oder verkleinert zu werden — das ist kein Einzelfall, sondern ein layoutbedingtes
> Verhalten, das wir beheben werden. Wir melden uns, sobald die Anpassung umgesetzt ist.

**Rückfragen-Guidance:** Kein Screenshot und kein konkretes Objekt/Exposé genannt, an dem der
Kunde das Problem gesehen hat. Für die Umsetzung nicht zwingend nötig (Ursache über Code-Grep
plausibel), aber ein Screenshot und der exakte Titel-Text würden helfen zu bestätigen, ob es sich
um ein einzelnes sehr langes Wort (kein Wortumbruch möglich) oder generell um viele Wörter/eine
lange Zeile handelt — das würde den passenden Fix (Wortumbruch/Hyphenation vs. Schriftgröße
skalieren vs. `maxLines`+Ellipsis) eingrenzen.

---

Nächster Schritt bei Bedarf: kleiner Layout-Fix im `immo-check`-Projekt
(`flutter_app/lib/features/expose/data/expose_pdf_builder.dart:172-175`, z. B. Schriftgröße bei
langen Titeln automatisch verkleinern oder `overflow`/Zeilenumbruch-Verhalten explizit setzen) —
Bugfix-Ticket, kein neues Feature. Da der Code in `immo-check` liegt, nicht in `jupiter`, müsste
der Fix dort eingeplant werden.
