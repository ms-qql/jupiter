# PROJ-13: Git-Branch-Handling (in-App, abc-konform)

## Status: Deployed
**Created:** 2026-06-23
**Last Updated:** 2026-06-25
**Baustein:** #31

## Dependencies
- Requires: PROJ-3 (Cockpit) — Branch-Status erscheint im Kontext von Projekt/Session.
- Verwandt: PROJ-8 (Gantt/abc-Phasen) und die Branch-Strategie des `abc-architecture`-Skills (`main ↔ dev`, `specs/PROJ-X-…`).

## Beschreibung
Eine **Ein-Klick-UI** für die Git-Branch-Logik des abc-Workflows — ohne Terminal: aktuellen Branch je Projekt/Session sehen, einfach wechseln (`main ↔ dev`), Feature-Branches `specs/PROJ-X-<slug>` anlegen und am Ende `dev → main` promoten. Die Versionskontroll-Logik des abc-Workflows wird sichtbar und bedienbar.

## User Stories
- Als Nutzer möchte ich pro Projekt den aktuellen Branch und den Sauberkeits-Status (clean/dirty) sehen.
- Als Nutzer möchte ich mit einem Klick zwischen `main` und `dev` wechseln.
- Als Nutzer möchte ich einen Feature-Branch `specs/PROJ-X-<slug>` aus der Feature-Auswahl anlegen.
- Als Nutzer möchte ich am Feature-Ende `dev → main` (bzw. Feature-Branch → `dev`) **promoten**, geführt und mit Vorab-Check.
- Als Nutzer möchte ich vor einem Wechsel/Merge gewarnt werden, wenn uncommittete Änderungen vorliegen.

## Acceptance Criteria
- [ ] Anzeige je Projekt: **aktueller Branch**, ahead/behind, **clean/dirty**, Liste vorhandener Branches.
- [ ] **Branch-Wechsel** per Klick; bei dirty Working Tree wird gewarnt und blockiert/optionen angeboten (stash/abbrechen), nie stiller Datenverlust.
- [ ] **Feature-Branch anlegen** mit korrektem Schema `specs/PROJ-X-<kebab-slug>` (Slug aus Spec-Titel), von `main` bzw. `dev` abgezweigt.
- [ ] **Promote-Flow** `dev → main` (und Feature → `dev`): Vorab-Check (clean, Branch ⊇ Ziel), Bestätigung, dann Merge `--no-ff`.
- [ ] Merge-/Wechsel-**Konflikte** werden klar gemeldet; die App führt keinen erzwungenen Merge aus.
- [ ] Alle Git-Operationen laufen **innerhalb der erlaubten Roots** und nur auf echten Git-Repos.
- [ ] Aktion ist nachvollziehbar protokolliert (welcher Branch, welche Operation, Ergebnis).
- [ ] Alle Texte deutsch; gefährliche Operationen (force) sind **nicht** Ein-Klick.

## Edge Cases
- **Dirty Working Tree** beim Wechsel → Optionen statt Zwang (stash / commit-Hinweis / abbrechen).
- **Merge-Konflikt** beim Promote → abbrechen + verständlicher Hinweis, Auflösung bleibt manuell/Terminal.
- **Kein Git-Repo** im Projekt → Aktionen ausgegraut, Angebot „git init?".
- **Branch existiert bereits** (z. B. Feedback-Runde 2) → auschecken statt neu anlegen.
- **Remote nicht erreichbar** → lokale Operationen funktionieren, Push/Pull klar getrennt und mit Fehlertoleranz.
- **Detached HEAD** → erkennen und sicher zurück auf einen Branch führen.

## Technical Requirements (optional)
- Backend kapselt Git über parametrisierten Subprozess (keine interaktiven Flags `-i`).
- Force-Operationen erfordern explizite, gesonderte Bestätigung (kein Default).
- Status-Abfrage performant (< 500 ms), pollbar im Cockpit.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (Cockpit) + FastAPI + Subprozess-Git (read-only SQLite-Index, kein DB-Schema) · **Branch:** dev

### A) Komponentenstruktur (Frontend, Next.js)
```
SessionTile / Projektzeile (bestehend)
└── BranchBadge (neu)                  → "dev · clean" | "main · 2 ahead" | "specs/PROJ-13… · dirty"
      └── onClick → BranchPanel (neu, shadcn Popover/Dialog)
            ├── BranchStatusHeader      → aktueller Branch, ahead/behind, clean/dirty
            ├── BranchList              → vorhandene Branches, Klick = Wechsel
            ├── SwitchAction            → main ↔ dev (1 Klick)
            ├── CreateFeatureBranch     → Feature-Auswahl (PROJ-X) → specs/PROJ-X-<slug>
            ├── PromoteFlow             → dev→main (bzw. Feature→dev): Vorab-Check → Bestätigen → Merge --no-ff
            └── DirtyGuardDialog        → bei dirty: Optionen (Stash / Abbrechen), nie stiller Verlust
```
Kein-Git-Repo → Badge ausgegraut, Angebot „git init?". Detached HEAD → Hinweis + „zurück auf Branch".

