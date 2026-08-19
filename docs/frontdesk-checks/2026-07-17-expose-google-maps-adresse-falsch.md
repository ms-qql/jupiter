# Frontdesk-Triage — 2026-07-17

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #131 und #130)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint c4c9a974 (Freshdesk #131) — "Adresse für Exposé falsche" | Übergreifendes Problem (mutmaßlicher Bug) | Mittel |
| Peppermint 1a1fa85d (Freshdesk #130) — "Exposé unprofessionel" (Dokumentgröße + Kartenposition) | Übergreifendes Problem (mutmaßlicher Bug, 2 Teilbefunde) | Mittel |

---

### Ticket: "Adresse für Exposé falsche" (Peppermint c4c9a974-30c7-4050-a284-801c7817db3f, Freshdesk #131)

**Kernaussage des Kunden:** Bei einer Doppelhaushälfte "Heinrich Grube Weg 41, 27476" wird die
Lagebeschreibung/Karte im Exposé trotz korrekt eingegebener Adresse (mit Straße) erneut ("schon
wieder heute") falsch angezeigt. Interne Notiz im Ticket behauptet einen Fallback auf
"Dorfstrasse 90", falls die Adresse nicht erkannt wird — Herkunft dieser Notiz unklar, siehe
Rückfragen.

**Kurzbefund:** Vermutlich echter, strukturell wiederkehrbarer Bug in der Kartenanzeige des
Exposés. Der Kunde spricht von "Google Maps", tatsächlich nutzt das System OpenStreetMap/Nominatim
(Begriffsverwechslung des Kunden, technisch aber irrelevant für die Einordnung).

**Eingrenzung:** Backend · Modul: Exposé-Kartenanzeige (`immo-crm`)
Code-Grep-Befund:
- `backend/app/routes/expose.py:963-999` — bei gesetzter `show_address` wird die volle Adresse
  (Straße + Hausnummer + PLZ + Ort) als `map_query` an `_geocode()` gegeben
  (`backend/app/routes/expose.py:284-303`), das synchron gegen die öffentliche
  Nominatim-API (`nominatim.openstreetmap.org`) auflöst.
- Schlägt die Geocodierung der vollen Adresse fehl, greift ein **stiller Fallback** auf
  `PLZ + Ort` (Zeile 989-994) — liefert dann nur noch einen groben Punkt im Ortszentrum statt der
  echten Straße, mit niedrigerem Zoom (12 statt 15). Dieser Fallback wird dem Kunden **nicht als
  Unsicherheit markiert** — das Exposé zeigt einfach eine (falsche) Position, ohne Hinweis, dass
  die genaue Adresse nicht gefunden wurde.
- Ein hartcodierter Fallback auf "Dorfstraße 90" o.ä. wurde im Code **nicht** gefunden; die
  einzigen Treffer für "Dorfstraße" im Repo sind unabhängige Beispiele in
  `import_export.py` (Kommentar) und `email_service.py`/Tests (IMAP-Ordnernamen-Encoding) — kein
  Bezug zur Kartenlogik.
- Nominatim ist eine öffentliche, unzuverlässige Geocoding-Quelle ohne Adress-Vollabdeckung
  (insb. bei ländlichen/neueren Straßen oder Schreibweise-Varianten wie "Heinrich Grube Weg" vs.
  "Heinrich-Grube-Weg"). Der Mechanismus (Geocoding schlägt fehl → ungenauer, unmarkierter
  Fallback) würde bei **jeder** Adresse mit vergleichbarem Nominatim-Coverage-Problem genauso
  zuschlagen — daher übergreifend, nicht objektspezifisch, auch wenn aktuell nur eine Meldung
  vorliegt.

**Dringlichkeit:** Mittel
Begründung: Kein Datenverlust, keine DSGVO-Relevanz, keine Blockade der Arbeit — aber die
Lagekarte ist kundenfacing im Exposé (Standort ist ein zentrales Entscheidungskriterium für
Käufer/Mieter), der Fehler ist laut Kunde wiederkehrend ("schon wieder"), und es gibt für den
Kunden selbst keinen Workaround (nur intern behebbar, z. B. Adress-Schreibweise anpassen oder
Fallback-Verhalten korrigieren/kennzeichnen).

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für den Hinweis. Wir prüfen die Kartendarstellung für "Heinrich Grube Weg 41,
> 27476" und schauen uns an, warum die Straße dort nicht korrekt übernommen wird. Bitte haben Sie
> kurz Geduld — wir melden uns, sobald wir die Ursache gefunden bzw. behoben haben.

**Rückfragen-Guidance:**
- Genauer Stadtname/Objekt-Datensatz zur PLZ 27476 fehlt im Ticket (nur PLZ genannt) — für eine
  gezielte Reproduktion wäre die Objekt-ID oder der vollständige Orts-/Straßenname hilfreich.
- Unklar, woher die interne Notiz "Standardmäßig wird Dorfstrasse 90 verwendet" stammt — im Code
  nicht auffindbar; könnte eine Verwechslung mit einem früheren, mündlich weitergegebenen
  Sachverhalt sein oder sich auf ein anderes System beziehen. Für die Root-Cause-Analyse (`/abc-backoffice`)
  lohnt sich eine Rückfrage, wo diese Notiz herkommt.
- Nicht angegeben, ob das Problem bei diesem einen Objekt reproduzierbar bleibt (z. B. nach
  erneutem Speichern) oder ob es jedes Mal wechselt.

---

Nächster Schritt bei Bedarf: `/abc-backoffice` im `immo-crm`-Projekt zur Root-Cause-Analyse des
Geocoding-Fallbacks (`backend/app/routes/expose.py:284-303` und `963-999`) — insbesondere ob der
Fallback dem Kunden sichtbar markiert werden sollte, statt eine falsche Position stillschweigend
anzuzeigen.

---

### Ticket: "Exposé unprofessionel" (Peppermint 1a1fa85d-cb05-48d2-aa04-78ac74bd4e26, Freshdesk #130, Absender: Firat Erol / Erol Immobilien GmbH, weitergeleitet von Manfred)

**Kernaussage des Kunden:** Bei einer neu angelegten Immobilie (Exposé bereits dem Eigentümer zur
Freigabe geschickt) sind zwei Beobachtungen vermischt: (1) die im Exposé eingebundenen Dokumente
werden viel zu groß dargestellt, wirken dadurch unprofessionell; (2) die Immobilie wird auf
"Google Maps" (tatsächlich OpenStreetMap/Nominatim, siehe Ticket #131 oben) an einer völlig
anderen Stelle angezeigt als die hinterlegte Adresse. Kein Datum, keine Objekt-ID, kein konkreter
Straßenname genannt. Der Kunde formuliert zusätzlich generelle Unzufriedenheit mit Basisfunktionen
— das ist Tonfall/Kontext, keine dritte separate technische Beobachtung.

**Kurzbefund:** Zwei vermutlich echte, strukturell wiederkehrbare Bugs im Exposé-PDF, kein
Benutzerfehler.

**Teilbefund A — Kartenposition falsch:** identischer Mechanismus wie Ticket #131 direkt oberhalb
in dieser Datei (Geocoding-Fallback in `backend/app/routes/expose.py:284-303` und `963-999`) —
selbes Ticket-Cluster, keine erneute Eingrenzung nötig, siehe dort.

**Teilbefund B — Dokumente zu groß:** Code-Grep in `backend/app/routes/expose.py:2247-2306`
(`generate_expose_pdf`) zeigt: eingebundene Bild-Dokumente laufen durch das Template
`expose_pdf.html` und sind dort sauber begrenzt (`.doc-page img { max-width:100%; max-height:700px
}`, Zeilen 395-399) — das ist vermutlich nicht die Fehlerquelle. PDF-Dokumente (z. B.
Energieausweis, Grundriss-Scan) werden dagegen NICHT über das Template gerendert, sondern per
`pypdf.PdfWriter`/`PdfReader` seitenweise roh in das fertige Exposé gemerged (Zeilen 2299-2306),
ohne Angleichung von Seitengröße/Skalierung an das A4-Format der übrigen Exposé-Seiten. Hat das
angehängte PDF ein anderes Seitenformat/eine andere Auflösung als die generierten Exposé-Seiten
(z. B. gescannter Energieausweis, Grundriss in A3), wirkt dieser Abschnitt beim Durchblättern
"zu groß" — passt exakt zur Kundenbeschreibung. Das im Ticket angehängte Beispiel-PDF
("Exposé Einfamilienhaus - Abriss oder Sanierung...") wurde nicht geöffnet (Freshdesk-Anhang,
kein Zugriff ohne Login) — Einschätzung beruht auf Code-Analyse, nicht auf visueller Prüfung des
konkreten Falls.

**Eingrenzung:** Backend · Modul: Exposé-PDF-Generierung (`immo-crm`)
- Teilbefund A: `backend/app/routes/expose.py:284-303`, `963-999` (siehe Ticket #131).
- Teilbefund B: `backend/app/routes/expose.py:2299-2306` (PDF-Merge ohne Seiten-Normalisierung).
- Der Mechanismus (rohes Seiten-Merge ohne Skalierung) würde bei jedem Mandanten zuschlagen, der
  ein PDF-Dokument mit abweichendem Seitenformat anhängt — strukturell übergreifend, auch wenn
  bisher nur dieses eine Ticket vorliegt.

**Dringlichkeit:** Mittel
Begründung: kein Datenverlust, keine DSGVO-Relevanz, keine Arbeitsblockade — aber das Exposé ist
das zentrale kundenfacing Verkaufsdokument (geht an Eigentümer zur Freigabe UND an Interessenten),
beide Symptome zusammen lassen das Produkt laut Kunde "unprofessionell" wirken, und es gibt aus
Kundensicht keinen Workaround. Kein Einzelfall, da beide Teilbefunde strukturell sind.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für die ausführliche Rückmeldung. Wir nehmen beide Punkte ernst und sehen sie uns
> gezielt an: die Darstellung der eingebundenen Dokumente im Exposé sowie die Kartenposition, die
> von der hinterlegten Adresse abweicht. Beides melden wir intern zur Behebung und geben Ihnen
> Bescheid, sobald wir mehr dazu sagen können. Für eine schnellere Reproduktion wäre es hilfreich,
> wenn Sie uns die konkrete Immobilie (Adresse oder Objekt-Link) sowie kurz nennen könnten, welches
> der angehängten Dokumente (z. B. Energieausweis, Grundriss) besonders groß dargestellt wurde.

**Rückfragen-Guidance:**
- Keine Objekt-ID/Adresse für den Dokumentgrößen-Fall genannt (nur für den Karten-Fall in Ticket
  #131 bekannt: "Heinrich Grube Weg 41, 27476") — unklar, ob beide Symptome dasselbe Objekt
  betreffen oder zwei verschiedene.
- Nicht genannt, welches konkrete Dokument (Typ, Dateiformat) zu groß dargestellt wurde — wichtig,
  um Teilbefund B zu verifizieren (Bild-Dokument vs. PDF-Dokument sind zwei unterschiedliche
  Code-Pfade, siehe oben).
- Kein Screenshot/Auszug aus dem gerenderten Exposé-PDF beigefügt, nur der externe
  Freshdesk-Anhang (nicht abrufbar ohne Login) — für eine visuelle Bestätigung wäre ein Screenshot
  der betroffenen Seite hilfreich.

---

Nächster Schritt bei Bedarf: `/abc-backoffice` im `immo-crm`-Projekt — Teilbefund A gemeinsam mit
Ticket #131 behandeln (gleicher Fallback-Mechanismus); Teilbefund B separat: Seiten-Normalisierung
beim PDF-Merge in `generate_expose_pdf` (`backend/app/routes/expose.py:2299-2306`), z. B. Zielgröße
auf A4 skalieren statt Originalseiten unverändert zu übernehmen.
