// PROJ-78 QA: Reine Pane-Logik des Workspace. Deckt alle Akzeptanzkriterien
// der Tab-Wechsel-/Ersetzen-Regel:
//   - bereits sichtbar → nur fokussieren (kein Duplikat)
//   - sonst den freien Pane-Slot belegen
//   - sonst den aktiven Pane ersetzen
// Plus die Sonderregel für „Dateien" (aktive Session bleibt sichtbar:
//   leerer Slot wird gefüllt; sonst ersetzt Dateien den NICHT-aktiven Pane).
// Plus die Edge Cases der Spec: aktive Session schließen → andere wird
// aktiv; letzte schließen → bothClosed-Flag; Schließen einer nicht aktiven
// Session lässt die aktive Ansicht unverändert.

import { describe, expect, it } from "vitest";
import {
  computeClosePanes,
  computeOpenPanes,
  computeToggleFiles,
  type Pane,
} from "./workspace-provider";

const empty: [Pane, Pane] = [null, null];
const a = (id: string): Pane => ({ kind: "session", id });
const files: Pane = { kind: "files" };

describe("computeOpenPanes (zentrale Öffnen-/Fokussieren-Regel)", () => {
  it("legt eine noch nie geöffnete Session in den linken freien Pane", () => {
    const r = computeOpenPanes(empty, 0, "S1");
    expect(r.panes).toEqual([a("S1"), null]);
    expect(r.activeIndex).toBe(0);
  });

  it("füllt den rechten freien Pane, wenn der linke belegt ist", () => {
    const r = computeOpenPanes([a("S1"), null], 0, "S2");
    expect(r.panes).toEqual([a("S1"), a("S2")]);
    expect(r.activeIndex).toBe(1);
  });

  it("fokussiert eine bereits sichtbare Session, ohne sie zu duplizieren", () => {
    const panes: [Pane, Pane] = [a("S1"), a("S2")];
    const r = computeOpenPanes(panes, 0, "S2");
    expect(r.panes).toBe(panes); // keine neue Allokation
    expect(r.activeIndex).toBe(1);
  });

  it("ist ein no-op, wenn die aktive Session erneut geöffnet wird", () => {
    const panes: [Pane, Pane] = [a("S1"), null];
    const r = computeOpenPanes(panes, 0, "S1");
    expect(r.panes).toBe(panes);
    expect(r.activeIndex).toBe(0);
  });

  it("ersetzt die aktive Session, wenn beide Pane belegt sind", () => {
    const r = computeOpenPanes([a("S1"), a("S2")], 0, "S3");
    expect(r.panes).toEqual([a("S3"), a("S2")]);
    expect(r.activeIndex).toBe(0);
  });

  it("ersetzt im aktiven Pane = 1 ⇒ rechte Session wird ersetzt", () => {
    const r = computeOpenPanes([a("S1"), a("S2")], 1, "S3");
    expect(r.panes).toEqual([a("S1"), a("S3")]);
    expect(r.activeIndex).toBe(1);
  });
});

describe("computeClosePanes (Schließen entfernt nur die Ansicht)", () => {
  it("leert den Pane der Session, lässt activeIndex aber unverändert, wenn ein anderer Pane aktiv ist", () => {
    const r = computeClosePanes([a("S1"), a("S2")], 0, "S2");
    expect(r.panes).toEqual([a("S1"), null]);
    expect(r.activeIndex).toBe(0);
    expect(r.bothClosed).toBe(false);
  });

  it("aktiviert die verbleibende Session, wenn die aktive geschlossen wird", () => {
    const r = computeClosePanes([a("S1"), a("S2")], 0, "S1");
    expect(r.panes).toEqual([null, a("S2")]);
    expect(r.activeIndex).toBe(1);
    expect(r.bothClosed).toBe(false);
  });

  it("setzt bothClosed=true, wenn die letzte Session im aktiven Pane geschlossen wird", () => {
    const r = computeClosePanes([a("S1"), null], 0, "S1");
    expect(r.panes).toEqual([null, null]);
    expect(r.activeIndex).toBe(0);
    expect(r.bothClosed).toBe(true);
  });

  it("ist ein no-op, wenn die ID in keinem Pane liegt", () => {
    const panes: [Pane, Pane] = [a("S1"), null];
    const r = computeClosePanes(panes, 0, "S-other");
    expect(r.panes).toBe(panes);
    expect(r.activeIndex).toBe(0);
    expect(r.bothClosed).toBe(false);
  });
});

describe("computeToggleFiles (Datei-Arbeitsfläche)", () => {
  it("füllt den freien Pane-Slot, wenn eine Session offen ist", () => {
    const r = computeToggleFiles([a("S1"), null], 0);
    expect(r.panes).toEqual([a("S1"), files]);
    expect(r.activeIndex).toBe(0); // aktive Session bleibt aktiv
    expect(r.clearedFileFullscreen).toBe(false);
  });

  it("ersetzt den NICHT-aktiven Pane, wenn beide Pane mit Sessions belegt sind", () => {
    const r = computeToggleFiles([a("S1"), a("S2")], 0);
    expect(r.panes).toEqual([a("S1"), files]);
    expect(r.activeIndex).toBe(0);
  });

  it("ersetzt auch in der anderen Richtung bei activeIndex=1", () => {
    const r = computeToggleFiles([a("S1"), a("S2")], 1);
    expect(r.panes).toEqual([files, a("S2")]);
    expect(r.activeIndex).toBe(1);
  });

  it("schließt die Datei-Arbeitsfläche wieder, wenn sie im linken Pane offen ist", () => {
    const r = computeToggleFiles([files, a("S1")], 0);
    expect(r.panes).toEqual([null, a("S1")]);
    expect(r.activeIndex).toBe(1); // Pane #1 wird aktiv
    expect(r.clearedFileFullscreen).toBe(true);
  });

  it("schließt die Datei-Arbeitsfläche, wenn sie im rechten Pane offen ist", () => {
    const r = computeToggleFiles([a("S1"), files], 1);
    expect(r.panes).toEqual([a("S1"), null]);
    expect(r.activeIndex).toBe(0);
    expect(r.clearedFileFullscreen).toBe(true);
  });

  it("setzt bothClosed=true, wenn die Datei-Arbeitsfläche die letzte Ansicht im aktiven Pane war", () => {
    const r = computeToggleFiles([files, null], 0);
    expect(r.panes).toEqual([null, null]);
    expect(r.activeIndex).toBe(0);
    expect(r.bothClosed).toBe(true);
  });

  it("schließt KEINE aktive Session, wenn die Datei eingehängt wird (aktive Session bleibt sichtbar)", () => {
    // Ausgangs-Situation: aktive Session S1 im linken Pane, leerer rechter Pane.
    // toggleFiles ⇒ Datei geht in den rechten Pane, S1 bleibt aktiv (Pane 0).
    const beforeSession = a("S1");
    const r = computeToggleFiles([beforeSession, null], 0);
    expect(r.panes[0]).toBe(beforeSession);
    expect(r.panes[1]).toEqual(files);
    expect(r.activeIndex).toBe(0);
  });
});
