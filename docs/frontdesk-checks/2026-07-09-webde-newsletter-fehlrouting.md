# Frontdesk-Triage — 2026-07-09

Quelle: Peppermint-Ticket-Notification
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint eb462ad6 — "Traumhaus auf Amrum gewinnen – 16 Lose nur 8 €¹!" | Kein Support-Ticket — WEB.DE-Marketing-Newsletter, fehlgeleitet ins Ticketsystem | Niedrig |

---

### Ticket: Peppermint-Ticket "Traumhaus auf Amrum gewinnen – 16 Lose nur 8 €¹!" (Peppermint eb462ad6-eac3-409a-94fa-510461a91f48, Absender: WEB.DE informiert <neu@mailings.web.de>)

**Kurzbefund:** Kein Systemfehler und keine Kundenanfrage. Der komplette Inhalt ist ein
generischer WEB.DE-Marketing-Newsletter (Lotto-Verlosung "Traumhaus Amrum", Games-Werbung,
Magazin-Tipps, Rabattcodes) mit automatisiertem "Antwort nicht möglich"-Hinweis im Footer. Es
gibt keinen Bezug zu ImmoCRM/Jupiter — der Newsletter richtet sich an einen "Herrn Schmitz" als
WEB.DE-Endkunden und wurde offenbar nur an eine Adresse zugestellt, die ins Peppermint-Ticketsystem
einläuft (z. B. eine allgemeine Support-/Postfach-Adresse, die WEB.DE-Newsletter abonniert hat).
Es handelt sich um ein reines Zustellungs-/Routing-Artefakt, kein Produktproblem.

**Eingrenzung:** entfällt — keine App-Komponente betroffen, daher kein Frontend/Backend/DB-Modul
zuzuordnen.

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug, kein blockierter Kunde, keine echte Support-Anfrage.
Einzige relevante Handlung ist organisatorisch (Ticket schließen, ggf. Newsletter-Absender vom
eingehenden Postfach abbestellen/filtern), nicht technisch dringend.

**Antwortentwurf an den Kunden:**
> Es handelt sich um eine automatisiert versendete Marketing-Mail von WEB.DE, keine Kundenanfrage
> an unseren Support. Der Absender weist im Footer selbst darauf hin, dass auf diese Adresse keine
> Antwort möglich ist. Das Ticket wird ohne weitere Rückmeldung geschlossen.

**Rückfragen-Guidance:** Keine — die Einstufung ist eindeutig anhand des Inhalts, es fehlen keine
Informationen. Sinnvoll wäre lediglich zu klären, über welches Postfach/welche Regel dieser
Newsletter überhaupt in Peppermint gelandet ist, damit sich das Fehlrouting künftig automatisch
herausfiltern lässt — das ist aber eine Postfach-/Weiterleitungskonfiguration außerhalb des Codes,
kein Bug-Ticket.

---

Nächster Schritt bei Bedarf: Keiner code-/produktseitig. Ticket kann geschlossen werden; optional
prüfen, ob die eingehende Adresse den WEB.DE-Newsletter abbestellen oder eine Filterregel vor
Peppermint bekommen sollte, um wiederkehrendes Rauschen zu vermeiden.
