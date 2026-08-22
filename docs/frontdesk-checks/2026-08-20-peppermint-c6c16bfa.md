# Frontdesk-Check — 2026-08-20

Quelle: Peppermint-Ticket-Weiterleitung, ID `c6c16bfa-88e9-42db-b973-3f0cfee176dc`, ursprünglich
Freshdesk-Ticket #152 von Auxevo Support (support@auxevo.freshdesk.com), Absender im Ticketinhalt
Firat Erol (Erol Immobilien GmbH). Interne Ersteinschätzung, kein QA-Ergebnis.

---

### Ticket: Kunde fehlt im CRM + Provisionsklausel widerspricht Exposé (Freshdesk #152)

**Kurzbefund:** Kein Jupiter-Systemfehler. Das Ticket betrifft eine andere Anwendung
(`crm.erol.msce.info`, Kunden-/Maklerprogramm), nicht diesen Codebase — `docs/architektur.md` und
`features/INDEX.md` enthalten keinerlei Treffer zu "Kunde", "Kundenanfrage", "Exposé" oder
"Provision/Maklercourtage". Es handelt sich um zwei vermischte Beobachtungen: (1) ein Kunde samt
seiner Anfrage ist im dortigen Programm nicht auffindbar, obwohl er zugestimmt hat; (2) inhaltlicher
Widerspruch zwischen Exposé (Verkäufer trägt Courtage) und Bestätigungsdokument (Käufer stimmt der
Provision bei Beurkundung zu) — letzteres ist eine Vertragsinhalt-Frage, kein Software-Bug.

**Eingrenzung:** — (nicht in diesem Repo/Codebase verortbar; anderes System)

**Dringlichkeit:** Mittel
Kein Kernsystem-Ausfall und keine akute Blockade in Jupiter selbst; aber (1) im Ziel-CRM fehlender
Kundendatensatz trotz erteilter Zustimmung ist ein Datenintegritäts-/Consent-Risiko, (2) der
Courtage-Widerspruch ist vertraglich relevant und sollte vor Beurkundung geklärt werden.

**Antwortentwurf an den Kunden:**
> Moin Manfred, danke für die Weiterleitung. Zwei Punkte trennen wir am besten: Erstens der fehlende
> Kunde samt Anfrage im Programm — dafür bräuchten wir kurz die genaue Kunden-ID bzw. den Namen, wie
> er im System angelegt sein sollte, sowie Datum/Uhrzeit der Zustimmung, damit wir gezielt nachsehen
> können. Zweitens der Widerspruch zwischen Exposé (Verkäufer trägt die Courtage) und der
> Bestätigung (Käufer stimmt der Provision bei Beurkundung zu) — das ist inhaltlich zu klären, bevor
> es zur Beurkundung geht; bitte kurz bestätigen, welche Fassung gilt. Wir melden uns, sobald wir den
> Datensatz geprüft haben.

**Rückfragen-Guidance:** Um welches System handelt es sich genau (crm.erol.msce.info — ist das ein
Jupiter-Mandant oder eine externe Anwendung)? Name/ID des gesuchten Kunden statt nur "der Kunde";
Zeitpunkt der Zustimmung; wurde die Suche im Programm mehrfach/mit anderen Suchbegriffen versucht;
welche der beiden Provisionsregelungen (Exposé vs. Bestätigung) ist die rechtsverbindliche Fassung.

---

**Übersicht:** Kunde fehlt im CRM + Provisionswiderspruch (#152) → Kein Jupiter-Bug (anderes System) → Dringlichkeit Mittel
