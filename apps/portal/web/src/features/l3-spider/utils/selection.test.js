import { describe, expect, it } from "vitest"

import {
  buildLineNameAvailabilityFromTree,
  createLeafSelectionFromSearchParams,
  createSelectionFromSearchParams,
  sortLineNames,
} from "./selection"

describe("L3 Spider URL 선택 계약", () => {
  it("camelCase와 snake_case query 값을 중복 없이 함께 읽는다", () => {
    const selection = createSelectionFromSearchParams(new URLSearchParams(
      "date=2026-08-03&lineId=L1&line_ids=L1,L2&processId=P1&eds_step=EDS1",
    ))

    expect(selection.date).toBe("2026-08-03")
    expect([...selection.lineIds]).toEqual(["L1", "L2"])
    expect([...selection.processIds]).toEqual(["P1"])
    expect([...selection.edsSteps]).toEqual(["EDS1"])
  })

  it("leaf query를 chart 분석 상태로 변환한다", () => {
    expect(createLeafSelectionFromSearchParams(new URLSearchParams(
      "edsStep=EDS1&stepSeq=100&ppid=PP1&eqpch=EQ1&binName=BIN1",
    ))).toEqual({
      checkedStep: "EDS1|||100",
      checkedPpid: "PP1",
      checkedEqc: "EQ1",
      checkedBin: "BIN1",
      analysisMode: "bin",
    })
  })

  it("빈 branch를 제외하고 line name availability를 만든다", () => {
    expect(buildLineNameAvailabilityFromTree({
      LINE_A: { P1: { EDS1: { 100: {} }, EMPTY: {} } },
      EMPTY_LINE: {},
    })).toEqual({ LINE_A: { P1: ["EDS1"] } })
  })

  it("EndFab을 마지막에 두고 나머지는 자연 정렬한다", () => {
    expect(sortLineNames(["End_Fab", "LINE10", "LINE2"])).toEqual([
      "LINE2",
      "LINE10",
      "End_Fab",
    ])
  })
})
