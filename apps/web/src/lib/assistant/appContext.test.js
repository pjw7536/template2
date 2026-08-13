import { describe, expect, it } from "vitest"

import {
  buildOpenWebUIContextKey,
  getAssistantAppContext,
  resolveAssistantAppContext,
} from "./appContext"

describe("Assistant 앱 컨텍스트", () => {
  it.each([
    ["/", "portal"],
    ["/appstore", "appstore"],
    ["/ESOP_Dashboard/status/ETCH-1", "line-dashboard"],
    ["/observer/EQP-01", "observer"],
    ["/emails/inbox", "emails"],
    ["/EMAILS/sent/", "emails"],
    ["/spider/l0", "l0-spider"],
    ["/spider/l3", "l3-spider"],
    ["/spider", "spider"],
    ["/settings/permissions", "settings"],
  ])("%s 경로를 %s 앱으로 해석한다", (pathname, expectedKey) => {
    expect(resolveAssistantAppContext(pathname).key).toBe(expectedKey)
  })

  it("알 수 없는 앱 키와 경로는 Portal로 안전하게 되돌린다", () => {
    expect(getAssistantAppContext("unknown").key).toBe("portal")
    expect(resolveAssistantAppContext("/unknown/path").key).toBe("portal")
    expect(buildOpenWebUIContextKey("unknown")).toBe("assistant:openwebui:portal")
  })
})
