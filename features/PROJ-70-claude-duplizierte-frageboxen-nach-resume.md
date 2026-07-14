# PROJ-70: Bugfix: Claude-Engine dupliziert Fragekarten nach jedem Resume (bis zu 6 gleiche Frageboxen)

## Status: Deployed
**Created:** 2026-07-12
**Last Updated:** 2026-07-12
**Deployed:** 2026-07-12 · Version 0.27.28 · https://jupiter.auxevo.tech

## Problem / Motivation
Nutzer meldete: bei der **Claude**-Engine wächst nach mehreren Runden die Anzahl **identischer** Decision-Cards/Frageboxen (`jupiter-question`) immer weiter an — bis zu 6 gleiche „Wie weiter?"-Karten übereinander. Bei **Codex** tritt das Problem nicht auf. Belegscreenshot: zwei bitgleiche „Claude fragt dich – Wie weiter?"-Karten (`crypto_mts_ui`, 21 Turns).

**Root Cause (durch Log-Analyse + Reproduktionstest verifiziert):**

Claude läuft als **langlebige tmux-Session** (PROJ-63). Der Pane-Wrapper schreibt stdout per `>> out.log` (Append, nie truncate), und die tmux-Session-/Verzeichnisnamen leiten sich aus der `session_id` ab — jeder `claude --resume` schreibt also in **dieselbe, wachsende** `out.log`. Bei jedem `_resume` (`manager.py`) wird eine **frische** `TmuxTransport(session_id)` gebaut; deren `spawn()` öffnet das Lese-Handle mit `open(out_path, "rb")` **ab Offset 0** (kein Seek-to-End, keine Offset-Persistenz). `_read_stdout` liest daraufhin die **komplette Historie erneut** und emittiert jedes vergangene `assistant`-Event nochmal.

Das erneute Lesen ist für Claude **beabsichtigt** — das UI-Transkript wird für Claude NICHT aus der DB rehydriert (nur Nicht-Claude-Engines, PROJ-66), sondern aus der out.log wiederaufgebaut. Der Defekt: die re-emittierten `assistant`-Events durchlaufen `handle_event` → `_extract_question_block` → `_open_user_question`, und **`_open_user_question` war nicht idempotent** — es erzeugte pro Durchlauf eine weitere Karte mit frischer `uuid4()`. Offene Karten werden zudem nicht persistiert und über einen Resume hinweg nicht abgeräumt. Folge: K Resumes ⇒ K+1 identische Karten (auto-Reanimierung, manuelles Reanimieren, Backend-Neustart/Deploy — bei häufigen Deploys entsteht so das „bis 6").

Codex/OpenCode sind **oneshot** (jeder Turn ein eigener Prozess, Transkript aus der DB rehydriert) → sie treffen den out.log-Re-Read nicht und duplizieren nicht.

## Dependencies
- Requires: PROJ-48 (Fragekarten-Vertrag/`_open_user_question`), PROJ-63 (langlebiger tmux-Transport mit wiederverwendeter out.log), PROJ-27/PROJ-45 (Resume/Reanimierung), PROJ-66 (Transkript-Persistenz — Claude liest bewusst NICHT zurück).

## Scope-Abgrenzung (bewusst)
- **In Scope:** `_open_user_question` (`backend/app/engine/manager.py`) idempotent machen — bei einer bereits **offenen** Fragekarte mit **identischem** Inhalt kein zweites Öffnen.
- **NICHT in Scope:** das Offset-0-Re-Lesen der out.log unterbinden (Seek-to-End). Das Re-Lesen ist der beabsichtigte Weg, Claudes Transkript nach Restart/Resume wiederaufzubauen — ein Seek-to-End würde das Transkript leeren. Fix daher an der Karten-Schicht, nicht am Transport.
- **Unberührt:** Codex/OpenCode/OpenAI-Pfade, Transkript-Wiederaufbau, Kosten-/Turn-Zählung.

## Acceptance Criteria
- [x] Ein wiederholtes, inhaltsgleiches `jupiter-question`-assistant-Event öffnet **keine** zweite offene Fragekarte (Idempotenz-Guard: gleiche `tool_name=="AskUserQuestion"` + `state==OPEN` + identisches `tool_input`).
- [x] Die erste Fragekarte entsteht unverändert; Erst-Emission → genau eine Karte, Status `awaiting_approval`.
- [x] Inhaltlich **unterschiedliche** Fragen öffnen weiterhin je eine eigene Karte (nur identische werden dedupliziert).
- [x] Codex-/Claude-Fragekarten-Wege unverändert (bestehende Suite `test_proj4_decision_cards.py` grün).
- [x] Neuer Regressionstest: dreifache Emission desselben Markers → genau eine offene Karte.

## Reproduktion
- `test_replayed_question_marker_does_not_duplicate_card` (`backend/tests/test_proj4_decision_cards.py`): derselbe assistant-Marker wird 3× durch `handle_event` geschickt (simuliert den out.log-Re-Read bei zwei Resumes). **Vor dem Fix:** 3 identische Karten. **Nach dem Fix:** genau 1.

## Technical Requirements
- `backend/app/engine/manager.py` — `_open_user_question()`: Idempotenz-Guard gegen bereits offene, inhaltsgleiche Fragekarte.
- `backend/tests/test_proj4_decision_cards.py` — Regressionstest.

## Rest-Risiko / Nächster Schritt
- Nebenbefund (nicht Teil dieses Fixes): Beim Backend-Neustart mit leerem `pending` re-erzeugt der out.log-Re-Read auch bereits **beantwortete** frühere Fragen als offene Karten (die Auflösung steht nicht in der out.log). Selten und separat zu bewerten (ggf. eigenes Ticket: Fragekarten-Auflösung in der out.log markieren oder Karten persistieren). Der hier gelieferte Guard entschärft das kumulative Wachstum identischer Karten, das der Nutzer gemeldet hat.
- Deploy: human-gated → `/abc-deploy`.

---
<!-- Sections below are added by subsequent skills -->
