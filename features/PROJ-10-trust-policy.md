# PROJ-10: Trust-Policy — abgestuftes, konfigurierbares Vertrauen

## Status: Planned
**Created:** 2026-06-23
**Last Updated:** 2026-06-23
**Baustein:** #5

## Dependencies
- Requires: PROJ-4 (Decision Cards) — die Policy entscheidet, was eine Card erzeugt (erweitert die heutige fixe `engine/policy.py`); nutzt die Pause-+-Card-+-Resume-Maschinerie.
- Requires: PROJ-6 (Knappheits-Konstitution / Rollen) — Policy ist pro Rolle/Skill/Projekt konfigurierbar.
- Requires: PROJ-8 (Phasenerkennung) — liefert das Signal für das **Phasen-Übergangs-Gate** (`abc_phase`-Wechsel).
- Requires: PROJ-1 (Engine / `permission_mode`) — die **bypass-festen** Gates müssen auch bei `bypassPermissions` greifen.
- Verwandt: PROJ-16 (Watchdog) — nutzt dieselbe Policy + dasselbe „pausieren statt killen"-Prinzip als Reißleine.

## Beschreibung
Im MVP gibt es einen **fixen, konservativen** Freigabe-Trigger (jede schreibende Aktion → Card). Dieses Feature macht Vertrauen zu einer **konfigurierbaren Richtlinie pro Kontext**: Pro Rolle/Skill/Projekt wird festgelegt, was **autonom** läuft (Auto-Approve), was eine **Decision Card** erzeugt und was **hart verboten** ist. Default bleibt „möglichst autonom, aber sicher".

