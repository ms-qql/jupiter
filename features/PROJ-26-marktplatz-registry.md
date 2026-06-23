# PROJ-26: Marktplatz/Registry für Rollen/Skills/Agenten

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
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
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
