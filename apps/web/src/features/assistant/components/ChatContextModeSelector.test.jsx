import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatContextModeSelector } from "./ChatContextModeSelector"

describe("ChatContextModeSelector", () => {
  afterEach(() => cleanup())

  it("앱 지식 사용을 기본 선택 상태로 표시하고 일반 대화 전환을 알린다", () => {
    const onChange = vi.fn()

    render(
      <ChatContextModeSelector
        appLabel="Appstore"
        usesAppContext
        onChange={onChange}
      />,
    )

    expect(screen.getByRole("radio", { name: "Appstore 지식 사용" })).toBeChecked()
    fireEvent.click(screen.getByRole("radio", { name: "일반 대화" }))
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

    expect(screen.getByRole("radio", { name: "일반 대화" })).toBeDisabled()
    expect(screen.getByRole("radio", { name: "Observer 지식 사용" })).toBeDisabled()
  })
})
