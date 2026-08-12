import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useChatSession } from "./useChatSession"

const conversationApiMocks = vi.hoisted(() => ({
  abandonGeneration: vi.fn(),
  acquireGeneration: vi.fn(),
  appendMessages: vi.fn(),
  clearMessages: vi.fn(),
  createConversation: vi.fn(),
  deleteFeedback: vi.fn(),
  deleteConversation: vi.fn(),
  exportConversation: vi.fn(),
  fetchMessages: vi.fn(),
  fetchConversationPage: vi.fn(),
  fetchConversations: vi.fn(),
  generateTitle: vi.fn(),
  finalizeGeneration: vi.fn(),
  refreshSummary: vi.fn(),
  submitFeedback: vi.fn(),
  updateConversation: vi.fn(),
}))

vi.mock("../api/conversationApi", () => ({
  abandonAssistantGeneration: conversationApiMocks.abandonGeneration,
  acquireAssistantGeneration: conversationApiMocks.acquireGeneration,
  appendAssistantConversationMessages: conversationApiMocks.appendMessages,
  clearAssistantConversationMessages: conversationApiMocks.clearMessages,
  createAssistantConversation: conversationApiMocks.createConversation,
  deleteAssistantConversation: conversationApiMocks.deleteConversation,
  deleteAssistantMessageFeedback: conversationApiMocks.deleteFeedback,
  exportAssistantConversation: conversationApiMocks.exportConversation,
  fetchAssistantConversationMessages: conversationApiMocks.fetchMessages,
  fetchAssistantConversations: conversationApiMocks.fetchConversations,
  fetchAssistantConversationPage: (...args) =>
    conversationApiMocks.fetchConversationPage(...args),
  fetchAssistantConversationMessagePage: async (...args) => {
    const response = await conversationApiMocks.fetchMessages(...args)
    return Array.isArray(response)
      ? { results: response, nextCursor: "", hasMore: false }
      : response
  },
  generateAssistantConversationTitle: conversationApiMocks.generateTitle,
  finalizeAssistantGeneration: conversationApiMocks.finalizeGeneration,
  refreshAssistantConversationSummary: conversationApiMocks.refreshSummary,
  submitAssistantMessageFeedback: conversationApiMocks.submitFeedback,
  updateAssistantConversation: conversationApiMocks.updateConversation,
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
    conversationApiMocks.appendMessages.mockResolvedValue([])
    conversationApiMocks.acquireGeneration.mockResolvedValue({
      id: "generation-1",
      status: "streaming",
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
    conversationApiMocks.finalizeGeneration.mockResolvedValue({ status: "completed" })
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
    expect(result.current.messages.map((message) => message.content)).toEqual([
      "오래된 질문",
      "최근 답변",
    ])

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
    const messageSender = vi.fn().mockResolvedValue({
      reply: "답변",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () => useChatSession({ userKey: 10, messageSender }),
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
    expect(messageSender).not.toHaveBeenCalled()
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

  it("Observer sender에는 같은 방의 일반 Chat과 Observer 대화를 함께 전달한다", async () => {
    const messageSender = vi.fn().mockResolvedValue({
      reply: "Observer 분석 결과",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          messageContextKey: "observer:scope-a",
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
          initialMessagesByRoom: {
            "room-1": [
              {
                role: "user",
                content: "일반 질문",
                contextKey: "assistant:openwebui",
              },
              { role: "user", content: "이전 분석", contextKey: "observer:scope-a" },
            ],
          },
        }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      await result.current.sendMessage("왜 반복됐어?")
    })

    const request = messageSender.mock.calls[0][0]
    expect(request.history.map((message) => message.content)).toEqual([
      "[이전 대화 출처: 일반 Chat]\n일반 질문",
      "이전 분석",
      "왜 반복됐어?",
    ])
    expect(result.current.messages.at(-1)).toMatchObject({
      role: "assistant",
      content: "Observer 분석 결과",
      contextKey: "observer:scope-a",
    })
  })

  it("일반 Chat sender에는 같은 방의 Observer 대화를 출처와 함께 전달한다", async () => {
    const messageSender = vi.fn().mockResolvedValue({
      reply: "일반 Chat 후속 답변",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          messageContextKey: "assistant:openwebui",
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
          initialMessagesByRoom: {
            "room-1": [
              {
                role: "user",
                content: "DOWN 반복을 분석해줘",
                contextKey: "observer:scope-a",
              },
              {
                role: "assistant",
                content: "특정 시간대에 집중됐습니다.",
                contextKey: "observer:scope-a",
              },
            ],
          },
        }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      await result.current.sendMessage("방금 분석을 한 줄로 정리해줘")
    })

    expect(messageSender.mock.calls[0][0].history.map((message) => message.content)).toEqual([
      "[이전 대화 출처: Observer]\nDOWN 반복을 분석해줘",
      "[이전 대화 출처: Observer]\n특정 시간대에 집중됐습니다.",
      "방금 분석을 한 줄로 정리해줘",
    ])
  })

  it("Email RAG sender에는 일반 Chat과 Observer 대화를 전달하지 않는다", async () => {
    const messageSender = vi.fn().mockResolvedValue({
      reply: "메일 답변",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          messageContextKey: "assistant",
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
          initialMessagesByRoom: {
            "room-1": [
              { role: "user", content: "일반 질문", contextKey: "assistant:openwebui" },
              { role: "assistant", content: "Observer 분석", contextKey: "observer:scope-a" },
              { role: "user", content: "이전 메일 질문", contextKey: "assistant" },
            ],
          },
        }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      await result.current.sendMessage("후속 메일 질문")
    })

    expect(messageSender.mock.calls[0][0].history.map((message) => message.content)).toEqual([
      "이전 메일 질문",
      "후속 메일 질문",
    ])
  })

  it("서버에서 현재 사용자의 방을 불러오고 user/assistant 메시지를 각각 저장한다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      {
        id: "room-server",
        name: "서버 대화",
        updatedAt: "2026-08-11T00:00:00Z",
      },
    ])
    conversationApiMocks.fetchMessages.mockResolvedValue([
      {
        id: "user-old",
        role: "user",
        content: "이전 질문",
        contextKey: "assistant:openwebui",
      },
    ])
    const messageSender = vi.fn().mockResolvedValue({
      reply: "새 답변",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
          messageSender,
          messageContextKey: "assistant:openwebui",
        }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => {
      expect(result.current.activeRoomId).toBe("room-server")
      expect(result.current.messages.some((message) => message.content === "이전 질문")).toBe(true)
    })

    await act(async () => {
      await result.current.sendMessage("새 질문")
    })

    expect(messageSender.mock.calls[0][0].history.map((message) => message.content)).toEqual([
      "이전 질문",
      "새 질문",
    ])
    expect(conversationApiMocks.appendMessages).toHaveBeenCalledTimes(2)
    expect(conversationApiMocks.appendMessages.mock.calls[0][1][0]).toMatchObject({
      role: "user",
      content: "새 질문",
      contextKey: "assistant:openwebui",
    })
    expect(conversationApiMocks.appendMessages.mock.calls[1][1][0]).toMatchObject({
      role: "assistant",
      content: "새 답변",
      contextKey: "assistant:openwebui",
    })
    expect(conversationApiMocks.acquireGeneration).toHaveBeenCalledWith(
      expect.objectContaining({
        conversationId: "room-server",
        contextKey: "assistant:openwebui",
      }),
    )
    expect(conversationApiMocks.finalizeGeneration).toHaveBeenCalledWith(
      "generation-1",
      "completed",
    )
    expect(
      conversationApiMocks.appendMessages.mock.invocationCallOrder[1],
    ).toBeLessThan(conversationApiMocks.finalizeGeneration.mock.invocationCallOrder[0])
  })

  it("백그라운드 메시지 응답이 늦게 도착해도 전송 중인 메시지를 유지한다", async () => {
    const modelResponse = createDeferred()
    const messageSender = vi.fn().mockReturnValue(modelResponse.promise)
    const serverMessages = [
      {
        id: "user-old",
        role: "user",
        content: "이전 질문",
        contextKey: "assistant:openwebui",
      },
    ]
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.fetchMessages.mockResolvedValue(serverMessages)
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
          messageSender,
          messageContextKey: "assistant:openwebui",
        }),
      { wrapper: createWrapper(queryClient) },
    )

    await waitFor(() => {
      expect(result.current.messages.map((message) => message.content)).toContain("이전 질문")
    })
    let sendPromise
    act(() => {
      sendPromise = result.current.sendMessage("새 질문")
    })
    await waitFor(() => {
      expect(result.current.messages.map((message) => message.content)).toContain("새 질문")
    })

    act(() => {
      queryClient.setQueryData(
        ["assistant", "conversation-messages", "10", "room-server"],
        {
          roomId: "room-server",
          page: { results: serverMessages, nextCursor: "", hasMore: false },
        },
      )
    })

    await waitFor(() => {
      expect(result.current.messages.map((message) => message.content)).toContain("새 질문")
    })
    conversationApiMocks.fetchMessages.mockResolvedValue(result.current.messages)
    await act(async () => {
      modelResponse.resolve({ reply: "새 답변", sources: [], segments: [] })
      await sendPromise
    })
  })

  it("이전 메시지 page를 500개를 넘어도 잘라내지 않고 앞에 추가한다", async () => {
    const currentMessages = Array.from({ length: 500 }, (_, index) => ({
      id: `current-${index}`,
      role: index % 2 === 0 ? "user" : "assistant",
      content: `현재 메시지 ${index}`,
      contextKey: "assistant:openwebui",
    }))
    const olderMessages = Array.from({ length: 20 }, (_, index) => ({
      id: `older-${index}`,
      role: index % 2 === 0 ? "user" : "assistant",
      content: `과거 메시지 ${index}`,
      contextKey: "assistant:openwebui",
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
    expect(result.current.messages).toHaveLength(520)
    expect(result.current.messages[0]).toMatchObject({ id: "older-0" })
    expect(result.current.messages.at(-1)).toMatchObject({ id: "current-499" })
    expect(result.current.hasOlderMessages).toBe(false)
  })

  it("Assistant 답변 저장 실패 시 generation을 완료로 표시하지 않는다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
      { id: "room-other", name: "다른 대화" },
    ])
    conversationApiMocks.appendMessages
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error("답변 저장 실패"))
      .mockResolvedValueOnce([])
    const messageSender = vi.fn().mockResolvedValue({
      reply: "화면에는 표시되는 답변",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
          messageSender,
          messageContextKey: "assistant:openwebui",
        }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    await act(async () => {
      await result.current.sendMessage("저장 실패를 확인해줘")
    })

    expect(result.current.messages.at(-1)).toMatchObject({
      role: "assistant",
      content: "화면에는 표시되는 답변",
    })
    expect(conversationApiMocks.finalizeGeneration).toHaveBeenCalledWith(
      "generation-1",
      "failed",
      "message_save_failed",
    )
    expect(conversationApiMocks.finalizeGeneration).not.toHaveBeenCalledWith(
      "generation-1",
      "completed",
    )
    expect(result.current.errorMessage).toBe("답변 저장 실패")
    expect(result.current.canRetrySave).toBe(true)

    await act(async () => {
      await result.current.sendMessage("저장 전에 보내면 안 되는 질문")
    })
    expect(messageSender).toHaveBeenCalledOnce()
    expect(result.current.errorMessage).toBe(
      "먼저 표시된 답변 저장을 다시 시도해주세요.",
    )

    act(() => {
      result.current.clearError()
      result.current.selectRoom("room-other")
    })
    expect(result.current.canRetrySave).toBe(true)
    expect(result.current.errorMessage).toContain("서버 대화")

    await act(async () => {
      await result.current.retryAssistantSave()
    })

    expect(messageSender).toHaveBeenCalledOnce()
    expect(conversationApiMocks.appendMessages).toHaveBeenCalledTimes(3)
    expect(result.current.canRetrySave).toBe(false)
    expect(result.current.errorMessage).toBe("")
  })

  it("저장에 실패한 Assistant 답변을 제거하면 다음 질문을 보낼 수 있다", async () => {
    conversationApiMocks.fetchConversations.mockResolvedValue([
      { id: "room-server", name: "서버 대화" },
    ])
    conversationApiMocks.appendMessages
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error("답변 저장 실패"))
    const messageSender = vi.fn().mockResolvedValue({
      reply: "저장되지 않은 답변",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
          messageSender,
          messageContextKey: "assistant:openwebui",
        }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.activeRoomId).toBe("room-server"))
    await act(async () => {
      await result.current.sendMessage("저장 실패 질문")
    })
    expect(result.current.canRetrySave).toBe(true)

    act(() => {
      result.current.discardFailedAssistantSave()
    })
    expect(result.current.canRetrySave).toBe(false)
    expect(result.current.messages.some((message) => message.content === "저장되지 않은 답변"))
      .toBe(false)

    await act(async () => {
      await result.current.sendMessage("다음 질문")
    })
    expect(messageSender).toHaveBeenCalledTimes(2)
  })

  it("10,000자를 넘는 메시지는 전송하지 않는다", async () => {
    const messageSender = vi.fn()
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
        }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      await result.current.sendMessage("가".repeat(10_001))
    })

    expect(messageSender).not.toHaveBeenCalled()
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
    const messageSender = vi.fn().mockResolvedValue({
      reply: "첫 답변",
      sources: [],
      segments: [],
    })
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
          messageSender,
          messageContextKey: "assistant:openwebui",
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
    expect(messageSender).toHaveBeenCalledOnce()
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
    const messageSender = vi.fn().mockResolvedValue({
      reply: "첫 답변",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
          messageSender,
          messageContextKey: "assistant:openwebui",
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
    expect(messageSender).toHaveBeenCalledOnce()
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
    expect(result.current.messages[0]).toMatchObject({
      feedback: { rating: "down", reason: "" },
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
    const messageSender = vi.fn().mockResolvedValue({
      reply: "DOWN 반복 원인은 인터락입니다.",
      sources: [],
      segments: [],
    })
    const { result } = renderHook(
      () =>
        useChatSession({
          userKey: 10,
          messageSender,
          messageContextKey: "assistant:openwebui",
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

  it("실제 모델 응답을 기다릴 때만 AI 생성 상태를 켠다", async () => {
    const modelResponse = createDeferred()
    const messageSender = vi.fn().mockReturnValue(modelResponse.promise)
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
        }),
      { wrapper: createWrapper() },
    )
    let sendPromise

    act(() => {
      sendPromise = result.current.sendMessage("질문")
    })
    await waitFor(() => {
      expect(result.current.isGenerating).toBe(true)
    })

    await act(async () => {
      modelResponse.resolve({ reply: "답변", sources: [], segments: [] })
      await sendPromise
    })
    expect(result.current.isGenerating).toBe(false)
  })

  it("응답 생성 중에도 다른 대화방으로 이동하고 목록을 조작할 수 있다", async () => {
    const modelResponse = createDeferred()
    const messageSender = vi.fn().mockReturnValue(modelResponse.promise)
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          initialRooms: [
            { id: "room-1", name: "첫 방" },
            { id: "room-2", name: "둘째 방" },
          ],
          initialActiveRoomId: "room-1",
        }),
      { wrapper: createWrapper() },
    )
    let sendPromise

    act(() => {
      sendPromise = result.current.sendMessage("질문")
    })
    await waitFor(() => expect(result.current.generationRoomId).toBe("room-1"))

    act(() => result.current.selectRoom("room-2"))
    expect(result.current.activeRoomId).toBe("room-2")
    expect(result.current.isGenerating).toBe(false)
    expect(result.current.isSending).toBe(true)
    expect(result.current.hasActiveGeneration).toBe(true)
    expect(result.current.isRoomListBusy).toBe(false)

    let rejectedResult
    await act(async () => {
      rejectedResult = await result.current.sendMessage("둘째 방 질문")
    })
    expect(rejectedResult).toEqual({ ok: false, accepted: false })
    expect(result.current.errorMessage).toBe("다른 대화방에서 답변을 생성하고 있어요.")

    await act(async () => {
      modelResponse.resolve({ reply: "답변", sources: [], segments: [] })
      await sendPromise
    })
  })

  it("응답 중지는 현재 요청을 Abort하고 생성 상태를 해제한다", async () => {
    const messageSender = vi.fn().mockImplementation(({ signal }) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"))
        })
      }),
    )
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
        }),
      { wrapper: createWrapper() },
    )
    let sendPromise

    act(() => {
      sendPromise = result.current.sendMessage("중지할 질문")
    })
    await waitFor(() => expect(result.current.isGenerating).toBe(true))
    act(() => result.current.stopGenerating())
    await act(async () => {
      await sendPromise
    })

    expect(result.current.generationRoomId).toBe(null)
    expect(result.current.isGenerating).toBe(false)
    expect(result.current.errorMessage).toBe("")
  })

  it("session hook이 unmount되면 화면에 보이지 않는 생성 요청을 중단한다", async () => {
    let requestSignal
    const messageSender = vi.fn().mockImplementation(({ signal }) => {
      requestSignal = signal
      return new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"))
        })
      })
    })
    const { result, unmount } = renderHook(
      () =>
        useChatSession({
          messageSender,
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
        }),
      { wrapper: createWrapper() },
    )
    let sendPromise

    act(() => {
      sendPromise = result.current.sendMessage("중단할 질문")
    })
    await waitFor(() => expect(result.current.isGenerating).toBe(true))
    unmount()

    expect(requestSignal?.aborted).toBe(true)
    await expect(sendPromise).resolves.toEqual({ ok: false, accepted: false })
  })

  it("실패한 질문은 사용자 메시지를 중복 저장하지 않고 재시도한다", async () => {
    const messageSender = vi
      .fn()
      .mockRejectedValueOnce(new Error("일시 오류"))
      .mockResolvedValueOnce({ reply: "재시도 성공", sources: [], segments: [] })
    const { result } = renderHook(
      () =>
        useChatSession({
          messageSender,
          initialRooms: [{ id: "room-1", name: "테스트" }],
          initialActiveRoomId: "room-1",
        }),
      { wrapper: createWrapper() },
    )

    await act(async () => {
      await result.current.sendMessage("재시도 질문")
    })
    expect(result.current.canRetry).toBe(true)

    await act(async () => {
      await result.current.retryLastMessage()
    })

    expect(messageSender).toHaveBeenCalledTimes(2)
    expect(
      result.current.messages.filter(
        (message) => message.role === "user" && message.content === "재시도 질문",
      ),
    ).toHaveLength(1)
    expect(result.current.messages.at(-1)).toMatchObject({
      role: "assistant",
      content: "재시도 성공",
    })
  })
})
