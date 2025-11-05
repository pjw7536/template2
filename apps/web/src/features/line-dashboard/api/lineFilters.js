// src/features/line-dashboard/api/lineFilters.js
import { runQuery } from "@/lib/db"
import { LINE_SDWT_TABLE_NAME } from "./constants"
import { findColumn } from "./columns"

const USER_SDWT_PROD_LOOKUP_QUERY = `
  SELECT DISTINCT user_sdwt_prod
  FROM \`${LINE_SDWT_TABLE_NAME}\`
  WHERE line_id = ?
    AND user_sdwt_prod IS NOT NULL
    AND user_sdwt_prod <> ''
`

/**
 * 특정 line_id에 연결된 user_sdwt_prod 목록 조회
 * - 문자열만 추려서 trim 후 중복 제거(Set)
 */
async function getUserSdwtProdValues(lineId) {
  const rows = await runQuery(USER_SDWT_PROD_LOOKUP_QUERY, [lineId])
  const set = new Set()
  for (const r of rows || []) {
    const v = typeof r?.user_sdwt_prod === "string" ? r.user_sdwt_prod.trim() : ""
    if (v) set.add(v)
  }
  return Array.from(set)
}

/**
 * 라인 필터 WHERE/params 생성 (간결 버전)
 * ------------------------------------------------------------
 * 1) user_sdwt_prod 컬럼이 존재하고, 해당 line에 매핑값이 있으면:
 *    - `user_sdwt_prod IN (?, ?, …)` 로 필터
 * 2) 그렇지 않으면(컬럼이 없거나 매핑이 비었으면):
 *    - line_id 컬럼이 있는 경우 `line_id = ?` 로 필터
 * 3) line_id도 없으면 필터 없이 반환
 *
 * @param {string[]} columnNames - 실제 테이블 컬럼 이름들
 * @param {string} lineId        - 외부에서 이미 정규화(normalize)된 line_id
 * @returns {{ filters: string[], params: any[] }}
 *   - filters: WHERE 절 조각 배열 (예: ["`line_id` = ?", "`user_sdwt_prod` IN (?, ?)"])
 *   - params : 바인딩 값 배열
 */
export async function buildLineFilters(columnNames, lineId) {
  const filters = []
  const params = []

  // lineId가 없으면 필터 없이 종료
  if (!lineId) return { filters, params }

  // 1) user_sdwt_prod 우선 사용
  const usdwtCol = findColumn(columnNames, "user_sdwt_prod")
  if (usdwtCol) {
    const values = await getUserSdwtProdValues(lineId)
    if (values.length > 0) {
      const placeholders = values.map(() => "?").join(", ")
      filters.push(`\`${usdwtCol}\` IN (${placeholders})`)
      params.push(...values)
      return { filters, params }
    }
  }

  // 2) 폴백: line_id = ?
  const lineCol = findColumn(columnNames, "line_id")
  if (lineCol) {
    filters.push(`\`${lineCol}\` = ?`)
    params.push(lineId)
  }

  return { filters, params }
}
