import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatErrorBanner } from "./ChatErrorBanner"

describe("ChatErrorBanner 복구 동작", () => {
  afterEach(() => cleanup())

  it("저장 실패에는 구체적인 재시도 문구를 표시한다", () => {
    const onRetry = vi.fn()
    const onDiscard = vi.fn()
    render(
      <ChatErrorBanner
        message="답변 저장 실패"
        onDismiss={vi.fn()}
        canRetry
        onRetry={onRetry}
        retryLabel="답변 저장 다시 시도"
        canDiscard
        onDiscard={onDiscard}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: "답변 저장 다시 시도" }))
    fireEvent.click(screen.getByRole("button", { name: "저장하지 않고 제거" }))
    expect(onRetry).toHaveBeenCalledOnce()
    expect(onDiscard).toHaveBeenCalledOnce()
    expect(screen.queryByRole("button", { name: "닫기" })).not.toBeInTheDocument()
  })
})
