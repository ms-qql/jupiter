# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #67)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint dbe815f8 (Freshdesk #67) — "Exposé noch mit Englischen Wörtern" | Bestätigter Bug (übergreifend): Übersetzungs-Fallback für Zustand/Warmwasser leakt rohen (englischen) Wert bei fehlendem exaktem Match | Mittel |

---

### Ticket: Peppermint-Ticket "Exposé noch mit Englischen Wörtern" (Peppermint dbe815f8-8837-4ae8-82c2-e9f99821a0a7, Freshdesk #67, Absender: Firat Erol / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Bestätigter Bug, kein Benutzerfehler. Meldung: "Exposé nimmt bei Warmwasser
und Zustand die Wörter im Englischen" (Anhang: Exposé-PDF eines Bauernhaus-Objekts). Code-Grep
bestätigt einen konkreten, reproduzierbaren Mechanismus dafür — siehe Eingrenzung.

**Eingrenzung:** Frontend · Modul: Objektdetail/Exposé-Anzeige
(`immo-crm`, `lib/features/properties/property_detail_screen.dart:39-69`).

Code-Grep-Befund:
- `_translateCondition()` (Zeile 39–45) und `_translateHotWater()` (Zeile 63–69) matchen den in
  der DB gespeicherten Wert nur **exakt** (`==`) gegen `PropertyCondition.apiValue` bzw.
  `HotWaterPreparationType.apiValue` (SCREAMING_SNAKE_CASE, z. B. `REFURBISHED`). Gibt es keinen
  exakten Treffer, wird am Ende schlicht der **rohe Eingabewert unverändert zurückgegeben**
  (`return condition;` / `return hw;`) — statt eines sicheren Fallbacks. Landet der Wert
  unverändert im Exposé, erscheint er dort in der ursprünglichen (meist englischen/
  IS24-Format-) Schreibweise.
- Die Enum-Definitionen selbst (`lib/features/properties/models/property_enums.dart:218-234`
  `PropertyCondition`, `:407-424` `HotWaterPreparationType`) haben vollständige deutsche Labels —
  das Problem ist nicht ein fehlendes Label, sondern der brüchige Exact-Match beim Auflösen.
- Backend-seitig (`backend/app/routes/expose.py`, Funktion `_label()`, Zeile 270ff.) ist derselbe
  Übersetzungsschritt für die Web-/PDF-Exposé-Route bereits **sicher** implementiert: tolerant
  gegen Schreibweise-Unterschiede (`_norm_key`) und gibt bei Miss `None` zurück statt roh zu
  leaken (Kommentar: "Returns None … so callers can omit a row instead of leaking raw English
  terms."). Das Leck sitzt also im Flutter-Frontend-Übersetzer, nicht im PDF-Generator selbst.
- Exakt dieselbe Bug-Klasse wurde bereits einmal für zwei andere Felder behoben: **PROJ-78**
  ("Deutsche Labels in der Immobilien-Detailansicht") fixte `.toString()`-Leaks bei Bodenbelag
  und Dokumentkategorie nach demselben Muster — wurde aber nicht auf `_translateCondition`/
  `_translateHotWater` (und vermutlich auch `_translateQuality` Zeile 47, `_translateHeatingType`
  Zeile 55 als Nebenbefund mit identischem Muster) angewendet.
- Strukturell **übergreifend**: der Mechanismus (Exact-Match-Fallback auf Rohwert) schlägt bei
  jedem Datensatz zu, dessen gespeicherter Wert nicht exakt dem heutigen `apiValue`-Format
  entspricht — plausibel z. B. bei IS24-/OpenImmo-Importdaten mit abweichender Schreibweise oder
  bei älteren Datensätzen aus vor einer Enum-Umbenennung. Nicht auf dieses eine Objekt beschränkt.

**Dringlichkeit:** Mittel
Kein Datenverlust, kein DSGVO-Bezug, keine Blockade (Exposé lässt sich weiter versenden) — aber
der Fehler landet direkt im kundenseitig sichtbaren PDF-Dokument (Reputationsrisiko) und betrifft
strukturell jeden Datensatz mit nicht exakt matchendem Wert, nicht nur diesen einen Fall. Freshdesk
hat "low" gesetzt; das passt zur fehlenden Dringlichkeit/Blockade, unterschätzt aber die
übergreifende Reichweite — daher hier Mittel statt Niedrig.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis und den beigefügten Exposé-Anhang. Wir konnten die Ursache bereits
> eingrenzen: Bei bestimmten Feldern (u. a. Zustand und Warmwasseraufbereitung) wird der
> gespeicherte Wert unter bestimmten Bedingungen nicht korrekt ins Deutsche übersetzt und
> erscheint dann im Originalformat. Wir nehmen das als Fix auf und melden uns, sobald es behoben
> ist.

**Rückfragen-Guidance:** Für die Einstufung nicht zwingend nötig — der Code-Grep liefert einen
klaren, plausiblen Mechanismus. Für die Fix-Umsetzung wäre hilfreich zu wissen, welchen genauen
Rohwert die Datenbank bei diesem Objekt für `condition`/`hotWaterPreparation` gespeichert hat
(z. B. per DB-Abfrage oder Rücksprache, ob das Objekt per IS24-Import angelegt wurde) — das würde
bestätigen, ob Import-Altdaten die Ursache sind, ist aber eine Umsetzungsdetail-Frage, keine für
diese Triage fehlende Information.

---

Nächster Schritt bei Bedarf: kein `/abc-requirements` nötig (klarer Bug, kein Feature) — direkt an
den Frontend-Developer zur Behebung von `_translateCondition`/`_translateHotWater` (und optional
`_translateQuality`/`_translateHeatingType`) in `immo-crm/lib/features/properties/property_detail_screen.dart`,
z. B. nach dem in `backend/app/routes/expose.py:_label()`/PROJ-78 (`FlooringType.fromRaw()`)
bereits etablierten Muster (tolerantes Matching + sicherer Fallback statt Rohwert-Leak).
