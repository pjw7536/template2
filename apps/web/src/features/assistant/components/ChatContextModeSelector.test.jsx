import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatContextModeSelector } from "./ChatContextModeSelector"
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
    expect(screen.getByRole("radio", { name: "현재 앱 지식만 사용" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    fireEvent.click(screen.getByRole("radio", { name: "자동 지식 선택" }))
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

    expect(screen.getByRole("radio", { name: "현재 앱 지식만 사용" })).toBeDisabled()
    expect(screen.getByRole("radio", { name: "자동 지식 선택" })).toBeDisabled()
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
      screen.getByRole("radio", { name: "현재 앱 지식만 사용" }),
    ).toBeDisabled()
    expect(screen.getByRole("radio", { name: "자동 지식 선택" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
  })
})
