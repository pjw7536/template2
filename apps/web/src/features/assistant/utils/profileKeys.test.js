import { describe, expect, it } from "vitest"

import {
  ASSISTANT_KNOWLEDGE_MODES,
  ASSISTANT_PROFILE_KEYS,
  ASSISTANT_PROFILE_VERSIONS,
} from "./profileKeys"

describe("assistant profile keys", () => {
  it("지원 Profile key와 version만 고정 계약으로 노출한다", () => {
    expect(ASSISTANT_PROFILE_KEYS).toEqual({
      portal: "portal-default",
      emails: "email-rag",
      observer: "observer-analysis",
      appstore: "appstore-context",
      lineDashboard: "line-dashboard-context",
      autoKnowledge: "auto-knowledge",
    })
    expect(ASSISTANT_PROFILE_VERSIONS[ASSISTANT_PROFILE_KEYS.portal]).toBe(2)
    expect(ASSISTANT_PROFILE_VERSIONS[ASSISTANT_PROFILE_KEYS.emails]).toBe(2)
    expect(ASSISTANT_PROFILE_VERSIONS[ASSISTANT_PROFILE_KEYS.observer]).toBe(2)
    expect(ASSISTANT_PROFILE_VERSIONS[ASSISTANT_PROFILE_KEYS.appstore]).toBe(2)
    expect(ASSISTANT_PROFILE_VERSIONS[ASSISTANT_PROFILE_KEYS.lineDashboard]).toBe(2)
    expect(ASSISTANT_PROFILE_VERSIONS[ASSISTANT_PROFILE_KEYS.autoKnowledge]).toBe(1)
    expect(ASSISTANT_KNOWLEDGE_MODES).toEqual({
      currentApp: "current_app",
      auto: "auto",
    })
  })
})
