# Benutzeranleitung

## Über diese App

Jupiter ist deine **selbstgehostete Kommandozentrale für KI-Agenten**. Statt mehrere Claude-Sessions im Terminal zu jonglieren, steuerst du sie hier als überwachbare Flotte: mehrere Sessions laufen parallel, du siehst auf einen Blick, welche arbeitet, welche auf dich wartet, und greifst nur an den wichtigen Stellen ein. Dein Wissen sammelt sich automatisch im Hal-Vault, der ABC-Workflow ist das native Arbeitsmodell.

## Erste Schritte

1. **Öffnen:** Rufe `https://jupiter.auxevo.tech` auf (Zugang über Basic-Auth / Tailscale).
2. **Oberfläche:** Links die **Sidebar** (Navigation + zuletzt genutzte Sessions), rechts der Inhalt. Oben dezent die App-Version.
3. **Navigation:** Vier Bereiche — **Cockpit** (Start, Mission Control), **Doku** (Markdown lesen/bearbeiten), **Dateien** (Fileexplorer). Eine offene Session bekommt ihre eigene Detailseite.
4. **Single-User:** Es gibt keine Mandanten/Login-Rollen — Jupiter ist deine persönliche Zentrale.

## Funktionen

### Neue Session starten
**Wofür ist das?** Eine neue Claude-Arbeitssitzung in einem Projekt beginnen.
**So nutzt du es:**
1. Klicke im Cockpit auf **„Neue Session"**.
2. Wähle das **Projekt** — Jupiter schlägt dir Feature, Phase, Skill und Modell vor (gelesen aus der `features/INDEX.md` des Projekts).
3. Übernimm den Vorschlag oder passe ihn an, dann **„Starten"**.
**Tipps & Hinweise:** Gibt es bereits sehr viele aktive Sessions, lehnt Jupiter den Start mit einer Meldung ab (Schutz vor Überlast) — beende oder lösche dann eine fertige Session.

