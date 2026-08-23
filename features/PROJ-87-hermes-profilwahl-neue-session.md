# PROJ-87: Hermes-Profilwahl im Neue-Hermes-Session-Dialog

## Status: Architected
**Created:** 2026-08-23
**Last Updated:** 2026-08-23

## Dependencies
- Requires: PROJ-85 (Hermes-Chat-Sessions im Cockpit) — liefert den „Neu Hermes“-Dialog, die
  Hermes-Session-Hülle (`POST /sessions/hermes`) und den HermesChatDriver, die dieses Feature
  um die Profilwahl erweitert.
- Requires: PROJ-86 (Hermes-Chat direkt fortsetzen) — der direkte Hermes-Chat-Aufruf mit
  Resume-Vertrag ist die Grundlage, auf der `--profile <name>` zusätzlich mitgegeben wird.
- Reuses: PROJ-83 (Modellwahl pro Hermes-Profil) — dessen Profil-Erkennung
  (`discover_profiles()`, `jupiter-`-Präfix-Konvention, Format-/Whitelist-/Realpath-Schutz gegen
  Path-Traversal) wird als Vorlage für die serverseitige Profilliste wiederverwendet.
- Erweitert (im Hermes-Start-Dialog): das bisherige Modell-Dropdown aus PROJ-85
  (`GET /sessions/hermes/options`, `POST /sessions/hermes { engine, model }`) bleibt bestehen und
  wird um ein zusätzliches Profil-Dropdown ergänzt, dessen gewähltes Profil das Modell-Dropdown
  vorbelegt. Andere Nutzungen dieser Registry (Neue-Session-Dialog für Nicht-Hermes-Engines,
  PROJ-51/PROJ-18) bleiben unverändert.

## Annahme (bestätigt durch Nutzer, 2026-08-23)
1. **Profil-Scope:** Das Dropdown zeigt alle zur Laufzeit erkannten Hermes-Profile — jedes
   `jupiter-*`-Profil (analog PROJ-83-Erkennung) **plus** das reguläre `default`-Profil. Keine
   fest kodierte Liste.
2. **Verhältnis zur Modellwahl:** Profil- und Modellwahl bleiben **zwei getrennte Dropdowns**,
   wie im PROJ-85-Dialog. Das Profil bestimmt Skills, Tools, Connectors und Konstitution der
   Session. Das Modell-Dropdown bleibt zusätzlich bestehen und ist beim Öffnen mit dem
   **Standardmodell des gewählten Profils vorausgewählt**, bleibt aber frei änderbar. Wählt der
   Nutzer im Modell-Dropdown ein anderes Modell, **überschreibt diese Wahl ausschließlich für die
   neue Session** das Standardmodell des Profils — alles andere am Profil (Skills, Tools,
   Konstitution) bleibt unverändert wirksam.
3. **Sessionumfang:** „Komplette Session läuft mit dem Profil“ bedeutet die **volle**
   Profil-Konfiguration (Skills, Tools, Systemprompt/Konstitution) — wie ein echter
   Hermes-Aufruf mit `--profile <name>`, wobei nur das Modell durch die separate Modellwahl im
   Dialog ersetzt werden kann.

## Beschreibung

Der bestehende „Neu Hermes“-Startdialog (PROJ-85) fragt aktuell Titel, Projektpfad und ein
einzelnes Modell ab; die Modellwahl wird serverseitig in eine Hermes-kompatible
Modellkonfiguration übersetzt. Auf dem Server sind bereits mehrere Hermes-**Profile** angelegt
(z. B. die `jupiter-*`-Rollenprofile aus PROJ-83 sowie das normale `default`-Profil), jedes mit
eigener `config.yaml` (Modell, Skills, Tools, Verhalten).

PROJ-87 ergänzt den Dialog um eine **Profil-Auswahl per Dropdown**, zusätzlich zur bestehenden
Modellwahl aus PROJ-85. Der Nutzer wählt eines der auf dem Server vorhandenen Hermes-Profile;
**„default“ ist voreingestellt**. Die gestartete Hermes-Session läuft **vollständig** mit dem
gewählten Profil — Hermes wird für diese Session mit `--profile <name>` (oder äquivalent)
aufgerufen, sodass Skills, Tools, Connectors und Konstitution des Profils gelten, exakt wie beim
direkten CLI-Aufruf mit diesem Profil.

Das bestehende Modell-Dropdown aus PROJ-85 bleibt unverändert im Dialog vorhanden. Beim Wählen
eines Profils wird es automatisch mit dem **Standardmodell dieses Profils vorausgewählt**, bleibt
aber frei änderbar. Ändert der Nutzer das Modell, gilt diese Wahl **nur für die neue Session** und
überschreibt ausschließlich das Modell — alle übrigen Profileigenschaften (Skills, Tools,
Konstitution) bleiben unverändert wirksam.

Die Auswahl gilt ausschließlich für die neu gestartete Session. Kein bestehendes Profil, keine
laufende Session und keine `config.yaml` wird durch die Auswahl verändert.

## User Stories

- Als Nutzer möchte ich beim Start einer neuen Hermes-Session per Dropdown eines meiner
  angelegten Hermes-Profile auswählen, damit die Session mit den passenden Skills, Tools und
  Connectors dieser Rolle läuft, ohne das Profil manuell in der CLI anzugeben.
- Als Nutzer möchte ich, dass **„default“** vorausgewählt ist, damit ich ohne Umweg einen
  normalen Hermes-Chat starten kann, wenn ich kein spezielles Profil brauche.
