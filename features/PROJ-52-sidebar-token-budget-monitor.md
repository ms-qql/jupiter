# PROJ-52: Sidebar Token-Budget-Monitor für Claude und Codex

## Status: Deployed
**Created:** 2026-06-27
**Last Updated:** 2026-06-28

## Dependencies
- Requires: PROJ-3 (Cockpit + Sidebar) — Anzeige sitzt unten in der persistenten Sidebar.
- Requires: PROJ-19 (Token-/Kosten-Dashboard) — vorhandene Usage-Modelle und Anzeige-Konventionen werden wiederverwendet.
- Requires: PROJ-48 (OpenAI Codex CLI als Engine) — Codex muss als Engine/Provider im System bekannt sein.
- Requires: PROJ-51 (Engine- und Modellverwaltung) — Claude/Codex-Provider und deren Verfügbarkeit kommen aus der Engine-Konfiguration.

## Beschreibung
Oben in der Jupiter-Sidebar soll ein kompakter **Token-Budget-Monitor** anzeigen, wie viel der providerseitigen Nutzungskontingente für **Claude** und **Codex** bereits verbraucht ist. Pro Provider werden zwei Zeitfenster sichtbar:

- **5h-Session**: Verbrauch in Prozent und Zeitpunkt des nächsten Resets.
- **Woche**: Verbrauch in Prozent und Zeitpunkt des nächsten Resets.

Die Anzeige aktualisiert sich automatisch in regelmäßigen Abständen, initial vorgeschlagen alle **30 Minuten**, und kann manuell neu geladen werden. Ziel ist ein schnelles Lagebild vor dem Start neuer Sessions: „Kann ich noch arbeiten oder nähere ich mich dem Limit?“

Wichtig: Die Anzeige darf keine falsche Präzision vortäuschen. Wenn Claude oder Codex den exakten Verbrauch bzw. Reset-Zeitpunkt nicht maschinenlesbar liefern, zeigt Jupiter einen klar gekennzeichneten Schätzwert oder „nicht verfügbar“ statt erfundener Prozentwerte.

## User Stories
- Als Nutzer möchte ich unten in der Sidebar sehen, wie viel meines **Claude-5h-Kontingents** und **Claude-Wochenkontingents** verbraucht ist, damit ich neue Claude-Sessions bewusst starten kann.
- Als Nutzer möchte ich dieselbe Information für **Codex** sehen, damit ich zwischen Engines wechseln kann, bevor ein Provider knapp wird.
- Als Nutzer möchte ich sehen, **wann** die 5h- und Wochenfenster jeweils zurückgesetzt werden, damit ich Wartezeiten einschätzen kann.
- Als Nutzer möchte ich, dass die Anzeige automatisch aktualisiert wird, ohne die Seite neu zu laden.
- Als Nutzer möchte ich manuell aktualisieren können, wenn ich gerade außerhalb von Jupiter Tokens verbraucht habe.
- Als Nutzer möchte ich klar erkennen, wenn ein Wert geschätzt oder nicht verfügbar ist, statt falsche Sicherheit zu bekommen.

## Acceptance Criteria
- [ ] Die Sidebar enthält unten im Footer-Bereich eine kompakte Anzeige **„Budget“** oder gleichwertig.
- [ ] Claude- und Codex-Verbrauch können über das bestehende Sidebar-Konfig-Panel einzeln ein- und ausgeblendet werden.
- [ ] Die Anzeige enthält mindestens zwei Provider-Zeilen: **Claude** und **Codex**.
- [ ] Pro Provider werden zwei Fenster angezeigt: **5h** und **Woche**.
- [ ] Pro Fenster zeigt die UI:
  - Verbrauch in Prozent (`0–100%`, bei Überziehung auch `>100%` möglich),
  - visuelle Füllstandsanzeige oder Statusfarbe,
  - Reset-Zeitpunkt als relative Zeit und/oder konkrete Uhrzeit,
  - Datenqualität: `live`, `geschätzt` oder `n/v`.
- [ ] Die Anzeige lädt beim Öffnen der App automatisch.
- [ ] Die Anzeige aktualisiert sich automatisch mindestens alle **30 Minuten**; das Intervall ist konfigurierbar, Default = 30 Minuten.
- [ ] Es gibt eine manuelle Aktualisieren-Aktion, z. B. Icon-Button mit Tooltip **„Budget aktualisieren“**.
- [ ] Während einer Aktualisierung bleibt der zuletzt bekannte Wert sichtbar; die UI zeigt einen dezenten Ladezustand statt zu flackern.
- [ ] Bei Fehlern zeigt die UI eine deutsche Kurzmeldung, z. B. **„Budget gerade nicht abrufbar“**, und behält den letzten erfolgreichen Stand, wenn vorhanden.
- [ ] Wenn ein Provider deaktiviert oder nicht verfügbar ist, zeigt die Anzeige diesen Provider als **„nicht verfügbar“** und startet keine unnötigen Abrufe.
- [ ] Wenn der Reset-Zeitpunkt überschritten ist, aber noch keine neuen Provider-Daten vorliegen, markiert die UI den Wert als **veraltet** und löst spätestens beim nächsten Intervall einen Refresh aus.
- [ ] Die Anzeige passt in die 72er Sidebar-Breite, verursacht kein horizontales Scrollen und bleibt auf Mobile im Sidebar-Drawer nutzbar.
- [ ] Alle sichtbaren Texte sind Deutsch.

## Datenqualität / Quellenregeln
- [ ] **Live-Wert bevorzugt:** Wenn Claude/Codex CLI, Provider-API oder lokale Statusdateien exakte Budgetdaten liefern, nutzt Jupiter diese als `source=live`.
- [ ] **Schätzung erlaubt, aber markiert:** Wenn nur lokale Session-Usage vorliegt, darf Jupiter den Verbrauch aus bekannten Tokens und konfigurierten Kontingenten schätzen; die UI zeigt dann `geschätzt`.
- [ ] **Keine erfundenen Limits:** Wenn weder live Daten noch konfigurierte Quoten vorhanden sind, zeigt Jupiter `n/v`.
- [ ] **Separate Fenster:** 5h- und Wochenfenster werden getrennt berechnet; ein Reset des 5h-Fensters darf das Wochenfenster nicht zurücksetzen.
- [ ] **Providerunterschiede:** Claude und Codex dürfen unterschiedliche Quellen, Fensterstarts, Reset-Logik und Quoten haben.

