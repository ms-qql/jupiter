# Frontdesk-Check — 2026-07-08

Quelle: Auxevo Support (Freshdesk, weitergeleitet an Peppermint), Ticket 9f62172c-a0c9-4df0-aa83-c6f58a5ac5ad / Freshdesk #133.
Interne Ersteinschätzung, kein QA-Ergebnis.

### Ticket: Sidebar — "Makler" soll Unterpunkt von "Verwaltung" sein statt eigener Hauptpunkt

**Kurzbefund:** Kein Bug — Feature-/UX-Wunsch (Sidebar-Struktur, App verhält sich wie programmiert).

**Eingrenzung:** Schicht: Frontend · Modul: Sidebar-Navigation
`immo-crm/lib/core/widgets/sidebar.dart:41-56` — flache `SidebarItem`-Liste, kein Untermenü-Konzept vorhanden. "Makler" (Zeile 52) und "Verwaltung" (Zeile 55) sind beides gleichrangige Top-Level-Einträge; Verschachtelung wie gewünscht existiert im Datenmodell aktuell gar nicht.

**Dringlichkeit:** Niedrig
Rein kosmetisch/strukturell, keine Kernfunktion blockiert, kein Datenrisiko, seit Monat bekannt und niedrige Priorität selbst laut Melder.

**Antwortentwurf an den Kunden:**
> Vielen Dank für Ihre Rückmeldung. Aktuell ist "Makler" bewusst als eigener Hauptpunkt in der Sidebar angelegt — eine Verschachtelung unter "Verwaltung" ist technisch noch nicht vorgesehen. Wir nehmen Ihren Wunsch als Verbesserungsvorschlag auf und prüfen eine Umsetzung in einem kommenden Update.

**Rückfragen-Guidance:** Keine — Ticket war für die Einordnung ausreichend (klare Erwartung vs. Ist-Zustand, Screenshot vorhanden). Für eine Umsetzung wäre zu klären, ob "Makler" komplett unter Verwaltung soll oder als Kurzlink zusätzlich sichtbar bleiben.

---

**Übersicht:** Sidebar Makler→Verwaltung → Kein Bug (Feature-Wunsch) → Niedrig