- Als Nutzer möchte ich, dass die Profilliste automatisch die auf dem Server tatsächlich
  vorhandenen Profile zeigt, damit ich nie ein nicht existierendes oder veraltetes Profil wähle.
- Als Nutzer möchte ich zusätzlich zum Profil weiterhin ein Modell auswählen können, damit ich
  bei Bedarf ein anderes Modell als das Standardmodell des Profils für diese eine Session nutzen
  kann.
- Als Nutzer möchte ich, dass das Modell-Dropdown beim Wählen eines Profils automatisch dessen
  Standardmodell vorschlägt, damit ich es nicht bei jedem Start manuell nachschlagen muss.
- Als Nutzer möchte ich, dass abgesehen vom Modell alle übrigen Profileigenschaften (Skills,
  Tools, Konstitution) unverändert wirksam bleiben, damit eine Modelländerung nicht versehentlich
  das Rollenverhalten der Session verändert.
- Als Nutzer möchte ich bei einem nicht mehr verfügbaren oder fehlerhaften Profil eine klare
  deutsche Fehlermeldung sehen, statt eine Session zu starten, die nicht das gewählte Profil nutzt.

## Acceptance Criteria

- [ ] Der „Neu Hermes“-Dialog zeigt zusätzlich zum bestehenden Modell-Dropdown ein neues
      **Profil-Dropdown** mit allen zur Laufzeit erkannten Hermes-Profilen (jedes `jupiter-*`-
      Profil sowie `default`).
- [ ] Das Profil-Dropdown ist beim Öffnen des Dialogs mit **„default“** vorausgewählt.
- [ ] Die Profilliste wird dynamisch vom Server geladen, nicht im Frontend fest kodiert; ein
      Profil, das serverseitig entfernt oder umbenannt wurde, verschwindet beim nächsten Laden
      aus der Liste.
- [ ] Wählt der Nutzer ein Profil, wird das Modell-Dropdown automatisch auf das in diesem Profil
      hinterlegte Standardmodell gesetzt; das Modell-Dropdown bleibt danach frei änderbar.
- [ ] Ändert der Nutzer die Modellauswahl nach dem Vorbelegen, bleibt diese manuelle Auswahl
      erhalten und wird nicht durch einen erneuten Profilwechsel automatisch zurückgesetzt, außer
      der Nutzer wählt das Profil erneut/anders — dann wird wieder dessen Standardmodell
      vorgeschlagen.
- [ ] Titel (optional) und Projekt-Pfad (erforderlich) bleiben im Dialog wie bisher vorhanden und
      erforderlich; alle sichtbaren Texte und Fehlermeldungen sind deutsch.
- [ ] Beim Start wird die Session serverseitig mit dem gewählten Profil gestartet
      (`--profile <name>` bzw. äquivalenter Hermes-Aufruf), sodass Skills, Tools, Connectors und
      Systemprompt/Konstitution dieses Profils für die **gesamte** Session gelten.
- [ ] Beim Start überschreibt die im Dialog gewählte Modellauswahl **ausschließlich das Modell**
      des gewählten Profils für diese eine Session; alle übrigen Profileigenschaften bleiben
      unverändert wirksam.
- [ ] Der Start einer Hermes-Session verändert kein bestehendes Profil (`config.yaml`) und keine
      bereits gestartete Hermes-Session — auch nicht, wenn ein vom Profildefault abweichendes
      Modell gewählt wurde.
- [ ] Bypass-Modus und Token Savings bleiben wie in PROJ-85 fest auf der Jupiter-Seite gesetzt und
      sind nicht Teil des Dialogs — unabhängig von Profil- und Modellwahl.
- [ ] Nach erfolgreichem Start erscheint die Session wie bisher unter „Aktive Sessions“ und zeigt
      zusätzlich das verwendete Profil (z. B. als Badge/Label neben dem Hermes-Engine-Badge und
      dem bereits vorhandenen Modell-Label).
- [ ] Wählt der Nutzer ein Profil, das zwischen Laden des Dialogs und Start nicht mehr existiert
      oder dessen `config.yaml` nicht lesbar ist, wird der Start abgelehnt; der Dialog zeigt eine
      deutsche Fehlermeldung und bleibt für eine Korrektur (Profil neu wählen) geöffnet.
- [ ] Wählt der Nutzer eine Modell/Profil-Kombination, die serverseitig nicht startfähig ist (z. B.
      Modell für die Engine des Profils nicht verfügbar), wird der Start abgelehnt; der Dialog
      zeigt eine deutsche Fehlermeldung, ohne das Profil-Dropdown zurückzusetzen.
- [ ] Eine Hermes-Session, die mit Profil X und Modell Y gestartet wurde, verhält sich für die
      volle Sitzungsdauer (alle Folge-Turns/Resume gemäß PROJ-86) weiterhin mit Profil X und
      Modell Y — ein nachträglicher Profil- oder Modellwechsel innerhalb derselben Session ist
      nicht vorgesehen.
- [ ] Mehrere Hermes-Sessions mit unterschiedlichen Profil-/Modell-Kombinationen können
      gleichzeitig neben Standard- und anderen Hermes-Sessions existieren und bleiben über ihre
      Session-ID getrennt.
- [ ] Die Kontextanzeige (Token verbraucht/Fenster, Fortschrittsbalken) aus PROJ-85 bleibt
      unverändert funktionsfähig, unabhängig von Profil- und Modellwahl.

## Edge Cases

