# Brainstorm — Buch-Nuggets (KI-Buch-Zusammenfassungen)

**Datum:** 2026-06-28
**Status:** Konzept geschärft — spec-reif (nächster Schritt: `/abc-requirements`)
**Modus:** Konzept schärfen · praktisch/baubar

---

## 1. Session-Setup

- **Topic:** KI-gestützte Mikro-App „Buch-Nuggets" innerhalb von Jupiter — komprimiert Bücher (überwiegend Technik & Finanz) zu strukturierten Kurzformen. Analog zur bestehenden Video-Summary-Micro-App.
- **Goal:** Robustes, baubares Produktkonzept mit klarem Datenmodell, das später Phase-2-Features (Vergleich, Quiz, Karteikarten) trägt.
- **Constraints / Kontext:**
  - Mikro-App in Jupiter, UX-Muster wie Video-Summary.
  - Input: Link **oder** Upload/Drag&Drop. Formate: pdf, epub, mobi, txt, docx.
  - Output: `.md` + extrahierte wichtige Abbildungen + konsolidierte PDF.
  - Ablage: `Hal/04_Resources/Buch_Nuggets/` (Reuse des `hal-video-summary`-Musters).
  - Modell-Auswahl zur Kostenkontrolle erforderlich.
- **Preferred energy:** praktisch/baubar.

---

## 2. Datenmodell der Nuggets

Pro Buch (Basisschicht CITE, erweitert für Fachbücher):

1. **1-Satz-Kernaussage** — was will der Autor beweisen?
2. **Executive Summary** — 5–10 Bullet Points, ohne Ausschmückung.
3. **Core Concepts** — Begriffe, Definitionen, Prinzipien.
4. **Tools/Frameworks** — Methoden, Entscheidungslogiken, Checklisten, Modelle.
5. **Numbers/Evidence** — Statistiken, Benchmarks, Formeln, Studien, Annahmen (mit Seitenzitat verankert).
6. **Examples/Case Studies** — konkrete Anwendung oder Gegenbeispiele.
7. **Actionable Takeaways** — was kann der Leser morgen anwenden?

**Erweiterungen für Fachbücher:**
- **Assumptions** — auf welchen (oft unausgesprochenen) Annahmen ruht das Buch?
- **Critique** — interne Schwächen/Lücken.
- **Action Items** — umsetzbare Schritte.

**Contra-Kapitel (Differenzierer):** Geht über den Buchinhalt hinaus. Führt mögliche Gegenbeweise auf — warum die Aussagen falsch oder lückenhaft sein könnten. Belegt mit externen Gegenpositionen + Quelle (kein freies Meinen).

---

## 3. Geschärfte Entscheidungen (D1–D11)

| # | Entscheidung | Ergebnis |
|---|---|---|
| **D1** | „Link zu einem Buch" | Direkte URL zu einer Datei (pdf/epub). Metadaten-Links (Goodreads/Amazon) liefern keinen Volltext → daraus keine Nuggets, Volltext anfordern. |
| **D2** | Verarbeitungsmodell | **Async-Job mit Fortschritt** (wie Video-Summary): Hochladen → Parsen → Analyse → PDF-Bau → in Hal abgelegt. Kein Browser-Blocking. |
| **D3** | Parsing/Chunking | **Map-Reduce**: pro Kapitel/Chunk Zwischen-Extrakte → Konsolidierung in die 7+3 Blöcke. Formate vorab zu Text+Bildern vereinheitlichen (calibre/pandoc/pdf-Extraktor). |
| **D4** | Abbildungs-Auswahl | Alle Figuren extrahieren → **LLM wählt per Bildunterschrift + Umgebungstext** die relevanten, referenziert sie im md an passender Stelle (wie hal-video-summary Frames einbettet). |
| **D5** | Contra-Engine: Wissensquelle | **Web-Recherche-gestützt** (deep-research-Pattern light): pro Kernthese 1–2 belegte Gegenpositionen mit Quelle. |
| **D6** | Zahlen/Formeln-Grounding | Block „Numbers/Evidence" **mit Seitenzitat** verankert (Seite X) gegen Halluzination. |
| **D7** | Modell-Auswahl (Kosten) | Dropdown aus `engines.yaml`. **Default Stufen-Logik:** günstiges Modell für Chunk-Extrakte, starkes Modell für Konsolidierung + Contra. Umschalter „global ein Modell für alles". **Kostenschätzung vor Start** (aus Seitenzahl/Tokens) + optionales Seitenlimit. |
| **D8** | Hal-Ablage | Reuse `hal-video-summary`-Muster: `04_Resources/Buch_Nuggets/`. Dateiname `<Autor>-<Titel>.md` + Unterordner `<Autor>-<Titel>/figures/`. md + integrierte PDF. |
| **D9** | Re-Run / Duplikate | Erkennung über Titel/Hash → fragen „überschreiben oder neue Version?". |
| **D10** | MVP-Scope-Grenze | Quiz, Karteikarten, Mehr-Buch-Vergleich, „apply to my business" = **Phase 2**, nicht MVP. |
| **D11** | Sprache | Nuggets immer **Deutsch**; Fachbegriffe/Zitate im Original. |