### Mit Claude arbeiten
**Wofür ist das?** Mit der laufenden Session interagieren.
**So nutzt du es:**
1. Öffne die Session (Klick auf die Kachel).
2. Tippe deinen Prompt ins **Eingabefeld** und sende ab.
3. Verfolge das **Live-Transkript** und den **Kontext-Füllstand** oben.
**Tipps & Hinweise:** Der Füllstand zeigt, wie voll das Kontextfenster ist. Nähert er sich der Schwelle, erscheint eine Warnung — dann ist ein Handover sinnvoll (siehe unten). Hinter den Kulissen: [Mit Claude arbeiten](funktionen.md#mit-claude-arbeiten-prompt-eingeben).

### Freigaben entscheiden (Decision Cards)
**Wofür ist das?** An Schaltstellen entscheidest du, ob die Session eine Aktion ausführen darf.
**So nutzt du es:**
1. Steht eine Session auf **„wartet auf Freigabe"**, erscheint eine Karte mit *Was* / *Warum* / *Ausschnitt*.
2. Wähle **Freigeben**, **Ablehnen** oder **Mit Kommentar zurück** (dein Kommentar geht an Claude zurück).
**Tipps & Hinweise:** Welche Aktionen automatisch erlaubt sind und welche dich fragen, steuerst du über die **Trust-Policy** (Einstellungen). Die Session ist währenddessen wirklich angehalten, läuft aber nicht ins Leere.

### Watchdog-Pausen auflösen
**Wofür ist das?** Schutz vor durchdrehenden Sessions (Endlosschleife, Token-Verbrennen, wildes Schreiben).
**So nutzt du es:**
1. Bei Amok pausiert Jupiter die Session automatisch und zeigt eine **amber Watchdog-Karte** mit der gerissenen Metrik.
2. Wähle **Fortsetzen**, **Mit Kommentar korrigieren** oder **Abbrechen**.
**Tipps & Hinweise:** Die Limits (Tokens/Zeit, Stillstand, Wiederholungen, Schreibrate) stellst du in den Einstellungen unter „Watchdog" ein. Eine legitime lange Aufgabe löst normalerweise nicht aus.

### Handover & Session zurücksetzen
**Wofür ist das?** Den Kontext einer vollen Session sauber an eine frische Folge-Session übergeben.
**So nutzt du es:**
1. Klicke in der Session auf **„Handover"** — du bekommst eine editierbare Zusammenfassung.
2. Passe sie an und **speichere** sie (landet als Markdown im Vault).
3. Klicke **„Zurücksetzen"** — eine neue Kind-Session startet mit dem Handover als Startkontext.
**Tipps & Hinweise:** Die Schwelle, ab der gewarnt wird, ist einstellbar (Threshold). Hinter den Kulissen: [Handover erzeugen](funktionen.md#handover-erzeugen--session-zur%C3%BCcksetzen).

### Wissen kuratieren
**Wofür ist das?** Wichtige Erkenntnisse (gelöste Bugs, Entscheidungen, Sackgassen) dauerhaft im Vault festhalten.
**So nutzt du es:**
1. Erkennt eine Session einen solchen Moment, schlägt sie über eine Karte eine **kuratierte Notiz** vor.
2. Passe **Titel/Text** an und gib frei — oder verwirf den Vorschlag.
**Tipps & Hinweise:** Der Vorschlag hält die Session nicht auf. Freigegebenes Wissen ist anschließend über die **Wissens-Suche** auffindbar.

### Doku lesen
**Wofür ist das?** Markdown aus dem Vault und deinen Projekten direkt in Jupiter lesen.
**So nutzt du es:**
1. Öffne **„Doku"**.
2. Wähle die **Quelle** (Vault oder Projekt) und navigiere im **Datei-Baum**.
3. Klicke eine Datei an — sie wird gerendert angezeigt.
**Tipps & Hinweise:** Die Ansicht ist read-only und auf erlaubte Ordner beschränkt.

### Doku bearbeiten
**Wofür ist das?** Markdown direkt bearbeiten, ohne Tool-Wechsel.
**So nutzt du es:**
1. In der Doku-Ansicht in den **Bearbeiten-Modus** wechseln.
2. Text ändern; mit **`[[`** öffnet sich eine Autocomplete für Verlinkungen.
3. **Speichern**.
**Tipps & Hinweise:** Wurde die Datei zwischenzeitlich anderswo geändert, warnt Jupiter (Konflikt), statt blind zu überschreiben. Das **Backlinks-Panel** zeigt, welche Dateien auf die aktuelle verweisen.

### Dateien & Clipboard
**Wofür ist das?** Dateien auf dem VPS verwalten und Inhalte schnell für eine Session bereitstellen.
**So nutzt du es:**
1. Öffne **„Dateien"**, navigiere, lade hoch/herunter, lege Ordner an, benenne um, lösche.
2. Per **Drag-and-Drop** oder **Strg/Cmd+V** (z. B. Screenshot) landet etwas im **Clipboard-Ordner**.
3. Nutze **„Pfad kopieren"** — oder droppe/paste direkt am Session-Eingabefeld, dann wird der Pfad automatisch eingefügt.
**Tipps & Hinweise:** Der Clipboard-Pfad ist kurz und stabil — ideal, um Claude ein gerade kopiertes Bild zu zeigen.

### Hängende Sessions wiederherstellen
**Wofür ist das?** Nach einem Backend-Neustart oder Abbruch eine Session weiterführen.
**So nutzt du es:**
1. Erscheint ein **Recovery-Banner**, öffne den Dialog.
2. Wähle einen Kandidaten (mit Stärke-Bewertung) und klicke **„Wiederherstellen"** — oder **„Verwerfen"**.
**Tipps & Hinweise:** Wiederhergestellt wird über das gespeicherte Handover/den Index — die neue Session führt den Faden fort.

### Sessions löschen & aufräumen
**Wofür ist das?** Das Cockpit übersichtlich halten.
**So nutzt du es:**
1. Auf einer **fertigen/fehlerhaften** Kachel das **Lösch-Icon** klicken und bestätigen.
2. Oder **„Erledigte aufräumen"** für alle terminalen Sessions auf einmal.
**Tipps & Hinweise:** Aktive Sessions lassen sich nicht löschen — beende sie zuerst.

### Workflow-Fortschritt verfolgen (ABC-Gantt)
**Wofür ist das?** Sehen, in welcher ABC-Phase (Brainstorm → … → Deploy → Document) jede Session steckt.
**So nutzt du es:**
1. Im Cockpit unter dem Kanban den **ABC-Gantt** ansehen — eine Zeile pro Session, die aktuelle Phase ist hervorgehoben.
**Tipps & Hinweise:** Die Phase wird automatisch aus dem laufenden `abc-*`-Skill erkannt — du musst nichts pflegen.

### Einstellungen (Trust-Policy & Watchdog)
**Wofür ist das?** Festlegen, was automatisch erlaubt ist und wann die Reißleine greift.
**So nutzt du es:**
1. Öffne die **Einstellungen**.
2. Im Tab **„Trust-Policy"** Freigabe-Regeln pflegen; im Tab **„Watchdog"** die vier Limits einstellen.
3. **Speichern** — die Änderungen greifen sofort.
**Tipps & Hinweise:** Lässt du Felder leer/ungültig, fallen sichere Defaults ein.

## Häufige Fragen

**Warum erscheint manchmal eine Freigabe-Karte und manchmal nicht?**
Das steuert deine Trust-Policy: manche Aktionen sind auto-erlaubt, andere brauchen deine Freigabe, manche werden ganz verweigert.

**Was passiert mit meinen Sessions bei einem Neustart?**
Die Übersicht bleibt erhalten (SQLite-Index). Laufende Sessions, deren Prozess den Neustart nicht überlebt, werden als „verwaist" markiert und lassen sich über Recovery weiterführen.

**Wo landet das Wissen, das die Sessions sammeln?**
Als offenes Markdown im Hal-Vault (Logs, Handovers, kuratiertes Wissen) — auch direkt in Obsidian lesbar.

**Warum wird eine Session plötzlich pausiert, obwohl ich nichts getan habe?**
Vermutlich der Watchdog — sie hat ein Limit gerissen (z. B. zu viele identische Aktionen). Die Karte nennt den Grund; mit „Fortsetzen" läuft sie weiter.

**Kann ich eine aktive Session löschen?**
Nein — beende sie zuerst. Das schützt vor versehentlichem Datenverlust.

**Brauche ich einen Anthropic-API-Key?**
Nein. Jupiter nutzt Claude Code headless über deine Subscription-Auth, kein API-Key.
