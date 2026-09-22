import { describe, expect, it, vi } from "vitest"

import { parseAssistantSseBlock, readAssistantSse } from "./standardSse"

describe("standard Assistant SSE", () => {
  it("event와 여러 data 줄을 JSON으로 해석한다", () => {
    expect(parseAssistantSseBlock('event: message.delta\ndata: {"content":\ndata: "안녕"}')).toEqual({
      event: "message.delta",
      payload: { content: "안녕" },
    })
  })

  it("CRLF chunk 경계에서도 event 순서를 보존한다", async () => {
    const chunks = [
      new TextEncoder().encode('event: run.started\r\ndata: {"runId":"1"}\r\n\r\n'),
      new TextEncoder().encode('event: run.completed\ndata: {"runId":"1"}\n\n'),
    ]
    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: chunks[0] })
        .mockResolvedValueOnce({ done: false, value: chunks[1] })
        .mockResolvedValueOnce({ done: true }),
      releaseLock: vi.fn(),
    }
    const events = await readAssistantSse({ body: { getReader: () => reader } })
    expect(events.map(({ event }) => event)).toEqual(["run.started", "run.completed"])
  })
})
