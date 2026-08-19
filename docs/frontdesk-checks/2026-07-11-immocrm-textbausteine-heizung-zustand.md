# Frontdesk-Triage — 2026-07-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #128)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 2b5dbceb (Freshdesk #128) — "Fehlende wichtige Textbausteine" | Kein Fehler, berechtigter Feature-Wunsch (3 Punkte: Ölheizung-Wert, Sanierungsbedürftig-Wert, Heizungsjahr-Feld) — teilweise Duplikat von Ticket #46 | Niedrig |

---

### Ticket: Peppermint-Ticket "Fehlende wichtige Textbausteine" (Peppermint 2b5dbceb-2e11-4acc-8876-fcf804171b1f, Freshdesk #128, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein Feature-Wunsch mit drei Einzelpunkten, den die
Absenderin mit "Hallo nochmal" einleitet (Hinweis auf eine bereits frühere Anfrage):
1. Bei der Heizungsart fehlt der Wert "Ölheizung".
2. Beim Zustand fehlt der Wert "Sanierungsbedürftig".
3. Das "Heizungsjahr" (Baujahr der Heizungsanlage) fehlt als Feld.

Punkt 3 ist inhaltlich deckungsgleich mit dem bereits dokumentierten Ticket #46
(`2026-07-08-immocrm-baujahr-heizung.md`, ebenfalls von Beata Rutkowska) — die Absenderin fragt
hier offenbar zum zweiten Mal nach demselben Feld, ergänzt um zwei neue Dropdown-Wert-Wünsche.

**Eingrenzung:** Frontend (+ kleines Backend/DB-Feld) · Modul: Objektformular → Energiedaten
(Heizungsart-Dropdown) und Zustand-Dropdown (`immo-crm`,
`lib/features/properties/models/property_enums.dart` + `form_field_config.dart`).

Code-Grep-Befund (Projekt `immo-crm`, nicht im Jupiter-Repo):
- `HeatingType`-Enum (`property_enums.dart:248`, Feld `heatingType`/"Heizungsart",
  `form_field_config.dart:96`) enthält aktuell: Keine Angabe, Etagenheizung, Fußbodenheizung,
  Zentralheizung, Fernwärme, Nachtspeicherheizung, Ofenheizung, Wärmepumpe, Solarheizung,
  Holz-Pelletheizung, Kombinierte Heizung — **kein "Ölheizung"-Wert**. "Öl" existiert nur im
  separaten Feld "Energiequellen" (`EnergySource`-Enum, Multi-Select, `form_field_config.dart:101`)
  bzw. im nicht im Formular verdrahteten `FiringType`-Enum. Aus Kundensicht wirkt das wie ein
  fehlender Wert direkt bei der Heizungsart, weil "Energiequellen" ein separates, nicht
  offensichtlich verknüpftes Feld ist.
- `PropertyCondition`-Enum (`property_enums.dart:218`, Feld `condition`/"Zustand",
  `form_field_config.dart:72`) enthält "Renovierungsbedürftig" (`NEED_OF_RENOVATION`), aber
  **keinen separaten Wert "Sanierungsbedürftig"** — im Maklerjargon nicht deckungsgleich
  (Renovierung = kosmetisch, Sanierung = strukturell/energetisch), Kunde vermisst zu Recht die
  Unterscheidung.
- Heizungsjahr: wie in Ticket #46 bereits festgestellt — kein Feld im Energiedaten-Formular,
  kein Backend-Parameter im Umfeld von `heatingType`. Unverändert offen seit 2026-07-08.
- Alle drei Punkte sind strukturelle Formular-/Enum-Lücken, keine Datenfehler.

**Dringlichkeit:** Niedrig
Kein Datenrisiko, kein DSGVO-Bezug, keine Blockade — reiner Formular-/Enum-Vollständigkeitswunsch,
passt zur "low"-Priorität in Freshdesk. Zu beachten für die Priorisierung: Punkt 3 ist ein
**Wiederholungswunsch** (Kunde fragt zum zweiten Mal nach), das spricht dafür, die bereits unter
Ticket #46 vorgeschlagene Feature-Spec zeitnah anzugehen, statt sie weiter aufzuschieben.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für die weiteren Hinweise. Wir haben das geprüft:
>
> - Der Wert "Ölheizung" ist bei der Heizungsart aktuell tatsächlich nicht auswählbar (Öl lässt
>   sich derzeit nur über das separate Feld "Energiequellen" hinterlegen).
> - Beim Zustand fehlt ebenfalls eine eigene Option "Sanierungsbedürftig".
> - Das Heizungsjahr als eigenes Feld hatten Sie uns bereits gemeldet — das steht weiterhin auf
>   unserer Liste.
>
> Wir nehmen alle drei Punkte als Ergänzung des Objektformulars auf und melden uns, sobald sie
> umgesetzt sind.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung — alle drei Punkte sind im Code klar
nachvollziehbar. Für die Umsetzung wäre höchstens zu klären, ob "Ölheizung" als eigener Wert im
`HeatingType`-Enum ergänzt werden soll oder ob stattdessen die Verknüpfung zwischen Heizungsart
und Energiequellen im UI verständlicher dargestellt werden soll — das ist aber eine Scope-Frage
für `/abc-requirements`, keine fehlende Information für diese Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine Sammel-Spec
("Fehlende Dropdown-Werte: Ölheizung, Sanierungsbedürftig, Heizungsjahr") — ggf. gebündelt mit dem
bereits offenen Ticket #46, da Heizungsjahr dort schon beschrieben ist.
