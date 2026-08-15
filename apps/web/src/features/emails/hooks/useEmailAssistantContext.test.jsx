import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useEmailAssistantContext } from "./useEmailAssistantContext"

const contextMocks = vi.hoisted(() => ({
  clearPageContext: vi.fn(),
  registerPageContext: vi.fn(),
}))

vi.mock("@/lib/assistant/pageContext", () => ({
  usePageAssistantContext: () => contextMocks,
}))

describe("useEmailAssistantContext", () => {
  beforeEach(() => {
    contextMocks.clearPageContext.mockReset()
    contextMocks.registerPageContext.mockReset()
  })

  it("현재 mailbox와 선택 Email ID만 page context로 등록한다", () => {
    const { rerender, unmount } = renderHook(
      ({ emailId }) => useEmailAssistantContext({
        scope: "inbox",
        mailbox: "ETCH_A",
        emailId,
      }),
      { initialProps: { emailId: 17 } },
    )

    expect(contextMocks.registerPageContext).toHaveBeenLastCalledWith(
      expect.objectContaining({
        kind: "emails",
        scope: { mailbox: "ETCH_A", emailId: "17" },
      }),
    )

    rerender({ emailId: null })
    expect(contextMocks.registerPageContext).toHaveBeenLastCalledWith(
      expect.objectContaining({ scope: { mailbox: "ETCH_A" } }),
    )
    unmount()
    expect(contextMocks.clearPageContext).toHaveBeenCalledWith("emails:v1")
  })
})
