# Frontdesk-Check: Buch-Nuggets bei größeren Büchern

**Datum:** 2026-07-16  
**Quelle:** Nutzerhinweis + Screenshot `image-165.png` + read-only Prüfung von Queue, Vault, Session-Transkripten und Worker-Code  
**Hinweis:** Interne Ersteinschätzung, kein vollständiger QA-Lauf und keine Implementierung.

**Gesamtübersicht:** Buch-Nuggets erzeugt überwiegend keine finalen Artefakte → Übergreifendes Problem → Hoch

### Ticket: Große Bücher enden ohne verwertbares Buch-Nugget

**Kurzbefund:** Übergreifendes Problem

**Eingrenzung:** Schicht: Backend · Modul: Buch-Nuggets-Worker / Session-Orchestrierung

Im Screenshot sind 14 Einträge sichtbar: 13 „Fertig“, 1 „Fehler“. Die persistierte Queue enthält ebenfalls 13 `done` und 1 `error`, aber nur 3 der 13 `done`-Einträge besitzen Markdown- und PDF-Ergebnispfade. Im Vault lassen sich für diese Charge ebenfalls nur diese drei Ergebnisse zuordnen. Damit sind nur 3 von 14 Läufen als vollständig erfolgreich belegt; 11 von 14 haben kein finales Nugget. Zehn davon wurden vom damaligen Worker fälschlich grün markiert, weil jeder beendete/wartende Session-Turn unabhängig von Ergebnisblock und Artefakten als Erfolg galt.

Der explizit fehlgeschlagene Kaufman-Lauf wurde bereits in zehn Chunks zerlegt. Das Transkript zeigt neun zurückgekehrte Chunk-Extrakte; Chunk 10 lief noch. Die Hauptsession wechselte zwischenzeitlich auf „wartend“. Der aktuelle Worker sendet bei einem unvollständigen Ergebnis genau eine Fortsetzung und erklärt das nächste Warten ohne Markdown/PDF sofort zum Fehler. Ein festes Buch-Nuggets-Laufzeit-Timeout ist im Worker nicht vorhanden; der sichtbare Fehler entstand nach rund fünf Minuten durch diese Abschlusslogik, nicht durch ein nachgewiesenes Zeitlimit oder einen belegten Kontextüberlauf.

**Dringlichkeit:** Hoch

Die Kernfunktion liefert in der geprüften Charge nur 3 von 14 belegte Ergebnisse und zeigt zehn unvollständige Läufe irreführend als „Fertig“. Es gibt keinen Datenverlust an Quelldateien, aber die App ist für den Hauptzweck weitgehend unzuverlässig.

**Vorschlag für die nachgelagerte Bearbeitung:**

1. `done` ausschließlich bei vorhandenem `JUPITER_BOOK_RESULT` sowie existierender Markdown- und PDF-Datei setzen; alte grüne Einträge ohne Artefakte als „unvollständig“ kennzeichnen.
2. Die Ein-Fortsetzung-Logik durch ein Fortschritts-/Inaktivitätskriterium ersetzen: Solange neue Chunk-Ergebnisse eintreffen, weiterlaufen lassen; erst nach definierter Inaktivität oder explizitem Agentenfehler abbrechen.
3. Für große Bücher die bereits vorgesehene Map-Reduce-Idee als persistente Pipeline ausführen: Text deterministisch in Kapitel/Chunks teilen, jeden Chunk-Extrakt separat auf Platte/DB checkpointen und anschließend nur die Extrakte konsolidieren. Ein Retry wiederholt dann nur fehlende Chunks statt das ganze Buch.
4. Chunk-Agenten begrenzen (z. B. 2–3 parallel) und pro Buch Fortschritt `9/10 Chunks` anzeigen. Das reduziert Provider-/Session-Druck und macht Hänger diagnostizierbar.
5. Einen Gesamtzeitrahmen nur als Sicherheitsnetz verwenden; entscheidend ist „keine Fortschrittsänderung seit X Minuten“, nicht die absolute Buchlaufzeit.

**Antwortentwurf an den Nutzer:**
> Die Prüfung bestätigt ein übergreifendes Problem. In der sichtbaren Charge sind zwar 13 Einträge grün, tatsächlich lassen sich aber nur drei vollständige Markdown-/PDF-Ergebnisse belegen. Der große Kaufman-Lauf wurde bereits in zehn Teile zerlegt; er scheiterte nicht nachweislich an einem festen Timeout, sondern an der Worker-Logik, die nach nur einer Fortsetzung zu früh abbricht. Wir empfehlen eine checkpoint-basierte Chunk-Pipeline und eine Abschlussprüfung auf echte Artefakte. Eine Implementierung wurde noch nicht vorgenommen.

**Rückfragen-Guidance:** Für eine spätere QA zusätzlich festhalten: gewünschte maximale Laufzeit pro Buch, akzeptierte Parallelität/Kosten sowie ob die zehn historischen „Fertig“-Einträge automatisch auf „unvollständig“ zurückgesetzt und erneut eingereiht werden dürfen.

## Backoffice-Fix

### Fix: Große Buchläufe nicht nach der ersten Fortsetzung abbrechen — PROJ-53

**Modus:** Produkt-Bug  
**Ausgangspunkt:** Dieser Frontdesk-Report · Prior Art: `bug-geloest-buch-pfad.md`, `gotcha-hal-8b905661.md`

**Reproduktion:** Ein Worker-Test simuliert `8/10 Chunks` → Fortsetzung → `9/10 Chunks` → Fortsetzung → vollständige Artefakte. Vor dem Fix endete der Eintrag nach `9/10` als Fehler.

**Ursache:** `backend/app/engine/book_nuggets.py`, `_poll_current()`: Der Bool-Merker `_continuation_sent` erlaubte exakt einen weiteren Turn. Jedes spätere `waiting` wurde unabhängig vom neuen Chunk-Fortschritt als endgültiges Scheitern behandelt.

**Fix:** Begrenzte, fortschrittsabhängige Fortsetzungen; Inline-Fallback im Prompt; Artefakt-Gate für `done`; Korrektur historischer `done`-Zeilen ohne Markdown/PDF beim Worker-Start.

**Verifikation:** Reproduktionsfall rot → grün; `test_proj53_book_nuggets.py` + `test_proj53_qa.py`: 43 Tests grün; `git diff --check` grün. Die vollständige Backend-Suite hing in der Umgebung ohne Abschluss und wurde nach über 90 Sekunden abgebrochen. `ruff` war im Dashboard-Environment nicht installiert.

**Tracking:** Fix `f5d790f`, OpenCode-Support `b0627e5`, Release `ba057a5`; deployed als `v0.27.33-PROJ-53` nach `https://jupiter.auxevo.tech`. `features/INDEX.md` bleibt auf `Deployed`.

**Knowledge:** `/home/dev/tools/Hal/Agentic OS/Jupiter/Knowledge/bug-geloest-jupiter-buch-nuggets-fortsetzung.md`

**Rest-Risiko / Nächster Schritt:** Health, Version, Queue-Korrektur und Modellmigration sind live geprüft. Ein kompletter erneuter Kaufman-Lauf bleibt wegen Laufzeit/Kosten ein manueller Smoke-Test. Persistente Chunk-Checkpoints wären ein separates Robustheits-Feature, nicht Teil dieses minimalen Bugfixes.
