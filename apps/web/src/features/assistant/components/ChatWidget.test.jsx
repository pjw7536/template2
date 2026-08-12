import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ChatWidget } from "./ChatWidget"

const chatSessionMocks = vi.hoisted(() => ({
  createRoom: vi.fn(),
  useChatSession: vi.fn(),
}))

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: 10 } }),
}))

vi.mock("@/lib/assistant/pageContext", () => ({
  usePageAssistantContext: () => ({ pageContext: null }),
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
    canRetrySave: false,
    createRoom: chatSessionMocks.createRoom,
  }
}

vi.mock("./ChatWidgetLauncher", () => ({
  ChatWidgetLauncher: ({ onClick }) => (
    <button type="button" onClick={onClick}>위젯 열기</button>
  ),
}))

vi.mock("./ChatWidgetPanel", () => ({
  ChatWidgetPanel: ({ onClose }) => (
    <button type="button" onClick={onClose}>위젯 닫기</button>
  ),
}))

describe("ChatWidget 대화방 생성", () => {
  beforeEach(() => {
    chatSessionMocks.createRoom.mockReset()
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
})
