# PROJ-25: Echtes Auth (JWT) + Scope/RLS auf `owner`

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #21 (Ausbau)
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung) — Vault-Schreib-/Lesezugriffe müssen an echte Identität/Scope gebunden werden.
- Requires: PROJ-24 (Vault als geteilter Dienst) — ein geteilter Dienst braucht echte Zugriffskontrolle; ohne sie bleibt er Single-User.
- Verwandt: ALLE Features mit `owner`-Feld — dieses Feature **aktiviert** das seit Tag 1 mitgeführte `owner`-Feld (#21) zu echtem Auth + Scope, statt es weiter als reines Etikett zu führen.
- Verwandt: PROJ-3 (Cockpit), PROJ-22 (Dispatch) — Sessions/Tickets werden nach Eigentümer sichtbar/filterbar.

## Beschreibung
Das MVP ist bewusst **single-user, ohne echtes Auth/RLS** — es trägt nur ein `owner`-Feld auf jedem Artefakt (Session/Handover/Wissensnotiz), damit die spätere Team-Migration billig bleibt (#21). Dieses Feature **macht aus dem Etikett echte Zugriffskontrolle**: **JWT-Login** (mehrere Nutzer) + **Scope/Row-Level-Security auf dem `owner`-Feld**, sodass jeder Nutzer nur seine eigenen Sessions/Handovers/Wissensnotizen sieht und ändert — und der geteilte Vault-Dienst (PROJ-24) pro Identität greift.

Damit wird Jupiter **teamfähig**, ohne das Datenmodell umzubauen: Das `owner`-Feld existiert überall schon; hier kommt die Durchsetzung dazu.

**Grundhaltung:** Identität war von Tag 1 da (#21); dieses Feature schaltet die Durchsetzung scharf — minimaler Umbau, maximaler Migrationsschutz.

## User Stories
- Als Nutzer möchte ich mich **anmelden** (JWT, kurzer Access- + längerer Refresh-Token) und danach nur **meine eigenen** Sessions/Artefakte sehen.
- Als Nutzer möchte ich, dass `owner` **immer aus dem Token** kommt, nie aus dem Client-Payload (Manipulationsschutz).
- Als Betreiber möchte ich, dass ein zweiter Nutzer **dieselbe Jupiter-Instanz** nutzen kann, ohne die Sessions/Wissensnotizen des anderen zu sehen oder zu ändern.
- Als Betreiber möchte ich, dass der **geteilte Vault-Dienst** (PROJ-24) Zugriffe an die echte Identität bindet (Scope pro Nutzer).
- Als Nutzer möchte ich, dass bestehende (vor dem Auth angelegte) Artefakte mit `owner = ich` **nahtlos weiter funktionieren** (Migration ohne Datenverlust).
- Als Betreiber möchte ich, dass **abgelaufene/ungültige Tokens** sauber zurückgewiesen werden und ein Refresh-Flow existiert.

## Acceptance Criteria
- [ ] **JWT-Login** existiert: kurzer Access-Token + längerer Refresh-Token; Standard-Schema (HS256) gemäß Stack-Konvention.
- [ ] **`owner` wird ausschließlich aus dem Token** gelesen — Client-Payload-`owner` wird ignoriert/abgelehnt.
- [ ] **Scope/RLS auf `owner`:** Lese-/Schreibzugriffe auf Sessions, Handovers und Wissensnotizen sind auf den eigenen `owner` beschränkt; Fremdzugriff liefert leer/403, nie fremde Daten.
- [ ] Der **geteilte Vault-Dienst** (PROJ-24) bindet Scope an die Token-Identität.
- [ ] **Migration:** vor dem Auth angelegte Artefakte (`owner` = bisheriger Single-User) bleiben für diesen Nutzer voll nutzbar; kein Datenverlust, keine verwaisten Artefakte.
- [ ] **Token-Ablauf** wird korrekt zurückgewiesen; ein **Refresh-Flow** verlängert ohne erneuten Login.
- [ ] Geschützte Endpunkte verlangen ein gültiges Token; öffentliche (Login/Refresh) sind klar abgegrenzt.
- [ ] Cross-Owner-**Red-Team-Test** bestätigt: Nutzer A kann Nutzer B's Sessions/Artefakte weder lesen noch ändern (auch nicht via ID-Raten oder Payload-Manipulation).
- [ ] Alle Texte/Fehlermeldungen deutsch.

## Edge Cases
- **Manipuliertes/gefälschtes Token** (Signatur, abgelaufen, `owner` umgeschrieben) → abgelehnt; nie Vertrauen in Payload-Claims ohne Signaturprüfung.
- **ID-Raten** (fremde session_id/Pfad direkt aufrufen) → 403/leer, kein Leak über Existenz/Inhalt.
- **Refresh-Token gestohlen/widerrufen** → Rotation/Invalidierung möglich; alter Refresh wird ungültig.
- **Bestandsdaten ohne klaren `owner`** (falls welche existieren) → einmalige, dokumentierte Migration weist sie dem Single-User zu; nichts wird unsichtbar.
- **Geteilter Vault-Pfad** (z. B. projektübergreifendes Wissen) → bewusst geteilte Bereiche sind explizit als „shared" markiert, nicht versehentlich für alle offen.
- **Erste Inbetriebnahme** (noch kein Nutzer) → klarer Bootstrap-Pfad für den ersten Account, kein offener Default-Zugang.
- **Engine-/Hintergrund-Sessions** (Koordinator/Spezialisten, PROJ-22) → laufen unter dem `owner` des startenden Nutzers; Kind-Sessions erben den Scope.

## Technical Requirements (optional)
- JWT HS256, `mandant_id`/`owner` **immer aus dem Token** (Stack-Konvention `rules/security.md`).
- **Achtung Jupiter-Override:** Das MVP nutzt bewusst **kein** JWT/RLS und ggf. **keine** klassische RLS-DB-Policy, sondern Scope-Enforcement in der Service-Schicht (siehe Memory „Stack-Overrides"). Architektur klärt: DB-RLS auf `owner` **oder** durchgängiges Service-Scoping — konsistent mit Jupiters In-memory/Datei-Ansatz.
- Scope greift sowohl auf den **Live-Index** (Sessions/Cards) als auch auf den **Vault-Dienst** (PROJ-24).
- Secrets via `pydantic-settings` + `.env`; nie hartkodiert.
- Migration der bestehenden `owner`-Etiketten zu echten Accounts dokumentiert und idempotent.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
