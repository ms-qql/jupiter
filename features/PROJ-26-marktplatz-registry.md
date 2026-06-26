# PROJ-26: Marktplatz/Registry für Rollen/Skills/Agenten

## Status: Approved
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

## Backend Implementation (abc-backend, 2026-06-26)
**Branch:** dev · **Stack:** FastAPI · **Persistenz: file-first** (kein Postgres) — wie im Tech-Design.

### Gebaut
- **`backend/app/engine/marketplace.py`** — `RegistryStore` (Datei-basiert, Modul-Singleton `registry_store`).
  Speichermodell `backend/registry/installed/<typ>s/<id>/{manifest.yaml,definition.md,versions/<v>/}` + `packages/_staging/`.
  - **Katalog** aus dem Dateisystem abgeleitet (kein doppelter Index): `catalog(typ,status,query)` filtert serverseitig.
  - **`.jupkg`** = Zip aus `manifest.yaml` + `definition.md`. `import_preview` validiert (Schema-Version-Kompatibilität per MAJOR, Struktur, ID) und **staged** das Paket unter einem `secrets.token_urlsafe`-Token → **aktiviert nichts**. `import_confirm(token, owner)` installiert + aktiviert (Human-in-the-Loop).
  - **Capability-/Policy-Ableitung** (`assess_capabilities`): unbekannte/gefährliche Tools → `default_policy="deny"` + `limited=True` + Warnung; nur Lese-Tools → `card`. **Nie `auto-allow`** (PROJ-10). Bekannte-Tools-Set aus `policy.AUTO_ALLOW_TOOLS` ∪ Mutations-Tools.
  - **Aktiv = Datei am Resolver-Pfad:** Rolle → `constitution_dir/roles/<id>.md` (wird von `resolve_constitution()`/`list_roles()` gelesen → Sessions/Launcher PROJ-9 sehen sie ohne Umbau). Skill/Agent → `registry_root/active/<typ>s/` (Best-Effort; Session-Start-Anbindung für Skills/Agenten ist Ausbaustufe).
  - **Resolver-Schutz:** entfernt/überschreibt eine Resolver-Datei nur, wenn die Registry sie selbst gelegt hat (`resolver_placed`). Eine von Hand gepflegte Konstitutions-Rolle (PROJ-6) gleichen Namens → Aktivierung bricht mit **409** ab, statt sie zu überschreiben.
  - **Versionierung/Rollback:** `versions/<v>/`-Archive + `rollback`; ID-Kollision beim Import → **neue Version** (`_bump_version`) statt stillem Überschreiben.
  - **owner** kommt aus `get_current_user().user_id` (Token/Default-Owner, PROJ-25), nie aus dem Client.
- **`backend/app/schemas/registry.py`** — Pydantic-v2 spiegelt den Frontend-Vertrag (`RegistryEntryRead`, `RegistryVersionRead`, `RegistryEntryDetailRead`, `RegistryCatalogRead`, `RegistryImportPreviewRead`, Rollback-/Confirm-Bodies).
- **`backend/app/routes/registry.py`** — Router exakt nach Tech-Design-Vertrag: `GET /registry/catalog`, `GET/POST/PATCH/DELETE /registry/{typ}/{id}[/install|/toggle|/rollback|/export]`, `POST /registry/import` (Multipart → Vorschau, max 2 MB), `POST /registry/import/confirm`. Registriert in `main.py` mit `auth_gate`.
- **`config.py`** — `registry_root` (Default `backend/registry/`). **`.gitignore`** → `backend/registry/` (Laufzeit-Daten).

### Umgesetzte Akzeptanzkriterien (Backend)
Durchsuchbarer Katalog + Status · Install/Toggle (aktiv=Resolver-Datei) · Export/Import `.jupkg` · zweistufige Capability-/Policy-Vorschau **vor** Aktivierung · Versionierung + Rollback · konservative Default-Policy (card/deny) · `owner` serverseitig · defektes/inkompatibles Paket abgewiesen (kein Teil-Import) · alle Fehlermeldungen deutsch.

### Tests
`backend/tests/test_proj26_registry.py` — **22 Tests grün**; volle Suite **809 passed**, keine Regression. Deckt: leerer Katalog, Filter, zweistufiger Import, Vorschau aktiviert nichts, card vs. deny+limited, defektes/inkompatibles/leeres/definitionsloses Paket → Ablehnung, Toggle-Roundtrip + Resolver-Entfernung, Resolver-Schutz fremder Dateien (409), Kollision→neue Version, Rollback, Export-Roundtrip, Delete, Detail-404, owner serverseitig.

