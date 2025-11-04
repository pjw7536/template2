// src/features/line-dashboard/api/validation.js
import { DATE_ONLY_REGEX, SAFE_IDENTIFIER } from "./constants"

// 컬럼/테이블 이름용 파라미터를 안전하게 정리해 줍니다.
export function sanitizeIdentifier(value, fallback = null) {
  if (typeof value !== "string") return fallback
  const trimmed = value.trim()
  return SAFE_IDENTIFIER.test(trimmed) ? trimmed : fallback
}

// YYYY-MM-DD 형식인지 검사하고 맞으면 그대로 돌려줍니다.
export function normalizeDateOnly(value) {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return DATE_ONLY_REGEX.test(trimmed) ? trimmed : null
}
