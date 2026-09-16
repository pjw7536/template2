import { describe, expect, it } from "vitest"

import {
  buildEmailMoveTargets,
  clampEmailListWidth,
  parseRoutedEmailId,
} from "./inboxController"

describe("Emails inbox controller helper", () => {
  it("숫자 ID와 RAG email ID를 같은 canonical ID로 해석한다", () => {
    expect(parseRoutedEmailId("42")).toBe(42)
    expect(parseRoutedEmailId("email-42")).toBe(42)
    expect(parseRoutedEmailId("email-invalid")).toBeNull()
    expect(parseRoutedEmailId("0")).toBeNull()
  })

  it("목록 폭을 list/detail 최소 폭 사이로 제한한다", () => {
    const container = { getBoundingClientRect: () => ({ width: 1200 }) }

    expect(clampEmailListWidth(100, container)).toBe(600)
    expect(clampEmailListWidth(900, container)).toBe(764)
    expect(clampEmailListWidth(700, container)).toBe(700)
  })

  it("현재·보낸·미분류 mailbox를 제외한 중복 없는 이동 대상을 만든다", () => {
    expect(buildEmailMoveTargets(
      ["ETCH_A", "PHOTO_A", "PHOTO_A", "__sent__", "UNASSIGNED"],
      "ETCH_A",
    )).toEqual([{ value: "PHOTO_A", label: "PHOTO_A" }])
  })
})
