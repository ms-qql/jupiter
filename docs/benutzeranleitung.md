# Benutzeranleitung

## Über diese App

Jupiter ist deine **selbstgehostete Kommandozentrale für KI-Agenten**. Statt mehrere Claude-Sessions im Terminal zu jonglieren, steuerst du sie hier als überwachbare Flotte: mehrere Sessions laufen parallel, du siehst auf einen Blick, welche arbeitet, welche auf dich wartet, und greifst nur an den wichtigen Stellen ein. Dein Wissen sammelt sich automatisch im Hal-Vault, der ABC-Workflow ist das native Arbeitsmodell.

## Erste Schritte

1. **Öffnen:** Rufe `https://jupiter.auxevo.tech` auf. Du landest auf dem **Login-Screen**.
2. **Erster Start:** Falls kein Account existiert, erscheint ein Bootstrap-Formular — einmalig Account anlegen.
3. **Login:** Benutzername + Passwort eingeben → **Anmelden**. Du bleibst eingeloggt; Access-Token wird automatisch erneuert.
4. **Oberfläche:** Links die **Sidebar** (Navigation + zuletzt genutzte Sessions, Micro-Apps, Orchestration), rechts der Inhalt.
5. **Navigation:** **Cockpit** (Kanban + Gantt), **Doku** (Markdown lesen/bearbeiten), **Dateien** (Fileexplorer), **Apps** (Marktplatz + Micro-Apps).

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

