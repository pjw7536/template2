import { describe, expect, it } from "vitest"

import {
  MAX_ASSISTANT_CONTEXT_SNAPSHOT_JSON_BYTES,
  MAX_ASSISTANT_MESSAGE_CHARS,
  MAX_ASSISTANT_SOURCES,
  MAX_ASSISTANT_SOURCES_JSON_BYTES,
  normalizeGeneratedAssistantMessage,
} from "./chatLimits"

function jsonByteLength(value) {
  return new TextEncoder().encode(JSON.stringify(value)).length
}

describe("생성 답변 저장 제한 정규화", () => {
  it("답변 내용과 출처를 서버 저장 상한 안으로 줄인다", () => {
    const message = normalizeGeneratedAssistantMessage({
      content: "가".repeat(MAX_ASSISTANT_MESSAGE_CHARS + 100),
      sources: Array.from({ length: 60 }, (_, index) => ({
        title: `출처 ${index}`,
        snippet: "나".repeat(3000),
      })),
    })

    expect(message.content.length).toBeLessThanOrEqual(MAX_ASSISTANT_MESSAGE_CHARS)
    expect(message.content).toContain("답변 일부를 생략했습니다")
    expect(message.sources.length).toBeLessThanOrEqual(MAX_ASSISTANT_SOURCES)
    expect(jsonByteLength(message.sources)).toBeLessThanOrEqual(
      MAX_ASSISTANT_SOURCES_JSON_BYTES,
    )
  })

  it("분석 근거 배열을 줄여 snapshot 저장 상한을 지킨다", () => {
    const message = normalizeGeneratedAssistantMessage({
      content: "분석 답변",
      contextSnapshot: {
        scope: { eqpId: "EQP-ALPHA" },
        evidence: Array.from({ length: 200 }, (_, index) => ({
          finding: `근거 ${index}`,
          evidenceIds: Array.from({ length: 100 }, (__, idIndex) =>
            `LOG-${index}-${idIndex}-${"가".repeat(30)}`,
          ),
        })),
      },
    })

    expect(message.contextSnapshot).toBeTruthy()
    expect(jsonByteLength(message.contextSnapshot)).toBeLessThanOrEqual(
      MAX_ASSISTANT_CONTEXT_SNAPSHOT_JSON_BYTES,
    )
  })
})
