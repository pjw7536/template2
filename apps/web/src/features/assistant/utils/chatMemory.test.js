import { describe, expect, it } from "vitest"

import {
  formatChatHistoryContent,
  getChatMemoryKey,
  isSameChatMemory,
} from "./chatMemory"

describe("chatMemory", () => {
  it("Portal 앱, Email RAG와 Observer 문맥을 모두 같은 기억 키로 묶는다", () => {
    expect(getChatMemoryKey("assistant:openwebui")).toBe("chatwidget:shared")
    expect(getChatMemoryKey("assistant:openwebui:appstore")).toBe("chatwidget:shared")
    expect(getChatMemoryKey("observer:v1:scope-a")).toBe("chatwidget:shared")
    expect(getChatMemoryKey("assistant")).toBe("chatwidget:shared")
    expect(isSameChatMemory("assistant:openwebui", "observer:v1:scope-b")).toBe(true)
    expect(isSameChatMemory("assistant", "assistant:openwebui:appstore")).toBe(true)
  })

  it("다른 모드의 이전 메시지에만 출처를 표시한다", () => {
    expect(
      formatChatHistoryContent(
        "이전 분석",
        "observer:v1:scope-a",
        "assistant:openwebui:portal",
      ),
    ).toBe("[이전 대화 출처: Observer]\n이전 분석")
    expect(
      formatChatHistoryContent(
        "같은 분석",
        "observer:v1:scope-a",
        "observer:v1:scope-a",
      ),
    ).toBe("같은 분석")
    expect(
      formatChatHistoryContent(
        "앱 등록 상태를 확인해줘",
        "assistant:openwebui:appstore",
        "assistant:openwebui:portal",
      ),
    ).toBe("[이전 대화 출처: Appstore]\n앱 등록 상태를 확인해줘")
    expect(
      formatChatHistoryContent(
        "이전 메일 질문",
        "assistant",
        "assistant:openwebui:portal",
      ),
    ).toBe("[이전 대화 출처: Emails]\n이전 메일 질문")
  })
})
