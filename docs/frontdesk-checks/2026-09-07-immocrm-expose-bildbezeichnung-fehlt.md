# Frontdesk-Check — 2026-09-07 — Exposé: Bild-Bezeichnungen fehlen im PDF ("Bild 1 / Bild 2" statt Raumname)

**Quelle:** Peppermint-Ticket a4be665e-948e-464a-b62c-6fbff7867fd9 (Freshdesk #159),
weitergeleitet über Auxevo Support. Melderin: B. Rutkowska (`b.rutkowska@erolimmobilien.de`),
Erol Immobilien. Mandant `00000000-0000-0000-0000-000000000001` (Demo-/Test-Mandant),
Anfrage-ID `d6bc5b78-c2a6-4e3b-9eda-a06aa5431a30`. Softwareversion v0.14.3.
Interne Ersteinschätzung, **kein QA-Ergebnis**. Reproduktion nur per Code-Analyse im
`immo-crm`-Projekt, nicht live nachgestellt (kein Zugriff auf echte Kundendaten ohne Freigabe).

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Exposé-PDF zeigt unter den Fotos nur "Bild 1 / Bild 2" statt der eingegebenen Bezeichnung (z. B. Kinderzimmer, Küche) | Übergreifendes Problem | Mittel |

---

### Ticket: Bezeichnung der Bilder erscheint nicht im Exposé — es steht auf jeder Seite nur "Bild 1" / "Bild 2"

**Kernfakten aus dem Ticket:**
- Melderin: B. Rutkowska (Erol Immobilien), schreibt an Manfred.
- Beobachtung: Beim Einfügen von Bildern ins Exposé steht die Bezeichnung ("wie z. B.
  Kinderzimmer oder Küche"), die sie eingegeben hat, **nicht unter dem Bild**. Stattdessen
  steht "immer nur Bild 1 und Bild 2 auf jeder Seite".
- Reproduzierbarkeit: laut Ticket **immer**.
- Kein konkretes Objekt, kein Screenshot, keine Angabe **welches** Feld sie befüllt hat
  (Titel / Klassifizierung / Beschreibung) und **welche** Exposé-Ausgabe gemeint ist
  (PDF-Download vs. Web-Exposé).
- "Bereits ausprobiert": nichts angegeben.

**Kurzbefund:** Übergreifendes Problem.
Die auslösende Vorbedingung — "Makler:in vergibt pro Foto eine sprechende Bezeichnung und
erwartet sie im Exposé unter dem Bild" — ist der Normalfall dieser Funktion. Das Foto-Bearbeiten-
Dialogfenster ("Foto bearbeiten", `lib/features/properties/property_form_screen.dart:1554 ff.`)
bietet dafür drei Felder an: **Titel**, **Klassifizierung** (Dropdown: Wohnzimmer/Küche/…) und
**Beschreibung (Exposé-Bildunterschrift)** — Letzteres mit dem Hinweistext *"Optional — wird im
Exposé unter dem Bild angezeigt"*. Genau dieses Versprechen wird von der PDF-Ausgabe nicht
eingelöst; das trifft jede:n Nutzer:in gleichermaßen, nicht nur diesen einen Datensatz.

**Eingrenzung (mutmaßlicher App-Fehler):** Schicht: **Backend** (Jinja-Template der PDF-Erzeugung)
· Modul: **Exposé-System** (PROJ-4 / PROJ-125 / PROJ-124), Server-seitiges PDF.
Stütze der Eingrenzung (nur Code-Analyse):
- Der "Exposé generieren"-Button POSTet an das Backend
  (`propertyExposePdfEndpoint`, `lib/features/properties/expose/expose_generator_screen.dart:549`)
  → das PDF wird server-seitig aus `backend/app/templates/expose_pdf.html` (WeasyPrint) gerendert,
  **nicht** aus dem Flutter-`expose_pdf_builder.dart`.
- Die Foto-Sektion des Templates rendert als Bildunterschrift ausschließlich:
  `{{ img.title or 'Foto ' ~ loop.index }}` (`backend/app/templates/expose_pdf.html:600`).
  → Ist das **Titel**-Feld leer, erscheint der generische Fallback "Foto 1 / Foto 2"
  (vom Ticket als "Bild 1 / Bild 2" wiedergegeben).
- Der Kontext-Builder übergibt pro Bild zwar `title` **und** `beschreibung`
  (`backend/app/routes/expose.py:2324-2328`), aber das Template gibt `img.beschreibung`
  **nirgends** aus. Ebenso wird die **Klassifizierung** ("Küche") im Server-PDF nicht gerendert.
- Damit landet eine im Feld "Beschreibung (Exposé-Bildunterschrift)" oder per Klassifizierungs-
  Dropdown gesetzte Bezeichnung nie im PDF — unabhängig vom Datensatz.
- Zusammenhang mit **PROJ-125** ("Foto-Klassifizierung & Beschreibungen"): Der Flutter-
  PDF-Builder wurde dort um `classification.label` + `title` + `description` erweitert
  (`lib/features/properties/expose/expose_pdf_builder.dart:370-392`), das tatsächlich
  ausgelieferte **Server-Template blieb dabei ungewired** — starker Verdacht auf unvollständige
  Umsetzung / Regression aus PROJ-125.

**Dringlichkeit:** Mittel.
- Kernfunktion betroffen (Exposé-PDF ist ein Hauptartefakt, das an Interessent:innen rausgeht)
  und übergreifend (Mechanismus greift bei jedem Exposé) → spricht für höher.
- Aber: kein Datenverlust, keine DSGVO-/Consent-Relevanz, keine falsche Zuordnung; das PDF wird
  vollständig erzeugt, alle Bilder sind drin. Nutzer ist nicht blockiert, nur gestört.
- Umgehung vorhanden (wenn auch nicht offensichtlich): Bezeichnung ins **Titel**-Feld des Fotos
  eintragen statt/zusätzlich zur "Beschreibung" — `img.title` wird im PDF gerendert.
- In Summe: sichtbarer Qualitätsmangel auf einem Kundendokument, aber ohne Risiko und mit
  Workaround → Mittel.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für Ihre Meldung. Sie haben recht: Im fertigen Exposé-PDF erscheint unter den
> Fotos aktuell nur "Foto 1", "Foto 2" usw., anstatt der Bezeichnung, die Sie zum Bild
> hinterlegt haben. Wir haben die Ursache eingegrenzt und kümmern uns darum, dass die von Ihnen
> vergebene Bild-Bezeichnung wieder unter dem jeweiligen Foto ausgegeben wird.
>
> Bis das behoben ist, ein Zwischenweg: Öffnen Sie am Foto den Dialog "Foto bearbeiten" und
> tragen Sie den Raumnamen (z. B. "Küche", "Kinderzimmer") in das Feld **Titel** ein — dieser
> Text wird im PDF bereits korrekt unter dem Bild angezeigt.
>
> Wir melden uns, sobald die Korrektur ausgeliefert ist.
>
> Freundliche Grüße
> Ihr Support-Team

**Rückfragen-Guidance:** Für dieses Ticket fehlten konkret:
- **Welches Feld** im Dialog "Foto bearbeiten" wurde befüllt — "Titel", "Klassifizierung"
  (Dropdown) oder "Beschreibung (Exposé-Bildunterschrift)"? Entscheidet, ob es reiner
  Template-Fix (Beschreibung/Klassifizierung ergänzen) ist oder zusätzlich das Titel-Feld
  betroffen ist.
- **Welche Exposé-Ausgabe** ist gemeint: das heruntergeladene **PDF**, das **Web-Exposé**
  (Link) oder der ImmoScout-Export? (Analyse bezieht sich auf das PDF.)
- **Screenshot** der betroffenen Exposé-Seite und, wenn möglich, des ausgefüllten
  "Foto bearbeiten"-Dialogs.
- Betroffenes **Objekt** (Objekt-/Property-ID) und ob es mit einem frischen Test-Objekt
  reproduzierbar ist.
- Verwendeter **Browser** und **Softwareversion** zum Zeitpunkt der PDF-Erstellung
  (Ticket nennt v0.14.3 — bitte bestätigen).

**Nächster Schritt (nicht Teil dieses Checks):** Wenn die Rückfrage "Beschreibung/
Klassifizierung wird nicht ins Server-PDF gerendert" bestätigt, ist das ein gezielter
Backend-Fix in `backend/app/templates/expose_pdf.html` (Foto-Sektion um `img.beschreibung`
und ggf. Klassifizierungs-Label erweitern, analog zum Flutter-Builder aus PROJ-125),
anschließend `/abc-qa` im `immo-crm`-Projekt mit Bezug zu PROJ-125 / PROJ-124.
