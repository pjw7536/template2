import { describe, expect, it } from "vitest"

import {
  buildLogRangeSearch,
  getObserverEquipmentPath,
  isObserverEquipmentPath,
} from "./observerLocation"

describe("Observer URL 동기화", () => {
  it("기존 query를 유지하면서 날짜 범위만 canonical 값으로 맞춘다", () => {
    expect(buildLogRangeSearch("?tab=logs&from=2026-08-01", {
      from: "2026-08-02",
      to: "2026-08-03",
    })).toBe("?tab=logs&from=2026-08-02&to=2026-08-03")
  })

  it("이미 같은 날짜 범위면 navigation을 만들지 않는다", () => {
    expect(buildLogRangeSearch("?from=2026-08-01&to=2026-08-03", {
      from: "2026-08-01",
      to: "2026-08-03",
    })).toBeNull()
  })

  it("설비 선택 유무를 Observer route로 변환한다", () => {
    expect(getObserverEquipmentPath(" EQP-01 ")).toBe("/observer/EQP-01")
    expect(getObserverEquipmentPath("")).toBe("/observer")
    expect(isObserverEquipmentPath("/observer/EQP-01")).toBe(true)
    expect(isObserverEquipmentPath("/observer")).toBe(false)
  })
})
