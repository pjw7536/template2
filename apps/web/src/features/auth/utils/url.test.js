import { describe, expect, it } from "vitest"

import { appendTargetParam, buildTargetUrl } from "./url"

describe("Auth redirect target contract", () => {
  it("상대 경로를 frontend origin의 절대 target으로 변환한다", () => {
    expect(buildTargetUrl("/settings/account", "https://portal.example.com")).toBe(
      "https://portal.example.com/settings/account",
    )
  })

  it("로그인 URL에는 target만 추가한다", () => {
    const result = appendTargetParam(
      "https://api.example.com/api/v1/auth/login",
      "https://portal.example.com/settings/account",
    )
    const url = new URL(result)

    expect(url.searchParams.get("target")).toBe(
      "https://portal.example.com/settings/account",
    )
    expect(url.searchParams.has("next")).toBe(false)
  })
})
