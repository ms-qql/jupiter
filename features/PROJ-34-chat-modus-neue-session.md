# PROJ-34: Chat-Modus im Neue-Session-Dialog (freies Chatfenster ohne ABC-Bezug)

## Status: Planned
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-3 (Cockpit / Neue-Session-Dialog) — der Modus-Umschalter und die ausgegraute Vorauswahl leben im `NewSessionDialog`.
- Requires: PROJ-9 (Smart Launcher) — der „Vorschlag aus dem Workflow" / „Weitere offene Features"-Block ist das, was im Chat-Modus ausgegraut wird.
- Requires: PROJ-1 (Engine-Treiber) — eine Chat-Session ist eine ganz normale Engine-Session (gleicher `POST /sessions`).

## Beschreibung
Im **Neue-Session-Dialog** wird man heute immer in die **ABC-Projekt-/Feature-Vorauswahl** geführt (Smart-Launcher-Vorschlag + „Weitere offene Features"). Es fehlt die Möglichkeit, im **gleichen Projektordner** einfach **ein reines Chatfenster** zu öffnen, um andere Dinge zu besprechen, ohne ein Feature/eine abc-Phase zu verknüpfen.

Gewünscht: ein **kleiner Umschalter** (z. B. Knopf/Segment „Chat" neben dem Default „Workflow/ABC"). Bei Auswahl **„Chat"** wird die **ABC-/Feature-Vorauswahl ausgegraut** (deaktiviert, nicht entfernt) und es wird **keine Feature-/Rollen-Verknüpfung** gesetzt. Es wird trotzdem eine **ganz normale Session** gestartet — gleicher Request, Engine/Modell/Berechtigung weiterhin wählbar, gleicher Projektpfad. Nur eben ohne abc-Bezug (laut Klärung 2026-06-25: kein eigenes Backend-Flag, kein Sonder-Lifecycle).

## User Stories
- Als Nutzer möchte ich im Neue-Session-Dialog zwischen **„Workflow/ABC"** und **„Chat"** umschalten können, um im selben Projektordner auch mal frei reden zu können, ohne ein Feature zu starten.
- Als Nutzer möchte ich, dass im **Chat-Modus** die ABC-/Feature-Vorauswahl **sichtbar, aber ausgegraut** ist, damit klar ist, dass sie bewusst deaktiviert wurde (statt zu verschwinden).
- Als Nutzer möchte ich im Chat-Modus weiterhin **Engine, Modell und Berechtigung** wählen können, weil ich auch im freien Chat das richtige Modell brauche.
- Als Nutzer möchte ich, dass eine im Chat-Modus gestartete Session **als normale Session** im Cockpit/in der Sidebar auftaucht, damit ich sie wie jede andere weiterführen kann.

## Acceptance Criteria
- [ ] Der Neue-Session-Dialog hat einen **Umschalter mit zwei Zuständen**: „Workflow/ABC" (Default, heutiges Verhalten) und „Chat".
- [ ] Default beim Öffnen ist **„Workflow/ABC"** — das bestehende Verhalten bleibt unverändert.
- [ ] Bei Auswahl **„Chat"** wird der gesamte ABC-Block (Smart-Launcher-Vorschlag „VORSCHLAG AUS DEM WORKFLOW", „Vorschlag starten", „Weitere offene Features") **sichtbar ausgegraut und nicht klickbar**.
- [ ] Im Chat-Modus ist **keine Feature-ID** und **keine abc-Rolle** vorausgewählt; ein zuvor (im Workflow-Modus) gewähltes Feature wird beim Wechsel nach „Chat" **entworfen/zurückgesetzt**.
- [ ] Im Chat-Modus bleiben **Projekt(-Titel), Projekt-Pfad, Initial-Prompt, Engine, Modell, Berechtigung** voll bedienbar.
- [ ] „Session starten" im Chat-Modus erzeugt eine **normale Session** (`POST /sessions`) **ohne** Feature-/abc-Verknüpfung im Payload; die Session erscheint danach wie üblich in der Sidebar und im Cockpit.
- [ ] Wechsel **zurück nach „Workflow/ABC"** reaktiviert den ABC-Block und lädt den Smart-Launcher-Vorschlag wie bisher (debounced beim Pfadwechsel).
- [ ] Alle Beschriftungen/Tooltips sind **deutsch**.

## Edge Cases
- **Wechsel mit bereits gewähltem Feature:** Nutzer wählt im Workflow-Modus ein Feature und schaltet dann auf „Chat" → Feature-Auswahl wird verworfen; schaltet er zurück, ist nichts vorausgewählt (kein „Geister"-Feature).
- **Projekt ohne abc-Struktur:** Im Workflow-Modus liefert der Launcher „kein abc erkannt"; der Chat-Modus muss auch hier sauber funktionieren (gleicher freier Start).
- **Leerer Initial-Prompt:** Pflichtfeld-Verhalten bleibt wie im Workflow-Modus (Start nur mit Prompt) — der Chat-Modus hebt keine bestehenden Pflichtfelder auf.
- **Pfadwechsel im Chat-Modus:** Ein Pfadwechsel soll im Chat-Modus **keinen** störenden Launcher-Request auslösen bzw. dessen Ergebnis nicht sichtbar einblenden (Block bleibt ausgegraut).
- **Schmaler Viewport:** Der Umschalter darf das Dialog-Layout auf 375 px nicht sprengen.

## Technical Requirements (optional)
- Reiner **Frontend-Fix** im `NewSessionDialog` (`nextjs_app/components/cockpit/new-session-dialog.tsx`); **keine** neue Backend-/DB-/Schema-Änderung (Chat = normale Session ohne abc-Felder im Payload).
- Der „Chat"-Zustand ist **lokaler Dialog-State**; beim Start wird der bestehende `createSession`-Payload nur **ohne** Feature-/Rollen-Verknüpfung gebaut.
- Ausgegraut = `disabled`/reduzierte Opazität, **nicht** entfernen (Erkennbarkeit, dass es bewusst deaktiviert ist).
- Texte/Tooltips deutsch; shadcn/ui-Primitive (z. B. Toggle/SegmentedControl) statt handgerollter Button-Logik.