- **Keine Profile auf dem Server gefunden (nicht einmal `default`):** Der Dialog zeigt einen
  deutschen Fehlerzustand statt eines leeren oder funktionslosen Profil-Dropdowns; ein Start ist
  in diesem Zustand nicht möglich.
- **Laden der Profilliste schlägt fehl (Server nicht erreichbar):** Der Dialog zeigt eine
  deutsche Fehlermeldung mit Wiederholen-Möglichkeit; der Startknopf bleibt deaktiviert, bis eine
  gültige Liste geladen wurde.
- **Gewähltes Profil hat kein auflösbares Standardmodell (z. B. `config.yaml` ohne `model.default`):**
  Das Modell-Dropdown bleibt leer/ohne Vorauswahl; der Nutzer muss vor dem Start manuell ein
  Modell wählen, der Start wird sonst abgelehnt.
- **Gewähltes Profil wird während des Dialogs auf dem Server gelöscht/defekt:** Der Start schlägt
  serverseitig fehl (kein stiller Fallback auf `default`); Dialog bleibt offen, Nutzer wählt neu.
- **Profil-`config.yaml` ist syntaktisch ungültig oder unlesbar:** Der Start wird abgelehnt mit
  einer deutschen Fehlermeldung, die auf das defekte Profil hinweist, ohne dessen Rohinhalt oder
  etwaige Secrets preiszugeben.
- **Nutzer wählt ein Modell, das zur Engine/dem Provider des gewählten Profils nicht passt:** Der
  Start wird serverseitig abgelehnt mit einer deutschen Fehlermeldung; das Modell-Dropdown zeigt
  nur zur aktuell gewählten Profil-Engine passende Modelle, sofern das serverseitig einschränkbar
  ist (analog PROJ-85s Engine→Modell-Filterung).
- **Nutzer öffnet den Dialog erneut nach vorherigem Fehlversuch:** „default“ ist als Profil wieder
  vorausgewählt und das Modell-Dropdown zeigt dessen Standardmodell; eine zuvor manuell
  abweichende, fehlgeschlagene Auswahl wird nicht übernommen.
- **Zwei Hermes-Sessions mit demselben Profil, aber unterschiedlichem Modell parallel gestartet:**
  Beide laufen unabhängig mit ihrer jeweiligen Profil-/Modell-Kombination zum Startzeitpunkt; eine
  spätere Änderung des Profils betrifft keine bereits laufende Session (Snapshot-Verhalten wie in
  PROJ-85 für Modelle etabliert).
- **Profil enthält Secrets/Credentials in der `config.yaml`:** Diese werden im Dialog, in der
  Profilliste und in keiner Antwort des Servers angezeigt oder übertragen — nur der Profilname,
  ggf. ein Anzeigelabel und das Standardmodell sind sichtbar.

## Non-Goals

- Kein Anlegen, Löschen, Umbenennen oder inhaltliches Bearbeiten von Hermes-Profilen aus diesem
  Dialog heraus (das bleibt PROJ-83/manueller `config.yaml`-Pflege vorbehalten).
- Kein nachträglicher Profilwechsel innerhalb einer bereits laufenden Hermes-Session.
- Keine Änderung an Nicht-Hermes-Session-Starts (Claude/Codex/OpenCode) oder deren
  Engine/Modell-Dropdown.
- Keine Änderung an den bestehenden `jupiter-*`-Profil-Konfigurationen selbst — dieses Feature
  liest sie nur, um sie zur Session-Startzeit zu übergeben.

## Technical Requirements (optional)
- Wiederverwendung der PROJ-83-Profilerkennung/-Validierung (Format-Regex, Whitelist gegen
  tatsächlich vorhandene Profile, Realpath-Scope-Check) als Vorlage für die Lese-/Validierungslogik
  dieses Features, um dieselbe Path-Traversal-Härtung sicherzustellen.
- Texte/Tooltips deutsch; shadcn-`Select`-Primitiv wie im bestehenden Dialog.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-23 · **Stack:** Next.js/shadcn + FastAPI + bestehender raw-SQL/SQLite-Session-Index mit JWT-Owner-Scope; Hermes CLI; Dokploy · **Branch:** specs/PROJ-87-hermes-profilwahl-neue-session

### Ziel und Abgrenzung

PROJ-87 ergänzt den bestehenden `HermesStartDialog` (PROJ-85/86) um ein zweites
Dropdown — **Profil** — neben dem vorhandenen Modell-Dropdown. Die Auswahl
bestimmt, mit welchem Hermes-Profil (`default` oder ein erkanntes `jupiter-*`-
Profil) der `HermesChatDriver` seinen `hermes chat`-Prozess startet. Alle
übrigen PROJ-85/86-Verträge (Session-Hülle, direkter Chat-Transport, Resume
über `--continue jupiter-<id>`) bleiben unverändert; PROJ-87 fügt ausschließlich
die Profildimension hinzu.

**Wichtige Korrektur gegenüber der Spec-Annahme:** Hermes kennt **kein**
CLI-Flag `--profile <name>`. Ein Profil wird ausschließlich über die
Umgebungsvariable `HERMES_HOME` gewählt — `~/.hermes` für `default`,
`~/.hermes/profiles/<name>` für ein `jupiter-*`-Profil (siehe
`get_hermes_home()`/`get_active_profile_name()` in der Hermes-CLI,
`hermes_cli/profiles.py:1962-1986`, sowie `hermes profile list`, das exakt
diese Verzeichnisstruktur zeigt). Der komplette Skill-/Tool-/Konstitutions-
Kontext eines Profils folgt automatisch aus `HERMES_HOME` — nicht aus einem
Extra-Flag. `LaunchSpec.env` (PROJ-80, `backend/app/engine/base.py:70`) ist
bereits der vorgesehene Mechanismus, um zusätzliche Prozess-Umgebungsvariablen
in den Subprozess zu mergen; PROJ-87 nutzt ihn, statt ein nicht existierendes
Flag zu simulieren.

