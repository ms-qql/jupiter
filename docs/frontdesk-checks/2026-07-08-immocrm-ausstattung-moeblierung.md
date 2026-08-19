# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #75)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 53a7daa2 (Freshdesk #75) — "Ausstattung: Bitte mit aufnehmen Vollmöblierung Teilmöblierung" | Kein Fehler, berechtigter Feature-Wunsch: Möblierungsstatus (voll/teil) fehlt als strukturierte Option im Ausstattungs-Bereich | Niedrig |

---

### Ticket: Peppermint-Ticket "Ausstattung" (Peppermint 53a7daa2-49c8-4d04-97c0-25ce03127129, Freshdesk #75, Absender: Firat Erol / Erol ImmobilienGmbH, Cuxhaven, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein knapper Verbesserungswunsch: "Bitte mit aufnehmen
Vollmöblierung Teilmöblierung." Kein Bezug auf einen konkreten Datensatz, keine Fehlermeldung —
der Kunde möchte, dass die Möblierungs-Ausprägungen "Vollmöblierung" / "Teilmöblierung" im
Ausstattungs-Bereich eines Objekts wählbar sind.

**Eingrenzung:** Frontend (+ kleines Backend/DB-Feld) · Modul: Objektformular → Ausstattung/Beschreibungstexte
(`immo-crm`, `lib/features/properties/models/form_field_config.dart`).

Code-Grep-Befund (im separaten Projekt `immo-crm`, nicht in diesem Jupiter-Repo):
- Das Feld, das dem Kunden als "Ausstattung" angezeigt wird, ist `furnishingNote`
  (`form_field_config.dart:115`) — ein reines Freitext-`textarea` in der Gruppe
  "Beschreibungstexte", kein strukturiertes Auswahlfeld.
- Es gibt aktuell **keine** eigene Möblierungs-Option (kein Enum/Dropdown wie z. B. bei
  `heatingType` oder `hotWaterPreparation`, die als strukturierte Dropdowns mit
  `_enumToOptions` gepflegt werden). "Vollmöblierung"/"Teilmöblierung" könnte der Kunde also
  bislang nur als freien Text in dieses Notizfeld eintippen.
- Import/Export-Mapping (`backend/app/routes/import_export.py:564,584,1078,1113,1348,1660,1695`,
  `backend/app/services/openimmo_parser.py:172`) behandelt `furnishingNote`/`furnishing_note`
  ebenfalls nur als unstrukturierten Text (1:1 Textübernahme bei IS24/OpenImmo).
- Strukturelle Lücke, kein Datenfehler — analog zum bereits dokumentierten Fall
  "Baujahr der Heizung" (`2026-07-08-immocrm-baujahr-heizung.md`): das gewünschte Attribut fehlt
  schlicht als eigenes, strukturiertes Feld im Formular/DB-Schema und in den Export-Mappings.

**Dringlichkeit:** Niedrig
Freshdesk hat "low" gesetzt, passt zum Charakter: kein Datenrisiko, kein DSGVO-Bezug, keine
Blockade — der Kunde kann den Möblierungsstatus schon jetzt als Freitext im Ausstattungsfeld
hinterlegen, es fehlt nur die strukturierte/wählbare Form.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihren Hinweis. Aktuell lässt sich der Möblierungsstatus (z. B.
> "Vollmöbliert"/"Teilmöbliert") bereits als Freitext im Ausstattungsfeld des Objekts hinterlegen,
> ein eigenes, auswählbares Feld dafür gibt es aber noch nicht. Wir nehmen das als kleine
> Ergänzung des Objektformulars auf und melden uns, sobald sie umgesetzt ist.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung — das Ticket ist klar genug, um als
reguläre Feature-Spec eingeplant zu werden. Für die Umsetzung selbst wäre höchstens zu klären, ob
"Vollmöbliert"/"Teilmöbliert" ein eigenes Dropdown-Feld werden soll (mit welchen weiteren
Ausprägungen, z. B. "Unmöbliert") und ob es auch in Exporte (IS24, OpenImmo, Exposé-PDF) einfließen
muss — das ist aber eine Scope-Frage für `/abc-requirements`, keine fehlende Information für diese
Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine
Frontend+Backend-Spec ("Möblierungsstatus als strukturiertes Feld in der Ausstattung") — kein
Bug-Fix, sondern regulärer Feature-Weg.
