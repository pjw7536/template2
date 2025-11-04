// src/features/line-dashboard/api/validation.js
import { DATE_ONLY_REGEX, SAFE_IDENTIFIER } from "./constants"

/* ============================================================================
 * 🧩 validation.js — 입력값 검증 관련 유틸 함수 모음
 * ----------------------------------------------------------------------------
 * ✅ 주요 목적
 * - SQL 인젝션 방지: 테이블/컬럼 이름에 위험한 문자가 들어오는 것을 차단
 * - 날짜 문자열 검증: YYYY-MM-DD 형식이 맞는지 확인
 * ========================================================================== */

/**
 * 문자열을 SQL용 안전한 식별자(identifier)로 정리합니다.
 * - 주로 테이블명, 컬럼명 등 SQL 쿼리 내에서 직접 문자열로 들어가는 항목에 사용
 * - 영문, 숫자, 밑줄(_)만 허용합니다.
 * - 조건에 맞지 않으면 fallback(기본값)을 반환합니다.
 *
 * 예시:
 *   sanitizeIdentifier("line_sdwt") → "line_sdwt"
 *   sanitizeIdentifier("DROP TABLE users;") → null (안전하게 차단)
 */
export function sanitizeIdentifier(value, fallback = null) {
  if (typeof value !== "string") return fallback

  const trimmed = value.trim()
  return SAFE_IDENTIFIER.test(trimmed) ? trimmed : fallback
}

/**
 * 날짜 문자열을 검증합니다 (형식: YYYY-MM-DD)
 * - 올바른 형식일 경우 그대로 반환
 * - 잘못된 형식(예: "2025/01/01" 또는 "25-01-01")이면 null 반환
 *
 * 예시:
 *   normalizeDateOnly("2025-11-04") → "2025-11-04"
 *   normalizeDateOnly("2025/11/04") → null
 */
export function normalizeDateOnly(value) {
  if (typeof value !== "string") return null

  const trimmed = value.trim()
  return DATE_ONLY_REGEX.test(trimmed) ? trimmed : null
}
