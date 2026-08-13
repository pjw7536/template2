import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useChatSession as useChatSessionBase } from "./useChatSession"

function useChatSession(options = {}) {
  return useChatSessionBase({
    profileKey: "portal-default",
    messageContextKey: "assistant:openwebui:portal",
    ...options,
  })
}

const conversationApiMocks = vi.hoisted(() => ({
  clearMessages: vi.fn(),
  createConversation: vi.fn(),
  deleteFeedback: vi.fn(),
  deleteConversation: vi.fn(),
  exportConversation: vi.fn(),
  fetchMessages: vi.fn(),
  fetchConversationPage: vi.fn(),
  fetchConversations: vi.fn(),
  generateTitle: vi.fn(),
  refreshSummary: vi.fn(),
  submitFeedback: vi.fn(),
  updateConversation: vi.fn(),
}))
const turnApiMocks = vi.hoisted(() => ({
  streamTurn: vi.fn(),
}))

vi.mock("../api/conversationApi", () => ({
  clearAssistantConversationMessages: conversationApiMocks.clearMessages,
  createAssistantConversation: conversationApiMocks.createConversation,
  deleteAssistantConversation: conversationApiMocks.deleteConversation,
  deleteAssistantMessageFeedback: conversationApiMocks.deleteFeedback,
  exportAssistantConversation: conversationApiMocks.exportConversation,
  fetchAssistantConversationPage: (...args) =>
    conversationApiMocks.fetchConversationPage(...args),
  fetchAssistantConversationMessagePage: async (...args) => {
    const response = await conversationApiMocks.fetchMessages(...args)
    return Array.isArray(response)
      ? { results: response, nextCursor: "", hasMore: false }
      : response
  },
  generateAssistantConversationTitle: conversationApiMocks.generateTitle,
  refreshAssistantConversationSummary: conversationApiMocks.refreshSummary,
  submitAssistantMessageFeedback: conversationApiMocks.submitFeedback,
  updateAssistantConversation: conversationApiMocks.updateConversation,
}))

vi.mock("../api/turnApi", () => ({
  streamAssistantTurn: turnApiMocks.streamTurn,
}))

