# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #66)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint ac83c273 (Freshdesk #66) — "Rechtschreibfehler erkenner" | Feature-Wunsch / Benutzerfehler: native Browser-Rechtschreibprüfung wurde in PROJ-28 bewusst erzwungen, Kunde möchte sie abschalten/anders dargestellt sehen | Niedrig |

---

### Ticket: Peppermint-Ticket "Rechtschreibfehler erkenner" (Peppermint ac83c273-fca8-4e6e-8b1b-a764af01842e, Freshdesk #66, Absender: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Firat Erol bittet um eine Möglichkeit, die Rechtschreibprüfung umzustellen — der
rote Unterstreichungs-Hinweis ziehe "direkt durch die Wörter" und mache unleserlich, was genau
als falsch markiert ist. Das betrifft nicht die vom Bildpfad angedeutete `crm.erol.msce.info`-App
selbst als Fehlfunktion, sondern eine bewusst eingeschaltete Funktion: **PROJ-28** in
`immo-crm` (`web/index.html:36-95`, Status "In Review") patcht per MutationObserver gezielt
`spellcheck="true"` auf alle Text-Inputs/-Textareas, weil Flutter Web dort standardmäßig
`spellcheck="false"` setzt. Der Kunde sieht also die **native Rechtschreibprüfung seines
Browsers** (Chrome/Firefox/Edge-eigene rote Wellenlinie) — kein von der App selbst gezeichnetes
UI-Element, dessen Stil man einfach per CSS ändern könnte.

**Eingrenzung:** Frontend · Modul: Text-Eingabefelder / Rechtschreibprüfung
(`immo-crm`, `web/index.html` + `backend/static/index.html` + `build/web/index.html`, sowie
`lib/core/widgets/app_text_field.dart` für die Flutter-seitige `spellCheckConfiguration`).
Code-Grep bestätigt: Die "rote Linie durch die Wörter" ist die native Browser-Spellcheck-UI,
die PROJ-28 erst aktiviert hat (vorher war sie durch Flutter-Web-Default deaktiviert) — kein
Bug, sondern die erwartete, aber vom Kunden als störend empfundene Nebenwirkung eines bewusst
gebauten Features. `app_text_field.dart` kennt bereits ein `spellCheckConfiguration`/Opt-out
(`data-spellcheck="false"`), das aber aktuell global bzw. nur einzelfeldweise, nicht nutzerweise
umschaltbar ist.

**Dringlichkeit:** Niedrig
Randfunktion (Komfort/Optik der Texteingabe), keine Kernfunktion, keine Daten- oder
DSGVO-Relevanz, nur ein Kunde meldet es bisher, kein Blocker — der Kunde kann weiterarbeiten,
ist nur genervt. Freshdesk-Priorität "low" passt hier.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Rückmeldung. Die rote Unterstreichung, die Sie meinen, stammt von der
> Rechtschreibprüfung Ihres Browsers (z. B. Chrome oder Firefox) — wir haben sie kürzlich bewusst
> für alle Textfelder aktiviert, damit Tippfehler leichter auffallen. Wie genau sich diese Linie
> darstellt, legt allerdings der Browser selbst fest, nicht unsere Anwendung; entsprechend können
> wir das Erscheinungsbild nicht direkt anpassen. Wir prüfen, ob wir eine Möglichkeit anbieten
> können, die Rechtschreibprüfung bei Bedarf pro Nutzer abzuschalten, und melden uns, sobald wir
> hierzu etwas Konkretes haben.

**Rückfragen-Guidance:**
- Welcher Browser (Chrome/Firefox/Edge/Safari) und welches Betriebssystem wird verwendet? (Die
  native Darstellung der Rechtschreib-Markierung unterscheidet sich je Browser.)
- In welchem konkreten Feld ist es ihm aufgefallen (z. B. E-Mail-Entwurf, Exposé-Text, Notizfeld)?
- Geht es ihm nur um die visuelle Störung, oder soll die Prüfung komplett abschaltbar sein
  (relevant für die Priorisierung eines möglichen Nutzer-Toggles)?

---

Nächster Schritt bei Bedarf: Falls mehrere Kunden dieselbe Rückmeldung zu PROJ-28 geben, lohnt
sich ein kleiner Folge-Task in `immo-crm` für einen nutzerseitigen Ein/Aus-Schalter der
Rechtschreibprüfung (Ergänzung zu PROJ-28, kein neuer Bug) statt eines QA-Laufs — es handelt sich
um einen Feature-Wunsch, nicht um eine Fehlfunktion.
