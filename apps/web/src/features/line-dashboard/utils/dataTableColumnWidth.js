// src/features/line-dashboard/utils/dataTableColumnWidth.js
import { DEFAULT_MIN_WIDTH, DEFAULT_WIDTH } from "./dataTableColumnConstants"

// config.width 값을 기반으로 컬럼 폭을 계산합니다.
export function resolveColumnSize(colKey, config) {
  const configuredWidth = Number(config.width?.[colKey])
  const size =
    Number.isFinite(configuredWidth) && configuredWidth > 0
      ? configuredWidth
      : DEFAULT_WIDTH

  return { size, minSize: DEFAULT_MIN_WIDTH, maxSize: Number.MAX_SAFE_INTEGER }
}
