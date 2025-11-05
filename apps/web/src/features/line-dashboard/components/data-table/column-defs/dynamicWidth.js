// src/features/line-dashboard/components/data-table/column-defs/dynamicWidth.js
import {
  DEFAULT_BOOL_ICON_WIDTH,
  DEFAULT_DATE_WIDTH,
  DEFAULT_ID_WIDTH,
  DEFAULT_MAX_WIDTH,
  DEFAULT_MIN_WIDTH,
  DEFAULT_NUMBER_WIDTH,
  DEFAULT_PROCESS_FLOW_WIDTH,
  DEFAULT_TEXT_WIDTH,
} from "./constants"
import { computeProcessFlowWidthFromRows } from "./processFlow"
import { computeAutoTextWidthFromRows } from "./textWidth"
import { isNumeric, tryDate } from "./sorting"

// 실 데이터(행) 기반으로 자동 폭 힌트를 계산합니다.
export function computeDynamicWidthHints(rows, config) {
  if (!Array.isArray(rows) || rows.length === 0) return {}
  const hints = {}

  if (config?.autoWidth?.process_flow) {
    const width = computeProcessFlowWidthFromRows(rows)
    if (width !== null) hints.process_flow = width
  }

  const textKeys = [
    "sdwt_prod",
    "ppid",
    "sample_type",
    config?.autoWidth?.knox_id ? "knox_id" : "knoxid",
    "user_sdwt_prod",
  ]

  for (const key of textKeys) {
    if (!key) continue
    if (config?.autoWidth?.[key]) {
      const width = computeAutoTextWidthFromRows(rows, key, { max: 720, cellPadding: 40 })
      if (width !== null) hints[key] = width
    }
  }

  return hints
}

// 기본적으로 어떤 폭을 줄지 간단한 규칙으로 추정합니다.
function inferDefaultWidth(colKey, sampleValue) {
  if (colKey === "process_flow") return DEFAULT_PROCESS_FLOW_WIDTH
  if (colKey === "needtosend" || colKey === "send_jira") return DEFAULT_BOOL_ICON_WIDTH
  if (/(_?id)$/i.test(colKey)) return DEFAULT_ID_WIDTH
  if (tryDate(sampleValue)) return DEFAULT_DATE_WIDTH
  if (isNumeric(sampleValue)) return DEFAULT_NUMBER_WIDTH
  return DEFAULT_TEXT_WIDTH
}

function toSafeNumber(value, fallback) {
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric > 0 ? numeric : fallback
}
// 사용자 설정 + 자동 힌트 + 샘플 값을 종합해 size/min/max를 계산합니다.
export function resolveColumnSizes(colKey, config, sampleValue, dynamicWidthHints) {
  const dynamicWidth = dynamicWidthHints?.[colKey]
  const baseWidth = dynamicWidth !== undefined ? dynamicWidth : config.width?.[colKey]
  const inferredWidth = inferDefaultWidth(colKey, sampleValue)
  const size = toSafeNumber(baseWidth, inferredWidth)

  const minSize = Math.min(Math.max(DEFAULT_MIN_WIDTH, Math.floor(size * 0.5)), size)
  const maxSize = Math.max(DEFAULT_MAX_WIDTH, Math.ceil(size * 2))
  return { size, minSize, maxSize }
}
