# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #137)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 81c311d1 (Freshdesk #137) — "Kundensuche über Nummer" | Übergreifendes Problem — Telefonnummer-Suche macht rohen ILIKE-Substring-Vergleich ohne Normalisierung | Mittel |

---

### Ticket: Peppermint "Kundensuche über Nummer" (Peppermint 81c311d1-e734-4b9a-9643-b9feeb9432b6, Freshdesk #137, Nutzer f.erol@erolimmobilien.de, Erol Immobilien GmbH, Mandant 00000000-0000-0000-0000-000000000001)

**Kurzbefund:** Kunde meldet, gespeicherte Kunden mit Telefonnummer tauchen bei Eingabe der Nummer
in der Kunden-Suchleiste nicht auf. Erwartung: Rückwärtssuche — bei eingehendem Anruf die Nummer in
die Suche eintippen und den passenden Kunden finden.

**Eingrenzung:** Backend · Modul: Kunden / Suche
(`immo-crm`, `backend/app/main.py:5956` `list_clients` — Suchleiste im Kunden-Modul — und
`backend/app/main.py:3232` `global_search` — Kopfzeilen-Suche): beide bauen die Telefon-Bedingung
identisch als `c.phone ILIKE %search%` (Zeilen 5970 bzw. 3288) — reiner Substring-Vergleich auf dem
rohen, so wie eingegeben gespeicherten `phone`-Textfeld. Keine Normalisierung beim Schreiben
(kein Trim von Leerzeichen/Trennzeichen, keine Vereinheitlichung von Vorwahlformat `+49`/`0`) und
keine beim Suchen gefunden. Ergebnis: die Suche findet nur, wenn der eingegebene Suchstring exakt
als Teilstring im gespeicherten Format vorkommt — z. B. `0301234567` gespeichert, aber
`+49 30 1234567`, `030 1234567` oder nur die letzten Ziffern eingetippt → kein Treffer, obwohl der
Kunde da ist.

Kein Einzelfall dieses einen Datensatzes: der Mechanismus (fehlende Normalisierung) würde bei jedem
Kunden zuschlagen, dessen gespeichertes Telefonformat vom Eingabeformat beim Suchen abweicht —
das ist bei frei eingegebenen Telefonnummern der Regelfall, nicht die Ausnahme. Nicht live
nachgestellt (kein Zugriff auf echte Kundendaten ohne Freigabe) — Einschätzung basiert auf
Code-Analyse der beiden Such-Endpunkte.

**Dringlichkeit:** Mittel
Randfunktion (Komfort-Feature „wer ruft an", kein Datenverlust-/DSGVO-Risiko), aber übergreifend
und blockiert den beschriebenen Arbeitsablauf komplett (Rückwärtssuche funktioniert praktisch nie
zuverlässig, sobald Formate abweichen) — daher nicht nur Niedrig.

**Antwortentwurf an den Kunden:**
> Guten Tag Herr Erol,
>
> vielen Dank für Ihre Meldung. Wir konnten im Code nachvollziehen, dass die Telefonnummer-Suche im
> Kundenmodul aktuell nur exakte Teilstrings findet — weicht das gespeicherte Format der Nummer
> (z. B. mit/ohne Vorwahl, mit/ohne Leerzeichen) vom eingegebenen Format ab, liefert die Suche
> keinen Treffer, auch wenn der Kunde vorhanden ist. Wir prüfen das und melden uns, sobald es
> behoben ist.
>
> Freundliche Grüße
> Ihr Support-Team

**Rückfragen-Guidance:** Für eine sichere Bestätigung wäre hilfreich: ein Beispiel eines
betroffenen Kunden (Name oder Kunden-ID) mit der genau gespeicherten Telefonnummer und der genau
eingetippten Suchanfrage, die keinen Treffer lieferte — damit sich die Formatabweichung konkret
verifizieren lässt statt nur aus dem Code abzuleiten.
