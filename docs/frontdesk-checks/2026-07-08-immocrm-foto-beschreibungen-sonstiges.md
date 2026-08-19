# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #146)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 8ab283d4 (Freshdesk #146) — "Beschreibungen Fotos" | Übergreifendes Problem, bekannter Cluster (siehe `2026-07-08-immocrm-foto-benennung.md`) | Mittel |

---

### Ticket: Peppermint-Ticket "ImmoCRM - Beschreibungen Fotos" (Peppermint 8ab283d4-e2f8-4c11-bf44-49d47859fa9b, Freshdesk #146, Absender: Auxevo Support/Weiterleitung, zugewiesen an "Pepper Mint")

**Kurzbefund:** Übergreifendes Problem. Meldung: "im Exposé werden nicht alle Beschreibungen bei
den Fotos übernommen, bei einigen steht weiterhin Sonstiges drunter." Kein Datum, kein konkreter
Objekt-/Kundendatensatz genannt.

**Eingrenzung:** Frontend (Flutter) · Modul: Objekt-Bilder / Exposé-Erzeugung (`immo-crm`).

Code-Grep-Befund (Abgleich mit Bekanntem, Schritt 3b):
- Deckt sich mit bereits dokumentiertem Fall `docs/frontdesk-checks/2026-07-08-immocrm-foto-benennung.md`
  (Freshdesk #49): Jedes Foto trägt ein `ImageClassification`-Enum
  (`lib/features/properties/models/property_enums.dart:460-476`) mit fester Werteliste
  (Außenansicht, Wohnzimmer, Schlafzimmer, Küche, Bad, Balkon, Garten, Flur, Keller, Dachboden,
  Garage, `other` → Label "Sonstige"). Im Exposé wird `classification.label` angezeigt, optional
  ergänzt um ein freies `title`-Feld (`expose_pdf_builder.dart:371,380`).
- Neu hochgeladene Fotos werden standardmäßig mit `ImageClassification.other` angelegt
  (`property_form_screen.dart:1378`, `:1450`) — Auswahl der richtigen Kategorie erfolgt manuell pro
  Bild über ein Dropdown (`:1523ff`). Räume, die nicht in der Enum-Liste vorkommen (z. B. laut
  vorherigem Ticket: Abstellraum, Treppenhaus, Waschküche, Ankleidezimmer, Gäste-WC …), lassen sich
  gar nicht korrekt zuordnen und bleiben zwangsläufig auf "Sonstige" stehen, unabhängig davon, ob
  der Nutzer eine Beschreibung im `title`-Feld eingetragen hat.
- Damit ist "bei einigen steht weiterhin Sonstiges drunter" strukturell erklärbar: entweder wurde
  die Klassifizierung für dieses Foto nicht manuell gesetzt (bleibt beim Default), oder der Raumtyp
  existiert schlicht nicht in der Enum-Liste. Das trifft jeden Nutzer mit vergleichbaren Motiven
  (Nebenräume, Sonderräume) gleichermaßen — kein Einzelfall-Datenfehler, sondern derselbe
  Mechanismus wie im bereits gemeldeten Cluster.
- Nicht live geprüft — Einschätzung basiert auf Code-Analyse, kein Zugriff auf das konkrete
  Exposé/den Datensatz aus Ticket #146.

**Dringlichkeit:** Mittel
Kein Datenverlust, kein DSGVO-Bezug, Kunde nicht blockiert (Exposé bleibt nutzbar) — aber
kundensichtbarer Qualitätsmangel im Exposé (Kernprodukt), der wiederholt gemeldet wird (zweites
Ticket zum selben Mechanismus binnen kurzer Zeit) und die Umsetzung des bereits erkannten
Feature-Gaps aus #49 unterstreicht.

**Antwortentwurf an den Kunden:**
> Vielen Dank für den Hinweis. Das hängt mit der aktuellen Foto-Kategorisierung im Exposé
> zusammen: Jedes Bild wird entweder manuell einer Kategorie (z. B. Wohnzimmer, Küche, Bad, Garten
> …) zugeordnet oder erscheint als "Sonstige", solange keine passende Kategorie ausgewählt wurde
> bzw. der Raumtyp noch nicht in unserer Liste enthalten ist. Wir haben das bereits als
> Verbesserung vorgemerkt (Erweiterung der Kategorie-Liste plus Überarbeitung der
> Beschriftungs-Anzeige im Exposé) und melden uns, sobald es umgesetzt ist.

**Rückfragen-Guidance:** Für eine genauere Zuordnung fehlen: welches konkrete Objekt/Exposé
betroffen ist (Objekt-ID statt nur "einige Fotos"), ob die Beschreibungen manuell pro Foto über das
Kategorie-Dropdown gesetzt wurden oder eine automatische Übernahme erwartet wurde, sowie ein
Screenshot des betroffenen Exposé-Ausschnitts.

---

Nächster Schritt bei Bedarf: Beide Tickets (#49 und #146) zusammen an `/abc-requirements` geben —
Erweiterung der `ImageClassification`-Enum um fehlende Raumtypen plus Überarbeitung der
Titel/Kategorie-Anzeige im Exposé, kein reiner Bug-Fix.
