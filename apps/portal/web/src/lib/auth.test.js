import { describe, expect, it } from "vitest"

import { formatProfileName } from "./auth"

describe("formatProfileName", () => {
  it("조합한 표시 이름을 반환하며 계정 데이터는 보존한다", () => {
    const user = { username: "홍길동", knoxId: "hong.gildong", avatarId: "90000001" }
    expect(formatProfileName(user)).toBe("홍길동(hong.gildong)")
    expect(user).toEqual({ username: "홍길동", knoxId: "hong.gildong", avatarId: "90000001" })
  })

  it("프로필 항목 하나만 있으면 그 값만 표시한다", () => {
    expect(formatProfileName({ username: "홍길동" })).toBe("홍길동")
    expect(formatProfileName({ knoxId: "hong.gildong" })).toBe("hong.gildong")
  })
})
