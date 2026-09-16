import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatComposer } from "./ChatComposer"

describe("ChatComposer 생성 제어", () => {
  afterEach(() => cleanup())

  it("답변 생성 중에는 전송 대신 중단 동작을 제공한다", () => {
    const onStop = vi.fn()
    const onSubmit = vi.fn((event) => event.preventDefault())
    render(
      <ChatComposer
        inputId="chat-input"
        label="메시지"
        inputValue="추가 질문"
        onInputChange={vi.fn()}
        onSubmit={onSubmit}
        isSending
        isGenerating
        onStop={onStop}
      />,
    )

    expect(screen.queryByRole("button", { name: "메시지 보내기" })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "응답 중지" }))
    expect(onStop).toHaveBeenCalledOnce()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("Enter는 전송하고 Shift+Enter는 줄바꿈으로 남긴다", () => {
    const onSubmit = vi.fn((event) => event.preventDefault())
    render(
      <ChatComposer
        inputId="chat-input"
        label="메시지"
        inputValue="질문"
        onInputChange={vi.fn()}
        onSubmit={onSubmit}
        isSending={false}
      />,
    )
    const textarea = screen.getByRole("textbox", { name: "메시지" })

    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true })
    expect(onSubmit).not.toHaveBeenCalled()
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false })
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it("메시지 입력은 10,000자로 제한한다", () => {
    render(
      <ChatComposer
        inputId="chat-input"
        label="메시지"
        inputValue="질문"
        onInputChange={vi.fn()}
        onSubmit={vi.fn()}
        isSending={false}
      />,
    )

    expect(screen.getByRole("textbox", { name: "메시지" })).toHaveAttribute(
      "maxlength",
      "10000",
    )
  })
})
