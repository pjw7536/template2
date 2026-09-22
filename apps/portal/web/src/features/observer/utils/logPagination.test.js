import { describe, expect, it } from "vitest"

import { DATA_TYPES } from "./constants"
import {
  getEnabledLogKeys,
  getLogKey,
  mergeUniqueLogItems,
} from "./logPagination"

describe("Observer log pagination", () => {
  it("활성 type filter를 API log key 순서로 변환한다", () => {
    expect(getEnabledLogKeys({
      [DATA_TYPES.EQP]: true,
      [DATA_TYPES.TIP]: false,
      [DATA_TYPES.ESOP]: true,
    })).toEqual(["eqp", "esop"])
  })

  it("compact log type을 상세 endpoint key로 변환한다", () => {
    expect(getLogKey("SPC_ITL")).toBe("spc-interlock")
    expect(getLogKey("UNKNOWN")).toBe("")
  })

  it("page 경계 중복을 제거하고 resident limit에서 중단한다", () => {
    expect(mergeUniqueLogItems([
      [{ logType: "EQP", id: 1 }, { logType: "TIP", id: 1 }],
      [{ logType: "EQP", id: 1 }, { logType: "EQP", id: 2 }],
    ], 3)).toEqual([
      { logType: "EQP", id: 1 },
      { logType: "TIP", id: 1 },
      { logType: "EQP", id: 2 },
    ])
  })
})