### Zwei Durchsetzungs-Ebenen (wichtig wegen Bypass)
Die heutigen Per-Tool-Cards hängen am **Claude-Permission-Hook** — `bypassPermissions` (PROJ-1) umgeht diesen Pfad, daher laufen im Bypass die operativen Freigaben (Bash & Co.) bewusst durch. Damit bestimmte Gates **trotzdem** greifen, kennt die Policy zwei Ebenen:
1. **Hook-Ebene (operativ):** `auto-allow` / `card` / `deny` pro Tool — über den Permission-Hook. Wird vom Bypass übersprungen (gewollt).
2. **Bypass-feste Gates („hart"):** von **Jupiter selbst** durchgesetzt (Backend erkennt das Ereignis → **pausiert die Session** → öffnet eine Decision Card → läuft erst nach Freigabe weiter), **unabhängig** vom `permission_mode`. Diese feuern auch bei `bypassPermissions`.

### Phasen-Übergangs-Gate (erstes bypass-festes Gate)
Beim Wechsel der **ABC-Phase** (z. B. Architecture → Frontend, erkannt über PROJ-8s `abc_phase`-Signal) wird **immer** — auch im Bypass — eine **Decision Card** erzeugt, bevor die nächste Phase startet. So bleibt der Mensch an den **Schaltstellen** in der Schleife, während die kleinteilige Arbeit innerhalb einer Phase (im Bypass) ungebremst läuft. Welche Übergänge gaten, ist konfigurierbar (Default: jeder Phasenwechsel).

## User Stories
- Als Nutzer möchte ich pro Rolle/Skill festlegen, welche Tool-Klassen autonom laufen dürfen, um vertraute Abläufe nicht ständig freigeben zu müssen.
- Als Nutzer möchte ich bestimmte Aktionen (z. B. `rm -rf`, force-push, Schreiben außerhalb des Projekts) **hart verbieten**, unabhängig vom Kontext.
- Als Nutzer möchte ich eine projektweite Default-Policy plus rollen-/skillspezifische Übersteuerungen pflegen.
- Als Nutzer möchte ich sehen, **welche Regel** eine konkrete Decision Card ausgelöst hat (Nachvollziehbarkeit).
- Als Nutzer möchte ich Policy-Änderungen ohne Backend-Neustart wirksam machen.
- Als Nutzer möchte ich, dass am **Phasenwechsel** (z. B. Architecture → Frontend) eine Freigabe kommt, damit ich an den Schaltstellen entscheide — **auch wenn die Session im Bypass-Modus läuft**.
- Als Nutzer möchte ich pro Projekt/Rolle festlegen können, **welche** Phasenübergänge eine Freigabe brauchen (oder alle).
- Als Nutzer möchte ich, dass solche „harten" Gates vom `bypassPermissions`-Modus **nicht** ausgehebelt werden.

## Acceptance Criteria
- [ ] Es gibt drei Vertrauensstufen pro Regel: **auto-allow**, **card** (Freigabe nötig), **deny** (hart verboten).
- [ ] Regeln können nach **Tool-Klasse** (Bash/Edit/Write/…) und **Kontext** (Rolle, Skill, Projekt) gematcht werden; spezifischere Regel schlägt allgemeinere.
- [ ] Eine **deny**-Regel verhindert die Aktion und erzeugt eine ablehnende Card-Notiz mit Begründung — die Aktion wird nie ausgeführt.
- [ ] Der Default (keine passende Regel) ist konservativ: schreibende/destruktive Tools → **card**, Lesezugriffe → **auto-allow** (= heutiges Verhalten).
- [ ] Jede erzeugte Card nennt die **auslösende Regel** (welche Stufe, welcher Match).
- [ ] Policy ist als Konfiguration editierbar (UI oder Settings) und wird **live** neu geladen, ohne Sessions zu unterbrechen.
- [ ] Bestehende PROJ-4-Cards funktionieren unverändert, wenn keine Policy gepflegt ist (Rückwärtskompatibilität).
- [ ] **Bypass-feste Gates:** Die Policy kennt Gates, die **unabhängig vom `permission_mode`** greifen — von Jupiter durchgesetzt (pausieren → Card → resume), nicht über den Claude-Permission-Hook.
- [ ] **Phasen-Übergangs-Gate:** Bei einem von PROJ-8 erkannten `abc_phase`-Wechsel wird **vor** dem Start der neuen Phase eine Decision Card erzeugt — **auch bei `bypassPermissions`** —; die Session pausiert bis zur Freigabe.
- [ ] Die zu gatenden Phasenübergänge sind **konfigurierbar** (Default: jeder Wechsel); Freigeben setzt die Session fort, Ablehnen/Mit-Kommentar wirkt wie bei PROJ-4.
- [ ] Im Bypass laufen die **operativen** Per-Tool-Freigaben (Bash etc.) weiterhin durch (nur die harten Gates feuern).
- [ ] **Phasenerkennung bypass-fest:** Das `abc_phase`-Signal wird so ermittelt, dass es auch im Bypass zuverlässig vorliegt (nicht ausschließlich am Permission-Hook hängend — ggf. aus dem `stream-json`-Verlauf), damit das Gate + die Gantt-Anzeige (PROJ-8) im Bypass nicht stocken.
- [ ] Alle Texte deutsch.

## Edge Cases
- **Widersprüchliche Regeln** (eine auto-allow, eine deny für denselben Match) → die restriktivere (deny) gewinnt; Konflikt wird geloggt.
- **Policy-Datei kaputt/ungültig** → Fallback auf konservativen Default, sichtbare Warnung, kein Crash.
- **Neue, unbekannte Tool-Klasse** → Default-Stufe (card), nie versehentlich auto-allow.
- **Auto-allow trotz Watchdog-Alarm** (PROJ-16) → Watchdog kann eine auto-allow-Aktion dennoch pausieren (Reißleine sticht Komfort).
- **Rolle ohne Policy** → projektweiter Default greift.
- **Phasenwechsel im Bypass** → Phasen-Gate feuert trotzdem (harter Gate, hookt nicht an der Permission-Prüfung).
- **Nicht-linearer Phasensprung** (z. B. Frontend ↔ Backend hin und her) → Gate pro tatsächlich erkanntem Wechsel; kein Doppel-Feuern beim selben Übergang (Entprellung).
- **Phase nicht erkennbar** (Skill ohne klaren abc-Bezug) → kein Phasen-Gate, nur die operative Hook-Ebene greift.
- **Nutzer lehnt den Phasenübergang ab** → Session bleibt in der alten Phase pausiert; Kommentar reist (wie bei PROJ-4) als Begründung zurück.

## Technical Requirements (optional)
- Erweitert `backend/app/engine/policy.py` (heute fixe `AUTO_ALLOW_TOOLS`) um die Stufen-Logik (Hook-Ebene).
- **Bypass-feste Gates** liegen **nicht** im Permission-Hook, sondern im Engine-Event-/Phasen-Pfad (`SessionManager`): erkannter Phasenwechsel → vorhandene Pause-+-Card-+-Resume-Mechanik (PROJ-4 `request_decision`/Futures) wiederverwenden, getriggert vom Backend statt von Claudes Permission-Entscheidung.
- **Phasenerkennung entkoppeln:** das `abc_phase`-Signal (PROJ-8) sollte auch im Bypass anliegen — d. h. nicht ausschließlich am Permission-Hook hängen (Fallback/Primär: Skill-Tool-Aufruf aus dem `stream-json`-Verlauf).
- Konfig versioniert/serverseitig; Secrets/Pfade nie aus Client-Payload.
- Auswertung pro Tool-Call < 5 ms (im Permission-Hook-Pfad).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
