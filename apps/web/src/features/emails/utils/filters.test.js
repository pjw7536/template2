import { describe, expect, it } from "vitest"

import { buildEmailListSearchParams, normalizeEmailListFilters } from "./filters"

describe("Emails 목록 filter 계약", () => {
  it("잘못된 page와 page size를 기본값으로 되돌린다", () => {
    expect(normalizeEmailListFilters({ page: 0, pageSize: 999, scope: "unknown" }))
      .toEqual(expect.objectContaining({ page: 1, pageSize: 20, scope: "inbox" }))
  })

  it("frontend filter를 backend snake_case query로 변환한다", () => {
    expect(buildEmailListSearchParams({
      page: 2,
      pageSize: 25,
      userSdwtProd: " ETCH_A ",
      q: " report ",
      dateFrom: "2026-08-01",
    })).toEqual({
      page: 2,
      page_size: 25,
      user_sdwt_prod: "ETCH_A",
      q: "report",
      date_from: "2026-08-01",
    })
  })

  it("sent 목록에서는 mailbox query를 제외한다", () => {
    expect(buildEmailListSearchParams(
      { userSdwtProd: "ETCH_A" },
      { includeMailbox: false },
    )).toEqual({ page: 1, page_size: 20 })
  })
})
