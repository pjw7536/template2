import { describe, expect, it } from "vitest"

import { buildEmailSourceUrl } from "./buildEmailSourceUrl"

describe("Assistant 이메일 근거 링크", () => {
  it("접근 가능한 메일함을 canonical query로 전달한다", () => {
    expect(
      buildEmailSourceUrl("DOC-1", "S1", {
        availableMailboxes: [{ userSdwtProd: "S1" }],
      }),
    ).toBe("/emails/inbox?userSdwtProd=S1&emailId=DOC-1")
  })

  it("보낸 메일 근거는 sent route로 연결한다", () => {
    expect(buildEmailSourceUrl("DOC-2", "__sent__")).toBe(
      "/emails/sent?emailId=DOC-2",
    )
  })
})