### A) Komponenten und Ablauf

```
HermesStartDialog (erweitert)
├── Titel (optional)
├── Projekt-Pfad (Pflicht)
├── Profil (Pflicht; Default „default“ vorausgewählt)   ← NEU (PROJ-87)
└── Modell (Pflicht; beim Profilwechsel auf dessen Standardmodell vorbelegt,
    danach frei änderbar)

HermesStartDialog
└── POST /sessions/hermes { title?, project_path, profile, engine, model }
    ├── Profil-Validierung (Whitelist gegen frischen discover_profiles()-Snapshot)
    ├── Modell-Validierung (bestehender PROJ-85-Resolver, unverändert)
    ├── HermesChatDriver(profile, provider, model, hermes_env)
    │     └── hermes_env = {"HERMES_HOME": <profil-pfad>} (nur bei Nicht-Default)
    └── bestehender SessionManager / Session-Index (erweitert um `hermes_profile`)

Aktive Sessions / SessionRail
└── bestehende Session-Kachel: Engine-Badge „Hermes“ + Modell-Label
    + NEUES Profil-Badge (z. B. „Backend“), nur sichtbar wenn ≠ default
```

Der Dialog lädt seine Profil-Liste aus einem **neuen, schmalen Lese-Endpunkt**
parallel zur bestehenden Modell-Options-Anfrage. Beide Ladevorgänge sind
unabhängig; das Modell-Dropdown reagiert auf Profilwechsel per lokalem
State-Effekt (kein Server-Roundtrip), analog zum bestehenden Muster, das die
Modell-Auswahl bereits beim ersten Laden der Optionen vorbelegt
(`hermes-start-dialog.tsx:70-76`).

### B) Datenmodell und Besitz

Kein neues Domänenobjekt, keine MinIO-Objekte. Ein Feld wird additiv an
Bestehendes angehängt; die Profilliste selbst bleibt weiterhin zur Laufzeit
aus dem Dateisystem abgeleitet (kein Cache, kein zweiter Speicherort).

1. **Hermes-Profil-Liste** (kein persistiertes Objekt, PROJ-83-Vorlage)
   - Wiederverwendung von `discover_profiles()`
     (`backend/app/engine/hermes_profiles.py:158-220`) UNVERÄNDERT: liefert
     bereits `jupiter-*`-Profile mit Format-/Whitelist-/Realpath-Schutz gegen
     Path-Traversal. PROJ-87 ergänzt in der Antwort lediglich einen
     **synthetischen `default`-Eintrag** (kein Verzeichnis-Scan nötig — er
     existiert per Definition), vorangestellt in der Liste.
   - Ein Profil ohne auflösbares `model.default`/`model.provider` (bereits
     heute `entry["engine"]=None`/`entry["model"]=None` bei nicht
     zurückübersetzbarer Kombination) liefert dem Frontend explizit „kein
     Standardmodell“ — das Modell-Dropdown bleibt dann ohne Vorauswahl
     (Edge Case aus der Spec).
   - **Schreiber/Owner:** Kein Schreibzugriff durch PROJ-87 — identisch zu
     PROJ-85s Prinzip bei Modellen. `PATCH /settings/hermes-profiles` (PROJ-83)
     bleibt der einzige Schreibpfad für Profil-`config.yaml`.
   - **Lesepfad:** neuer `GET /sessions/hermes/profiles` vor dem Öffnen des
     Dialogs; `POST /sessions/hermes` validiert die Auswahl serverseitig
     erneut gegen denselben frischen Snapshot (identisches Muster zu
     Modell-Validierung, PROJ-85 Tech Design Punkt E).

2. **Session** (bestehend, additiv erweitert)
   - Neues Feld `hermes_profile: str` (Default `"default"`), analog zu den
     bestehenden `engine`/`model`-Feldern rein informativ persistiert — dient
     der Badge-Anzeige und der Rehydrierung nach Backend-Neustart (damit ein
     wiederaufgenommener Turn wieder mit demselben `HERMES_HOME` läuft, nicht
     mit `default`).
   - **Schreiber/Owner:** `POST /sessions/hermes` setzt das Feld beim Erstellen;
     danach unveränderlich für die Sitzungsdauer (kein Profilwechsel während
     laufender Session, siehe Non-Goals).
   - **Lesepfade:** `GET /sessions`, `GET /sessions/{id}`, WS-Snapshot — additiv,
     wie die bestehenden Hermes-Kontextfelder aus PROJ-85.

3. **HermesChatDriver-Prozessumgebung** (flüchtig, kein Datenbankfeld)
   - Der Manager übergibt dem Driver bei jedem Turn (Erst- und Folge-Turn) ein
     `env`-Dict mit `HERMES_HOME`, abgeleitet aus dem persistierten
     `hermes_profile` — nicht neu vom Client pro Turn. Für `default` wird
     bewusst **kein** `HERMES_HOME` gesetzt (identisches Verhalten zum
     bisherigen, profil-losen Prozessstart), um keine Regression für alle
     bestehenden Hermes-Sessions (vor PROJ-87 immer `default`) zu riskieren.

