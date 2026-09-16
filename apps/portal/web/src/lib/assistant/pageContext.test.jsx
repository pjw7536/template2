import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { PageAssistantContextProvider, usePageAssistantContext } from "./pageContext"

function ContextWrapper({ children }) {
  return <PageAssistantContextProvider>{children}</PageAssistantContextProvider>
}

describe("PageAssistantContextProvider", () => {
  it("이전 context 정리가 새 context를 제거하지 않는다", () => {
    const { result } = renderHook(() => usePageAssistantContext(), {
      wrapper: ContextWrapper,
    })

    act(() => result.current.registerPageContext({ key: "observer:a" }))
    act(() => result.current.registerPageContext({ key: "observer:b" }))
    act(() => result.current.clearPageContext("observer:a"))

    expect(result.current.pageContext).toEqual({ key: "observer:b" })
  })

  it("현재 context key로 정리하면 연결을 해제한다", () => {
    const { result } = renderHook(() => usePageAssistantContext(), {
      wrapper: ContextWrapper,
    })

    act(() => result.current.registerPageContext({ key: "observer:a" }))
    act(() => result.current.clearPageContext("observer:a"))

    expect(result.current.pageContext).toBeNull()
  })
})
