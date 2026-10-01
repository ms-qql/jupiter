# Frontdesk-Check — Immo-CRM: falsches Titelbild im Homepage-Export

- **Datum des Laufs:** 2026-08-27
- **Quelle:** Peppermint-Ticket `d076423c-a731-4c79-99b4-ea8763342975` (Freshdesk #157), gemeldet von einem Mitarbeiter für Erol Immobilien
- **Hinweis:** Interne Ersteinschätzung (Frontdesk-Triage), **kein** QA-Ergebnis. Kein Code-Repro möglich — das Jupiter-Repo enthält den Immo-CRM-Code nicht; Einschätzung stützt sich rein auf Ticketinhalt + Domänenlogik.

---

## Gesamtübersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Falsches Titelbild (fremdes Werbebild) auf Erol-Homepage, nur dieser eine Kanal, „manchmal", nach Exposé-Regenerierung weg | Übergreifendes Problem (latent, seltene Auslösung) | Mittel |

---

### Ticket: Immobilien auf der Erol-Homepage zeigten ein fremdes Werbebild als Titelbild; ImmoScout + IMMOCRM korrekt; nach Exposé-Neugenerierung behoben

**Kernfakten aus dem Ticket:**
- Melder: `b.rutkowska@erolimmobilien.de` (Mitarbeiter), Mandant `00000000-0000-0000-0000-000000000001`
- Bezug Immobilie: `c663d2e5-12a5-4f4e-a1c8-2bc0361bcca7` (nur eine ID genannt — unklar, ob nur diese oder mehrere Objekte betroffen)
- Symptom: Auf der Homepage von Erolimmobilien wurde bei Objekten ein falsches Titelbild angezeigt — konkret „Firat seine Werbesbild" (Werbebild eines anderen Maklers/Objekts).
- Nur der Kanal **Homepage** betroffen; **ImmoScout** und **IMMOCRM-Ansicht** zeigten das richtige Bild.
- Reproduzierbarkeit: „manchmal". Dringlichkeit laut Melder: niedrig. Version v0.14.2.
- Bereits gemacht: Exposés neu generiert → seitdem wieder korrekt.

**Kurzbefund:** Übergreifendes Problem (latent)
Kein Benutzerfehler — das System hat ein fremdes Asset in einen Ausgabekanal geschrieben. Die auslösende Vorbedingung (kanal-spezifische Titelbild-/Asset-Zuordnung bei der Homepage-/Exposé-Generierung) ist kein Anomalie-Einzeldatensatz, sondern ein Mechanismus, der bei jedem Objekt unter gleicher Konstellation genauso danebengreifen kann. Dass bisher nur eine Meldung vorliegt und es sich selbst „reparierte", ändert die Einstufung nicht — die seltene, schwer greifbare Auslösung („manchmal") spricht eher für eine Race-Condition / veralteten Cache / falsch aufgelöste Asset-Referenz im Generierungsschritt.

**Eingrenzung:** Schicht: Backend · Modul: Immobilien → Exposé-/Homepage-Export (Titelbild-/Medien-Zuordnung pro Ausgabekanal)
Stütze: Der Fehler tritt genau in **einem** Kanal auf, während die anderen Kanäle und die CRM-Ansicht dasselbe Objekt korrekt darstellen → das gemeinsame Objekt-/Medienmodell ist wahrscheinlich intakt, der Fehler sitzt im kanal-spezifischen Rendering/Publishing der Homepage bzw. in einer davorgelagerten Cache-/Referenz-Auflösung. „Nach Regenerieren weg" passt zu stale/falsch gecachtem Titelbild-Verweis. Nicht live geprüft (Code liegt außerhalb dieses Repos).

**Dringlichkeit:** Mittel
Kernkriterien: (a) **öffentlich sichtbar** — falsches Bild auf der Live-Homepage des Kunden, dazu ein *fremdes* Werbebild (mögliche Marken-/Fremddaten-Vermischung nach außen), das hebt es über „Niedrig". (b) Aktuell **behoben**, **selten**, **kein Datenverlust**, **Workaround vorhanden** (Regenerieren), Melder stuft niedrig ein — das hält es unter „Hoch". Wenn eine zweite Meldung reinkommt oder das Muster reproduzierbar wird → hochstufen und an `/abc-qa`.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> danke für die Rückmeldung und dafür, dass Sie das direkt geprüft haben. Gut zu hören, dass nach dem erneuten Generieren der Exposés wieder das richtige Titelbild auf der Homepage steht.
>
> Wir schauen uns an, warum bei diesem einen Ausgabekanal (Homepage) zeitweise ein falsches Titelbild ausgespielt wurde, während ImmoScout und die CRM-Ansicht korrekt waren. Eine Ursache können wir noch nicht nennen — sobald wir mehr wissen, melden wir uns.
>
> Falls es noch einmal auftritt, helfen uns diese Angaben sehr: bei welchen Objekten genau, ungefährer Zeitpunkt, ein Screenshot der Homepage im fehlerhaften Zustand, und ob nur das Exposé oder auch die Homepage neu veröffentlicht wurde. Bitte einmal kurz auch mit geleertem Browser-Cache (Strg+F5) gegenprüfen.
>
> Viele Grüße
> Ihr Immo-CRM-Support

**Rückfragen-Guidance:** Für dieses Ticket fehlten: (1) ob nur Objekt `c663d2e5-…` oder mehrere betroffen waren; (2) ungefährer Zeitpunkt/Zeitraum der falschen Anzeige und wann zuletzt vor dem Fehler die Homepage/das Exposé generiert wurde; (3) Screenshot des fehlerhaften Homepage-Zustands; (4) Name/ID des „Firat"-Objekts, dessen Werbebild auftauchte (zeigt, ob es ein Nachbar-Datensatz, dasselbe Bild-Asset oder ein globaler Werbe-Slot ist); (5) ob der Browser-/CDN-Cache als Ursache ausgeschlossen wurde (Hard-Reload, anderes Gerät); (6) „manchmal" — schon früher beobachtet, wie oft?
