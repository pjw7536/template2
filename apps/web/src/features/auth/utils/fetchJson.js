// 파일 경로: src/features/auth/utils/fetchJson.js
// fetch 호출을 공통으로 다루기 위한 헬퍼입니다.
// - JSON 응답과 일반 텍스트 응답을 모두 안전하게 처리합니다.
// - AuthProvider뿐 아니라 향후 인증 관련 API 호출에서도 재사용할 수 있습니다.

/**
 * @template T
 * @typedef {Object} FetchResult
 * @property {boolean} ok - HTTP ok 여부(response.ok)
 * @property {number} status - HTTP 상태 코드
 * @property {T|null} data - 파싱된 데이터(JSON 또는 null)
 * @property {string | null} [error] - 오류 메시지(있을 경우)
 */

/**
 * fetch JSON 유틸 함수
 * @template T
 * @param {string} url - 호출할 URL
 * @param {RequestInit} [options] - fetch 옵션
 * @returns {Promise<FetchResult<T>>}
 */
export async function fetchJson(url, options = {}) {
  /**
   * 타입: FetchResult<any>
   * @type {FetchResult<any>}
   */
  const base = { ok: false, status: 0, data: null, error: null }
  let response

  try {
    response = await fetch(url, {
      credentials: "include", // ✅ 쿠키 기반 세션 정보를 항상 포함
      ...options,
    })
  } catch (networkError) {
    return { ...base, error: String(networkError) }
  }

  const contentType = response.headers.get("content-type") || ""
  let data = null

  try {
    if (contentType.includes("application/json")) {
      data = await response.json()
    } else {
      const text = await response.text()
      try {
        data = text ? JSON.parse(text) : null
      } catch {
        data = text || null // JSON 파싱 실패 시 원본 텍스트를 유지
      }
    }
  } catch {
    // 파싱에 실패하면 data를 null로 유지합니다.
  }

  return {
    ok: response.ok,
    status: response.status,
    data,
    error: response.ok ? null : (typeof data === "string" ? data : null),
  }
}
