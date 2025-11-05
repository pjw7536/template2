// src/features/line-dashboard/components/data-table/column-defs/alignment.js
import { isNumeric } from "./sorting"

const ALIGNMENT_VALUES = new Set(["left", "center", "right"])

// 문자열 입력을 소문자로 정리하고 허용되는 값일 때만 사용합니다.
export function normalizeAlignment(value, fallback = "left") {
  if (typeof value !== "string") return fallback
  const lowered = value.toLowerCase()
  return ALIGNMENT_VALUES.has(lowered) ? lowered : fallback
}

// 숫자/ID 패턴 등을 기준으로 기본 정렬 방향을 추론합니다.
export function inferDefaultAlignment(colKey, sampleValue) {
  if (typeof sampleValue === "number") return "right"
  if (isNumeric(sampleValue)) return "right"
  if (colKey && /(_?id|count|qty|amount|number)$/i.test(colKey)) return "right"
  return "left"
}

// 추론값에 사용자가 지정한 설정을 덮어써 최종 정렬 정보를 돌려줍니다.
export function resolveAlignment(colKey, config, sampleValue) {
  const inferred = inferDefaultAlignment(colKey, sampleValue)
  const cellAlignment = normalizeAlignment(config.cellAlign?.[colKey], inferred)
  const headerAlignment = normalizeAlignment(config.headerAlign?.[colKey], cellAlignment)
  return { cell: cellAlignment, header: headerAlignment }
}
