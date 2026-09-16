import { afterEach, describe, expect, it, vi } from "vitest"

import { createApp, fetchApps, reorderApps } from "./appstore"

function jsonResponse(payload = {}, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(payload),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("AppStore API canonical 계약", () => {
  it("앱 생성 body에서 snake_case 필드를 제거한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ app: { id: 1, name: "App", manualUrl: "/manual" } }),
    )
    vi.stubGlobal("fetch", fetchMock)

    await createApp({
      name: "App",
      category: "Tools",
      url: "/app",
      manualUrl: "/manual",
      manual_url: "/legacy",
      screenshot_urls: ["/legacy.png"],
    })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      name: "App",
      category: "Tools",
      url: "/app",
      manualUrl: "/manual",
    })
  })

  it("순서 body는 appIds와 orderVersion만 전송한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ appIds: [2, 1], orderVersion: "next", updated: 2 }),
    )
    vi.stubGlobal("fetch", fetchMock)

    await reorderApps({
      appIds: [2, 1],
      orderVersion: "current",
      app_ids: [1, 2],
    })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      appIds: [2, 1],
      orderVersion: "current",
    })
  })

  it("응답 정규화는 snake_case fallback을 사용하지 않는다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          results: [{
            id: 1,
            name: "App",
            manual_url: "/legacy",
            screenshot_url: "/legacy.png",
            display_order: 7,
          }],
          order_version: "legacy",
        }),
      ),
    )

    const result = await fetchApps()

    expect(result.orderVersion).toBe("")
    expect(result.apps[0]).toMatchObject({
      manualUrl: "",
      screenshotUrl: "",
      displayOrder: 0,
    })
  })

  it("canonical 오류 message와 payload를 보존한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            code: "invalid_request",
            message: "앱 입력이 올바르지 않습니다.",
            details: {},
            fieldErrors: {},
          },
          { ok: false, status: 400 },
        ),
      ),
    )

    await expect(fetchApps()).rejects.toMatchObject({
      message: "앱 입력이 올바르지 않습니다.",
      status: 400,
      payload: { code: "invalid_request" },
    })
  })
})
