# Frontdesk-Check — 2026-08-16

Quelle: Peppermint-Ticket (weitergeleitet von Auxevo Support / Freshdesk #150, Peppermint-ID `36f5034e-d960-4728-a127-c717767369cc`), Melder: b.rutkowska@erolimmobilien.de (für Kundin "Beata"). Interne Ersteinschätzung, kein QA-Ergebnis.

---

### Ticket: Gewerbearten/Textbausteine bei Exposé-Erstellung reichen nicht aus (Beispiel: Immobilie "Strichweg")

**Kurzbefund:** Kein App-Fehler im klassischen Sinn — **Feature-Wunsch/Erweiterungsbedarf**. Die Kundin meldet, dass beim Erstellen eines Exposés auf der ersten Seite die Art-Auswahl ("Gewerbeart", z. B. Büroräume) nicht alle real vorkommenden Gewerbearten abdeckt, und fragt zusätzlich, ob eigene Textbausteine benannt werden könnten.

**Eingrenzung:** Frontend · Modul: Immobilien/Exposé-Erstellung (Property-Formular bzw. Exposé-Wizard).
Code-Grep im immo-crm-Repo zeigt: Die "Art der Immobilie"-Auswahl ist ein festes Enum `PropertyType` (`lib/features/properties/models/property_enums.dart:14-38`) mit u. a. `officeBuy/officeRent` ("Büro/Praxis"), `storeBuy/storeRent` ("Einzelhandel"), `gastronomyBuy/gastronomyRent` ("Gastronomie/Hotel"), `industryBuy/industryRent` ("Halle/Produktion"), `specialPurposeBuy/specialPurposeRent` ("Spezialgewerbe"). Der von der Kundin genannte Begriff "Büroräume" existiert wörtlich nicht (nächstliegend: "Büro/Praxis"), aber inhaltlich benachbarte Kategorien (Lager, Verkaufsfläche, Gastronomie, Spezialgewerbe) sind im Enum bereits vorhanden — die Auswahl ist also breiter als im Ticket unterstellt, aber offenbar für den konkreten Fall ("Strichweg") trotzdem nicht passend oder für die Kundin nicht auffindbar.
Ein separates KI-gestütztes Textbaustein-System für Exposé-Beschreibungen (das an die Immobilienart gekoppelt wäre) existiert im Code **nicht**: Der reale Exposé-Wizard (`lib/features/properties/expose/expose_generator_screen.dart`) ist reine PDF-Zusammenstellung (Fotos/Dokumente/Recht), keine Textgenerierung. Die einzige KI-Textfunktion (`backend/app/services/ai_service.py:52-89`) ist an Kommunikationskanäle (E-Mail/WhatsApp) gekoppelt, nicht an Immobilienarten. Die Exposé-Beschreibungstexte selbst sind freie Textfelder (`descriptionNote`, `furnishingNote`, `locationNote` in `property_form_screen.dart`) — Nutzer können also faktisch schon frei formulieren, es gibt aber keinen benannten/wiederverwendbaren Textbaustein-Katalog.

**Dringlichkeit:** Niedrig
Randfunktion (Komfort/Flexibilität bei Textformulierung), kein Datenverlust-/Datenintegritäts- oder DSGVO-Bezug, Kundin ist nicht blockiert (freies Textfeld vorhanden als Workaround). Kein Hinweis auf systemweite Störung.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für die Rückmeldung. Die Auswahl der Immobilienart beim Anlegen ist bereits recht breit gefasst (u. a. Büro/Praxis, Einzelhandel, Gastronomie/Hotel, Halle/Produktion, Spezialgewerbe) — für die Beschreibungstexte selbst steht Ihnen zusätzlich ein freies Textfeld zur Verfügung, in dem Sie unabhängig von der gewählten Art frei formulieren können.
>
> Ihren Wunsch nach flexibler benennbaren bzw. wiederverwendbaren Textbausteinen je Gewerbeart nehmen wir als Verbesserungsvorschlag auf und prüfen ihn für eine der nächsten Erweiterungen. Könnten Sie uns kurz schildern, welche konkrete Art bei der Immobilie "Strichweg" gefehlt hat bzw. welchen Textbaustein Sie sich dafür wünschen würden? Das hilft uns, die Erweiterung passgenau zu planen.
>
> Viele Grüße
> Ihr Immo-CRM-Team

**Rückfragen-Guidance:**
- Welche konkrete Gewerbeart fehlte im Dropdown für die Immobilie "Strichweg" (Name/ID des Datensatzes)?
- Ist mit "Textbaustein" ein wiederverwendbarer, benannter Beschreibungsblock gemeint (Feature-Wunsch) oder wurde erwartet, dass die App automatisch passenden Text generiert (KI-Funktion, aktuell nicht für Exposé-Beschreibungen vorhanden)?
- Screenshot des betreffenden Auswahlschritts wäre hilfreich, um zu prüfen, ob evtl. eine andere/ältere Formular-Ansicht als der aktuelle Code gemeint ist (gemeldete Softwareversion v0.8.10 — Versionsstand im Vergleich zum aktuellen Code nicht verifiziert).

---

**Gesamtübersicht:** Gewerbearten/Textbausteine Exposé → Feature-Wunsch (kein Bug) → Niedrig
