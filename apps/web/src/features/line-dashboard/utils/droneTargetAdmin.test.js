import { describe, expect, it } from "vitest"

import {
  normalizeDroneTargetAdminCount,
  normalizeDroneTargetAdminRow,
  normalizeDroneTargetAdminRows,
} from "./droneTargetAdmin"

describe("Line Dashboard target 관리자 응답 정규화", () => {
  it("식별자와 연결 count를 안정적인 숫자로 정규화한다", () => {
    expect(normalizeDroneTargetAdminRow({
      id: "5",
      lineId: " L1 ",
      targetUserSdwtProd: " ETCH_A ",
      mappingCount: "3",
      recipientCount: null,
      hasNeedToSendRule: 1,
    })).toEqual(expect.objectContaining({
      id: 5,
      lineId: "L1",
      targetUserSdwtProd: "ETCH_A",
      mappingCount: 3,
      recipientCount: 0,
      hasNeedToSendRule: true,
    }))
  })

  it("유효하지 않은 행은 목록 계약에서 제외한다", () => {
    expect(normalizeDroneTargetAdminRows([
      { id: 0, lineId: "L1" },
      null,
      { id: 9, lineId: "L2", targetUserSdwtProd: "PHOTO_A" },
    ])).toEqual([
      expect.objectContaining({ id: 9, lineId: "L2" }),
    ])
  })

  it("잘못된 row count는 0으로 처리한다", () => {
    expect(normalizeDroneTargetAdminCount("12")).toBe(12)
    expect(normalizeDroneTargetAdminCount("unknown")).toBe(0)
  })
})
