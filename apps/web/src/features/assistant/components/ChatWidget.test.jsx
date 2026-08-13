import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, useNavigate } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ChatWidget } from "./ChatWidget"

const chatSessionMocks = vi.hoisted(() => ({
  createRoom: vi.fn(),
  pageContext: null,
  user: { id: 10 },
  useChatSession: vi.fn(),
}))

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: chatSessionMocks.user }),
}))

vi.mock("@/lib/assistant/pageContext", () => ({
  usePageAssistantContext: () => ({ pageContext: chatSessionMocks.pageContext }),
}))

vi.mock("../hooks/useAttentionTooltip", () => ({
  useAttentionTooltip: () => ({
    isAttentionTooltipVisible: false,
    attentionTooltipText: "",
  }),
}))

vi.mock("../hooks/useAssistantRagIndex", () => ({
  useAssistantRagIndex: () => ({ permissionGroups: [], ragIndexNames: [] }),
}))

vi.mock("../hooks/useChatSession", () => ({
  useChatSession: (...args) => chatSessionMocks.useChatSession(...args),
}))

function createChatSessionResult() {
  return {
    rooms: [],
    roomListRooms: [],
    roomSearch: "",
    showArchived: false,
    hasMoreRooms: false,
    isLoadingMoreRooms: false,
    activeRoomId: null,
    messages: [],
    messagesByRoom: {},
    isSending: false,
    isGenerating: false,
    hasActiveGeneration: false,
    generationRoomId: null,
    isRoomListBusy: false,
    errorMessage: "",
    canRetry: false,
    createRoom: chatSessionMocks.createRoom,
  }
}

vi.mock("./ChatWidgetLauncher", () => ({
  ChatWidgetLauncher: ({ onClick }) => (
    <button type="button" onClick={onClick}>위젯 열기</button>
  ),
}))

vi.mock("./ChatWidgetPanel", () => ({
  ChatWidgetPanel: ({
    onClose,
    isSidebarOpen,
    onToggleSidebar,
    sidebarWidth,
    sidebarMinWidth,
    sidebarMaxWidth,
    onSidebarResizePointerDown,
    onSidebarResizeKeyDown,
    activeAppContext,
    usesAppContext,
    onUsesAppContextChange,
  }) => (
    <div>
      <span>{activeAppContext?.label || "Portal"}</span>
      <button
        type="button"
        role="radio"
        aria-checked={!usesAppContext}
        onClick={() => onUsesAppContextChange(false)}
      >
        일반 대화
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={usesAppContext}
        onClick={() => onUsesAppContextChange(true)}
      >
        {activeAppContext?.label || "Portal"} 지식 사용
      </button>
      <button type="button" onClick={onClose}>위젯 닫기</button>
      <button type="button" onClick={onToggleSidebar}>목록 전환</button>
      {isSidebarOpen ? (
        <div
          role="separator"
          aria-label="대화방 목록 너비 조절"
          aria-valuemin={sidebarMinWidth}
          aria-valuemax={sidebarMaxWidth}
          aria-valuenow={sidebarWidth}
          tabIndex={0}
          onPointerDown={onSidebarResizePointerDown}
          onKeyDown={onSidebarResizeKeyDown}
        />
      ) : null}
    </div>
  ),
}))

function ChatWidgetRouteHarness() {
  const navigate = useNavigate()

  return (
    <>
      <button type="button" onClick={() => navigate("/emails/inbox")}>Emails로 이동</button>
      <button type="button" onClick={() => navigate("/appstore")}>Appstore로 이동</button>
      <ChatWidget />
    </>
  )
}

