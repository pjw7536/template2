import { afterEach, describe, expect, it, vi } from "vitest"

import { accountApi } from "./accountApi"

function jsonResponse(payload = {}) {
  return {
    ok: true,
    headers: { get: vi.fn().mockReturnValue("application/json") },
    json: vi.fn().mockResolvedValue(payload),
  }
}

function errorResponse(payload = {}) {
  return {
    ...jsonResponse(payload),
    ok: false,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("Account affiliation API contract", () => {
  it("canonical 오류 message를 사용자 오류로 전달한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errorResponse({ message: "소속 요청이 올바르지 않습니다." })),
    )

    await expect(accountApi.fetchAffiliation()).rejects.toThrow(
      "소속 요청이 올바르지 않습니다.",
    )
  })

  it("소속 변경 body는 canonical 필드만 전송한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "pending" }))
    vi.stubGlobal("fetch", fetchMock)

    await accountApi.updateAffiliation({
      userSdwtProd: "GROUP-A",
      department: "무시되어야 함",
      line: "무시되어야 함",
    })

    const request = fetchMock.mock.calls[0][1]
    expect(JSON.parse(request.body)).toEqual({ userSdwtProd: "GROUP-A" })
  })

  it("소속 요청과 멤버 query는 camelCase만 사용한다", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ results: [] }))
      .mockResolvedValueOnce(jsonResponse({ members: [] }))
    vi.stubGlobal("fetch", fetchMock)

    await accountApi.fetchAffiliationRequests({
      search: "kim",
      userSdwtProd: "GROUP-A",
      pageSize: 30,
    })
    await accountApi.fetchAffiliationMembers({ userSdwtProd: "GROUP-A" })

    const requestUrl = new URL(fetchMock.mock.calls[0][0])
    const membersUrl = new URL(fetchMock.mock.calls[1][0])
    expect(Object.fromEntries(requestUrl.searchParams)).toEqual({
      page: "1",
      pageSize: "30",
      status: "pending",
      search: "kim",
      userSdwtProd: "GROUP-A",
    })
    expect(Object.fromEntries(membersUrl.searchParams)).toEqual({
      userSdwtProd: "GROUP-A",
    })
  })

  it("승인 body는 이전 id와 snake_case 별칭을 전송하지 않는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "approved" }))
    vi.stubGlobal("fetch", fetchMock)

    await accountApi.decideAffiliationRequest({
      changeId: 12,
      decision: "approve",
      id: 99,
      rejection_reason: "무시되어야 함",
    })

    const request = fetchMock.mock.calls[0][1]
    expect(JSON.parse(request.body)).toEqual({
      changeId: 12,
      decision: "approve",
    })
  })

  it("사용자 pool은 canonical 수신인 식별자가 없는 행을 제외한다", async () => {
    const canonicalUser = {
      id: 7,
      userId: 7,
      recipientType: "user",
      recipientKey: "user:7",
      username: "사용자",
      displayName: "사용자",
      sabun: "S7",
      knoxId: "user.7",
      email: "user.7@example.com",
      department: "Dept",
      line: "L1",
      userSdwtProd: "GROUP-A",
    }
    const legacyIdOnlyUser = {
      ...canonicalUser,
      id: 8,
      userId: undefined,
      recipientKey: undefined,
    }
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        results: [canonicalUser, legacyIdOnlyUser],
        departments: ["Dept"],
        userSdwtProds: ["GROUP-A"],
      }),
    )
    vi.stubGlobal("fetch", fetchMock)

    const result = await accountApi.fetchUserPool()

    expect(result.results).toHaveLength(1)
    expect(result.results[0]).toMatchObject({
      userId: 7,
      recipientKey: "user:7",
    })
  })
})
