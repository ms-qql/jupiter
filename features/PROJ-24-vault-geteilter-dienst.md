# PROJ-24: Vault als geteilter Dienst (auch für eingebettete Apps)

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #14
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-2 (Vault-Anbindung als Dienst) — dieses Feature **öffnet** die bestehende interne Vault-Anbindung als allgemein nutzbaren Dienst.
- Requires: PROJ-15 (Vault Stufe 3 / roh↔kuratiert) — geteilter Lese-/Schreib-/Suchzugriff soll die kuratierte Wissensschicht respektieren.
- Verwandt: PROJ-18 (Weitere Engines + iFrame/Launch) — eingebettete/fremde Apps (#13) sind die Hauptkonsumenten dieses Dienstes.
- Verwandt: PROJ-25 (Auth/RLS) — ein **geteilter** Dienst braucht Zugriffskontrolle pro Konsument; ohne PROJ-25 nur token-loser Single-User-Betrieb.

## Beschreibung
Heute ist die Vault-Anbindung (lesen/schreiben/suchen) **intern** für Jupiters Sessions gebaut (PROJ-2). Dieses Feature hebt sie zu einem **geteilten Dienst mit stabilem Vertrag**, den auch **eingebettete/fremde Apps** (z. B. über iFrame oder Launch-Button eingebundene Tools, #13) nutzen können — die **gemeinsame Datenschicht der ganzen Kommandozentrale**.

Der Vault bleibt **offenes MD** (Obsidian/PARA, `/home/dev/tools/Hal`) — der Dienst legt nur eine **saubere, versionierte API** darüber (lesen / schreiben / suchen / Pointer auflösen), damit nicht jede App ihre eigene, inkonsistente Vault-Logik nachbaut. Eine Wahrheit, viele Konsumenten.

**Grundhaltung:** Der Vault ist die einzige Wahrheit; der geteilte Dienst macht diese Wahrheit für die ganze Plattform konsumierbar, ohne sie zu duplizieren oder zu verstecken.

## User Stories
- Als Betreiber möchte ich, dass eine **eingebettete App** über eine definierte API im Vault lesen/schreiben/suchen kann, ohne eigene Vault-Logik zu implementieren.
- Als Betreiber möchte ich einen **stabilen, versionierten API-Vertrag** für den Vault-Dienst, damit Konsumenten nicht bei jeder internen Änderung brechen.
- Als Betreiber möchte ich pro Konsument festlegen, **welche Bereiche** des Vaults er sehen/schreiben darf (Scope), damit eine eingebettete App nicht den ganzen Vault aufmacht.
- Als Betreiber möchte ich **Pointer** statt Volltext zurückgeben können, damit Konsumenten kontextsparsam arbeiten (#23-Linie).
- Als Betreiber möchte ich nachvollziehen, **welcher Konsument wann was** geschrieben hat (Audit), da nun mehrere Quellen schreiben.

## Acceptance Criteria
- [ ] Es gibt einen **eigenständigen Vault-Dienst** mit dokumentierter API für mindestens: **lesen** (Datei/Ausschnitt), **schreiben/anhängen**, **suchen**, **Pointer auflösen**.
- [ ] Die API ist **versioniert** (z. B. `/vault/v1/...`); Brüche am internen Vault-Layout schlagen nicht ungefiltert auf Konsumenten durch.
- [ ] **Eingebettete Apps** (PROJ-18 / #13) können den Dienst nutzen; ein dokumentiertes Beispiel-Konsumenten-Setup existiert.
- [ ] Pro Konsument ist ein **Scope** konfigurierbar (welche Vault-Pfade lesbar/schreibbar) — kein Vollzugriff per Default.
- [ ] Schreibzugriffe tragen **Herkunft** (welcher Konsument/`owner`) und sind im Vault als Spur nachvollziehbar (Audit).
- [ ] Der Vault bleibt **offenes MD** — der Dienst fügt keine Binär-/Black-Box-Schicht ein; Dateien bleiben direkt les-/editierbar.
- [ ] Lese-Antworten unterstützen **Pointer/Ausschnitt** statt nur Volltext (kontextsparsam).
- [ ] Gleichzeitige Schreibzugriffe sind **konfliktsicher** (kein stilles Überschreiben — siehe Edge Cases).
- [ ] Alle Texte/Fehlermeldungen deutsch.

## Edge Cases
- **Zwei Konsumenten schreiben dieselbe Datei** → konfliktsicher (Append/Locking/Versionsprüfung); kein Last-Write-wins-Datenverlust.
- **Konsument schreibt außerhalb seines Scopes** → abgelehnt mit klarer Fehlermeldung, kein Teil-Schreib.
- **Vault-Pfad existiert nicht / Tippfehler im Pointer** → sauberer 404-äquivalenter Fehler, kein Crash, kein versehentliches Anlegen am falschen Ort.
- **Große Datei** → Ausschnitt/Pointer statt Volltext; harte Größengrenze mit klarer Meldung.
- **Vault temporär nicht erreichbar** (FS/Mount weg) → Dienst meldet Degradation; Konsumenten erhalten klaren Fehler statt Hänger.
- **Schädlicher Pfad** (`../`, absolute Pfade, Symlink-Ausbruch) → Path-Traversal wird verhindert; nur innerhalb des erlaubten Scopes.
- **Ohne PROJ-25 (kein Auth)** → Dienst läuft im Single-User-Modus ohne Token; bei Mehrnutzer/Team **muss** Scope an echte Identität gebunden werden (klar dokumentiertes Vorbedingung).

## Technical Requirements (optional)
- Refaktoriert die interne PROJ-2-Anbindung hinter eine **stabile Service-Fassade**; interne Aufrufer migrieren auf denselben Vertrag (eine Quelle der Wahrheit).
- **Path-Traversal-Schutz** und Scope-Enforcement serverseitig; Pfade nie ungeprüft aus Konsumenten-Payload.
- **Pointer-First**-Antworten (konsistent mit #23) zur Kontextsparsamkeit.
- Audit-Spur der Schreibzugriffe (Herkunft/`owner`/Zeit) — passt zur Identitäts-Linie #21 und bereitet PROJ-25 vor.
- Bleibt dateibasiert/offenes MD; keine DB als Wahrheitsquelle (Postgres bleibt Live-Index).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