---

## 4. Pipeline (End-to-End, MVP)

```
1. Input        Link-URL ODER Upload/Drag&Drop (pdf|epub|mobi|txt|docx)
2. Normalize    → einheitliches Text+Bild-Format (calibre/pandoc/pdf-Extraktor)
3. Cost-Estimate Seiten/Tokens → Kostenschätzung anzeigen, Modellwahl bestätigen
4. Chunk        Kapitel-/Abschnittsweise zerlegen (Map)
5. Extract      Pro Chunk Zwischen-Extrakte (günstiges Modell)
6. Consolidate  Zusammenführen in 7+3 Blöcke (starkes Modell), Zahlen mit Seitenzitat
7. Figures      Abbildungen extrahieren → LLM wählt relevante → in md referenzieren
8. Contra       Web-Recherche pro Kernthese → belegte Gegenpositionen mit Quelle
9. Render       .md + figures/ + konsolidierte PDF (pdf-Skill, Bild-Embedding)
10. Store        → Hal/04_Resources/Buch_Nuggets/<Autor>-<Titel>/
```

Async-Job mit Status-Fortschritt im Jupiter-UI (D2).

---

## 5. Wiederverwendbare Bausteine in der bestehenden Umgebung

- **Video-Summary-Micro-App** — UX-, Job- und Fortschritts-Muster (Vorlage).
- **`hal-video-summary`-Skill** — md+Bilder+PDF nach Hal schreiben, Kategorie-Ordner-Logik.
- **`pdf`-Skill** — Markdown→PDF mit Bild-Embedding (Schritt 9).
- **`deep-research`-Pattern** — Quellen-gestützte Verifikation für das Contra-Kapitel (Schritt 8).
- **Jupiter `engines.yaml`** — Modell-Dropdown + Stufen-Logik (D7).

---

## 6. Offene Punkte vor dem Bauen (für `/abc-requirements`)

1. **mobi/epub-Parsing-Stack** final festlegen (calibre `ebook-convert` vorhanden? sonst Fallback).
2. **Bild-Extraktion aus Formaten** ohne saubere Bildebene (txt/manche pdf) — Verhalten bei „keine Abbildungen".
3. **Kostenschätzungs-Formel** kalibrieren (Tokens/Seite, Preis pro Engine aus `engines.yaml`).
4. **Web-Recherche-Budget** fürs Contra-Kapitel begrenzen (Anzahl Suchen/Thesen) — Kosten + Laufzeit.
5. **Hal-Schreibrechte** des Jupiter-Backends auf den Vault-Pfad bestätigen.
6. **Versionierungs-Schema** bei „neue Version" (D9) — Suffix/Timestamp.

---

## 7. Empfohlener nächster Schritt

Konzept ist baubar geschärft. **Run `/abc-requirements`** für die formale Feature-Spec
(`features/PROJ-X-buch-nuggets.md`) als Mikro-App in Jupiter, MVP-Scope nach D10.
