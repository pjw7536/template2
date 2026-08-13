import { describe, expect, it } from "vitest"

import { resolveAssistantSurface } from "./surfaceConfig"

describe("resolveAssistantSurface", () => {
  it("Portal 앱을 명시적인 app context로 변환한다", () => {
    expect(resolveAssistantSurface({ appKey: "appstore" })).toEqual({
      mode: "portal",
      profileKey: "portal-default",
      profileVersion: 1,
      appContextKey: "assistant:openwebui:appstore",
      toolInputs: {},
    })
  })

  it("Email RAG 선택을 정규화된 Tool 입력으로 변환한다", () => {
    expect(
      resolveAssistantSurface({
        appKey: "emails",
        permissionGroups: ["group-a", "group-a", ""],
        ragIndexNames: ["rp-email"],
      }),
    ).toEqual({
      mode: "email",
      profileKey: "email-rag",
      profileVersion: 1,
      appContextKey: "assistant",
      toolInputs: {
        "rag.search": {
          permissionGroups: ["group-a"],
          ragIndexes: ["rp-email"],
        },
      },
    })
  })

  it("Observer page context가 준비된 경우에만 분석 surface를 반환한다", () => {
    expect(resolveAssistantSurface({ appKey: "observer" })).toBeNull()

    expect(
      resolveAssistantSurface({
        appKey: "observer",
        pageContext: {
          kind: "observer",
          key: "observer:v1:scope-hash",
          scope: {
            eqpId: "EQP-01",
            from: "2026-08-01",
            to: "2026-08-13",
            logTypes: ["eqp", "tip"],
            tipGroups: ["__ALL__"],
          },
        },
      }),
    ).toEqual({
      mode: "observer",
      profileKey: "observer-analysis",
      profileVersion: 1,
      appContextKey: "observer:v1:scope-hash",
      toolInputs: {
        "observer.analysis": {
          eqpId: "EQP-01",
          from: "2026-08-01",
          to: "2026-08-13",
          logTypes: ["eqp", "tip"],
          tipGroups: ["__ALL__"],
        },
      },
    })
  })

  it("등록되지 않은 앱을 Portal로 추정하지 않는다", () => {
    expect(resolveAssistantSurface({ appKey: "unknown" })).toBeNull()
  })
})
