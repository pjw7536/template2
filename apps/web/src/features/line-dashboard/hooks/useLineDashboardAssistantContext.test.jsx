import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useLineDashboardAssistantContext } from "./useLineDashboardAssistantContext"

const contextMocks = vi.hoisted(() => ({
  clearPageContext: vi.fn(),
  registerPageContext: vi.fn(),
}))

vi.mock("@/lib/assistant/pageContext", () => ({
  usePageAssistantContext: () => contextMocks,
}))

describe("useLineDashboardAssistantContext", () => {
  beforeEach(() => {
    contextMocks.clearPageContext.mockReset()
    contextMocks.registerPageContext.mockReset()
  })

  it("현재 status 표의 라인·날짜·필터 범위를 page context에 등록한다", () => {
    const { unmount } = renderHook(() =>
      useLineDashboardAssistantContext({
        view: "status",
        lineId: " L1 ",
        from: "2026-08-15",
        to: "2026-08-15",
        lineFilterMode: "target_user_sdwt_prod",
        recentHoursStart: 8,
        recentHoursEnd: 0,
      }),
    )

    expect(contextMocks.registerPageContext).toHaveBeenLastCalledWith({
      kind: "line-dashboard",
      key: "line-dashboard:v1",
      scope: {
        view: "status",
        lineId: "L1",
        from: "2026-08-15",
        to: "2026-08-15",
        lineFilterMode: "target_user_sdwt_prod",
        recentHoursStart: 8,
        recentHoursEnd: 0,
      },
    })

    unmount()
    expect(contextMocks.clearPageContext).toHaveBeenCalledWith("line-dashboard:v1")
  })
})
