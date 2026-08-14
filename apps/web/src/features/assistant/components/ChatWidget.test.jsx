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
    isAppContextReady,
    onUsesAppContextChange,
    pageContext,
    currentPageScope,
  }) => (
    <div>
      <span>{activeAppContext?.label || "Portal"}</span>
      {pageContext ? <span>{pageContext.label || "현재 화면 데이터 연결됨"}</span> : null}
      {currentPageScope?.lineId ? <span>현재 Line: {currentPageScope.lineId}</span> : null}
      {activeAppContext?.key !== "portal" ? (
        <div>
          <button
            type="button"
            role="switch"
            aria-checked={usesAppContext}
            disabled={!isAppContextReady}
            aria-label={activeAppContext?.key === "appstore"
              ? "App Store 지식 사용"
              : `${activeAppContext?.label || "Portal"} 지식 사용`}
            onClick={() => onUsesAppContextChange(!usesAppContext)}
          />
          {activeAppContext?.key === "appstore"
            ? "App Store 지식 사용"
            : `${activeAppContext?.label || "Portal"} 지식 사용`}
        </div>
      ) : null}
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

  it("Portal 홈은 지식 선택 없이 일반 대화 surface를 사용한다", () => {
    render(
      <MemoryRouter>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:assistant",
        profileKey: "portal-default",
        profileToolInputs: {},
      }),
    )
    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    expect(
      screen.queryByRole("switch", { name: "Portal 지식 사용" }),
    ).not.toBeInTheDocument()
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

  it("현재 Appstore 화면 조건을 전용 contextKey로 전달한다", () => {
    chatSessionMocks.pageContext = {
      kind: "appstore",
      key: "appstore:v1",
      scope: { query: "", category: "all", selectedAppId: null },
    }
    render(
      <MemoryRouter initialEntries={["/appstore"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).toHaveBeenCalledWith(
      expect.objectContaining({
        messageContextKey: "appstore:v1",
        profileKey: "appstore-context",
        profileToolInputs: {
          "appstore.catalog": {
            query: "",
            category: "all",
            selectedAppId: null,
          },
        },
      }),
    )
    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    expect(screen.getByText("Appstore")).toBeInTheDocument()
  })

  it("일반 대화를 선택하면 현재 대화방의 이후 Turn을 일반 surface로 전환한다", () => {
    chatSessionMocks.pageContext = {
      kind: "appstore",
      key: "appstore:v1",
      scope: { query: "", category: "all", selectedAppId: null },
    }
    render(
      <MemoryRouter initialEntries={["/appstore"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("switch", { name: "App Store 지식 사용" }))

    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:assistant",
        profileKey: "portal-default",
        profileToolInputs: {},
      }),
    )
  })

  it("ESOP 현재 화면 조건을 snapshot Tool과 Widget page context로 전달한다", () => {
    chatSessionMocks.pageContext = {
      kind: "line-dashboard",
      key: "line-dashboard:v1",
      scope: {
        view: "history",
        lineId: "L1",
        from: "2026-08-01",
        to: "2026-08-14",
      },
    }
    render(
      <MemoryRouter initialEntries={["/ESOP_Dashboard/history/L1"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).toHaveBeenCalledWith(
      expect.objectContaining({
        messageContextKey: "line-dashboard:v1",
        profileKey: "line-dashboard-context",
        profileToolInputs: {
          "line-dashboard.snapshot": {
            view: "history",
            lineId: "L1",
            from: "2026-08-01",
            to: "2026-08-14",
          },
        },
      }),
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    expect(screen.getByText("현재 화면 데이터 연결됨")).toBeInTheDocument()
    expect(screen.getByText("현재 Line: L1")).toBeInTheDocument()
  })

  it("앱을 이동하면 해당 앱 지식 사용을 기본값으로 다시 선택한다", () => {
    chatSessionMocks.pageContext = {
      kind: "appstore",
      key: "appstore:v1",
      scope: { query: "", category: "all", selectedAppId: null },
    }
    render(
      <MemoryRouter initialEntries={["/appstore"]}>
        <ChatWidgetRouteHarness />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    fireEvent.click(screen.getByRole("switch", { name: "App Store 지식 사용" }))
    fireEvent.click(screen.getByRole("button", { name: "Emails로 이동" }))

    expect(screen.getByRole("switch", { name: "Emails 지식 사용" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({ profileKey: "email-rag" }),
    )

    fireEvent.click(screen.getByRole("button", { name: "Appstore로 이동" }))

    expect(screen.getByRole("switch", { name: "App Store 지식 사용" })).toHaveAttribute(
      "aria-checked",
      "true",
    )
    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "appstore:v1",
        profileKey: "appstore-context",
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
    fireEvent.click(screen.getByRole("switch", { name: "Emails 지식 사용" }))

    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:assistant",
        profileKey: "portal-default",
        profileToolInputs: {},
      }),
    )
  })

  it("Observer 문맥 등록 전에도 일반 대화 launcher를 표시하고 준비 후 분석으로 전환한다", () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/observer/EQP-01"]}>
        <ChatWidget />
      </MemoryRouter>,
    )

    expect(chatSessionMocks.useChatSession).toHaveBeenLastCalledWith(
      expect.objectContaining({
        messageContextKey: "assistant:openwebui:assistant",
        profileKey: "portal-default",
      }),
    )
    expect(screen.getByRole("button", { name: "위젯 열기" })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "위젯 열기" }))
    expect(
      screen.getByRole("switch", { name: "Observer 지식 사용" }),
    ).toBeDisabled()

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
    expect(
      screen.getByRole("switch", { name: "Observer 지식 사용" }),
    ).not.toBeDisabled()
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
