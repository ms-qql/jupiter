// PROJ-38 QA: Invarianten der zentralen Sidebar-Definition. Diese sichern den
// Erweiterungs-Vertrag für PROJ-39/40 (jede neue Sektion/Eintrag muss diese
// Regeln erfüllen, sonst bricht Merge/Reorder).

import { describe, expect, it } from "vitest";
import {
  SIDEBAR_ITEMS,
  SIDEBAR_SECTIONS,
  sectionLabel,
} from "./sidebar-config";

describe("sidebar-config (PROJ-38)", () => {
  it("Item-Keys sind eindeutig", () => {
    const keys = SIDEBAR_ITEMS.map((it) => it.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("jeder Eintrag gehört zu einer definierten Sektion", () => {
    const sectionIds = new Set(SIDEBAR_SECTIONS.map((s) => s.id));
    for (const it of SIDEBAR_ITEMS) {
      expect(sectionIds.has(it.section)).toBe(true);
    }
  });

  it("Workspace-Einträge haben ein Navigationsziel, die Session-Sektion nicht", () => {
    for (const it of SIDEBAR_ITEMS.filter((i) => i.section === "workspace")) {
      expect(it.href).toBeTruthy();
    }
    const sessions = SIDEBAR_ITEMS.find((i) => i.key === "sessions");
    expect(sessions?.href).toBeUndefined();
  });

  it("Default-Reihenfolge ist innerhalb jeder Sektion eindeutig", () => {
    for (const sec of SIDEBAR_SECTIONS) {
      const orders = SIDEBAR_ITEMS.filter((i) => i.section === sec.id).map(
        (i) => i.defaultOrder,
      );
      expect(new Set(orders).size).toBe(orders.length);
    }
  });

  it("liefert die Sektionslabels Workspace und Aktive Sessions", () => {
    expect(sectionLabel("workspace")).toBe("Workspace");
    expect(sectionLabel("sessions")).toBe("Aktive Sessions");
  });
});
