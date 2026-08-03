import { describe, expect, it } from "vitest"

import { buildVocStatusCounts, getVocPostAuthorKey } from "./postTransforms"

describe("VOC post transforms", () => {
  it("현재 화면 범위에서 상태 개수를 계산한다", () => {
    const counts = buildVocStatusCounts([
      { status: "접수" },
      { status: "접수" },
      { status: "완료" },
    ])

    expect(counts).toEqual({ 접수: 2, 진행중: 0, 완료: 1, 반려: 0 })
  })

  it("권한 비교에는 canonical author id만 사용한다", () => {
    expect(getVocPostAuthorKey({ author: { id: 7, name: "사용자" } })).toBe(7)
    expect(getVocPostAuthorKey({ author: { name: "legacy" } })).toBeNull()
  })
})
