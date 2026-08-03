import { describe, expect, it } from "vitest"

import {
  buildObserverLogScopeKey,
  getLatestObserverLogPageState,
  mergeResidentLogs,
  shouldRetryObserverLogQuery,
} from "./observerLogController"

describe("Observer log controller 계산", () => {
  it("batch와 추가 page를 log type별로 중복 없이 병합한다", () => {
    const result = mergeResidentLogs(
      {
        eqp: { items: [{ id: "1", eventTime: "2026-08-03T10:00:00Z" }] },
      },
      [
        { logKey: "eqp", cursor: "eqp-1" },
        { logKey: "tip", cursor: "tip-1" },
      ],
      [
        { data: { items: [
          { id: "1", eventTime: "2026-08-03T10:00:00Z" },
          { id: "2", eventTime: "2026-08-03T11:00:00Z" },
        ] } },
        { data: { items: [{ id: "1", eventTime: "2026-08-03T12:00:00Z" }] } },
      ],
    )

    expect(result.eqp.map((item) => item.id)).toEqual(["1", "2"])
    expect(result.tip.map((item) => item.id)).toEqual(["1"])
  })

  it("같은 log type의 가장 마지막 page 상태를 우선한다", () => {
    const state = getLatestObserverLogPageState(
      "eqp",
      { eqp: { nextCursor: "initial", hasMore: true } },
      [
        { logKey: "eqp", cursor: "initial" },
        { logKey: "tip", cursor: "tip" },
        { logKey: "eqp", cursor: "next" },
      ],
      [
        { data: { page: { nextCursor: "next", hasMore: true } } },
        { data: { page: { nextCursor: null, hasMore: false } } },
        { data: { page: { nextCursor: "last", hasMore: false } } },
      ],
    )

    expect(state).toEqual({ cursor: "last", hasMore: false })
  })

  it("EQP와 날짜 옵션으로 scope key를 만들고 일시 오류만 한 번 재시도한다", () => {
    expect(buildObserverLogScopeKey("EQ1", { startDate: "2026-08-01" }))
      .toBe('["EQ1",{"startDate":"2026-08-01"}]')
    expect(shouldRetryObserverLogQuery(0, { status: 503 })).toBe(true)
    expect(shouldRetryObserverLogQuery(0, { status: 400 })).toBe(false)
    expect(shouldRetryObserverLogQuery(1, { status: 503 })).toBe(false)
  })
})
