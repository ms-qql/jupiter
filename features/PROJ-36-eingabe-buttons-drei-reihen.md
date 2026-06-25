# PROJ-36: Eingabe-Buttons auf drei Reihen (Senden · Mikrofon+Büroklammer · Stop)

## Status: In Progress
**Created:** 2026-06-25
**Last Updated:** 2026-06-25

## Implementation Notes (Frontend)
- **`session-clipboard-button.tsx`**: Auf Icon-only umgestellt (`size="icon"`). Textbeschriftung „Anhängen"/„Lädt…" entfällt; `uploading` zeigt jetzt `Loader2`-Spinner statt `Paperclip`. Deutsches `aria-label` (`„Datei anhängen"` / `„Datei wird angehängt…"`) + `title` bleiben. Neue optionale `className`-Prop (via `cn`), damit der Composer `flex-1` zum Füllen der Icon-Reihe durchreichen kann.
- **`sessions/[id]/page.tsx`**: Button-Spalte von 4 auf 3 Reihen reduziert. Reihe 2 ist eine `flex gap-2`-Gruppe mit `PushToTalkButton` (links) + `SessionClipboardButton` (rechts), beide `flex-1` → gleich breit, kein Umbruch bei 375 px. Senden bleibt Reihe 1, Stop Reihe 3 (konditional `!ended`). Höhe weiter aus den Buttons abgeleitet (kein Magic-Number) → PROJ-29-Symmetrie unverändert.
- **`push-to-talk-button.tsx`**: Unverändert (war schon `size="icon"` + deutsches `aria-label`), nur neu platziert + `flex-1` über bestehende `className`-Prop.
- Verifikation: `tsc`/`eslint` auf den geänderten Dateien sauber. Kein Backend, keine API-Änderung.

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

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-25 · **Stack:** Next.js 16 (App Router) Frontend-only — kein Backend, keine DB · **Branch:** dev

### Einordnung
Reiner Layout-/Markup-Fix an **einer** bestehenden Stelle (Session-Composer). Keine neue Route, kein State, keine API. Risiko minimal; Hauptaugenmerk: Höhen-Symmetrie (PROJ-29) und Barrierefreiheit der Icon-only-Reihe nicht brechen.

### Komponenten-Struktur (Ist → Soll)
Heute (4 vollbreite Reihen, `sessions/[id]/page.tsx:363`):
```
Button-Spalte (flex-col)
├── Senden          (volle Breite)
├── Anhängen        (Icon + Text, volle Breite)
├── Mikrofon        (size=icon, volle Breite)
└── Stop            (volle Breite, nur wenn !ended)
```
Soll (3 Reihen):
```
Button-Spalte (flex-col)
├── Senden                         ← Reihe 1, volle Breite
├── Icon-Reihe (flex, 2 Spalten)   ← Reihe 2
│   ├── Mikrofon  (size=icon)      links
│   └── Büroklampe (size=icon)     rechts
└── Stop                           ← Reihe 3, volle Breite (nur wenn !ended)
```

### Umzusetzen
1. **`session-clipboard-button.tsx`** — Icon-only-Variante: Text „Anhängen"/„Lädt…" entfällt, Button wird `size="icon"`; statt Text ein Lade-Zustand über das Icon (z. B. `Loader2` spinnend bei `uploading`, sonst `Paperclip`) analog zu `push-to-talk-button.tsx`. `aria-label`/`title` deutsch: „Datei anhängen" (bzw. „Lädt…" während Upload). Upload-Verhalten (`onPick`, `disabled`, `uploading`) bleibt 1:1.
2. **`sessions/[id]/page.tsx`** (Composer) — Mikrofon + Büroklammer in eine **2-Spalten-Flex-Reihe** zusammenfassen (`flex gap-2`, beide `flex-1`/gleich hoch), zwischen Senden (oben) und Stop (unten). `items-stretch`-Symmetrie der Textarea bleibt, da Höhe weiterhin aus den Button-Reihen abgeleitet wird (kein Magic-Number).
3. **`push-to-talk-button.tsx`** — unverändert (schon `size="icon"` + deutsches `aria-label`); nur Platzierung in der Icon-Reihe.

### Tech-Entscheidungen (Begründung)
- **Icon-only statt Text für Anhängen:** zwei Icon-Aktionen (Mikro/Büroklammer) teilen sich eine Reihe → spart eine volle Zeile; deutsches `aria-label`/`title` erhält Barrierefreiheit trotz fehlendem Text.
- **Höhe aus Buttons abgeleitet (kein Pixel-Wert):** verhindert ein erneutes Brechen der PROJ-29-Symmetrie; die Textarea (`items-stretch`) folgt automatisch der neuen, niedrigeren Button-Spalte.
- **Reihe 2 als Flex mit gleich breiten Buttons:** auch bei 375 px kein Umbruch/Überlappen; Mindest-Tap-Größe über `size="icon"`.
- **Stop bleibt konditional unten:** bei beendeter Session (`ended`) entfällt Reihe 3 → sauberes 2-Reihen-Layout (Senden + Icon-Reihe), keine schwebende Lücke.

### Betroffene Dateien
- `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx` (Composer-Markup, Reihe-2-Gruppe)
- `nextjs_app/components/cockpit/session-clipboard-button.tsx` (Icon-only-Variante)
- `push-to-talk-button.tsx` — nur Platzierung, keine Änderung nötig
- Test-Hinweis QA: kein Backend; visuelle Prüfung Senden/Icon-Reihe/Stop + 375 px, plus Snapshot/Render-Test, dass die Büroklammer ein `aria-label` trägt.

### Dependencies
Keine neuen Pakete. Genutzt: `lucide-react` (`Paperclip`, `Loader2`, `Mic`, `Square` — bereits im Projekt), shadcn/ui `Button` (`size="icon"`).