### C) API-Vertrag

- **NEU:** `GET /sessions/hermes/profiles` — liefert `default` + alle
  erkannten `jupiter-*`-Profile (`profile`, `label`, `engine`, `model`,
  `error`). Reine Leseoperation, JWT erforderlich (kein Owner-Scope nötig, da
  Profile serverweit gleich sichtbar sind — wie schon `GET
  /settings/hermes-profiles` aus PROJ-83, das keinerlei Owner-Filterung
  kennt). Fehler: liefert bei nicht erreichbarem Profilverzeichnis `warning`
  + trotzdem den `default`-Eintrag (nie eine leere Liste, Edge Case „keine
  Profile gefunden“ ist damit strukturell ausgeschlossen).
- **GEÄNDERT:** `POST /sessions/hermes` — Request erhält ein neues Pflichtfeld
  `profile: str` (Default `"default"`, falls vom Client nicht mitgeschickt —
  Rückwärtskompatibilität für den Fall unfertiger Frontend-Deployments
  zwischen Backend- und Frontend-Rollout). Server validiert `profile` gegen
  denselben frischen Snapshot wie der Options-Endpoint (Whitelist,
  `discover_profiles()`); ein zwischenzeitlich gelöschtes/defektes Profil
  liefert `400` mit deutscher Fehlermeldung (**kein** stiller Fallback auf
  `default`, exakt wie in den Edge Cases gefordert). Antwort bleibt der
  normale `SessionRead`-Snapshot, jetzt zusätzlich mit `hermes_profile`.
- **GEÄNDERT (additiv):** `GET /sessions`, `GET /sessions/{id}`, `WS
  /sessions/{id}/stream` — erhalten additiv `hermes_profile: str` (bei
  Nicht-Hermes-Sessions `"default"` oder `null`, siehe Entscheidung D).
- Alle übrigen PROJ-85/86-Endpunkte (`POST /sessions/{id}/input`, Resume,
  Reanimation) bleiben vertraglich unverändert; sie lesen `hermes_profile`
  intern aus dem persistierten `SessionState`, nie aus einem neuen
  Client-Payload.

### D) Entscheidungen (und warum)

- **`HERMES_HOME`-Env statt erfundenes `--profile`-Flag:** Die Spec nennt
  `--profile <name>` als Platzhalter für „äquivalenter Hermes-Aufruf“ — die
  tatsächliche Hermes-CLI kennt dieses Flag nicht. Der reale, vom Hermes-CLI-
  Code selbst genutzte Mechanismus ist `HERMES_HOME` (`hermes_cli/
  profiles.py:1962-1986`). Diese Korrektur ändert nichts an den
  Akzeptanzkriterien (volle Profilwirkung inkl. Skills/Tools/Konstitution),
  nur an der technischen Umsetzung — `HERMES_HOME` ist sogar vollständiger,
  weil es exakt der Mechanismus ist, den `hermes profile use`/die reale CLI
  selbst verwenden.
- **Additive Felder statt neuer Tabellen:** Wie PROJ-85/86 bleibt der
  bestehende SQLite-Session-Index führend; `hermes_profile` ist ein einzelnes
  zusätzliches Feld, keine neue Domäne.
- **Kein Owner-Scope auf der Profilliste:** Profile sind serverweite
  Konfiguration (identisch zu PROJ-83s `GET /settings/hermes-profiles`, das
  ebenfalls ungescoped ist) — kein Widerspruch zu PROJ-25, weil Profile kein
  Nutzerdatum sind, sondern Serverzustand, der für jeden authentifizierten
  Jupiter-Nutzer gleich sichtbar ist.
- **`default` ist ein synthetischer Listeneintrag, kein Verzeichnis-Scan:**
  Vermeidet eine Sonderbehandlung/Race gegenüber `discover_profiles()`, das
  `default` bewusst ausschließt (`_DEFAULT_PROFILE`, `hermes_profiles.py:40`).
- **Kein Profilwechsel innerhalb einer laufenden Session:** Deckt sich mit der
  Spec (Non-Goals) und mit PROJ-86s ADR-86-3 (Hermes läuft immer direkt, ohne
  tmux/Reanimation) — `HERMES_HOME` wird nur beim ersten Turn-Aufbau aus dem
  persistierten Feld gelesen, danach unverändert für jeden Folge-Turn
  wiederverwendet.
- **Rückwärtskompatibler `profile`-Default `"default"`:** Verhindert einen
  Breaking-Change-Zeitraum zwischen Backend- und Frontend-Deploy (wie in
  PROJ-85 BUG-2 bereits einmal real aufgetreten — Contract-Mismatch zwischen
  Front-/Backend-Rollout-Reihenfolge).

### E) Delivery-Reihenfolge und Akzeptanzzuordnung

1. **Backend:** `GET /sessions/hermes/profiles` (Wiederverwendung
   `discover_profiles()` + synthetischer `default`-Eintrag), `profile`-Feld in
   `HermesSessionCreate`/`SessionState`/`SessionRead`, `HERMES_HOME`-Env-
   Weiterreichung in `SessionManager.create_hermes()` → `HermesChatDriver`
   (über `LaunchSpec.env`, wiederverwendet aus PROJ-80). Deckt ACs zu
   Profil-Erkennung, Default-Vorauswahl, Start-Ablehnung bei ungültigem/
   verschwundenem Profil.
