# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #148)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint a8569e07 (Freshdesk #148) — "ImmoCRM - Verknüpfung Kunde" | **Korrigiert (2026-08-11):** kein Benutzerfehler — Funktion existiert im Live-UI nicht. Fehlendes Feature, kein Bug | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCRM - Verknüpfung Kunde" (Peppermint a8569e07-30ab-4c80-9459-30da5ab61125, Freshdesk #148, Absender: Auxevo Support/Freshdesk-Weiterleitung)

**Kurzbefund:** Wunsch: eine eingehende Bank-Mail (Unterlagenanforderung) soll mit dem
zugehörigen Käufer verknüpft werden können.

> **Überarbeiteter Befund (abc-backoffice, 2026-08-11):** Die ursprüngliche Einschätzung unten
> (Funktion existiert, nur versteckt im "⋮"-Menü) ist **falsch** und zurückgezogen. Der
> Code-Grep-Treffer lag in `lib/features/messages/messages_screen.dart` — das ist **toter Code**.
> Route `/messages` redirected serverseitig sofort auf `/email`
> (`lib/core/router/app_router.dart:204-211`), das Widget wird nirgends gebaut/importiert
> (Faktum bereits seit PROJ-91, 2026-06-30 dokumentiert, hier nur nicht beachtet). Das echte
> Live-UI (Sidebar „E-Mail" → `email_screen.dart`, Sidebar „Kommunikation" →
> `kunden_neu_screen.dart`/`clients_mailview`) hat **keine** "Kunde zuordnen"-Funktion. Der Kunde
> hatte recht: er hat die Funktion nicht gesehen, weil sie nicht da ist.
>
> Root-Cause: manuelles Mail↔Kunde-Verknüpfen ist im Spec `PROJ-41` explizit als Out-of-Scope
> benannt und nach `PROJ-38-email-verlauf-cross-user-visibility.md` verschoben — Status dort:
> **On Hold**. Kein Bug, sondern eine zurückgestellte Anforderung. Backend-Endpoint `PATCH
> /conversations/{conversation_id}/assign-client` (`messaging.py:845`) existiert und funktioniert,
> ist vom Frontend aus aber nicht erreichbar.
>
> Fix-Bericht + Korrektur: `abc-backoffice`-Lauf zu Jupiter-Ticket 1006 (2026-08-11). Hal-Vault:
> `gotcha-immo-crm-a8569e07-messages-screen-dead-code.md`. Nächster Schritt: neues Feature über
> `/abc-requirements` (Nutzer plant das separat), keine Kundenantwort mehr im Sinne von "gibt es
> schon".

**Eingrenzung (korrigiert):** Frontend · fehlende Funktionalität, kein Bug. Live-Screens
`lib/features/email/email_screen.dart` und `lib/features/clients_mailview/` (immo-crm-Repo).
`lib/features/messages/messages_screen.dart` ist toter Code — nicht mehr als Fundstelle
verwenden.

**Dringlichkeit:** Niedrig
Keine Kernfunktion blockiert, keine Datenintegrität betroffen — echtes Feature-Gap, aber mit
Workaround (Backend-Endpoint ließe sich künftig anbinden) und ohne akuten Business-Impact.

**Antwortentwurf an den Kunden (korrigiert):**
> Guten Tag,
>
> vielen Dank für Ihre Nachricht und Entschuldigung für die verzögerte Antwort. Nach genauerer
> Prüfung müssen wir uns korrigieren: Eine eingehende E-Mail manuell mit einem Käufer/Kunden zu
> verknüpfen, ist in ImmoCRM aktuell **noch nicht** möglich — Sie haben also nichts übersehen.
> Wir haben das als Feature-Wunsch aufgenommen und planen die Umsetzung. Sobald es verfügbar ist,
> melden wir uns bei Ihnen.
>
> Freundliche Grüße

**Rückfragen-Guidance:** entfällt — Ursache ist geklärt (fehlendes Feature, kein Reproduktionsfall
beim Kunden nötig).

---

**Original-Einschätzung vom 2026-07-08 (zurückgezogen, nur zur Nachvollziehbarkeit erhalten):**

Code-Grep-Befund:
- Backend-Endpoint existiert bereits: `PATCH /conversations/{conversation_id}/assign-client`
  (`backend/app/routes/messaging.py:845`) setzt `client_id` an der Conversation.
- Frontend nutzt ihn bereits: Aktion **"Kunde zuordnen"** je Konversation
  (`messages_screen.dart:1731` Popup-Menü bzw. `:1746` IconButton, Icon `LucideIcons.link`),
  ruft `MessageApi.assignClient(conv.id, ...)` auf (`:629`).
- Die Funktion ist vorhanden, sitzt aber im "⋮"-Aktionsmenü der Konversation (bzw. als kleines
  Link-Icon daneben) statt prominent sichtbar — daher plausibel, dass der Melder sie schlicht
  nicht gefunden hat, nicht dass sie fehlt.
- Kein Treffer in `features/INDEX.md` für eine offene Lücke zu diesem Modul (anders als z. B.
  PROJ-Cluster zur Objekt↔Eigentümer-Verknüpfung, die tatsächlich fehlt).
- Nicht live geprüft — Einschätzung basiert auf Code-Analyse.

**Fehler in der Original-Analyse:** Der Code-Grep hat nicht geprüft, ob `messages_screen.dart`
über Routing/Sidebar überhaupt erreichbar ist — war es nicht (siehe korrigierter Befund oben).