## Edge Cases
- **Provider liefert keine Budgetdaten** → UI zeigt `n/v` und einen kurzen Tooltip, keine roten Fehlerzustände.
- **CLI nicht installiert / nicht eingeloggt** → Provider-Zeile zeigt „nicht verfügbar“ mit Setup-Hinweis; andere Provider funktionieren weiter.
- **Abruf dauert lange** → Timeout; letzter Stand bleibt sichtbar, nächster Intervall versucht erneut.
- **Verbrauch außerhalb von Jupiter** → manueller Refresh kann die Anzeige aktualisieren; falls nur Schätzung aus Jupiter-Daten möglich ist, bleibt der Wert als `geschätzt` markiert.
- **Systemuhr / Zeitzone** → Resetzeiten werden intern in UTC gespeichert und in lokaler UI-Zeit angezeigt.
- **Fenstergrenze während geöffnetem UI** → Anzeige zählt die relative Restzeit herunter bzw. aktualisiert beim nächsten Intervall; keine negative Restzeit.
- **Wert > 100%** → UI zeigt `>100%` bzw. den echten Prozentwert und markiert das Fenster kritisch, statt bei 100% abzuschneiden.
- **Mehrere Browser-Tabs** → jeder Tab darf lesen; Backend sollte Abrufe cachen, damit nicht jeder Tab Provider-CLIs parallel triggert.
- **Provider-Format ändert sich** → Parser-Fehler wird als `n/v`/Fehler für diesen Provider behandelt; die Sidebar bleibt bedienbar.

## Technical Requirements (optional)
- Backend sollte einen read-only Endpoint bereitstellen, z. B. `GET /usage/provider-budgets`, der Claude/Codex-Budgetdaten normalisiert zurückgibt.
- Antwortmodell sollte pro Provider/Fenster mindestens enthalten: `provider`, `window`, `used_pct`, `used_tokens?`, `limit_tokens?`, `reset_at?`, `quality`, `source`, `updated_at`, `error?`.
- Provider-Abrufe sollten serverseitig gecacht werden; Default-TTL passend zum UI-Intervall (30 Minuten), manueller Refresh optional per `force=true` mit Rate-Limit.
- Provider-spezifische Adapter sollten getrennt sein, damit Claude- und Codex-Quellen unabhängig ausfallen können.
- Frontend sollte die Anzeige als eigene Sidebar-Komponente bauen, z. B. `ProviderBudgetWidget`, ohne das bestehende Session-Polling alle 4 Sekunden zu belasten.
- Die Komponente darf die bestehende `UsageDashboard`-Logik nicht ersetzen; sie ist ein **Quota-Lagebild**, während PROJ-19 historische Verbrauchsanalyse bleibt.

## Non-Goals
- Keine exakte Abrechnung oder Provider-Billing-Seite.
- Keine automatische Engine-Umschaltung, wenn ein Budget knapp wird.
- Keine Benachrichtigungen außerhalb der App.
- Keine Speicherung von Provider-Secrets in Jupiter.
- Keine Garantie, dass providerseitige Limits korrekt angezeigt werden, wenn der Provider keine maschinenlesbaren Daten bereitstellt.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-27 · **Stack:** Next.js Sidebar + FastAPI Usage-Service + In-Memory Provider-Cache · **Branch:** dev

### Überblick / Kernaussage
PROJ-52 ergänzt Jupiter um ein kleines, dauerhaft sichtbares **Quota-Lagebild** unten in der Sidebar. Es ist bewusst **nicht** das bestehende PROJ-19-Verbrauchsdashboard: PROJ-19 beantwortet „Was haben meine Jupiter-Sessions verbraucht?“, PROJ-52 beantwortet „Wie voll sind meine providerseitigen Claude-/Codex-Fenster gerade?“.

Die Architektur trennt deshalb drei Ebenen:

1. **Provider-Budget-Snapshot** im Backend: Claude und Codex werden über getrennte Adapter abgefragt bzw. degradieren sauber zu Schätzung/`n/v`.
2. **Normalisierte Usage-API** unter `/usage/provider-budgets`: ein einheitliches Antwortformat für Sidebar und spätere Widgets.
3. **Sidebar-Widget** im bestehenden `SessionRail`: kompakte Anzeige im Sidebar-Footer, mit automatischem 30-Minuten-Refresh, manuellem Refresh und Provider-Sichtbarkeit über das Sidebar-Konfig-Panel.

Wichtigste Produktentscheidung: **Keine falsche Genauigkeit.** Wenn Claude/Codex keine maschinenlesbaren 5h-/Wochen-Budgetdaten liefern, zeigt Jupiter `n/v` oder ausdrücklich `geschätzt`, nicht erfundene Prozentwerte.

### A) Komponenten-Struktur
```
SessionRail
├── RailHeader (Jupiter + Neue Session)
├── ProviderBudgetWidget
│   ├── Header ("Budget" + Aktualisieren-Button + letzter Stand)
│   ├── ProviderBudgetRow: Claude
│   │   ├── BudgetWindowPill: 5h
│   │   └── BudgetWindowPill: Woche
│   ├── ProviderBudgetRow: Codex
│   │   ├── BudgetWindowPill: 5h
│   │   └── BudgetWindowPill: Woche
│   └── CompactErrorState / UnavailableState
├── Workspace-Links
├── Orchestration / Micro-Apps
└── Sessions-Liste
```

**Platzierung:** Unten im Sidebar-Footer. Damit bleibt der Monitor dauerhaft erreichbar, ohne Workspace-, Orchestration-, Micro-App- oder Session-Navigation nach unten zu drücken.

**Darstellung:** Pro Provider eine schmale Zeile mit zwei kompakten Fenster-Chips (`5h`, `Woche`). Jeder Chip zeigt Prozent, kleine Füllstandslinie/Farbe und Reset-Kurztext. Tooltips erklären Quelle und Datenqualität (`live`, `geschätzt`, `n/v`, `veraltet`).

**Mobile:** Dieselbe Komponente erscheint im bestehenden Sidebar-Drawer. Sie bleibt kompakt; keine separate Mobile-Topbar-Anzeige in diesem Feature.

### B) Datenmodell (Klartext)
Es wird **keine neue persistente Tabelle** angelegt. Die Daten sind ein flüchtiger Lagebild-Snapshot:

Ein **Provider-Budget** enthält:
- Provider-Key: `claude` oder `codex`
- Anzeigename: „Claude“ / „Codex“
- Verfügbarkeit: verfügbar, deaktiviert, CLI fehlt, nicht eingeloggt, Daten nicht abrufbar
- Zwei Fenster: `5h` und `week`

Ein **Budget-Fenster** enthält:
- Verbrauch in Prozent, falls bekannt
- optional bekannte Tokens: verbraucht / Limit
- Reset-Zeitpunkt, falls bekannt
- Datenqualität: `live`, `estimated`, `unavailable`, `stale`
- Quelle: z. B. CLI/API/Statusdatei, lokale Jupiter-Usage, Konfiguration
- Zeitpunkt des letzten erfolgreichen Updates
- optionale deutsche Kurzmeldung

**Speicherung:** Backend hält den letzten Snapshot in-memory mit TTL. Das reicht, weil Budgetdaten extern/providerseitig sind und jederzeit neu abgefragt werden können. Kein MinIO, kein Vault, kein SQLite-Schema.

### C) API-Shape
Neue read-only Usage-Endpunkte:

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/usage/provider-budgets` | Liefert den gecachten Budget-Snapshot für Claude und Codex. |
| POST | `/usage/provider-budgets/refresh` | Erzwingt eine Aktualisierung, rate-limited und weiterhin gecacht. |

Alternativ kann der manuelle Refresh als `GET /usage/provider-budgets?force=true` gebaut werden. Bevorzugt ist aber ein separater POST, weil ein erzwungener Provider-Abruf Seiteneffekt-Charakter hat.

Antwortstruktur in Klartext:
- `updated_at`: Zeitpunkt des Snapshots
- `ttl_seconds`: wie lange der Snapshot frisch ist
- `providers[]`: Claude/Codex mit Verfügbarkeit und Fenstern
- `warnings[]`: nicht-blockierende Hinweise, z. B. „Codex-Budgetdaten nicht maschinenlesbar“

Die Endpunkte hängen am bestehenden geschützten `/usage`-Router und nutzen dieselbe Auth-Grenze wie das Verbrauchsdashboard.

### D) Provider-Adapter
Backend bekommt eine kleine Adapter-Schicht:

```
ProviderBudgetService
├── SnapshotCache (TTL, letzter erfolgreicher Stand)
├── ClaudeBudgetAdapter
├── CodexBudgetAdapter
└── LocalUsageEstimator
```

**ClaudeBudgetAdapter:** Prüft zuerst, ob eine maschinenlesbare Claude-Quelle verfügbar ist. Falls nicht, liefert er `unavailable` oder delegiert an den Estimator, wenn konfigurierte Quoten vorhanden sind.

**CodexBudgetAdapter:** Prüft analog Codex. Codex ist bereits als `generic_cli`-Engine mit `usage`-Capability registriert; das hilft für lokale Verbrauchsschätzung, ersetzt aber keine providerseitige Quota-Quelle.

**LocalUsageEstimator:** Nutzt vorhandene Jupiter-Usage-Daten aus dem Session-Index, gruppiert nach Engine (`claude`, `codex`) und Zeitfenster. Er darf nur dann Prozentwerte liefern, wenn ein konfiguriertes Quota-Limit existiert. Ohne Limit zeigt die UI `n/v`.

### E) Refresh- und Cache-Verhalten
- Default-Intervall: **30 Minuten**.
- Backend-TTL: ebenfalls 30 Minuten, konfigurierbar.
- Sidebar lädt beim Mount einmal.
- Danach pollt nur das Budget-Widget im 30-Minuten-Takt; es nutzt **nicht** den bestehenden 4-Sekunden-Session-Poll.
- Manueller Refresh triggert den POST-Endpunkt, aber mit Rate-Limit, damit mehrere Tabs nicht mehrere Provider-CLIs parallel starten.
- Während Refresh bleibt der letzte Stand sichtbar.
- Wenn ein Reset-Zeitpunkt überschritten ist und der Snapshot noch alt ist, markiert die UI das Fenster als `veraltet` und fordert beim nächsten Abruf neue Daten an.

### F) Tech-Entscheidungen (Warum)
- **Eigener `/usage/provider-budgets`-Pfad statt Erweiterung von `/usage/summary`:** Historische Session-Usage und Provider-Quota sind unterschiedliche Konzepte. Eine Trennung verhindert falsche Vermischung und hält PROJ-19 stabil.
- **In-Memory-Cache statt DB:** Budgetdaten sind externe Momentaufnahmen. Persistenz würde keinen Mehrwert liefern und könnte sogar veraltete Quota-Stände autoritativ wirken lassen.
- **Provider-Adapter getrennt:** Claude und Codex werden unterschiedlich authentifiziert und können unterschiedliche Quellformate haben. Ein Adapter-Ausfall darf den anderen Provider nicht beschädigen.
- **Schätzung nur mit Konfiguration:** Jupiter kennt lokale Tokens, aber nicht automatisch das echte Anbieterlimit. Prozentwerte aus lokalen Tokens sind nur seriös, wenn ein Limit explizit konfiguriert ist.
- **Sidebar-eigener Poll:** Das Budget ändert sich langsam. 30 Minuten reichen und vermeiden unnötige CLI-/API-Aufrufe.
- **Auth geschützt:** Budgets sind Account-/Subscription-bezogen. Der Endpoint bleibt hinter JWT wie die übrigen Cockpit-Daten.

### G) Konfiguration
Neue Settings-Felder, alle optional und mit konservativen Defaults:
- `provider_budget_refresh_minutes` — Default 30.
- `provider_budget_timeout_seconds` — kurzer Abruf-Timeout pro Adapter.
- `provider_budget_force_refresh_min_seconds` — Rate-Limit für manuelle Refreshes.
- optionale Quoten pro Provider/Fenster, z. B. Claude 5h/Woche und Codex 5h/Woche, falls live Quellen fehlen.

Ohne Quoten liefert der Estimator keine Prozentwerte, sondern `n/v`.

### H) Frontend-Datenfluss
```
ProviderBudgetWidget mount
  → GET /usage/provider-budgets
  → Provider-Zeilen rendern
  → alle 30 Minuten erneut GET
  → Klick "Aktualisieren"
      → POST /usage/provider-budgets/refresh
      → Widget mit neuem Snapshot ersetzen