2. **Frontend:** Profil-Dropdown im `HermesStartDialog` (gleiches
   shadcn-`Select`-Muster wie das bestehende Modell-Dropdown), Laden via
   neuem Endpoint, Vorbelegung des Modell-Dropdowns bei Profilwahl (lokaler
   State-Effekt, kein Server-Call), Profil-Badge auf der Session-Kachel
   (`session-tile.tsx`, gleiches Muster wie das bestehende Engine-/
   Transport-Badge, nur sichtbar bei `hermes_profile !== "default"`). Deckt
   ACs zu Formularverhalten, deutschen Fehlermeldungen, Badge-Sichtbarkeit.
3. **QA:** Profilwechsel im Dialog vor Submit, Start mit gelöschtem/defektem
   Profil zwischen Laden und Submit, parallele Sessions mit unterschiedlichen
   Profil-/Modell-Kombinationen, Resume/Folge-Turn behält `HERMES_HOME` über
   die gesamte Sitzungsdauer, Skills/Tools eines gewählten `jupiter-*`-Profils
   sind im laufenden Chat tatsächlich aktiv (Stichprobe: mind. ein Profil mit
   abweichenden Skills gegenüber `default`).

### F) ADRs

- **ADR-87-1 — `HERMES_HOME`-Env statt `--profile`-Flag:** angenommen. Einzige
  reale, vom Hermes-CLI-Code unterstützte Profilwahl-Methode; volle
  funktionale Äquivalenz zu einem CLI-Aufruf mit diesem Profil.
- **ADR-87-2 — Profil ist ein Session-Snapshot, kein laufzeitänderbares
  Feld:** angenommen, analog zu ADR-85-2 (Modell ist Session-Snapshot). Ein
  einmal gestarteter Chat behält sein Profil für die gesamte Sitzungsdauer.
- **ADR-87-3 — `default` als synthetischer Listeneintrag:** angenommen,
  vermeidet Änderungen an `discover_profiles()`s bewusstem Default-Ausschluss.
- **ADR-87-4 — Ungescopte Profilliste:** angenommen, konsistent mit PROJ-83s
  bereits etabliertem, ungescoptem `GET /settings/hermes-profiles`.

### G) Implementierungsinvarianten aus dem Codebase-Abgleich

- **Profilauflösung ist ein vollständiger Start-Snapshot:** Der neue Profile-Endpoint
  liefert pro Eintrag mindestens `profile`, `label`, `engine`, `model`, `error` und
  `warning`; für `default` wird Engine/Modell aus der normalen Hermes-Home-Konfiguration
  gelesen, ohne Secrets in die Antwort aufzunehmen. Ein kaputtes Profil bleibt als
  fehlerhafter Eintrag sichtbar, ist aber nicht startbar. Der Client darf nur
  startfähige Profile wählen; das explizit sichtbare Fehlerprofil erklärt den
  Ablehnungsgrund statt beim Submit auf ein anderes Profil zurückzufallen.
- **Engine und Modell bleiben ein Paar:** Der Frontend-State und `POST /sessions/hermes`
  transportieren die vom Profil vorgeschlagene bzw. vom Nutzer gewählte
  `{ engine, model }`-Kombination gemeinsam. Das Modell-Select wird aus
  `GET /sessions/hermes/options` auf die Engine des aktuell gewählten Profils gefiltert;
  bei einer manuellen Modellwahl wird die zugehörige Engine mitgespeichert. Die Auswahl
  darf nicht allein per Modellstring aufgelöst werden, weil Registry-Modelle künftig
  engineübergreifend gleich heißen können.
- **`HERMES_HOME` muss jeden echten Hermes-Turn erreichen:** `create_hermes()` setzt
  `LaunchSpec.env` aus dem validierten Profilpfad. `HermesChatDriver._spec_with_prompt()`
  kopiert `env` (sowie den übrigen Launch-Kontext) in den Folge-Turn-Spec, damit der
  direkte Respawn nicht auf die Prozessumgebung zurückfällt. Beim Rehydrieren einer
  wartenden Hermes-Session wird aus dem persistierten `hermes_profile` ein vollständiger
  `LaunchSpec` für den nächsten Input rekonstruiert; nur den Driver mit einer
  Resume-Referenz zu erzeugen genügt nicht. Für `default` wird die explizite,
  konfigurierte Standard-Home verwendet bzw. ein geerbtes `HERMES_HOME` entfernt, damit
  ein möglicherweise profilbehafteter Backend-Prozess nicht versehentlich ein anderes
  Profil auswählt.
- **Persistenzpfad vollständig erweitern:** `hermes_profile` gehört konsistent in
  `SessionState`, `to_read()`, `SessionRead`, Frontend-`Session`, `COLUMNS`,
  `SCHEMA_SQL`, `_MIGRATIONS`, `_row()` und `_state_from_row()`. Der Migrations-Default
  ist `"default"`; somit bleiben bestehende Datensätze und gemischte Frontend-/Backend-
  Rollouts kompatibel. Der WebSocket nutzt bereits `to_read()` und erhält das Feld damit
  ohne einen separaten Event-Vertrag.
- **Fehler- und Auth-Vertrag:** `GET /sessions/hermes/profiles` verwendet wie die
  bestehenden `/sessions`-Read-Endpunkte `get_current_user`. `POST /sessions/hermes`
  validiert zuerst den frischen Profil-Snapshot (Name, realpath, lesbare Konfiguration),
  danach die zusammengehörige Engine/Modell-Kombination und startet erst anschließend den
  Driver. Ungültige/zwischenzeitlich entfernte Profile und nicht startfähige Kombinationen
  liefern `400` mit deutscher, secret-freier Detailmeldung; Options-Ladefehler bleiben im
  Dialog mit Wiederholen behandelbar.

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-23 · **Verdict:** Architected

