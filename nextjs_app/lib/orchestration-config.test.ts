// PROJ-39 QA: Pure-Helfer der Orchestration-Sidebar (Icon-Auflösung, Item-Bau,
// Namensraum-Key). Deckt Akzeptanzkriterien „Label + Icon", „eigene Route je
// Eintrag" und „kein Key-Konflikt mit statischen Einträgen" ohne DOM ab.

import { describe, expect, it } from "vitest";
import {
  AppWindowIcon,
  PaperclipIcon,
  WavesIcon,
} from "lucide-react";
import {
  SIDEBAR_SECTIONS,
  orchestrationItemDef,
  orchestrationItemKey,
  resolveOrchestrationIcon,
  sectionLabel,
} from "./sidebar-config";

describe("Orchestration-Sektion (PROJ-39)", () => {
  it("existiert als Sektion unter „Aktive Sessions“", () => {
    const ids = SIDEBAR_SECTIONS.map((s) => s.id);
    expect(ids).toContain("orchestration");
    expect(ids.indexOf("orchestration")).toBeGreaterThan(ids.indexOf("sessions"));
    expect(sectionLabel("orchestration")).toBe("Orchestration");
  });
});

describe("resolveOrchestrationIcon", () => {
  it("löst bekannte lucide-Namen auf (paperclip, waves)", () => {
    expect(resolveOrchestrationIcon("paperclip")).toBe(PaperclipIcon);
    expect(resolveOrchestrationIcon("waves")).toBe(WavesIcon);
  });

  it("ist case-insensitiv", () => {
    expect(resolveOrchestrationIcon("Paperclip")).toBe(PaperclipIcon);
  });

  it("fällt bei unbekanntem/leerem Namen auf ein neutrales App-Icon zurück", () => {
    expect(resolveOrchestrationIcon("gibtsnicht")).toBe(AppWindowIcon);
    expect(resolveOrchestrationIcon(null)).toBe(AppWindowIcon);
    expect(resolveOrchestrationIcon(undefined)).toBe(AppWindowIcon);
  });
});

describe("orchestrationItemDef / orchestrationItemKey", () => {
  const engine = { key: "paperclip", label: "Paperclip", icon: "paperclip" };

  it("baut einen Sidebar-Eintrag mit Route /orchestration/<key> + Icon + Sektion", () => {
    const def = orchestrationItemDef(engine, 2);
    expect(def.key).toBe("orch:paperclip");
    expect(def.label).toBe("Paperclip");
    expect(def.icon).toBe(PaperclipIcon);
    expect(def.href).toBe("/orchestration/paperclip");
    expect(def.section).toBe("orchestration");
    expect(def.defaultVisible).toBe(true);
    expect(def.defaultOrder).toBe(2);
  });

  it("nutzt einen eigenen Namensraum (orch:) → kein Konflikt mit statischen Keys", () => {
    expect(orchestrationItemKey("paperclip")).toBe("orch:paperclip");
    // statische Keys sind „doku"/„dateien"/„sessions" — der Präfix trennt sie sicher.
    expect(orchestrationItemKey("sessions")).toBe("orch:sessions");
  });

  it("fehlt das Icon, greift der Default (kein Crash)", () => {
    const def = orchestrationItemDef({ key: "x", label: "X", icon: null }, 0);
    expect(def.icon).toBe(AppWindowIcon);
  });
});
