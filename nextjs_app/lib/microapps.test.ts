// PROJ-40 QA: Pure-Logic-Tests für die Micro-Apps-Sidebar-Helfer und die
// native Komponenten-Registry. Sichern den Erweiterungs-Vertrag (eigener
// Namespace, eigene Sektion/Route) und die Abgrenzung zu Orchestration.

import { describe, expect, it } from "vitest";
import {
  SIDEBAR_SECTIONS,
  microAppItemDef,
  microAppItemKey,
  orchestrationItemKey,
  resolveOrchestrationIcon,
  sectionLabel,
} from "./sidebar-config";
import { resolveMicroApp } from "./microapps-registry";

const engine = { key: "whiteboard", label: "Excalidraw", icon: "pentool" };

describe("Micro-Apps Sidebar-Konfig (PROJ-40)", () => {
  it("die Sektion micro existiert mit deutschem Label", () => {
    const micro = SIDEBAR_SECTIONS.find((s) => s.id === "micro");
    expect(micro).toBeDefined();
    expect(micro?.label).toBe("Micro-Apps");
    expect(sectionLabel("micro")).toBe("Micro-Apps");
  });

  it("Micro-Apps sitzen UNTER der Orchestration-Sektion", () => {
    const ids = SIDEBAR_SECTIONS.map((s) => s.id);
    expect(ids.indexOf("micro")).toBeGreaterThan(ids.indexOf("orchestration"));
  });

  it("microAppItemDef erzeugt eine /apps/[key]-Route in der micro-Sektion", () => {
    const def = microAppItemDef(engine, 3);
    expect(def.href).toBe("/apps/whiteboard");
    expect(def.section).toBe("micro");
    expect(def.defaultOrder).toBe(3);
    expect(def.defaultVisible).toBe(true);
    expect(def.label).toBe("Excalidraw");
  });

  it("Micro-Keys sind ein eigener Namespace, kollidieren NICHT mit Orchestration", () => {
    expect(microAppItemKey("whiteboard")).toBe("micro:whiteboard");
    expect(microAppItemKey("whiteboard")).not.toBe(
      orchestrationItemKey("whiteboard"),
    );
  });

  it("löst das pentool-Icon auf, fällt sonst auf ein Default-Icon zurück", () => {
    expect(resolveOrchestrationIcon("pentool")).toBeTruthy();
    // unbekannter Name → kein Crash, ein Fallback-Icon
    expect(resolveOrchestrationIcon("gibtsnicht")).toBeTruthy();
    expect(resolveOrchestrationIcon(null)).toBeTruthy();
  });
});

describe("native Micro-App-Registry (PROJ-40)", () => {
  it("liefert null für einen (noch) nicht registrierten key — kein Crash", () => {
    expect(resolveMicroApp("rechner")).toBeNull();
    expect(resolveMicroApp("")).toBeNull();
  });
});