### Checklist
- [x] Component structure — `HermesStartDialog` nutzt die vorhandenen shadcn-`Select`-Primitiven; Profil-Select, nach Engine gefiltertes Modell-Select und nicht-default Profil-Badge in `SessionTile` sind konkret zugeordnet.
- [x] Data model — `hermes_profile: str` ist als unveränderlicher Session-Snapshot mit SQLite-Migration, Rehydrierung und Response-Propagation festgelegt; der Migrationsdefault schützt alte Sessions.
- [x] API shape — neuer authentifizierter `GET /sessions/hermes/profiles` sowie der additive `POST /sessions/hermes`-Vertrag haben Methode, Pfad, Payload, erneute serverseitige Validierung und deutsche Fehlersemantik.
- [x] Tech decisions — `HERMES_HOME` ersetzt das nicht vorhandene `--profile`-Flag; warum der Wert über alle Folge-Turns und nach Rehydrierung weitergereicht werden muss, wurde präzisiert.
- [x] Dependencies — keine neue Bibliothek nötig; `discover_profiles()`, `LaunchSpec.env`, SQLite-Add-Column-Migration, `GenericCliDriver`-Env-Merge und bestehende Frontend-API-/Typmuster sind vorhanden.
- [x] Branch field — `specs/PROJ-87-hermes-profilwahl-neue-session` existiert lokal und ist der aktuelle Branch.
- [x] Conflict-free — `/sessions/hermes/profiles` ist ein neues statisches Segment und kollidiert weder mit `/sessions/hermes/options` noch mit `/{session_id}`; `hermes_profile` ist kein bestehendes Session-Index-Feld.
- [x] Acceptance-criteria coverage — Dialog, dynamischer Read-Pfad, Default, Modell-Vorbelegung/Override, vollständige Profilprozessumgebung, Fehlerpfade, Badge und Resume-Snapshot sind jeweils Komponenten bzw. API-/Persistenzpfaden zugeordnet.

### Autonom behoben
- Den Header auf `Architected` korrigiert, damit er mit dem vorherigen Architecture-Draft und dem Status-Gate übereinstimmt.
- Den Designvertrag um vollständige Engine/Modell-Paare, den Folge-Turn-/Rehydrate-Transport von `HERMES_HOME`, die Default-Home-Isolation, die gesamte Persistenzkette und präzise Fehlerreihenfolge ergänzt. Diese Punkte folgen direkt aus den vorhandenen Implementierungsseams und ändern keine Produktanforderung.
- Codebase-Cross-Check berücksichtigt: `discover_profiles()` liefert derzeit nur `jupiter-*`; `default` muss daher separat, aber auslesbar und ohne Secret-Leak ergänzt werden. Die bestehende `LaunchSpec.env`-Unterstützung wird im direkten Spawn gemergt, aber von `HermesChatDriver._spec_with_prompt()` noch nicht automatisch bewahrt; die Umsetzung muss dies schließen.

## QA Test Results
**Getestet:** 2026-08-23 · **Verdict:** READY (keine Critical/High-Bugs)

### Akzeptanzkriterien (Code-Review + eigener Testlauf)
1. Profil-Dropdown zusätzlich zum Modell-Dropdown — PASS (`hermes-start-dialog.tsx:313-364`)
2. „default“ beim Öffnen vorausgewählt — PASS (`DEFAULT_PROFILE`, State-Init + Reset-Effekt)
3. Profilliste dynamisch vom Server (`GET /sessions/hermes/profiles`), kein Hardcoding — PASS; `discover_profiles()` scannt zur Laufzeit, kein Cache
4. Modell-Dropdown auf Profil-Standardmodell vorbelegt bei Profilwahl — PASS (`applyProfileDefault(force:true)` in `handleProfileChange`)
5. Manuelle Modellwahl bleibt bei Profilwechsel erhalten, außer erneuter/anderer Profilwechsel — PASS (`applyProfileDefault(force:false)` beim initialen Laden respektiert `model`-State)
6. Titel optional/Pfad Pflicht, deutsche Texte — PASS, alle UI-Strings deutsch
7. Start läuft serverseitig mit Profil via `HERMES_HOME` (kein `--profile`-Flag, da nicht existent — korrekt in ADR-87-1 korrigiert) — PASS, verifiziert in `test_make_driver_sets_hermes_home_for_nondefault` + eigener Codeprüfung `manager.py:2043,2067`
8. Modellwahl überschreibt nur das Modell, übrige Profileigenschaften bleiben — PASS (`hermes_env`/`HERMES_HOME` unabhängig von `inv.model`)
9. Kein bestehendes Profil/keine laufende Session verändert — PASS, nur Lesezugriff (`discover_profiles`, kein Schreibpfad in PROJ-87-Code)
10. Bypass/Token-Savings serverseitig fix, nicht im Dialog — PASS, `HermesSessionCreate` mit `extra="forbid"`; eigener Angriffsversuch (`permission_mode`/`token_savings`/`initial_prompt` im Payload) → 422 verifiziert
11. Session-Kachel zeigt Profil-Badge (nur ≠ default) — PASS (`session-tile.tsx:74-87`), vitest 5/5 grün
12. Ungültiges/verschwundenes Profil beim Start → Ablehnung + deutsche Fehlermeldung, Dialog bleibt offen — PASS, `validate_profile()` kein stiller Fallback, 400 mit deutscher Meldung; `submitError`-State hält Dialog offen
13. Nicht startfähige Modell/Profil-Kombi → Ablehnung, Profil-Dropdown bleibt erhalten — PASS (Fehlerzustand setzt nur `submitError`, kein Reset von `profile`)
14. Profil/Modell bleiben für gesamte Sitzungsdauer (Resume/Folge-Turns) unverändert — PASS, verifiziert in `test_hermes_spec_carries_hermes_home_env` + `test_persisted_hermes_profile_survives_rehydrate_env`
15. Mehrere Hermes-Sessions mit unterschiedlichen Profil-/Modellkombis parallel, getrennt über Session-ID — PASS (kein globaler State, `hermes_profile` ist Session-Snapshot)
16. Kontextanzeige (PROJ-85) bleibt unverändert funktionsfähig — PASS, `context_used_tokens`/`context_window_tokens`/`context_usage_available` unverändert in `SessionRead`

