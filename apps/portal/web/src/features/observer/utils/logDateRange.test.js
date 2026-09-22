import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  buildLogDateRangeOptions,
  getLogRangeFromSearchParams,
  normalizeLogRange,
} from "./logDateRange"

describe("Observer 로그 날짜 범위", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-08-03T03:00:00Z"))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("역전된 값과 허용 범위를 canonical 범위로 정리한다", () => {
    expect(normalizeLogRange({ startDaysAgo: 1, endDaysAgo: 200 })).toEqual({
      startDaysAgo: 90,
      endDaysAgo: 1,
    })
  })

  it("서울 날짜 기준으로 backend from/to query를 만든다", () => {
    expect(buildLogDateRangeOptions({ startDaysAgo: 3, endDaysAgo: 1 })).toEqual({
      from: "2026-08-01",
      to: "2026-08-03",
    })
  })

  it("legacy date query와 from/to query를 같은 범위로 읽는다", () => {
    expect(getLogRangeFromSearchParams(new URLSearchParams("date=2026-08-02"))).toEqual({
      startDaysAgo: 2,
      endDaysAgo: 2,
    })
  })
})
