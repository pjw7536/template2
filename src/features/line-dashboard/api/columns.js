import { DATE_COLUMN_CANDIDATES } from "./constants"

// 데이터베이스가 내려준 컬럼 이름 배열에서 원하는 키를 찾아줍니다.
export function findColumn(columnNames, target) {
  const list = Array.isArray(columnNames) ? columnNames : []
  const targetLower = String(target ?? "").toLowerCase()

  for (const name of list) {
    if (typeof name !== "string") continue
    if (name.toLowerCase() === targetLower) return name
  }
  return null
}

// 날짜/시간 컬럼 후보 목록을 순서대로 검사해 가장 먼저 찾은 컬럼 이름을 돌려줍니다.
export function pickBaseTimestampColumn(columnNames) {
  for (const candidate of DATE_COLUMN_CANDIDATES) {
    const found = findColumn(columnNames, candidate)
    if (found) return found
  }
  return null
}
