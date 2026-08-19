# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #60)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 3cd38518 (Freshdesk #60) — "Bild in der Signatur wird nicht angezeigt" | Übergreifendes Verhalten: Namensduplikation strukturell durch Signatur-Design bedingt; Bildanzeige ohne Live-Check nicht abschließend zu klären | Niedrig |

---

### Ticket: Peppermint-Ticket "Bild in der Signatur wird nicht angezeigt" (Peppermint 3cd38518-3613-48f5-ab4e-b6573b9aa8dd, Freshdesk #60, Absender: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Zwei Beobachtungen in einem Ticket:
1. Das Bild in der E-Mail-Signatur wird beim Kunden nicht angezeigt.
2. Der Name "Firat Erol" erscheint doppelt — einmal in der von ihm selbst getippten Grußzeile
   ("Mit freundlichen Grüßen Firat Erol") und einmal im automatisch eingefügten Signaturblock,
   der ebenfalls mit "Firat Erol" beginnt. Er möchte den Namen aus dem eingebauten Block entfernt
   haben.

**Eingrenzung:** Backend (Python/FastAPI) — **Projekt `immo-crm`, nicht Jupiter.** Der Kunde
nutzt die Domain `crm.erol.msce.info`, hinter der das immo-crm-Backend liegt; Jupiter selbst hat
keine Signatur-/Agentenfoto-Funktion (per Codegrep bestätigt: keine Treffer für "Signatur",
"agent-photo" o. Ä. im Jupiter-Repo).

Code-Grep-Befund in `/home/dev/projects/immo-crm`:
- Öffentlicher Bild-Endpunkt `GET /api/public/agent-photo/{storage_key:path}`
  (`backend/app/main.py:5167-5185`), liest aus MinIO/Storage-Bucket
  `bucket_property_images`, wirft bei jeder Exception unspezifisch `404 Image not found`. Der im
  Ticket zitierte Bild-Link (`.../agent-photo/agents/5480ffa8.../20260318T...png`) folgt exakt
  diesem Muster — der Endpunkt existiert und ist ungeschützt (kein Auth), das Problem liegt also
  entweder am Objekt selbst (fehlt/gelöscht im Storage), an der Domain-Weiterleitung
  `crm.erol.msce.info` → Backend, oder — am wahrscheinlichsten — daran, dass Firat Erols
  E-Mail-Programm (z. B. Outlook) extern verlinkte Bilder standardmäßig blockt. Ohne Live-Zugriff
  auf sein Postfach/den Storage-Bucket lässt sich das nicht abschließend unterscheiden (siehe
  Nicht-Ziele dieses Skills — kein Login mit Kundendaten ohne Freigabe).
- Signatur-Zusammensetzung: `agents`-Tabelle hat Felder `email_signature_html` und
  `signature_mode`; die Foto-Einbettung passiert serverseitig beim Versand
  (`backend/app/services/email_service.py:4421-4449`, Kommentar "MAIL-07") per Regex-Suche nach
  einem `<hr style="...border-top...">`-Trenner, hinter den die Bild-Tabelle eingefügt wird.
  Zusätzlich baut `_build_signature_with_photo()` (`email_service.py:2895-2911`) für Auto-Replies
  denselben Aufbau. Der im Ticket zitierte Signaturblock (Name, Titel, Firmendaten, Bild) entspricht
  strukturell `email_signature_html` — dieses Feld enthält den Agentennamen offenbar fest als erste
  Zeile. Da Nutzer zusätzlich manuell "Mit freundlichen Grüßen \<Name\>" tippen, erscheint der Name
  zwangsläufig doppelt. Das ist kein Einzelfall-Datenfehler, sondern betrifft strukturell jeden
  Agenten, der die automatische Signatur nutzt und zusätzlich manuell grüßt — daher als
  "übergreifendes Verhalten" statt Einzelfall eingestuft, auch wenn bisher nur eine Meldung vorliegt.

**Dringlichkeit:** Niedrig
Kein Datenverlust-/DSGVO-Risiko, keine Blockade (Kunde kann weiter Mails senden/empfangen), rein
kosmetisch/komfortbezogen. Deckt sich mit der von Freshdesk gesetzten Priorität "low".

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Nachricht. Zu beiden Punkten:
>
> Dass das Bild in der Signatur bei Ihnen nicht angezeigt wird, liegt häufig daran, dass
> E-Mail-Programme wie Outlook extern verlinkte Bilder standardmäßig blockieren — in dem Fall
> reicht es meist, das Bild einmalig über "Bilder anzeigen" freizugeben. Sollte es danach immer
> noch nicht erscheinen, prüfen wir das gerne zusätzlich auf unserer Seite.
>
> Den doppelten Namen können wir nachvollziehen: Da Sie in Ihren E-Mails selbst
> "Mit freundlichen Grüßen Firat Erol" schreiben und die automatische Signatur den Namen ebenfalls
> enthält, taucht er zweimal auf. Wir nehmen das als Verbesserungswunsch auf, damit der Name im
> automatischen Signaturblock künftig weggelassen werden kann.
>
> Wir melden uns, sobald wir mehr wissen bzw. es umgesetzt ist.
>
> Mit freundlichen Grüßen

**Rückfragen-Guidance:** Für eine sichere Klärung des Bild-Problems wäre hilfreich zu wissen:
welches E-Mail-Programm/welcher Client bei ihm verwendet wird, ob "Bilder anzeigen" testweise
aktiviert wurde, und ob das Bild auch in der immo-crm-eigenen Signatur-Vorschau (Agenten-Profil)
fehlt oder nur in extern versendeten Mails. Für die Namensduplikation ist keine weitere Rückfrage
nötig — der Wunsch ist eindeutig (Name aus dem automatischen Block entfernen); zu klären wäre nur
im Rahmen von `/abc-requirements`, ob das über das bereits vorhandene Feld `signature_mode`
konfigurierbar gemacht werden soll oder generell entfernt wird.

---

Nächster Schritt bei Bedarf: Ticket gehört ins `immo-crm`-Projekt, nicht Jupiter — dort ggf.
`/abc-requirements` für "Signaturblock ohne Namenszeile (konfigurierbar via `signature_mode`)" und
ein kurzer manueller Check des Storage-Objekts/der Domain-Weiterleitung für das Bild-Problem.
