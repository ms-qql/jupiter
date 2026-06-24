# PROJ-20: Spracheingabe / Push-to-Talk (abo-frei, DSGVO-konform)

## Status: Deployed
**Created:** 2026-06-23
**Last Updated:** 2026-06-24
**Baustein:** #29

## Dependencies
- Requires: PROJ-9 (Smart Launcher) — Diktat fürs Auftrag-/Prompt-Feld beim Session-Start.
- Requires: PROJ-4 (Decision Cards) — Diktat für Card-Antworten/Kommentare.

## Beschreibung
**Push-to-Talk-Diktat** statt Tippen — für das Auftrag-Feld im Smart Launcher (#12) und für Decision-Card-Antworten (#4). **Kein Monats-Abo** (kein WhisperFlow) und **DSGVO-konform**: Standard ist **self-hosted Whisper auf dem VPS** (`faster-whisper`/`whisper.cpp`, lokal, keine laufenden Kosten); optionaler Schnell-Fallback **Groq Whisper** (pay-per-use). Die **Browser Web Speech API ist verworfen** (sendet Audio an Google → kollidiert mit der DSGVO-Linie).

## User Stories
- Als Nutzer möchte ich per Push-to-Talk meinen Auftrag ins Smart-Launcher-Feld diktieren, statt zu tippen.
- Als Nutzer möchte ich Decision-Card-Kommentare/Antworten diktieren können.
- Als Nutzer möchte ich, dass die Transkription standardmäßig **lokal auf dem VPS** läuft, damit keine Audiodaten das System verlassen.
- Als Nutzer möchte ich optional einen schnelleren Cloud-Fallback (Groq) aktivieren, wenn ich das bewusst will.
- Als Nutzer möchte ich das Transkript vor dem Absenden sehen und korrigieren.

## Acceptance Criteria
- [ ] **Push-to-Talk**-Aufnahme im Auftrag-Feld (PROJ-9) und in Card-Antworten (PROJ-4): aufnehmen → transkribieren → Text einfügen.
- [ ] **Standard-Transkription self-hosted** auf dem VPS (faster-whisper/whisper.cpp); kein API-Key nötig, keine laufenden Kosten.
- [ ] **Optionaler Groq-Fallback** ist konfigurierbar (API-Key in `.env`), standardmäßig **aus**; Umschalten ist eine bewusste Nutzerentscheidung.
- [ ] **Browser Web Speech API wird nicht verwendet** (kein Audio an Google); Audio geht nur an die konfigurierte (lokale/EU-)Transkription.
- [ ] Das **Transkript ist vor dem Absenden editierbar** (Korrektur), nicht auto-submit.
- [ ] Mikrofon-Zugriff scheitert/verweigert → klare Meldung, Tippen bleibt jederzeit möglich.
- [ ] Alle Texte deutsch; Aufnahme-/Transkriptions-/Fehler-Zustände sichtbar.

## Edge Cases
- **Kein Mikrofon / Permission verweigert** → verständlicher Hinweis, Feature degradiert auf Texteingabe.
- **Whisper-Dienst nicht erreichbar** → Fehlermeldung + (falls konfiguriert) Angebot Groq-Fallback; nie stiller Verlust der Aufnahme.
- **Lange Aufnahme** → Größen-/Längenlimit mit Hinweis; Transkription gestreamt/segmentiert.
- **Schlechte Audioqualität** → Transkript trotzdem anzeigen (editierbar), keine Auto-Aktion.
- **Groq aktiviert ohne Key** → Setup-Hinweis, bleibt auf self-hosted.
- **Mehrsprachigkeit** → Sprache konfigurierbar/Autodetect, Default Deutsch.

## Technical Requirements (optional)
- Muster analog `watch`-Skill: self-hosted Whisper als Standard, Groq als optionaler pay-per-use-Fallback.
- DSGVO: keine US-Browser-Speech-API; Audio-Upload nur an konfigurierten lokalen/EU-Endpunkt; Secrets via `.env`.
- Audio wird nach Transkription nicht dauerhaft gespeichert (sofern nicht bewusst aktiviert).

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js 16 (App Router) + FastAPI (conda `Dashboard`) + faster-whisper (in-process) · **Branch:** dev

### Überblick & Kernentscheidung
Push-to-Talk-Diktat als wiederverwendbare Frontend-Komponente (Mikrofon-Button) plus **ein** neuer
Backend-Endpunkt zum Transkribieren. Standard ist **self-hosted faster-whisper als In-Process-Python-Lib**
im `Dashboard`-Env (kein extra Dienst, kein Port, Modell einmal in den RAM geladen), Modellgröße **`small`**
(gutes Deutsch, CPU-tauglich, ~1–2 GB RAM). Optionaler **Groq-Fallback** (`whisper-large-v3`) ist per `.env`
konfigurierbar und standardmäßig **aus**. Die Browser **Web Speech API wird bewusst nicht verwendet**
(DSGVO: kein Audio an Google).

### A) Komponenten-Struktur (UI)
```
PushToTalkButton (neue, wiederverwendbare Komponente — components/cockpit/push-to-talk-button.tsx)
├── Mic-Icon-Button (shadcn/ui Button, neben dem jeweiligen Textfeld)
├── Zustände: idle · recording (rote Pulse-Anzeige) · transcribing (Spinner) · error (Tooltip)
├── nutzt MediaRecorder (Browser) → Audio-Blob (webm/opus)
└── liefert Transkript per Callback → ruft setValue(prev + transcript) des Zielfelds

Eingebunden an zwei Stellen (Transkript wird ins Feld eingefügt, NICHT auto-submit):
├── NewSessionDialog  → neben <Textarea id="initial_prompt">  (new-session-dialog.tsx:267)
└── DecisionCard      → neben <Textarea value={comment}>      (decision-card.tsx:399)
    (Question-Card-Freitextfeld optional in gleicher Manier — Input statt Textarea)

Settings (Transkriptions-Quelle umschalten):
└── kleine Toggle-Zeile „Cloud-Fallback (Groq)" im bestehenden Settings-Bereich,
    nur sichtbar/aktivierbar wenn Groq-Key konfiguriert ist
```

### B) Datenmodell (Klartext)
Es wird **nichts dauerhaft gespeichert**. Audio existiert nur transient während der Anfrage:
```
Aufnahme (transient): Audio-Blob im Browser → POST an Backend → Transkription → Audio verworfen.
Transkript: lebt nur im Frontend-State des Zielfelds, bis der Nutzer absendet.

Konfiguration (in-memory Settings + .env):
- whisper_model         : Modellname (Default "small"), JUPITER_WHISPER_MODEL
- whisper_language      : Default "de", autodetect optional, JUPITER_WHISPER_LANGUAGE
- groq_api_key          : optionaler Key (leer = Fallback nicht verfügbar), JUPITER_GROQ_API_KEY
- use_groq_transcription: bool, Default false (bewusste Nutzerentscheidung)
- max_audio_seconds     : Längenlimit (z. B. 120 s), JUPITER_MAX_AUDIO_SECONDS
```
Keine DB-Tabelle, kein MinIO — reines Transkriptions-Feature.

### C) API-Form (nur Endpunkte, kein Code)
```
- POST /transcription            → Audio (multipart) entgegennehmen, transkribieren,
                                    { transcript, provider } zurückgeben.
                                    provider = "faster-whisper" | "groq".
                                    Wählt Engine: use_groq && key vorhanden → Groq, sonst lokal.
- GET  /settings/transcription   → { use_groq, groq_available, model, language }
- PATCH /settings/transcription  → use_groq umschalten (400, wenn Groq an ohne Key)
```
Muster analog `backend/app/routes/files.py:77` (UploadFile + Form) und `routes/settings.py:29`
(GET/PATCH read-/patch-Modelle). Registrierung via `app.include_router(...)` in `main.py:132`.
Frontend ruft per `FormData`-Upload (analog `uploadFiles` in `lib/api.ts:391`), Settings per JSON
(`request(...)`-Wrapper, `api.ts:50`).

### D) Tech-Entscheidungen (WARUM)
- **In-Process faster-whisper statt separatem Dienst:** läuft im selben `Dashboard`-Env wie das Backend
  — keine zusätzliche systemd-Unit, kein Port, kein IPC. Modell wird beim ersten Aufruf lazy geladen
  und im RAM gehalten (warme Folge-Transkriptionen). Geringster Deploy-/Betriebs-Aufwand.
- **Modell `small`:** bester Kompromiss aus Deutsch-Qualität und CPU-Latenz/RAM auf dem GPU-losen Dev-VPS.
  Über `JUPITER_WHISPER_MODEL` jederzeit hoch-/runterschaltbar, ohne Code-Änderung.
- **Groq nur opt-in:** Cloud-Transkription verlässt das System → bewusste Entscheidung, Default aus.
  Ist kein Key gesetzt, ist der Toggle deaktiviert und das System bleibt lokal.
- **Kein Web Speech API:** würde Audio an Google senden — verletzt die DSGVO-Linie des Projekts.
- **Transkript editierbar, kein Auto-Submit:** Whisper kann irren; der Nutzer korrigiert vor dem Absenden.
- **Audio transient:** Datenschutz by default — kein persistentes Audio, sofern nicht bewusst aktiviert.
- **Eine wiederverwendbare Button-Komponente:** beide Einsatzorte (Launcher, Decision Card) teilen Aufnahme-,
  Fehler- und Transkriptions-Logik — kein dupliziertes MediaRecorder-Handling.

### E) Abhängigkeiten (nur Namen + Zweck)
- **Backend (Python):** `faster-whisper` (lokale Whisper-Transkription, CTranslate2-Backend);
  optional `groq` SDK ODER schlicht `httpx` (bereits da) für den Groq-REST-Call.
- **Frontend:** keine neue Lib nötig — `MediaRecorder` ist Browser-nativ; Icons/Button via bestehendes
  shadcn/ui + lucide-react.
- **System:** `ffmpeg` auf dem VPS (faster-whisper dekodiert webm/opus darüber) — laut Setup bereits vorhanden.

### F) Edge-Case-Abdeckung (Architektur-Sicht)
- Kein Mikro / Permission verweigert → Button zeigt Fehlerzustand, Tippen bleibt immer möglich (Feld unverändert nutzbar).
- Whisper/Groq nicht erreichbar → klare deutsche Fehlermeldung; Aufnahme geht nie still verloren (Blob bleibt bis Erfolg/Abbruch).
- Lange Aufnahme → `max_audio_seconds`-Limit mit Hinweis; Aufnahme stoppt automatisch.
- Groq an ohne Key → 400 + Setup-Hinweis, bleibt auf self-hosted.
- Mehrsprachig → `whisper_language` konfigurierbar (Default „de", Autodetect optional).

## Implementation Notes — Frontend (/abc-frontend, 2026-06-24)
**Branch:** dev · **Stack:** Next.js 16 (App Router) — kein Flutter (Jupiter-Override).

Gebaut (Frontend, gegen den geplanten Backend-Vertrag — Endpunkte folgen in /abc-backend):
- **`components/cockpit/use-push-to-talk.ts`** — Hook: MediaRecorder-Aufnahme, Auto-Stop bei
  Längenlimit (Default 120 s), Mikrofon-Freigabe beim Unmount, Transkription via `transcribeAudio`.
  Zustände `idle | recording | transcribing`. Fehler (kein Mikro / Permission verweigert / Dienst
  nicht erreichbar / keine Sprache erkannt) → deutsche Meldung als Toast + `error`-State; Tippen
  bleibt immer möglich. **Bewusst keine Web Speech API.**
- **`components/cockpit/push-to-talk-button.tsx`** — wiederverwendbarer Icon-Button (shadcn/ui
  `Button` + lucide `Mic`/`Square`/`Loader2`). Sichtbare Zustände: Mic (idle) · pulsierender
  Stopp in `destructive` (recording) · Spinner (transcribing). Liefert Transkript per Callback,
  **kein Auto-Submit** — Aufrufer fügt den Text editierbar ins Feld ein.
- **Einbindung Smart-Launcher** (`new-session-dialog.tsx`): Mic-Button neben dem
  „Initial-Prompt"-Label; Transkript wird an den bestehenden Prompt angehängt (`appendDictation`).
- **Einbindung Decision Card** (`decision-card.tsx`): Mic-Button in der „Mit Kommentar zurück"-
  Eingabe; Transkript wird an den Kommentar angehängt.
- **Groq-Toggle** (`transcription-control.tsx`): neuer Tab „Sprache" im `settings-dialog.tsx`.
  Lokal (Default) ↔ Groq (Cloud); Groq-Button nur aktiv, wenn `groq_available` (Key gesetzt).
- **API-Client** (`lib/api.ts`): `transcribeAudio(blob, language?)` (multipart, POST `/transcription`),
  `getTranscriptionSettings()` / `setTranscriptionSettings(useGroq)` (GET/PATCH `/settings/transcription`).
- **Types** (`lib/types.ts`): `TranscriptionResult`, `TranscriptionSetting`.

Verifiziert: `npx tsc --noEmit` (nur vorbestehender Fehler in `md-tree.test.ts`, nicht aus diesem
Feature) und `npx eslint` über alle geänderten Dateien → sauber.

**Offen (Backend, /abc-backend):** `POST /transcription` (faster-whisper `small`, Default `de`,
optional Groq-Fallback), `GET/PATCH /settings/transcription`, Config-Felder
(`JUPITER_WHISPER_MODEL`/`_LANGUAGE`, `JUPITER_GROQ_API_KEY`, `JUPITER_MAX_AUDIO_SECONDS`).

## Implementation Notes — Backend (/abc-backend, 2026-06-24)
**Branch:** dev · kein DB/JWT (Jupiter-Override) · stateless, Audio nicht persistiert.

Gebaut:
- **`app/engine/transcription.py`** — `TranscriptionService`: wählt Engine anhand der Settings
  (`use_groq()` nur bei `use_groq_transcription` **und** vorhandenem Key, sonst lokal). Schreibt
  das Audio nur transient als Temp-Datei (`tempfile.mkstemp`), löscht sie im `finally`
  (Datenschutz). Lokal = **faster-whisper** (lazy geladen, `device="cpu"`, `compute_type="int8"`,
  im Threadpool via `anyio.to_thread`); fehlt die Lib → `TranscriptionError` (klare Meldung →
  503). Groq = `httpx`-Multipart-POST an `whisper-large-v3`. Beide Runner injizierbar (Tests).
- **`app/routes/transcription.py`** — `POST /transcription` (multipart `audio` + optional
  `language`). Leer → 400, > `max_audio_bytes` → 413, `TranscriptionError` → 503.
- **`app/routes/settings.py`** — `GET/PATCH /settings/transcription` (Quelle lokal/Groq;
  `use_groq=true` ohne Key → 400 mit Setup-Hinweis).
- **`app/schemas/transcription.py`** — `TranscriptionResult`, `TranscriptionSettingRead/Patch`.
- **`app/config.py`** — `whisper_model` (`small`), `whisper_language` (`de`), `groq_api_key`,
  `use_groq_transcription`, `max_audio_seconds`, `max_audio_bytes` (25 MB).
- **`app/main.py`** — Service in `app.state.transcription`, Router registriert.
- **`requirements.txt`** + **`.env.example`** — `faster-whisper>=1.0`; `JUPITER_WHISPER_MODEL/_LANGUAGE`,
  `JUPITER_GROQ_API_KEY`, `JUPITER_USE_GROQ_TRANSCRIPTION` dokumentiert.

Verifiziert: **`tests/test_proj20_transcription.py`** (11 Fälle: Engine-Wahl, leer/zu-groß,
503-Mapping, Settings + Groq-Guard, Temp-Datei-Löschung) grün; **volle Suite 590 passed**.
Zusätzlich realer End-to-End-Smoke auf dem VPS: faster-whisper lädt, dekodiert webm/opus (PyAV)
und inferiert ohne Crash (`tiny`-Modell gegen ffmpeg-Testaudio). faster-whisper in die
`Dashboard`-Env installiert.

**API-Vertrag (für /abc-qa):**
- `POST /transcription` · multipart: `audio` (File, webm/opus), `language` (optional) → `{ transcript, provider }`.
- `GET /settings/transcription` → `{ use_groq, groq_available, model, language }`.
- `PATCH /settings/transcription` · `{ use_groq: bool }` → wie GET (400 ohne Key).

## QA Test Results (/abc-qa, 2026-06-24)
**Branch:** dev · **Tester:** QA Engineer · **Verdikt: READY** (0 kritische/hohe Bugs).

### Acceptance Criteria (7/7 bestanden)
| # | Kriterium | Ergebnis | Nachweis |
|---|-----------|----------|----------|
| 1 | Push-to-Talk in Launcher (PROJ-9) + Card-Antworten (PROJ-4): aufnehmen→transkribieren→einfügen | ✅ PASS | `PushToTalkButton` an `new-session-dialog.tsx:278` + `decision-card.tsx:413` eingebunden; Hook `transcribeAudio` → Callback fügt ein |
| 2 | Standard self-hosted, kein API-Key, keine Kosten | ✅ PASS | Default `use_groq=false`; realer Smoke faster-whisper (webm/opus→Inferenz) ohne Key; `test_local_transcription_is_default` |
| 3 | Groq-Fallback konfigurierbar, default aus, bewusster Schalter | ✅ PASS | `test_groq_used_when_enabled_and_key_present`, `test_patch_groq_with_key_enables`; Probe: PATCH ohne Key → 400 |
| 4 | Web Speech API wird NICHT verwendet | ✅ PASS | grep: kein `SpeechRecognition`/`webkitSpeech` (nur Kommentar, der es ausschließt) |
| 5 | Transkript editierbar vor Absenden, kein Auto-Submit | ✅ PASS | Callbacks rufen ausschließlich `setPrompt`/`setComment` — kein `submit`/`decide`/`createSession` |
| 6 | Mikro verweigert/scheitert → klare Meldung, Tippen bleibt möglich | ✅ PASS | Hook mappt `NotAllowedError`/`NotFoundError`/kein-Support → deutscher Toast; Feld bleibt unberührt nutzbar |
| 7 | Alle Texte deutsch; Aufnahme-/Transkriptions-/Fehler-Zustände sichtbar | ✅ PASS | Button: Mic→pulsierender Stopp→Spinner; deutsche Toasts; „Sprache"-Tab deutsch |

### Edge Cases
- Kein Mikro / Permission verweigert → degradiert auf Tippen ✅
- Whisper-/Groq-Dienst-Fehler → `TranscriptionError` → **503** mit Klartext (nie 500, nie stiller Verlust) ✅ (`test_runner_error_maps_to_503`)
- Lange Aufnahme → Client-Auto-Stop (`max_audio_seconds`) + Server-Limit `max_audio_bytes` → **413** ✅ (`test_oversized_audio_rejected`)
- Groq aktiviert ohne Key → 400 + Setup-Hinweis, bleibt lokal ✅; Toggle ohne Key fällt zur Laufzeit auf lokal zurück (`test_groq_toggle_without_key_stays_local`)
- Leere Aufnahme → **400** ✅ (`test_empty_audio_rejected`)
- Mehrsprachigkeit → `language` durchgereicht, Default `de` ✅ (`test_language_override_is_passed_through`)

### Security / Red-Team (12/12)
- **Secret-Leak:** `JUPITER_GROQ_API_KEY` taucht weder in `GET/PATCH /settings/transcription` noch in Fehler-Responses auf ✅
- **Kein stiller Cloud-Versand:** `use_groq=true` ohne Key → 400 **und** zur Laufzeit Fallback auf lokal (Audio verlässt das System nie unbeabsichtigt) ✅
- **DSGVO/Datenschutz:** Audio nur transient als Temp-Datei, im `finally` gelöscht ✅ (`test_temp_audio_is_removed_after_transcription`); keine US-Browser-Speech-API ✅
- **Eingabe-Robustheit:** fehlendes `audio`-Feld → 422; JSON statt multipart → 422; bösartiger `language`-String wird nur durchgereicht (kein SQL/Shell-Pfad — Whisper-Param) ✅
- Kein JWT/RLS (Jupiter-MVP-Override, single-user) — bewusst, konsistent mit PROJ-1/2/11.

### Tests & Regression
- **`tests/test_proj20_transcription.py`** — 11 Fälle, alle grün.
- **Volle Backend-Suite: 590 passed** (keine Regression durch `click`-Upgrade/neue Imports).
- **Frontend:** `npx tsc --noEmit` keine neuen Fehler (nur vorbestehender `md-tree.test.ts`); `npx eslint` der PROJ-20-Dateien sauber.

### Offene Hinweise (nicht-blockierend)
- **Low:** Echte Spracherkennungs-Qualität (Deutsch, `small`) wurde nicht mit echter Sprache gemessen — nur die Decode-/Inferenz-Pipeline (Tonsignal → leeres Transkript, erwartet). Empfehlung: kurzer manueller Browser-Test mit echtem Diktat nach Deploy.
- **Low:** Erster lokaler Transkriptions-Aufruf lädt das `small`-Modell (~470 MB) → spürbare Erst-Latenz; danach im Prozess gecached. Optional Modell-Preload beim Start.

**Production-Ready: JA.**

## Deployment (/abc-deploy, 2026-06-24)
- **Production-URL:** https://jupiter.auxevo.tech
- **Deployed:** 2026-06-24 · **Version:** 0.8.0 · **Tag:** `v0.8.0`
- **Host:** Dev-VPS, host-native (systemd: backend/frontend/webhook + Caddy TLS), GitHub-Webhook Auto-Deploy auf `main` (kein Dokploy/Docker).
- **Promotion:** `dev → main` (zusammen mit PROJ-19 ausgeliefert).
- **Geliefert:** Push-to-Talk-Diktat (Smart-Launcher + Decision-Card-Kommentar), self-hosted faster-whisper (`small`, Default) + optionaler Groq-Cloud-Fallback, „Sprache"-Tab in den Einstellungen, `POST /transcription` + `GET/PATCH /settings/transcription`.
- **Host-Vorbereitung:** `faster-whisper` (+ ctranslate2/av) vor dem Deploy manuell in die `Dashboard`-Env installiert (`pip install -r backend/requirements.txt`); `ffmpeg` auf dem VPS vorhanden.
- **Manueller Smoke nach Deploy (Browser-only):** echtes Diktat im „Neue Session"-Feld + in einer Decision-Card-Antwort testen (Mikrofon-Permission, Transkript editierbar, kein Auto-Submit). Erst-Diktat lädt das `small`-Modell (~470 MB) → spürbare Erst-Latenz, danach gecached.
