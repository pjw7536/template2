import { describe, expect, it } from "vitest"

import {
  isAssistantAppContextReady,
  resolveAssistantSurface,
} from "./surfaceConfig"

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
      profileVersion: 1,
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
      profileVersion: 1,
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

  it.each(["appstore", "emails", "observer"])(
    "%s 앱 지식을 끄면 Tool 없는 일반 대화 surface를 반환한다",
    (appKey) => {
      expect(resolveAssistantSurface({ appKey, useAppContext: false })).toEqual({
        mode: "portal",
        profileKey: "portal-default",
        profileVersion: 2,
        appContextKey: "assistant:openwebui:assistant",
        toolInputs: {},
      })
    },
  )

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
