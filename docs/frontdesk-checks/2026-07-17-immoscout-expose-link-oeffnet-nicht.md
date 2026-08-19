# Frontdesk-Checks — 2026-07-17 — ImmoScout24-Exposé-Link öffnet nicht

Quelle: Peppermint-Ticket fee5c545-e18f-4c64-b422-1dc85212b179 (Freshdesk #129), Kunde: Beata
Rutkowska / Erol Immobilien GmbH (immo-crm, `crm.erol.msce.info`), Nachricht an "Manfred".

Interne Ersteinschätzung (keine QA-Freigabe, kein Testergebnis).

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| "Vollständiges Exposé" auf IS24 öffnet nichts (ETW Schuberstraße 32) | Vermutlich Übergreifendes Problem | Hoch |

---

### Ticket: ETW Schuberstraße 32 — Klick auf "Vollständiges Exposé" ganz unten im IS24-Inserat öffnet nichts

**Kurzbefund:** Vermutlich Übergreifendes Problem. Die Betreff-"Dringend!!!"-Formulierung stammt
vom Kunden, nicht aus objektiven Kriterien — Priorität im Ticket-System steht auf "low", was
gegensätzlich wirkt; die Einstufung unten folgt den Sachkriterien, nicht dem Tonfall.

**Eingrenzung:** Schicht: Backend · Modul: IS24-Integration (PROJ-8, PROJ-20–24, PROJ-26, PROJ-85,
PROJ-86), separates Repo `/home/dev/projects/immo-crm`.
- `backend/app/services/is24_sync.py:472` `set_property_expose_link()` — PROJ-86 "Automatischer
  Web-Exposé-Link". Es wird **kein PDF** hochgeladen, sondern ein `Link`-Attachment
  ("Vollständiges Exposé", `WEB_EXPOSE_LINK_TITLE`, Zeile 442) unter IS24 "Ergänzende Links"
  gesetzt, das auf `{APP_BASE_URL}/{slug}/expose/{public_token}` zeigt (Zeile 517). Der Klick in
  IS24 öffnet also die öffentliche Exposé-Seite im eigenen CRM — kein Dokument.
- Mögliche Bruchstellen, warum dieser Link leer/tot bleibt:
  - `expose_published=false` oder fehlender `public_token` → Link wird entfernt, `status:
    no_expose` (Zeile 502–508).
  - `company_website` in `tenant_settings` fehlt/nicht auflösbar → `_website_slug()` liefert
    `None` → `status: no_slug`, **kein Link wird gesetzt** (Zeile 513–515). Auffällig:
    `routes/expose.py:2040` (Publish-Route) hat einen Fallback-Slug `"expose"`, `is24_sync.py`
    nicht — Inkonsistenz, durch die die Exposé-Seite existieren, der IS24-Link aber nie gesetzt
    werden kann.
  - `APP_BASE_URL` nicht konfiguriert → `status: no_base_url`.
  - Stale `public_token` nach Deaktivieren/Reaktivieren des Objekts.
- Gleiches Kundenkonto, gleicher Themenbereich (IS24-Reaktivierungs-/Sync-Pfad) wie zwei bereits
  dokumentierte Tickets vom 09.07.2026: `2026-07-09-is24-aenderungsuebernahme.md` (Objekt 1014,
  Änderungen nach Reaktivierung nicht übernommen) und `2026-07-09-is24-text-sync-fehlermeldung.md`.
  Dort bereits vermuteter struktureller Bruch im Reaktivierungs-/Re-Publish-Pfad
  (`run_auto_update()`, frühe Skip-Gates). Das gleiche Muster (früh angelegtes/reaktiviertes
  Objekt) könnte hier ebenso den Exposé-Link stale/leer lassen — noch nicht bestätigt, aber ein
  naheliegender gemeinsamer Nenner über inzwischen drei Tickets desselben Kunden.
- Nicht live geprüft (kein DB-Zugriff auf Objekt "ETW Schuberstraße 32" ohne Freigabe) — Aussage
  stützt sich auf Code-Analyse, nicht auf einen tatsächlichen Reproduktionsversuch.
- Fallstrick-Check Einzelfall vs. übergreifend: Die Vorbedingung (fehlender/nicht auflösbarer
  Website-Slug, Reaktivierungs-Historie, oder fehlende `APP_BASE_URL`-Konfiguration) ist keine
  Anomalie eines einzelnen Datensatzes, sondern ein strukturelles Muster, das bei jedem Mandanten
  mit ähnlicher Konstellation (fehlende Website-URL in den Tenant-Settings, oder Objekt mit
  Deaktivierungs-Historie) gleich auftreten würde → übergreifend, nicht Einzelfall.

**Dringlichkeit:** Hoch
- Kernfunktion betroffen: Der Exposé-Link ist das zentrale Vermarktungsinstrument im IS24-Inserat —
  Interessenten können das vollständige Exposé nicht einsehen, was direkten Geschäftsschaden
  (verlorene Leads) bedeuten kann.
- Vermutlich übergreifend (dritter Vorfall im selben Themenfeld beim selben Kunden binnen 8 Tagen),
  kein reiner Einzelfall.
- Kein Datenverlust, keine DSGVO-Relevanz — reines Anzeige-/Verlinkungsproblem, kein Daten-Risiko.
- Kunde ist funktional blockiert bezogen auf dieses eine Inserat (Exposé nicht einsehbar), Immo CRM
  selbst läuft weiter — daher Hoch, nicht Dringend.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für die Meldung. Wir prüfen aktuell, warum der Link zum vollständigen Exposé im
> ImmobilienScout24-Inserat der ETW Schuberstraße 32 sich nicht öffnen lässt. Das hat vermutlich
> einen technischen Zusammenhang mit der Übertragung des Exposé-Links an ImmobilienScout24 und
> steht möglicherweise im Zusammenhang mit zwei ähnlichen Meldungen, die wir bereits zu Ihrem
> Konto in Bearbeitung haben. Wir melden uns, sobald wir die Ursache eingegrenzt und behoben haben.
>
> Viele Grüße
> Ihr Support-Team

**Rückfragen-Guidance:** Für eine schnellere Eingrenzung wären beim nächsten Mal hilfreich:
- Interne Objekt-ID/UUID statt nur der Adresse "ETW Schuberstraße 32".
- War das Objekt zwischenzeitlich deaktiviert/reaktiviert (wie bei Objekt 1014)? Wenn ja, wann?
- Screenshot der Fehlersituation auf IS24 (leere Seite, Ladefehler, 404?) statt nur "öffnet sich
  nichts" — das würde zwischen `no_expose`/`no_slug`/totem Link unterscheiden helfen.
- Ist die öffentliche Exposé-Seite im Immo CRM selbst (direkt über den öffentlichen Link, ohne
  Umweg über IS24) erreichbar?
