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

// user_sdwt_prod 값을 우선적으로 활용하기 위해 라인별 매핑을 미리 조회합니다.
async function getUserSdwtProdValues(lineId) {
  const rows = await runQuery(USER_SDWT_PROD_LOOKUP_QUERY, [lineId])
  const unique = new Set()

  rows.forEach((row) => {
    const value = typeof row?.user_sdwt_prod === "string" ? row.user_sdwt_prod.trim() : ""
    if (value) unique.add(value)
  })

  return Array.from(unique)
}

/**
 * 라인 필터링에 사용할 WHERE 절 조각과 바인딩 값을 만들어 줍니다.
 * - user_sdwt_prod 컬럼이 있으면 IN 조건으로 좁혀주고,
 * - 그렇지 않으면 line_id 컬럼을 직접 사용합니다.
 * - 매핑 테이블에 값이 하나도 없으면 더 이상 조회할 필요가 없으므로 earlyEmpty를 true로 돌려줍니다.
 */
export async function buildLineFilters(columnNames, normalizedLineId) {
  const filters = []
  const params = []
  if (!normalizedLineId) return { filters, params, earlyEmpty: false }

  const userSdwtProdColumn = findColumn(columnNames, "user_sdwt_prod")
  if (userSdwtProdColumn) {
    const values = await getUserSdwtProdValues(normalizedLineId)
    if (values.length === 0) {
      return { filters, params, earlyEmpty: true }
    }
    const placeholders = values.map(() => "?").join(", ")
    filters.push(`\`${userSdwtProdColumn}\` IN (${placeholders})`)
    params.push(...values)
    return { filters, params, earlyEmpty: false }
  }

  const lineIdColumn = findColumn(columnNames, "line_id")
  if (lineIdColumn) {
    filters.push(`\`${lineIdColumn}\` = ?`)
    params.push(normalizedLineId)
  }

  return { filters, params, earlyEmpty: false }
}