### B) Datenmodell (Klartext)
Git **ist** die Quelle der Wahrheit — keine neue Tabelle. Der Branch-Status wird live aus dem Repo gelesen, nicht persistiert. Ein abgefragter Status umfasst je Projekt:
- aktueller Branch (oder „detached")
- clean/dirty (uncommittete Änderungen ja/nein)
- ahead/behind ggü. Tracking-Branch (lokal berechnet, **ohne** Netz)
- Liste der lokalen Branches
- ist-Git-Repo (ja/nein)

Audit/Protokoll: jede schreibende Git-Operation wird als **Session-/Server-Logeintrag** (Branch, Operation, Ergebnis) festgehalten — wie bestehende Tool-Ausgaben; keine eigene Audit-Tabelle im MVP.

### C) API-Form (nur Endpunkte, kein Code)
```
GET  /git/status?project_path=…           → Branch, clean/dirty, ahead/behind, Branch-Liste, is_repo
POST /git/switch       {project_path, branch}            → checkout; bei dirty 409 + Optionen, nie erzwungen
POST /git/feature-branch {project_path, feature_id, slug}→ legt specs/PROJ-X-<slug> an (von main/dev), oder checkout falls existiert
POST /git/promote      {project_path, from, to}          → Vorab-Check (clean, from ⊇ to) → Merge --no-ff; Konflikt = 409 + klarer Hinweis, kein Force
POST /git/stash        {project_path}                    → optionaler Stash vor Wechsel (explizit, nicht automatisch)
POST /git/init         {project_path}                    → git init für Nicht-Repos (bestätigt)
```
Alle Schreib-Endpunkte validieren `project_path` gegen `allowed_roots` (bestehender `validate_project_path`-Seam). Force/`-i`-Flags existieren nicht.

### D) Tech-Entscheidungen (WARUM)
- **Git als Subprozess kapseln** (neue `backend/app/engine/git_service.py` + Route `backend/app/routes/git.py`) — exakt das bestehende `asyncio.create_subprocess_exec`-Muster (parametrisierte Args, `cwd=project_path`, Timeout, stderr-Auswertung) wie `claude_driver`/`scout`. Keine Shell, keine interaktiven Flags → keine Injection.
- **Pfad-Sicherheit wiederverwenden** statt neu erfinden: `validate_project_path()` (realpath + `_in_allowed_roots`-Prefix-Check) ist der einzige Eintrittspunkt; Git läuft nur in echten Repos innerhalb der erlaubten Roots.
- **Kein erzwungener Merge / kein Force als Ein-Klick**: Konflikt → 409, App bricht ab und verweist auf manuelle Auflösung. Gefährliches braucht eine zweite, gesonderte Bestätigung (Konstitution PROJ-6/Trust PROJ-10-konform).
- **Status read-only & pollbar (< 500 ms)**: nur lokale Git-Reads, ahead/behind ohne `fetch`; Push/Pull bewusst getrennt und fehlertolerant (Remote nicht erreichbar bricht lokale Ops nicht).
- **Kein neues Persistenz-Schema**: Status ist flüchtig (Git ist Wahrheit), Protokoll geht in vorhandenes Logging — minimale Angriffsfläche, keine Migration.

### E) Abhängigkeiten
- Backend: keine neuen Pakete — Git über `git`-CLI als Subprozess, `asyncio` vorhanden.
- Frontend: keine neuen Pakete — shadcn/ui (Popover/Dialog/Badge) + bestehender `lib/api.ts`-Client; neuer `BranchStatus`-Typ in `lib/types.ts`.

### Zuständigkeit
- **Backend Developer** (`/abc-backend`): `git_service.py`, Route `git.py`, in `main.py` registrieren.
- **Frontend Developer** (`/abc-frontend`): `BranchBadge` + `BranchPanel`, Einbindung in SessionTile/Projektzeile, `lib/api.ts`-Calls.

### Backend-Implementierung (2026-06-25, Branch `dev`)
**Neu:**
- `backend/app/engine/git_service.py` — `GitService`: Git als parametrisierter `asyncio`-Subprozess (kein Shell, kein `-i`, kein Force-Default), `cwd` = via `validate_project_path` (manager.py) gegen `allowed_roots` gehärteter Realpfad, hartes Timeout. Exceptions `GitError/NotARepo/DirtyWorkingTree/MergeConflict/GitTimeout`.
- `backend/app/schemas/git.py` — `BranchStatus` + Request-Schemas (Pydantic v2).
- `backend/app/routes/git.py` — Router `/git`, Fehler-Mapping dirty/Konflikt/kein-Repo → **409**, Timeout → **504**, Scope/sonstige Git-Fehler → **400**.
- `backend/tests/test_proj13_git.py` — 14 Tests gegen echte tmp-Repos (alle grün).

**Geändert:**
- `backend/app/config.py` — `git_bin` + `git_timeout_seconds` (default 15 s).
- `backend/app/main.py` — `app.state.git = GitService()` + Router registriert.

**API (alle scoped auf `allowed_roots`):**
- `GET  /git/status?project_path=…` → `BranchStatus` (is_repo, branch, detached, dirty, ahead/behind lokal **ohne fetch**, branches).
- `POST /git/switch {project_path, branch}` — blockiert bei dirty (409).
- `POST /git/feature-branch {project_path, feature_id, slug, base=main}` → `specs/PROJ-<id>-<kebab-slug>`; existiert er → checkout.
- `POST /git/promote {project_path, source, target}` — Vorab-Check clean + Ziel ⊆ Quelle (`merge-base --is-ancestor`), dann `merge --no-ff --no-edit`; Konflikt → `merge --abort` + 409.
- `POST /git/stash {project_path}` — expliziter `stash push -u` (nie automatisch).
- `POST /git/init {project_path}` — `git init` für Nicht-Repos.

**Designabweichungen / Notizen:**
- ahead/behind rein lokal gegen `@{upstream}`; ohne Tracking-Branch `null` (Remote optional, kein Netz im Status-Pfad → bleibt < 500 ms pollbar).
- Detached HEAD wird erkannt (`detached=true`, `branch` = Kurz-Hash). Force/Push/Pull bewusst **nicht** Teil dieses Stands (kein Ein-Klick-Force lt. Spec).
- Protokoll via `logging.info` je schreibender Operation (keine eigene Audit-Tabelle im MVP — Git ist die Wahrheit).

### Frontend-Implementierung (2026-06-25, Next.js, Branch `dev`)
**Neu:**
- `nextjs_app/components/cockpit/branch-panel.tsx` — `BranchBadge` (Header-Badge, pollt `/git/status` für den aktuellen Pfad) + `BranchPanel` (shadcn/base-ui Dialog): Status-Kopf (Branch/clean-dirty/ahead-behind), Branch-Wechsel-Buttons, Dirty-Warnung mit explizitem Stash, Feature-Branch-Formular (`specs/PROJ-<id>-<slug>` + Basis main/dev), Promote `dev → main` (und `<feature> → dev`). Reine Darstellungs-Logik als exportierte `describeBranch()` (separat getestet).
- `nextjs_app/components/cockpit/branch-panel.test.tsx` — 6 Vitest-Tests für alle Badge-Varianten (lädt/kein-Repo/clean/dirty/ahead-behind/detached).

**Geändert:**
- `nextjs_app/lib/types.ts` — `BranchStatus`-Interface.
- `nextjs_app/lib/api.ts` — `getBranchStatus/switchBranch/createFeatureBranch/promoteBranch/stashChanges/gitInit`.
- `nextjs_app/components/cockpit/file-explorer.tsx` — `BranchBadge` im Header (pfad-/projekt-scoped, neben ThemeToggle).

**UI-Verhalten:**
- Kein-Repo → Aktionen aus, Button „git init ausführen". Dirty → Wechsel/Promote blockiert (Backend-409 als deutscher Toast) + Stash-Option. Detached HEAD → destructive Badge; Rückkehr via Branch-Wechsel.
- States: lädt/leer/Fehler explizit; alle Texte deutsch; Erfolg/Fehler via Sonner-Toast; Status nach jeder Mutation aus der Antwort gespiegelt.

**Tests gesamt:** Backend 29 (pytest) + Frontend 6 (vitest, `describeBranch`); volle FE-Suite 109 grün, Lint clean, keine Regression.

## QA Test Results
**Getestet:** 2026-06-25 · **Branch:** dev · **Ergebnis:** ✅ Production-Ready (keine Critical/High-Bugs)

**Suite:** `backend/tests/test_proj13_git.py` (14) + `backend/tests/test_proj13_git_qa.py` (15, Red-Team) = **29 Tests, alle grün**. Volle Backend-Suite **608 passed** → keine Regression. Tests laufen gegen echte tmp-Git-Repos (kein Mock der Git-Schicht).

### Akzeptanzkriterien
| # | Kriterium | Status | Beleg |
|---|-----------|--------|-------|
| 1 | Anzeige Branch / ahead-behind / clean-dirty / Branch-Liste | ✅ | `test_status_repo`, `test_status_dirty_detected`, `test_ahead_behind_against_upstream` (ahead=1/behind=0 korrekt) |
| 2 | Branch-Wechsel per Klick; dirty → blockiert, kein stiller Verlust | ✅ | `test_switch_clean`, `test_switch_dirty_blocks_409` (409 + dt. Hinweis) |
| 3 | Feature-Branch `specs/PROJ-X-<kebab-slug>` von main/dev | ✅ | `test_feature_branch_created_with_schema`, `test_feature_branch_existing_checks_out` |
| 4 | Promote dev→main: Vorab-Check (clean, Ziel ⊆ Quelle) + `--no-ff` | ✅ | `test_promote_dev_into_main`, `test_promote_diverged_target_blocked` (400) |
| 5 | Konflikte klar gemeldet, kein erzwungener Merge | ✅ | Vorab-Check `merge-base --is-ancestor` verhindert divergente Merges (400); `MergeConflict`-Pfad bricht mit `merge --abort` ab (defensiver Gürtel, durch Pre-Check faktisch unerreichbar) |
| 6 | Ops nur in erlaubten Roots, nur echte Repos | ✅ | `test_path_outside_roots_blocked`, `test_symlink_escape_blocked`, `test_path_outside_roots_on_write_endpoints` |
| 7 | Aktion nachvollziehbar protokolliert | ✅ | `logging.info` je schreibender Op (switch/feature/promote/stash/init) |
| 8 | Texte deutsch; Force nicht Ein-Klick | ✅ | dt. Fehlermeldungen; kein Force/Push/Pull-Endpoint vorhanden |

### Edge Cases
| Fall | Status | Beleg |
|------|--------|-------|
| Dirty beim Wechsel → Optionen statt Zwang | ✅ | `test_switch_dirty_blocks_409` + `test_stash_then_switch` (expliziter Stash entsperrt) |
| Kein Git-Repo → `is_repo:false`, init angeboten | ✅ | `test_status_non_repo`, `test_init_makes_repo`, `test_init_on_existing_repo_400` |
| Branch existiert bereits → auschecken | ✅ | `test_feature_branch_existing_checks_out` |
| Remote nicht erreichbar → lokale Ops laufen | ✅ | ahead/behind rein lokal gegen `@{upstream}`, kein `fetch` im Pfad |
| Detached HEAD → erkennen + sicher zurückführen | ✅ | `test_detached_head_detected` |
| Stash bei sauberem Tree | ✅ | `test_stash_clean_tree_400` |

### Security-Audit (Red-Team)
- **Command/Option-Injection über Branch-Namen:** abgewehrt. `--help`, `-f`, `--output=…`, `; touch …`, `$(…)`, `main; rm -rf /` als `branch`/`source`/`target`/`base` → durchweg **400** via Existenz-Check (`show-ref --verify refs/heads/<name>`, Name immer prefix-gebunden), nie als Flag/Shell ausgeführt (`create_subprocess_exec`, kein Shell). Beleg: `test_switch_rejects_injection_branch_names`, `test_promote_rejects_injection_refs`, `test_feature_branch_rejects_injection_base`.
- **Slug-Sanitisierung:** `../../etc/passwd; rm -rf` → `specs/PROJ-7-etc-passwd-rm-rf` (kebab, keine Pfad-/Shell-Zeichen). Beleg: `test_feature_branch_slug_is_sanitised`.
- **Scope-Escape:** Symlink innerhalb der Root nach `/etc` → `realpath` fällt aus den Roots → **400** (`test_symlink_escape_blocked`); `/`, `/etc`, `/root` direkt → 400.
- **Force/Destruktiv:** kein Force-/Reset-/Push-Endpoint; Promote nie erzwungen; dirty blockiert. Kein stiller Datenverlust nachweisbar.

### Bugs
Keine. (0 Critical · 0 High · 0 Medium · 0 Low)

### Beobachtung (kein Bug)
- `MergeConflict` (409) ist durch den `is-ancestor`-Vorab-Check in der Praxis nicht erreichbar (divergente Stände werden vorher mit 400 abgewiesen) — bewusst als defensiver Sicherheitsgürtel belassen.
- Push/Pull/Force sind bewusst **nicht** Teil dieses Stands (Spec: kein Ein-Klick-Force) — Folge-Feature bei Bedarf.

## Deployment
**Deployed:** 2026-06-25 · **Version:** 0.11.0 · **Host:** jupiter.auxevo.tech (host-nativ, systemd + Caddy, GitHub-Webhook) · **Release:** `dev → main`, Tag `v0.11.0`.
Geliefert: Backend `/git`-Endpunkte (status/switch/feature-branch/promote/stash/init) + Frontend `BranchBadge`/`BranchPanel` im FileExplorer-Header.
Smoke-Test (Prod) ausstehend: Branch-Badge zeigt Status, Wechsel main↔dev, Feature-Branch anlegen, Promote dev→main.
