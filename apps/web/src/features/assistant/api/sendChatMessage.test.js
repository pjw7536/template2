import { afterEach, describe, expect, it, vi } from "vitest"

import {
  sendChatMessage,
  sendOpenWebUIStreamingMessage,
} from "./sendChatMessage"

function createSseResponse(events) {
  const encoder = new TextEncoder()
  return {
    ok: true,
    body: new ReadableStream({
      start(controller) {
        events.forEach((event) => controller.enqueue(encoder.encode(event)))
        controller.close()
      },
    }),
  }
}

describe("sendChatMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("메일 RAG 요청도 외부 AbortSignal로 중지한다", async () => {
    const fetchMock = vi.fn().mockImplementation((_url, request) =>
      new Promise((_resolve, reject) => {
        request.signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"))
        })
      }),
    )
    vi.stubGlobal("fetch", fetchMock)
    const controller = new AbortController()

    const pending = sendChatMessage({
      prompt: "메일 질문",
      roomId: "room-1",
      signal: controller.signal,
    })
    controller.abort()

    await expect(pending).rejects.toMatchObject({
      name: "AbortError",
      message: "응답 생성을 중지했습니다.",
    })
  })
})

describe("sendOpenWebUIStreamingMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("SSE delta를 순서대로 전달하고 최종 답변을 반환한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createSseResponse([
        'event: meta\ndata: {"provider":"openwebui","ragConfigured":false}\n\n',
        'event: delta\ndata: {"content":"첫 번째 "}\n\n',
        'event: delta\ndata: {"content":"답변"}\n\n',
        'event: done\ndata: {"reply":"첫 번째 답변"}\n\n',
      ]),
    )
    vi.stubGlobal("fetch", fetchMock)
    const onDelta = vi.fn()

    const result = await sendOpenWebUIStreamingMessage({
      prompt: "질문",
      history: [],
      roomId: "room-1",
      onDelta,
    })

    expect(fetchMock.mock.calls[0][0]).toMatch(
      /\/api\/v1\/assistant\/openwebui-chat\/stream$/,
    )
    expect(onDelta.mock.calls.map(([delta]) => delta)).toEqual(["첫 번째 ", "답변"])
    expect(result.reply).toBe("첫 번째 답변")
    expect(result.meta).toMatchObject({ provider: "openwebui", ragConfigured: false })
  })

  it("done 없이 연결이 종료되면 일부 답변을 성공으로 저장하지 않는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createSseResponse([
        'event: delta\ndata: {"content":"일부 답변"}\n\n',
      ]),
    )
    vi.stubGlobal("fetch", fetchMock)

    await expect(
      sendOpenWebUIStreamingMessage({
        prompt: "질문",
        history: [],
        roomId: "room-1",
      }),
    ).rejects.toThrow("응답이 완료되기 전에 연결이 종료되었습니다")
  })

  it("외부 AbortSignal이 중지되면 취소 오류를 반환한다", async () => {
    const fetchMock = vi.fn().mockImplementation((_url, request) =>
      new Promise((_resolve, reject) => {
        request.signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"))
        })
      }),
    )
    vi.stubGlobal("fetch", fetchMock)
    const controller = new AbortController()

    const pending = sendOpenWebUIStreamingMessage({
      prompt: "질문",
      roomId: "room-1",
      signal: controller.signal,
    })
    controller.abort()

    await expect(pending).rejects.toMatchObject({
      name: "AbortError",
      message: "응답 생성을 중지했습니다.",
    })
  })
})
