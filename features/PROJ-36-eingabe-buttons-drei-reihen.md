# PROJ-36: Eingabe-Buttons auf drei Reihen (Senden · Mikrofon+Büroklammer · Stop)

## Status: Planned
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Dependencies
- Requires: PROJ-3 (Cockpit / Session-Eingabeleiste) — der Composer im Session-Detail.
- Requires: PROJ-20 (Spracheingabe / Push-to-Talk) — durch das neue **Mikrofon-Icon** ist die Button-Spalte auf vier Reihen gewachsen.
- Requires: PROJ-11 (Fileexplorer / „Anhängen") — liefert den Anhängen-Button (Büroklammer).
- Verwandt: PROJ-29 (Eingabefeld-Höhe symmetrisch zur Button-Gruppe) — die Höhen-Symmetrie muss nach der Umstellung auf 3 Reihen weiter greifen.

## Beschreibung
Seit das **Mikrofon-Icon** (PROJ-20) in die Eingabeleiste kam, hat die rechte Button-Spalte **vier Reihen** (Senden · Anhängen · Mikrofon · Stop) — sie ist zu hoch geworden. Gewünscht ist ein **kompakteres 3-Reihen-Layout**:

```
┌───────────────┐
│    Senden     │   ← Reihe 1 (volle Breite)
├───────┬───────┤
│  🎤   │  📎   │   ← Reihe 2: links Mikrofon, rechts Büroklammer (Anhängen)
├───────┴───────┤
│     Stop      │   ← Reihe 3 (volle Breite)
└───────────────┘
```

Der **Anhängen-Button** verliert seine Textbeschriftung „Anhängen" und wird zum **reinen Icon (Büroklammer)**, damit er mit dem Mikrofon **in eine Reihe** passt. Verhalten aller Buttons bleibt unverändert (Senden, Anhängen-Upload, Diktat, Stop).

## User Stories
- Als Nutzer möchte ich, dass die Eingabeleiste nur noch **drei Reihen** hoch ist, damit der Composer kompakter ist und mehr Platz fürs Gespräch bleibt.
- Als Nutzer möchte ich **Mikrofon und Büroklammer in einer Reihe** nebeneinander, weil beide Icon-Aktionen sind und nicht je eine volle Zeile brauchen.
- Als Nutzer möchte ich den **Anhängen-Button nur als Büroklammer-Icon**, damit er platzsparend neben das Mikrofon passt; die Funktion (Datei anhängen) bleibt gleich.
- Als Nutzer möchte ich, dass **Senden oben** und **Stop unten** weiterhin gut erreichbar und klar als Primär-/Abbruch-Aktion erkennbar sind.

## Acceptance Criteria
- [ ] Die Button-Spalte hat genau **drei Reihen**: (1) **Senden** volle Breite, (2) **Mikrofon links + Büroklammer rechts** in einer Reihe, (3) **Stop** volle Breite.
- [ ] Der **Anhängen-Button** zeigt **nur das Büroklammer-Icon** (keine Textbeschriftung „Anhängen") und behält seine Upload-Funktion (Datei anhängen → Pfad in Prompt).
- [ ] **Mikrofon** und **Büroklammer** stehen in Reihe 2 **nebeneinander** (Mikro links, Büroklammer rechts) und sind gleich hoch.
- [ ] Der **Stop-Button** bleibt unten; entfällt er bei beendeter Session, bleibt das Layout konsistent (dann Senden + Icon-Reihe, sauber abgeschlossen).
- [ ] **Tooltips/aria-Labels** bleiben deutsch und beschreiben die Aktionen (Mikrofon = „Spracheingabe", Büroklammer = „Datei anhängen") — Barrierefreiheit trotz Icon-only.
- [ ] Die **Höhen-Symmetrie** zwischen Textarea und Button-Gruppe (PROJ-29) bleibt erhalten — Eingabefeld schließt bündig zur 3-Reihen-Gruppe ab.
- [ ] Keine Funktionsänderung an Senden, Upload, Diktat oder Stop.

## Edge Cases
- **Beendete Session (kein Stop):** Layout bleibt stimmig (zwei Reihen: Senden + Icon-Reihe), keine schwebenden Lücken; Höhen-Symmetrie folgt automatisch (PROJ-29).
- **Push-to-Talk aktiv/aufnehmend:** Der Mikrofon-Button zeigt seinen Aufnahmezustand wie bisher, auch in der schmaleren Icon-Reihe.
- **Upload läuft (`uploading`):** Büroklammer zeigt Lade-/Disabled-Zustand wie bisher, ohne die Reihe zu verschieben.
- **Schmaler Viewport (375 px):** Die Icon-Reihe (Mikro+Büroklammer) darf nicht umbrechen oder überlappen; Buttons bleiben tappbar (Mindestgröße).
- **Disabled-Zustände** (z. B. Senden bei leerem Input, pending Decision Card) bleiben unverändert wirksam.

## Technical Requirements (optional)
- Reiner **Frontend-/Layout-Fix** in der Session-Eingabeleiste (`nextjs_app/app/(cockpit)/sessions/[id]/page.tsx`), ggf. minimal an `session-clipboard-button.tsx` (Icon-only-Variante) und `push-to-talk-button.tsx`.
- **Keine** Backend-/API-Änderung.
- Reihe 2 als kleine 2-Spalten-Flex/Grid-Gruppe innerhalb der bestehenden Button-Spalte; shadcn/ui-Button mit `size="icon"` für die Icon-Buttons.
- Höhe weiterhin **aus den Buttons abgeleitet** (kein Magic-Number), damit PROJ-29-Symmetrie nicht erneut bricht.
- Icon-only-Buttons brauchen `aria-label`/`title` (deutsch) für Zugänglichkeit.