function createWrapper(queryClient = new QueryClient({
  defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
})) {
  return function QueryWrapper({ children }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

function createDeferred() {
  let resolve
  const promise = new Promise((nextResolve) => {
    resolve = nextResolve
  })
  return { promise, resolve }
}

describe("useChatSession page context", () => {
  beforeEach(() => {
    Object.values(conversationApiMocks).forEach((mock) => mock.mockReset())
    turnApiMocks.streamTurn.mockReset()
    turnApiMocks.streamTurn.mockImplementation(async (_payload, { onEvent }) => {
      onEvent({ event: "run.started", payload: { runId: "run-1" } })
      onEvent({
        event: "message.completed",
        payload: {
          id: "assistant-1",
          role: "assistant",
          content: "서버 답변",
          sources: [],
          accessState: "available",
        },
      })
      onEvent({ event: "run.completed", payload: { runId: "run-1" } })
    })
    conversationApiMocks.clearMessages.mockResolvedValue({})
    conversationApiMocks.createConversation.mockResolvedValue({
      id: "room-server",
      name: "새 대화",
    })
    conversationApiMocks.deleteConversation.mockResolvedValue({})
    conversationApiMocks.fetchMessages.mockResolvedValue([])
    conversationApiMocks.fetchConversations.mockResolvedValue([])
    conversationApiMocks.fetchConversationPage.mockImplementation(async () => ({
      results: await conversationApiMocks.fetchConversations(),
      nextCursor: "",
      hasMore: false,
    }))
    conversationApiMocks.generateTitle.mockResolvedValue({
      id: "room-server",
      name: "장비 상태 이상 원인 분석",
    })
    conversationApiMocks.refreshSummary.mockResolvedValue({ updated: false })
    conversationApiMocks.submitFeedback.mockResolvedValue({ rating: "up", reason: "" })
    conversationApiMocks.deleteFeedback.mockResolvedValue({})
    conversationApiMocks.exportConversation.mockResolvedValue(undefined)
    conversationApiMocks.updateConversation.mockImplementation(async (_roomId, updates) => ({
      id: "room-server",
      name: updates.name || "서버 대화",
      pinned: updates.pinned === true,
      archived: updates.archived === true,
    }))
  })

  it("Profile 설정 시 표준 Turn이 user/assistant 저장과 generation을 소유한다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    turnApiMocks.streamTurn.mockImplementation(async (_payload, { onEvent }) => {
      onEvent({
        event: "run.started",
        payload: { runId: "run-1", assistantClientId: "assistant-1" },
      })
      onEvent({ event: "message.delta", payload: { content: "표준 " } })
      onEvent({ event: "message.delta", payload: { content: "답변" } })
      onEvent({
        event: "message.completed",
        payload: {
          id: "assistant-1",
          role: "assistant",
          content: "표준 답변",
          sources: [],
          blocks: [{ type: "text", content: "표준 답변", sourceIds: [] }],
          accessState: "available",
        },
      })
      onEvent({ event: "run.completed", payload: { runId: "run-1" } })
      return []
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
          profileKey: "portal-default",
          profileVersion: 1,
          profileToolInputs: {},
        }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    await waitFor(() => expect(result.current.messages[0]?.isGreeting).toBe(true))
    await act(async () => {
      await result.current.sendMessage("표준 질문")
    })

    expect(turnApiMocks.streamTurn).toHaveBeenCalledOnce()
    expect(turnApiMocks.streamTurn.mock.calls[0][0]).toMatchObject({
      action: "send",
      conversationId: "room-server",
      profileKey: "portal-default",
      appContextKey: "assistant:openwebui:portal",
      message: { content: "표준 질문" },
    })
    expect(turnApiMocks.streamTurn.mock.calls[0][0]).not.toHaveProperty("history")
    expect(result.current.messages.at(-1)).toMatchObject({
      id: "assistant-1",
      content: "표준 답변",
    })
  })

  it("앱 전환 후에도 기존 10,000자 메시지를 client history로 다시 전송하지 않는다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.fetchMessages.mockResolvedValue([
      {
        id: "long-message",
        role: "user",
        content: "가".repeat(10_000),
        contextKey: "profile:email-rag",
        accessState: "available",
      },
    ])
    const { result, rerender } = renderHook(
      ({ messageContextKey }) =>
        useChatSession({
          userKey: 10,
          messageContextKey,
        }),
      {
        initialProps: { messageContextKey: "profile:email-rag" },
        wrapper: createWrapper(),
      },
    )

    await waitFor(() => expect(result.current.messages[0]?.content).toHaveLength(10_000))
    rerender({ messageContextKey: "profile:portal-default" })
    await act(async () => {
      await result.current.sendMessage("후속 질문")
    })

    const payload = turnApiMocks.streamTurn.mock.calls[0][0]
    expect(payload.message.content).toBe("후속 질문")
    expect(payload).not.toHaveProperty("history")
  })

  it("Run 시작 전 실패한 Email 요청은 앱 이동 후에도 기존 RAG 설정으로 재시도한다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    turnApiMocks.streamTurn.mockRejectedValueOnce(new Error("연결 실패"))
    const emailToolInputs = {
      "rag.search": {
        permissionGroups: ["mail-a"],
        ragIndexes: ["email-index-a"],
      },
    }
    const { result, rerender } = renderHook(
      ({ profileKey, profileToolInputs }) =>
        useChatSession({
          userKey: 10,
          profileKey,
          profileToolInputs,
        }),
      {
        initialProps: {
          profileKey: "email-rag",
          profileToolInputs: emailToolInputs,
        },
        wrapper: createWrapper(),
      },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    await act(async () => {
      await result.current.sendMessage("메일 질문")
    })
    expect(result.current.canRetry).toBe(true)

    rerender({ profileKey: "portal-default", profileToolInputs: {} })
    await act(async () => {
      await result.current.retryLastMessage()
    })

    expect(turnApiMocks.streamTurn).toHaveBeenCalledTimes(2)
    expect(turnApiMocks.streamTurn.mock.calls[1][0]).toMatchObject({
      profileKey: "email-rag",
      profileVersion: 1,
      toolInputs: emailToolInputs,
      message: { content: "메일 질문" },
    })
  })

  it("첫 페이지 재조회 후에도 추가 페이지와 선택 대화를 유지한다", async () => {
    conversationApiMocks.fetchConversationPage.mockImplementation(async ({ cursor } = {}) => {
      if (cursor === "cursor-1") {
        return {
          results: [{ id: "room-2", name: "두 번째 대화" }],
          nextCursor: "",
          hasMore: false,
        }
      }
      return {
        results: [{ id: "room-1", name: "첫 번째 대화" }],
        nextCursor: "cursor-1",
        hasMore: true,
      }
    })
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => expect(result.current.hasMoreRooms).toBe(true))
    await act(async () => {
      await Promise.all([
        result.current.loadMoreRooms(),
        result.current.loadMoreRooms(),
      ])
    })
    expect(
      conversationApiMocks.fetchConversationPage.mock.calls.filter(
        ([options]) => options?.cursor === "cursor-1",
      ),
    ).toHaveLength(1)
    act(() => result.current.selectRoom("room-2"))

    await act(async () => {
      await queryClient.invalidateQueries({
        queryKey: ["assistant", "conversations", "10", "active"],
      })
    })

    await waitFor(() => {
      expect(result.current.roomListRooms.map((room) => room.id)).toEqual([
        "room-1",
        "room-2",
      ])
      expect(result.current.activeRoomId).toBe("room-2")
    })
  })

  it("이전 메시지 page를 불러온 뒤 첫 page를 재조회해도 과거 이력을 유지한다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.fetchMessages.mockImplementation(
      async (_roomId, { before } = {}) => {
        if (before === "older-cursor") {
          return {
            results: [
              { id: "user-old", role: "user", content: "오래된 질문" },
            ],
            nextCursor: "",
            hasMore: false,
          }
        }
        return {
          results: [
            { id: "assistant-latest", role: "assistant", content: "최근 답변" },
          ],
          nextCursor: "older-cursor",
          hasMore: true,
        }
      },
    )
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => expect(result.current.hasOlderMessages).toBe(true))
    await act(async () => {
      await result.current.loadOlderMessages()
    })
    await waitFor(() => {
      expect(result.current.messages.map((message) => message.content)).toEqual([
        "오래된 질문",
        "최근 답변",
      ])
    })

    await act(async () => {
      await queryClient.invalidateQueries({
        queryKey: ["assistant", "conversation-messages", "10", "room-server"],
      })
    })

    await waitFor(() => {
      expect(result.current.messages.map((message) => message.content)).toEqual([
        "오래된 질문",
        "최근 답변",
      ])
      expect(result.current.hasOlderMessages).toBe(false)
    })
  })

  it("사용자가 바뀐 뒤 도착한 대화방 생성 결과를 현재 session에 반영하지 않는다", async () => {
    const creation = createDeferred()
    conversationApiMocks.createConversation.mockReturnValue(creation.promise)
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    })
    const { result, rerender } = renderHook(
      ({ userKey }) => useChatSession({ userKey }),
      { initialProps: { userKey: 10 }, wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => expect(result.current.isSessionLoading).toBe(false))
    let createPromise
    act(() => {
      createPromise = result.current.createRoom()
    })
    await waitFor(() => {
      expect(conversationApiMocks.createConversation).toHaveBeenCalledOnce()
    })

    rerender({ userKey: 20 })
    await waitFor(() => expect(result.current.isSessionLoading).toBe(false))
    expect(result.current.isRoomListBusy).toBe(false)
    expect(result.current.isSending).toBe(false)
    await act(async () => {
      creation.resolve({ id: "old-user-room", name: "이전 사용자 대화" })
      await createPromise
    })

    expect(result.current.rooms).toEqual([])
    expect(result.current.activeRoomId).toBeNull()
    expect(
      queryClient.getQueryData(["assistant", "conversations", "20", "active"])
        ?.results || [],
    ).toEqual([])
  })

  it("대화 초기화 중에는 새 메시지 전송을 시작하지 않는다", async () => {
    const clearing = createDeferred()
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.clearMessages.mockReturnValue(clearing.promise)
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    let resetPromise
    let sendPromise
    act(() => {
      resetPromise = result.current.resetConversation("room-server")
      sendPromise = result.current.sendMessage("초기화와 겹친 질문")
    })

    await expect(sendPromise).resolves.toEqual({ ok: false, accepted: false })
    expect(turnApiMocks.streamTurn).not.toHaveBeenCalled()
    await act(async () => {
      clearing.resolve({})
      await resetPromise
    })
    expect(result.current.isSending).toBe(false)
  })

  it("마지막 대화방 보관 후 빈 상태를 답변 생성 중으로 표시하지 않는다", async () => {
    conversationApiMocks.fetchConversations
      .mockResolvedValueOnce([{ id: "room-server", name: "서버 대화" }])
      .mockResolvedValue([])
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    await act(async () => {
      await result.current.toggleArchiveRoom("room-server")
    })

    await waitFor(() => expect(result.current.activeRoomId).toBeNull())
    expect(result.current.generationRoomId).toBeNull()
    expect(result.current.isGenerating).toBe(false)
  })

  it("보관함에서 복원한 최신 대화를 활성 목록 전환 즉시 표시한다", async () => {
    const activeRefetch = createDeferred()
    let activeFetchCount = 0
    let restored = false
    const oldRoom = {
      id: "room-old",
      name: "기존 대화",
      updatedAt: "2026-08-01T00:00:00Z",
    }
    const restoredRoom = {
      id: "room-restored",
      name: "복원한 대화",
      archived: false,
      updatedAt: "2026-08-12T00:00:00Z",
    }
    conversationApiMocks.fetchConversationPage.mockImplementation(
      async ({ archived } = {}) => {
        if (archived) {
          return {
            results: restored
              ? []
              : [{ ...restoredRoom, archived: true }],
            nextCursor: "",
            hasMore: false,
          }
        }
        activeFetchCount += 1
        if (activeFetchCount === 1) {
          return { results: [oldRoom], nextCursor: "", hasMore: false }
        }
        return activeRefetch.promise
      },
    )
    conversationApiMocks.updateConversation.mockImplementation(async () => {
      restored = true
      return restoredRoom
    })
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-old"))
    act(() => result.current.toggleArchivedView())
    await waitFor(() => {
      expect(result.current.showArchived).toBe(true)
      expect(result.current.roomListRooms[0]?.id).toBe("room-restored")
    })

    await act(async () => {
      await result.current.toggleArchiveRoom("room-restored")
    })
    expect(
      queryClient
        .getQueryData(["assistant", "conversations", "10", "active"])
        .results.map((room) => room.id),
    ).toEqual(["room-restored", "room-old"])

    act(() => result.current.toggleArchivedView())
    expect(result.current.showArchived).toBe(false)
    expect(result.current.roomListRooms.map((room) => room.id)).toEqual([
      "room-restored",
      "room-old",
    ])

    await act(async () => {
      activeRefetch.resolve({
        results: [restoredRoom, oldRoom],
        nextCursor: "",
        hasMore: false,
      })
      await activeRefetch.promise
    })
  })







  it("이전 메시지 page를 500개를 넘어도 잘라내지 않고 앞에 추가한다", async () => {
    const currentMessages = Array.from({ length: 500 }, (_, index) => ({
      id: `current-${index}`,
      role: index % 2 === 0 ? "user" : "assistant",
      content: `현재 메시지 ${index}`,
      contextKey: "assistant:openwebui:portal",
    }))
    const olderMessages = Array.from({ length: 20 }, (_, index) => ({
      id: `older-${index}`,
      role: index % 2 === 0 ? "user" : "assistant",
      content: `과거 메시지 ${index}`,
      contextKey: "assistant:openwebui:portal",
    }))
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.fetchMessages
      .mockResolvedValueOnce({
        results: currentMessages,
        nextCursor: "older-page",
        hasMore: true,
      })
      .mockResolvedValueOnce({
        results: olderMessages,
        nextCursor: "",
        hasMore: false,
      })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(500)
      expect(result.current.hasOlderMessages).toBe(true)
    })
    await act(async () => {
      await Promise.all([
        result.current.loadOlderMessages(),
        result.current.loadOlderMessages(),
      ])
    })

    expect(
      conversationApiMocks.fetchMessages.mock.calls.filter(
        ([, options]) => options?.before === "older-page",
      ),
    ).toHaveLength(1)
    await waitFor(() => {
      expect(result.current.messages).toHaveLength(520)
      expect(result.current.messages[0]).toMatchObject({ id: "older-0" })
      expect(result.current.messages.at(-1)).toMatchObject({ id: "current-499" })
    })
    expect(result.current.hasOlderMessages).toBe(false)
  })
  it("10,000자를 넘는 메시지는 전송하지 않는다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-1", name: "테스트" },
    ])
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-1"))
    await act(async () => {
      await result.current.sendMessage("가".repeat(10_001))
    })

    expect(turnApiMocks.streamTurn).not.toHaveBeenCalled()
    expect(result.current.errorMessage).toContain("10,000자")
  })

  it("새 대화방에는 스트리밍 인사 메시지를 만든다", async () => {
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => {
      expect(result.current.isSessionLoading).toBe(false)
    })

    await act(async () => {
      await result.current.createRoom()
    })

    expect(result.current.messages).toMatchObject([
      {
        role: "assistant",
        content: "무엇을 도와드릴까요?",
        streamId: expect.any(String),
      },
    ])
  })

  it("빈 상태의 첫 메시지에서만 대화방을 만들고 제목을 생성한다", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false, staleTime: Infinity },
      },
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
        }),
      { wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => expect(result.current.isSessionLoading).toBe(false))
    expect(result.current.rooms).toEqual([])
    expect(conversationApiMocks.createConversation).not.toHaveBeenCalled()

    let resetResult
    await act(async () => {
      resetResult = await result.current.resetConversation()
    })
    expect(resetResult).toEqual({ ok: false })
    expect(conversationApiMocks.createConversation).not.toHaveBeenCalled()

    await act(async () => {
      await result.current.sendMessage("첫 질문")
    })

    expect(conversationApiMocks.createConversation).toHaveBeenCalledOnce()
    expect(conversationApiMocks.createConversation.mock.calls[0][0]).toEqual({
      name: "새 대화 1",
    })
    expect(turnApiMocks.streamTurn).toHaveBeenCalledOnce()
    await waitFor(() => {
      expect(conversationApiMocks.generateTitle).toHaveBeenCalledWith("room-server")
      expect(result.current.rooms[0]?.name).toBe("장비 상태 이상 원인 분석")
    })
    expect(
      queryClient
        .getQueryData(["assistant", "conversations", "10", "active"])
        .results[0],
    ).toMatchObject({
      id: "room-server",
      name: "장비 상태 이상 원인 분석",
    })

    act(() => result.current.toggleArchivedView())
    await waitFor(() => {
      expect(result.current.showArchived).toBe(true)
      expect(result.current.roomListRooms).toEqual([])
    })
    act(() => result.current.toggleArchivedView())
    expect(result.current.showArchived).toBe(false)
    expect(result.current.roomListRooms[0]).toMatchObject({ id: "room-server" })
  })

  it("빈 상태에서 전송이 겹쳐도 대화방과 모델 요청을 한 번만 만든다", async () => {
    const creation = createDeferred()
    conversationApiMocks.createConversation.mockReturnValue(creation.promise)
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
        }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.isSessionLoading).toBe(false))
    let firstSendPromise
    let secondSendPromise
    act(() => {
      firstSendPromise = result.current.sendMessage("첫 질문")
      secondSendPromise = result.current.sendMessage("중복 질문")
    })

    await waitFor(() => {
      expect(conversationApiMocks.createConversation).toHaveBeenCalledOnce()
      expect(result.current.isSending).toBe(true)
    })
    let secondResult
    await act(async () => {
      secondResult = await secondSendPromise
    })
    expect(secondResult).toEqual({ ok: false, accepted: false })

    await act(async () => {
      creation.resolve({ id: "room-server", name: "새 대화 1" })
      await firstSendPromise
    })

    expect(conversationApiMocks.createConversation).toHaveBeenCalledOnce()
    expect(turnApiMocks.streamTurn).toHaveBeenCalledOnce()
    expect(result.current.rooms).toHaveLength(1)
  })

  it("대화방 이름과 고정 상태를 conversation cache에 반영한다", async () => {
    let serverRoom = { id: "room-server", name: "서버 대화", pinned: false }
    conversationApiMocks.fetchConversations.mockResolvedValue([serverRoom])
    conversationApiMocks.updateConversation.mockImplementation(async (_roomId, updates) => {
      serverRoom = { ...serverRoom, ...updates }
      return serverRoom
    })
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    await act(async () => {
      await result.current.renameRoom("room-server", "변경된 이름")
    })
    await act(async () => {
      await result.current.togglePinRoom("room-server")
    })

    expect(
      queryClient
        .getQueryData(["assistant", "conversations", "10", "active"])
        .results[0],
    ).toMatchObject({
      id: "room-server",
      name: "변경된 이름",
      pinned: true,
    })
  })

  it("대화방 고정 요청을 순서대로 처리해 마지막 선택을 유지한다", async () => {
    const firstUpdate = createDeferred()
    let serverRoom = { id: "room-server", name: "서버 대화", pinned: false }
    conversationApiMocks.fetchConversations.mockResolvedValue([serverRoom])
    conversationApiMocks.updateConversation
      .mockImplementationOnce(() => firstUpdate.promise)
      .mockImplementation(async (_roomId, updates) => {
        serverRoom = { ...serverRoom, ...updates }
        return serverRoom
      })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    let firstPromise
    let secondPromise
    act(() => {
      firstPromise = result.current.togglePinRoom("room-server")
      secondPromise = result.current.togglePinRoom("room-server")
    })
    await waitFor(() => {
      expect(conversationApiMocks.updateConversation).toHaveBeenCalledOnce()
    })
    expect(conversationApiMocks.updateConversation).toHaveBeenCalledWith(
      "room-server",
      { pinned: true },
    )

    await act(async () => {
      serverRoom = { ...serverRoom, pinned: true }
      firstUpdate.resolve(serverRoom)
      await Promise.all([firstPromise, secondPromise])
    })

    expect(conversationApiMocks.updateConversation).toHaveBeenNthCalledWith(
      2,
      "room-server",
      { pinned: false },
    )
    expect(result.current.rooms[0]).toMatchObject({ pinned: false })
  })

  it("답변 평가 요청을 순서대로 처리해 마지막 평가를 유지한다", async () => {
    const firstFeedback = createDeferred()
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.fetchMessages.mockResolvedValue([
      { id: "assistant-1", role: "assistant", content: "서버 답변" },
    ])
    conversationApiMocks.submitFeedback
      .mockImplementationOnce(() => firstFeedback.promise)
      .mockResolvedValueOnce({ rating: "down", reason: "" })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => {
      expect(result.current.messages[0]).toMatchObject({ id: "assistant-1" })
    })
    let firstPromise
    let secondPromise
    act(() => {
      firstPromise = result.current.rateAssistantMessage("assistant-1", "up")
      secondPromise = result.current.rateAssistantMessage("assistant-1", "down")
    })
    await waitFor(() => expect(conversationApiMocks.submitFeedback).toHaveBeenCalledOnce())

    await act(async () => {
      firstFeedback.resolve({ rating: "up", reason: "" })
      await Promise.all([firstPromise, secondPromise])
    })

    expect(conversationApiMocks.submitFeedback).toHaveBeenNthCalledWith(
      2,
      "room-server",
      "assistant-1",
      { rating: "down" },
    )
    await waitFor(() => {
      expect(result.current.messages[0]).toMatchObject({
        feedback: { rating: "down", reason: "" },
      })
    })
  })

  it("마지막 대화방을 삭제한 뒤 빈 상태를 유지한다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    await act(async () => {
      await result.current.removeRoom("room-server")
    })

    expect(result.current.rooms).toEqual([])
    expect(result.current.activeRoomId).toBeNull()
    expect(result.current.messages).toMatchObject([
      {
        role: "assistant",
        content: "무엇을 도와드릴까요?",
        isGreeting: true,
      },
    ])
    expect(conversationApiMocks.createConversation).not.toHaveBeenCalled()
  })

  it("선택 대화방 삭제 성공과 실패를 한 번에 상태에 반영한다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-1", name: "첫 방" },
      { id: "room-2", name: "둘째 방" },
      { id: "room-3", name: "셋째 방" },
    ])
    conversationApiMocks.deleteConversation.mockImplementation(async (roomId) => {
      if (roomId === "room-2") throw new Error("삭제 실패")
      return {}
    })
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => expect(result.current.rooms).toHaveLength(3))
    let deletionResult
    await act(async () => {
      deletionResult = await result.current.removeRooms(["room-1", "room-2"])
    })

    expect(deletionResult).toEqual({
      deletedIds: ["room-1"],
      failedIds: ["room-2"],
    })
    expect(result.current.rooms.map((room) => room.id)).toEqual(["room-2", "room-3"])
    expect(result.current.activeRoomId).toBe("room-2")
    expect(result.current.errorMessage).toContain("1개 대화방을 삭제하지 못했어요")
    expect(
      queryClient
        .getQueryData(["assistant", "conversations", "10", "active"])
        .results.map((room) => room.id),
    ).toEqual(["room-2", "room-3"])

    act(() => {
      queryClient.setQueryData(
        ["assistant", "conversations", "10", "active"],
        {
          results: [
            { id: "room-1", name: "첫 방" },
            { id: "room-2", name: "둘째 방" },
            { id: "room-3", name: "셋째 방" },
          ],
          nextCursor: "",
          hasMore: false,
        },
      )
    })
    await waitFor(() => {
      expect(
        queryClient
          .getQueryData(["assistant", "conversations", "10", "active"])
          .results.map((room) => room.id),
      ).toEqual(["room-2", "room-3"])
    })
  })

  it("첫 답변 저장 후 생성된 제목을 대화방에 반영한다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "새 대화" },
    ])
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
        }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => {
      expect(result.current.activeRoomId).toBe("room-server")
    })
    await act(async () => {
      await result.current.sendMessage("DOWN이 반복되는 원인은?")
    })

    await waitFor(() => {
      expect(result.current.rooms[0]?.name).toBe("장비 상태 이상 원인 분석")
    })
    expect(conversationApiMocks.generateTitle).toHaveBeenCalledWith("room-server")
  })

  it("대화방 이력 로딩은 전송을 잠그지만 AI 생성 상태를 켜지 않는다", async () => {
    const messageHistory = createDeferred()
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.fetchMessages.mockReturnValue(messageHistory.promise)
    const { result } = renderHook(
      () => useChatSession({ userKey: 10 }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => {
      expect(result.current.activeRoomId).toBe("room-server")
      expect(result.current.isSending).toBe(true)
    })
    expect(result.current.isGenerating).toBe(false)

    await act(async () => {
      messageHistory.resolve([])
      await messageHistory.promise
    })
  })






})
