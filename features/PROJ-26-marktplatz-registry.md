# PROJ-26: Marktplatz/Registry für Rollen/Skills/Agenten

## Status: In Progress
**Created:** 2026-06-23
**Last Updated:** 2026-06-26
**Baustein:** — (Roadmap-Erweiterung, Phase 2)
**Prio:** P2 (Phase 2 — Skalierung)

## Dependencies
- Requires: PROJ-6 (Knappheits-Konstitution / Rollen) — definiert das Format von Rollen/Skill-Prompts, das die Registry verwaltet und teilt.
- Requires: PROJ-1 (Engine-Treiber) — installierte Rollen/Skills/Agenten werden beim Session-Start verwendet.
- Verwandt: PROJ-9 (Smart Launcher) — der Launcher schlägt installierte Rollen/Skills vor; die Registry erweitert den Vorrat.
- Verwandt: PROJ-10 (Trust-Policy) — Policy ist **pro Rolle/Skill** konfigurierbar; eine importierte Rolle muss eine Default-Policy mitbringen/erhalten.
- Verwandt: PROJ-25 (Auth/owner) — geteilte/teilbare Einträge tragen einen Eigentümer; Sichtbarkeit/Teilen setzt Identität voraus.

## Beschreibung
Rollen, Skills und Agenten-Definitionen sind heute lose Dateien im Setup (`rules/agents/*.md`, `.claude/skills/*`, Konstitutions-Rollen). Dieses Feature gibt ihnen eine **Registry**: ein durchsuchbarer Katalog, aus dem man **Rollen/Skills/Agenten installiert, aktiviert/deaktiviert, versioniert und (später) teilt**. Das macht Jupiters Erweiterbarkeits-Prinzip („maximal modular") sichtbar und bedienbar — statt Dateien von Hand zu kopieren.

**Scope-Hinweis (P2, bewusst schlank):** MVP der Registry = **lokaler Katalog + Import/Export** (Rolle/Skill als portierbares Paket). Ein **öffentlicher Online-Marktplatz** mit fremden Anbietern ist die Ausbaustufe; dieses Spec deckt zunächst den lokalen/teilbaren Kern. Was hier bewusst **nicht** drin ist, wird unter „offene Punkte" benannt, statt es zu implizieren.

**Grundhaltung:** Wissen über *Rollen/Skills* wird zum kuratierbaren, teilbaren Asset — wie der Vault für Projektwissen, nur für die Arbeitsweise selbst.

## User Stories
- Als Nutzer möchte ich einen **Katalog** aller verfügbaren Rollen/Skills/Agenten durchsuchen und sehen, was installiert/aktiv ist.
- Als Nutzer möchte ich eine Rolle/einen Skill **installieren und aktivieren/deaktivieren**, ohne Dateien von Hand zu kopieren.
- Als Nutzer möchte ich eine Rolle/einen Skill als **portierbares Paket exportieren** und in einer anderen Jupiter-Instanz **importieren**.
- Als Nutzer möchte ich beim Import sehen, **was das Paket darf** (welche Tools/Policy-Defaults), bevor ich es aktiviere (Sicherheit/Transparenz).
- Als Nutzer möchte ich **Versionen** einer Rolle/eines Skills unterscheiden und auf eine frühere zurück.
- Als Nutzer (später) möchte ich Einträge mit anderen **teilen** (Sichtbarkeit pro `owner`/geteilt), sobald Auth (PROJ-25) aktiv ist.

## Acceptance Criteria
- [ ] Es gibt einen durchsuchbaren **Katalog** von Rollen/Skills/Agenten mit Status (installiert / aktiv / inaktiv).
- [ ] Ein Eintrag lässt sich **installieren, aktivieren und deaktivieren**; aktive Rollen/Skills stehen Sessions/Launcher (PROJ-9) zur Verfügung.
- [ ] **Export** erzeugt ein portierbares, selbstbeschreibendes Paket (Prompt/Definition + Metadaten + Default-Policy); **Import** liest es zurück.
- [ ] Beim Import wird eine **Capability-/Policy-Vorschau** gezeigt (welche Tools, welche Trust-Defaults), Aktivierung erst nach Bestätigung.
- [ ] Jeder Eintrag ist **versioniert**; eine frühere Version ist wiederherstellbar.
- [ ] Importierte Rollen/Skills erhalten eine **Default-Trust-Policy** (PROJ-10) — niemals stillschweigend volle Autonomie.
- [ ] Einträge tragen einen **`owner`** (PROJ-25-kompatibel); Teilen/öffentliche Sichtbarkeit ist als klar abgegrenzte Ausbaustufe markiert.
- [ ] Ein **defektes/inkompatibles Paket** wird beim Import abgewiesen (Validierung), ohne das System zu beschädigen.
- [ ] Alle Texte/Fehlermeldungen deutsch.

## Edge Cases
- **Namens-/ID-Kollision** beim Import (Rolle existiert schon) → Versionierung/Umbenennen statt stillem Überschreiben.
- **Inkompatible Schema-Version** des Pakets → klare Ablehnung mit Grund, kein Teil-Import.
- **Paket fordert unbekannte/gefährliche Tools** → Capability-Vorschau warnt; Default-Policy stuft es konservativ ein (card/deny), nie auto-allow.
- **Aktive Rolle wird deaktiviert, während eine Session sie nutzt** → laufende Session läuft mit der geladenen Version weiter; Deaktivierung wirkt erst auf neue Sessions.
- **Manipuliertes Paket** (Import aus fremder Quelle) → Validierung + Capability-Vorschau; ohne Auth (PROJ-25) Warnung „Quelle nicht verifiziert".
- **Rückrollen auf eine Version, die ein nicht mehr vorhandenes Tool referenziert** → Hinweis statt Crash; Rolle wird als „eingeschränkt lauffähig" markiert.
- **Leerer Katalog / Erststart** → klarer Empty-State + Hinweis auf Import.

## Technical Requirements (optional)
- Paketformat selbstbeschreibend (Definition + Metadaten + Default-Policy + Schema-Version); dateibasiert, konsistent mit Jupiters offenem-MD/Datei-Ansatz.
- Capability-/Policy-Vorschau leitet sich aus Paket-Metadaten ab; Aktivierung ist ein bewusster Schritt (Human-in-the-Loop).
- Versionierung ohne DB-Zwang (Datei-/Git-basiert denkbar); Live-Index optional in Postgres.
- `owner`/Teilen baut auf PROJ-25 auf; bis dahin Single-User mit lokalem Katalog.
- Sicherheitslinie: importierte Definitionen werden **nicht** ungeprüft mit Vollrechten ausgeführt (Default-Policy konservativ).

### Offene Punkte (für Architektur/Requirements-Schärfung)
- Öffentlicher Online-Marktplatz mit Fremdanbietern, Signaturen/Trust-Chain, Ratings — **Ausbaustufe**, hier nur als Richtung benannt.
- Genaues Paketformat und Versionsstrategie (Git-Tags vs. eigenes Manifest) in der Architektur zu entscheiden.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (Cockpit) + FastAPI · **Persistenz: file-first** (kein Postgres — konsistent mit Konstitution/Policy/Engines) · **Branch:** dev

### Grundentscheidung: warum file-basiert
Jupiter hat keine DB-Schicht. Alles ist Datei/Config: Konstitution (`backend/constitution/global.md` + `roles/<role>.md`), Policy/Watchdog/Engines (`backend/config/*.yaml`), Sessions in-memory + Vault file-backed. Die Registry folgt demselben Muster — ein durchsuchbarer Index über die ohnehin existierenden Rollen-/Skill-/Agenten-Dateien + ein portierbares Paketformat. Deckt sich mit dem Spec-Hinweis „dateibasiert, konsistent mit Jupiters offenem-MD/Datei-Ansatz" und „Versionierung ohne DB-Zwang". Dateien sind git-versionierbar → Versionierung & Rollback praktisch „kostenlos", und der Nutzer kann Pakete von Hand inspizieren (Transparenz-Prinzip).

### A) Daten-/Speichermodell (Klartext, kein SQL)
```
backend/registry/
├── catalog.yaml                  # Live-Index: was existiert, Status (installed/active/inactive), version
├── installed/
│   ├── roles/<id>/
│   │   ├── manifest.yaml         # Metadaten + Default-Policy + Schema-Version + owner + angeforderte Tools
│   │   ├── definition.md         # der eigentliche Rollen-/Skill-Prompt
│   │   └── versions/<v>/         # frühere Versionen (Rollback-Quelle)
│   ├── skills/<id>/...
│   └── agents/<id>/...
└── packages/                     # exportierte/importierte .jupkg (zip aus manifest+definition)
```
Jeder Katalog-Eintrag trägt: **id, typ** (role | skill | agent), **name, beschreibung**, **status** (installiert / aktiv / inaktiv), **version** (+ Historie), **owner** (PROJ-25-kompatibles Feld; bis Auth da ist lokaler Single-User-Default), **capabilities** (welche Tools die Definition anfordert), **default_policy** (konservativ: card/deny — nie auto-allow).

**Aktiv-Schaltung wirkt über die bestehenden Resolver:** eine aktive Rolle wird als Datei dorthin gelegt, wo `resolve_constitution()` / `list_roles()` (`backend/app/engine/constitution.py`) bereits lesen → Sessions/Launcher (PROJ-9) sehen sie ohne Umbau automatisch. Skills analog im Skill-Pfad. Die Registry füllt nur den Vorrat, den der Session-Start ohnehin liest.

### B) Paketformat `.jupkg` (selbstbeschreibend)
Zip aus `manifest.yaml` (Metadaten + Default-Policy + **Schema-Version** + owner + angeforderte Tools) + `definition.md`. **Export** packt, **Import** validiert:
- Schema-Version inkompatibel → klare Ablehnung, **kein Teil-Import**.
- ID-Kollision → neue **Version** statt stillem Überschreiben (oder Umbenennen).
- fordert unbekannte/gefährliche Tools → **Capability-Vorschau** warnt; Default-Policy stuft konservativ ein.
- defektes/manipuliertes Paket → Validierung weist ab; ohne PROJ-25 Hinweis „Quelle nicht verifiziert".

### C) API-Shape (nur Endpunkte, kein Code)
```
GET    /registry/catalog            → Katalog durchsuchen (typ, status, query)
GET    /registry/{typ}/{id}         → Detail + Versions-Historie + capabilities
POST   /registry/{typ}/{id}/install → installieren (Datei extrahieren)
PATCH  /registry/{typ}/{id}/toggle  → aktivieren/deaktivieren
POST   /registry/{typ}/{id}/rollback→ frühere Version wiederherstellen
DELETE /registry/{typ}/{id}         → deinstallieren
GET    /registry/{typ}/{id}/export  → .jupkg herunterladen
POST   /registry/import             → .jupkg hochladen → Capability-/Policy-Vorschau (NOCH NICHT aktiv)
POST   /registry/import/confirm     → nach Bestätigung aktivieren (Human-in-the-Loop)
```
Konfliktfrei zu bestehenden Routen: `/constitution` bleibt read-only, `/settings` bleibt Policy-Quelle. Neue Router-Datei `backend/app/routes/registry.py`.

### D) Komponenten-Struktur (Cockpit-UI)
Neuer Tab im bestehenden `settings-dialog.tsx` (Muster wie Policy/Watchdog-Tabs), optional zusätzlich Sidebar-Sektion.
```
RegistryTab
├── CatalogSearchBar (Filter: Typ · Status · Suchtext)
├── CatalogList
│   └── CatalogRow (Name · Typ-Badge · Status-Badge · Version-Select · Toggle · ⋯)
├── EmptyState ("Katalog leer — importiere ein Paket")
├── ImportDialog
│   └── CapabilityPreview (angeforderte Tools + Trust-Defaults · "Quelle nicht verifiziert"-Warnung)
│       → Bestätigen aktiviert erst dann
└── EntryDetailSheet (Versions-Historie · Rollback · Export · Deinstallieren)
```
Wiederverwendung: shadcn/ui Dialog, Tabs, Badge, Select, Switch — keine neuen Komponenten.

### E) Tech-Entscheidungen (WARUM)
- **File-first statt Postgres:** keine DB-Schicht im Projekt; git-Versionierung liefert Versionierung/Rollback und manuelle Inspizierbarkeit der Pakete.
- **Aktiv = Datei am Resolver-Pfad:** kein Umbau an Session-Start/Launcher nötig — die Registry erweitert nur den Vorrat, den `list_roles()` ohnehin liest.
- **Import zweistufig (Vorschau → Bestätigen):** erzwingt Human-in-the-Loop; importierte Definitionen laufen nie ungeprüft mit Vollrechten (PROJ-10 Default-Policy konservativ).
- **owner-Feld jetzt, Teilen später:** Feld wird mitgeführt; öffentlicher Online-Marktplatz/Signaturen bleiben klar abgegrenzte Ausbaustufe.

### F) Abhängigkeiten
- Backend: keine neuen Pakete (`pyyaml` für Manifest vorhanden, `zipfile` stdlib für `.jupkg`).
- Frontend: keine neuen — vorhandene shadcn/ui-Komponenten.

### Bewusst NICHT im Scope (Ausbaustufe → offene Punkte)
Öffentlicher Online-Marktplatz mit Fremdanbietern, Signatur-/Trust-Chain, Ratings; echtes Teilen/Sichtbarkeit (braucht PROJ-25 Auth).

### Mapping Akzeptanzkriterium → Baustein
| Kriterium | Baustein |
|---|---|
| Durchsuchbarer Katalog + Status | `GET /registry/catalog` + CatalogList |
| Install/Aktivieren/Deaktivieren | `install` + `toggle`; aktiv = Datei am Resolver-Pfad |
| Export/Import Paket | `.jupkg` + `export`/`import` |
| Capability-/Policy-Vorschau vor Aktivierung | `import` (Vorschau) → `import/confirm`; CapabilityPreview |
| Versionierung + Rollback | `versions/<v>/` + `rollback` |
| Default-Trust-Policy (PROJ-10) | `default_policy` im manifest, konservativ |
| owner (PROJ-25-kompatibel) | owner-Feld im manifest |
| Defektes Paket abgewiesen | Import-Validierung (Schema-Version, Struktur) |
| Texte deutsch | UI/Fehlermeldungen deutsch |

**Verantwortliche Spezialisten:** Backend Developer (`registry.py`, Manifest/Validierung, `.jupkg`, Resolver-Anbindung) → Frontend Developer (RegistryTab + Import-Flow). QA: Import-Validierung & Capability-Vorschau red-teamen.

## Frontend Implementation (abc-frontend, 2026-06-26)
**Branch:** dev · **Stack:** Next.js (Cockpit) — neuer Tab im `settings-dialog.tsx`.

### Gebaut
- **`lib/types.ts`** — Registry-Typen: `RegistryType` (role|skill|agent), `RegistryStatus` (installed|active|inactive), `RegistryEntry` (inkl. `capabilities`, `default_policy` als `PolicyLevel`, `owner`, `verified`, `limited`), `RegistryVersion`, `RegistryEntryDetail` (Definition + Versions-Historie), `RegistryCatalog`, `RegistryImportPreview` (token + Schema-Version + Kollision + Warnungen).
- **`lib/api.ts`** — Client gegen den Tech-Design-Vertrag `/registry/*`: `getRegistryCatalog`, `getRegistryEntry`, `installRegistryEntry`, `toggleRegistryEntry`, `rollbackRegistryEntry`, `deleteRegistryEntry`, `exportRegistryPackage` (Blob-Download mit Bearer-Token), `importRegistryPreview` (Multipart → Vorschau), `importRegistryConfirm` (Token → aktivieren).
- **`components/cockpit/registry-control.tsx`** — `RegistryControl` (Such-/Filterleiste: Typ · Status · Freitext, client-seitig gefiltert), `CatalogRow` (Name · Typ-/Status-/„eingeschränkt"-Badge · Version · Installieren/Aktivieren/Deaktivieren · Detail), `ImportDialog` (zweistufig: Datei → Vorschau → Bestätigen), `CapabilityPreview` (angeforderte Tools + konservative Default-Policy + „Quelle nicht verifiziert"/Kollisions-/Warn-Hinweise), `EntryDetailDialog` (Definition-Text · Versions-Historie + Rollback · Export · Deinstallieren).
- **`settings-dialog.tsx`** — neuer Tab „Registry" (Muster wie Policy/Watchdog, in `ScrollArea`).

### Umgesetzte Akzeptanzkriterien (UI-seitig)
Durchsuchbarer Katalog + Status · Install/Toggle · Export/Import `.jupkg` · Capability-/Policy-Vorschau **vor** Aktivierung (Human-in-the-Loop) · Versionierung + Rollback · Default-Trust-Policy konservativ angezeigt · `owner` mitgeführt · Import-Fehler/defektes Paket → deutsche Fehler-Toasts (Backend-`detail`) · alle Texte deutsch · Empty-State („Katalog leer — importiere ein Paket") + Filter-Leer-Zustand · `limited`-Markierung („eingeschränkt lauffähig").

### Deviations / offen
- **Keine neuen shadcn-Komponenten** (kein `Sheet` im Projekt) → `EntryDetailDialog` als `Dialog` statt Sheet umgesetzt; deckt Versions-Historie/Rollback/Export/Deinstallieren ab.
- Toggle/Status laut Edge-Case (laufende Session behält geladene Version) ist serverseitige Semantik — UI zeigt nur den neuen Status.
- **Backend fehlt noch:** `backend/app/routes/registry.py` + `backend/registry/`-Speichermodell + `.jupkg`-Validierung sind noch nicht gebaut. Bis dahin zeigt der Tab den Lade-Fehlzustand („Katalog nicht ladbar — Backend offline?"). Verifikation: `npm run build` ✓, `eslint` ✓, `tsc --noEmit` (nur vorbestehender, unabhängiger Fehler in `lib/md-tree.test.ts`).

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
