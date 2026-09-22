import { describe, expect, it } from "vitest"

import {
  buildAffiliationRequestRows,
  buildMemberRows,
  selectVisibleMemberRows,
} from "./memberRows"

describe("Account 멤버 행 변환", () => {
  it("멤버 표시값과 역할 fallback을 안정적인 table 행으로 변환한다", () => {
    expect(buildMemberRows([
      {
        userId: 7,
        username: "사용자",
        department: "ETCH",
        userSdwtProd: "ETCH_A",
        role: "UNKNOWN",
        isCurrentAffiliation: true,
      },
    ])).toEqual([
      expect.objectContaining({
        id: "member-7",
        name: "사용자",
        affiliationLabel: "ETCH / ETCH_A",
        memberRole: "viewer",
        isCurrentAffiliation: true,
      }),
    ])
  })

  it("소속 변경 요청의 대상과 승인 역할을 table 계약으로 변환한다", () => {
    expect(buildAffiliationRequestRows([
      {
        id: 11,
        user: { sabun: "S001", knoxId: "knox-1" },
        department: "PHOTO",
        line: "L1",
        toUserSdwtProd: "PHOTO_A",
        role: "MANAGER",
        status: "pending",
      },
    ])).toEqual([
      expect.objectContaining({
        id: "request-11",
        name: "S001",
        affiliationLabel: "PHOTO / L1 / PHOTO_A",
        approvalRole: "manager",
        status: "pending",
      }),
    ])
  })

  it("활성 tab에 맞는 행만 노출하고 전체에서는 요청을 먼저 둔다", () => {
    const memberRows = [{ id: "member" }]
    const requestRows = [{ id: "request" }]

    expect(selectVisibleMemberRows({ activeTab: "members", memberRows, requestRows })).toBe(memberRows)
    expect(selectVisibleMemberRows({ activeTab: "requests", memberRows, requestRows })).toBe(requestRows)
    expect(selectVisibleMemberRows({ activeTab: "all", memberRows, requestRows })).toEqual([
      { id: "request" },
      { id: "member" },
    ])
  })
})