describe("ChatWidget 대화방 생성", () => {
  beforeEach(() => {
    chatSessionMocks.createRoom.mockReset()
    chatSessionMocks.pageContext = null
    chatSessionMocks.user = { id: 10 }
    chatSessionMocks.useChatSession.mockReset()
    chatSessionMocks.useChatSession.mockImplementation(createChatSessionResult)
  })

  afterEach(() => cleanup())

  it("빈 상태에서 위젯을 열고 닫아도 대화방을 생성하지 않는다", () => {
    render(
      <MemoryRouter>
        <ChatWidget />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("button", { name: "위젯 닫기" }))
    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))

    expect(chatSessionMocks.createRoom).not.toHaveBeenCalled()
  })

  it("Assistant 전체 페이지에서는 Widget session을 만들지 않는다", () => {
    render(
      <MemoryRouter initialEntries={["/assistant"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).not.toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: "위젯 열기" })).not.toBeInTheDocument()
  })

  it("인증 사용자가 없으면 비저장 session으로 대신 실행하지 않는다", () => {
    chatSessionMocks.user = null

    render(
      <MemoryRouter>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).not.toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: "위젯 열기" })).not.toBeInTheDocument()
  })

  it("현재 앱을 Portal 공용 기억의 contextKey로 전달한다", () => {
    render(
      <MemoryRouter initialEntries={["/appstore"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).toHaveBeenCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:appstore",
      }),
    )
    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    expect(screen.getByText("Appstore")).toBeInTheDocument()
  })

  it("일반 대화를 선택하면 현재 대화방의 이후 Turn을 일반 surface로 전환한다", () => {
    render(
      <MemoryRouter initialEntries={["/appstore"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("radio", { name: "일반 대화" }))

    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:assistant",
        profileKey: "portal-default",
        profileToolInputs: {},
      }),
    )
  })

  it("앱을 이동하면 해당 앱 지식 사용을 기본값으로 다시 선택한다", () => {
    render(
      <MemoryRouter initialEntries={["/appstore"]}>
        <ChatWidgetRouteHarness />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("radio", { name: "일반 대화" }))
    fireEvent.click(screen.getByRole("button", { name: "Emails로 이동" }))

    expect(screen.getByRole("radio", { name: "Emails 지식 사용" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({ profileKey: "email-rag" }),
    )

    fireEvent.click(screen.getByRole("button", { name: "Appstore로 이동" }))

    expect(screen.getByRole("radio", { name: "Appstore 지식 사용" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:appstore",
        profileKey: "portal-default",
      }),
    )
  })

  it("Emails는 Portal 대화방을 유지하면서 Email RAG contextKey를 사용한다", () => {
    render(
      <MemoryRouter initialEntries={["/emails/inbox"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).toHaveBeenCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant",
        profileKey: "email-rag",
      }),
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("radio", { name: "일반 대화" }))

    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:assistant",
        profileKey: "portal-default",
        profileToolInputs: {},
      }),
    )
  })

  it("Observer 문맥 등록 전에는 Portal Profile로 대신 실행하지 않는다", () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/observer/EQP-01"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).not.toHaveBeenCalled()

    chatSessionMocks.pageContext = {
      kind: "observer",
      key: `observer:v1:${"a".repeat(64)}`,
      scope: { eqpId: "EQP-01" },
    }
    rerender(
      <MemoryRouter initialEntries={["/observer/EQP-01"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).toHaveBeenCalledWith(
      expect.objectContaining({
        messageContextKey: `observer:v1:${"a".repeat(64)}`,
        profileKey: "observer-analysis",
      }),
    )
  })

  it("대화방 목록 구분선을 드래그해 사이드바 너비를 조절한다", () => {
    render(
      <MemoryRouter>
        <ChatWidget />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("button", { name: "목록 전환" }))

    const separator = screen.getByRole("separator", { name: "대화방 목록 너비 조절" })
    expect(separator).toHaveAttribute("aria-valuenow", "208")

    fireEvent.pointerDown(separator, { clientX: 300, pointerId: 1 })
    fireEvent.pointerMove(document, { clientX: 364, pointerId: 1 })
    fireEvent.pointerUp(document, { pointerId: 1 })

    expect(separator).toHaveAttribute("aria-valuenow", "272")
  })

  it("키보드로 사이드바 너비를 단계 조절하고 최댓값으로 이동한다", () => {
    render(
      <MemoryRouter>
        <ChatWidget />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("button", { name: "목록 전환" }))

    const separator = screen.getByRole("separator", { name: "대화방 목록 너비 조절" })
    fireEvent.keyDown(separator, { key: "ArrowRight" })
    expect(separator).toHaveAttribute("aria-valuenow", "224")

    fireEvent.keyDown(separator, { key: "End" })
    expect(separator).toHaveAttribute("aria-valuenow", "360")
  })
})
