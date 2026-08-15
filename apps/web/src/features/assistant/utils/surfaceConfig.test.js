import { describe, expect, it } from "vitest"

import {
  isAssistantAppContextReady,
  resolveAssistantSurface,
} from "./surfaceConfig"
import { ASSISTANT_KNOWLEDGE_MODES } from "./profileKeys"

describe("resolveAssistantSurface", () => {
  it("Portal 홈은 앱 지식이 없는 일반 대화 surface를 반환한다", () => {
    expect(resolveAssistantSurface({ appKey: "portal" })).toEqual({
      mode: "portal",
      profileKey: "portal-default",
      profileVersion: 2,
      appContextKey: "assistant:openwebui:assistant",
      toolInputs: {},
    })
  })

  it("Appstore 화면 조건을 카탈로그 Tool surface로 변환한다", () => {
    expect(resolveAssistantSurface({
      appKey: "appstore",
      pageContext: {
        kind: "appstore",
        key: "appstore:v1",
        scope: { query: "분석", category: "Tools", selectedAppId: 7 },
      },
    })).toEqual({
      mode: "appstore",
      profileKey: "appstore-context",
      profileVersion: 2,
      appContextKey: "appstore:v1",
      toolInputs: {
        "appstore.catalog": {
          query: "분석",
          category: "Tools",
          selectedAppId: 7,
        },
      },
    })
  })

  it("ESOP line과 기간을 snapshot Tool surface로 변환한다", () => {
    expect(resolveAssistantSurface({
      appKey: "line-dashboard",
      pageContext: {
        kind: "line-dashboard",
        key: "line-dashboard:v1",
        scope: {
          view: "history",
          lineId: "L1",
          from: "2026-08-01",
          to: "2026-08-14",
        },
      },
    })).toEqual({
      mode: "line-dashboard",
      profileKey: "line-dashboard-context",
      profileVersion: 2,
      appContextKey: "line-dashboard:v1",
      toolInputs: {
        "line-dashboard.snapshot": {
          view: "history",
          lineId: "L1",
          from: "2026-08-01",
          to: "2026-08-14",
        },
      },
    })
  })

  it("자동 지식 선택은 권한 필터링 전 네 앱 후보를 Profile에 전달한다", () => {
    expect(resolveAssistantSurface({
      appKey: "emails",
      knowledgeMode: ASSISTANT_KNOWLEDGE_MODES.auto,
      permissionGroups: ["group-a"],
      ragIndexNames: ["rp-email"],
    })).toEqual({
      mode: "auto",
      profileKey: "auto-knowledge",
      profileVersion: 1,
      appContextKey: "assistant:openwebui:emails",
      toolInputs: {
        "rag.search": {
          permissionGroups: ["group-a"],
          ragIndexes: ["rp-email"],
        },
        "observer.analysis": {},
        "appstore.catalog": {
          query: "",
          category: "all",
          selectedAppId: null,
        },
        "line-dashboard.snapshot": {},
      },
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
      profileVersion: 2,
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
    expect(isAssistantAppContextReady({ appKey: "observer" })).toBe(false)
    expect(resolveAssistantSurface({ appKey: "observer" })).toBeNull()

    const observerOptions = {
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
    }
    expect(isAssistantAppContextReady(observerOptions)).toBe(true)
    expect(resolveAssistantSurface(observerOptions)).toEqual({
      mode: "observer",
      profileKey: "observer-analysis",
      profileVersion: 2,
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

  it("Observer 자동 모드는 현재 화면 범위를 후보 Tool에 포함한다", () => {
    const pageContext = {
      kind: "observer",
      key: "observer:v1:scope-hash",
      scope: {
        eqpId: "EQP-01",
        from: "2026-08-01",
        to: "2026-08-13",
        logTypes: ["eqp"],
        tipGroups: ["__ALL__"],
      },
    }
    expect(resolveAssistantSurface({
      appKey: "observer",
      knowledgeMode: ASSISTANT_KNOWLEDGE_MODES.auto,
      pageContext,
    })).toMatchObject({
      mode: "auto",
      profileKey: "auto-knowledge",
      appContextKey: "assistant:openwebui:observer",
      toolInputs: {
        "observer.analysis": pageContext.scope,
      },
    })
  })

  it("등록되지 않은 앱을 Portal로 추정하지 않는다", () => {
    expect(resolveAssistantSurface({ appKey: "unknown" })).toBeNull()
  })
})
