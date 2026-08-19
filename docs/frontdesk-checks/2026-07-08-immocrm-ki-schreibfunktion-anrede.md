# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #84)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint a9bb375f (Freshdesk #84) — "KI Schreibfunktion" | Übergreifendes Problem: KI-Schreibassistent (PROJ-14) verwandelt informelle Anrede systematisch in Sie-Form | Mittel |

---

### Ticket: Peppermint-Ticket "KI Schreibfunktion" (Peppermint a9bb375f-05bb-4d1a-9c37-d2717290ecd7, Freshdesk #84, Absender: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Firat Erol schreibt seine Texte extern mit ChatGPT (Prompt: "Hallo kannst Du meinen
Text verbessern") und fügt sie dann in die App ein. Wenn er dort die KI-Schreibfunktion nutzt,
wird eine informelle Anrede wie "Hallo Manfred" konsequent in die Sie-Form umgewandelt — er möchte
wissen, ob sich das einstellen lässt. Zwei Word-Dokumente als Beispiel liegen dem Ticket bei
(`Mein Text.docx`, `Mein Text -2.docx`, Freshdesk-Attachments, nicht abgerufen).

**Eingrenzung:** Backend · Modul: KI-Schreibassistent (`immo-crm`, PROJ-14, Deployed)
Code-Grep bestätigt einen echten, übergreifenden Bug, keinen Benutzerfehler:
- `backend/app/services/ai_service.py:131-136` (`rewrite_text`) erkennt zwar informelle
  Anreden ("hallo", "hey", "hi", "moin", "guten tag") in der ersten Zeile und schaltet den
  System-Prompt auf einen lockeren Ton (`email_casual`, Zeilen 53-58: "Behalte die informelle
  Anrede … bei").
- Aber: **jeder** "Verbessern"-Button im Frontend (`lib/features/messages/messages_screen.dart`,
  `lib/features/email/email_screen.dart`) ruft `AiApi.rewriteText` fest verdrahtet mit
  `tone: 'professional'` auf — es gibt keine UI-Auswahl für andere Töne, obwohl das Backend
  `friendly`/`casual`/`shorter`/`longer`/`formal` unterstützt.
- `tone: 'professional'` löst in `ai_service.py:149` die User-Anweisung "Schreibe den Text
  professioneller und **formeller** um" aus — das überschreibt die im System-Prompt eigentlich
  vorgesehene Beibehaltung der informellen Anrede. Ergebnis: Die App instruiert das Modell
  widersprüchlich (System-Prompt: "locker bleiben" vs. User-Prompt: "formeller machen"), und in
  der Praxis gewinnt die explizite "formeller"-Anweisung.
- Das betrifft nicht nur diesen Kunden: Jeder Nutzer, der einen informell begonnenen Text über
  die KI-Funktion "verbessern" lässt, bekommt denselben Effekt, da der Ton clientseitig nie
  konfigurierbar ist.

**Dringlichkeit:** Mittel
Kein Datenverlust-, DSGVO- oder Blocker-Fall (Kunde kann seinen Text einfach unverändert
übernehmen), aber es ist ein systemischer Bug in einer Kernfunktion (KI-Schreibassistent, PROJ-14),
der die Funktion für jeden Nutzer mit informellem Schreibstil unbrauchbar für ihren eigentlichen
Zweck macht. Freshdesk-Priorität "low" wirkt daher etwas zu niedrig angesetzt; eher Mittel, da
kein Blocker, aber ein wiederkehrendes Ärgernis mit klarem Fix-Ansatz (Tonauswahl im UI ergänzen
oder Default auf "casual"/kontextsensitiv setzen statt hart "professional").

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre ausführliche Rückmeldung und die beigefügten Beispiele. Sie haben recht:
> Die KI-Schreibfunktion wandelt aktuell auch informell begonnene Texte (z. B. "Hallo Manfred")
> grundsätzlich in eine formelle Sie-Anrede um, da der "Verbessern"-Button derzeit immer auf einen
> möglichst professionellen, formellen Ton eingestellt ist — eine Einstellmöglichkeit für einen
> lockereren Ton gibt es dafür aktuell noch nicht. Wir prüfen, wie wir hier eine Auswahlmöglichkeit
> ergänzen können, und melden uns, sobald wir mehr dazu wissen.

**Rückfragen-Guidance:** keine zwingend nötigen offenen Punkte — die Beschreibung und die zwei
Beispieldokumente reichen für eine klare Einordnung. Für die spätere Fix-Priorisierung optional
interessant: Nutzt er ausschließlich den E-Mail-Kanal, oder auch WhatsApp/interne Notizen, bei
denen der gleiche Effekt auftreten könnte?

---
