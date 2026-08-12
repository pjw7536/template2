import { act, render } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { StreamingText } from "./StreamingText"

describe("StreamingText", () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("마운트 1초 후부터 글자를 순서대로 표시한다", () => {
    vi.useFakeTimers()
    const { container } = render(
      <StreamingText content="무엇을 도와드릴까요?" streamId="greeting-1" />,
    )
    const visualText = container.querySelector("[aria-hidden='true']")
    const streamingWrapper = container.firstElementChild

    expect(streamingWrapper).toHaveClass("min-h-6")
    expect(container.querySelector("[data-streaming-cursor]")).not.toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(999)
    })
    expect(visualText).toBeEmptyDOMElement()
    expect(container.querySelector("[data-streaming-cursor]")).not.toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(container.querySelector("[data-streaming-cursor]")).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(visualText).toHaveTextContent("무엇")
    expect(container.querySelector("[data-streaming-cursor]")).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(400)
    })
    expect(visualText).toHaveTextContent("무엇을 도와드릴까요?")
    expect(container.querySelector("[data-streaming-cursor]")).not.toBeInTheDocument()
    expect(streamingWrapper).toHaveClass("min-h-6")
  })

  it("마운트 이전에 흐른 시간과 관계없이 1초를 기다린다", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-08-11T00:00:00Z"))
    const streamId = "greeting-delayed"
    vi.advanceTimersByTime(5_000)
    const { container } = render(
      <StreamingText content="무엇을 도와드릴까요?" streamId={streamId} />,
    )
    const visualText = container.querySelector("[aria-hidden='true']")

    expect(container.querySelector("[data-streaming-cursor]")).not.toBeInTheDocument()
    expect(visualText).not.toHaveTextContent("무엇을 도와드릴까요?")

    act(() => {
      vi.advanceTimersByTime(1_000)
    })
    expect(container.querySelector("[data-streaming-cursor]")).toBeInTheDocument()
  })

  it("기존 대화방 인사말도 같은 높이로 즉시 표시한다", () => {
    const { container } = render(<StreamingText content="무엇을 도와드릴까요?" />)
    const streamingWrapper = container.firstElementChild
    const visualText = container.querySelector("[aria-hidden='true']")

    expect(streamingWrapper).toHaveClass("min-h-6")
    expect(visualText).toHaveTextContent("무엇을 도와드릴까요?")
    expect(container.querySelector("[data-streaming-cursor]")).not.toBeInTheDocument()
  })
})
