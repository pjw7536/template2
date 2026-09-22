import { describe, expect, it } from "vitest"

import {
  hasAppOrderChanged,
  moveAppById,
  moveAppInOrder,
  moveAppWithinCategory,
} from "./appOrder"

const APPS = [{ id: 1 }, { id: 2 }, { id: 3 }]

describe("appOrder", () => {
  it("앱을 지정한 위치로 이동한다", () => {
    expect(moveAppInOrder(APPS, 2, 0).map((app) => app.id)).toEqual([3, 1, 2])
  })

  it("목록 범위를 벗어난 이동은 원본 순서를 유지한다", () => {
    expect(moveAppInOrder(APPS, 0, -1)).toBe(APPS)
    expect(moveAppInOrder(APPS, 2, 3)).toBe(APPS)
  })

  it("초기 순서와 draft 순서의 변경 여부를 판정한다", () => {
    expect(hasAppOrderChanged(APPS, APPS)).toBe(false)
    expect(hasAppOrderChanged(APPS, [APPS[1], APPS[0], APPS[2]])).toBe(true)
  })

  it("드래그한 앱을 대상 앱 위치로 이동한다", () => {
    expect(moveAppById(APPS, 3, 1).map((app) => app.id)).toEqual([3, 1, 2])
  })

  it("카테고리 앱만 기존 전역 슬롯 안에서 재배치한다", () => {
    const apps = [
      { id: 1, category: "X" },
      { id: 2, category: "Y" },
      { id: 3, category: "X" },
      { id: 4, category: "Y" },
      { id: 5, category: "X" },
    ]

    const result = moveAppWithinCategory(apps, 5, 1, "X")

    expect(result.map((app) => app.id)).toEqual([5, 2, 1, 4, 3])
    expect(result.filter((app) => app.category === "X").map((app) => app.id)).toEqual([5, 1, 3])
  })

  it("전체 카테고리에서는 전역 순서를 재배치한다", () => {
    expect(moveAppWithinCategory(APPS, 3, 1, "all").map((app) => app.id)).toEqual([3, 1, 2])
  })
})
