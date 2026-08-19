import { describe, expect, it } from "vitest"

import { normalizeRouteError } from "./routeError"

describe("normalizeRouteError", () => {
  it("공개 status, code, message만 오류 화면 값으로 사용한다", () => {
    const result = normalizeRouteError({
      status: 403,
      statusText: "Forbidden",
      internal: false,
      data: {
        code: "scope_access_required",
        message: "Access to this scope is required.",
        stack: "민감한 내부 stack",
      },
    })

    expect(result).toEqual({
      title: "Request could not be completed",
      description: "Access to this scope is required.",
      statusLabel: "HTTP 403 · scope_access_required",
    })
    expect(JSON.stringify(result)).not.toContain("민감한 내부 stack")
  })

  it("일반 예외의 내부 메시지는 노출하지 않는다", () => {
    const result = normalizeRouteError(new Error("database password leaked"))

    expect(result.description).not.toContain("database password leaked")
    expect(result.statusLabel).toBe("")
  })
})
