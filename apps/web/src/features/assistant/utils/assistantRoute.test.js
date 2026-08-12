import { describe, expect, it } from "vitest"

import { isEmailAssistantRoute } from "./assistantRoute"

describe("isEmailAssistantRoute", () => {
  it.each(["/emails", "/emails/", "/emails/inbox", "/EMAILS/sent"])(
    "%s는 메일 RAG 화면으로 판별한다",
    (pathname) => {
      expect(isEmailAssistantRoute(pathname)).toBe(true)
    },
  )

  it.each(["/", "/assistant", "/observer", "/emails-archive"])(
    "%s는 OpenWebUI 화면으로 판별한다",
    (pathname) => {
      expect(isEmailAssistantRoute(pathname)).toBe(false)
    },
  )
})
