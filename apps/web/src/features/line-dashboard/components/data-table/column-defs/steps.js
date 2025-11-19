// src/features/line-dashboard/components/data-table/column-defs/steps.js
// 스텝 관련 컬럼을 하나의 process_flow 컬럼으로 통합하기 위한 도우미입니다.
import { STEP_COLUMN_KEY_SET } from "../utils/constants"
import { renderMetroStepFlow } from "../utils/formatters.jsx"
import { resolveAlignment } from "./alignment"
import { resolveColumnSizes } from "./dynamicWidth"

// 원본 컬럼 배열에서 스텝 관련 키와 인덱스를 추출합니다.
export function pickStepColumnsWithIndex(columns) {
  return columns
    .map((key, index) => ({ key, index }))
    .filter(({ key }) => STEP_COLUMN_KEY_SET.has(key))
}

// main_step 또는 metro_steps가 있다면 통합 컬럼을 생성합니다.
export function shouldCombineSteps(stepCols) {
  if (!stepCols.length) return false
  return (
    stepCols.some(({ key }) => key === "main_step") ||
    stepCols.some(({ key }) => key === "metro_steps")
  )
}

function getSampleValueForColumns(row, columns) {
  if (!row || typeof row !== "object" || !Array.isArray(columns)) return undefined
  for (const { key } of columns) {
    if (row[key] !== undefined) return row[key]
  }
  return undefined
}

// 스텝 통합 컬럼 정의를 실제로 생성합니다.
export function makeStepFlowColumn(stepCols, label, config, firstRow) {
  const sample = getSampleValueForColumns(firstRow, stepCols)
  const alignment = resolveAlignment("process_flow", config, sample)
  const { size, minSize, maxSize } = resolveColumnSizes("process_flow", config)

  return {
    id: "process_flow",
    header: () => label,
    accessorFn: (row) => row?.["main_step"] ?? row?.["metro_steps"] ?? null,
    cell: (info) => renderMetroStepFlow(info.row.original),
    enableSorting: false,
    meta: { isEditable: false, alignment },
    size,
    minSize,
    maxSize,
  }
}