### Deviations / offen
- **Skill/Agent-Aktivierung** legt die Definition in `registry_root/active/<typ>s/` ab — Jupiters Session-Start liest Skills aus `~/.claude/skills` (außerhalb des Repos); die Live-Anbindung für Skills/Agenten bleibt bewusst Ausbaustufe (Rollen sind voll verdrahtet).
- **`verified`** ist für importierte Pakete immer `false` (keine PROJ-25-Signatur/Trust-Chain) — Vorschau warnt „Quelle nicht verifiziert".
- **Staging** der Import-Pakete liegt unter `packages/_staging/<token>.jupkg`; eine abgelaufene/unbekannte Vorschau → 404 mit Hinweis „erneut hochladen".

## QA Test Results (abc-qa, 2026-06-26)
**Branch:** dev · **Tester:** QA Engineer / Red-Team · **Build:** Backend `bf385a1`

### Zusammenfassung
- **Akzeptanzkriterien:** 9/9 bestanden (1 mit Sicherheits-Caveat — siehe BUG-26-1).
- **Edge Cases:** 7/8 bestanden, 1 teilweise (manipuliertes Paket: Validierung greift, aber Zip-Bombe nicht abgefangen).
- **Automatisierte Tests:** `backend/tests/test_proj26_registry.py` — **22 passed, 3 xfailed** (xfail = dokumentierte offene Befunde). Volle Suite: **809 passed, 3 xfailed, keine Regression**.
- **Bugs:** 0 Critical · 0 High · 1 Medium · 2 Low.
- **Production-Ready:** ✅ **READY** (keine Critical/High) — **Empfehlung:** BUG-26-1 vor dem Deploy fixen, da der Import-Pfad bewusst Fremd-Pakete annimmt.

### Akzeptanzkriterien (pass/fail)
| # | Kriterium | Ergebnis | Beleg |
|---|---|---|---|
| 1 | Durchsuchbarer Katalog + Status (installiert/aktiv/inaktiv) | ✅ PASS | `test_catalog_*`, Filter Typ/Status/Query |
| 2 | Install/aktivieren/deaktivieren; aktiv steht Sessions/Launcher zur Verfügung | ✅ PASS | `test_toggle_*`, `test_install_*` + `list_roles()` sieht aktive Rolle |
| 3 | Export portierbares Paket; Import liest zurück | ✅ PASS | `test_export_roundtrip` |
| 4 | Capability-/Policy-Vorschau vor Aktivierung (Human-in-the-Loop) | ✅ PASS | `test_import_preview_does_not_activate`, `test_import_confirm_activates` |
| 5 | Versioniert; frühere Version wiederherstellbar | ✅ PASS | `test_rollback_restores_previous_version` |
| 6 | Default-Trust-Policy konservativ (card/deny — nie auto-allow) | ✅ PASS | `test_readonly_caps_get_card_policy`, `test_unknown_dangerous_tool_gets_deny_and_limited` |
| 7 | owner PROJ-25-kompatibel; Teilen als Ausbaustufe markiert | ✅ PASS | `test_owner_comes_from_server_not_client` (owner serverseitig) |
| 8 | Defektes/inkompatibles Paket abgewiesen, ohne System zu beschädigen | ⚠️ PASS* | `test_corrupt_package_rejected`, `test_incompatible_schema_version_rejected`, `test_missing_definition_rejected` — *aber Zip-Bombe umgeht die Validierung → BUG-26-1 |
| 9 | Alle Texte/Fehlermeldungen deutsch | ✅ PASS | alle `detail`-Strings deutsch |

### Edge Cases
| Edge Case | Ergebnis |
|---|---|
| Namens-/ID-Kollision → neue Version statt Überschreiben | ✅ `test_id_collision_creates_new_version_not_overwrite` |
| Inkompatible Schema-Version → Ablehnung, kein Teil-Import | ✅ `test_incompatible_schema_version_rejected` |
| Fordert unbekannte/gefährliche Tools → Vorschau warnt, Default deny | ✅ `test_unknown_dangerous_tool_gets_deny_and_limited` |
| Aktive Rolle deaktiviert während laufender Session → läuft weiter | ✅ by design (toggle wirkt nur auf Resolver-Datei; geladener Prompt der Session unberührt) |
| Manipuliertes Paket → Validierung + „Quelle nicht verifiziert" | ⚠️ teilweise — Validierung/Warnung vorhanden, aber **Dekomprimierungs-Bombe** nicht abgefangen (BUG-26-1) |
| Rollback auf Version mit fehlendem Tool → Hinweis statt Crash, „eingeschränkt lauffähig" | ✅ `limited`-Flag live abgeleitet, kein Crash |
| Leerer Katalog / Erststart → Empty-State | ✅ `test_catalog_empty_on_first_start` |