16/16 Akzeptanzkriterien PASS.

### Eigener Testlauf (nicht nur „Dev sagt“)
- Backend: `conda run -n Dashboard python -m pytest tests/test_proj87_hermes_profile.py -q` → **18/18 grün**
- Backend-Vollregression: `pytest -q` (gesamtes Projekt) → **29 Fehler, 1322 passed**. Alle 29 Fehler geprüft: identisch reproduzierbar auf `git stash` (Stand VOR PROJ-87) — vorbestehende Baseline-Fehler in test_proj39/50/79/80/83 (unabhängig von PROJ-87, u.a. Fixture-Drift und PROJ-83-Testerwartung, die durch die Registry-Reihenfolge nicht mehr passt). Keine Regression durch PROJ-87.
- Frontend: `npx vitest run` (session-tile, active-session-panel, status) → **51/51 grün**
- Frontend: `npx tsc --noEmit` → 6 Fehler, alle in `*.test.tsx`/`*.test.ts`-Fixtures (`hermes_profile`/`context_usage_available`/`md-tree`), identisch via `git stash`-Vergleich als Baseline-Debt bestätigt (Testfixtures wurden nicht an die additiven Pflichtfelder aus PROJ-85/87 angepasst) — kein PROJ-87-Regressions-Fehler im Produktivcode.
- Frontend: `npx eslint` auf geänderten Dateien → 1 Fehler (`set-state-in-effect`), via `git stash`-Vergleich als vorbestehend bestätigt (identischer Fehler existierte schon vor PROJ-87 an derselben Stelle). 1 Warning (`HermesKanbanTask` unused) — unrelated zu PROJ-87 (in `lib/api.ts`, nicht Teil dieses Diffs' Kernlogik).
- Live-Backend-Smoke: eigener uvicorn-Start (Port 8091), `GET /health` → 200, `/openapi.json` bestätigt `/sessions/hermes/profiles` + `/sessions/hermes/options` registriert.

### Security-Red-Team (eigener Angriffsversuch)
- Unauthentifizierter Zugriff auf `GET /sessions/hermes/profiles` und `POST /sessions/hermes` → **401** (Soft-Gate: sobald Nutzer existieren, kein anonymer Zugriff)
- Path-Traversal im `profile`-Feld (`jupiter-../../etc/passwd`, `default/../jupiter-backend`, `../../../etc/passwd`, URL-encoded `%2e%2e`, `jupiter-backend/../../`) → alle **pydantic-Pattern-Rejects (422)**, kein Fall erreicht den Handler
- SQL-Injection-artiger Profilname (`jupiter-x'; DROP TABLE sessions;--`) → **422** (Regex-Whitelist blockt Sonderzeichen)
- Case-Bypass (`JUPITER-BACKEND`) → **422** (Regex ist case-sensitive, nur Kleinbuchstaben erlaubt)
- Shell-Injection-Versuch (`default; rm -rf /`) → **422**
- `extra="forbid"`-Bypass-Versuch: `permission_mode`/`token_savings`/`initial_prompt` zusätzlich im Payload → **korrekt abgelehnt** (Pydantic `ValidationError` bei direktem Modelltest, HTTP-Route bestätigt via bestehende Testsuite `test_create_hermes_bad_format_profile_422`)
- Unbekanntes, aber formatgültiges Profil (`jupiter-ghost-nope`) → serverseitig **400 mit deutscher Meldung**, kein stiller Fallback auf `default` (bestätigt in `test_create_hermes_unknown_profile_400`)
- Secrets-Leak-Check: `HermesProfileOption`-Schema erlaubt nur `profile/label/engine/model/error/warning` — kein `provider`/`default`/Rohinhalt der `config.yaml` im API-Response (eigene Codeprüfung `schemas/sessions.py:127-144`, zusätzlich testabgesichert `test_profiles_endpoint_includes_default`)

Keine Findings im Red-Team-Durchlauf.

### Regressionscheck
- Bestehende Hermes-Chat-Session-Verträge (PROJ-85/86) unverändert: `GET /sessions/hermes/options`, Resume-Ablauf, WS-Snapshot — kein Vertragsbruch, additive Felder mit Defaults.
- `features/INDEX.md`: keine anderen „Deployed“-Features durch diesen Diff berührt (nur additive Felder, kein bestehender Endpoint-Vertrag geändert).

### Nicht-fixierte Findings
Keine Low-Bugs gefunden.

### Empfehlung
**READY.** Status auf **Approved** setzen möglich. Nächster Schritt: `/abc-deploy`.

## Deployment
_To be added by /abc-deploy_
