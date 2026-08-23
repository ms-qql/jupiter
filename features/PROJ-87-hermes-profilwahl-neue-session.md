# PROJ-87: Hermes-Profilwahl im Neue-Hermes-Session-Dialog

## Status: Planned
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
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
