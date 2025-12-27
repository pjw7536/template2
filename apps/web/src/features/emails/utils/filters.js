import { DEFAULT_EMAIL_PAGE_SIZE, EMAIL_PAGE_SIZE_OPTIONS } from "./emailPagination"

// 이메일 목록 쿼리 파라미터를 일관되게 정규화하는 헬퍼
// - 숫자/문자 타입을 정리해 캐시 키 변동을 최소화합니다.
// - 잘못된 페이지 크기 입력을 방지하고, 지정된 옵션에 맞춥니다.
export function normalizeEmailListFilters(rawFilters = {}) {
  const allowedPageSizes = new Set(EMAIL_PAGE_SIZE_OPTIONS)
  const safePageSize = (() => {
    const parsed = Number(rawFilters.pageSize ?? DEFAULT_EMAIL_PAGE_SIZE)
    if (Number.isNaN(parsed) || parsed <= 0) return DEFAULT_EMAIL_PAGE_SIZE
    return allowedPageSizes.has(parsed) ? parsed : DEFAULT_EMAIL_PAGE_SIZE
  })()

  const parsePage = (value) => {
    const parsed = Number(value ?? 1)
    if (Number.isNaN(parsed) || parsed <= 0) return 1
    return parsed
  }

  const trim = (value) => (typeof value === "string" ? value.trim() : "")
  const scope = trim(rawFilters.scope)

  return {
    scope: scope === "sent" ? "sent" : "inbox",
    page: parsePage(rawFilters.page),
    pageSize: safePageSize,
    userSdwtProd: trim(rawFilters.userSdwtProd),
    q: trim(rawFilters.q),
    sender: trim(rawFilters.sender),
    recipient: trim(rawFilters.recipient),
    dateFrom: trim(rawFilters.dateFrom),
    dateTo: trim(rawFilters.dateTo),
  }
}
