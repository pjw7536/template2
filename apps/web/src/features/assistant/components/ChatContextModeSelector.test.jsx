import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatContextModeSelector } from "./ChatContextModeSelector"

describe("ChatContextModeSelector", () => {
  afterEach(() => cleanup())

  it("사용할 앱 지식 이름과 Switch 상태를 표시하고 일반 대화 전환을 알린다", () => {
    const onChange = vi.fn()

    render(
      <ChatContextModeSelector
        appLabel="Appstore"
        usesAppContext
        onChange={onChange}
      />,
    )

    expect(screen.getByText("App Store 지식 사용")).toBeInTheDocument()
    const knowledgeSwitch = screen.getByRole("switch", { name: "App Store 지식 사용" })
    expect(knowledgeSwitch).toHaveAttribute("aria-checked", "true")
    fireEvent.click(knowledgeSwitch)
    expect(onChange).toHaveBeenCalledWith(false)
  })

  it("답변 생성 중에는 모드를 변경할 수 없다", () => {
    render(
      <ChatContextModeSelector
        appLabel="Observer"
        usesAppContext
        onChange={vi.fn()}
        disabled
      />,
    )

    const knowledgeSwitch = screen.getByRole("switch", {
      name: "Observer 지식 사용",
    })
    expect(knowledgeSwitch).toHaveAttribute("aria-disabled", "true")
    expect(knowledgeSwitch).toHaveAttribute("tabindex", "-1")
  })
})