### Security Audit (Red-Team)
| Vektor | Befund |
|---|---|
| Path-Traversal über `id`/`typ`/`token` | ✅ blockiert — Regex-Validierung (`_VALID_ID`, `VALID_TYPES`, Token-Pattern) |
| Zip-Slip über `.jupkg` (bösartige Pfade im Zip) | ✅ kein Risiko — nur feste Namen `manifest.yaml`/`definition.md` gelesen, Rest ignoriert |
| YAML-Deserialisierung (Code-Exec) | ✅ `yaml.safe_load` überall |
| Überschreiben von Hand-gepflegten Konstitutions-Rollen (PROJ-6) | ✅ **gut verteidigt** — fremde Resolver-Datei → 409, `resolver_placed`-Tracking; `test_foreign_resolver_file_not_overwritten` |
| Auth / owner-Spoofing | ✅ Router hinter `auth_gate`; `owner` aus Token, nie aus Client-Payload |
| **Dekomprimierungs-Bombe (DoS)** | ❌ **BUG-26-1** — kleines Paket (<2 MB komprimiert) entpackt unbegrenzt (verifiziert: 61 KB → 60 MB RAM + Platte) |
| Staging-Storage-Leak | ❌ **BUG-26-3** — nicht bestätigte Vorschauen lassen `.jupkg` dauerhaft liegen (kein TTL/Cleanup) |

### Gefundene Bugs

**BUG-26-1 — Dekomprimierungs-Bombe beim Import (Medium, DoS)**
- *Beschreibung:* Der Upload-Cap (`MAX_PACKAGE_BYTES = 2 MB`) prüft nur die **komprimierte** Größe. `import_preview`/`_read_package` rufen `zf.read("definition.md")` ohne Größenlimit → ein wenige KB großes `.jupkg` kann zig/hunderte MB in RAM und (bei Confirm) auf die Platte schreiben.
- *Repro:* `.jupkg` mit `definition.md` = `"A"*60MB` → 61 KB auf der Leitung → `import_preview` akzeptiert, `import_confirm` schreibt 60 MB nach `installed/roles/r/definition.md`. (Empirisch verifiziert.)
- *Deckt Spec-Edge-Case „Manipuliertes Paket" nur unvollständig ab.*
- *Fix-Vorschlag (Backend):* entpackte Größe deckeln — `ZipInfo.file_size` vor `read` prüfen (z. B. Definition ≤ 1 MB, Manifest ≤ 64 KB) und Zahl der Zip-Einträge begrenzen; Überschreitung → 413.
- *Test:* `test_decompression_bomb_rejected` (xfail).

**BUG-26-2 — 409-Abbruch hinterlässt Teil-Installation (Low)**
- *Beschreibung:* Kollidiert eine zu aktivierende Rolle mit einer fremden Resolver-Datei, legt `import_confirm` zuerst den Eintrag (`status=installed`) an und wirft **erst danach** beim `_place_resolver` 409. Die fremde Datei bleibt korrekt geschützt, aber ein halber Katalog-Eintrag „architect/installed" bleibt zurück.
- *Repro:* Hand-Rolle `architect.md` anlegen → gleichnamiges Paket importieren+confirm → 409, danach `GET /registry/catalog` zeigt `architect/installed`. (Verifiziert.)
- *Fix-Vorschlag:* Resolver-Kollision vor dem Anlegen des Eintrags prüfen, oder bei 409 das angelegte Verzeichnis zurückrollen (transaktional).
- *Test:* `test_foreign_collision_409_leaves_no_partial_entry` (xfail).

**BUG-26-3 — Staging-Pakete lecken (Low, Storage)**
- *Beschreibung:* Jede `POST /registry/import`-Vorschau legt ein `.jupkg` unter `packages/_staging/<token>.jupkg` ab; ohne anschließendes `import/confirm` wird es nie entfernt (kein TTL/GC). Wiederholte Vorschauen → unbegrenztes Plattenwachstum (verschärft BUG-26-1).
- *Fix-Vorschlag:* TTL-basiertes Aufräumen alter Staging-Dateien (z. B. beim nächsten Import) oder In-Memory-Staging mit Ablauf.
- *Test:* `test_unconfirmed_previews_do_not_leak_staging` (xfail).

