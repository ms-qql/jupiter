# PROJ-69: Clipboard (native Micro-App)

## Status: Approved
**Created:** 2026-07-08
**Last Updated:** 2026-07-08

## Dependencies
- Requires: PROJ-40 (Sidebar-Sektion „Micro-Apps" + `kind: native`) — Clipboard ist eine native Micro-App (`group: micro`, `kind: native`, Route `/apps/<key>`, Eintrag in `microapps-registry.ts`).
- Requires: PROJ-2 / PROJ-24 (Vault-Anbindung) — jedes angenommene Clipboard-Item wird automatisch als Rohmaterial in den Hal-Vault geschrieben.
- Requires: PROJ-11 (Fileexplorer + Drag-and-Drop) — vorhandene Upload-/Download-/Scope-Mechanik und Drag&Drop-Muster werden wiederverwendet.
- Bezug: PROJ-15 / PROJ-55 (Vault-Kuratierung und Session-Kondensierung) — spätere HAL-Kondensierung liest aus dem Clipboard-Inbox-Rohspeicher, ist aber nicht Teil dieses MVP.
- Bezug: PROJ-25 (Auth/Owner-Feld) — MVP bleibt Tailscale/single-user, stempelt aber `owner` für spätere Teamfähigkeit.

## Beschreibung
Eine native Jupiter Micro-App **„Clipboard"** stellt einen privaten, über Tailscale erreichbaren, geräteübergreifenden Datei-Clipboard für **PC, Mac, iPad und iPhone** bereit. Der Nutzer legt Screenshots, PDFs und Dokumente von Desktop- oder Mobilgeräten in eine chronologische Clipboard-Liste. Jeder angenommene Eintrag wird automatisch als Rohmaterial in einen unsortierten **HAL Inbox**-Ordner kopiert.

Die aktive Clipboard-Liste bleibt erhalten, bis der Nutzer Einträge manuell entfernt. Entfernen aus der aktiven Liste löscht im MVP **nicht** die HAL-Inbox-Rohdatei. Die App ist ein Arbeits-Puffer und Transferkanal, kein vollständiger OS-Clipboard-Ersatz und keine automatische Wissens-Kuratierung.

### Geklärte Entscheidungen aus `docs/Brainstorm.md` (2026-07-08)
- **Produktform:** Native Micro-App in Jupiter, erreichbar über Tailscale.
- **MVP-Ziel:** iPad-Screenshot auf PC bewegen und PC-PDF auf iPad bewegen; beide Dateien landen automatisch im HAL Inbox.
- **Eingaben:** Desktop Drag&Drop, Desktop Paste soweit Browser-APIs es erlauben, mobile/iOS Share-kompatibler Upload-Pfad.
- **Ausgaben:** Vorschau für Bilder/PDFs, Download für alle Dateien, Desktop Copy-to-Clipboard für unterstützte Bilder, iOS Öffnen/Teilen wo Browser/PWA-APIs es erlauben.
- **HAL-Speicher:** Jedes Item wird automatisch als Rohdatei plus Metadaten in den HAL Inbox geschrieben.
- **Lifecycle:** Einträge bleiben sichtbar bis zur manuellen Entfernung; keine automatische Retention im MVP.
- **Abgrenzung:** Watch Folder, automatische semantische HAL-Ablage, wöchentliche Kondensierung, öffentliche Internetfreigabe und komplexe Rechteverwaltung sind nicht Teil dieses Features.

## User Stories
- Als Nutzer möchte ich die Clipboard-Micro-App auf PC, Mac, iPad und iPhone über mein Tailscale-Netz öffnen, damit ich Dateien ohne Cloud-Dienst zwischen Geräten bewegen kann.
- Als Nutzer möchte ich Bilder, PDFs und Dokumente per Drag&Drop vom Desktop hinzufügen, damit lokale Dateien sofort auf anderen Geräten verfügbar sind.
- Als Nutzer möchte ich unterstützte Desktop-Clipboard-Inhalte in die App einfügen, damit Screenshots oder Dateien ohne Dateiauswahl übernommen werden.
- Als Nutzer möchte ich von iPhone/iPad aus über den bestmöglichen Share-/Upload-Pfad Bilder und PDFs an Jupiter Clipboard senden, damit mobile Screenshots und Dokumente im PC-/VPS-Workflow ankommen.
- Als Nutzer möchte ich jedes Item in einer chronologischen Liste mit Name, Typ, Quelle, Zeitpunkt und Größe sehen, damit ich schnell das richtige Material finde.
- Als Nutzer möchte ich Bilder und PDFs direkt in der App ansehen, damit ich vor Download oder Weitergabe prüfen kann, ob es das richtige Item ist.
- Als Nutzer möchte ich jedes Item herunterladen, öffnen oder auf iOS weiterteilen können, damit der Transfer in beide Richtungen funktioniert.
- Als Nutzer möchte ich unterstützte Bilder aus der App in die Desktop-Zwischenablage kopieren, damit ein iPad-Screenshot direkt in das nächste Desktop-Tool eingefügt werden kann.
- Als Nutzer möchte ich ein Item aus der aktiven Liste entfernen, ohne die HAL-Inbox-Rohdatei zu verlieren.
- Als Nutzer möchte ich sicher sein, dass jedes akzeptierte Item automatisch im HAL Inbox landet, damit Transfermaterial später kondensiert oder einsortiert werden kann.

## Acceptance Criteria
- [ ] **Clipboard** erscheint als Eintrag in der Sidebar-Sektion „Micro-Apps" (`group: micro`, `kind: native`) mit Label + Icon und öffnet als Vollbild unter `/apps/<key>`.
- [ ] Die App ist als **native** Micro-App umgesetzt (React-Komponente im Repo, registriert in `microapps-registry.ts`) — kein iFrame.
- [ ] Die Micro-App ist von Tailscale-verbundenen Geräten per Browser erreichbar; es wird kein öffentlicher Internetzugang benötigt.
- [ ] Die aktive Liste zeigt Clipboard-Items chronologisch, neueste zuerst oder klar erkennbar sortiert.
- [ ] Die Liste zeigt pro Item mindestens: Anzeigename/Dateiname, MIME-/Dateityp, Quelle/Source-Methode, Upload-Zeitpunkt, Größe und Status.
- [ ] Desktop Drag&Drop akzeptiert Bilder, PDFs und generische Dokumente innerhalb des konfigurierten Größenlimits.
- [ ] Desktop Paste akzeptiert unterstützte Clipboard-Inhalte (insbesondere Bilder/Screenshots), wenn der Browser diese über die Clipboard API bereitstellt.
- [ ] Mobile/iOS bietet einen share-kompatiblen Eingabepfad für mindestens Bilder und PDFs; falls native Share-Target-PWA technisch nicht verfügbar ist, muss ein klarer Upload-/Öffnen-in-Browser-Fallback vorhanden sein.
- [ ] Jedes akzeptierte Item erscheint nach Upload ohne manuellen Refresh oder nach einer klar sichtbaren Aktualisierung in der Liste.
- [ ] Jedes akzeptierte Item wird automatisch in den konfigurierten HAL-Inbox-Zielordner kopiert.
- [ ] Zu jedem HAL-Inbox-Item wird Metadatenkontext gespeichert: Upload-Zeit, Quelle/Source-Methode, Originalname, MIME-Type, Größe und interner Item-Identifier.
- [ ] Bilder und PDFs können in der App als Vorschau geöffnet werden; nicht vorschaubare Dateien fallen auf eine generische Dateiansicht mit Download-Aktion zurück.
- [ ] Jedes Item kann heruntergeladen werden.
- [ ] Unterstützte Bilder können über eine Aktion **„In Zwischenablage kopieren"** in die Desktop-OS-Zwischenablage geschrieben werden; nicht unterstützte Typen zeigen eine deutsche, nicht-blockierende Erklärung.
- [ ] Auf iOS/iPadOS können unterstützte Items geöffnet oder weitergeteilt werden, soweit Browser/PWA-APIs dies erlauben; andernfalls bleibt Download/Öffnen als Fallback verfügbar.
- [ ] Der Nutzer kann einzelne Items aus der aktiven Clipboard-Liste entfernen.
- [ ] Entfernen aus der aktiven Liste setzt das Item auf `removed_from_clipboard` oder blendet es aus, löscht aber im MVP **nicht** die HAL-Inbox-Rohdatei.
- [ ] Upload-Fehler erzeugen keinen irreführenden aktiven Eintrag; die UI zeigt eine deutsche Fehlermeldung mit knappem Grund.
- [ ] Nicht unterstützte Dateitypen werden entweder als generische Datei angenommen oder mit deutscher Fehlermeldung abgewiesen; das Verhalten ist konsistent dokumentiert.
- [ ] Liste und Metadaten überleben Browser-Reload und Backend-Neustart.
- [ ] Alle UI-Texte, Fehler und Statusmeldungen sind deutsch; App-Eigenname „Clipboard" bleibt.

## Edge Cases
- **Browser unterstützt Clipboard API nicht** → Paste-/Copy-Aktionen sind deaktiviert oder zeigen „Diese Aktion wird von diesem Browser nicht unterstützt"; Upload/Download bleiben nutzbar.
- **iOS Share Target nicht zuverlässig verfügbar** → MVP bietet einen klaren Browser-Upload-Fallback; das Feature gilt trotzdem als erfüllt, wenn Bilder/PDFs vom iOS-Gerät in die Liste gelangen.
- **Sehr große Datei** → Upload wird vor oder während der Annahme mit deutscher Fehlermeldung abgewiesen; es wird kein halbes Item in der aktiven Liste erzeugt.
- **Doppelter Upload derselben Datei** → MVP darf beide Einträge als separate Clipboard-Items anlegen, muss sie aber anhand Zeitstempel/Name unterscheidbar anzeigen.
- **Unbekannter MIME-Type** → Item wird als generische Datei geführt, sofern Größe/Extension erlaubt sind; Vorschau wird nicht erzwungen.
- **Dateiname fehlt** (z. B. Paste-Blob oder Share-Blob) → App erzeugt einen stabilen Anzeigenamen aus Zeitstempel, Source-Methode und Extension/Fallback.
- **HAL-Kopie schlägt fehl** → Upload gilt als fehlgeschlagen oder Item geht sichtbar auf `error`; es darf kein aktives Item ohne HAL-Inbox-Persistenz entstehen.
- **Aktive Liste entfernt, HAL-Rohdatei bleibt** → Wiederherstellung über HAL ist möglich, aber nicht Teil der aktiven Liste; kein stilles Löschen im Vault.
- **Backend-Neustart während Upload** → Item wird entweder vollständig übernommen oder sauber verworfen; keine defekten Dateileichen in der aktiven Liste.
- **Zwei Geräte laden gleichzeitig hoch** → beide Items erhalten eindeutige IDs und sortieren sich deterministisch nach `created_at`.
- **Sektion „Micro-Apps" im Konfig-Panel ausgeblendet** → Direkt-URL `/apps/<key>` bleibt erreichbar.
- **Tailscale-/Netzwerkunterbrechung** → laufende Upload-Aktion zeigt Fehler; bereits persistierte Items bleiben sichtbar.

## Technical Requirements (optional)
- **Native Micro-App-Muster (PROJ-40/41/53):** Metadaten-Eintrag in `backend/config/engines.yaml` (`kind: native`, `group: micro`, Label, Icon); Code unter `nextjs_app/components/microapps/<key>/`, registriert in `nextjs_app/lib/microapps-registry.ts`; Render über den native-Zweig in `app/(cockpit)/apps/[key]/page.tsx`.
- **Persistenz:** Aktive Clipboard-Liste und Metadaten serverseitig persistieren, konsistent mit bestehenden Micro-App-Mustern (SQLite-Repo/Tabellen statt neuer Infrastruktur). Jedes Item enthält mindestens `id`, `owner`, `created_at`, `source_device`, `source_method`, `original_filename`, `display_name`, `mime_type`, `size_bytes`, `storage_path`, `hal_inbox_path`, `status`, `notes`.
- **HAL-Inbox-Ziel:** Default-Vorschlag aus dem Brainstorm: `/home/dev/tools/Hal/00 Inbox/Clipboard/`, sofern bestehende Hal-Konventionen keinen anderen Inbox-Pfad vorgeben. Pro Item: `YYYY-MM-DD_HHMMSS_<source-device>_<slug-or-id>.<ext>` plus Sidecar-Metadaten (`.md` oder zentrale Index-Zeile).
- **Storage-Entscheidung:** Architektur entscheidet, ob die aktive App-Datei identisch mit der HAL-Inbox-Datei ist oder zusätzlich ein App-Storage-Pfad existiert. Requirement: HAL-Inbox-Kopie muss nach erfolgreicher Annahme existieren und aktive Löschung darf sie nicht entfernen.
- **API:** neue FastAPI-Routen für Upload/Paste-Blob-Annahme, Liste, Dateiabruf/Download, Vorschau, Entfernen aus aktiver Liste und optional Metadaten-/Notiz-Update.
- **Frontend:** React-Komponente mit Dropzone, Paste-Handler, Liste, Preview-Panel/Dialog, Download/Open/Share/Copy/Delete-Aktionen, Empty/Loading/Error-Zuständen und Polling/Refresh nach Upload.
- **iOS-Pfad:** Architektur validiert, ob Jupiter als PWA Share Target, Shortcut-kompatibler Upload-Endpunkt oder Browser-Upload umgesetzt wird. MVP muss mindestens einen zuverlässigen iOS-Pfad für Bilder/PDFs bieten.
- **Sicherheit:** Kein öffentliches Sharing im MVP; Zugriff bleibt im Tailscale/private deployment-Kontext. `owner` wird gestempelt, aber echtes Auth/RLS ist nicht Teil dieses Features.
- **Texte deutsch.**

### Open Points (für /abc-architecture zu entscheiden)
1. **Exakter HAL-Inbox-Pfad:** `/home/dev/tools/Hal/00 Inbox/Clipboard/` übernehmen oder bestehende Inbox-Konvention im Hal-Vault nutzen?
2. **Source-Device-Erkennung:** automatisch aus Client/UA ableiten, manuelles Gerätelabel anbieten oder optional lassen?
3. **Aktive Dateiablage:** nur HAL-Inbox-Datei verwenden oder zusätzlich App-Storage mit `storage_path` führen?
4. **iOS Share-Integration:** PWA Share Target vs. Shortcut-kompatibler Upload-Endpunkt vs. Browser-only Upload-Fallback.
5. **MVP-Dateigröße:** globales Upload-Limit festlegen und konsistent mit vorhandenen Jupiter-Upload-Limits halten.
6. **Löschsemantik:** aktive Liste nur ausblenden (`removed_from_clipboard`) oder App-Storage entfernen, während HAL-Inbox erhalten bleibt.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-08 · **Stack:** Next.js 16 native Micro-App + FastAPI + SQLite + Hal-Vault-Dateisystem · **Branch:** dev

### Überblick / Grundhaltung
Clipboard wird als **native Micro-App** gebaut, nicht als iFrame und nicht als Erweiterung des bestehenden Fileexplorers. Der bestehende `/files`-Dienst bleibt der generische Datei-Service für Explorer, Session-Anhänge und Downloads. PROJ-69 bekommt einen eigenen **Clipboard-Dienst**, weil hier drei Dinge untrennbar zusammengehören: Datei annehmen, Rohkopie im HAL Inbox speichern und einen persistenten aktiven Listen-Eintrag erzeugen.

Die Datei im **HAL Inbox ist die primäre Ablage**. Es wird kein separater App-Storage und kein MinIO eingeführt. Die SQLite-Tabelle ist nur der schnelle Live-Index für Liste, Metadaten, Status und Löschsemantik. Das passt zu Video Summary, Buch-Nuggets, Session-Kondensierung und Peppermint: Micro-App-Zustand lokal in SQLite, langlebige Artefakte offen im Dateisystem/Vault.

### A) Komponenten-Struktur (UI-Baum)
```
/apps/clipboard  (native, Vollbild)
└── ClipboardApp
    ├── UploadZone
    │   ├── Dropzone für Drag&Drop
    │   ├── Datei-auswählen Button
    │   └── Paste-Listener für unterstützte Clipboard API Inhalte
    ├── DeviceHintBar
    │   └── zeigt aktuellen Erkennungshinweis: PC · Mac · iPad · iPhone · unbekannt
    ├── ClipboardList
    │   └── ClipboardItemRow
    │       ├── Typ-/Status-Badge
    │       ├── Name, Größe, Quelle, Zeitpunkt
    │       └── Aktionen: Vorschau · Download · Kopieren · Teilen/Öffnen · Entfernen
    ├── PreviewPanel oder PreviewDialog
    │   ├── Bildvorschau
    │   ├── PDF-Vorschau
    │   └── generische Dateiansicht
    ├── EmptyState
    ├── UploadProgress / Fehlerzustand
    └── MobileFallbackPanel
        └── iOS/iPadOS Upload-Hinweis + Datei-Auswahl-Fallback
```

Registry-Wiring wie PROJ-41/53: `engines.yaml` bekommt `clipboard` mit `kind: native`, `group: micro`, Icon z. B. `clipboard`; `microapps-registry.ts` registriert die React-Komponente unter demselben Key. Die Route `/apps/clipboard` läuft über den bestehenden nativen Micro-App-Host.

### B) Datenmodell (Klartext)
**SQLite-Tabelle `clipboard_items`** hält einen Eintrag pro angenommenem Item:
- eindeutige ID
- `owner` für die spätere Team-Migration
- Upload-Zeitpunkt
- Source-Methode: `drag_drop`, `paste`, `upload`, später optional `ios_share`
- Source-Gerät: best-effort `pc`, `mac`, `ipad`, `iphone`, `unknown`
- Original-Dateiname und Anzeigename
- MIME-Type, Extension, Größe
- HAL-Inbox-Pfad der Datei
- Pfad der Sidecar-Metadaten im HAL Inbox
- Status: `active`, `removed_from_clipboard`, `error`
- optionale Notiz / Kontexttext
- Fehlertext bei fehlgeschlagener Annahme

**HAL Inbox-Ablage**:
- Zielordner: `/home/dev/tools/Hal/00 Inbox/Clipboard/`
- Pro Item eine Rohdatei mit Zeitstempel, Source-Gerät und kurzer ID im Namen.
- Pro Item eine Sidecar-Markdown-Datei mit Metadaten. Das hält den Vault menschenlesbar und gibt späterer Kondensierung eine stabile Quelle.

**Keine zusätzliche App-Dateiablage:** Download, Vorschau und Copy-to-Clipboard lesen die HAL-Datei. Entfernen aus der aktiven Liste blendet nur den SQLite-Eintrag aus bzw. setzt ihn auf `removed_from_clipboard`; die HAL-Datei bleibt.

### C) API-Shape (Endpunkte, kein Code)
- `GET /clipboard/items` → aktive Clipboard-Liste, neueste zuerst.
- `POST /clipboard/items` → Datei/Blob annehmen, HAL-Datei + Sidecar schreiben, Listen-Eintrag erzeugen.
- `GET /clipboard/items/{id}` → Metadaten eines Items lesen.
- `GET /clipboard/items/{id}/download` → Datei authentifiziert herunterladen.
- `GET /clipboard/items/{id}/preview` → Datei für Vorschau laden, wenn Browser/Typ geeignet.
- `PATCH /clipboard/items/{id}` → Anzeigename oder Notiz ändern.
- `DELETE /clipboard/items/{id}` → aus aktiver Liste entfernen, HAL-Rohdatei behalten.
- `GET /clipboard/settings` → Größenlimit, erlaubte Typen, HAL-Inbox-Ziel lesen.

Die Routen hängen wie die übrigen geschützten Micro-App-APIs am bestehenden Auth-Gate. Vor Bootstrap bleibt der heutige Single-User-Modus erhalten; danach greift PROJ-25.

### D) Tech-Entscheidungen (WARUM)
- **Eigener `/clipboard`-Router statt `/files/upload` direkt:** `/files/upload` speichert nur Dateien. Clipboard muss Dateiannahme, HAL-Persistenz und Listen-Metadaten atomar behandeln. Sonst könnten Dateien ohne Listen-Eintrag oder Einträge ohne HAL-Kopie entstehen.
- **HAL-Datei als primäre Dateiablage:** Das Brainstorm verlangt automatische Rohspeicherung im HAL Inbox. Eine zweite App-Kopie würde Löschsemantik, Speicherverbrauch und Recovery verkomplizieren.
- **SQLite für den Live-Index:** Jupiter nutzt für native Micro-App-Zustand bereits SQLite. Für eine private Tailscale-Clipboard-Liste ist Postgres/MinIO zu groß und würde neue Infrastruktur ohne Nutzen einführen.
- **Kein MinIO:** Dateien sollen offen im Hal-Vault landen, nicht in Object Storage. Die Dateigröße ist durch das vorhandene Upload-Limit gedeckelt.
- **Sidecar-Markdown statt nur DB-Metadaten:** Die spätere HAL-Kondensierung kann direkt im Vault arbeiten, auch wenn die SQLite-DB fehlt oder neu aufgebaut wird.
- **Best-effort Device Detection:** Source-Gerät wird aus Browser-/Client-Hinweisen abgeleitet und darf `unknown` sein. Kein Blocker, weil Source-Methode und Zeitstempel die Kernnachvollziehbarkeit liefern.
- **iOS im MVP über zuverlässigen Upload-Fallback:** Eine echte PWA Share-Target-Integration ist browser-/Installations-abhängig. Das MVP gilt als erfüllt, wenn iPhone/iPad Bilder und PDFs zuverlässig über die Micro-App-Dateiauswahl bzw. Öffnen-im-Browser hochladen können. PWA Share Target bleibt Fast-Follow.
- **Polling/Refresh statt WebSocket:** Clipboard-Uploads sind nutzergetrieben und selten. Nach Upload aktualisiert die UI direkt; zusätzlich reicht leichtes Polling/Refresh für andere Geräte.
- **Aktives Entfernen ist kein Vault-Löschen:** Das schützt vor versehentlichem Datenverlust und entspricht dem Brainstorm: Arbeitsliste aufräumen, Rohmaterial für HAL behalten.

### E) Abhängigkeiten / Pakete
- **Backend:** keine neuen Pakete. FastAPI Multipart, SQLite, Dateisystem und bestehende Auth-/File-Patterns reichen.
- **Frontend:** keine neuen Pakete. React/Next.js, bestehender API-Client, shadcn/ui, lucide-react und Browser APIs (`DataTransfer`, `Clipboard API`, `Web Share` best-effort) reichen.
- **Infra:** keine neuen Dienste. Kein MinIO, kein Worker, keine Headless-Agent-Session.

### F) Bau-Reihenfolge / Hand-offs
1. **Backend (`/abc-backend`)**: SQLite-Repository, `ClipboardService`, `/clipboard`-Router, Config-Defaults (`clipboard_db_path`, `clipboard_inbox_dir`), HAL-Sidecar-Schreiben, Download/Preview aus Item-ID, Tests für Upload/Status/Löschsemantik.
2. **Frontend (`/abc-frontend`)**: `engines.yaml`/Registry-Eintrag, `clipboard`-Komponente, Dropzone, Paste-Handler, Liste, Vorschau, Download/Copy/Share/Remove-Aktionen, API-Client-Typen.
3. **QA (`/abc-qa`)**: Desktop Drag&Drop, Paste, Download, Bild/PDF-Vorschau, Entfernen ohne HAL-Löschung, Reload/Neustart-Persistenz, mobile Upload-Fallbacks.

### G) Open Points — entschieden für MVP
1. **HAL-Inbox-Pfad:** `/home/dev/tools/Hal/00 Inbox/Clipboard/`.
2. **Source-Device:** automatische Best-effort-Erkennung; kein Pflichtfeld im UI.
3. **Aktive Dateiablage:** HAL-Datei ist primär; kein separater App-Storage.
4. **iOS Share:** MVP baut Browser-/Dateiauswahl-Fallback; PWA Share Target nur Fast-Follow, falls schnell möglich.
5. **Dateigröße:** vorhandenes globales `upload_max_file_bytes` verwenden (aktuell 50 MB), kein zweites Limit.
6. **Löschsemantik:** aktive Liste blendet aus bzw. markiert `removed_from_clipboard`; HAL-Datei und Sidecar bleiben erhalten.

## Implementation Notes (Backend — /abc-backend, 2026-07-08)

**Branch:** `dev`. Backend vollständig; Frontend ist der nächste Hand-off.

### Neue/geänderte Dateien
- `backend/app/db/clipboard_items.py` — SQLite-Repository für `clipboard_items` mit Status `active`, `removed_from_clipboard`, `error`; aktive Liste sortiert neueste zuerst; Metadaten überleben Neustart.
- `backend/app/engine/clipboard.py` — `ClipboardService`: nimmt Upload-/Paste-Blobs an, schreibt Rohdatei + Sidecar-Markdown atomar in den HAL Inbox, legt danach den Live-Index-Eintrag an, entfernt aktive Items ohne HAL-Löschung.
- `backend/app/schemas/clipboard.py` — Pydantic-v2-Schemas für Item, Liste, Patch und Settings.
- `backend/app/routes/clipboard.py` — API unter `/clipboard`: Upload/List/Get/Patch/Delete/Download/Preview/Settings.
- `backend/app/config.py` — neue Defaults `clipboard_db_path` und `clipboard_inbox_dir`; bestehende Upload-Limits/Extensions werden wiederverwendet.
- `backend/app/db/__init__.py` — Repository-Exports.
- `backend/app/main.py` — Clipboard-Service initialisiert und Router registriert.
- `backend/tests/conftest.py` — Test-Isolation für Clipboard-DB und HAL-Inbox.
- `backend/tests/test_proj69_clipboard.py` — 7 Tests für Service, Persistenz und API.

### API-Vertrag (für Frontend)
- `GET /clipboard/items` → `{items:[ClipboardItem]}`
- `POST /clipboard/items` → Multipart `{file, source_method?, source_device?, notes?}`; schreibt Datei + Sidecar in HAL Inbox und gibt das Item zurück.
- `GET /clipboard/items/{id}` → Item-Metadaten.
- `PATCH /clipboard/items/{id}` → `display_name`/`notes` ändern; Sidecar wird aktualisiert.
- `DELETE /clipboard/items/{id}` → aus aktiver Liste entfernen; HAL-Datei bleibt.
- `GET /clipboard/items/{id}/download` → Datei aus HAL Inbox herunterladen.
- `GET /clipboard/items/{id}/preview` → gleiche Datei für Vorschau laden.
- `GET /clipboard/settings` → Inbox-Pfad, Upload-Limit, erlaubte Extensions.

### Entscheidungen / Verhalten
- Dateiablage ist ausschließlich der HAL Inbox (`clipboard_inbox_dir`, Default `/home/dev/tools/Hal/00 Inbox/Clipboard`); kein MinIO und kein zweiter App-Storage.
- Der SQLite-Eintrag entsteht erst nach erfolgreichem Schreiben von Rohdatei und Sidecar. Bei Upload-/Größenfehlern bleibt kein aktives Item zurück.
- Entfernen setzt den Status auf `removed_from_clipboard`; Download/Preview bleiben über ID möglich, weil die HAL-Datei bewusst erhalten bleibt.
- `source_device` ist best-effort; unbekannte Werte werden zu `unknown` normalisiert.
- Auth-Gate ist identisch zu den anderen geschützten Jupiter-Routen.

### Verifikation
- `python -m pytest backend/tests/test_proj69_clipboard.py -q` → **7 passed**
- `python -m pytest backend/tests/test_proj11_files.py backend/tests/test_proj41_video_summary.py backend/tests/test_proj53_book_nuggets.py backend/tests/test_proj40_microapps.py -q` → **80 passed**
- `conda run -n Dashboard ...` konnte nicht verwendet werden, weil `conda` in dieser Shell nicht verfügbar ist.

## Implementation Notes (Frontend — /abc-frontend, 2026-07-08)

**Branch:** `dev`. Native Next.js-Micro-App umgesetzt; Backend war bereits vorhanden.

### Neue/geänderte Dateien
- `nextjs_app/components/microapps/clipboard/clipboard-app.tsx` — native Clipboard-App mit Dropzone, Datei-Auswahl, Paste-Handler, aktiver Liste, Vorschau-Dialog, Download, Bild-in-Zwischenablage, Web-Share/Download-Fallback, Bearbeiten und Entfernen.
- `nextjs_app/lib/types.ts` — Clipboard-Typen (`ClipboardItem`, Liste, Settings, Source-Methode/Gerät).
- `nextjs_app/lib/api.ts` — Client-Funktionen für `/clipboard/items`, Upload, Patch, Delete, Blob-Preview/Download und Download-Helfer.
- `nextjs_app/lib/microapps-registry.ts` — `clipboard` als Lazy-loaded native Micro-App registriert.
- `backend/config/engines.example.yaml` — getrackter Registry-Beispieleintrag für `clipboard`.
- `backend/config/engines.yaml` — lokaler, gitignored Eintrag ergänzt, damit die App im laufenden Jupiter sichtbar ist.

### UI-Verhalten
- Drag&Drop nutzt `source_method=drag_drop`; Datei-Auswahl nutzt `upload`; Clipboard-Paste nutzt `paste`.
- `source_device` wird best-effort aus Browser/Plattform erkannt (`pc`, `mac`, `ipad`, `iphone`, sonst `unknown`).
- Die Liste pollt alle 5 Sekunden und aktualisiert sofort nach Upload/Remove/Edit.
- Bild- und PDF-Vorschau laden authentifiziert über `/clipboard/items/{id}/preview` als Blob/Object-URL.
- Bild-Kopieren nutzt die Browser Clipboard API, wenn verfügbar; sonst zeigt die UI eine deutsche Fehlermeldung.
- Teilen nutzt Web Share API, wenn verfügbar; sonst fällt die Aktion auf Download zurück.
- Entfernen löscht nur aus der aktiven Liste; die HAL-Datei bleibt erhalten.

### Verifikation
- `npm run lint -- components/microapps/clipboard/clipboard-app.tsx lib/api.ts lib/types.ts lib/microapps-registry.ts` → **0 Fehler**
- `npx tsc --noEmit` → bricht an einem vorbestehenden Fehler in `lib/md-tree.test.ts:118` ab; keine PROJ-69-Datei wurde als Fehler gemeldet.

---

## QA Test Results

**Tested:** 2026-07-08
**Backend:** eigene Instanz auf `127.0.0.1:8124` (FastAPI, env `Dashboard`, isolierter tmp-Vault/DB — die echte `jupiter-backend`-systemd-Instanz auf Port 8000 lief noch mit altem Code vor diesem Feature und wurde NICHT neu gestartet, um den laufenden Dev-Betrieb nicht zu stören)
**Frontend:** Code-Review + `npm run lint`/`tsc` (kein Browser-Lauf in dieser Session — siehe Hinweis unten)
**Tester:** QA Engineer (AI)

### Vorgehen
`conda`/`pytest` liefen über `source ~/miniconda3/etc/profile.d/conda.sh && conda activate Dashboard` (bare `conda run` scheiterte an fehlendem PATH-Eintrag in dieser Shell). Backend-Regressionssuite komplett ausgeführt (1165 Tests), zusätzlich eine isolierte zweite Uvicorn-Instanz mit `JUPITER_VAULT_ROOT`/`JUPITER_CLIPBOARD_*`/`JUPITER_SESSION_INDEX_DB_PATH` auf `/tmp` gestartet, um die API-Vertrag-Kette (Upload → Liste → Preview → Download → Patch → Delete) end-to-end per `curl` gegen echten FastAPI-Code zu fahren, ohne den produktiven Hal-Vault oder die echte Nutzer-DB zu berühren.

### Acceptance Criteria Status

#### AC-1 bis AC-3: Native Micro-App, Registry, Tailscale-Erreichbarkeit
- [x] `clipboard` als `kind: native`/`group: micro` in `engines.example.yaml` + lokaler `engines.yaml`; React-Komponente lazy in `microapps-registry.ts` registriert — kein iFrame.
- [ ] Tailscale-Erreichbarkeit selbst NICHT geprüft (kein Tailscale-Client in dieser Session verfügbar) — strukturell unverändert zu den bereits deployten nativen Micro-Apps (PROJ-40/41/53), daher geringes Risiko, aber offen.

#### AC-4/AC-5: Chronologische Liste + Metadatenfelder
- [x] SQL `ORDER BY created_at DESC, id DESC` — neueste zuerst, deterministisch bei gleichem Zeitstempel.
- [x] Name, MIME/Extension, Quelle, Zeitpunkt, Größe werden angezeigt (per `curl`-Antwort + Komponenten-Review verifiziert).
- [ ] **BUG-3 (Low):** `status` wird in der aktiven Liste NICHT angezeigt (weder Text noch Badge) — siehe BUG-3.

#### AC-6/AC-7: Drag&Drop / Paste
- [x] Drag&Drop akzeptiert Bild/PDF/Dokument innerhalb Größenlimit (`source_method=drag_drop` per curl verifiziert, Frontend-Handler vorhanden).
- [x] Paste-Handler vorhanden (`onPaste` liest `e.clipboardData.files`); Browser-Fähigkeit selbst nicht in echtem Browser getestet.

#### AC-8: Mobile/iOS Upload-Pfad
- [x] Datei-Auswahl-Fallback vorhanden und funktional (API-seitig identisch zum Desktop-Upload-Pfad); kein echtes iOS-Gerät in dieser Session verfügbar.

#### AC-9: Sofortige Sichtbarkeit nach Upload
- [x] UI ruft `refresh()` direkt nach Upload auf; zusätzlich 5s-Polling.

#### AC-10/AC-11: HAL-Inbox-Kopie + Metadatenkontext
- [x] Rohdatei + Sidecar-`.md` werden atomar in den konfigurierten Inbox-Ordner geschrieben (per curl verifiziert: Datei-Bytes identisch, Sidecar enthält `created_at`, `source_method`, `source_device`, `original_filename`, `mime_type`, `size_bytes`, `hal_inbox_path`).

#### AC-12/AC-13: Vorschau + Download
- [x] `/preview` und `/download` liefern die Datei; Bild-Bytes stimmen exakt mit dem Upload überein.

#### AC-14: Copy-to-Clipboard für Bilder
- [x] Implementiert über `navigator.clipboard.write` mit `ClipboardItem`; deutsche Fehlermeldung bei fehlender Browser-Unterstützung. Nicht in echtem Browser gegengeprüft.

#### AC-15: iOS Teilen/Öffnen
- [x] Web-Share-API mit Download-Fallback implementiert; nicht auf echtem iOS-Gerät geprüft.

#### AC-16/AC-17: Entfernen ohne HAL-Löschung
- [x] `DELETE /clipboard/items/{id}` setzt `status=removed_from_clipboard`; Liste danach leer; Datei bleibt unter derselben ID downloadbar (per curl verifiziert).

#### AC-18: Upload-Fehler ohne irreführenden aktiven Eintrag
- [x] Ungültiger `source_method` → 400 mit deutscher Meldung, kein Listen-Eintrag.
- [x] Zu große Datei → `ValueError`, kein aktives Item, keine Datei bleibt liegen (per pytest `test_service_rejects_too_large_without_leaving_active_item` verifiziert).
- [x] **BUG-1 gefixt (siehe „Fix-Verifikation" unten):** Namenskollision erzeugt jetzt sofort einen unterscheidbaren zweiten Eintrag statt eines Prozess-Hängers.

#### AC-19: Nicht unterstützte Dateitypen konsistent behandelt
- [x] `_check_extension` weist nicht erlaubte Extensions mit deutscher Meldung ab (`"Dateityp '.exe' ist nicht erlaubt."`, per curl verifiziert).

#### AC-20: Persistenz über Reload/Neustart
- [x] `test_repository_persists_across_service_restart` (pytest) + eigener Restart-Test einer zweiten `ClipboardService`-Instanz auf derselben SQLite-Datei bestätigen Persistenz.

#### AC-21: Deutsche Texte
- [x] Alle geprüften UI-Texte und Backend-Fehlermeldungen sind deutsch; App-Name „Clipboard" bleibt.

### Edge Cases Status

#### EC „Doppelter Upload derselben Datei"
- [x] **Gefixt:** Zwei Uploads derselben Datei innerhalb derselben Sekunde erzeugen jetzt zwei unterscheidbare aktive Einträge (`…testshot.png`, `…testshot-1.png`, …) statt eines Prozess-Hängers. Siehe „Fix-Verifikation" am Ende dieses Abschnitts.

#### EC „Sehr große Datei"
- [x] Wird sauber mit `ValueError`/400 abgelehnt, kein halbes Item.

#### EC „Dateiname fehlt"
- [x] Erzeugt stabilen Fallback-Namen aus Zeitstempel + Extension (per eigenem Repro-Skript verifiziert: `clip-20260708-170332.png`).

#### EC „Unbekannter MIME-Type"
- [x] Fällt auf generische Datei-Ansicht zurück (Frontend `itemIcon`/Preview-`kind: "file"`).

#### EC „HAL-Kopie schlägt fehl"
- [x] `_write_stream`/`add_upload` löschen bei Exception sowohl Datei als auch Sidecar wieder (`except BaseException` Cleanup-Block) — kein aktives Item ohne HAL-Persistenz.

#### EC „Backend-Neustart während Upload"
- [x] Größtenteils erfüllt: DB-Eintrag entsteht erst nach vollständigem Schreiben von Datei+Sidecar, daher kein "kaputtes" aktives Item nach hartem Kill.
- [ ] **BUG-4 (Low):** Ein harter Prozess-Kill mitten im `_write_stream`-Schreiben lässt eine verwaiste `*.tmp`-Datei im HAL-Inbox-Ordner zurück (kein Cleanup ohne Exception-Pfad). Kosmetisch, kein Datenverlust, aber Sammelmüll im Vault.

#### EC „Sektion Micro-Apps ausgeblendet → Direkt-URL erreichbar"
- [x] Nicht PROJ-69-spezifisch, folgt dem bereits etablierten nativen Micro-App-Routing (PROJ-40) — nicht erneut einzeln getestet.

### Security Audit Results
- [x] Authentication: `/clipboard/*` hängt am globalen `auth_gate` (`Depends(get_current_user)`); ohne Token + bestehende Nutzerbasis → 401 (per curl gegen die echte Instanz auf Port 8123 verifiziert).
- [x] Pfad-Traversal: `_clean_name` nutzt `os.path.basename` (entfernt `../`-Anteile); `resolve_file` prüft `os.path.realpath` gegen den Inbox-Root, bevor die Datei ausgeliefert wird.
- [x] Kein Zugriff außerhalb der Inbox: `_inbox_dir()` verweigert Start, wenn `clipboard_inbox_dir` außerhalb `vault_root`/`allowed_roots` liegt.
- [x] Input-Validierung: `ClipboardItemUpdate` begrenzt `display_name`/`notes` per Pydantic (`max_length`).
- [ ] **BUG-1 (Critical) ist zugleich ein Verfügbarkeits-/DoS-Befund:** Da Uvicorn hier als einzelner Worker/Event-Loop läuft (wie auch der reale `jupiter-backend`-systemd-Dienst), legt ein einziger, unauffälliger Request den GESAMTEN Jupiter-Prozess lahm — nicht nur Clipboard, sondern auch Auth, alle anderen Micro-Apps, alles. Kein Rate-Limiting oder Timeout schützt davor.

### Bugs Found

#### BUG-1: Endlosschleife bei Datei-Namenskollision hängt den gesamten Backend-Prozess auf — GEFIXT (2026-07-08)
- **Severity:** Critical
- **Steps to Reproduce:**
  1. Lade eine Datei mit `source_method=drag_drop`, `source_device=pc`, Dateiname `testshot.png` hoch (`POST /clipboard/items`).
  2. Lade **innerhalb derselben Sekunde** dieselbe Datei mit demselben Namen erneut hoch.
  3. Erwartet: laut Edge-Case-Spec „Doppelter Upload derselben Datei" — beide Einträge werden als separate, per Zeitstempel/Name unterscheidbare Items angelegt.
  4. Tatsächlich: Der zweite Request kehrt nie zurück. `py-spy dump` zeigt den Hauptthread dauerhaft (100 % CPU) in `ClipboardService._target_paths` (`backend/app/engine/clipboard.py:210`), in einer Endlosschleife. **Der komplette Uvicorn-Prozess wird dadurch für alle Requests (auch andere Micro-Apps) unerreichbar**, bis er extern gekillt wird.
- **Root Cause:** In `_target_paths` prüft die Kollisions-Schleife
  ```python
  while os.path.exists(file_path) or os.path.exists(os.path.join(inbox, f"{stem}.md")):
      filename = f"{stem}-{i}{ext}"
      file_path = os.path.join(inbox, filename)
      i += 1
  ```
  den zweiten Teil der Bedingung IMMER gegen den unveränderten Basis-`stem` (`f"{stem}.md"`), nicht gegen den gerade erzeugten Kandidaten (`f"{stem}-{i}.md"`). Existiert das Sidecar der Basis-Variante bereits (weil der erste Upload sie gerade angelegt hat), ist diese Teilbedingung für immer `True` — die Schleife kann nie terminieren, unabhängig davon, wie viele `-1`, `-2`, … Varianten von `file_path` bereits frei wären. Da `_target_paths`/`_write_stream` synchroner Code ohne `await`-Punkt sind, blockiert das den einzigen Event-Loop-Thread komplett (bestätigt per `py-spy dump`: State `R`, 96 % CPU, alle anderen Requests liefen in Timeout).
- **Fix (umgesetzt):** `_target_paths` in `backend/app/engine/clipboard.py` prüft jetzt pro Schleifendurchlauf den jeweils aktuellen Kandidaten-Stem (Datei UND `.md`), statt den zweiten Teil der Bedingung dauerhaft gegen den unveränderten Basis-Stem zu prüfen. Jeder Kandidat (`base_stem`, `base_stem-1`, `base_stem-2`, …) wird nur einmal geprüft, die Schleife terminiert garantiert nach endlich vielen bereits belegten Namen.
- **Priority:** Fix before deployment → **erledigt**.
- **Fix-Verifikation:**
  - Neuer Regressionstest `test_service_duplicate_filename_within_same_second_creates_distinct_items` (mit `SIGALRM`-Timeout-Guard, damit ein Rückfall den Test hart fehlschlagen lässt statt die Suite aufzuhängen) — **PASSED**.
  - Eigenständiges Repro-Skript: 5 aufeinanderfolgende Uploads derselben Datei (`testshot.png`) innerhalb derselben Sekunde erzeugen sofort `…testshot.png`, `…testshot-1.png`, `…testshot-2.png`, `…testshot-3.png`, `…testshot-4.png` — kein Hänger, jeweils < 1s.
  - Volle Backend-Regressionssuite danach erneut ausgeführt: **1165 passed**, 1 unveränderter, PROJ-69-unabhängiger Fehler (`test_proj50_codex_abc.py::test_generator_check_passes_no_drift`, Codex-Skill-Drift, nicht Teil dieses Features).

#### BUG-2: Kein Test deckt den Namenskollisions-Fall ab — GEFIXT (2026-07-08)
- **Severity:** High (Testabdeckungslücke, die BUG-1 durch die komplette Suite schlüpfen ließ)
- **Beschreibung:** `backend/tests/test_proj69_clipboard.py` verwendete in allen 7 Tests durchgehend unterschiedliche Dateinamen/Device-Kombinationen. Der im Spec explizit als Edge Case benannte Fall „Doppelter Upload derselben Datei" hatte keinen Test — genau dieser Fall triggerte BUG-1.
- **Fix (umgesetzt):** Neuer Test `test_service_duplicate_filename_within_same_second_creates_distinct_items` deckt exakt diesen Fall ab (zwei Uploads derselben Datei ohne Zeitversatz → zwei distinkte aktive Items, distinkte HAL-Pfade, Timeout-Guard gegen erneute Endlosschleifen).
- **Priority:** Fix before deployment → **erledigt**.

#### BUG-3: Item-Status wird in der aktiven Liste nicht angezeigt
- **Severity:** Low
- **Steps to Reproduce:**
  1. Clipboard-App öffnen, ein Item hochladen.
  2. Erwartet laut AC: „Die Liste zeigt pro Item mindestens: … Status."
  3. Tatsächlich: `clipboard-app.tsx` rendert `mime_type`, Größe, Quelle, Gerät, Zeitpunkt — aber kein `status`-Feld (weder Text noch Badge).
- **Anmerkung:** Da die aktive Liste serverseitig ohnehin nur `active`-Items liefert, ist der praktische Impact gering (Status variiert in der Liste nie sichtbar), das AC ist aber wörtlich nicht erfüllt.
- **Priority:** Nice to have.

#### BUG-4: Verwaiste `*.tmp`-Datei bei hartem Prozess-Kill während des Schreibens
- **Severity:** Low
- **Beschreibung:** `_write_stream` räumt die temporäre Datei nur im `except`-Pfad auf. Ein harter Kill (z. B. `SIGKILL`, Server-Crash) mitten im Schreiben hinterlässt eine `*.tmp`-Leiche im HAL-Inbox-Ordner ohne zugehörigen DB-Eintrag. Kein Datenverlust, aber Sammelmüll, den niemand aufräumt.
- **Priority:** Nice to have.

### Summary
- **Acceptance Criteria:** 18/21 klar bestanden (inkl. BUG-1-betroffenem AC-18, jetzt gefixt), 1 nicht erfüllt (BUG-3), 2 nicht testbar in dieser Umgebung (Tailscale-Erreichbarkeit, echtes iOS-Gerät — strukturell aber unverändert zu bereits deployten nativen Micro-Apps).
- **Bugs Found:** 4 total (1 Critical — gefixt, 1 High — gefixt, 2 Low — offen).
- **Security:** Auth-Gate, Pfad-Traversal-Schutz und Inbox-Root-Eingrenzung bestehen. Der kritische Verfügbarkeits-/DoS-Befund aus BUG-1 (kompletter Prozess-Hänger durch simplen doppelten Upload) ist behoben und per Regressionstest + Repro-Skript verifiziert.
- **Production Ready:** YES (User-Entscheidung 2026-07-08: auf **Approved** gesetzt) — BUG-1/BUG-2 sind gefixt und verifiziert, keine Critical/High-Bugs mehr offen. BUG-3/BUG-4 (Low) bleiben bewusst offen und blockieren laut Schweregrad-Konvention keine Freigabe.
- **Recommendation:** BUG-3 (Status-Anzeige in der Liste) und BUG-4 (verwaiste `.tmp`-Datei bei Hard-Kill) vor oder kurz nach dem Deploy nachziehen. Browser-/Geräte-Tests (Tailscale, iOS, Responsive-Breakpoints, Web-Share/Clipboard-API in echtem Chrome/Safari) wurden in dieser Session nicht durchgeführt — vor dem ersten echten Multi-Geräte-Einsatz `/abc-qa-e2e` oder einen manuellen Durchlauf nachholen.
