import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatContextModeSelector } from "./ChatContextModeSelector"

describe("ChatContextModeSelector", () => {
  afterEach(() => cleanup())

  it("현재 앱 지식 사용 여부를 단일 switch로 전달한다", () => {
    const onChange = vi.fn()

    render(
      <ChatContextModeSelector
        usesAppContext
        onChange={onChange}
      />,
    )

    const toggle = screen.getByRole("switch", { name: "현재 앱 지식 사용" })
    expect(toggle).toHaveAttribute("aria-checked", "true")
    fireEvent.click(toggle)
    expect(onChange).toHaveBeenCalledWith(false)
  })

  it("답변 생성 중에는 모드를 변경할 수 없다", () => {
    render(
      <ChatContextModeSelector
        usesAppContext
        onChange={vi.fn()}
        disabled
      />,
    )

    expect(screen.getByRole("switch", { name: "현재 앱 지식 사용" })).toHaveAttribute(
      "aria-disabled",
      "true",
    )
  })
})
