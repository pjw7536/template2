import { afterEach, describe, expect, it, vi } from "vitest"

import {
  fetchAppAccessStats,
  previewManualAppAccessStats,
  recordAppAccess,
} from "./accessStatsApi"

function jsonResponse(payload = {}) {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("Access Stats API contract", () => {
  it("통계 query는 appId와 period만 사용한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ apps: [] }))
    vi.stubGlobal("fetch", fetchMock)

    await fetchAppAccessStats({
      from: "2026-08-01",
      to: "2026-08-02",
      appId: "voc",
      period: "day",
      app_id: "legacy",
      granularity: "month",
    })

    const url = new URL(fetchMock.mock.calls[0][0])
    expect(Object.fromEntries(url.searchParams)).toEqual({
      from: "2026-08-01",
      to: "2026-08-02",
      appId: "voc",
      period: "day",
    })
  })

  it("접속 이벤트 body는 camelCase 필드만 전송한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }))
    vi.stubGlobal("fetch", fetchMock)

    await recordAppAccess({
      appId: "voc",
      appName: "VoE",
      path: "/voc",
      app_id: "legacy",
    })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      appId: "voc",
      appName: "VoE",
      path: "/voc",
    })
  })

  it("수동 입력 body는 pastedText와 sourceName만 전송한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ rows: [] }))
    vi.stubGlobal("fetch", fetchMock)

    await previewManualAppAccessStats({
      pastedText: "date\tappName",
      sourceName: "manual",
      pasted_text: "legacy",
    })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      pastedText: "date\tappName",
      sourceName: "manual",
    })
  })
})
