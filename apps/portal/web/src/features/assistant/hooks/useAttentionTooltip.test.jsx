import { StrictMode } from "react"
import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useAttentionTooltip } from "./useAttentionTooltip"

const { mockUser } = vi.hoisted(() => ({
  mockUser: { id: "user-1" },
}))

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: mockUser }),
}))

describe("useAttentionTooltip", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("Strict Mode에서도 최초 안내 문구를 끝까지 표시한다", () => {
    const { result } = renderHook(
      () => useAttentionTooltip({ isOpen: false, isHomePage: true }),
      { wrapper: StrictMode },
    )

    expect(result.current.isAttentionTooltipVisible).toBe(true)

    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(result.current.attentionTooltipText).toBe("무엇이든 물어보세요")

    act(() => {
      vi.advanceTimersByTime(2_700)
    })
    expect(result.current.isAttentionTooltipVisible).toBe(false)
    expect(result.current.attentionTooltipText).toBe("")
  })

  it("홈이 아닌 화면에서는 표시하지 않는다", () => {
    const { result } = renderHook(() =>
      useAttentionTooltip({ isOpen: false, isHomePage: false }),
    )

    expect(result.current.isAttentionTooltipVisible).toBe(false)
    expect(result.current.attentionTooltipText).toBe("")
  })

  it("홈에서 다른 화면으로 이동한 뒤 다시 홈에 들어오면 재표시한다", () => {
    const { result, rerender } = renderHook(
      ({ isHomePage }) => useAttentionTooltip({ isOpen: false, isHomePage }),
      { initialProps: { isHomePage: true } },
    )

    expect(result.current.isAttentionTooltipVisible).toBe(true)

    act(() => {
      vi.advanceTimersByTime(3_000)
    })
    expect(result.current.isAttentionTooltipVisible).toBe(false)

    rerender({ isHomePage: false })
    rerender({ isHomePage: true })

    expect(result.current.isAttentionTooltipVisible).toBe(true)
    expect(result.current.attentionTooltipText).toBe("무")
  })

  it("홈에 머무는 동안에는 단순 재렌더링으로 재표시하지 않는다", () => {
    const { result, rerender } = renderHook(
      ({ isHomePage }) => useAttentionTooltip({ isOpen: false, isHomePage }),
      { initialProps: { isHomePage: true } },
    )

    act(() => {
      vi.advanceTimersByTime(3_000)
    })
    rerender({ isHomePage: true })

    expect(result.current.isAttentionTooltipVisible).toBe(false)
    expect(result.current.attentionTooltipText).toBe("")
  })
})
