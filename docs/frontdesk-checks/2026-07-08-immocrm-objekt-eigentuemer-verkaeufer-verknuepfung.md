# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #70)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint ff47421c (Freshdesk #70) — "Neue Immobilie verbinden mit Eigentümer oder Verkäufer" | Kein Fehler, Feature-Wunsch: Objekt↔Eigentümer/Verkäufer-Verknüpfung fehlt strukturell | Niedrig |

---

### Ticket: Peppermint-Ticket "Neue Immobilie verbinden mit Eigentümer oder Verkäufer" (Peppermint ff47421c-a9ef-42f0-8225-7718649c5a07, Freshdesk #70, Absender: Firat Erol / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein Verbesserungswunsch: Beim Objekt soll sichtbar
sein, wer Eigentümer/Verkäufer ist (mit Sprung zum Kundendatensatz), zusätzlich soll bei
Verkaufs-/Vermietungsobjekten ein Interessent oder Käufer angelegt werden können. Kein
Datensatz, kein Datum genannt — betrifft die allgemeine Objekt-Kunden-Verknüpfung, kein
Einzelfall.

**Eingrenzung:** Backend + Frontend · Modul: Objektdetail ↔ Kundenverknüpfung
(`client_property_relations`, `properties`-Tabelle, `property_detail_screen.dart`).

Code-Grep-Befund (immo-crm-Repo, read-only):
- Eine Objekt↔Kunde-Verknüpfung existiert bereits als generische Tabelle
  `client_property_relations` (`backend/app/schema.py:467-477`) mit Endpoints
  `GET /api/properties/{id}/clients` (`backend/app/main.py:4641`) und
  `POST /api/clients/{id}/properties` (`backend/app/main.py:6103`).
- Diese Verknüpfung bildet aber ausschließlich den **Interessenten-Trichter** ab: die einzigen
  `relation_type`-Werte sind `inquiry`/`viewing`/`offer`/`contract` (Anfrage/Besichtigung/
  Angebot/Vertrag), hartkodiert im Dropdown und im Label-Switch
  (`lib/features/properties/property_detail_screen.dart:3989-3992`, `:4126-4132`, `:4376-4381`).
  Es gibt keinen Wert wie „Eigentümer" oder „Verkäufer".
- Die `properties`-Tabelle selbst hat kein `owner_id`/`owner_client_id`-Feld
  (`backend/app/schema.py:264-313`) — es gibt also auch keinen direkten, immer sichtbaren
  „Eigentümer"-Verweis am Objekt, unabhängig vom Interessenten-Trichter.
- Ergebnis: echte Funktionslücke, kein Datenfehler und kein Bedienfehler — der Kunde kann diese
  Verknüpfung mit der aktuellen App schlicht nicht abbilden, weil die Rolle „Eigentümer/
  Verkäufer" im Datenmodell nicht vorgesehen ist. Das „Käufer"-Bedürfnis ist über den
  bestehenden Trichter (`contract`) teilweise abgedeckt, aber nicht als eigene, klar benannte
  Rolle sichtbar.

**Dringlichkeit:** Niedrig
Freshdesk hat „low" gesetzt, das passt: kein Datenrisiko, keine DSGVO-Relevanz, keine Blockade —
der Kunde kann Objekte und Kunden weiterhin getrennt pflegen, das ist ein struktureller
Komfort-/Vollständigkeits-Wunsch, kein akutes Problem.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Vorschlag. Aktuell lässt sich am Objekt zwar der Interessenten-Verlauf
> (Anfrage/Besichtigung/Angebot/Vertrag) abbilden, aber es gibt noch keine eigene Verknüpfung
> zum Eigentümer bzw. Verkäufer des Objekts mit direktem Sprung zum Kundendatensatz. Wir nehmen
> das als Erweiterung des Objektformulars auf (Eigentümer/Verkäufer als eigene Rolle,
> Interessent/Käufer klarer sichtbar) und melden uns, sobald es umgesetzt ist.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung — das Ticket ist klar genug, um es
als reguläre Feature-Spec zu behandeln. Für die Umsetzung selbst wäre zu klären, ob „Eigentümer"
als 1:1-Feld am Objekt reichen soll oder ob (wie beim Interessenten-Trichter) mehrere
Eigentümer/Verkäufer pro Objekt möglich sein müssen (z. B. Erbengemeinschaft) — das ist eine
Scope-Frage für `/abc-requirements`, keine fehlende Information für diese Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine
Backend+Frontend-Spec „Eigentümer/Verkäufer- und Käufer-Rolle am Objekt" — kein Bug-Fix,
sondern regulärer Feature-Weg.