### Spracheingabe
**Wofür ist das?** Prompts per Sprache diktieren statt tippen.
**So nutzt du es:**
1. In der Session den **Mikrofon-Button** gedrückt halten.
2. Sprechen.
3. Loslassen — der Text erscheint im Eingabefeld (wird ans Bestehende angehängt, nicht ersetzt).
**Tipps & Hinweise:** Läuft lokal auf dem VPS (kein US-Dienst). Hinter den Kulissen: [Spracheingabe](funktionen.md#spracheingabe--push-to-talk).

### Git-Branch wechseln / Feature-Branch anlegen
**Wofür ist das?** Branches direkt in Jupiter wechseln oder neue Feature-Branches anlegen — ohne Terminal.
**So nutzt du es:**
1. Im Bereich **„Dateien"** das **Branch-Panel** öffnen.
2. Einen bestehenden Branch wählen (wechseln) **oder** einen neuen Namen eingeben.
3. Bestätigen.
**Tipps & Hinweise:** Gibt es uncommittete Änderungen, blockiert Jupiter den Wechsel mit einer Meldung. Erst committen oder stashen.

### Multi-Agent-Fleet starten
**Wofür ist das?** Mehrere Tickets (Features) automatisch auf parallele Claude-Sessions verteilen lassen.
**So nutzt du es:**
1. In einer Koordinator-Session das **Dispatch-Panel** öffnen.
2. Den Plan prüfen (Reihenfolge, Abhängigkeiten).
3. **„Freigeben"** — Jupiter startet die Kind-Sessions automatisch.
**Tipps & Hinweise:** Blockierte Tickets (offene Abhängigkeiten) warten in der Queue und starten automatisch nach. Fleet jederzeit pausierbar. Hinter den Kulissen: [Multi-Agent-Fleet](funktionen.md#multi-agent-fleet-starten-coordinator).

### Cross-Agent-Review starten
**Wofür ist das?** Ein Artefakt von einer zweiten KI (evtl. anderer Engine) adversariell prüfen lassen.
**So nutzt du es:**
1. In der Session auf **„Review starten"** klicken.
2. Reviewer-Engine und Fokus wählen (z. B. „Sicherheit").
3. Findings im **Reviews-Panel** einzeln annehmen, ablehnen oder kommentieren.
**Tipps & Hinweise:** Der Reviewer sucht bewusst Fehler. Alle Entscheidungen landen als Audit-Trail im Vault. Hinter den Kulissen: [Cross-Agent-Review](funktionen.md#cross-agent-review-starten).

### Marktplatz: Rollen, Skills, Agenten
**Wofür ist das?** Neue Rollen (z. B. Sicherheits-Reviewer) oder Skills importieren und aktivieren.
**So nutzt du es:**
1. Öffne **„Apps"** in der Navigation.
2. Katalog durchsuchen **oder** `.jupkg`-Datei hochladen.
3. Import-Preview prüfen → **Bestätigen** → **Aktivieren**.
**Tipps & Hinweise:** Import ist zweistufig (Preview → Confirm) — du siehst den Einfluss auf Policies, bevor etwas wirksam wird.

### Session reanimieren
**Wofür ist das?** Eine hängende Session automatisch oder manuell neu starten.
**So nutzt du es:**
1. Der **Heartbeat-Dot** einer Session wird rot → sie ist eingefroren.
2. Jupiter versucht automatisch neu zu starten (Standard: 2 Versuche mit Abstand).
3. Danach: **„Reanimieren"**-Button in der Session drücken.
**Tipps & Hinweise:** Hinter den Kulissen: [Session reanimieren](funktionen.md#session-reanimieren-liveness--auto-restart).

### Video zusammenfassen
**Wofür ist das?** Video-Inhalte (URL) automatisch transkribieren und zusammenfassen.
**So nutzt du es:**
1. Öffne die **Video-Summary-App** in der Sidebar.
2. Video-URL einfügen → **„In Warteschlange"**.
3. **„Jetzt starten"** oder im Hintergrund laufen lassen.
4. Fertiges Summary in der **Bibliothek** lesen.
**Tipps & Hinweise:** Modell-Wahl ist persistent gespeichert. Summary landet als Markdown im Hal-Vault.

### VPS-Admin: Metriken & Terminal
**Wofür ist das?** Serverauslastung im Blick halten und bei Bedarf eine Shell öffnen.
**So nutzt du es:**
1. **Dashboard**: VPS-Admin-App öffnen → CPU/RAM/Disk/Load als Ampel sehen.
2. **Terminal**: „Terminal öffnen" klicken → vollwertige Shell im Browser-Tab (ttyd).
**Tipps & Hinweise:** Metriken sind read-only und gecacht. Das Terminal ist eine echte Shell auf dem VPS.

### Sidebar anpassen
**Wofür ist das?** Sektionen ein-/ausblenden und umordnen, damit die Sidebar zu deinem Workflow passt.
**So nutzt du es:**
1. Klicke das **Konfig-Icon** im Sidebar-Header.
2. Sektionen ein-/ausblenden oder per Drag-and-Drop verschieben.
3. **Speichern** — Einstellung bleibt nach Reload erhalten.
**Tipps & Hinweise:** Die Workspace-Sektion ist immer sichtbar — so kommst du immer ans Konfig-Panel. Neue Apps erscheinen nach Installation automatisch in der Sidebar.

## Häufige Fragen

**Warum erscheint manchmal eine Freigabe-Karte und manchmal nicht?**
Das steuert deine Trust-Policy: manche Aktionen sind auto-erlaubt, andere brauchen deine Freigabe, manche werden ganz verweigert. Einstellbar unter „Trust-Policy".

**Was passiert mit meinen Sessions bei einem Neustart?**
Jupiter versucht beim Hochfahren, geordnet beendete Sessions automatisch fortzusetzen (Drain/Resume). Laufende Sessions, die den Neustart nicht überlebt haben, werden als „verwaist" markiert und lassen sich über Recovery weiterführen.

**Wo landet das Wissen, das die Sessions sammeln?**
Als offenes Markdown im Hal-Vault (Logs, Handovers, kuratiertes Wissen) — auch direkt in Obsidian lesbar.

**Warum wird eine Session plötzlich pausiert, obwohl ich nichts getan habe?**
Entweder der Watchdog (zu viele identische Aktionen / Token-Burn) oder ein Liveness-Timeout. Die Karte nennt den Grund; mit „Fortsetzen" läuft sie weiter.

**Kann ich eine aktive Session löschen?**
Nein — beende sie zuerst. Das schützt vor versehentlichem Datenverlust.

**Brauche ich einen Anthropic-API-Key?**
Nein. Jupiter nutzt Claude Code headless über deine Subscription-Auth, kein API-Key.

**Wie lange bin ich eingeloggt?**
Der Access-Token läuft nach 15 Minuten ab und wird automatisch erneuert (über ein httpOnly-Cookie, das 7 Tage gilt). Im Normalbetrieb musst du dich nicht erneut anmelden.

**Was ist der Unterschied zwischen Decision Card, Watchdog-Karte und Liveness-Banner?**
Decision Card = Claude fragt vor einer Aktion nach Erlaubnis. Watchdog-Karte (amber) = automatische Reißleine bei Amok-Verhalten. Liveness-Banner (rot) = Session ist eingefroren, nicht pausiert.

**Kann ich mehrere Tickets gleichzeitig bearbeiten lassen?**
Ja — mit dem Coordinator (Multi-Agent-Fleet) dispatcht Jupiter mehrere Kind-Sessions parallel. Abhängige Tickets warten automatisch auf ihre Vorgänger.

**Warum erkenne ich im Aktivitäts-Ticker keine alten Tool-Aufrufe?**
Der Ticker ist transient — er zeigt nur das Jetzt. Für die volle Tool-History ist das Transkript zuständig.
