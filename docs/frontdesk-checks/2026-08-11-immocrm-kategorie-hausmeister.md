# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #149)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 080985dd (Freshdesk #149) — "ImmoCRM - Kategorie Hausmeister" | Feature-Wunsch, kein Fehlerbericht | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCRM - Kategorie Hausmeister" (Peppermint 080985dd-ba9b-44fa-95d4-72c9acfefb89, Freshdesk #149, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern zwei Wünsche in einer Meldung: (1) bei "Dienstleister"
soll die Kategorie "Hausmeister" ergänzt werden, (2) Admin/Superuser sollen solche Kategorien
künftig selbst anlegen können, statt jede neue Kategorie einzeln melden zu müssen. Kein
Fehlverhalten der App beschrieben — reguläre Erweiterungsanfrage.

ImmoCRM liegt nicht in diesem Repository (kein Backend-/Frontend-Code hier vorhanden), daher kein
Code-Grep möglich — Einordnung rein auf Basis des Ticket-Texts. Keine bestehende Doku
(`docs/architektur.md`, `features/INDEX.md`) zu diesem System in diesem Repo, folglich auch kein
Abgleich mit einem bereits bekannten Cluster möglich.

**Eingrenzung:** entfällt (kein App-Fehler) — sachlich betrifft es das Stammdaten-/Kategorie-
Modul "Dienstleister" in ImmoCRM (fest hinterlegte Werteliste vs. vom Admin pflegbare Liste).

**Dringlichkeit:** Niedrig
Freshdesk hat „low" gesetzt, passt: reine Komfort-/Erweiterungsanfrage, keine Blockade, kein
Datenrisiko, keine DSGVO-Relevanz. Zwei Teilwünsche, aber beide unkritisch.

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für den Hinweis. Wir haben zwei Punkte notiert: die zusätzliche
> Dienstleister-Kategorie "Hausmeister" sowie den Wunsch, dass Admin und Superuser solche
> Kategorien künftig selbst anlegen können, ohne dafür jedes Mal ein Ticket zu erstellen. Wir
> melden uns, sobald wir das umgesetzt haben bzw. mit weiteren Rückfragen zum genauen Umfang.

**Rückfragen-Guidance:** Für die Umsetzung noch offen (nicht im Ticket enthalten): soll
"Hausmeister" zusätzlich zur bestehenden Liste ergänzt werden, oder gibt es eine gewünschte
Reihenfolge/Gruppierung? Beim zweiten Wunsch (Admin legt Kategorien selbst an): reicht eine reine
Textliste, oder sollen Kategorien weitere Eigenschaften haben (z. B. Icon, Zuordnung zu
Objekttyp)? Mandantenweit oder pro Mandant unterschiedlich?

---

Nächster Schritt bei Bedarf: `/abc-requirements` für "Dienstleister-Kategorien admin-verwaltbar
machen" (deckt beide Teilwünsche ab — "Hausmeister" wäre dann kein Einzel-Fix mehr, sondern der
erste Anwendungsfall der neuen Verwaltungsfunktion).
