import { afterEach, describe, expect, it, vi } from "vitest"

import {
  appendAssistantConversationMessages,
  createAssistantConversation,
  fetchAssistantConversationMessagePage,
  fetchAssistantConversationPage,
  generateAssistantConversationTitle,
  refreshAssistantConversationSummary,
} from "./conversationApi"

describe("conversationApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("대화방 생성과 메시지 저장 요청을 camelCase로 전송한다", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: vi.fn().mockResolvedValue({ id: "room-1", name: "새 대화" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: vi.fn().mockResolvedValue({ results: [] }),
      })
    vi.stubGlobal("fetch", fetchMock)

    await createAssistantConversation({ name: "새 대화" })
    await appendAssistantConversationMessages("room-1", [
      { id: "user-1", role: "user", content: "질문", contextKey: "assistant" },
    ])

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ name: "새 대화" })
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      messages: [
        {
          clientId: "user-1",
          role: "user",
          content: "질문",
          contextKey: "assistant",
          sources: [],
          userSdwtProd: "",
        },
      ],
    })
  })

  it("대화방 제목 생성을 전용 action endpoint로 요청한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        id: "room-1",
        name: "EQP DOWN 반복 원인 분석",
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(generateAssistantConversationTitle("room-1")).resolves.toMatchObject({
      name: "EQP DOWN 반복 원인 분석",
    })
    expect(fetchMock.mock.calls[0][0]).toMatch(
      /\/api\/v1\/assistant\/conversations\/room-1\/generate-title$/,
    )
    expect(fetchMock.mock.calls[0][1].method).toBe("POST")
  })

  it("대화방 검색과 메시지 이전 page cursor를 query에 전달한다", async () => {
    const conversationController = new AbortController()
    const messageController = new AbortController()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          results: [{ id: "room-1", name: "DOWN 분석" }],
          nextCursor: "room-cursor",
          hasMore: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          results: [{ id: "message-1", content: "이전 메시지" }],
          nextCursor: "message-cursor",
          hasMore: false,
        }),
      })
    vi.stubGlobal("fetch", fetchMock)

    await expect(
      fetchAssistantConversationPage({
        search: "DOWN",
        cursor: "next room",
        limit: 10,
        signal: conversationController.signal,
      }),
    ).resolves.toMatchObject({ nextCursor: "room-cursor", hasMore: true })
    await expect(
      fetchAssistantConversationMessagePage("room-1", {
        before: "older message",
        limit: 10,
        signal: messageController.signal,
      }),
    ).resolves.toMatchObject({ nextCursor: "message-cursor", hasMore: false })

    expect(fetchMock.mock.calls[0][0]).toContain(
      "/api/v1/assistant/conversations?search=DOWN&cursor=next+room&limit=10",
    )
    expect(fetchMock.mock.calls[1][0]).toContain(
      "/api/v1/assistant/conversations/room-1/messages?before=older+message&limit=10",
    )
    expect(fetchMock.mock.calls[0][1].signal).toBe(conversationController.signal)
    expect(fetchMock.mock.calls[1][1].signal).toBe(messageController.signal)
  })

  it("장기 대화 요약 갱신을 전용 action endpoint로 요청한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ updated: true, coveredMessageCount: 15 }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await expect(
      refreshAssistantConversationSummary("room-1", "assistant:openwebui"),
    ).resolves.toMatchObject({
      updated: true,
      coveredMessageCount: 15,
    })
    expect(fetchMock.mock.calls[0][0]).toMatch(
      /\/api\/v1\/assistant\/conversations\/room-1\/refresh-summary$/,
    )
    expect(fetchMock.mock.calls[0][1].method).toBe("POST")
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      contextKey: "assistant:openwebui",
    })
  })

  it("요약 갱신 context를 생략하면 Portal 문맥을 사용한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ updated: false }),
    })
    vi.stubGlobal("fetch", fetchMock)

    await refreshAssistantConversationSummary("room-1")

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      contextKey: "assistant:openwebui:portal",
    })
  })
})
