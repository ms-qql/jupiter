// PROJ-38 QA: Pure-Logik des Prefs-Providers (Merge, Toggle, Move, Reorder,
// Reset). Deckt Akzeptanzkriterien (Sichtbarkeit, Reorder, RESET, Persistenz-
// Merge) + Edge-Cases (veralteter/unbekannter Key, neue Sektion, kaputter
// Storage-Inhalt) ohne DOM ab — Konvention des Repos (Vitest, node-Env).

import { describe, expect, it } from "vitest";
import {
  buildDefaults,
  mergeStored,
  movePref,
  reorderPref,
  togglePref,
} from "./sidebar-prefs-provider";

describe("buildDefaults", () => {
  it("setzt alle bekannten Einträge auf ihre Defaults (sichtbar)", () => {
    const d = buildDefaults();
    expect(d.doku).toEqual({ visible: true, order: 0 });
    expect(d.dateien).toEqual({ visible: true, order: 1 });
    expect(d.sessions).toEqual({ visible: true, order: 0 });
  });
});

describe("mergeStored (Persistenz-Merge)", () => {
  it("übernimmt gespeicherte Nutzerwünsche über die Defaults", () => {
    const m = mergeStored({
      doku: { visible: false, order: 1 },
      dateien: { visible: true, order: 0 },
    });
    expect(m.doku).toEqual({ visible: false, order: 1 });
    expect(m.dateien).toEqual({ visible: true, order: 0 });
  });

  it("ignoriert veraltete/unbekannte Keys (Sektion existiert nicht mehr)", () => {
    const m = mergeStored({ geloeschtesItem: { visible: false, order: 9 } });
    expect(m.geloeschtesItem).toBeUndefined();
    // bekannte Einträge bleiben auf Default
    expect(m.doku).toEqual({ visible: true, order: 0 });
  });

  it("neue Sektion (kein Storage-Eintrag) erscheint sichtbar an Default-Position", () => {
    // simuliert: gespeicherte Konfig kennt nur Workspace, „sessions" ist neu
    const m = mergeStored({ doku: { visible: false, order: 0 } });
    expect(m.sessions).toEqual({ visible: true, order: 0 });
  });

  it("verwirft kaputte Einträge (falsche Typen) und fällt auf Default zurück", () => {
    const m = mergeStored({
      doku: { visible: "nope", order: 2 },
      dateien: { order: 3 },
    });
    expect(m.doku).toEqual({ visible: true, order: 0 });
    expect(m.dateien).toEqual({ visible: true, order: 1 });
  });

  it("null/Unsinn → reine Defaults, kein Crash", () => {
    expect(mergeStored(null)).toEqual(buildDefaults());
    expect(mergeStored("kaputt")).toEqual(buildDefaults());
    expect(mergeStored(42)).toEqual(buildDefaults());
  });
});

describe("togglePref (Auge)", () => {
  it("schaltet Sichtbarkeit um, ohne order zu verändern", () => {
    const next = togglePref(buildDefaults(), "doku");
    expect(next.doku).toEqual({ visible: false, order: 0 });
    expect(next.dateien).toEqual({ visible: true, order: 1 });
  });

  it("unbekannter Key → unverändert (no-op)", () => {
    const prev = buildDefaults();
    expect(togglePref(prev, "gibtsnicht")).toBe(prev);
  });
});

describe("movePref (▲/▼)", () => {
  it("verschiebt innerhalb der Sektion nach unten und vergibt order neu", () => {
    const next = movePref(buildDefaults(), "doku", 1);
    expect(next.doku.order).toBe(1);
    expect(next.dateien.order).toBe(0);
  });

  it("nach oben über die Grenze hinaus ist ein no-op", () => {
    const prev = buildDefaults();
    expect(movePref(prev, "doku", -1)).toBe(prev); // doku ist bereits oben
  });

  it("nach unten über die Grenze hinaus ist ein no-op", () => {
    const prev = buildDefaults();
    expect(movePref(prev, "dateien", 1)).toBe(prev); // dateien ist bereits unten
  });
});

describe("reorderPref (Drag-and-Drop)", () => {
  it("sortiert fromKey direkt vor beforeKey ein", () => {
    const next = reorderPref(buildDefaults(), "dateien", "doku");
    expect(next.dateien.order).toBe(0);
    expect(next.doku.order).toBe(1);
  });

  it("Drop auf sich selbst ist ein no-op", () => {
    const prev = buildDefaults();
    expect(reorderPref(prev, "doku", "doku")).toBe(prev);
  });

  it("sektionsübergreifendes Droppen wird verhindert (no-op)", () => {
    const prev = buildDefaults();
    // „sessions" liegt in einer anderen Sektion als „doku"
    expect(reorderPref(prev, "doku", "sessions")).toBe(prev);
    expect(reorderPref(prev, "sessions", "doku")).toBe(prev);
  });
});

describe("RESET", () => {
  it("buildDefaults() stellt nach Änderungen Sichtbarkeit + Reihenfolge wieder her", () => {
    let s = togglePref(buildDefaults(), "doku");
    s = movePref(s, "dateien", -1);
    expect(s).not.toEqual(buildDefaults());
    // RESET im Provider = setPrefs(buildDefaults())
    expect(buildDefaults()).toEqual({
      doku: { visible: true, order: 0 },
      dateien: { visible: true, order: 1 },
      sessions: { visible: true, order: 0 },
    });
  });
});
