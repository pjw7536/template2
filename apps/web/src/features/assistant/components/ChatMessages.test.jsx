import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, useLocation } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ChatMessages } from "./ChatMessages"

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="현재 위치">{`${location.pathname}${location.search}`}</output>
}

describe("ChatMessages 문맥과 과거 이력", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => cleanup())

  it("contextKey가 바뀐 위치에만 조회 조건 변경 구분선을 표시한다", () => {
    render(
      <MemoryRouter>
        <ChatMessages
          messages={[
            { id: "user-1", role: "user", content: "첫 질문", contextKey: "observer:a" },
            { id: "assistant-1", role: "assistant", content: "첫 답변", contextKey: "observer:a" },
            { id: "user-2", role: "user", content: "다음 질문", contextKey: "observer:b" },
          ]}
        />
      </MemoryRouter>,
    )

    expect(screen.getAllByText("조회 조건 또는 대화 모드가 변경되었습니다.")).toHaveLength(1)
  })

  it("이전 메시지 불러오기 동작을 부모 handler에 전달한다", () => {
    const onLoadOlderMessages = vi.fn()
    render(
      <MemoryRouter>
        <ChatMessages
          messages={[]}
          hasOlderMessages
          onLoadOlderMessages={onLoadOlderMessages}
        />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "이전 메시지 불러오기" }))
    expect(onLoadOlderMessages).toHaveBeenCalledOnce()
  })

  it("이전 메시지 요청 실패 후 새 답변이 와도 오래된 scroll anchor를 적용하지 않는다", async () => {
    const onLoadOlderMessages = vi.fn().mockResolvedValue({ ok: false, addedCount: 0 })
    const { rerender } = render(
      <MemoryRouter>
        <ChatMessages
          messages={[{ id: "assistant-1", role: "assistant", content: "첫 답변" }]}
          hasOlderMessages
          onLoadOlderMessages={onLoadOlderMessages}
        />
      </MemoryRouter>,
    )
    const messageLog = screen.getByRole("log", { name: "대화 메시지" })
    let scrollHeight = 1000
    Object.defineProperties(messageLog, {
      scrollHeight: { configurable: true, get: () => scrollHeight },
      clientHeight: { configurable: true, value: 300 },
      scrollTop: { configurable: true, value: 100, writable: true },
    })

    fireEvent.click(screen.getByRole("button", { name: "이전 메시지 불러오기" }))
    await waitFor(() => expect(onLoadOlderMessages).toHaveBeenCalledOnce())
    scrollHeight = 1300
    rerender(
      <MemoryRouter>
        <ChatMessages
          messages={[
            { id: "assistant-1", role: "assistant", content: "첫 답변" },
            { id: "assistant-2", role: "assistant", content: "새 답변" },
          ]}
        />
      </MemoryRouter>,
    )

    expect(messageLog.scrollTop).toBe(100)
  })

  it("사용자가 이전 내용을 읽는 동안 새 답변이 와도 하단으로 강제 이동하지 않는다", () => {
    const { rerender } = render(
      <MemoryRouter>
        <ChatMessages
          messages={[{ id: "assistant-1", role: "assistant", content: "첫 답변" }]}
        />
      </MemoryRouter>,
    )
    const messageLog = screen.getByRole("log", { name: "대화 메시지" })
    Object.defineProperties(messageLog, {
      scrollHeight: { configurable: true, value: 1000 },
      clientHeight: { configurable: true, value: 300 },
      scrollTop: { configurable: true, value: 100, writable: true },
    })
    fireEvent.scroll(messageLog)

    rerender(
      <MemoryRouter>
        <ChatMessages
          messages={[
            { id: "assistant-1", role: "assistant", content: "첫 답변" },
            { id: "assistant-2", role: "assistant", content: "새 답변" },
          ]}
          isGenerating
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole("button", { name: "최신 답변으로 이동" })).toBeInTheDocument()
  })

  it("최초 인사 메시지에는 복사 action을 표시하지 않는다", () => {
    render(
      <MemoryRouter>
        <ChatMessages
          messages={[
            {
              id: "greeting",
              role: "assistant",
              content: "무엇을 도와드릴까요?",
              isGreeting: true,
            },
          ]}
        />
      </MemoryRouter>,
    )

    expect(screen.queryByRole("button", { name: "메시지 복사" })).not.toBeInTheDocument()
  })

  it("질문 수정과 답변 재생성·평가 동작을 부모 handler에 전달한다", async () => {
    const onEditMessage = vi.fn().mockResolvedValue({ ok: true })
    const onRegenerateMessage = vi.fn()
    const onRateMessage = vi.fn()
    render(
      <MemoryRouter>
        <ChatMessages
          messages={[
            { id: "user-1", role: "user", content: "원본 질문" },
            { id: "assistant-1", role: "assistant", content: "원본 답변" },
          ]}
          onEditMessage={onEditMessage}
          onRegenerateMessage={onRegenerateMessage}
          onRateMessage={onRateMessage}
        />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "메시지 수정" }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    const editInput = screen.getByRole("textbox", { name: "메시지 수정 입력" })
    expect(editInput).toHaveValue("원본 질문")
    fireEvent.change(editInput, { target: { value: "수정 질문" } })
    fireEvent.click(screen.getByRole("button", { name: "수정 후 다시 생성" }))
    expect(onEditMessage).toHaveBeenCalledWith("user-1", "수정 질문")
    await waitFor(() => {
      expect(screen.queryByRole("textbox", { name: "메시지 수정 입력" })).not.toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: "답변 다시 생성" }))
    expect(onRegenerateMessage).toHaveBeenCalledWith("assistant-1")
    fireEvent.click(screen.getByRole("button", { name: "도움됨" }))
    expect(onRateMessage).toHaveBeenCalledWith("assistant-1", "up")
  })

  it("다른 대화방에서 답변 생성 중이면 수정과 재생성만 비활성화한다", () => {
    render(
      <MemoryRouter>
        <ChatMessages
          messages={[
            { id: "user-1", role: "user", content: "원본 질문" },
            { id: "assistant-1", role: "assistant", content: "원본 답변" },
          ]}
          isActionDisabled
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole("button", { name: "메시지 수정" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "답변 다시 생성" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "도움됨" })).toBeEnabled()
  })

  it("질문 수정 요청이 거절되면 인라인 편집창과 입력값을 유지한다", async () => {
    const onEditMessage = vi.fn().mockResolvedValue({ ok: false })
    render(
      <MemoryRouter>
        <ChatMessages
          messages={[{ id: "user-1", role: "user", content: "원본 질문" }]}
          onEditMessage={onEditMessage}
        />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "메시지 수정" }))
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "수정 질문" } })
    fireEvent.click(screen.getByRole("button", { name: "수정 후 다시 생성" }))

    await waitFor(() => expect(onEditMessage).toHaveBeenCalledOnce())
    expect(screen.getByRole("textbox", { name: "메시지 수정 입력" })).toHaveValue("수정 질문")
  })

  it("인라인 편집에서 단축키와 취소 동작을 처리한다", async () => {
    const onEditMessage = vi.fn().mockResolvedValue({ ok: true })
    render(
      <MemoryRouter>
        <ChatMessages
          messages={[{ id: "user-1", role: "user", content: "원본 질문" }]}
          onEditMessage={onEditMessage}
        />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "메시지 수정" }))
    let editInput = screen.getByRole("textbox", { name: "메시지 수정 입력" })
    fireEvent.change(editInput, { target: { value: "첫 줄\n둘째 줄" } })
    fireEvent.keyDown(editInput, { key: "Enter", shiftKey: true })
    expect(onEditMessage).not.toHaveBeenCalled()

    fireEvent.keyDown(editInput, { key: "Escape" })
    expect(screen.queryByRole("textbox", { name: "메시지 수정 입력" })).not.toBeInTheDocument()
    expect(screen.getByText("원본 질문")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "메시지 수정" }))
    editInput = screen.getByRole("textbox", { name: "메시지 수정 입력" })
    fireEvent.change(editInput, { target: { value: "Enter로 제출" } })
    fireEvent.keyDown(editInput, { key: "Enter" })

    await waitFor(() => {
      expect(onEditMessage).toHaveBeenCalledWith("user-1", "Enter로 제출")
    })
  })

  it("편집 대상 메시지가 목록에서 사라지면 편집 상태를 종료한다", () => {
    const { rerender } = render(
      <MemoryRouter>
        <ChatMessages
          messages={[{ id: "user-1", role: "user", content: "원본 질문" }]}
          onEditMessage={vi.fn()}
        />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "메시지 수정" }))
    expect(screen.getByRole("textbox", { name: "메시지 수정 입력" })).toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <ChatMessages messages={[]} onEditMessage={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.queryByRole("textbox", { name: "메시지 수정 입력" })).not.toBeInTheDocument()
  })

  it("분석 당시 범위와 버전을 표시하고 근거 로그 위치로 이동한다", () => {
    const evidenceHref =
      "/observer/EQP-1?from=2026-08-01&to=2026-08-03&evidenceId=EQP%3A1&analysisLogType=EQP"
    render(
      <MemoryRouter initialEntries={["/observer/EQP-2"]}>
        <ChatMessages
          currentPageScope={{
            eqpId: "EQP-2",
            from: "2026-08-10",
            to: "2026-08-11",
            logTypes: ["EQP"],
          }}
          messages={[
            {
              id: "assistant-evidence",
              role: "assistant",
              content: "분석 결과",
              contextSnapshot: {
                scope: {
                  eqpId: "EQP-1",
                  from: "2026-08-01",
                  to: "2026-08-03",
                  logTypes: ["EQP"],
                },
                coverage: {
                  analysisModel: "gpt-oss-120b",
                  promptVersion: "observer-analysis-prompt-v1",
                },
                evidence: [
                  {
                    category: "EQP",
                    target: "DOWN",
                    evidenceTargets: [{ id: "EQP:1", href: evidenceHref }],
                  },
                ],
              },
            },
          ]}
        />
        <LocationProbe />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "분석 범위와 근거" }))
    expect(screen.getByText("현재 조회와 다름")).toBeInTheDocument()
    expect(screen.getByText(/gpt-oss-120b · observer-analysis-prompt-v1/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "근거 로그 EQP:1 열기" }))
    expect(screen.getByLabelText("현재 위치")).toHaveTextContent(evidenceHref)
  })
})
