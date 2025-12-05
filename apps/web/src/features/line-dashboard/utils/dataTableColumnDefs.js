// src/features/line-dashboard/utils/dataTableColumnDefs.js
// 복잡한 컬럼 정의 로직을 작은 모듈로 나눠 관리하기 위한 래퍼입니다.
// createColumnDefs 함수는 여전히 한 번에 컬럼 배열을 만들어 주지만,
// 세부 정렬/폭/정렬방향 계산은 column-defs 하위 파일에 위임합니다.

import { mergeConfig } from "./dataTableColumnConfig"
import { resolveAlignment } from "./dataTableColumnAlignment"
import { getSortingFnForKey } from "./dataTableColumnSorting"
import { renderCellByKey } from "../components/DataTableColumnRenderers"
import {
  makeStepFlowColumn,
  pickStepColumnsWithIndex,
  shouldCombineSteps,
} from "./dataTableColumnSteps"
import { resolveColumnSize } from "./dataTableColumnWidth"

// 단일 컬럼 정의 객체를 생성합니다.
function makeColumnDef(colKey, config, sampleValueFromFirstRow) {
  const label = config.labels?.[colKey] ?? colKey
  const enableSorting =
    typeof config.sortable?.[colKey] === "boolean"
      ? config.sortable[colKey]
      : colKey !== "defect_url" && colKey !== "jira_key"

  const sortingFn = enableSorting
    ? getSortingFnForKey(colKey, config, sampleValueFromFirstRow)
    : undefined

  const { size, minSize, maxSize } = resolveColumnSize(colKey, config)
  const alignment = resolveAlignment(colKey, config, sampleValueFromFirstRow)

  return {
    id: colKey,
    header: () => label,
    accessorFn: (row) => row?.[colKey],
    meta: {
      isEditable: colKey === "comment" || colKey === "needtosend",
      alignment,
    },
    cell: (info) => renderCellByKey(colKey, info),
    enableSorting,
    sortingFn,
    size,
    minSize,
    maxSize,
  }
}

// 데이터 테이블에서 사용할 전체 컬럼 정의 배열을 생성합니다.
export function createColumnDefs(rawColumns, userConfig, firstRowForTypeGuess) {
  const config = mergeConfig(userConfig)
  const columns = Array.isArray(rawColumns) ? rawColumns : []

  const stepCols = pickStepColumnsWithIndex(columns)
  const combineSteps = shouldCombineSteps(stepCols)

  const stepKeySet = new Set(stepCols.map(({ key }) => key))
  const baseKeys = combineSteps ? columns.filter((key) => !stepKeySet.has(key)) : [...columns]

  const defs = baseKeys.map((key) => {
    const sample = firstRowForTypeGuess ? firstRowForTypeGuess?.[key] : undefined
    return makeColumnDef(key, config, sample)
  })

  if (combineSteps) {
    const headerText = config.labels?.process_flow ?? config.processFlowHeader ?? "process_flow"
    const stepFlowCol = makeStepFlowColumn(stepCols, headerText, config, firstRowForTypeGuess)

    const insertionIndex = stepCols.length
      ? Math.min(...stepCols.map(({ index }) => index))
      : defs.length

    defs.splice(Math.min(Math.max(insertionIndex, 0), defs.length), 0, stepFlowCol)
  }

  const order = Array.isArray(config.order) ? config.order : null
  if (order && order.length > 0) {
    const idSet = new Set(defs.map((d) => d.id))
    const head = order.filter((id) => idSet.has(id))
    const tail = defs.map((d) => d.id).filter((id) => !head.includes(id))
    const finalIds = [...head, ...tail]

    finalIds.forEach((id, i) => {
      const idx = defs.findIndex((d) => d.id === id)
      if (idx !== -1 && idx !== i) {
        const [moved] = defs.splice(idx, 1)
        defs.splice(i, 0, moved)
      }
    })
  }

  return defs
}
