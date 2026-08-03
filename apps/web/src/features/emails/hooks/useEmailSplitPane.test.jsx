import { act, renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useEmailSplitPane } from "./useEmailSplitPane"

describe("Emails split pane hook", () => {
  it("pointer 위치를 목록 폭으로 변환하고 drag 종료 상태를 정리한다", () => {
    const { result } = renderHook(() => useEmailSplitPane())
    const container = {
      getBoundingClientRect: () => ({ left: 100, width: 1200 }),
    }
    const preventDefault = vi.fn()

    act(() => {
      result.current.splitPaneRef.current = container
      result.current.handleResizeStart({ preventDefault })
    })
    expect(result.current.isDragging).toBe(true)

    act(() => {
      window.dispatchEvent(new MouseEvent("pointermove", { clientX: 800 }))
    })
    expect(result.current.splitPaneStyles).toEqual({
      "--email-list-width": "700px",
      "--email-handle-offset": "708px",
    })

    act(() => {
      window.dispatchEvent(new MouseEvent("pointerup"))
    })
    expect(result.current.isDragging).toBe(false)
    expect(preventDefault).toHaveBeenCalledOnce()
  })
})
