// src/features/line-dashboard/api/columns.js

import { DATE_COLUMN_CANDIDATES } from "./constants"

/* ============================================================================
 * ✅ findColumn(columnNames, target)
 * ----------------------------------------------------------------------------
 * - 데이터베이스에서 받은 컬럼 이름 배열(columnNames) 중에서
 *   특정 이름(target)과 "대소문자 구분 없이" 일치하는 항목을 찾아줍니다.
 *
 * 예시)
 *   findColumn(["ID", "Created_At", "Name"], "created_at")
 *   → "Created_At" (대소문자 달라도 OK)
 * ============================================================================
 */
export function findColumn(columnNames, target) {
  // 안전하게 배열 형태로 강제 변환 (null, undefined 방지)
  const list = Array.isArray(columnNames) ? columnNames : []

  // 찾고 싶은 대상 문자열을 소문자로 통일
  const targetLower = String(target ?? "").toLowerCase()

  // 모든 컬럼 이름을 순회하며 비교
  for (const name of list) {
    if (typeof name !== "string") continue // 문자열이 아닌 값은 무시
    if (name.toLowerCase() === targetLower) return name // 일치하면 원래 이름 그대로 반환
  }

  // 끝까지 못 찾으면 null
  return null
}

/* ============================================================================
 * ✅ pickBaseTimestampColumn(columnNames)
 * ----------------------------------------------------------------------------
 * - DATE_COLUMN_CANDIDATES에 정의된 "날짜/시간 관련 컬럼 이름 후보들" 중에서
 *   실제 존재하는 첫 번째 컬럼 이름을 찾아 반환합니다.
 *
 * 예시)
 *   DATE_COLUMN_CANDIDATES = ["updated_at", "created_at", "timestamp", "date"]
 *   columnNames = ["id", "timestamp"]
 *   → "timestamp" 반환
 *
 * - 없으면 null 반환
 * ============================================================================
 */
export function pickBaseTimestampColumn(columnNames) {
  // 후보 목록을 순서대로 확인
  for (const candidate of DATE_COLUMN_CANDIDATES) {
    const found = findColumn(columnNames, candidate)
    if (found) return found // 첫 번째로 발견된 컬럼 반환
  }

  // 후보 중 아무 것도 없으면 null
  return null
}
