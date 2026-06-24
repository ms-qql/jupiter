// PROJ-17 QA: Vertrags-Tests für den Recovery-API-Client (Pfad/Methode/Body +
// Antwort-Parsing). Mockt global.fetch — kein Backend nötig.

import { afterEach, describe, expect, it, vi } from "vitest";
import { dismissRecovery, listRecovery, restoreRecovery, API_BASE } from "./api";

function mockFetch(status: number, body: unknown) {
  const resp = {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(resp);
}

afterEach(() => vi.restoreAllMocks());

describe("Recovery-API-Client — PROJ-17", () => {
  it("listRecovery: GET /recovery, parst candidates", async () => {
    const f = mockFetch(200, { candidates: [{ session_id: "s1" }] });
    const res = await listRecovery();
    expect(f).toHaveBeenCalledWith(`${API_BASE}/recovery`, expect.objectContaining({}));
    expect(res.candidates[0].session_id).toBe("s1");
  });

  it("restoreRecovery: POST /recovery/{id}/restore mit initial_prompt im Body", async () => {
    const f = mockFetch(201, { session_id: "child" });
    await restoreRecovery("s1", "weiter so");
    const [url, init] = f.mock.calls[0];
    expect(url).toBe(`${API_BASE}/recovery/s1/restore`);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ initial_prompt: "weiter so" });
  });

  it("restoreRecovery ohne Prompt: initial_prompt = null", async () => {
    const f = mockFetch(201, { session_id: "child" });
    await restoreRecovery("s1");
    expect(JSON.parse(String(f.mock.calls[0][1]?.body))).toEqual({ initial_prompt: null });
  });

  it("dismissRecovery: POST /recovery/{id}/dismiss, 204 → void", async () => {
    const f = mockFetch(204, undefined);
    const res = await dismissRecovery("s1");
    expect(f.mock.calls[0][0]).toBe(`${API_BASE}/recovery/s1/dismiss`);
    expect(f.mock.calls[0][1]?.method).toBe("POST");
    expect(res).toBeUndefined();
  });

  it("Fehlerstatus → ApiError mit detail (z. B. 409 bereits wiederhergestellt)", async () => {
    mockFetch(409, { detail: "Dieser Strang wurde bereits wiederhergestellt." });
    await expect(restoreRecovery("s1")).rejects.toThrow("bereits wiederhergestellt");
  });
});