### Regression
Keine. Volle Backend-Suite **809 passed** nach der Änderung (`config.py`/`main.py` berührt); verwandte Features PROJ-6/10/25 grün.

### Empfehlung
**READY** (keine Critical/High). Vor `/abc-deploy` jedoch **BUG-26-1 (Medium) fixen** — der Import-Pfad nimmt per Design Fremd-Pakete an, daher gehört das Dekomprimierungs-Limit zur Kern-Sicherheitslinie der Spec. BUG-26-2/-3 (Low) können nachgezogen werden.

## Bug Fixes (abc-backend, 2026-06-26)
Alle drei QA-Befunde behoben in `backend/app/engine/marketplace.py`:

- **BUG-26-1 (Medium, behoben):** Dekomprimierungs-Limit. `_read_package` liest `manifest.yaml` (≤ 64 KB) und `definition.md` (≤ 1 MB) jetzt **gestreamt mit hartem Byte-Cap** (`_read_capped` via `zf.open(...).read(limit+1)`) — greift auch bei gefälschtem Größen-Header im Zip; zusätzlich Eintragszahl ≤ 16. Überschreitung → **413**, kein Teil-Import/Staging-Rest.
- **BUG-26-2 (Low, behoben):** `import_confirm` prüft die Resolver-Kollision (fremde Datei) jetzt **vor** dem Anlegen des Eintrags → bei 409 bleibt kein halber `installed`-Eintrag zurück; die hand-gepflegte Datei bleibt unangetastet.
- **BUG-26-3 (Low, behoben):** `_stage_package` ruft `_sweep_staging()` → nie bestätigte Staging-Pakete älter als `STAGING_TTL_SECONDS` (1 h) werden opportunistisch entfernt; frische Vorschauen bleiben (noch bestätigbar).

**Re-Test:** `backend/tests/test_proj26_registry.py` — **26 passed** (inkl. 4 Regressionstests für die Fixes: `test_decompression_bomb_rejected`, `test_oversized_manifest_rejected`, `test_foreign_collision_409_leaves_no_partial_entry`, `test_stale_unconfirmed_staging_is_swept`). Volle Suite: **813 passed, keine Regression**. Keine offenen Critical/High/Medium/Low mehr → bereit für `/abc-qa`-Re-Pass (→ Approved) bzw. `/abc-deploy`.

## QA Re-Test — 2. Durchlauf (abc-qa, 2026-06-26)
**Branch:** dev · **Build:** Backend `403dbc3` · **Ergebnis: ✅ APPROVED**

Alle drei Bugs erneut geprüft (manuell empirisch + automatisiert) — **alle behoben**:

| Bug | Re-Test | Befund |
|---|---|---|
| BUG-26-1 (Medium, DoS) | 60-MB-Definition → **413**; **gefälschter Größen-Header** (claimt 5 B, real 10 MB) → **413**; übergroßes Manifest (>64 KB) → 413 | ✅ behoben — gestreamter Byte-Cap, header-unabhängig |
| BUG-26-2 (Low) | 409 bei fremder Resolver-Datei → Katalog bleibt **leer**, Hand-Datei intakt | ✅ behoben — Prüfung vor Anlegen |
| BUG-26-3 (Low) | Abgelaufenes Staging-Paket wird beim nächsten Stagen **gefegt**, frische Vorschau bleibt | ✅ behoben — TTL-Sweep |

**Zusätzliche Security-Vertiefung (2. Durchlauf):**
- Auth-Härtung: sobald ein Account existiert (scharfe Instanz), liefern `GET /registry/catalog` **und** `POST /registry/import` ohne Token **401** (`test_registry_requires_token_once_users_exist`).
- owner-Integrität: `owner` stammt aus dem Token-`sub`, nie aus dem Client (`test_owner_taken_from_token_not_client`).
- Re-geprüfte Sicherheitslinie (weiterhin grün): Path-Traversal-Blocker, kein Zip-Slip, `yaml.safe_load`, Schutz hand-gepflegter PROJ-6-Rollen (409).

**Automatisierte Suite:** `test_proj26_registry.py` — **29 passed** · volle Backend-Suite **816 passed, keine Regression**.

**Bugs offen:** 0 Critical · 0 High · 0 Medium · 0 Low.
**Production-Ready: ✅ READY** → Status **Approved**. Nächster Schritt: `/abc-deploy`.

## Deployment
_To be added by /abc-deploy_
