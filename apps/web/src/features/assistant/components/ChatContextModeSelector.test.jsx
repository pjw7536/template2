import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatContextModeSelector, ChatKnowledgeToggle } from "./ChatContextModeSelector"
import { ASSISTANT_KNOWLEDGE_MODES } from "../utils/profileKeys"

describe("ChatContextModeSelector", () => {
  afterEach(() => cleanup())

  it("현재 앱 전용과 자동 선택 모드를 명시적으로 표시한다", () => {
    const onChange = vi.fn()

    render(
      <ChatContextModeSelector
        appLabel="Appstore"
        mode={ASSISTANT_KNOWLEDGE_MODES.currentApp}
        onChange={onChange}
      />,
    )

    expect(screen.getByRole("radiogroup", { name: "App Store 지식 선택 모드" })).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "현재 화면" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    fireEvent.click(screen.getByRole("radio", { name: "자동" }))
    expect(onChange).toHaveBeenCalledWith(ASSISTANT_KNOWLEDGE_MODES.auto)
  })

  it("답변 생성 중에는 모드를 변경할 수 없다", () => {
    render(
      <ChatContextModeSelector
        appLabel="Observer"
        mode={ASSISTANT_KNOWLEDGE_MODES.currentApp}
        onChange={vi.fn()}
        disabled
      />,
    )

    expect(screen.getByRole("radio", { name: "현재 화면" })).toBeDisabled()
    expect(screen.getByRole("radio", { name: "자동" })).toBeDisabled()
  })

  it("현재 앱 조건이 없으면 현재 앱 전용 모드만 비활성화한다", () => {
    render(
      <ChatContextModeSelector
        appLabel="Emails"
        mode={ASSISTANT_KNOWLEDGE_MODES.auto}
        onChange={vi.fn()}
        currentAppReady={false}
      />,
    )

    expect(
      screen.getByRole("radio", { name: "현재 화면" }),
    ).toBeDisabled()
    expect(screen.getByRole("radio", { name: "자동" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
  })

  it("Portal switch는 ON/OFF를 자동과 일반 전용 모드로 전달하고 전송 중 비활성화한다", () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <ChatKnowledgeToggle checked onChange={onChange} />,
    )

    const toggle = screen.getByRole("switch", { name: "업무 지식 자동 사용" })
    expect(toggle).toHaveAttribute("aria-checked", "true")
    fireEvent.click(toggle)
    expect(onChange).toHaveBeenCalledWith(ASSISTANT_KNOWLEDGE_MODES.generalOnly)

    rerender(<ChatKnowledgeToggle checked onChange={onChange} disabled />)
    expect(toggle).toBeDisabled()
  })
})
