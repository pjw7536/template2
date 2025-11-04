import { runQuery } from "@/lib/db"
import { LINE_SDWT_TABLE_NAME } from "./constants"
import { findColumn } from "./columns"

/**
 * Builds dynamic WHERE clause snippets for line-based filtering.
 *
 * Returns
 *  - filters: array of SQL snippets
 *  - params: bound parameter values for the snippets
 *  - earlyEmpty: when true the caller should immediately return an empty
 *    response because no records can match
 */
export async function buildLineFilters(columnNames, normalizedLineId) {
  const filters = []
  const params = []

  if (!normalizedLineId) {
    return { filters, params, earlyEmpty: false }
  }

  const userSdwtProdColumn = findColumn(columnNames, "user_sdwt_prod")
  const lineIdColumn = findColumn(columnNames, "line_id")

  if (userSdwtProdColumn) {
    const mappingRows = await runQuery(
      `
        SELECT DISTINCT user_sdwt_prod
        FROM \`${LINE_SDWT_TABLE_NAME}\`
        WHERE line_id = ?
          AND user_sdwt_prod IS NOT NULL
          AND user_sdwt_prod <> ''
      `,
      [normalizedLineId]
    )

    const userSdwtProds = Array.from(
      new Set(
        mappingRows
          .map((row) =>
            typeof row?.user_sdwt_prod === "string" ? row.user_sdwt_prod.trim() : ""
          )
          .filter((value) => value.length > 0)
      )
    )

    if (userSdwtProds.length === 0) {
      return { filters, params, earlyEmpty: true }
    }

    filters.push(`\`${userSdwtProdColumn}\` IN (${userSdwtProds.map(() => "?").join(", ")})`)
    params.push(...userSdwtProds)
    return { filters, params, earlyEmpty: false }
  }

  if (lineIdColumn) {
    filters.push(`\`${lineIdColumn}\` = ?`)
    params.push(normalizedLineId)
    return { filters, params, earlyEmpty: false }
  }

  return { filters, params, earlyEmpty: false }
}
