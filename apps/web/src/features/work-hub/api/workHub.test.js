import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchWorkHubContext } from "./workHub"

describe("fetchWorkHubContext", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("returns the launcher context", async () => {
    const payload = {
      enabled: true,
      available: true,
      mode: "single",
      reason: "",
      groups: [{ user_sdwt_prod: "SDWT-A", launch_url: "http://localhost:8100/o/work-hub/doc/abc123" }],
    }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(payload),
    }))

    await expect(fetchWorkHubContext()).resolves.toEqual(payload)
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/work-hub/context"),
      expect.objectContaining({ credentials: "include", cache: "no-store" })
    )
  })

  it("throws a status-aware error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: vi.fn().mockResolvedValue({ error: "scope_access_required" }),
    }))

    await expect(fetchWorkHubContext()).rejects.toMatchObject({
      message: "scope_access_required",
      status: 403,
    })
  })
})