```

Fehlerstrategie:
- Erstladung fehlgeschlagen: kompakte Meldung „Budget gerade nicht abrufbar“.
- Späterer Refresh fehlgeschlagen: alter Stand bleibt sichtbar, Hinweis „Aktualisierung fehlgeschlagen“.
- Provider deaktiviert/nicht verfügbar: Provider-Zeile bleibt sichtbar, aber ausgegraut.

### I) Dependencies
**Backend:** keine neuen Pflichtpakete. Es reicht FastAPI, vorhandene Settings, Engine-Registry und Session-Index. Falls später eine offizielle Provider-API verfügbar wird, wird sie im jeweiligen Adapter ergänzt.

**Frontend:** keine neuen Pakete. Bestehende UI-Bausteine reichen: Button, Badge/kleine Statuschips, Tooltip/Title, einfache DOM-Füllstandslinien.

**Datenbank/MinIO:** nicht betroffen.

### J) Auswirkungen auf bestehende Features
| Feature | Auswirkung |
|---|---|
| PROJ-3 / PROJ-38 | Sidebar bekommt einen festen oberen Budget-Block; er ist nicht Teil der ausblendbaren Workspace-/Session-Sektionen. |
| PROJ-19 | Usage-Service wird um Provider-Budget-Snapshot erweitert; bestehendes Dashboard bleibt unverändert. |
| PROJ-48 | Codex-Usage kann als Schätzquelle genutzt werden; Codex-CLI-Verfügbarkeit kommt aus der Registry. |
| PROJ-51 | Engine-Verfügbarkeit/Deaktivierung wird berücksichtigt; deaktivierte Provider werden als nicht verfügbar angezeigt. |
| PROJ-25 | Endpunkte bleiben auth-geschützt; keine Secret-Werte in Antworten. |

### K) Bau-Reihenfolge / Handoff
1. **Backend zuerst:** Schemas für Provider-Budgets, `ProviderBudgetService`, Claude-/Codex-Adapter, TTL-Cache, `/usage/provider-budgets`, Tests für Live/Schätzung/`n/v`/Fehler/Rate-Limit.
2. **Frontend danach:** `ProviderBudgetWidget`, API-Client-Typen, Einbau in `SessionRail`, kompakte Darstellung + Mobile-Drawer-Check.
3. **QA:** Backend-Matrix für Provider verfügbar/nicht verfügbar, keine Live-Quelle, Quoten konfiguriert/nicht konfiguriert, Refresh-Rate-Limit; Browser-Smoke Desktop/Mobile, Textüberlauf in der 72er Sidebar.

## Implementation Notes (Backend Developer)
**Datum:** 2026-06-27 · **Branch:** dev · **Stand:** Backend fertig.

### Gebaut
- **Schemas:** `ProviderBudgetSnapshot`, `ProviderBudget`, `ProviderBudgetWindow` in `backend/app/schemas/usage.py`. Qualität explizit als `live | estimated | unavailable | stale`; Provider-Verfügbarkeit als `available | disabled | unavailable`.
- **Service:** `ProviderBudgetService` in `backend/app/engine/usage.py` mit kurzlebigem In-Memory-Cache, TTL aus `provider_budget_refresh_minutes` und separatem manuellem Refresh mit Rate-Limit (`provider_budget_force_refresh_min_seconds`).
- **Datenquelle:** vorhandener `session_index` über `repo.list_all()` für lokale Schätzung. Es gibt **keine neue Tabelle**, keine Migration, kein MinIO.
- **Provider-Handling:** `claude` und `codex` werden über die bestehende Engine-Registry auf Konfiguration, Aktiv-Status und Verfügbarkeit geprüft. Ein Ausfall von Codex beschädigt Claude nicht.
- **Schätzlogik:** Prozentwerte entstehen nur, wenn ein explizites Limit konfiguriert ist (`provider_budget_<provider>_5h_tokens`, `provider_budget_<provider>_week_tokens`). Ohne Limit liefert der Service `quality=unavailable` und `used_pct=null` statt erfundener Prozentwerte.
- **API:** `GET /usage/provider-budgets` liefert den gecachten Snapshot; `POST /usage/provider-budgets/refresh` erzwingt Refresh und antwortet bei zu schnellem Wiederholen mit 429.
- **Config:** neue optionale Settings-Felder in `backend/app/config.py`: Refresh-Minuten, Provider-Timeout, Force-Refresh-Rate-Limit und vier optionale Quota-Limits für Claude/Codex je 5h/Woche.

### Tests
- `backend/tests/test_proj52_provider_budgets.py` deckt ab: `n/v` ohne Limits, konfigurierte Schätzung pro Provider/Fenster, deaktivierter Provider, CLI-/Provider-unavailable, Cache-TTL, manueller Refresh-Rate-Limit und beide Endpunkte.
- Regression mit bestehendem PROJ-19 Usage-Backend geprüft.

### Verifikation
- `python -m pytest tests/test_proj52_provider_budgets.py tests/test_proj19_usage.py` → **16 passed**.
- Hinweis: `conda` ist in dieser Shell nicht als Kommando verfügbar; ausgeführt wurde direkt `/home/dev/miniconda3/envs/Dashboard/bin/python`.

## Implementation Notes (Frontend Developer)
**Datum:** 2026-06-27 · **Branch:** dev · **Stand:** Frontend fertig, QA bestanden.

### Gebaut
- **API-Typen:** `ProviderBudgetSnapshotRead`, `ProviderBudgetRead`, `ProviderBudgetWindowRead` plus Qualitäts-/Verfügbarkeits-Literals in `nextjs_app/lib/types.ts`.
- **API-Client:** `getProviderBudgets()` für `GET /usage/provider-budgets` und `refreshProviderBudgets()` für `POST /usage/provider-budgets/refresh` in `nextjs_app/lib/api.ts`.
- **Sidebar-Widget:** `ProviderBudgetWidget` in `nextjs_app/components/cockpit/provider-budget-widget.tsx`.
  - Lädt beim Mount den Budget-Snapshot.
  - Pollt danach anhand `ttl_seconds` aus dem Backend (Default backendseitig 30 Minuten).
  - Bietet manuellen Refresh per Icon-Button **„Budget aktualisieren“**.
  - Hält bei Refresh-Fehlern den letzten Stand sichtbar.
  - Zeigt `live`, `geschätzt`, `veraltet` oder `n/v`; unbekannte Prozentwerte bleiben `n/v`.
  - Rendert Claude/Codex-Zeilen mit 5h-/Wochen-Chips, Füllstandsbalken, Reset-Kurztext und Tooltips.
- **Einbau:** `ProviderBudgetWidget` im Footer des `SessionRail`; Claude/Codex werden über die Sidebar-Präferenz-Sektion `Verbrauch` gefiltert. Damit erscheint es auch im Mobile-Drawer.

### Tests / Verifikation
- `npm test -- provider-budget-widget.test.tsx` → **1 passed**.
- `npm test` → **170 passed**.
- `npm run lint` → **grün**.
- `npx tsc --noEmit` wurde geprüft, scheitert aber an einem bestehenden, nicht PROJ-52-bezogenen Typfehler in `nextjs_app/lib/md-tree.test.ts:118` (`children`-Cast). Die neuen PROJ-52-Dateien sind davon nicht betroffen.

## QA Test Results
**Datum:** 2026-06-27 · **QA:** abc-qa · **Branch:** dev · **Entscheidung:** Approved / production-ready.

### Test Matrix
- Backend fokussiert: `/home/dev/miniconda3/envs/Dashboard/bin/python -m pytest tests/test_proj52_provider_budgets.py tests/test_proj19_usage.py` → **16 passed**.
- Backend komplett: `/home/dev/miniconda3/envs/Dashboard/bin/python -m pytest` → **915 passed, 1 warning**. Die Warnung ist eine bestehende Starlette-Cookie-Deprecation in `tests/test_proj25_auth.py`.
- Frontend fokussiert: `npm test -- provider-budget-widget.test.tsx` → **2 passed**.
- Frontend komplett: `npm test` → **171 passed**.
- Frontend Lint: `npm run lint` → **grün**.
- Frontend Production Build: `npm run build` → **grün**.
- Separater TypeScript-Check: `npx tsc --noEmit` → **bekannter Altfehler außerhalb PROJ-52** in `nextjs_app/lib/md-tree.test.ts:118`; `next build` und alle PROJ-52-Dateien sind nicht betroffen.

### Acceptance Criteria
- Sidebar-Platzierung, Claude-/Codex-Zeilen, 5h-/Wochenfenster, Prozent-/Balkenanzeige, Reset-Kurztext und deutsche UI-Texte sind im `ProviderBudgetWidget` umgesetzt.
- Initiales Laden, regelmäßiger Refresh über backendseitiges `ttl_seconds` und manueller Refresh über `POST /usage/provider-budgets/refresh` sind umgesetzt.
- Bei Refresh-Fehlern bleibt der letzte Snapshot sichtbar; Erstladefehler zeigen eine deutsche Kurzmeldung.
- Provider-deaktiviert, Provider-unavailable und fehlende Quota-Limits degradieren zu `n/v` statt erfundenen Prozentwerten.
- Backend-Cache, 30-Minuten-Default, konfigurierte Limits, getrennte Providerfenster und Refresh-Rate-Limit sind durch Tests abgedeckt.
- Mobile-Drawer-Nutzung wird durch Einbau in den bestehenden `SessionRail` mit kompakten, nicht horizontal scrollenden Grid-Chips unterstützt; kein separater Browser-E2E wurde in dieser QA ausgeführt.

### Edge Cases / Security
- Auth-Grenze geprüft: `usage.router` wird in `backend/app/main.py` mit `Depends(get_current_user)` eingebunden; die neuen Budget-Endpunkte liegen damit hinter derselben JWT-Grenze wie das Usage-Dashboard.
- Keine Secrets in API-Antworten: Budgetantworten enthalten nur Provider-Key, Anzeigename, Verfügbarkeit, Fensterwerte, Quellenklasse und deutsche Fehltexte.
- Kein XSS-Risiko gefunden: Frontend rendert Provider-/Fehlertexte als React-Text/`title`; kein `dangerouslySetInnerHTML`.
- Kein MinIO-/DB-Migrationsrisiko: Feature nutzt nur In-Memory-Cache plus vorhandenen Session-Index.
- Mehrere Tabs/manueller Doppelrefresh: Backend-Rate-Limit gibt 429 mit deutscher Kurzmeldung zurück.

### Findings
- **Resolved Low:** Wenn ein `reset_at`-Zeitpunkt im geöffneten UI überschritten wird, zeigt die UI weiter `fällig` und setzt die Fensterqualität nun clientseitig auf `veraltet`. Abgedeckt durch `provider-budget-widget.test.tsx`.

### Ergebnis
Keine Critical- oder High-Findings. PROJ-52 ist aus QA-Sicht bereit für Deployment.

## Deployment
**Datum:** 2026-06-28 · **Version:** 0.24.1 · **Branch:** main · **Production URL:** https://jupiter.auxevo.tech

### Ausgeliefert
- Sidebar-Budget-Monitor unten im `SessionRail` für Claude und Codex.
- `GET /usage/provider-budgets` und `POST /usage/provider-budgets/refresh` hinter der bestehenden Auth-Grenze.
- Konfigurierbare 30-Minuten-TTL, manueller Refresh mit Rate-Limit und konservative Degradation auf `n/v`.
- Bugfix 0.24.1: Budget-Anzeige sitzt unten im Sidebar-Footer.
- Bugfix 0.24.1: Claude- und Codex-Verbrauch sind einzeln über „Sidebar anpassen" ein-/ausblendbar.
- Living Docs aktualisiert: Architektur, Benutzeranleitung, Funktionsablauf und PRD-Roadmap.

### Smoke-Test nach Host-Build
- [ ] `https://jupiter.auxevo.tech/api/health` liefert OK.
- [ ] Login-Screen lädt, Login funktioniert, geschützte Route überlebt Hard-Reload.
- [ ] Sidebar zeigt unten den Bereich **Budget** mit Claude und/oder Codex.
- [ ] „Sidebar anpassen" enthält **Verbrauch** mit getrennten Schaltern für Claude und Codex.
- [ ] 5h- und Wochenfenster zeigen Prozentwerte, `geschätzt` oder `n/v`; kein horizontales Scrollen.
- [ ] **Budget aktualisieren** triggert Refresh; bei zu schnellem Wiederholen erscheint eine deutsche Kurzmeldung.
- [ ] Host-Logs für Frontend und Backend zeigen keine neuen Fehler.

