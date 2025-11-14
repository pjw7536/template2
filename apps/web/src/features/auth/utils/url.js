// src/features/auth/utils/url.js
// 로그인/리다이렉트 관련 URL을 안전하게 만들기 위한 유틸 모음입니다.

/**
 * next 파라미터에 사용할 절대 URL 생성
 * @param {string | undefined} nextPath - 이동하고 싶은 경로(절대/상대 허용)
 * @param {string | undefined} base - 기준이 될 절대 경로 (예: 프론트엔드 도메인)
 * @returns {string | undefined}
 */
export function buildNextUrl(nextPath, base) {
  if (!nextPath) return undefined

  const trimmed = String(nextPath).trim()
  if (!trimmed) return undefined

  const baseUrl = base && base.trim() ? base.trim() : (typeof window !== "undefined" ? window.location.origin : "")
  if (!baseUrl) return trimmed

  try {
    return new URL(trimmed, baseUrl).toString()
  } catch {
    if (trimmed.startsWith("/")) {
      return `${baseUrl.replace(/\/+$/, "")}${trimmed}`
    }
    return trimmed
  }
}

/**
 * 로그인 URL에 next 파라미터를 붙여주는 함수
 * @param {string} url - 로그인 URL(절대/상대)
 * @param {string | undefined} nextUrl - next 파라미터로 전달할 절대 URL
 */
export function appendNextParam(url, nextUrl) {
  if (!nextUrl) return url

  try {
    const u = new URL(url)
    u.searchParams.set("next", nextUrl)
    return u.toString()
  } catch {
    const sep = url.includes("?") ? "&" : "?"
    return `${url}${sep}next=${encodeURIComponent(nextUrl)}`
  }
}
