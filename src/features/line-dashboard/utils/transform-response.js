// src/features/line-dashboard/utils/transform-response.js
// 서버 응답을 테이블 컴포넌트가 바로 쓸 수 있는 안전한 형태로 바꿔 줍니다.
export function normalizeTablePayload(payload, defaults) {
  const { table: defaultTable, from: defaultFrom, to: defaultTo } = defaults

  if (!payload || typeof payload !== "object") {
    return {
      table: defaultTable,
      from: defaultFrom,
      to: defaultTo,
      rowCount: 0,
      columns: [],
      rows: [],
    }
  }

  const normalizedColumns = Array.isArray(payload.columns)
    ? payload.columns.filter((value) => typeof value === "string")
    : []

  const normalizedRows = Array.isArray(payload.rows)
    ? payload.rows
        .filter((row) => row && typeof row === "object")
        .map((row) => ({ ...row }))
    : []

  const rowCountRaw = Number(payload.rowCount)
  const normalizedRowCount = Number.isFinite(rowCountRaw) ? rowCountRaw : normalizedRows.length

  const normalizedFrom = typeof payload.from === "string" ? payload.from : null
  const normalizedTo = typeof payload.to === "string" ? payload.to : null
  const normalizedTable = typeof payload.table === "string" ? payload.table : null

  return {
    table: normalizedTable,
    from: normalizedFrom,
    to: normalizedTo,
    rowCount: normalizedRowCount,
    columns: normalizedColumns,
    rows: normalizedRows,
  }
}

// 설비 ID와 챔버 ID를 보기 좋은 하나의 문자열로 합쳐 줍니다.
export function composeEqpChamber(eqpId, chamberIds) {
  const a = (eqpId ?? "").toString().trim()
  const b = (chamberIds ?? "").toString().trim()
  if (a && b) return `${a}-${b}`
  if (a) return a
  if (b) return b
  return ""
}