---

## Tech Design — Iteration 2: Echte Live-Werte (Solution Architect)
**Erstellt:** 2026-06-28 · **Stack:** Next.js Sidebar (unverändert) + FastAPI Live-Adapter (neu) + In-Memory-Cache · **Branch:** dev

### Problem / Auslöser
Iteration 1 zeigt im Widget nur **manuell gepflegte bzw. konfigurierte Schätzwerte** (`source=manual_input` / `local_usage_estimate`). Ohne hinterlegte Quoten degradiert alles zu `n/v`. Der Nutzer will die **tatsächlichen providerseitigen Verbrauchswerte** sehen, automatisch abgefragt — ohne von Hand Prozentwerte einzutragen.

Nutzer-Hypothese (verifiziert): „Bei Claude `/usage` aufrufen, Werte aus der Antwort ins Widget eintragen. Bei Codex heißt der Befehl `status`, nicht `usage`."

### Feasibility-Befund (am echten Host geprüft, 2026-06-28)
Beide Provider liefern eine **maschinenlesbare Live-Quelle** — aber über **zwei unterschiedliche Mechanismen**:

**Claude — funktioniert direkt headless.**
`claude -p "/usage"` gibt nicht-interaktiv sauberen Klartext zurück, u. a.:
- `You are currently using your subscription to power your Claude Code usage` (Login-/Subscription-Nachweis)
- `Current session: 22% used · resets Jun 28, 10:40am (UTC)` → **5h-Fenster**
- `Current week (all models): 45% used · resets Jul 1, 8pm (UTC)` → **Wochenfenster**
- (zusätzliche Zeile „Current week (Sonnet only)" wird ignoriert.)
→ Prozent + Reset-Zeitpunkt (UTC) sind direkt parsebar. Kein TUI-Scraping nötig.

**Codex — `/status` ist NICHT headless-fähig, aber die Daten liegen in Session-Dateien.**
`codex exec "/status"` interpretiert `/status` als **Agent-Prompt** (führte `git status` aus) — es ist KEIN Slash-Command in `exec`. Die echten Limits stehen aber strukturiert in jeder Rollout-Datei `~/.codex/sessions/<jjjj>/<mm>/<tt>/rollout-*.jsonl`. Jeder Turn schreibt ein `rate_limits`-Objekt:
- `primary` → 5h-Fenster (`window_minutes: 300`): `used_percent`, `resets_at` (Unix-Epoch)
- `secondary` → Wochenfenster (`window_minutes: 10080` = 7 Tage): `used_percent`, `resets_at`
- `plan_type` (z. B. `plus`)
→ Das ist robuster als TUI-Scraping. `codex login status` (→ „Logged in using ChatGPT") dient als Verfügbarkeits-/Login-Check.

**Konsequenz:** Die User-Hypothese stimmt im Kern — mit der Korrektur, dass Codex nicht per Befehl abgefragt, sondern aus der jüngsten Session-Rollout-Datei gelesen wird.

### A) Was sich ändert (Scope dieser Iteration)
Nur der **Backend-Datenpfad**. Schemas und Frontend-Widget bleiben strukturell unverändert — das Widget rendert `used_pct`, `reset_at`, `quality`, `source` bereits. Es kommt lediglich eine neue Quelle `source=cli_live` mit `quality=live` hinein.

```
ProviderBudgetService  (backend/app/engine/usage.py)
├── SnapshotCache (TTL)                         [unverändert]
├── NEU: ClaudeCliBudgetAdapter  →  source=cli_live
│        ruft `claude -p "/usage"`, parst Session-/Wochen-Zeile
├── NEU: CodexRateLimitAdapter   →  source=cli_live
│        liest jüngste ~/.codex/sessions/**/rollout-*.jsonl, letztes rate_limits
├── ClaudeBudgetAdapter / CodexBudgetAdapter    [bestehende Schätz-/Manual-Pfade als Fallback]
└── LocalUsageEstimator                          [unverändert]
```

**Auflösungs-Reihenfolge pro Provider/Fenster (erste erfolgreiche gewinnt):**
1. **Live** (`cli_live`) — Claude-CLI-Output bzw. Codex-Rollout. → `quality=live`.
2. **Schätzung** (`local_usage_estimate`) — nur wenn ein konfiguriertes Limit existiert. → `quality=estimated`.
3. **Manuell** (`manual_input`) — falls weiter gepflegt. → `quality=estimated`.
4. **n/v** — sonst. → `quality=unavailable`.

### B) Provider-Adapter im Detail (Verhalten, kein Code)

**ClaudeCliBudgetAdapter**
- Führt `claude -p "/usage"` als Subprozess mit kurzem Timeout aus (off-event-loop, threadpool/async-subprocess).
- Parst die Zeilen „Current session: N% … resets <Datum> (UTC)" → 5h, „Current week (all models): N% … resets <Datum> (UTC)" → Woche.
- Reset-Strings werden zu UTC-Zeitpunkten geparst; fehlt das Jahr (Session-Zeile), wird das nächste passende Datum angenommen.
- Fehlt „using your subscription" / Exit ≠ 0 / Parse schlägt fehl → dieser Provider degradiert sauber (Fallback-Kette), Claude beschädigt Codex nicht.

**CodexRateLimitAdapter**
- Liest **ohne** Codex zu starten: jüngste `rollout-*.jsonl`, letztes `rate_limits`-Event. → `primary`=5h, `secondary`=Woche, `resets_at` (Epoch→UTC).
- **Frische:** Die Datei ist nur so aktuell wie der letzte Codex-Turn. Liegt das `resets_at` in der Vergangenheit oder ist das Event älter als das Fenster, markiert der Adapter `quality=stale` (Widget zeigt „veraltet").
- **Optionaler Force-Refresh** (Default AUS): Ein minimaler `codex exec`-Turn aktualisiert die Rollout-Daten. Kostet Tokens und braucht auf diesem Host `-s danger-full-access` (siehe Codex-Sandbox-Einschränkung: `workspace-write` scheitert am netns-Loopback). Wird hinter ein Setting + das bestehende Force-Refresh-Rate-Limit gelegt; ohne Aktivierung liest der Adapter nur die vorhandene Datei.
- Kein Login / keine Rollout-Datei → `unavailable` mit deutschem Hinweis.

### C) Betriebliche Voraussetzungen (wichtig fürs Deployment)
- Das Backend läuft host-nativ als systemd-Dienst. Die Live-Adapter funktionieren nur, wenn **derselbe Service-User** die CLIs eingeloggt hat, d. h. Zugriff auf `~/.claude` (Claude-Subscription-OAuth) und `~/.codex/sessions` hat. Vor dem Bau verifizieren: läuft `jupiter-backend` unter dem User, dessen `claude`/`codex` eingeloggt sind?
- `claude -p "/usage"` darf den Request-Thread nicht blockieren → asynchroner Subprozess mit hartem Timeout; das bestehende 30-Min-TTL hält die Aufrufrate niedrig (kein Pro-Tab-Trigger).
- Keine Secrets in die API-Antwort: nur Prozent, Reset, Quelle, Qualität — `plan_type` optional, keine Tokens/Keys.

### D) Schemas / Frontend
- **Schemas:** unverändert. `source` ist bereits ein freier String → `cli_live` ohne Migration. Optional ergänzend ein Quell-Label für den Tooltip („Live aus Claude-CLI" / „Live aus Codex-Session").
- **Frontend:** `provider-budget-widget.tsx` rendert `quality=live` bereits (Tooltip/Chip). Minimal: Tooltip-Text um die Live-Quelle ergänzen. `resolveWindowQuality()` (Client-`stale`-Logik) bleibt.

### E) Config (neue optionale Felder)
- `provider_budget_claude_cli_enabled` — Default an (sofern CLI verfügbar).
- `provider_budget_codex_rollout_enabled` — Default an.
- `provider_budget_codex_force_exec` — Default **aus** (kostenpflichtiger Codex-Turn für Frische).
- Bestehende Timeout-/Quota-/Refresh-Felder bleiben; die Quota-Limits dienen nur noch als Fallback-Schätzung, wenn die Live-Quelle ausfällt.

### F) Tech-Entscheidungen (Warum)
- **CLI/Datei lesen statt API:** Es gibt keine stabile öffentliche Quota-API; die CLIs sind die autoritative, vom Nutzer bereits authentifizierte Quelle. `claude -p "/usage"` und die Codex-Rollouts sind genau die Daten, die der Nutzer im TUI sieht.
- **Codex aus Session-Datei statt TUI-Scrape:** strukturiertes JSON (`used_percent`/`resets_at`) ist robust gegen TUI-/ANSI-Änderungen; kein pty, keine Token-Kosten beim Lesen.
- **Live als zusätzliche Quelle, nicht als Ersatz:** Schätz-/Manual-/`n/v`-Pfade bleiben als Fallback — fällt eine CLI aus, bleibt das Widget bedienbar (Constitution „keine falsche Genauigkeit").
- **Force-Refresh für Codex optional & aus:** automatisches Token-Ausgeben widerspricht der Knappheits-Doktrin; der Nutzer aktiviert es bewusst.

### G) Bau-Reihenfolge / Handoff
1. **Vorab-Check (Backend):** Service-User-Zugriff auf `~/.claude` + `~/.codex/sessions` verifizieren; Claude-`/usage`-Output und Codex-Rollout-Format am Zielhost gegenprüfen.
2. **Backend:** `ClaudeCliBudgetAdapter` + `CodexRateLimitAdapter`, Einhängen in `ProviderBudgetService` als oberste Quelle der Fallback-Kette, neue Config-Flags, Tests (Live-Parse OK, CLI fehlt/Exit≠0, Codex-Rollout fehlt/veraltet, Fallback auf Schätzung/`n/v`, kein Event-Loop-Block). Subprozesse in Tests gemockt.
3. **Frontend:** nur Tooltip-/`source=cli_live`-Feinschliff; kein struktureller Umbau.
4. **QA:** Matrix live/stale/unavailable je Provider; Smoke, dass echte Prozentwerte erscheinen; Regression PROJ-19.

### H) Risiken / offene Punkte
- **CLI-Output-Format kann sich ändern** (Claude-Update ändert „Current session:"-Wording) → Parse-Fehler wird als `n/v`/Fallback behandelt, nie als Crash; Format in einem Test fixiert.
- **Service-User ≠ CLI-Login-User** → Live-Quelle fällt komplett aus; muss im Deploy geklärt werden.
- **Codex-Frische ohne Force-Exec** begrenzt: zeigt Stand des letzten Codex-Laufs (als `veraltet` markiert) — bewusst akzeptiert, um Token-Kosten zu vermeiden.

## Implementation Notes (Backend Developer) — Iteration 2
**Datum:** 2026-06-28 · **Branch:** dev · **Stand:** Backend fertig, am echten Host verifiziert.

### Gebaut
- **Neues Modul `backend/app/engine/provider_budget_live.py`** mit zwei Live-Probes + reinen Parser-Funktionen:
  - `ClaudeUsageProbe` — startet `claude -p "/usage"` als async-Subprozess (Timeout `provider_budget_timeout_seconds`, Default **20 s**), parst per Regex `Current session:` → 5h und `Current week (all models):` → Woche; `_parse_claude_reset` wandelt „Jun 28, 10:40am (UTC)" / „Jul 1, 8pm (UTC)" in UTC (fehlendes Jahr → aktuelles, bei Vergangenheit aufs nächste Jahr gerollt). Exit≠0 / Timeout / kein Treffer → `{}`.
  - `CodexRolloutProbe` — liest **read-only** die jüngste `~/.codex/sessions/**/rollout-*.jsonl` (`latest_rollout_file` nach mtime), nimmt das **letzte** `rate_limits`-Event (`read_codex_rate_limits` + rekursives `_find_rate_limits`), mappt `primary`→5h, `secondary`→Woche (robust über `window_minutes` 300/10080), `resets_at`-Epoch→UTC. Dateizugriff via `asyncio.to_thread` (kein Event-Loop-Block).
  - `LiveWindow`-Dataclass + `build_live_probes()`-Factory fürs Production-Wiring.
- **`ProviderBudgetService` (usage.py) erweitert:** neuer Parameter `live_probes`; pro verfügbarem Provider wird die Probe einmal je Snapshot abgefragt (`_live_for`, fehlertolerant — jede Exception → `{}`, kein Crash). Neue Auflösungs-Reihenfolge je Fenster: **Live (`cli_live`, `quality=live`)** → Store/manuell → Schätzung → `n/v`. `_live_window` markiert ein bereits überschrittenes `reset_at` als `stale`.
- **Wiring `main.py`:** `ProviderBudgetService(repo, store=…, live_probes=build_live_probes())`.
- **Config `config.py`:** `provider_budget_claude_cli_enabled` (True), `provider_budget_codex_rollout_enabled` (True), `codex_sessions_dir` (`~/.codex/sessions`); `provider_budget_timeout_seconds` Default 10→**20 s**.

### Bewusste Entscheidungen
- **Schemas + Frontend unverändert:** `source` ist ein freier String → `cli_live:claude_usage` / `cli_live:codex_session` ohne Migration. Das Widget rendert `quality=live` bereits; es reagiert nur auf `quality`, nicht auf `source` → kein Frontend-Change nötig (optionaler Tooltip-Feinschliff bleibt offen).
- **Kein Force-Exec für Codex:** read-only genügt — Jupiters eigene Codex-Sessions (PROJ-48) schreiben laufend frische Rollouts. Spart Tokens und umgeht die netns-Sandbox-Einschränkung. Setting bewusst weggelassen statt als Dead-Flag.

### Verifikation
- `python -m pytest tests/test_proj52_live_budgets.py tests/test_proj52_provider_budgets.py tests/test_proj19_usage.py` → **34 passed**.
- Voller Backend-Lauf: `python -m pytest` → **933 passed, 1 warning** (bekannte Starlette-Cookie-Deprecation, nicht PROJ-52).
- **Echter Host-Smoke** mit den realen Probes: Claude → 5h 30 %, Woche 46 % (+ Reset-UTC); Codex → 5h 20 %, Woche 20 % (+ Reset-UTC). Beide Provider liefern echte Live-Werte.
- Hinweis: `conda` ist in dieser Shell kein Kommando; ausgeführt via `/home/dev/miniconda3/envs/Dashboard/bin/python`.

## QA Test Results — Iteration 2 (Live-Werte)
**Datum:** 2026-06-28 · **QA:** abc-qa · **Branch:** dev · **Entscheidung:** Approved / production-ready.

### Test-Matrix
- Fokus Live + Budget: `python -m pytest tests/test_proj52_live_budgets.py tests/test_proj52_provider_budgets.py` → **31 passed**.
- Voller Backend-Lauf: `python -m pytest` → **939 passed, 1 warning** (bekannte Starlette-Cookie-Deprecation in `test_proj25_auth.py`, nicht PROJ-52). Vorher 933 → +6 neue QA-Tests, keine Regression.
- Echter Host-Smoke (reale Probes, nicht gemockt): Claude 5h/Woche und Codex 5h/Woche liefern echte Prozentwerte + UTC-Reset → bestätigt, dass statt `n/v` nun `live` erscheint.

### Acceptance Criteria (Iterationsziel)
- **Echte aktuelle Werte statt nur manueller:** erfüllt — Live-Quelle hat Vorrang (`quality=live`, `source=cli_live:*`), per Host-Smoke + Endpoint-Integration (`test_endpoint_surfaces_live_values`) belegt.
- **Claude über `/usage`:** `claude -p "/usage"` headless geparst (`parse_claude_usage`), inkl. Reset-UTC; Sonnet-only-Zeile ignoriert.
- **Codex über `status`-Äquivalent:** `/status` ist nicht headless — stattdessen read-only aus dem `rate_limits`-Event der jüngsten Rollout-Datei (`primary`=5h, `secondary`=Woche). Korrektur zur ursprünglichen Hypothese, gleiches Ergebnis.
- **Keine falsche Präzision / saubere Degradation:** Probe-Fehler, fehlende Datei, partielle Daten und nicht verfügbarer Provider fallen auf Schätzung/manuell/`n/v` zurück (`test_failing_probe_degrades_to_fallback`, `test_partial_live_falls_back_for_other_window`).
- **Reset überschritten → veraltet:** `test_live_window_past_reset_is_stale` → `quality=stale`.
- **Wert > 100 %:** `test_parse_claude_usage_over_100_percent_not_truncated` → 105 % nicht gekappt.

### Edge Cases
- Garbage-/Nicht-JSON-Zeile mit `rate_limits`-Marker in Codex-Rollout → übersprungen, letztes gültiges Event gewinnt.
- Claude-Output ohne parsebaren Reset → Prozentwert bleibt erhalten, `reset_at=None` (Service füllt `now+duration`).
- Codex-Datei vorhanden, aber ohne `rate_limits`-Event → `n/v`-Fallback.
- Probe deaktiviert per Config (`provider_budget_codex_rollout_enabled=False`) → leer, kein Abruf.

### Security (Red-Team)
- **Auth:** `usage.router` in `main.py:284` mit `dependencies=auth_gate` eingebunden — die Live-Endpunkte liegen hinter derselben JWT-Grenze.
- **Command-Injection:** Claude-Probe nutzt `create_subprocess_exec` (keine Shell) mit **fixem** argv `[claude_bin, "-p", "/usage"]` — kein User-Input fließt in die Kommandozeile. Codex-Probe liest aus fixem Config-Verzeichnis per Glob, ebenfalls ohne User-Input.
- **Keine Secret-Exposition:** Live-Fenster enthält ausschließlich Lagebild-Felder (`test_live_window_exposes_no_secret_fields`); `plan_type`, Token- und Limit-Zahlen werden nicht in die API-Antwort übernommen.
- **DoS/Last:** Probes laufen nur einmal je 30-Min-Snapshot; manueller Refresh rate-limited (429). Subprozess mit hartem Timeout (20 s) + `to_thread`-Dateizugriff blockieren den Event-Loop nicht.

### Findings
- Keine Critical-/High-/Medium-Findings.
- **Low / offen (kein Blocker):** Frontend-Tooltip nennt die konkrete Live-Quelle noch nicht (Widget rendert `quality=live` korrekt, da es nur auf `quality` reagiert). Optionaler Feinschliff, falls gewünscht.
- **Nicht ausgeführt:** kein separater Browser-E2E (Frontend strukturell unverändert; Datenpfad über Host-Smoke + Endpoint-Integrationstest abgedeckt). Empfehlung: nach Deploy einmal in der UI prüfen, dass Claude/Codex `live`-Prozentwerte zeigen.

### Ergebnis
Keine Critical- oder High-Findings. PROJ-52 Iteration 2 ist aus QA-Sicht **production-ready**.
