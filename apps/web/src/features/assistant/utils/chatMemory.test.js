import { describe, expect, it } from "vitest"

import {
  formatChatHistoryContent,
  getChatMemoryKey,
  isSameChatMemory,
} from "./chatMemory"

describe("chatMemory", () => {
  it("일반 Chat과 모든 Observer 문맥을 같은 기억 키로 묶는다", () => {
    expect(getChatMemoryKey("assistant:openwebui")).toBe("chatwidget:shared")
    expect(getChatMemoryKey("observer:v1:scope-a")).toBe("chatwidget:shared")
    expect(isSameChatMemory("assistant:openwebui", "observer:v1:scope-b")).toBe(true)
  })

  it("Email RAG 문맥은 공유 기억과 분리한다", () => {
    expect(getChatMemoryKey("assistant")).toBe("assistant")
    expect(isSameChatMemory("assistant", "assistant:openwebui")).toBe(false)
  })

  it("다른 모드의 이전 메시지에만 출처를 표시한다", () => {
    expect(
      formatChatHistoryContent(
        "이전 분석",
        "observer:v1:scope-a",
        "assistant:openwebui",
      ),
    ).toBe("[이전 대화 출처: Observer]\n이전 분석")
    expect(
      formatChatHistoryContent(
        "같은 분석",
        "observer:v1:scope-a",
        "observer:v1:scope-a",
      ),
    ).toBe("같은 분석")
  })
})
