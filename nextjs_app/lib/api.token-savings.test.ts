import { afterEach, describe, expect, it, vi } from "vitest";
import {
  API_BASE,
  getTokenSavings,
  previewTokenSavings,
  setTokenSavings,
} from "./api";

function mockFetch(body: unknown) {
  const response = { ok: true, status: 200, json: async () => body } as Response;
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

afterEach(() => vi.restoreAllMocks());

describe("Token-Savings-API — PROJ-73", () => {
  it("liest engine- und projektspezifischen Health", async () => {
    const fetchMock = mockFetch({ enabled: false, modules: [] });
    await getTokenSavings("opencode", "/home/dev/projects/mein projekt");
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${API_BASE}/settings/token-savings?engine=opencode&project_path=%2Fhome%2Fdev%2Fprojects%2Fmein+projekt`,
    );
  });

  it("speichert ausschließlich den globalen Profilvertrag", async () => {
    const fetchMock = mockFetch({ enabled: true, modules: [] });
    const config = {
      enabled: true,
      profile_id: "balanced-v1" as const,
      module_enabled: { caveman: true, ponytail: true, codegraph: false },
    };
    await setTokenSavings(config, "claude");
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(String(init?.body))).toEqual(config);
  });

  it("fragt die effektive Session-Preview mit Override ab", async () => {
    const fetchMock = mockFetch({ enabled: true, modules: [] });
    await previewTokenSavings("codex", "/home/dev/projects/jupiter", "on");
    expect(fetchMock.mock.calls[0][0]).toContain("engine=codex");
    expect(fetchMock.mock.calls[0][0]).toContain("choice=on");
    expect(fetchMock.mock.calls[0][0]).toContain("project_path=%2Fhome%2Fdev%2Fprojects%2Fjupiter");
  });
});
