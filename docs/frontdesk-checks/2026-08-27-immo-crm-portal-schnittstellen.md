# Frontdesk-Check — Immo CRM: Portal-Schnittstellen (Immowelt/Immonet)

- **Datum Analyse-Lauf:** 2026-08-27
- **Quelle:** Peppermint-Ticket `d510a3ec-24a0-41d7-809f-3b3751f7a670` (Freshdesk #156), Kunde Firat Erol (Erol Immobilien GmbH, Cuxhaven), an Manfred
- **Hinweis:** Interne Ersteinschätzung (Frontdesk-Triage), **kein QA-Ergebnis**, keine Codeänderung.

---

### Ticket: Kunde fordert Portal-Anbindung über ImmoScout24 hinaus (Immowelt, Immonet) + Marktrecherche/Partnerschaft

**Kurzbefund:** Kein Systemfehler — strategische Feature-/Roadmap-Anfrage.
Weder Benutzerfehler noch Bug: Das CRM unterstützt aktuell bewusst nur die ImmoScout24-Schnittstelle. Der Kunde sieht darin ein Klumpenrisiko (Abhängigkeit/Monopol) und bittet um (a) Recherche zu Schnittstellen von Immowelt und Immonet und (b) Prüfung einer möglichen späteren Zusammenarbeit mit Immowelt (Argument: dort fehle das Versenden des vollständigen Exposés bei einer Anfrage).

**Eingrenzung:** Kein App-Fehler — daher keine Schicht/Modul-Zuordnung.
Betroffener Produktbereich wäre bei Umsetzung: Backend-Integrationen / Portal-Export (heute IS24-spezifisch). Umfang = neues Feature-Vorhaben, gehört über `/abc-requirements` in die Feature-Planung, nicht in einen Bugfix.

**Dringlichkeit:** Niedrig.
Kein Defekt, kein Datenverlust-/DSGVO-Risiko, kein Nutzer ist blockiert — bestehende IS24-Anbindung funktioniert. Ticket-Priorität im System bereits `low`. Strategisch relevant (Anbieter-Lock-in), aber zeitlich unkritisch; gehört in eine Roadmap-/Requirements-Diskussion, nicht in die akute Bearbeitung.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre ausführliche Einschätzung — das Thema Unabhängigkeit von einem einzelnen Portal verstehen wir gut und nehmen es ernst.
>
> Wir nehmen Ihren Wunsch als Roadmap-Punkt auf: Wir schauen uns an, welche Schnittstellen Immowelt und Immonet (bzw. deren gemeinsame Plattform) für die Objektübertragung anbieten, und prüfen, was eine Anbindung zusätzlich zu ImmoScout24 bedeuten würde. Sobald wir dazu eine belastbare Einschätzung haben (Machbarkeit, Aufwand, mögliche Reihenfolge), melden wir uns mit einem konkreten Vorschlag bei Ihnen.
>
> Den Gedanken einer möglichen Zusammenarbeit mit Immowelt und den Punkt „vollständiges Exposé bei Anfragen" notieren wir uns gesondert für dieses Gespräch.
>
> Die bestehende ImmoScout24-Anbindung ist davon nicht betroffen und läuft unverändert weiter.
>
> Beste Grüße

**Rückfragen-Guidance:** Für die Priorisierung wäre hilfreich: Bis wann bzw. mit welcher Dringlichkeit braucht der Kunde die Zweit-Portal-Anbindung (konkretes Projekt/Deadline oder „irgendwann")? Welches Portal hat Vorrang — Immowelt oder Immonet? Nutzt der Kunde diese Portale heute schon manuell (dann Vergleichsdaten zum Datenmodell vorhanden)? Gibt es bereits einen Kontakt bei Immowelt für die Partnerschafts-Idee? Diese Punkte fehlten im Ticket und entscheiden über Roadmap-Einordnung.

---

**Gesamtübersicht:** Portal-Schnittstellen Immowelt/Immonet → Kein Systemfehler (Feature-/Roadmap-Anfrage) → Niedrig. Nächster Schritt: `/abc-requirements` für ein Feature „Portal-Export über IS24 hinaus" anlegen; kein Bugfix, kein `/abc-qa`.
